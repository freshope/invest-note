# Spec: FE/BE simplify — is_manual_input 폐기 + accounts queryKey 통일

> 완료: 2026-05-03

## 배경 / 문제

`docs/backlog.md` 의 FE/BE simplify 잔여 3개 중, BE 협조 없이 처리 가능한 작은 2개를 1개 spec으로 묶어 정리한다. 가장 큰 항목인 trades 페이지네이션은 별도 spec(BE+FE 동반)으로 미룸.

### (1) `SellBreakdown.is_manual_input` 폐기

BE/FE 모두 항상 `False`/`false`만 송수신하는 dead 필드.
- BE: `compute_flexible_breakdown()` 항상 `is_manual_input=False` (`api/src/invest_note_api/domain/holdings.py:72`)
- FE: `computeFlexibleBreakdown()` 항상 `isManualInput: false` (`app/src/lib/holdings.ts:121`)
- FE: `TradeDetail.tsx:177` 의 `&& !summary.breakdown.isManualInput` 분기는 항상 truthy (효과 없음)
- DB 컬럼 없음 (순수 응답 필드) → 마이그레이션 불필요
- "진짜 manual input 케이스"는 명세된 적 없음 → 폐기로 결론

### (2) `accountsApi` 캐시 키 통일

`queryKeys.accounts = ["accounts"]` 가 `queryKeys.portfolio = ["portfolio"]` 트리 밖에 있어, account mutation 시 두 번의 `invalidateQueries` 가 강제됨 (`AccountCard:33-35`, `AccountFormPanel:92-95`). React Query 의 prefix-based invalidation 을 활용하지 못하고 있음.

> portfolioSummary 의 `snapshots[].account` 로 selector 대체하는 방안은 검토했으나, 해당 path 의 account 가 `trade_count` 를 enrich 받지 않아 (`api/src/invest_note_api/routers/portfolio.py:77` 의 `list_accounts(conn)`) BE 변경 없이는 채택 불가. queryKey 트리 통일이 FE-only 로 가능한 최소 침습 단순화.

## 목표

- `SellBreakdown` 에서 `is_manual_input` 필드가 BE/FE 모두에서 제거되고, 응답 스키마·테스트·UI 분기 잔재가 없음
- account mutation 시 `invalidateQueries` 호출이 1회로 축소되고, `Promise.all` 보일러플레이트 제거
- `pnpm tsc`, `pnpm test`, `cd api && poetry run pytest -q` 통과

## 설계

### 접근 방식

**(1) is_manual_input 폐기**: BE 도메인/스키마/테스트 → FE 타입/계산 함수/UI 분기/테스트 순으로 동기 제거.

**(2) queryKeys.accounts 통일**: `["accounts"]` → `["portfolio", "accounts"]` 로 변경. 그러면 `queryKeys.portfolio = ["portfolio"]` 한 번 invalidate 로 summary 와 accounts 가 같이 무효화됨. 두 mutation 사이트의 `Promise.all` 제거.

### 주요 변경 파일

**(1) is_manual_input**
- `api/src/invest_note_api/domain/holdings.py` — `SellBreakdown.is_manual_input` 필드 + `compute_flexible_breakdown` 의 `is_manual_input=False` 인자 제거
- `api/src/invest_note_api/schemas/trade_response.py` — `SellBreakdownResponse.is_manual_input` 제거
- `app/src/lib/holdings.ts` — `SellBreakdown.isManualInput` 필드 + `computeFlexibleBreakdown` 의 `isManualInput: false` 제거
- `app/src/components/records/TradeDetail.tsx:177` — 조건에서 `&& !summary.breakdown.isManualInput` 제거
- `app/src/lib/__tests__/holdings.test.ts:48` — `isManualInput` 단언 제거
- `api/tests/...` — 만약 BE 테스트가 `is_manual_input` 응답 필드를 단언하면 수정 (작업 시 grep 으로 확인)

**(2) accounts queryKey 통일**
- `app/src/lib/query-keys.ts` — `accounts: ["accounts"]` → `accounts: ["portfolio", "accounts"]`
- `app/src/components/settings/AccountCard.tsx:32-36` — `Promise.all([invalidate(portfolio), invalidate(accounts), invalidate(trades)])` 의 `accounts` 줄 제거 (portfolio invalidate 가 prefix 매칭으로 흡수)
- `app/src/components/settings/AccountFormPanel.tsx:92-95` — `Promise.all([invalidate(portfolio), invalidate(accounts)])` 를 `await invalidate(portfolio)` 단일 호출로 단순화

### backlog 정리

`docs/backlog.md` 의 FE simplify 성능 섹션에서 "accountsApi.list ↔ portfolioApi.summary 캐시 키 통일" 항목을 처리됨으로 표시(완료 메모 추가). BE simplify 의 `SellBreakdown.is_manual_input` 항목도 동일 처리.

## 구현 체크리스트

- [x] BE: `SellBreakdown` dataclass / `compute_flexible_breakdown` / `SellBreakdownResponse` 에서 `is_manual_input` 제거
- [x] BE 테스트: `is_manual_input` 참조 grep 후 정리, `cd api && poetry run pytest -q` 통과
- [x] FE: `holdings.ts` 의 `SellBreakdown` 타입과 `computeFlexibleBreakdown` 에서 `isManualInput` 제거
- [x] FE: `TradeDetail.tsx:177` 의 `!summary.breakdown.isManualInput` 분기 제거
- [x] FE 테스트: `holdings.test.ts:48` 의 `isManualInput` 단언 제거
- [x] FE: `query-keys.ts` 의 `accounts` 를 `["portfolio", "accounts"]` 로 변경
- [x] FE: `AccountCard.tsx` / `AccountFormPanel.tsx` 의 mutation 후 `invalidateQueries(accounts)` 호출 제거 + `Promise.all` 단순화
- [x] `pnpm tsc --noEmit` 통과 (`pnpm -C app exec tsc --noEmit`)
- [x] `pnpm test` 통과 (`pnpm -C app test`)
- [x] `docs/backlog.md` 의 두 항목에 처리 완료 메모 추가

## 검증

1. **BE 단위 테스트**: `cd api && poetry run pytest tests/test_holdings.py -q` (또는 trade_summary 관련 테스트)
2. **FE 단위 테스트**: `pnpm -C app test src/lib/__tests__/holdings.test.ts`
3. **타입 체크**: `pnpm -C app exec tsc --noEmit` — `is_manual_input`/`isManualInput` 참조가 남아 있으면 컴파일 실패
4. **수동 검증** (가능 시):
   - 매도 거래 상세 페이지: 거래 결과 breakdown 박스가 정상 노출되는지 (`TradeDetail.tsx:177` 분기가 항상 표시 쪽으로 동작)
   - settings 페이지에서 계좌 추가/수정/삭제: 홈 대시보드와 settings 양쪽 데이터가 즉시 반영되는지 (queryKey 통일 후 단일 invalidate 로도 양쪽이 새로고침되는지)

## 우려사항 / 리스크

- `queryKeys.accounts` shape 변경은 모든 사용처를 grep 으로 확인해야 함 (`queryKeys.accounts` 만 사용하면 안전, raw `["accounts"]` 직접 사용이 있으면 추가 수정 필요).
- BE 테스트가 응답 JSON 의 `isManualInput` 필드를 단언하는지 사전 확인. 응답 schema 가 camelCase 출력이므로 `isManualInput` 키워드로 grep.
- React Query prefix invalidation 동작은 v4+ 기본값이므로 변경 없음 (이미 `queryKeys.portfolioSummary` 가 같은 패턴으로 동작 중).
