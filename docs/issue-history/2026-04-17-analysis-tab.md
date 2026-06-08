# 현재 작업 사양: 분석 탭 구현

## 목표

`/analysis` 탭에 매매 패턴 분석 화면을 구현해 MVP를 완성한다.
현재 해당 경로는 스켈레톤(빈 페이지) 상태다.

---

## 구현할 기능

### 기본 통계 카드

| 지표 | 계산 방법 |
|------|---------|
| 총 거래 수 | `trades` 전체 count |
| 매도 거래 수 | `trade_type = 'SELL'` count |
| 승률 | `result = 'SUCCESS'` / 매도 거래 수 × 100 |
| 총 실현 손익 | `SUM(profit_loss)` where `trade_type = 'SELL'` |

### 전략별 분석

- 전략 타입(SCALPING / SWING / LONG_TERM)별 거래 수 & 승률
- 바 차트 또는 테이블로 표시

### 감정별 분석

- 진입 감정(CONFIDENT / ANXIOUS / FOMO / IMPULSIVE / CALM)별 승률
- 어떤 감정 상태에서 진입했을 때 결과가 좋은지 시각화

### 태그별 분석

- 분석 태그(TECHNICAL / FUNDAMENTAL / NEWS / FEELING)별 승률

---

## 완료 기준

- [ ] `/analysis` 페이지에 기본 통계 카드 표시 (총 거래, 매도, 승률, 총 손익)
- [ ] 전략별 승률 표시
- [ ] 감정별 승률 표시
- [ ] 빈 상태 UI (거래 데이터 없을 때)
