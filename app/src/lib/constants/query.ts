// 전역 React Query 기본값 — QueryProvider에 주입
export const QUERY_DEFAULT_STALE_TIME_MS = 30_000;
export const QUERY_DEFAULT_RETRY = 1;

// 자주 쓰이는 비-기본 staleTime — 의도적 override 시 사용
export const QUERY_STOCK_SEARCH_STALE_TIME_MS = 60_000;

// 분석 대시보드 — 거래 등록/수정 시 invalidate 가 보장되므로 5 분 stale 허용
export const QUERY_ANALYSIS_STALE_TIME_MS = 5 * 60_000;
// 포트폴리오 요약 — 동일 보장 + 시세는 백엔드 실시간 조회로 분리되어 있음
export const QUERY_PORTFOLIO_STALE_TIME_MS = 2 * 60_000;
// 매도 폼 보유 수량 조회 — 같은 종목/계좌로 짧은 시간 내 재조회 시 캐시 활용
export const QUERY_HOLDING_STALE_TIME_MS = 10_000;
