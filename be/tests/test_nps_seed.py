"""nps_seed — discovery·fetch·이름정제·매칭·apply·fingerprint skip·admin 토큰 테스트.

네트워크는 httpx.MockTransport 로 차단. DB 는 FakeConn + repo 함수 monkeypatch 로 대체(실DB 미사용).
"""
from __future__ import annotations

import httpx
import pytest

from invest_note_api.services import nps_seed


def _mock_client(handler) -> httpx.AsyncClient:
    return httpx.AsyncClient(transport=httpx.MockTransport(handler))


class FakeConn:
    """apply/seed_nps 테스트용 최소 conn. transaction()·fetchval()·close() 만 제공."""

    def __init__(self, fingerprints: dict | None = None):
        self.fps = fingerprints or {}

    def transaction(self):
        conn = self

        class _Tx:
            async def __aenter__(self):
                return conn

            async def __aexit__(self, *exc):
                return False

        return _Tx()

    async def fetchval(self, query: str, *args):
        if "advisory_lock" in query:
            return True
        if "seed_source_state" in query:
            return self.fps.get(args[0])
        return None

    async def close(self):
        pass


# ─────────────────────────── 순수 함수 ───────────────────────────


def test_clean_name_strips_annotations():
    assert nps_seed.clean_name("셀트리온(배당)") == "셀트리온"
    assert nps_seed.clean_name("동원산업무상(보)") == "동원산업"
    assert nps_seed.clean_name("아모레G3우(전환)") == "아모레G3우"
    assert nps_seed.clean_name("삼성전자") == "삼성전자"  # 주석 없으면 그대로


def test_latest_path_picks_max_date():
    oas = {
        "paths": {
            "/x/uddi:old": {"get": {"summary": "국내주식 투자정보_20231231"}},
            "/x/uddi:new": {"get": {"summary": "국내주식 투자정보_20241231"}},
            "/x/uddi:nodate": {"get": {"summary": "메타 정보(날짜없음)"}},
        }
    }
    path, as_of = nps_seed._latest_path(oas, "/fallback")
    assert path == "/x/uddi:new"
    assert as_of == "20241231"


def test_latest_path_empty_returns_fallback():
    assert nps_seed._latest_path({"paths": {}}, "/fb") == ("/fb", "")


def test_fingerprint_distinguishes_snapshot():
    assert nps_seed._fingerprint("/p", "20241231") == nps_seed._fingerprint("/p", "20241231")
    assert nps_seed._fingerprint("/p", "20241231") != nps_seed._fingerprint("/p", "20251231")
    assert nps_seed._fingerprint("/p1", "20241231") != nps_seed._fingerprint("/p2", "20241231")


def test_extract_odcloud():
    data, total = nps_seed._extract_odcloud({"totalCount": 3, "data": [{"a": 1}]})
    assert total == 3 and data == [{"a": 1}]
    assert nps_seed._extract_odcloud({}) == ([], 0)


# ─────────────────────────── fetch_rows ───────────────────────────


async def test_fetch_rows_paginates_to_totalcount():
    pages = {
        "1": {"totalCount": 3, "data": [{"종목명": "삼성전자"}, {"종목명": "SK하이닉스"}]},
        "2": {"totalCount": 3, "data": [{"종목명": "기아"}]},
    }

    def handler(req: httpx.Request) -> httpx.Response:
        return httpx.Response(200, json=pages[req.url.params["page"]])

    async with _mock_client(handler) as client:
        rows = await nps_seed.fetch_rows(client, "key", "/3070507/v1/uddi:x")
    assert [r["종목명"] for r in rows] == ["삼성전자", "SK하이닉스", "기아"]


async def test_fetch_rows_sanitizes_servicekey_on_error():
    def handler(req: httpx.Request) -> httpx.Response:
        return httpx.Response(500, json={})

    async with _mock_client(handler) as client:
        with pytest.raises(RuntimeError) as exc:
            await nps_seed.fetch_rows(client, "SECRET_KEY", "/x")
    assert "SECRET_KEY" not in str(exc.value)
    assert "500" in str(exc.value)


# ─────────────────────────── discover ───────────────────────────


async def test_discover_falls_back_on_oas_error():
    def handler(req: httpx.Request) -> httpx.Response:
        return httpx.Response(503, json={})

    async with _mock_client(handler) as client:
        path, as_of = await nps_seed.discover(client, nps_seed._MAJOR)
    assert path == nps_seed._MAJOR["fallback_path"]
    assert as_of == nps_seed._MAJOR["fallback_as_of"]


# ─────────────────────────── resolve_tickers ───────────────────────────


async def test_resolve_tickers_splits_matched_and_unmatched(monkeypatch):
    table = {"삼성전자": "005930", "기아": "000270"}

    async def fake_search(conn, q, **kw):
        return [{"code": table[q]}] if q in table else []

    monkeypatch.setattr(nps_seed.stocks_repo, "search", fake_search)
    matched, unmatched = await nps_seed.resolve_tickers(
        FakeConn(), ["삼성전자", "셀트리온(배당)", "없는종목"]
    )
    # '셀트리온(배당)' 은 정제돼도 table 에 없어 미매칭, '삼성전자' 만 매칭.
    assert matched == {"005930"}
    assert unmatched == ["셀트리온(배당)", "없는종목"]


# ─────────────────────────── apply_snapshot ───────────────────────────


def _patch_repo(monkeypatch):
    """reset/set/upsert 를 recorder 로 교체. 반환 dict 에 호출 인자 기록."""
    rec = {"reset": 0, "set": [], "unmatched": []}

    async def fake_reset(conn, **kw):
        rec["reset"] += 1
        return 0

    async def fake_set(conn, tickers, level, as_of, **kw):
        rec["set"].append((set(tickers), level))
        return len(tickers)

    async def fake_upsert(conn, rows):
        rec["unmatched"] = rows
        return len(rows)

    monkeypatch.setattr(nps_seed.stocks_repo, "reset_nps_holding", fake_reset)
    monkeypatch.setattr(nps_seed.stocks_repo, "set_nps_holding", fake_set)
    monkeypatch.setattr(nps_seed.stocks_repo, "upsert_nps_unmatched", fake_upsert)
    return rec


async def test_apply_major_precedence_and_unmatched(monkeypatch):
    # 삼성전자=held+major, 기아=held only, POSCO=major only, '없는종목'=held 미매칭.
    table = {"삼성전자": "005930", "기아": "000270", "포스코퓨처엠": "003670"}

    async def fake_search(conn, q, **kw):
        return [{"code": table[q]}] if q in table else []

    monkeypatch.setattr(nps_seed.stocks_repo, "search", fake_search)
    rec = _patch_repo(monkeypatch)

    held_rows = [{"종목명": "삼성전자"}, {"종목명": "기아"}, {"종목명": "없는종목"}]
    major_rows = [{"발행기관명": "삼성전자"}, {"발행기관명": "포스코퓨처엠"}]
    stats = await nps_seed.apply_snapshot(FakeConn(), held_rows, "20241231", major_rows, "20251231")

    assert rec["reset"] == 1
    # set 호출 순서: held 먼저 → major 나중(덮어쓰기). major 가 삼성전자 포함 → 'major' 우선.
    assert rec["set"][0] == ({"005930", "000270"}, "held")
    assert rec["set"][1] == ({"005930", "003670"}, "major")
    assert stats["held_matched"] == 2 and stats["held_unmatched"] == 1
    assert stats["major_matched"] == 2 and stats["major_unmatched"] == 0
    # 미매칭 '없는종목' 은 held as_of 로 큐 적재.
    assert rec["unmatched"] == [
        {"nps_name": "없는종목", "nps_as_of": nps_seed._to_date("20241231"), "holding_level": "held"}
    ]


async def test_apply_empty_held_guard_skips(monkeypatch):
    rec = _patch_repo(monkeypatch)
    stats = await nps_seed.apply_snapshot(FakeConn(), [], "20241231", [{"발행기관명": "X"}], "20251231")
    assert stats == {"skipped": "empty_held"}
    assert rec["reset"] == 0  # 빈 스냅샷 → 리셋조차 안 함


# ─────────────────────────── seed_nps fingerprint skip ───────────────────────────


async def test_seed_nps_skips_when_both_unchanged(monkeypatch):
    async def fake_discover(client, ds):
        return ds["fallback_path"], ds["fallback_as_of"]

    monkeypatch.setattr(nps_seed, "discover", fake_discover)

    async def fake_connect(*a, **kw):
        held_fp = nps_seed._fingerprint(nps_seed._HELD["fallback_path"], nps_seed._HELD["fallback_as_of"])
        major_fp = nps_seed._fingerprint(nps_seed._MAJOR["fallback_path"], nps_seed._MAJOR["fallback_as_of"])
        return FakeConn({"nps_held": held_fp, "nps_major": major_fp})

    monkeypatch.setattr(nps_seed.asyncpg, "connect", fake_connect)

    async def boom(*a, **kw):
        raise AssertionError("fingerprint 동일 시 fetch 하면 안 됨")

    monkeypatch.setattr(nps_seed, "fetch_rows", boom)

    stats = await nps_seed.seed_nps("postgresql://x", api_key="key")
    assert stats == {"skipped": "unchanged"}


async def test_seed_nps_reapplies_when_one_changed(monkeypatch):
    async def fake_discover(client, ds):
        return ds["fallback_path"], ds["fallback_as_of"]

    monkeypatch.setattr(nps_seed, "discover", fake_discover)

    async def fake_connect(*a, **kw):
        # held 만 stored fp 일치, major 는 불일치 → 재적용 경로.
        held_fp = nps_seed._fingerprint(nps_seed._HELD["fallback_path"], nps_seed._HELD["fallback_as_of"])
        return FakeConn({"nps_held": held_fp, "nps_major": "stale"})

    monkeypatch.setattr(nps_seed.asyncpg, "connect", fake_connect)

    async def fake_fetch(client, api_key, path):
        return [{"x": 1}]

    monkeypatch.setattr(nps_seed, "fetch_rows", fake_fetch)

    called = {"apply": False, "fp": []}

    async def fake_apply(conn, *a, **kw):
        called["apply"] = True
        return {"held_matched": 1, "held_unmatched": 0, "major_matched": 1, "major_unmatched": 0}

    async def fake_set_fp(conn, source, fp, n):
        called["fp"].append(source)

    monkeypatch.setattr(nps_seed, "apply_snapshot", fake_apply)
    monkeypatch.setattr(nps_seed, "set_source_fingerprint", fake_set_fp)

    stats = await nps_seed.seed_nps("postgresql://x", api_key="key")
    assert called["apply"] is True
    assert set(called["fp"]) == {"nps_held", "nps_major"}  # 양쪽 fingerprint 갱신
    assert stats["held_matched"] == 1


async def test_seed_nps_skips_without_api_key():
    assert await nps_seed.seed_nps("postgresql://x", api_key="") == {"skipped": "no_api_key"}


# ─────────────────────────── admin 토큰 (/seed/nps) ───────────────────────────


def _admin_client(admin_token: str):
    from fastapi.testclient import TestClient

    from invest_note_api.config import Settings, get_settings
    from invest_note_api.main import create_app

    settings = Settings(supabase_url="https://test.supabase.co", admin_token=admin_token)
    app = create_app(settings)
    app.dependency_overrides[get_settings] = lambda: settings
    return TestClient(app)


def test_admin_seed_nps_rejects_missing_token():
    assert _admin_client("secret").post("/admin/seed/nps").status_code == 403


def test_admin_seed_nps_accepts_valid_token_returns_202(monkeypatch):
    async def noop(*_a, **_k):
        return None

    monkeypatch.setattr("invest_note_api.routers.admin.run_seed_nps", noop)
    client = _admin_client("secret")
    r = client.post("/admin/seed/nps", headers={"X-Admin-Token": "secret"})
    assert r.status_code == 202
    assert r.json() == {"status": "started"}
