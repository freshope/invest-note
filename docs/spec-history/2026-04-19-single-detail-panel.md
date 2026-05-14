> 완료: 2026-04-19

# Spec: 거래상세·종목상세 패널 단일 오픈 유지

## 배경 / 문제

현재 `TradeDetailPanel`은 자식으로 `<StockDetailPanel>`을, `StockDetailPanel`은 자식으로 `<TradeDetailPanel>`을 렌더한다. 사용자가 거래→종목→거래…를 클릭할 때마다 같은 `z-[100]` portal 패널이 DOM에 무한 누적되어 메모리/렌더 비용이 쌓이고 뒤로가기 동작이 한 단계씩만 진행된다.

## 목표

- 거래상세 패널과 종목상세 패널 중 **단 하나만** 동시에 열려있다.
- 한 패널이 열린 상태에서 상대 패널을 호출하면, 기존 패널은 슬라이드 아웃 애니메이션으로 닫히고 새 패널이 슬라이드 인 한다 (잠깐의 동시 애니메이션 허용).
- 거래상세 ↔ 종목상세를 여러 번 왕복해도 DOM에는 패널 portal이 최대 1개(전환 중에는 일시적으로 2개)만 존재한다.
- 외부 라우트(`/stocks/[country]/[ticker]`, `/records/[id]`) 직접 진입은 영향 없이 동작한다.

## 설계

### 접근 방식

전역 컨텍스트 SSOT(Single Source of Truth)로 패널 상태를 끌어올린다. 새 `DetailPanelProvider`를 `(app)/layout.tsx`에 마운트하고, Provider가 두 패널(`<FullScreenPanel>` 2개)을 직접 소유한다. 호출자는 `useDetailPanel().openTrade(...)` / `openStock(...)` / `close()` 만 호출한다. 두 패널의 `open` props는 단일 `mode` 상태로 mutual-exclusive 하게 제어되므로 동시 오픈이 구조적으로 불가능하다.

`FullScreenPanel`의 기존 transitionEnd 기반 unmount 메커니즘과 `useSnapshotWhileOpen`을 그대로 재사용해 슬라이드 아웃 애니메이션을 보존한다.

### 주요 변경 파일

- `src/components/panels/DetailPanelProvider.tsx` — **신규**. Context + Provider + `useDetailPanel()` 훅. 두 `<FullScreenPanel>`을 자체 렌더하고 `handleDeleted`/`handleSaved`(invalidate + router.refresh + close)를 흡수.
- `src/app/(app)/layout.tsx` — `<DetailPanelProvider>`로 children 래핑.
- `src/components/records/TradeList.tsx` — `selectedTrade`/`detailOpen`/`useSnapshotWhileOpen`/`<TradeDetailPanel>` 제거, `onPress`에서 `openTrade({trade, accounts, allTrades: trades})` 호출.
- `src/components/home/HoldingsList.tsx` — `panelOpen`/`useSnapshotWhileOpen`/`dynamic StockDetailPanel`/`<StockDetailPanel>` 제거, fetch 성공 시 `openStock({...})` 호출 (fetch 가드 유지).
- `src/components/records/TradeDetailPanel.tsx` — **삭제**. 책임이 Provider로 이동.
- `src/components/stocks/StockDetailPanel.tsx` — **삭제**. 책임이 Provider로 이동.

### 재사용

- `FullScreenPanel`, `FullScreenPanelContent`, `useSnapshotWhileOpen` (`src/components/base/FullScreenPanel.tsx`).
- `TradeDetail` (`src/components/records/TradeDetail.tsx`), `StockDetail` (`src/components/stocks/StockDetail.tsx`) — props 변경 없음.
- `computeRealizedPnL` (`src/lib/analysis/realized-pnl.ts`) — 종목 stats 계산.

## 구현 체크리스트

- [x] `src/components/panels/DetailPanelProvider.tsx` 신규 작성 (Context, hook, Provider, 두 패널 렌더, deleted/saved 처리)
- [x] `src/app/(app)/layout.tsx`에 `<DetailPanelProvider>` 래핑 추가
- [x] `src/components/records/TradeList.tsx` 리팩터 — local panel state 제거, `useDetailPanel().openTrade(...)` 호출
- [x] `src/components/home/HoldingsList.tsx` 리팩터 — local panel state 제거, `useDetailPanel().openStock(...)` 호출
- [x] `src/components/records/TradeDetailPanel.tsx` 삭제
- [x] `src/components/stocks/StockDetailPanel.tsx` 삭제
- [x] 타입 체크 통과 (`pnpm tsc --noEmit`)
- [x] 수동 검증: 거래→종목→거래 왕복 시 portal 1개만 유지, 슬라이드 아웃 애니메이션 정상

## 우려사항 / 리스크

- **allTrades stale**: 패널이 열려있는 동안 외부에서 거래가 추가/수정되면 payload가 stale. 기존 동작과 동일하므로 회귀 아님.
- **router.refresh 후 payload stale**: 삭제/저장 후 호출자 페이지 trades는 갱신되지만 Provider 내부 payload는 stale. 그 시점에 `close()`가 함께 호출되므로 사용자 영향 없음.
- **외부 라우트(`/stocks/...`, `/records/...`)**: Server Component가 `TradeDetail`/`StockDetail`을 직접 렌더하며 `onStockPress`/`onTradePress`를 넘기지 않으므로 패널 동작이 비활성화되고 Link fallback이 그대로 작동.
- **TradeFormPanel과의 z-index 충돌**: 둘 다 `z-[100]`이지만 동시 오픈 케이스 없음.
