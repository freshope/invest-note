"""data.go.kr(금융위 1160100) 게이트웨이 안정성 실측 진단.

재시도 없이 raw 로 각 엔드포인트를 N회 반복 호출해 성공률·지연분포·에러 양상을 집계한다.
운영에 영향 없는 read-only GET 진단이며, 결과만 stdout 으로 출력한다(DB 미접근).

사용:
    cd api && poetry run python scripts/diagnose_data_go_kr.py [반복횟수]
"""

import asyncio
import os
import statistics
import sys
import time
from datetime import date, timedelta

import httpx
from dotenv import load_dotenv

load_dotenv(".env.local")

USER_AGENT = "invest-note-diagnose/1.0"
TIMEOUT = 60  # 운영 코드와 동일(_DATA_GO_KR_TIMEOUT)
PAGE_SIZE = 1000

ENDPOINTS = {
    "getItemInfo": "https://apis.data.go.kr/1160100/service/GetKrxListedInfoService/getItemInfo",
    "getStockPriceInfo": "https://apis.data.go.kr/1160100/service/GetStockSecuritiesInfoService/getStockPriceInfo",
    "getETFPriceInfo": "https://apis.data.go.kr/1160100/service/GetSecuritiesProductInfoService/getETFPriceInfo",
}


def recent_basdt_candidates() -> list[str]:
    today = date.today()
    return [(today - timedelta(days=d)).strftime("%Y%m%d") for d in range(1, 8)]


def classify(res: httpx.Response) -> str:
    """응답 본문을 보고 정상 JSON / HTML 오류페이지 / 기타 분류."""
    ctype = res.headers.get("content-type", "")
    body = res.text[:200].lstrip()
    if body.startswith("{") or body.startswith("["):
        return "json"
    if "html" in ctype.lower() or body.lower().startswith("<!doctype") or body.lower().startswith("<html"):
        return "html_error"
    if "<OpenAPI_ServiceResponse" in res.text[:500] or "<response" in res.text[:500].lower():
        return "xml_error"
    return "other"


def count_items(res: httpx.Response) -> int:
    try:
        data = res.json()
    except Exception:
        return -1
    try:
        body = data["response"]["body"]
        items = body["items"]["item"]
        if isinstance(items, dict):
            return 1
        return len(items) if isinstance(items, list) else 0
    except (KeyError, TypeError):
        return -1


async def find_basdt(client: httpx.AsyncClient, api_key: str) -> str | None:
    """getItemInfo 가 비지 않은 응답을 주는 첫 basDt 를 찾는다(재시도 포함, 최대 후보 전부)."""
    for cand in recent_basdt_candidates():
        try:
            res = await client.get(
                ENDPOINTS["getItemInfo"],
                params={"serviceKey": api_key, "resultType": "json",
                        "numOfRows": 1, "pageNo": 1, "basDt": cand},
            )
            if classify(res) == "json" and count_items(res) > 0:
                return cand
        except httpx.HTTPError:
            continue
    return None


async def probe_once(client: httpx.AsyncClient, name: str, url: str, api_key: str, bas_dt: str) -> dict:
    params = {"serviceKey": api_key, "resultType": "json",
              "numOfRows": PAGE_SIZE, "pageNo": 1, "basDt": bas_dt}
    t0 = time.monotonic()
    try:
        res = await client.get(url, params=params)
        dt = time.monotonic() - t0
        kind = classify(res)
        n = count_items(res)
        ok = res.status_code == 200 and kind == "json" and n > 0
        detail = f"HTTP {res.status_code} {kind} items={n}"
        return {"ok": ok, "elapsed": dt, "status": res.status_code,
                "kind": kind, "items": n, "error": None if ok else detail}
    except httpx.TimeoutException:
        return {"ok": False, "elapsed": time.monotonic() - t0, "status": None,
                "kind": "timeout", "items": -1, "error": "ReadTimeout"}
    except httpx.TransportError as e:
        return {"ok": False, "elapsed": time.monotonic() - t0, "status": None,
                "kind": "transport", "items": -1, "error": type(e).__name__}


def pctl(values: list[float], p: float) -> float:
    if not values:
        return 0.0
    s = sorted(values)
    k = max(0, min(len(s) - 1, int(round((len(s) - 1) * p))))
    return s[k]


async def main() -> None:
    api_key = os.environ.get("DATA_GO_KR_API_KEY", "").strip()
    if not api_key:
        print("DATA_GO_KR_API_KEY 미설정")
        sys.exit(1)
    reps = int(sys.argv[1]) if len(sys.argv) > 1 else 20

    async with httpx.AsyncClient(headers={"User-Agent": USER_AGENT}, timeout=TIMEOUT) as client:
        bas_dt = await find_basdt(client, api_key)
        if not bas_dt:
            print("유효 basDt 후보를 찾지 못함(전부 빈 응답/오류)")
            sys.exit(1)
        print(f"basDt={bas_dt}, 엔드포인트당 {reps}회 raw 호출(재시도 없음), timeout={TIMEOUT}s\n")

        for name, url in ENDPOINTS.items():
            results = []
            for _ in range(reps):
                results.append(await probe_once(client, name, url, api_key, bas_dt))
                await asyncio.sleep(0.3)  # 게이트웨이 부하 방지

            oks = [r for r in results if r["ok"]]
            elapsed_ok = [r["elapsed"] for r in oks]
            elapsed_all = [r["elapsed"] for r in results]
            err_kinds: dict[str, int] = {}
            for r in results:
                if not r["ok"]:
                    err_kinds[r["kind"]] = err_kinds.get(r["kind"], 0) + 1

            print(f"■ {name}")
            print(f"   성공률 : {len(oks)}/{reps} ({100*len(oks)/reps:.0f}%)")
            if elapsed_ok:
                print(f"   성공지연: median {statistics.median(elapsed_ok):.1f}s  "
                      f"p90 {pctl(elapsed_ok,0.9):.1f}s  max {max(elapsed_ok):.1f}s")
            print(f"   전체지연: median {statistics.median(elapsed_all):.1f}s  max {max(elapsed_all):.1f}s")
            if err_kinds:
                print(f"   실패유형: {err_kinds}")
            print()


if __name__ == "__main__":
    asyncio.run(main())
