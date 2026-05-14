# Spec: TradeTypeBadge 추출 (FE simplify Round 4)

> 완료: 2026-04-30

## 배경 / 문제

`docs/backlog.md` "FE simplify — 컴포넌트 추출" 섹션의 첫 번째 항목.
Round 2(3개) / Round 3(1개) 처리 완료 후, Round 4 후보 중 가장 위험도 낮고 도메인 의미가 명확한 항목.

매수/매도 라벨 뱃지가 인라인으로 반복되며, `PNL_COLORS.rise/fall` 분기도 동일 패턴으로 흩어져 있다. 단독 진행 (ProgressTrack 등 나머지는 후속 Round 로 deferred).

## 목표

- `src/components/shared/TradeTypeBadge.tsx` 신규 — `tradeType: TradeType` props 만 받는 뱃지 컴포넌트로 매수/매도 라벨 + bgSoft/text 색을 일원화
- `src/lib/constants/trading.ts` 에 `TRADE_TYPE_LABELS: Record<TradeType, string>` 상수 추가 (`{ BUY: "매수", SELL: "매도" }`)
- `getTradeTypeAccent(tradeType)` 헬퍼로 `PNL_COLORS.rise | fall` 분기 추출 (좌측/상단 컬러 액센트 줄 재사용)
- `TradeCard.tsx`, `TradeHeaderCard.tsx` 두 곳의 인라인 분기를 헬퍼/래퍼로 교체
- 시각적/동작 회귀 없음

## 설계

### 접근 방식

백로그 표현은 "TradeDetail / TradeCard / TradeEditPanel 3 곳" 이지만, 실제 매수/매도 라벨 뱃지 인라인 패턴은 다음 2 파일에만 존재:

- `app/src/components/records/TradeCard.tsx:30-51` — 좌측 컬러 액센트(`isBuy ? PNL_COLORS.rise.bg : PNL_COLORS.fall.bg`) + 매수/매도 뱃지(`isBuy ? cn(rise.bgSoft, rise.text) : cn(fall.bgSoft, fall.text)` + `isBuy ? "매수" : "매도"`)
- `app/src/components/records/TradeHeaderCard.tsx:37-73` — `accent = isBuy ? PNL_COLORS.rise : PNL_COLORS.fall` 변수 + 상단 1px `accent.bg` 라인 + `accent.bgSoft / accent.text` 뱃지 + `isBuy ? "매수" : "매도"`

`TradeDetail` / `TradeEditPanel` 은 둘 다 `TradeHeaderCard` 를 호출하므로 자동으로 함께 일원화된다.

3 단계로 추출:

1. **상수**: `lib/constants/trading.ts` 에 `TRADE_TYPE_LABELS: Record<TradeType, string> = { BUY: "매수", SELL: "매도" }` 추가
2. **헬퍼**: `lib/constants/colors.ts` 에 `getTradeTypeAccent(tradeType: TradeType)` 추가 — `tradeType === "BUY" ? PNL_COLORS.rise : PNL_COLORS.fall`. 컬러 액센트 줄(좌측/상단 막대)은 그대로 `accent.bg` 클래스로 사용
3. **컴포넌트**: `components/shared/TradeTypeBadge.tsx` — props `{ tradeType: TradeType; className?: string; size?: "sm" | "md" }`. `size="sm"` 은 `text-[11px] px-1.5 py-0.5` (TradeCard 용), `size="md"` 는 `text-[12px] px-2 py-0.5` (TradeHeaderCard 용)

`TradeHeaderCard` props 는 `isBuy: boolean` → `tradeType: TradeType` 으로 시그니처 변경 (호출부 2 곳 함께 수정).

### 주요 변경 파일

- `app/src/lib/constants/trading.ts` — `TRADE_TYPE_LABELS` 상수 추가
- `app/src/lib/constants/colors.ts` — `getTradeTypeAccent` 헬퍼 추가
- `app/src/components/shared/TradeTypeBadge.tsx` — 신규
- `app/src/components/records/TradeCard.tsx` — 인라인 뱃지/색 분기 → `<TradeTypeBadge>` + `getTradeTypeAccent(...)`
- `app/src/components/records/TradeHeaderCard.tsx` — 인라인 뱃지/색 분기 → `<TradeTypeBadge>` + `getTradeTypeAccent(...)`. props `isBuy` → `tradeType: TradeType`
- `app/src/components/records/TradeDetail.tsx` — `TradeHeaderCard` 호출의 `isBuy={isBuy}` → `tradeType={trade.trade_type}`
- `app/src/components/records/TradeEditPanel.tsx` — 동일 (`isBuy={!isSell}` → `tradeType={isSell ? "SELL" : "BUY"}`)

## 구현 체크리스트

- [x] `lib/constants/trading.ts` 에 `TRADE_TYPE_LABELS` 상수 추가
- [x] `lib/constants/colors.ts` 에 `getTradeTypeAccent` 헬퍼 추가
- [x] `components/shared/TradeTypeBadge.tsx` 신규 작성 (sm/md 두 사이즈)
- [x] `TradeCard.tsx` 인라인 뱃지/색 분기 교체
- [x] `TradeHeaderCard.tsx` 인라인 뱃지/색 분기 교체 + props 시그니처 변경
- [x] `TradeDetail.tsx` / `TradeEditPanel.tsx` 호출부 시그니처 업데이트
- [x] 타입 체크 통과 (`pnpm -C app exec tsc --noEmit`)
- [x] 단위 테스트 통과 (`pnpm -C app test`) — 110/110 pass

## 우려사항 / 리스크

- `TradeHeaderCard` props 시그니처 변경(`isBuy` → `tradeType`)으로 호출부 2 곳 동시 수정 필요. 호출부가 한정적이라 위험은 낮으나, 동일 PR 내 일관성 확인 필수
- size 변형(sm/md) 의 padding/font-size 가 기존과 1px 라도 다르면 시각 회귀 — 기존 인라인 클래스(`text-[11px] px-1.5 py-0.5`, `text-[12px] px-2 py-0.5`)를 그대로 보존
