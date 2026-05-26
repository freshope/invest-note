"""외부 HTTP 통신 공통 상수."""

USER_AGENT = "Mozilla/5.0"
CURRENCY_KRW = "KRW"
CURRENCY_USD = "USD"
HTTP_TIMEOUT_SECONDS = 5.0

QUOTE_CACHE_MAXSIZE = 512
QUOTE_CACHE_TTL = 10

NAVER_REALTIME_URL = "https://polling.finance.naver.com/api/realtime/domestic/stock/{code}"
NAVER_BASIC_URL = "https://api.stock.naver.com/stock/{code}/basic"
NAVER_SEARCH_URL = "https://ac.stock.naver.com/ac"
YAHOO_CHART_URL = "https://query2.finance.yahoo.com/v8/finance/chart/{symbol}?interval=1d&range=1d"
YAHOO_SEARCH_URL = "https://query2.finance.yahoo.com/v1/finance/search"
