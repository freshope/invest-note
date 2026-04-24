// 전역 React Query 기본값 — QueryProvider에 주입
export const QUERY_DEFAULT_STALE_TIME_MS = 30_000;
export const QUERY_DEFAULT_RETRY = 1;

// 자주 쓰이는 비-기본 staleTime — 의도적 override 시 사용
export const QUERY_STOCK_SEARCH_STALE_TIME_MS = 60_000;
