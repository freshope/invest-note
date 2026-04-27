# Spec: 전략/거래 UI 후속 수정

## 배경 / 문제

직전 `feature/refine-sell-trade-ui` 머지 이후 매도 거래 화면에서 4가지 잔여 이슈가 보고됨.

1. 매도 거래 상세의 "보유 정보 (자동 계산)" 섹션이 실제로는 계획/실제 전략까지 포함하므로 "전략 결과"가 더 적합한 명칭이다.
2. 매도 거래 상세에서 보유정보 카드 안의 "계획 전략"과 별도 "근거/감정" 섹션의 "전략" 라인이 중복 표시된다 (저장 시 `strategy_type = strategyEvaluation.planned`로 동기화되기 때문).
3. 거래 등록 폼의 "종목코드(자동입력)" 필드가 `bg-muted/50`인 반면 가격/수량/수수료/세금은 `bg-muted`라 시각적으로 톤이 어긋난다.
4. 매도 등록(step 2 meta)과 수정 화면에 자동 계산되는 "거래 결과 / 보유 정보" 카드가 노출돼 입력에 집중하기 어렵다.

## 목표

- 매도 거래 상세에서 자동 계산 카드 타이틀이 "전략 결과 (자동 계산)"로 표기된다.
- 매도 거래 상세에서 "전략"이 한 곳(전략 결과 카드의 "계획 전략")에만 표시되고, "근거/감정" 섹션의 "전략" 라인은 더 이상 노출되지 않는다.
- 거래 등록 폼의 "종목코드(자동입력)" 필드와 "총액(자동계산)" 필드가 일반 입력과 동일하게 `bg-muted`로 표시된다.
- 매도 등록(step 2)과 매도 수정 화면에서 "거래 결과"·"보유 정보" 카드가 더 이상 표시되지 않는다 (상세 화면에서는 그대로 유지).

## 설계

### 접근 방식

- **Issue 1**: `TradeHoldingSection`이 사실상 매도 전용이므로 컴포넌트 내부의 하드코딩 문구를 직접 변경한다. prop으로 분기하지 않는다 (불필요한 일반화 회피).
- **Issue 2**: `TradeDetail`의 "근거/감정" 섹션 내 "전략" InfoRow 노출 조건을 매수일 때만(`isBuy && trade.strategy_type`) 표시하도록 좁힌다. 매도 저장 로직은 변경하지 않는다.
- **Issue 3**: `TradeBasicForm`의 종목코드 표시 div(`bg-muted/50` → `bg-muted`)와 총액 자동계산 div(`bg-muted/50` → `bg-muted`)를 일반 Input과 동일한 톤으로 맞춘다. 자동입력/자동계산 표시는 라벨 보조 문구("(자동입력)", "(자동계산)")로만 구분.
- **Issue 4**: `TradeMetaSellForm`의 "거래 결과" 인라인 섹션 + `TradeHoldingSection` 호출을 모두 제거. `TradeEditPanel`도 `isSell` 가드 안의 "거래 결과" 인라인 섹션 + `TradeHoldingSection` 호출을 제거. 두 곳에서 더 이상 사용되지 않게 되는 헬퍼(`BreakdownRow` 등)와 임포트도 정리.
- 상세 화면(`TradeDetail`)은 결과/전략 결과 카드를 그대로 유지.

### 주요 변경 파일

- `app/src/components/records/TradeHoldingSection.tsx` — 카드 타이틀 "보유 정보 (자동 계산)" → "전략 결과 (자동 계산)" (line 39).
- `app/src/components/records/TradeDetail.tsx` — "근거/감정" 섹션 내 "전략" InfoRow를 `isBuy`일 때만 렌더 (line 254 근처).
- `app/src/components/records/TradeBasicForm.tsx` — 종목코드 표시 div(`bg-muted/50` → `bg-muted`, font-medium 추가)와 총액 표시 div(`bg-muted/50` → `bg-muted`) 통일 (line 362, 441).
- `app/src/components/records/TradeMetaSellForm.tsx` — "거래 결과" 인라인 섹션(line 96-161)과 `TradeHoldingSection` 호출(line 163-168) 제거. 미사용 import(`BreakdownRow`, `TradeHoldingSection`, `cn`, summary 관련 유틸 등) 정리.
- `app/src/components/records/TradeEditPanel.tsx` — `isSell` 가드 안의 "거래 결과" 인라인 섹션(line 299-355)과 `TradeHoldingSection` 호출(line 357-364) 제거. 미사용 import/헬퍼 정리. (저장 로직의 `strategy_type: isSell ? summary?.strategyEvaluation?.planned ?? null : ...` 분기는 유지 — 저장값에는 영향 없음.)

## 구현 체크리스트

- [x] `TradeHoldingSection.tsx` 타이틀을 "전략 결과 (자동 계산)"로 변경
- [x] `TradeDetail.tsx`의 "근거/감정" 섹션에서 "전략" 라인을 `isBuy`일 때만 노출하도록 조건 추가
- [x] `TradeBasicForm.tsx`의 종목코드/총액 표시 div를 `bg-muted`로 통일하고 폰트 weight를 일반 Input과 맞춤
- [x] `TradeMetaSellForm.tsx`에서 "거래 결과" 섹션과 `TradeHoldingSection` 호출 제거 + 미사용 import 정리
- [x] `TradeEditPanel.tsx`에서 매도용 "거래 결과" 섹션과 `TradeHoldingSection` 호출 제거 + 미사용 import/헬퍼 정리
- [x] 타입 체크 통과 (`pnpm -C app exec tsc --noEmit`)
- [ ] 매수/매도 등록·수정·상세 화면을 직접 열어 확인 (`pnpm -C app dev`)

## 우려사항 / 리스크

- `TradeMetaSellForm`에서 "보유 정보"를 제거하면 매도 step 2에서 사용자가 "보유일/평균 매수일"을 즉시 확인할 단서를 잃는다. 다만 사용자 요청이 "입력 집중"이므로 의도된 트레이드오프로 본다.
- `TradeDetail`의 "전략" 라인을 매도에서 숨기더라도 매도 거래의 `trade.strategy_type` 값 자체는 DB에 그대로 남음 (저장 로직 유지). 화면 표시만 변경.

## 검증

- `pnpm -C app exec tsc --noEmit` 으로 타입 체크.
- `pnpm -C app dev` 실행 후:
  - 매도 거래 등록 step 2: 메타 입력 영역만 보이고 "거래 결과", "보유 정보" 카드가 없는지 확인.
  - 매도 거래 수정: 동일하게 두 카드가 없는지 확인.
  - 매도 거래 상세: "전략 결과 (자동 계산)" 타이틀 노출, "근거/감정" 섹션에 "전략" 라인이 사라졌는지 확인.
  - 매수 거래 상세: 기존처럼 "근거/감정" 섹션에 "전략" 라인이 그대로 표시되는지 확인 (회귀 방지).
  - 거래 등록(매수/매도) 폼: 종목코드와 총액 필드가 가격/수량/수수료 필드와 동일한 배경 톤인지 확인.
