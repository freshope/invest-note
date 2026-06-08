# Spec: 거래 카드 스와이프-삭제

> 완료: 2026-05-24

## 배경 / 문제

현재 단건 삭제 경로가 "선택 → 체크 → 삭제 → 확인" 4스텝으로 잦은 사용 패턴 대비 마찰이 크다. 모바일 표준인 좌측 스와이프 → 트레일링 삭제 버튼 패턴을 도입해 단건 삭제를 단축한다. 일괄 삭제(선택 모드)는 별도 job이므로 유지한다.

## 목표

- 거래 카드를 우→좌로 스와이프하면 우측에 빨간 "삭제" 버튼이 노출된다.
- 삭제 버튼을 누르면 기존 `ConfirmDeleteDialog` 가 떠 1건 삭제를 확인한다.
- 확인 시 단건 삭제 API 호출 후 trades/portfolio/analysis 쿼리가 무효화된다.
- 한 번에 한 카드만 열린다. 다른 카드 스와이프, 빈 영역 탭, 스크롤 시 닫힌다.
- 선택 모드일 때는 스와이프가 비활성화된다.
- `useLongPress` 훅 및 관련 코드/테스트가 코드베이스에서 제거된다.
- 카드 탭(상세 열기), "선택" 버튼(일괄 모드 진입), 일괄 삭제는 영향 없이 동작한다.

## 설계

### 접근 방식

- `react-swipeable` 의 `useSwipeable` 훅 사용 (포인터/터치 이벤트 통합, 작은 번들).
- `TradeCard` 를 "내용 레이어 + 우측 액션 레이어" 두 레이어 구조로 재구성. translateX 로 내용 레이어를 이동.
- 드래그 중에는 `onSwiping` 의 `deltaX` 를 실시간 반영해 카드를 따라 움직이고(iOS Mail/토스 감각), 손을 떼면 `onSwiped` 에서 최종 위치 기준으로 open/close 결정 (50% 임계).
- 열림 상태는 `TradeList` 가 단일 ID로 보유(`openSwipeId`). `TradeCard` 는 `swipeOpen` / `onSwipeOpenChange(id, open)` props 로 외부 제어 (id 시그니처로 memo 유지).
- 단건 삭제는 `useDialogState` + `ConfirmDeleteDialog` 재사용. 대상 trade 는 `pendingDelete` state 로 보유.
- 수직 스크롤 보호를 위해 `delta: { left: 12, right: 12, up: Infinity, down: Infinity }` 사용 — 수직 임계를 Infinity 로 두어 세로 의도는 절대 swipe 로 판정되지 않고 native scroll 이 항상 이긴다. `trackTouch: true`, `trackMouse: false`, `preventScrollOnSwipe: true`, 컨텐츠 레이어 CSS `touch-pan-y` 병행.
- `onSwipeStart` 에서 `suppressClickRef = true` 로 세팅해 스와이프 직후 합성 click 으로 카드가 즉시 닫히는 현상 차단.
- 열림 카드 자동 닫힘 트리거: 다른 카드 스와이프, 카드 탭, 콘텐츠 영역 빈 곳 탭, 페이지 스크롤, 선택 모드 진입, AccountFilter 변경.
- BE 단건 삭제 oversell 메시지를 라우터에서 변환 — `validate_mutation` 의 "매도 시점" 관점 메시지가 삭제 컨텍스트에서 오인을 일으키므로 "매도 거래에 매칭되어 있어 삭제할 수 없습니다. 매도 거래를 먼저 삭제해 주세요." 로 변환.

### 주요 변경 파일

- `fe/package.json` — `react-swipeable` 의존성 추가 (`pnpm -C fe add react-swipeable`).
- `fe/src/components/records/TradeCard.tsx` — 스와이프 래퍼 추가, 트레일링 삭제 버튼 레이어 추가, props 변경: `onLongPress` 제거, `swipeOpen?: boolean` / `onSwipeOpenChange?: (open: boolean) => void` / `onRequestDelete?: (trade) => void` 추가. (루트 button → div role=button, nested button 회피)
- `fe/src/components/records/TradeList.tsx` — `handleLongPress` 제거, `openSwipeId` 상태 + `pendingDelete` 상태 추가, 단건 삭제 다이얼로그 분기(`onConfirmSingleDelete`). 선택 모드 진입/AccountFilter 변경 시 `openSwipeId` 초기화.
- `fe/src/hooks/useLongPress.ts` — **삭제** (다른 사용처 없음).
- `fe/src/components/records/__tests__/TradeCard.longPress.test.tsx` — **삭제**.
- (선택) `fe/src/components/records/__tests__/TradeCard.swipe.test.tsx` — 신규 추가.

### 재사용 자산

- `fe/src/components/shared/ConfirmDeleteDialog.tsx` — props 변경 없이 그대로 사용.
- `fe/src/hooks/useDialogState.ts` — `run()` 패턴으로 단건 삭제 성공/에러 처리.
- `fe/src/lib/api-client.ts` 의 `tradesApi.delete(id)` — 단건 삭제 엔드포인트(이미 존재).
- `queryKeys.trades`, `queryKeys.portfolio`, `["analysis"]` — TradeList bulk delete 와 동일 invalidate 세트.

## 구현 체크리스트

- [x] `react-swipeable` 의존성 추가
- [x] `useLongPress` 훅 및 longPress 테스트 파일 제거
- [x] `TradeCard.tsx` — 스와이프 레이어 구조로 재작성, 트레일링 삭제 버튼 추가, props 시그니처 변경
- [x] `TradeList.tsx` — `openSwipeId` / `pendingDelete` 상태 추가, 단건 삭제 다이얼로그 분기, `handleLongPress` 및 `onLongPress` prop 전달 제거, 선택 모드/필터 변경 시 swipe 닫기
- [x] 카드 탭/선택 모드 동작 수동 회귀 (사용자 직접 확인 — 배경 비침/모서리 갭/스크롤 민감도 등 fix 진행)
- [x] 타입 체크 (`pnpm -C fe exec tsc --noEmit`)
- [x] 기존 테스트 통과 (`pnpm -C fe test` — 13 파일 136 통과)

## 우려사항 / 리스크

- **세로 스크롤과의 제스처 충돌** — `delta.up/down: Infinity` 패턴(다른 프로젝트 검증)으로 수직 의도를 swipe 인식 자체에서 배제. `preventScrollOnSwipe: true` + `touch-pan-y` 병행 (해결됨).
- **invalidate 누락** — 단건 삭제도 bulk 와 동일하게 trades + portfolio + ["analysis"] 무효화 호출 (해결됨).
- **race** — 다이얼로그 표시 중 trade 가 사라지는 좁은 race. 대상 null 시 조용히 닫음 (해결됨).
- **nested button** — 컨테이너 `<div>` + 컨텐츠 `role="button"` + 액션 `<button>` 형제 구조로 회피 (해결됨).
- **수동 회귀 미실행** — 스와이프 동작은 단위 테스트로 커버 어렵다. dev 서버 또는 실기기에서 6개 케이스(다른 카드 스와이프, 카드 탭, 빈 영역 탭, 스크롤, 선택 모드 진입, 삭제 확인) 확인 필요.
