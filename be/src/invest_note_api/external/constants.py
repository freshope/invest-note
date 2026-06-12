"""외부 HTTP 통신 공통 상수."""

# 통화 상수는 domain.trade_types(typed Currency Literal)를 단일 출처로 두고 re-export 한다 —
# 두 곳 정의로 인한 drift 방지. 방향: external→domain 단방향(domain 은 external 미참조, 사이클 없음).
from invest_note_api.domain.trade_types import CURRENCY_KRW, CURRENCY_USD  # noqa: F401

USER_AGENT = "Mozilla/5.0"
HTTP_TIMEOUT_SECONDS = 5.0

# 시세 fallback 체인(naver realtime → basic → yahoo .KS/.KQ)의 worst-case latency 가드.
# 종목당 개별 시도는 짧게(2s), 전체 체인은 deadline(5s)으로 캡 → Naver 장애 시에도
# 종목당 ~20s(4×5s) 대신 최대 ~5s 로 제한한다.
QUOTE_ATTEMPT_TIMEOUT = 2.0
QUOTE_FETCH_DEADLINE = 5.0

QUOTE_CACHE_MAXSIZE = 512
# pull-to-refresh 는 `refresh=1` 쿼리 파라미터로 캐시를 우회하므로 baseline TTL 을 길게
# 둬도 신선도 저하 없이 외부 호출 빈도를 낮출 수 있다 (탭 전환/재렌더 시 캐시 재사용).
QUOTE_CACHE_TTL = 45

# 환율(FX)은 시세보다 변동이 느려 TTL 을 길게(10분) 둔다. 통화쌍 수가 적어 maxsize 도 작다.
FX_CACHE_MAXSIZE = 16
FX_CACHE_TTL = 600

# KIS Open API(한국투자증권) — 실전/모의 도메인. KIS_ENV(real|mock)로 분기.
KIS_REAL_BASE_URL = "https://openapi.koreainvestment.com:9443"
KIS_MOCK_BASE_URL = "https://openapivts.koreainvestment.com:29443"
# 국내주식 현재가 조회 (tr_id FHKST01010100, 실전/모의 동일)
KIS_INQUIRE_PRICE_PATH = "/uapi/domestic-stock/v1/quotations/inquire-price"
# 국내주식 기간별 시세 — 일/주/월/년 캔들 (tr_id FHKST03010100, 호출당 최대 100건 역순)
KIS_DAILY_CHART_PATH = "/uapi/domestic-stock/v1/quotations/inquire-daily-itemchartprice"

NAVER_REALTIME_URL = "https://polling.finance.naver.com/api/realtime/domestic/stock/{code}"
NAVER_BASIC_URL = "https://api.stock.naver.com/stock/{code}/basic"
NAVER_SEARCH_URL = "https://ac.stock.naver.com/ac"
YAHOO_CHART_URL = "https://query2.finance.yahoo.com/v8/finance/chart/{symbol}?interval=1d&range=1d"
# 일별 시계열용 — interval/range 또는 period1/period2 를 params 로 받는다(쿼리스트링 미포함).
# YAHOO_CHART_URL 은 ?interval=1d&range=1d 가 박혀 있어 historical 구간 조회에 부적합.
YAHOO_CHART_RANGE_URL = "https://query2.finance.yahoo.com/v8/finance/chart/{symbol}"
YAHOO_SEARCH_URL = "https://query2.finance.yahoo.com/v1/finance/search"
# 환율 폴백 — open.er-api.com(무인증). 응답: {"result":"success","base_code","rates":{...},...}
ER_API_LATEST_URL = "https://open.er-api.com/v6/latest/{base}"
