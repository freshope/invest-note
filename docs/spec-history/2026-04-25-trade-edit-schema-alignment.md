> 완료: 2026-04-25

# Spec: TradeEditPanel 스키마 일관성 정렬

## 배경 / 문제

`TradeBasicForm`(거래 신규 등록)과 `TradeEditPanel`(거래 수정 패널)은 동일한 4개의 숫자 입력 필드(price, quantity, commission, tax)를 다루지만 zod 스키마 표현이 다릅니다.

- `TradeBasicForm`: `price: z.number().positive(...)` 등 — number 기반
- `TradeEditPanel`: `price_display: z.string()` 등 — 포맷된 문자열을 폼 상태에 그대로 보관

이 불일치 때문에 (1) 검증 메시지가 수정 패널에서만 비어 있고, (2) 동일 형식 헬퍼가 두 파일에 거의 그대로 중복 정의되어 있으며, (3) 제출 시 `parseRaw(values.price_display)` 같은 우회 변환이 필요합니다.

## 목표

- TradeEditPanel의 zod 스키마가 TradeBasicForm과 정확히 같은 형태(필드명·검증 규칙·메시지)로 동작한다.
- 두 폼 모두 폼 상태를 `number`로 보유하고, 표시 단계에서만 천단위 콤마 문자열로 변환한다.
- 숫자 입력 포맷 헬퍼는 `app/src/lib/format.ts` 한곳에서만 정의되고 두 컴포넌트가 import해서 사용한다.
- `pnpm tsc --noEmit` 통과, 기존 거래 등록·수정·자동계산 흐름이 회귀 없이 동작.

## 설계

### 접근 방식

1. `app/src/lib/format.ts`에 폼 입력용 헬퍼 3개 추가
   - `fmtNumberInput(n)` — n > 0이면 toLocaleString, 그 외 ""
   - `formatNumberInput(raw)` — 숫자 외 문자 제거 → 천단위 콤마 포맷
   - `parseNumberInput(s)` — "," 제거 후 Number(s) || 0

2. `TradeEditPanel` zod 스키마를 TradeBasicForm과 동일하게 교체
   - 필드명: `price_display` 등 → `price`/`quantity`/`commission`/`tax`
   - 검증: price·quantity → `.positive()`, commission·tax → `.min(0)`

3. `TradeEditPanel` 폼 흐름 number 기반으로 단순화

4. `TradeBasicForm`도 format.ts에서 import, 로컬 헬퍼 제거

### 주요 변경 파일

- `app/src/lib/format.ts` — 헬퍼 3개 추가
- `app/src/components/records/TradeEditPanel.tsx` — 스키마/폼/제출 number 기반 교체
- `app/src/components/records/TradeBasicForm.tsx` — 로컬 헬퍼 제거 후 format.ts import

## 구현 체크리스트

- [x] `app/src/lib/format.ts`에 `fmtNumberInput`, `formatNumberInput`, `parseNumberInput` 추가
- [x] `TradeBasicForm.tsx`의 로컬 `fmtNum`/`formatInput`/`parseNum` 제거하고 format.ts에서 import
- [x] `TradeEditPanel.tsx` zod 스키마 교체
- [x] `TradeEditPanel.tsx` defaultValues/reset에서 `fmtNum` 제거하고 number 직접 주입
- [x] `TradeEditPanel.tsx` Controller 4개를 새 패턴으로 변경
- [x] `TradeEditPanel.tsx` watch/onSubmit에서 `parseRaw` 제거
- [x] 로컬 헬퍼 3개 제거
- [x] 타입 체크 통과 (`pnpm tsc --noEmit`)
- [x] 수동 검증: 등록/수정/자동계산 회귀 없음

## 우려사항 / 리스크

- commission/tax는 0이 정상값이므로 `.min(0)` 사용 (`.positive()` 그대로면 검증 실패)
