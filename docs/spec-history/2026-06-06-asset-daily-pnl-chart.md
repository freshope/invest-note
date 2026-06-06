> 완료: 2026-06-06

# Spec: 자산 추이 일별 손익 막대 차트

## 배경 / 문제

자산 추이 페이지(`AssetHistoryView`)는 현재 누적 자산 평가액 AreaChart 하나만 보여준다. 하루하루의 증감(일별 손익)을 보려면 '일별 내역' 표의 전일대비 숫자를 훑어야 한다. 홈의 `AllocationTabs`처럼 탭으로 누적 차트 ↔ 일별 손익 막대 차트를 전환할 수 있게 한다.

**사용자 확정 사항:**
- 손익 정의 = 기존 '일별 내역' 표의 **전일대비**(자산 평가액 일간 변화, 매수/매도 증감 포함) → **FE 단독 작업, BE 변경 없음**
- 일별 손익 탭의 헤더(날짜+금액) = 포커스된 날짜의 **손익 금액** (+/− 부호, 빨강/파랑 색상)

## 목표

- 자산 추이 페이지에서 탭("자산" / "일별 손익")으로 차트를 전환할 수 있다
- 일별 손익 탭은 막대 차트로 표시된다: 이익 빨강(`var(--rise)`), 손실 파랑(`var(--fall)`), 0 기준선(ReferenceLine)
- 누적 차트와 동일하게 최대 2년치(BE 캡) 데이터를 63거래일 윈도우로 보여주고 스와이프로 좌우 이동할 수 있다
- 일별 손익 탭에서 헤더가 포커스 날짜의 손익 금액을 부호·색상과 함께 표시한다
- 막대 값 = 기존 '일별 내역' 표 전일대비와 정확히 일치한다

## 설계

### 접근 방식

1. **팬 로직 훅 추출** — `AssetHistoryChartInner`의 endIndex/clampedEnd/visible/move/pointer 핸들러(~50줄)를 `useChartPan(seriesLength)` 훅으로 추출, 두 차트가 공유. 기존 AreaChart 동작 불변.
2. **막대 차트 신규** — recharts `BarChart` + `Bar` + per-bar `Cell`(change ≥ 0 → rise, < 0 → fall), `ReferenceLine y={0}`, 연도 구분선·XAxis 스타일은 기존 차트와 동일. 데이터는 `items`를 역순으로 뒤집어 `{date, value: change}` 형태로 전달. dynamic ssr:false 래퍼 패턴 동일 적용.
3. **탭 전환** — `AssetHistoryView`의 차트 카드 안에 `base/Tabs` 사용 (홈 `AllocationTabs.tsx` 패턴). 탭 상태를 view가 제어(controlled)해 헤더 표시를 분기. 탭 전환 시 `setFocus(null)`로 포커스 리셋(차트 remount 후 새 우측점 통지).
4. **헤더 분기** — 일별 손익 탭이면 `signColor`(`fe/src/lib/format.ts`) + 부호 포함 금액 표시.

### 재사용

- `base/Tabs` 래퍼 (`fe/src/components/base/Tabs.tsx`)
- `signColor` / 부호 포맷 (`fe/src/lib/format.ts`, `AssetHistoryList.tsx`의 formatChange 패턴)
- 색상 변수 `var(--rise)` `var(--fall)` (pnl-colors와 동일 소스)
- BE 응답 `items[].change` (재계산 없음 — '일별 내역' 표와 정합 보장)

### 주요 변경 파일

- `fe/src/hooks/useChartPan.ts` (신규) — 윈도우(63)/스와이프(6px) 팬 로직 훅
- `fe/src/components/assets/AssetHistoryChartInner.tsx` — 자체 팬 로직 → 훅 사용으로 교체
- `fe/src/components/assets/AssetDailyPnlChartInner.tsx` (신규) — recharts BarChart 본체
- `fe/src/components/assets/AssetDailyPnlChart.tsx` (신규) — dynamic ssr:false 래퍼 (`AssetHistoryChart.tsx` 패턴)
- `fe/src/components/assets/AssetHistoryView.tsx` — Tabs 추가 + 헤더 표시 분기

## 구현 체크리스트

- [x] `fe/src/hooks/useChartPan.ts` 신규 — 팬/윈도우 훅 추출
- [x] `fe/src/components/assets/AssetHistoryChartInner.tsx` — 훅 적용 (동작 불변 리팩토링)
- [x] `fe/src/components/assets/AssetDailyPnlChartInner.tsx` 신규 — 막대 차트 (Cell 색상, 0 기준선, 연도 구분선, 포커스 통지)
- [x] `fe/src/components/assets/AssetDailyPnlChart.tsx` 신규 — dynamic 래퍼
- [x] `fe/src/components/assets/AssetHistoryView.tsx` — 탭 + 헤더 분기
- [x] 포커스 표시 — 화살표 마커(ReferenceDot, 샤프트+화살촉 스트로크). 수익: 막대 위 ↓ / 손실: 막대 아래 ↑, 색상은 막대와 동일(rise/fall). 흐림(fillOpacity)·폭 2배(Bar shape)·삼각형 ▼ 방식은 반려됨
- [x] 타입 체크 통과 (`pnpm -C fe exec tsc --noEmit`)
- [x] FE 테스트 통과 (`pnpm -C fe test`) — 159개

## 우려사항 / 리스크

- 모바일 폭(~350px)에서 63개 막대 → 막대폭 약 3px. 시인성이 낮으면 barGap/barCategoryGap 조정으로 후속 보정
- 큰 매수일에 큰 빨간 막대(손익 아님)가 보이는 건 전일대비 정의의 알려진 특성 (사용자 확인 완료)
- 첫 데이터 포인트는 change=0 (BE 정의) → 막대 없음, 자연스러움
