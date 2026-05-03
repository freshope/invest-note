# FE simplify 정리 작업

플랜 원본: `~/.claude/plans/fe-wise-mountain.md`

`/simplify fe 전체를 조사해라` 결과 발견된 ~150건 중, 검증 완료되고 FE 단독으로 처리 가능한
7개 항목을 작업 단위로 정리. BE 변경이 필요한 항목은 `docs/backlog.md` v2 섹션에 이미 있음.

## 작업 항목 (실행 순서)

1. **AuthGuard 분리** — `(app)/layout.tsx` 인증 로직을 `<AuthGuard>` 로 추출
2. **format.ts 백분율 헬퍼** — `calcPercent`, `calcChangePercent` 추가 + 8개 인라인 제거
3. **useDialogState 훅** — `TradeDetail` + `AccountCard` 다이얼로그 4-state 통합
4. **StatCard 추출** — `SummaryCards` + `DashboardSummary` 카드 통합
5. **SellResultSection 추출** — `TradeDetail.tsx` 60줄 IIFE → 컴포넌트
6. **invalidateQueries 정밀화** — 11곳 mutation의 무효화 키 좁힘 (BUY→SELL emotion 자동산출 주의)
7. **TRADE_TYPE / COUNTRY_CODE 상수** — raw 문자열 60+곳 치환 (`as const satisfies`)

## 보류 / 제외

- TradeMetaBuyForm + TradeMetaSellForm 통합: 두 폼 공통부분이 form skeleton만, 통합 시 분기 복잡 → 보류
- HoldingSelectInput / StockSearchInput 드롭다운 추출: simplify 범위 초과 → 별도 PR
- HoldingCard useMemo 추가: 측정값 없는 메모이제이션은 노이즈 → 보류
- 전체 trades / portfolio summary 클라이언트 필터링: BE 변경 필요 → backlog v2

## 검증

각 항목마다:
- `pnpm -C app exec tsc --noEmit`
- `pnpm -C app test`

전체 완료 후:
- `pnpm -C app build`
- 핵심 플로우 수동 QA (로그인 → 거래 등록 BUY/SELL → 메타 → 분석 → 계좌 추가/삭제)
