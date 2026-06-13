"""국민연금(NPS) 보유종목 적재 — odcloud OpenAPI 자동화.

진입점:
    POST /admin/seed/nps  →  seed_nps(db_url, api_key=...)

소스(odcloud, data.go.kr serviceKey):
  - held : 국내주식 투자정보(3070507, 전체보유)   — 연1회, `종목명`.     nps_holding='held'.
  - major: 대량보유주식 보고내역(15106890, 5%+)     — 분기, `발행기관명`. nps_holding='major'(held 덮어씀).

흐름:
  1. discovery — infuser OAS(infuser.odcloud.kr/oas/docs)에서 최신 uddi path 선택(summary 날짜 max).
     OAS 실패 시 검증된 fallback uddi 상수 사용(soft dependency).
  2. fingerprint skip — seed_source_state(source='nps_held'/'nps_major', 각 uddi+as_of 해시).
     둘 다 동일하면 전체 skip. 하나라도 변경되면 양쪽 fetch + 조인트 재적용(reset 이 held 를 지우므로).
  3. fetch — api.odcloud.kr 페이지네이션(perPage 1200, totalCount 경계).
  4. 매칭 — 종목명 정제(부기 주석 제거) 후 stocks_repo.search 로 ticker 해소. 실패분은 nps_unmatched.
  5. apply(트랜잭션) — 전체 nps_holding NULL 리셋 → held set → major 덮어쓰기 → nps_as_of(held 기준일).
     held 0건이면 빈스냅샷 가드로 전체 abort(리셋 안 함).

NPS 응답에 종목코드가 없어 종목명→ticker 매칭이 필요하며, 시점 사명 드리프트로 ~5% 미매칭은
nps_unmatched 큐로 남긴다. 판정 정정 배경은 docs/decisions.md 2026-06-02.
"""
from __future__ import annotations

import hashlib
import logging
import re
from collections import defaultdict
from datetime import date
from typing import Any

import asyncpg
import httpx

from invest_note_api.config import Settings
from invest_note_api.db_ops import stocks_repo
from invest_note_api.domain.trade_types import DEFAULT_COUNTRY
from invest_note_api.external.constants import USER_AGENT
from invest_note_api.external.provider_registry import resolve_chain
from invest_note_api.services.stock_seed import (
    get_source_fingerprint,
    set_source_fingerprint,
    upsert_aliases,
)

logger = logging.getLogger(__name__)

_OAS_URL = "https://infuser.odcloud.kr/oas/docs"
_API_BASE = "https://api.odcloud.kr/api"
_PER_PAGE = 1200

# 데이터셋 정의. fallback_path/fallback_as_of 는 2026-06-02 실호출로 확인한 최신값 —
# OAS discovery 실패 시에만 사용(soft dependency). OAS 가 정상이면 최신 uddi 를 자동 추적한다.
_HELD = {
    "namespace": "3070507",
    "name_field": "종목명",
    "source": "nps_held",
    "level": "held",
    "fallback_path": "/3070507/v1/uddi:cc757223-fdc0-45b2-a617-dcbecec3fe1f",
    "fallback_as_of": "20241231",
}
_MAJOR = {
    "namespace": "15106890",
    "name_field": "발행기관명",
    "source": "nps_major",
    "level": "major",
    "fallback_path": "/15106890/v1/uddi:1f30a355-f5be-4b09-81c1-a09ba1f4e234",
    "fallback_as_of": "20251231",
}

# NPS 종목명 후행 부기 주석 — '(배당)'/'(무상)'/'(전환)'/'무상(보)' 등. 매칭 전 제거.
_ANNOTATION_RE = re.compile(r"\s*(?:무상|배당|유상)?\([^)]*\)\s*$")
# major(발행기관명)에만 붙는 접두 법인격 표기 '(주)'/'㈜'. 접미 '(주)'는 _ANNOTATION_RE 가 처리.
_CORP_PREFIX_RE = re.compile(r"^\s*(?:\(주\)|㈜)\s*")


def clean_name(name: str) -> str:
    """NPS 종목명 정제. '셀트리온(배당)'→'셀트리온', '동원산업무상(보)'→'동원산업', '(주)녹십자'→'녹십자'."""
    s = _CORP_PREFIX_RE.sub("", name or "")
    return _ANNOTATION_RE.sub("", s).strip()


def _to_date(yyyymmdd: str) -> date | None:
    """'YYYYMMDD' → date. 파싱 불가면 None."""
    try:
        return date(int(yyyymmdd[:4]), int(yyyymmdd[4:6]), int(yyyymmdd[6:8]))
    except (ValueError, TypeError, IndexError):
        return None


def _fingerprint(path: str, as_of: str) -> str:
    """스냅샷 식별자 — uddi path + 기준일. 불변 스냅샷이라 이 둘이 같으면 내용도 동일."""
    return hashlib.sha256(f"{path}|{as_of}".encode()).hexdigest()


# ─────────────────────────── discovery ───────────────────────────


def _latest_path(oas: dict, fallback: str) -> tuple[str, str]:
    """OAS paths 에서 summary 의 날짜(YYYYMMDD)가 최신인 uddi path 선택.

    summary 예: '국민연금공단_국내주식 투자정보_20241231'. 날짜 없는 path 는 '0' 으로 밀린다.
    반환: (path, as_of 'YYYYMMDD'). 후보 없으면 (fallback, '').
    """
    best_path: str | None = None
    best_date = ""
    for path, item in (oas.get("paths") or {}).items():
        summary = (item.get("get") or {}).get("summary", "")
        dates = re.findall(r"20\d{6}", summary)
        dk = max(dates) if dates else "0"
        if best_path is None or dk > best_date:
            best_path, best_date = path, dk
    if best_path is None:
        return fallback, ""
    return best_path, (best_date if best_date != "0" else "")


async def discover(client: httpx.AsyncClient, ds: dict) -> tuple[str, str]:
    """최신 (uddi_path, as_of 'YYYYMMDD'). infuser OAS 우선, 실패 시 fallback 상수."""
    try:
        res = await client.get(_OAS_URL, params={"namespace": f"{ds['namespace']}/v1"})
        res.raise_for_status()
        path, as_of = _latest_path(res.json(), ds["fallback_path"])
        if path and as_of:
            return path, as_of
        logger.warning("NPS discovery(%s) — OAS 에 날짜 미발견, fallback 사용", ds["source"])
    except (httpx.HTTPError, ValueError) as e:
        logger.warning("NPS discovery(%s) 실패(%s) — fallback uddi 사용", ds["source"], type(e).__name__)
    return ds["fallback_path"], ds["fallback_as_of"]


# ─────────────────────────── fetch (api.odcloud.kr) ───────────────────────────


def _extract_odcloud(payload: dict) -> tuple[list[dict], int]:
    """odcloud 응답 envelope({totalCount, data[]})에서 (data, totalCount) 추출."""
    data = payload.get("data")
    total = payload.get("totalCount") or 0
    return (data if isinstance(data, list) else []), int(total)


async def fetch_rows(client: httpx.AsyncClient, api_key: str, path: str) -> list[dict]:
    """uddi path 의 전체 행을 페이지네이션으로 수신.

    serviceKey 가 예외 메시지(URL 포함)로 로그에 새지 않도록 status code 만 담은 RuntimeError 로 정제한다.
    """
    rows: list[dict] = []
    page = 1
    while True:
        try:
            res = await client.get(
                f"{_API_BASE}{path}",
                params={"serviceKey": api_key, "page": page, "perPage": _PER_PAGE, "returnType": "JSON"},
            )
            res.raise_for_status()
        except httpx.HTTPStatusError as e:
            raise RuntimeError(f"NPS fetch HTTP {e.response.status_code}") from None
        except httpx.HTTPError as e:
            raise RuntimeError(f"NPS fetch 실패: {type(e).__name__}") from None
        data, total = _extract_odcloud(res.json())
        rows.extend(data)
        if not data or len(rows) >= total:
            break
        page += 1
    return rows


# ─────────────────────────── 매칭 ───────────────────────────


async def resolve_tickers(
    conn: Any, names: list[str], *, country_code: str = DEFAULT_COUNTRY
) -> tuple[set[str], list[str]]:
    """NPS 원본 종목명 리스트 → (매칭된 ticker 집합, 미매칭 원본명 리스트).

    정제(clean_name) 후 stocks_repo.search 로 1건 해소(stocks + stock_aliases 통합 검색).
    import 자동매칭과 동일한 경로라 trgm 부분일치도 채택될 수 있다 — 미매칭은 reconcile 큐로 남긴다.
    """
    matched: set[str] = set()
    unmatched: list[str] = []
    for raw in names:
        q = clean_name(raw)
        results = (
            await stocks_repo.search(conn, q, country_code=country_code, limit=1, min_len=2)
            if q
            else []
        )
        if results:
            matched.add(results[0]["code"])
        else:
            unmatched.append(raw)
    return matched, unmatched


# ─────────────────────────── apply ───────────────────────────


async def apply_snapshot(
    conn: Any,
    held_rows: list[dict],
    held_as_of: str,
    major_rows: list[dict],
    major_as_of: str,
    *,
    country_code: str = DEFAULT_COUNTRY,
) -> dict:
    """트랜잭션으로 nps_holding 전면 재계산. held 0건이면 빈스냅샷 가드로 skip.

    nps_as_of 는 held(3070507) 기준일로 통일(major 는 보조 플래그).
    """
    if not held_rows:
        logger.warning("NPS held 스냅샷 0건 — 전체 리셋 방지 위해 적재 skip")
        return {"skipped": "empty_held"}

    held_names = [r.get(_HELD["name_field"], "") for r in held_rows]
    major_names = [r.get(_MAJOR["name_field"], "") for r in major_rows]
    as_of_date = _to_date(held_as_of)
    major_as_of_date = _to_date(major_as_of)

    async with conn.transaction():
        held_tickers, held_unmatched = await resolve_tickers(conn, held_names, country_code=country_code)
        major_tickers, major_unmatched = await resolve_tickers(conn, major_names, country_code=country_code)

        await stocks_repo.reset_nps_holding(conn, country_code=country_code)
        await stocks_repo.set_nps_holding(conn, held_tickers, "held", as_of_date, country_code=country_code)
        await stocks_repo.set_nps_holding(conn, major_tickers, "major", as_of_date, country_code=country_code)

        unmatched_rows = [
            {"nps_name": n, "nps_as_of": as_of_date, "holding_level": "held"}
            for n in held_unmatched
            if as_of_date is not None
        ] + [
            {"nps_name": n, "nps_as_of": major_as_of_date, "holding_level": "major"}
            for n in major_unmatched
            if major_as_of_date is not None
        ]
        await stocks_repo.upsert_nps_unmatched(conn, unmatched_rows)

    return {
        "held_matched": len(held_tickers),
        "held_unmatched": len(held_unmatched),
        "major_matched": len(major_tickers),
        "major_unmatched": len(major_unmatched),
        "nps_as_of": held_as_of,
    }


# ─────────────────────────── 진입점 ───────────────────────────


async def _seed_nps_odcloud(db_url: str, *, api_key: str, country_code: str = DEFAULT_COUNTRY) -> dict:
    """odcloud 공급자 — discovery → fingerprint skip → fetch → apply. 통계 dict 반환."""
    if not api_key:
        logger.warning("NPS 적재 — DATA_GO_KR_API_KEY 미설정, skip")
        return {"skipped": "no_api_key"}

    conn = await asyncpg.connect(db_url, statement_cache_size=0)
    try:
        # 다중 인스턴스 동시 실행 가드(seed_stocks 와 독립 lock).
        if not await conn.fetchval("select pg_try_advisory_lock(hashtext('seed_nps'))"):
            logger.info("NPS 적재 — 다른 인스턴스 실행 중, skip")
            return {"skipped": "locked"}

        async with httpx.AsyncClient(headers={"User-Agent": USER_AGENT}, timeout=30) as client:
            held_path, held_as_of = await discover(client, _HELD)
            major_path, major_as_of = await discover(client, _MAJOR)

            held_fp = _fingerprint(held_path, held_as_of)
            major_fp = _fingerprint(major_path, major_as_of)
            held_unchanged = held_fp == await get_source_fingerprint(conn, _HELD["source"])
            major_unchanged = major_fp == await get_source_fingerprint(conn, _MAJOR["source"])
            if held_unchanged and major_unchanged:
                logger.info("NPS 적재 — 양 스냅샷 변경 없음(held %s / major %s), skip", held_as_of, major_as_of)
                return {"skipped": "unchanged"}

            # 둘 중 하나만 바뀌어도 reset 이 held 를 지우므로 양쪽 모두 fetch + 조인트 재적용.
            held_rows = await fetch_rows(client, api_key, held_path)
            major_rows = await fetch_rows(client, api_key, major_path)

        stats = await apply_snapshot(
            conn, held_rows, held_as_of, major_rows, major_as_of, country_code=country_code
        )
        if stats.get("skipped"):
            return stats

        # 적재 성공 후에만 두 fingerprint 갱신(실패 시 다음 run 이 멱등 재적용).
        await set_source_fingerprint(conn, _HELD["source"], held_fp, len(held_rows))
        await set_source_fingerprint(conn, _MAJOR["source"], major_fp, len(major_rows))
        logger.info("NPS 적재 완료 — %s", stats)
        return stats
    finally:
        await conn.close()


# NPS 공급자 registry — 현재 odcloud 단일(registry-of-one). 대체 공급처가 생기면 등록 후
# env NPS_PROVIDER 변경만으로 전환 가능.
_NPS_REGISTRY = {"odcloud": _seed_nps_odcloud}


async def seed_nps(
    db_url: str,
    *,
    api_key: str,
    country_code: str = DEFAULT_COUNTRY,
    provider: str = "odcloud",
) -> dict:
    """NPS 보유 적재 — env NPS_PROVIDER 로 선택된 공급자에 위임."""
    fetch = resolve_chain([provider], _NPS_REGISTRY, domain="nps")[0]
    return await fetch(db_url, api_key=api_key, country_code=country_code)


# ─────────────────────────── reconcile (과거사명 수동 매핑) ───────────────────────────


async def reconcile_nps_unmatched(
    db_url: str, *, country_code: str = DEFAULT_COUNTRY
) -> dict:
    """관리자가 resolved_ticker 를 채운 nps_unmatched 를 해소.

    NPS seed 는 fingerprint-skip(스냅샷 연1회)이라 다음 적재에 위임할 수 없어 자기완결로 처리한다.
    행마다(단일 트랜잭션): ① resolved_ticker 가 stocks 에 존재하는지 검증(없으면 skip+행 보존)
    ② stock_aliases 에 clean_name(nps_name) 별칭 등록(재발 방지 보험) ③ set_nps_holding 즉시 반영
    ④ 해소 행 삭제. 통계 dict 반환.
    """
    conn = await asyncpg.connect(db_url, statement_cache_size=0)
    try:
        rows = await stocks_repo.fetch_resolved_unmatched(conn, country_code=country_code)
        if not rows:
            return {"reconciled": 0, "aliases": 0, "skipped_no_stock": 0}

        async with conn.transaction():
            # ① stocks 에 실존하는 resolved_ticker 만 처리(상폐/오타는 skip → 행 보존).
            tickers = {r["resolved_ticker"] for r in rows}
            present = set(
                await conn.fetchval(
                    "select coalesce(array_agg(ticker), '{}') from stocks "
                    "where country_code = $1 and ticker = any($2::text[])",
                    country_code,
                    list(tickers),
                )
            )

            # ② 별칭 등록(보험). upsert_aliases 의 existing 필터가 present 와 동일하게 동작.
            aliases = [
                {"ticker": r["resolved_ticker"], "alias": clean_name(r["nps_name"]), "source": "nps_reconcile"}
                for r in rows
                if r["resolved_ticker"] in present and clean_name(r["nps_name"])
            ]
            n_alias = await upsert_aliases(conn, aliases, country_code=country_code)

            # nps_as_of 는 seed(apply_snapshot)와 동일하게 held 기준일로 통일(major 는 보조 플래그).
            # 행별 nps_as_of(major 행은 major 기준일)를 그대로 쓰면 seed-매칭분과 날짜가 갈리므로,
            # 현재 stocks 에 박힌 기준일(seed 통일값)을 조회해 사용한다.
            canonical_as_of = await conn.fetchval(
                "select max(nps_as_of) from stocks where country_code = $1 and nps_holding is not null",
                country_code,
            )

            # ③ nps_holding 즉시 반영 — level 그룹화. held 먼저→major 덮어쓰기 순서 유지.
            groups: dict[str, set[str]] = defaultdict(set)
            resolved_keys: list[tuple] = []
            for r in rows:
                if r["resolved_ticker"] not in present:
                    continue
                groups[r["holding_level"]].add(r["resolved_ticker"])
                resolved_keys.append((r["nps_name"], r["nps_as_of"]))
            for level in sorted(groups):  # 'held' < 'major'
                await stocks_repo.set_nps_holding(
                    conn, groups[level], level, canonical_as_of, country_code=country_code
                )

            # ④ 해소 행 삭제(stale 방지). present 아닌 행은 남겨 재확인 유도.
            await stocks_repo.delete_nps_unmatched(conn, resolved_keys)

        stats = {
            "reconciled": len(resolved_keys),
            "aliases": n_alias,
            "skipped_no_stock": len(rows) - len(resolved_keys),
        }
        logger.info("NPS reconcile 완료 — %s", stats)
        return stats
    finally:
        await conn.close()


def main() -> None:
    """CLI 진입점 — `cd api && poetry run python -m invest_note_api.services.nps_seed`.

    reconcile(관리자 resolved_ticker 해소) 선행 후 seed_nps — admin /seed/nps 래퍼와 동일 순서.
    reconcile 이 과거사명을 별칭(nps_reconcile)으로 등록하면 이어지는 seed 매칭이 자동 해소해
    같은 종목이 nps_unmatched 에 다시 쌓이지 않는다. reconcile 실패는 seed 를 막지 않는다(독립 로깅).
    """
    import asyncio

    settings = Settings()
    db_url = settings.database_url.replace("postgresql+asyncpg://", "postgresql://")
    if not db_url:
        raise SystemExit("database_url 미설정")
    logging.basicConfig(level=logging.INFO)

    async def _run() -> None:
        try:
            print(await reconcile_nps_unmatched(db_url))
        except Exception:
            logger.exception("nps_seed CLI 선행 reconcile 실패 — seed 는 계속 진행")
        print(
            await seed_nps(
                db_url, api_key=settings.data_go_kr_api_key, provider=settings.nps_provider
            )
        )

    asyncio.run(_run())


if __name__ == "__main__":
    main()
