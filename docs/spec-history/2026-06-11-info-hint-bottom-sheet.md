# Spec: 안내문구 → 정보 아이콘 + 바텀시트 (자산추이 + 홈 fxBasis)

> 완료: 2026-06-11

## 배경 / 문제

자산추이 화면은 금액/날짜 아래에 중립 설명문구(예수금 제외, 환율 환산 기준)를 항상
인라인으로 깔아 시각적 잡음을 만든다. 이를 금액/날짜 우측의 정보 아이콘 뒤 바텀시트로
옮겨 화면을 정리하고, 같은 패턴을 홈의 fxBasis(환율 기준 투명성 표시)에도 동일하게 적용한다.

## 목표

- 자산추이 헤더에서 **중립 설명**(예수금 제외 · 환율 환산 기준)이 인라인으로 보이지 않고,
  금액/날짜 **우측 정보 아이콘** 탭 시 바텀시트로 안내된다.
- **경고/에러 문구**(환율 미상 · 시세 보정값 포함)는 기존처럼 인라인(빨강)으로 유지된다.
- 홈의 **중립 fxBasis**("환율 … 기준 · 시각")도 동일한 아이콘+바텀시트로 표시되고,
  **환율 미상 경고**는 인라인 유지된다.
- `pnpm -C fe exec tsc --noEmit` 및 `pnpm -C fe test` 통과.

## 설계

### 접근 방식

`StockMetaBadges`의 Drawer(바텀시트) 패턴을 공유 컴포넌트로 일반화한다. lucide `Info`
아이콘 버튼을 트리거로, `base/Drawer` 바텀시트에 섹션 목록을 띄운다.

**중립 설명만 아이콘 뒤로 숨기고, 경고/에러는 인라인 유지**한다(사용자 결정). 경고는
화면 숫자가 빠졌거나 보정됐다는 신호라 가시성을 유지해야 한다.

자산추이 헤더 아이콘은 클릭 가능한 카드 안에 중첩되지 않으므로 `StockMetaBadges`의
`stop()`/`display:contents`/직접 dismiss 복잡도는 복사하지 않는다(평범한 Drawer 트리거).

### 주요 변경 파일

- `fe/src/components/shared/InfoHintSheet.tsx` — 신규 공유 컴포넌트(Info 아이콘 + Drawer)
- `fe/src/components/assets/AssetHistoryView.tsx` — 중립 문구 2종을 아이콘+시트로 이동
  (금액/날짜 행 우측 배치), 경고 2종 인라인 유지. `"환율 확인 중"`(값 자리 대체)은 건드리지 않음
- `fe/src/components/home/HomeDashboard.tsx` — fxBasis를 중립(note)/경고로 분리해 전달
- `fe/src/components/home/DashboardSummary.tsx` — 중립 fxBasis는 아이콘+시트, 환율 미상 경고는 인라인 유지

## 구현 체크리스트

- [x] `InfoHintSheet.tsx` 공유 컴포넌트 작성 (Info 아이콘 + Drawer)
- [x] AssetHistoryView: 중립 문구 2종 → 아이콘+시트, 경고 인라인 유지
- [x] HomeDashboard/DashboardSummary: 중립 fxBasis → 아이콘+시트, 경고 인라인 유지
- [x] `pnpm -C fe exec tsc --noEmit` 통과
- [x] `pnpm -C fe test` 통과 (187 passed)
- [x] 변경 파일 ESLint 통과

## 우려사항 / 리스크

- 경고 가시성: 경고/에러는 의도적으로 인라인 유지하므로 가시성 손실 없음.
- 홈 fxBasis는 현재 footer 행에 있어 "금액 우측"과 위치가 다름 → 기존 footer 슬롯 자리에
  아이콘을 두어 최소 침습으로 구현(총자산 옆 이동은 하지 않음).
