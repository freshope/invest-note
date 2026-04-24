> 완료: 2026-04-24

# Spec: 거래/종목 상세 판넬 타입당 1개 제한 (2-슬롯 구조)

## 배경 / 문제

`DetailPanelProvider`의 `useSnapshotWhileOpen` ref 두 개가 null로 리셋되지 않아 `<TradePanel>` 과 `<StockPanel>` 엘리먼트가 항상 동시에 렌더된다. `open` 토글 race로 portal이 중첩/잔존하며 "무한히 쌓이는" 현상이 발생한다.

## 목표

- 거래 상세·종목 상세 각 타입당 portal이 최대 1개만 존재한다.
- 같은 타입을 다시 열면 콘텐츠만 즉시 교체된다(애니메이션 없음).
- 뒤로가기는 해당 판넬 자신만 닫는다. 두 판넬이 동시에 열려 있어도 2번 클릭이면 원래 페이지로 복귀한다.

## 설계

### 접근 방식

`DetailPanelProvider`를 2개의 독립 슬롯 + `topType`으로 재작성한다.

- `tradePayload`, `stockPayload`, `topType: "trade" | "stock" | null` 3개 상태.
- 각 `<FullScreenPanel>`은 해당 slot payload 존재 여부로 `open` 결정.
- 뒤로가기는 자기 타입 slot만 null로 설정.
- `topType`은 z-order 결정용(마지막으로 연 타입이 위).
- 각 slot 래퍼에 고정 `key`를 부여해 렌더 순서 변경 시 remount 방지.

### 주요 변경 파일

- `app/src/components/panels/DetailPanelProvider.tsx` — 상태/API/렌더 교체

## 구현 체크리스트

- [x] `tradePayload`/`stockPayload`/`topType` 3개 상태로 교체 (`mode` 제거)
- [x] `openTrade`: trade slot set + `setTopType("trade")`
- [x] `openStock`: stock slot set + `setTopType("stock")`
- [x] `closeTrade` / `closeStock` / `closeAll` 핸들러 (topType 재계산 포함)
- [x] `useSnapshotWhileOpen`의 `open` 인자를 `payload !== null`로 전달
- [x] z-order 분기 렌더 + 각 slot에 고정 `key`
- [x] `handleTradeMutated` → `closeTrade()` + invalidate
- [x] `TradePanel` `onClose={closeTrade}`, `StockPanel` `onClose={closeStock}`
- [x] `usePathname` effect → `closeAll()`
- [x] 타입 체크 통과 (`pnpm --filter app tsc --noEmit`)

## 우려사항 / 리스크

- z-order 분기 렌더 시 고정 `key` 없으면 remount 발생 → 반드시 부여.
- 삭제 후 동작 변경: 기존은 모두 닫혔으나 이제 Trade만 닫혀 Stock이 남음. 사용자 기대에 부합.
