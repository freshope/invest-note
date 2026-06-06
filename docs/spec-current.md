# Spec: 자산 추이 차트 — 매수 금액 가이드 + 손익 구간 색상

**브랜치:** `feature/asset-history-pnl-chart` (develop 기준)

## 배경 / 문제

자산 추이 차트(홈 → 자산 추이 패널, 계좌뷰/종목뷰 공용)는 현재 단색 보라(`--chart-1`) AreaChart라 차트만 봐서는 수익/손실 상태를 알 수 없다. 매수 금액(보유분 원금)을 가이드 라인으로 표시하고, 이를 기준으로 수익 구간 빨강·손실 구간 파랑으로 칠해 손익 상태를 즉시 인지할 수 있게 한다.

- `/assets/history` 응답에는 매수 금액(원금) 정보가 없음 → BE 필드 추가 필요
- 가이드 라인은 **차트 Y 도메인을 바꾸지 않고**, 현재 보이는 데이터 범위 안에 들어올 때만 표시 (사용자 요구)

## 목표

- 차트에 현재 매수 금액 수평 가이드 라인(점선)이 표시된다 — 단, 가시 구간 데이터 범위(min~max) 안에 있을 때만. Y 도메인 계산은 기존 그대로(데이터만 기준)라 차트 모양이 변하지 않는다.
- 매수 금액 기준 위(수익)는 빨강(`--rise` #F04452), 아래(손실)는 파랑(`--fall` #1B6AC9)으로 라인·면이 칠해진다.
- 면 그라데이션은 매수 금액 라인 방향으로 투명해진다 (수익: 위에서 라인 쪽으로 fade, 손실: 아래에서 라인 쪽으로 fade).
- 매수 금액이 없으면(null/0, 전량 매도 등) 기존 보라색 차트 그대로 (하위호환).
- 가이드 값은 포트폴리오 대시보드의 평가손익 계산과 동일한 `cost_basis` 기준이라 숫자가 일치한다.

## 설계

### 접근 방식

**BE — `/assets/history` 응답에 `investedAmount` 추가**

- 라우터(`assets.py`)는 이미 scoped trades를 로드함 → `build_positions(trades)`(portfolio.py:232, trade walker 기반) 재사용
- `invested = sum(p.cost_basis for p in positions if p.holding_quantity > 0)` — 대시보드 `unrealized_pnl = evaluation - cost_basis`와 동일 계산 경로라 정합성 보장
- 응답 스키마에 `invested_amount: float | None = None` 추가 (CamelModel → `investedAmount`). 거래 없음 early-return 시 None
- 계좌뷰/종목뷰 모두 동일 — trades가 이미 scope 필터됨

**FE — 차트 3-케이스 분기 (가시 윈도우의 데이터 min/max 기준, 팬마다 재계산)**

`AssetHistoryChartInner.tsx`에서 `invested` prop 받아 분기:

1. **`dataMin < invested < dataMax`** (분할 케이스):
   - `<Area baseValue={invested}>` → fill이 곡선~매수 금액 선 사이에만 그려짐. stroke·fill path의 bbox가 모두 [dataMin, dataMax]로 동일해져 단일 offset 공유 가능
   - `offset = (dataMax - invested) / (dataMax - dataMin)`
   - fill 그라데이션: `0%` rise 0.28 → `offset` rise 0 / `offset` fall 0 → `100%` fall 0.28 (양쪽 모두 매수 금액 선 방향으로 fade)
   - stroke 그라데이션: `0%~offset` rise, `offset~100%` fall (hard stop)
   - `<ReferenceLine y={invested}>` 점선 가이드 + 좌측에 `매수 {fmtCompact(invested)}` 라벨(9px muted) 표시
2. **`invested <= dataMin`** (전 구간 수익): 기존 형태(baseValue 기본=바닥, 아래로 fade) 그대로, 색만 rise 빨강 단색. 가이드 라인 없음
3. **`invested >= dataMax`** (전 구간 손실): fall 파랑 단색. 매수 원금이 위에 있으므로 `baseValue=yDomain 상단`으로 곡선 위로 채우고 위로 갈수록 투명(profit과 대칭). 가이드 라인 없음

- **`invested`가 null/≤0**: 현행 보라색 그대로 (폴백)
- focus 마커(dot) 색: focus.value ≥ invested → rise, 미만 → fall (폴백 시 보라)
- flat line(min===max) 등 0-나누기 가드
- recharts `baseValue`는 설치본(3.8.1) 타입에서 지원 확인됨

### 주요 변경 파일

- `be/src/invest_note_api/schemas/asset_response.py` — `invested_amount: float | None` 필드 + docstring
- `be/src/invest_note_api/routers/assets.py` — `build_positions` 재사용해 invested 계산·응답 포함
- `be/tests/test_assets_router.py` — investedAmount 응답 검증 (값 일치 + 거래 없음 시 null)
- `fe/src/lib/api-client.ts` — `AssetHistoryResponse.investedAmount?: number | null`
- `fe/src/components/assets/AssetHistoryView.tsx` — `data.investedAmount`를 차트에 전달
- `fe/src/components/assets/AssetHistoryChart.tsx` — prop 패스스루
- `fe/src/components/assets/AssetHistoryChartInner.tsx` — 3-케이스 색상/그라데이션/가이드 라인 구현

## 구현 체크리스트

- [x] BE: `asset_response.py`에 `invested_amount` 필드 추가
- [x] BE: `assets.py` 라우터에서 invested 계산 + 응답 포함
- [x] BE: `test_assets_router.py` 테스트 추가 → `cd be && poetry run pytest tests/test_assets_router.py -q` (10 passed)
- [x] FE: `api-client.ts` 타입 추가
- [x] FE: `AssetHistoryView.tsx` / `AssetHistoryChart.tsx` prop 전달
- [x] FE: `AssetHistoryChartInner.tsx` 가이드 라인 + 손익 색상/그라데이션
- [x] 타입 체크 통과 (`pnpm -C fe exec tsc --noEmit`)
- [x] BE 전체 테스트 (`cd be && poetry run pytest -q` — 435 passed) / FE 테스트 (159 passed)

## 우려사항 / 리스크

- 분할 그라데이션 offset은 objectBoundingBox 기준이라 baseValue=invested일 때만 정확 — 3-케이스 분기로 회피
- 그라데이션 시각 디테일(투명도, 점선 스타일)은 구현 중 미세 조정 가능
