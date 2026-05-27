"""외부 HTTP 통신 공통 상수."""

USER_AGENT = "Mozilla/5.0"
CURRENCY_KRW = "KRW"
CURRENCY_USD = "USD"
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

NAVER_REALTIME_URL = "https://polling.finance.naver.com/api/realtime/domestic/stock/{code}"
NAVER_BASIC_URL = "https://api.stock.naver.com/stock/{code}/basic"
NAVER_SEARCH_URL = "https://ac.stock.naver.com/ac"
YAHOO_CHART_URL = "https://query2.finance.yahoo.com/v8/finance/chart/{symbol}?interval=1d&range=1d"
YAHOO_SEARCH_URL = "https://query2.finance.yahoo.com/v1/finance/search"
