"""OpenFIGI /v3/mapping — ISIN → ticker 해소 페처.

토스 해외(USD) import 시 미해결 ISIN 을 ticker 로 해소한다. OpenFIGI 출력에 ISIN 이
없어(입력 전용) 마스터 백필이 불가하므로 import 시점 해소 + 캐시(isin_ticker_map)가 정합.

라이선스: FIGI public domain, 상업 이용·재배포 허용. CUSIP 미출력으로 라이선스 함정 회피.
Rate limit: 무키 25req/분·10건/요청, 무료키 25req/6초·100건/요청. `OPENFIGI_API_KEY` 옵션.

네트워크/HTTP 실패는 graceful — 예외를 삼키고 해당 배치를 미해결(None)로 처리한다.
import preview 전체가 OpenFIGI 장애로 5xx 가 되면 안 된다(부분 해소·종목명 폴백 유지).
"""

from __future__ import annotations

import asyncio
import logging
from typing import TypedDict

import httpx

from invest_note_api.domain.trade_types import COUNTRY_US

logger = logging.getLogger(__name__)

OPENFIGI_MAPPING_URL = "https://api.openfigi.com/v3/mapping"
_TIMEOUT_SECONDS = 10.0

# 배치 크기 — 무키 10건/요청, 키 100건/요청.
_BATCH_NO_KEY = 10
_BATCH_KEY = 100
# 배치 간 페이싱(초) — 무키 25req/분(2.4s), 키 25req/6초(0.24s). **단일 배치면 sleep 안 함**.
_PACE_NO_KEY = 60.0 / 25.0
_PACE_KEY = 6.0 / 25.0

# 429(rate limit) 백오프 — 횟수·시간 상한으로 무한 대기 방지.
_MAX_RETRIES = 2
_BACKOFF_BASE = 1.0

# OpenFIGI exchCode 중 미국 거래소(합성 'US' + 개별 venue 코드). 다건 매칭 시 미국 상장 우선.
_US_EXCH_CODES = frozenset(
    {"US", "UN", "UW", "UQ", "UR", "UA", "UP", "UV", "UD", "UF", "UT", "PQ"}
)
# 우선 securityType — 보통주/ETP 류. 워런트/채권 등보다 우선해 토스 USD 거래의 본주를 고른다.
_PREFERRED_SECURITY_TYPES = frozenset(
    {"Common Stock", "ETP", "Depositary Receipt", "REIT", "Mutual Fund", "ADR"}
)


class OpenFigiResult(TypedDict):
    ticker: str
    exch_code: str
    name: str
    security_type: str


def exch_code_to_country(exch_code: str) -> str:
    """OpenFIGI exchCode → country_code.

    토스 USD 섹션은 전부 해외(미국 상장) 거래이고 로컬 stocks 의 유일한 해외 마스터가
    US 이므로, 미국 거래소 코드든 미상 코드든 US 로 매핑한다(US 외 매핑은 매칭 대상이 없다).
    exchCode 인자는 향후 비-US 해외 마스터 도입 시 분기점으로 남겨 둔다.
    """
    return COUNTRY_US


def _choose(items: list[dict]) -> OpenFigiResult | None:
    """OpenFIGI 한 ISIN 의 data 항목들 중 최적 1건 선택.

    우선순위: (1) 미국 거래소 + 우선 securityType → (2) 미국 거래소 → (3) 우선 securityType
    → (4) 첫 항목. ticker 가 없는 항목은 제외(해소 가치 없음).
    """
    candidates = [it for it in items if isinstance(it, dict) and it.get("ticker")]
    if not candidates:
        return None

    def _rank(it: dict) -> int:
        is_us = it.get("exchCode") in _US_EXCH_CODES
        is_pref = it.get("securityType") in _PREFERRED_SECURITY_TYPES
        if is_us and is_pref:
            return 0
        if is_us:
            return 1
        if is_pref:
            return 2
        return 3

    best = min(candidates, key=_rank)
    return {
        "ticker": str(best.get("ticker") or ""),
        "exch_code": str(best.get("exchCode") or ""),
        "name": str(best.get("name") or ""),
        "security_type": str(best.get("securityType") or ""),
    }


async def map_isins(
    isins: list[str],
    *,
    api_key: str | None = None,
    client: httpx.AsyncClient | None = None,
) -> dict[str, OpenFigiResult | None]:
    """ISIN 목록 → {isin: OpenFigiResult | None}. 미해결 ISIN 은 None.

    - 입력 중복은 제거하고 한 번만 조회한다(반환 dict 은 유니크 ISIN 키).
    - 배치 크기·페이싱은 api_key 유무로 분기. 단일 배치면 sleep 하지 않는다.
    - HTTP/네트워크 실패는 graceful — 해당 배치를 전부 None(미해결)으로 처리하고 진행한다.
    - `client` 주입 시 재사용, 없으면 소유 client 를 만들어 닫는다.
    """
    unique = list(dict.fromkeys(i for i in isins if i))
    if not unique:
        return {}

    batch_size = _BATCH_KEY if api_key else _BATCH_NO_KEY
    pace = _PACE_KEY if api_key else _PACE_NO_KEY
    batches = [unique[i : i + batch_size] for i in range(0, len(unique), batch_size)]

    result: dict[str, OpenFigiResult | None] = {isin: None for isin in unique}

    own_client = client is None
    cl = client or httpx.AsyncClient(timeout=_TIMEOUT_SECONDS)
    try:
        for idx, batch in enumerate(batches):
            if idx > 0:
                await asyncio.sleep(pace)  # 배치 ≥2 일 때만 페이싱
            result.update(await _map_batch(cl, batch, api_key))
    finally:
        if own_client:
            await cl.aclose()
    return result


async def _map_batch(
    client: httpx.AsyncClient,
    batch: list[str],
    api_key: str | None,
    *,
    attempt: int = 0,
) -> dict[str, OpenFigiResult | None]:
    """ISIN 한 배치를 OpenFIGI 로 조회. 실패 시 배치 전체를 미해결(None)로 반환."""
    headers = {"Content-Type": "application/json"}
    if api_key:
        headers["X-OPENFIGI-APIKEY"] = api_key
    jobs = [{"idType": "ID_ISIN", "idValue": isin} for isin in batch]

    try:
        res = await client.post(
            OPENFIGI_MAPPING_URL, json=jobs, headers=headers, timeout=_TIMEOUT_SECONDS
        )
    except httpx.HTTPError as e:
        logger.info("openfigi 네트워크 예외 n=%d: %s", len(batch), type(e).__name__)
        return {isin: None for isin in batch}

    if res.status_code == 429 and attempt < _MAX_RETRIES:
        await asyncio.sleep(_BACKOFF_BASE * (2**attempt))
        return await _map_batch(client, batch, api_key, attempt=attempt + 1)

    if res.status_code != 200:
        logger.warning("openfigi non-200 status=%d n=%d", res.status_code, len(batch))
        return {isin: None for isin in batch}

    try:
        data = res.json()
    except ValueError:
        logger.warning("openfigi 응답 JSON 파싱 실패 n=%d", len(batch))
        return {isin: None for isin in batch}

    if not isinstance(data, list) or len(data) != len(batch):
        logger.warning("openfigi 응답 shape 불일치 n=%d", len(batch))
        return {isin: None for isin in batch}

    out: dict[str, OpenFigiResult | None] = {}
    for isin, job_result in zip(batch, data):
        items = job_result.get("data") if isinstance(job_result, dict) else None
        out[isin] = _choose(items) if isinstance(items, list) else None
    return out
