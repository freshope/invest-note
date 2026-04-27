# Spec: 매도 거래 UI 개선 (보유 정보 섹션 강화 + 회고 필드 정리 + 자동입력 라벨)

## 배경 / 문제

서버에서 매도 등록 시 `strategy_type`과 `holding_days`가 자동 저장되도록 변경되었다 (마이그레이션 011 + `recalc_group_pnl`). 이를 기반으로 매도 관련 UI를 다음 방향으로 정돈한다:

- 거래 상세/수정에서 보유일이 한 줄 muted 텍스트로만 표기되어, 거래 결과 카드와 비교해 시각적 위계가 너무 약하다.
- 매도 회고 입력 항목(잘한 점/개선할 점)이 매도 이유(`sell_reason`)와 역할이 겹치고, 사용 빈도가 낮아 정리 대상.
- 종목코드가 종목명 자동완성으로 채워지는데 라벨이 단순 "종목코드"로 표시되어 자동입력임을 알기 어렵다.

## 목표

- 매도 거래의 보유 정보(보유일, 매도일, 평균 매수일, 계획 전략, 실제 전략, 전략 준수도)가 거래 결과 카드와 동일한 디자인 레벨의 별도 섹션 카드로 표시된다.
- 거래 상세/거래 수정/매도 등록 세 화면에서 보유 정보 섹션이 동일한 컴포넌트로 일관되게 노출된다.
- 매도 등록/수정 폼에서 잘한 점/개선할 점 입력 필드가 사라지고, 거래 상세에서도 해당 필드가 표시되지 않는다.
- DB의 `trades.reflection_note`, `trades.improvement_note` 컬럼이 제거된다.
- 분석 화면의 `reviewHabit` / `reflectionRate` 지표가 `sell_reason` 기반으로 재정의된다 (키 이름 유지, 의미만 "매도 이유 작성 비율"로 변경).
- 매수/매도 거래 등록 시 종목코드 라벨에 "(자동입력)"이 표기된다.
- `pnpm tsc --noEmit`, `pnpm test`, `poetry run pytest -q`가 모두 통과한다.

## 설계

### 결정 사항

- **분석 지표 처리**: `sell_reason` 기반으로 재정의. 키 이름 유지, 산출 입력만 교체.
- **보유 정보 카드 빈 상태**: `holdingDays == null`이면 카드는 유지하되 "보유일 계산 중…" placeholder 표시.
- **보유 정보 카드 위치**: 거래 결과 카드와 별도 sibling 카드로 배치.

### 보유 정보 섹션 컴포넌트

**경로**: `app/src/components/records/TradeHoldingSection.tsx` (신규)

**Props**:
```ts
interface TradeHoldingSectionProps {
  tradedAt: string;                              // ISO
  holdingDays: number | null;
  strategyEvaluation: StrategyEvaluation | null;
}
```

**디자인 토큰** (거래 결과 카드와 동일):
- 외부: `rounded-2xl bg-muted/60 p-4 space-y-3`
- 라벨: `text-[12px] font-semibold text-muted-foreground uppercase tracking-wide` → "보유 정보 (자동 계산)"
- 헤더: `flex items-center justify-between` → 좌측 `보유 N일` (`text-[16px] font-bold tabular-nums`), 우측 전략 준수도 뱃지
- 내부 박스: `rounded-lg bg-background border border-border/60 px-3 py-2.5 space-y-1.5`
  - 매도일, 평균 매수일 (= 매도일 - 보유일), 계획 전략, 실제 전략

### 분석 지표 재정의

`reviewHabit`/`reflectionRate`/`ProfileInputRates.reflection`: `sell_reason`이 비어있지 않은 비율로 산출 로직 교체. 키 이름 및 반환 구조는 그대로 유지.

### DB 마이그레이션 012

```sql
ALTER TABLE trades
  DROP COLUMN IF EXISTS reflection_note,
  DROP COLUMN IF EXISTS improvement_note;
```

## 구현 체크리스트

- [ ] 1. 백엔드: `trade_types.py`에서 두 필드 제거
- [ ] 2. 백엔드: `trades_repo.py`의 `_PATCH_ALLOWED`/INSERT 정리
- [ ] 3. 백엔드: `routers/portfolio.py` SELECT 컬럼 정리
- [ ] 4. 백엔드: `domain/portfolio.py` `last_note` fallback 단순화
- [ ] 5. 백엔드: `schemas/trade.py` `TradeUpdate`/`_free_text_max_len` 정리
- [ ] 6. 백엔드: `domain/analysis/profile.py` `sell_reason` 기반 재정의
- [ ] 7. 백엔드: `domain/analysis/aggregate.py` `reflectionRate` 입력 교체
- [ ] 8. 백엔드: pytest fixture/assertion 정리
- [ ] 9. DB: 마이그레이션 012 작성
- [ ] 10. 프론트엔드 타입: `types/database.ts`, `lib/api-client.ts` 두 필드 제거
- [ ] 11. 프론트엔드 분석: `lib/analysis/profile.ts`, `lib/analysis/aggregate.ts` 입력 교체
- [ ] 12. 프론트엔드 분석 테스트 갱신
- [ ] 13. UI: `TradeHoldingSection.tsx` 신규 작성
- [ ] 14. UI: `TradeMetaSellForm.tsx` 적용
- [ ] 15. UI: `TradeEditPanel.tsx` 적용
- [ ] 16. UI: `TradeDetail.tsx` 적용
- [ ] 17. UI: `TradeBasicForm.tsx` 종목코드 라벨 "(자동입력)" 추가
- [ ] 18. UI 테스트: `TradeFreeTextField.test.tsx` 라벨 교체
- [ ] 19. grep 0 매칭 확인: `reflection_note|improvement_note|잘한 점|개선할 점`
- [ ] 20. 검증: `pnpm tsc --noEmit && pnpm test`
- [ ] 21. 검증: `poetry run pytest -q`
- [ ] 22. 수동 확인: 매수 등록, 매도 등록 → meta, 거래 상세(매도), 거래 수정(매도)

## 우려사항 / 리스크

- DB 마이그레이션은 코드 변경(1~8) 완료 후 마지막에 적용
- `reviewHabit`/`reflectionRate` 수치가 이전 회차와 달라질 수 있음 (사용자 확인 완료)
- grep으로 누락 없는지 반드시 확인
