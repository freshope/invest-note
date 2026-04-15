# 기능 명세서

## MVP 범위

### 1. 거래 기록

| 필드 | 타입 | 비고 |
|------|------|------|
| assetName | string | 종목명 |
| marketType | STOCK / CRYPTO / ETC | |
| tradeType | BUY / SELL | |
| price | number | |
| quantity | number | |
| tradedAt | datetime | |
| totalAmount | number | 자동 계산 |
| profit/loss | number | SELL 시 자동 계산 |

### 2. 매매 이유

| 필드 | 타입 | 필수 |
|------|------|------|
| buyReason / sellReason | text | 선택 |
| strategyType | SCALPING / SWING / LONG_TERM / UNKNOWN | 선택 |
| reasoningTag | TECHNICAL / FUNDAMENTAL / NEWS / FEELING (다중) | 선택 |

### 3. 감정 기록

`CONFIDENT` / `ANXIOUS` / `FOMO` / `IMPULSIVE` / `CALM` — 단일 선택

### 4. 복기 (회고)

| 필드 | 타입 |
|------|------|
| result | SUCCESS / FAIL / BREAKEVEN |
| reflectionNote | text |
| improvementNote | text |

### 5. 포트폴리오 조회

- 보유 종목 목록 (평균단가 WAC 기준)
- 평가손익 (KRX API 15분 지연)
- 계좌별 분리 조회 + 전체 합산

### 6. 기본 통계

- 총 거래 수
- 승률
- 총 수익/손실

### 7. 다중 계좌

- 계좌 수동 등록
- 예수금 수동 입력 (`cash_balance`)
- 총 자산 = 주식 평가 + 예수금

---

## 입력 UX 흐름

```
1. 종목 선택
2. 가격 / 수량 입력
3. 매수 / 매도 선택
4. 전략 + 감정 버튼 선택 (기본값 제공)
5. (선택) 메모 입력
```

---

## MVP 제외 항목 (v2+)

- 증권사 API 자동 연동
- CSV 임포트
- 실시간 시세
- AI 분석
- 푸시 알림
- 세금 계산
