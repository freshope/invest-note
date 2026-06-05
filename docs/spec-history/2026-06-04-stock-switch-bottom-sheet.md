> 완료: 2026-06-04

# Spec: 종목 헤더에서 바텀시트로 종목 전환

## Context / 배경

종목 상세 패널과 종목 자산 추이 패널에서 **다른 보유 종목으로 이동**하려면 지금은 패널을 닫고 홈으로 돌아가 다시 종목을 골라야 한다. 헤더의 종목명 옆에 chevron-down 을 두고, 종목명을 누르면 바텀시트로 보유 종목 목록을 띄워 그 자리에서 전환할 수 있게 한다.

## 목표 (완료 기준)

- 종목 상세 패널 / 종목 자산 추이 패널(종목 view) 헤더의 종목명 옆에 chevron-down 아이콘이 보인다.
- 종목명(+chevron) 을 누르면 바텀시트가 아래에서 올라오고 보유 종목 목록이 표시된다.
- 목록에서 종목을 고르면 현재 패널이 해당 종목으로 전환된다(상세 → 새 종목 거래내역 / 추이 → 새 종목 추이).
- `/assets` 라우트(계좌 단위 "내 자산 추이", 종목명 없음)에는 chevron·전환이 나타나지 않는다.
- 전환·시트 닫기 후 페이지 스크롤/클릭이 정상이고, 헤더 좌측 뒤로가기·우측 "자산 추이" 버튼 클릭이 그대로 동작한다.

## 설계

### 핵심 결정

1. **전환 메커니즘 재사용** — 기존 `openStock` / `openAssetHistory` + `useStaggeredPanel` 의 `remountKey` 가 "열린 상태에서 새 payload" 를 이미 remount 로 처리한다(`FullScreenPanel.tsx:257-263`). 새 상태 추가 없이 그대로 사용.

2. **바텀시트 = 단일 feature 컴포넌트** `StockSwitchSheet`, radix-ui `Dialog` primitive 직접 사용. (vaul 미설치, `FullScreenPanel` 은 우→좌 슬라이드라 부적합. 단일 사용처이므로 `base/` 래퍼는 만들지 않음.)
   - `DialogOverlay`(백드롭) + bottom-anchored `DialogContent`(`fixed inset-x-0 bottom-0 z-[200] rounded-t-2xl bg-background max-h-[70vh]`, `slide-in-from-bottom`, safe-area bottom 패딩, 상단 그랩 핸들, a11y용 `DialogTitle`).
   - z-[200] > 패널 z-[100] 이라 패널 위에 정상 노출.

3. **시트 데이터는 시트가 자체 소유** — `StockSwitchSheet` 내부에서 accounts 쿼리 + `useEffectiveAccountId(accounts)` + `usePortfolioSummary(effectiveAccountId)` → `positions`. 현재 계좌 필터 존중. 정렬 평가액 내림차순. 행 = `assetName` + `CountryBadge` + `ticker`(mono), 현재 종목 강조+체크. 빈 목록이면 안내.

4. **시트 소유 위치 = 비리마운트 wrapper** — `StockPanel` / `AssetHistoryPanel`(remount 되지 않는 wrapper)에서 시트 open-state·`StockSwitchSheet` 를 소유하고, child 에는 `onSwitchStock` 콜백만 전달.

5. **route-shared view 에 전환 로직 미배치** — `AssetHistoryView` 는 plain `onSwitchStock?` 만 받는다. 라우트(`AssetHistoryPage`)는 미전달 → chevron 없음·positions 쿼리 없음.

6. **헤더 타이틀 hit-area** — 컨테이너 `pointer-events-none` 유지, 내부에 중앙 `inline-flex` 버튼(`pointer-events-auto`, `max-w`, text `truncate`, chevron `shrink-0`) 중첩 → 좌/우 버튼 클릭 통과 유지.

7. **trades 로드 공유** — `HoldingsList` 의 fetch→`openStock`(+에러 토스트) 로직을 `useOpenStock` 훅으로 추출해 공유. 추이 전환은 `openAssetHistory` 만 호출.

### 주요 변경 파일

- `fe/src/components/stocks/StockSwitchSheet.tsx` (신규)
- `fe/src/hooks/useOpenStock.ts` (신규)
- `fe/src/components/home/HoldingsList.tsx`
- `fe/src/components/stocks/StockDetail.tsx`
- `fe/src/components/assets/AssetHistoryView.tsx`
- `fe/src/components/panels/DetailPanelProvider.tsx`

## 구현 체크리스트

- [x] `useOpenStock.ts` 추출 + `HoldingsList.tsx` 리팩토링(동작 동일)
- [x] `StockSwitchSheet.tsx` — radix Dialog 바텀시트, positions 목록/정렬/현재종목 강조/빈 상태
  - useQuotes + mergeQuotes overlay 로 evaluation 채운 뒤 정렬(summary lite 는 evaluation=null 이라 overlay 필수), 로딩 중 스켈레톤
- [x] `StockDetail.tsx` 헤더 타이틀 버튼+chevron (`onSwitchStock` gating)
- [x] `AssetHistoryView.tsx` 헤더 타이틀 버튼+chevron (`isStockView && onSwitchStock` gating)
- [x] `DetailPanelProvider.tsx` — 시트 소유 + 선택 핸들러 + `onSwitchStock` 전달
- [x] 타입 체크 통과 (`pnpm -C fe exec tsc --noEmit`) / 변경 파일 ESLint clean
- [ ] **런타임 검증(미완)**: 종목 전환 후 스크롤·버튼 클릭 정상(radix scroll-lock × FullScreenPanel body lock) — 실기기/dev 확인 필요 (backlog 추적)

## 세션 후속 변경 (같은 브랜치)

- **전환 무애니메이션** — 종목 변경 시 `remountKey` 가 `FullScreenPanel`(슬라이드 lifecycle)까지 remount 시켜 슬라이드-인이 재생되던 문제 수정. `FullScreenPanel` 은 유지하고 `key` 를 `FullScreenPanelContent`(content surface=스크롤 컨테이너)로 이동 → `visible=true` 상태로 바로 `translate-x-0` 마운트되어 애니메이션 없이 즉시 교체 + 스크롤 상단 리셋. `StockPanelContent` 에서 내부 `FullScreenPanel` 래퍼·`open` prop 제거. (설계 결정 #1 의 remount 경계가 wrapper→content surface 로 변경됨.)
- **자산뷰 차트 높이 220→170px** — iPhone 등에서 일별 내역 영역 확보. `AssetHistoryChartInner`(ResponsiveContainer) + `AssetHistoryChart`(로딩/빈 상태) 3곳.

## 우려사항 / 리스크

- radix Dialog scroll-lock 과 `FullScreenPanel` body lock 중첩 → 전환/닫기 후 body `overflow`·`pointer-events` 복구가 핵심 회귀 포인트. (런타임 검증 항목 참조)
- 상세 전환 시 `useOpenStock` 가 fetch 후 `openStock` → 빈 플래시 없음.
