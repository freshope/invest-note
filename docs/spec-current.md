# Spec: 기록 탭 거래 일괄 삭제

## 배경 / 문제

기록 탭에서 잘못 입력된 거래나 가져오기로 누적된 다수의 거래를 정리할 때, 현재는 거래 상세 패널을 한 건씩 열어 삭제해야 한다(`fe/src/components/records/TradeDetail.tsx`). 다건 정리에 시간이 오래 걸리고 모바일에서 반복 탭이 번거롭다. 본 작업은 기록 탭 안에서 다중 선택 모드를 도입하고, BE에 트랜잭션 일괄 삭제 API를 추가해 한 번에 정리할 수 있게 한다.

## 목표

- 카드 롱프레스(약 500ms) 또는 PageHeader 우측 '선택' 버튼으로 선택 모드에 진입한다.
- 선택 모드에서 카드 탭은 상세를 열지 않고 토글 선택으로 동작한다.
- 헤더가 "취소 / N개 선택됨 / 삭제"로 교체되고, 헤더 아래에 '전체 선택/전체 해제' 토글이 표시된다.
- 계좌 필터 적용 시 '전체 선택'은 필터된 거래만 대상으로 한다.
- 선택 모드에서 FAB·업로드 버튼은 숨김, AccountFilter는 유지하며 필터 변경 시 선택은 초기화된다.
- 삭제 → 확인 다이얼로그 → `POST /trades/bulk-delete` → 단일 트랜잭션 내 전부 성공 or 전부 롤백.
- 일부 거래가 oversell 등으로 차단되면 충돌 종목·계좌가 메시지로 안내된다.
- 성공 시 trades / portfolio 쿼리 invalidate + 토스트 + 선택 모드 종료.

## 설계

### 접근 방식 (BE)

- 새 엔드포인트 `POST /trades/bulk-delete` (`be/src/invest_note_api/routers/trades.py`)
  - Body: `{ ids: list[str] }` (1~200건)
  - 단일 `acquire_for_user` 트랜잭션 안에서:
    1. id 일괄 조회, 누락 시 404
    2. 영향 그룹 키 수집 → **정렬된 순서로** `acquire_trade_group_lock` (데드락 회피)
    3. 그룹별 `list_trades_in_group` 후 삭제 대상들을 한 번에 가상 제거 → `walk_trades`로 oversell 검사. 실패 시 충돌 종목/계좌 메시지로 400 (트랜잭션 롤백)
    4. 통과 시 각 id에 `delete_trade` 호출
    5. 영향 그룹마다 1회 `recalc_group_pnl`
  - 응답: 204 (성공) / 400 + 메시지 (충돌)
- 다건 가상 적용 헬퍼는 라우터 내에서 `[t for t in trades if t.id not in delete_ids]` 로 직접 처리(별도 헬퍼 불필요).

### 접근 방식 (FE)

- `useLongPress` 훅 신규: 터치/포인터 통합, 500ms threshold, 이동 시 취소.
- `useTradeSelection` 훅 신규: `isSelectMode`, `selectedIds: Set<string>`, `enter`/`exit`/`toggle`/`selectAll`/`clearAll`.
- shadcn checkbox 설치 후 `src/components/base/Checkbox.tsx` 래퍼(AGENTS.md 규칙).
- `TradeList`가 헤더를 일반/선택 모드로 분기 렌더, 헤더 아래에 선택 모드 토글 줄 표시, `useEffectiveAccountId` 변경 시 `clearAll`.
- `TradeCard`에 `selectionMode` / `selected` / `onSelectToggle` props 추가, 좌측 액센트 옆에 체크박스.
- `tradesApi.bulkDelete(ids)` 추가, 확인 다이얼로그(`useDialogState`) + mutation, 성공 시 invalidate(`queryKeys.trades`, portfolio/analysis) + 모드 종료 + 토스트.

### 주요 변경 파일

- `be/src/invest_note_api/routers/trades.py` — bulk-delete 엔드포인트
- `be/src/invest_note_api/schemas/trade_response.py` (or 신규 request 모듈) — `TradeBulkDeleteRequest`
- `be/tests/.../test_trades.py` — 일괄 삭제 테스트
- `fe/src/hooks/useTradeSelection.ts` (신규)
- `fe/src/hooks/useLongPress.ts` (신규)
- `fe/src/components/base/Checkbox.tsx` (신규)
- `fe/src/components/records/TradeList.tsx` — 선택 모드 통합
- `fe/src/components/records/TradeCard.tsx` — 선택 props 추가
- `fe/src/lib/api-client.ts` — `tradesApi.bulkDelete`
- `fe/src/components/layout/PageHeader.tsx` — 선택 모드 variant (필요 시)

### 재사용

- BE: `validate_mutation`/`walk_trades`/`acquire_trade_group_lock`/`list_trades_in_group`/`delete_trade`/`recalc_group_pnl`/`trade_to_group_key`
- FE: `useDialogState`, `queryKeys.trades`, `PageHeader`

## 구현 체크리스트

- [ ] BE: `TradeBulkDeleteRequest` 스키마 (1~200건)
- [ ] BE: `POST /trades/bulk-delete` 라우터 — 트랜잭션·정렬 락·일괄 검증·일괄 삭제·그룹별 recalc
- [ ] BE: pytest — 여러 그룹 혼합 성공, oversell 충돌, 누락 id
- [ ] FE: shadcn checkbox 설치 + base 래퍼
- [ ] FE: `useLongPress` 훅
- [ ] FE: `useTradeSelection` 훅
- [ ] FE: `TradeCard` 선택 props + 체크박스 UI
- [ ] FE: `TradeList` 선택 모드 헤더·전체 선택 토글·FAB/업로드 숨김·필터 변경 시 초기화
- [ ] FE: `tradesApi.bulkDelete`
- [ ] FE: 확인 다이얼로그 + mutation + invalidate + 토스트
- [ ] FE: vitest — `useTradeSelection`, `TradeList` 선택 모드
- [ ] 타입 체크 통과 (`pnpm -C fe exec tsc --noEmit`), BE 테스트 통과 (`cd be && poetry run pytest -q`)

## 우려사항 / 리스크

- BUY만 선택해 삭제하면 같은 그룹 SELL이 oversell이 되어 거부될 수 있다 → BE 에러 메시지에 충돌 종목/계좌를 담아 친절히 안내.
- 다중 그룹 락은 키 정렬 후 획득해 동시 요청 데드락 방지.
- 삭제 후 invalidate는 trades + portfolio + analysis 모두 수행(BUY 메타 cascade 영향).
- ids 상한(200건) 초과 시는 FE에서 분할하지 않고 안내(스펙 단순화).
