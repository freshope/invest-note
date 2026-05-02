# Spec: DetailPanelProvider 5중 상태 단순화

브랜치: `feature/fe-simplify-round2-detail-panel`

## 배경 / 문제

`DetailPanelProvider` 가 trade/stock 패널 각각에 대해 `open` / `payload` / `key` / `payloadRef` / `closeTimer` 5 가지 상태·ref 를 관리해 한 컴포넌트에 총 10 개의 state/ref 가 분산되어 있다. 슬라이드 lifecycle (mount → animate-in → animate-out → unmount, 같은 type 재호출 시 즉시 재마운트) 이 Provider 와 `FullScreenPanel` 양쪽에 걸쳐 있어 변경 시 이해 비용이 높다.

backlog "FE simplify Round 2+" 의 상태/구조 리팩터 항목 중 첫 번째 작업.

## 목표

- Provider 가 trade/stock 각각 **payload state 1 개만** 관리한다 (open/key/closeTimer/payloadRef 제거).
- 슬라이드 lifecycle 을 `useStaggeredPanel<T>(externalPayload)` 훅 1 개로 캡슐화하고, `FullScreenPanel.tsx` 에서 export 한다.
- 호출자(`HoldingsList`, `TradeList`) 의 사용 API (`openTrade`, `openStock`) 는 시그니처 변경 없음.
- 기존 UX 모두 유지: 라우트 이동 시 자동 close, trade ↔ stock 교차 전환, 같은 type 재호출 시 부드러운 panel 전환, slide-out 중 content 보존, mutated/saved 후 invalidate.

## 설계

### 접근 방식

1. `useStaggeredPanel<T>(externalPayload: T | null)` 훅을 `app/src/components/base/FullScreenPanel.tsx` 에 추가 export. 반환: `{ open, payload, remountKey }`.
   - 내부: `open` / `payload` state, `internalPayloadRef`, `closeTimer` ref, `useEffect([externalPayload])`.
   - non-null 진입 + 이미 open → `remountKey++` (애니메이션 cancel 효과). null 진입 → `setOpen(false)` + `setTimeout(setPayload(null), PANEL_ANIMATION_MS + 50)`.
   - cleanup effect 별도로 분리해 unmount 시 timer leak 방지.

2. `DetailPanelProvider` 본체:
   - state 2 개 (`tradePayload`, `stockPayload`) 만 보유.
   - `openTrade` = `setTradePayload`, `openStock` = `setStockPayload` (raw setState 노출 금지를 위해 useCallback wrap).
   - close = payload 를 null 로 설정. slide-out 은 훅이 처리.
   - 라우트 변경 시 두 setter 모두 null. mutated/saved 핸들러는 그대로.
   - TradePanel/StockPanel 을 conditional render 가 아닌 **항상 mount** (훅 timer 가 살아있어야 slide-out 완료됨).

3. `TradePanel` / `StockPanel` 을 wrapper + content 2 층으로 분할:
   - wrapper: `useStaggeredPanel(externalPayload)` 호출. payload 가 null 이면 `null` 반환.
   - content: 기존 payload-dependent 훅 (`useAccountFilter`, `useEnsureValidAccount`, `useMemo` 등) 호출. `<FullScreenPanel open={open}>` 렌더.
   - `key={remountKey}` 는 **content 에** (wrapper 에 두면 훅 state 가 리셋되어 "이미 열려 있었는지" 신호가 사라짐).

### 주요 변경 파일

- `app/src/components/base/FullScreenPanel.tsx` — `useStaggeredPanel<T>` 훅 추가 export (~30 줄). 기존 코드 무수정.
- `app/src/components/panels/DetailPanelProvider.tsx` — Provider 본체 단순화 + TradePanel/StockPanel wrapper/content 2 층 분할.

호출자 (`HoldingsList`, `TradeList`), 테스트 (`layout.test.tsx`), `FullScreenPanel` 기존 export 는 모두 무수정.

## 구현 체크리스트

- [ ] `app/src/components/base/FullScreenPanel.tsx` 에 `useStaggeredPanel<T>` 훅 추가 + export
- [ ] `app/src/components/panels/DetailPanelProvider.tsx` 리팩터 — state 2 중화 + Wrapper/Content 분할
- [ ] 타입 체크 통과 (`pnpm -C app exec tsc --noEmit`)
- [ ] 수동 동작 검증 6 시나리오:
  - 거래 → 종목 → 거래 back-stack 보존
  - 같은 type 빠른 재오픈 (key 증가로 cancel)
  - slide-in 도중 close 후 즉시 reopen
  - slide-out 중 라우트 변경 시 timer leak 없음
  - 거래 삭제 → close + invalidate
  - 거래 저장 → panel 유지 + invalidate
- [ ] backlog `상태/구조 리팩터` 의 본 항목 제거 + spec-history 이동 (`/custom:spec-finish` 단계)

## 우려사항 / 리스크

- 같은 reference 객체로 두 번 호출 시 useState bail-out 으로 useEffect 미실행 → key 증가 안 함. **현재 구현도 동일** 이므로 회귀 없음 (호출자 모두 매번 새 객체 생성).
- StrictMode 이중 effect 호출: 모든 setTimeout 이 cleanup 의 clearTimeout 과 짝지어져 있고 unmount cleanup 을 별도 effect 로 분리해 방어.
- `FullScreenPanel` 내부 mounted timer (transitionEnd @300ms) 와 `useStaggeredPanel` timer (payload null @350ms) 는 책임이 다르므로 통합하지 않음 (전자: DOM unmount, 후자: 외부 payload 정리).
- 자동 테스트 미추가 결정: jsdom 에서 fake timer + transitionEnd 합성 + double rAF 시뮬레이션 비용이 ROI 를 초과. 회귀는 모바일 슬라이드 시각 흐름에서 발생하므로 수동 device 검증이 더 신뢰성 높음.
