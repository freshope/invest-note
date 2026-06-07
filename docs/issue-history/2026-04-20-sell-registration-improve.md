> 완료: 2026-04-20

# Spec: 매도 등록 개선 (보유량 검증 · 손익 자동화 · 전략 평가)

## 배경 / 문제

현재 매도 등록 플로우에는 세 가지 문제가 있다.

1. **보유량 검증 없음** — 서버/클라 모두 보유 수량을 확인하지 않아, 없는 종목이나 초과 수량으로도 SELL을 등록할 수 있다. `computeRealizedPnL`/`buildPositions`가 사후 `Math.min` 방어만 하고 분석 지표는 오염된다.
2. **회고 필드 수동 입력** — `profit_loss`와 `result`를 사용자가 직접 계산·선택해야 한다. 조회 시점 자동 계산과 어긋나 `winRate` · `byStrategy` 등이 왜곡된다.
3. **매도 시 전략 중복 입력** — 매수에서 이미 받은 `strategy_type`을 매도에서 또 받는다. "계획대로 지켰는가"라는 본래 분석 의도가 UX·집계 모두에서 흐려진다.

## 목표

- 보유 0 또는 초과 수량의 매도 등록이 **서버·클라에서 차단**된다.
- 매도 회고 폼에서 `거래 결과`와 `손익 금액`이 **WAC 기준 서버 계산값으로 읽기전용 표시**된다.
- 매도 시 전략 필드는 제거되고, **매수 전략 × FIFO 보유일수 기반 "전략 준수/이탈"** 이 자동 판정·표시된다.
- 기존 분석 탭 · 포트폴리오의 숫자는 회귀 없이 유지된다.

## 설계

### 접근 방식

- **계산 방식: WAC 유지**. 기존 `sellPnL`/`computeRealizedPnL`/`buildPositions`와 일치.
- **result 자동 판정**: 수수료·세금 반영 후 `pnl > 0 → SUCCESS`, `< 0 → FAIL`, `= 0 → BREAKEVEN`.
- **저장 정책**: `profit_loss`·`result`는 DB에 저장하지 않고 조회 시점 파생. 매수 수정 시 stale 위험 제거. 기존 수동 입력 레코드(`profit_loss`값)는 `sellPnL`이 우선 사용하므로 호환.
- **전략 평가**: 매수 `strategy_type` vs SELL의 FIFO 가중평균 보유일수로 실제 전략 역산.
  - SCALPING ≤ 1일, 1 < SWING ≤ 30일, LONG_TERM > 30일
  - 매수 전략 null/UNKNOWN이면 `adherence: "UNKNOWN"`
- **보유 수량 산정**: `ticker:country:account_id` lot의 runningQty. `buildPositions` lot 로직을 공용 util로 추출.

### 주요 변경 파일

- `src/lib/holdings.ts` (신규) — lot 집계 공용 util (`computeLotQuantity`, `findLatestBuyStrategy`)
- `src/lib/analysis/strategy-adherence.ts` (신규) — 전략 평가 유틸
- `src/app/api/trades/route.ts` — POST에 SELL 보유량 검증 추가
- `src/app/api/trades/[id]/summary/route.ts` (신규) — WAC pnl · FIFO 보유일수 · 매수 상속 전략 · adherence 반환
- `src/lib/api-client.ts` — `tradesApi.summary(id)` 메서드 추가
- `src/components/records/TradeBasicForm.tsx` — 매도 시 보유 수량 헬퍼·"전량" 버튼·검증
- `src/components/records/TradeMetaSellForm.tsx` — 결과/손익/전략 입력 제거, 자동 계산 카드 표시로 대체
- `src/lib/api-server/validators.ts` — SELL PATCH에서 `profit_loss`/`result`/`strategy_type` 제거

## 구현 체크리스트

- [x] `src/lib/holdings.ts` 신규 — `computeLotQuantity`, `findLatestBuyStrategy`
- [x] `src/lib/analysis/strategy-adherence.ts` 신규 — `inferActualStrategy`, `evaluateStrategyAdherence`
- [x] `src/app/api/trades/route.ts` POST — SELL 보유량 검증
- [x] `src/app/api/trades/[id]/summary/route.ts` 신규 — 자동 계산 summary 엔드포인트
- [x] `src/lib/api-client.ts` — `tradesApi.summary(id)` 추가
- [x] `src/components/records/TradeBasicForm.tsx` — 보유량 헬퍼·"전량" 버튼·검증
- [x] `src/components/records/TradeMetaSellForm.tsx` — 자동 계산 카드로 교체
- [x] `src/lib/api-server/validators.ts` — 변경 불필요 (TradeMetaSellForm이 해당 필드 미전송으로 충분)
- [x] 타입 체크 통과 (`pnpm tsc --noEmit`)
- [x] 테스트 통과 (`pnpm test` — 63/63)
- [x] 통합 시나리오 수동 확인 (보유없음·초과·다계좌·부분매도)

## 우려사항 / 리스크

- 기존 수동 입력 레코드(`profit_loss` 컬럼값 있음): `sellPnL` 우선순위로 호환 유지.
- BREAKEVEN 허용 오차: 기본 엄격히 `=0`만. 필요 시 후속 backlog.
- 전략 임계값(1/30일): 상수로 분리해 추후 튜닝 용이하게.
