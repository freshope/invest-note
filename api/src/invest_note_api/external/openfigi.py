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
    """ISIN 목록 → {isin: OpenFigiResult | None}.

    반환 값의 의미를 3가지로 구분한다(negative cache 오염 방지의 핵심):
    - `isin → OpenFigiResult`: 해소 성공.
    - `isin → None`: OpenFIGI 가 정상 응답했으나 매칭이 없음(genuine not-found). 캐시해도 안전.
    - **키 자체 없음**: 일시 장애(네트워크/timeout/non-200/429 소진/shape 불일치)로 판정 불가.
      호출자는 이를 **캐시하지 말고** 다음 import 때 재조회해야 한다(영구 미해결 박제 방지).

    - 입력 중복은 제거하고 한 번만 조회한다.
    - 배치 크기·페이싱은 api_key 유무로 분기. 단일 배치면 sleep 하지 않는다.
    - `client` 주입 시 재사용, 없으면 소유 client 를 만들어 닫는다.
    """
    unique = list(dict.fromkeys(i for i in isins if i))
    if not unique:
        return {}

    batch_size = _BATCH_KEY if api_key else _BATCH_NO_KEY
    pace = _PACE_KEY if api_key else _PACE_NO_KEY
    batches = [unique[i : i + batch_size] for i in range(0, len(unique), batch_size)]

    # 일시 장애 배치는 결과에서 빠진다(키 없음) → 호출자가 캐시 제외 + 재조회.
    result: dict[str, OpenFigiResult | None] = {}

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
    """ISIN 한 배치를 OpenFIGI 로 조회.

    - 정상 응답: {isin: Result | None}(None = genuine not-found).
    - **일시 장애**(네트워크/non-200/429 소진/JSON·shape 불일치): **빈 dict** 반환 →
      배치 ISIN 들이 호출자 결과에서 빠져 캐시 제외·다음 import 재조회된다(영구 박제 방지).
    """
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
        return {}

    if res.status_code == 429 and attempt < _MAX_RETRIES:
        await asyncio.sleep(_BACKOFF_BASE * (2**attempt))
        return await _map_batch(client, batch, api_key, attempt=attempt + 1)

    if res.status_code != 200:
        logger.warning("openfigi non-200 status=%d n=%d", res.status_code, len(batch))
        return {}

    try:
        data = res.json()
    except ValueError:
        logger.warning("openfigi 응답 JSON 파싱 실패 n=%d", len(batch))
        return {}

    if not isinstance(data, list) or len(data) != len(batch):
        logger.warning("openfigi 응답 shape 불일치 n=%d", len(batch))
        return {}

    out: dict[str, OpenFigiResult | None] = {}
    for isin, job_result in zip(batch, data):
        items = job_result.get("data") if isinstance(job_result, dict) else None
        out[isin] = _choose(items) if isinstance(items, list) else None
    return out
