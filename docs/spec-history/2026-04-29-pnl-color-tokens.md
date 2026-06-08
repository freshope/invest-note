# Spec: PnL 색상 클래스 토큰화

> 완료: 2026-04-29

## 배경 / 문제

`text-[var(--rise)]`, `bg-[var(--fall)]/10`, `border-[var(--rise)]/30` 등 PnL 상승/하강 색상을 표현하는 Tailwind arbitrary value 클래스가 31개 위치(컴포넌트 9곳 + 유틸 2곳)에 raw string으로 흩어져 있다. 색상 의미를 변경하거나 새 변형(예: focus ring, hover bg)을 추가할 때 모든 호출부를 검색·수정해야 한다.

기존 `:root --rise / --fall` CSS 변수는 단일 지점(globals.css:6-7)에 정의돼 있지만, "rise/fall 의미를 갖는 클래스 문자열" 자체는 아직 토큰화되지 않은 상태.

## 목표

- `app/src/lib/constants/colors.ts`를 신규 추가하여 PnL 색상 클래스를 단일 지점에 모은다.
- 31개 raw 문자열 사용처를 모두 상수 import로 교체한다.
- 기존 `:root --rise / --fall` CSS 변수 정의는 변경하지 않는다 (백로그 명시).
- 동작·렌더 결과는 동일하게 유지한다 (시각적 회귀 없음).
- `pnpm tsc --noEmit` 통과.

## 설계

### 접근 방식

**1. `app/src/lib/constants/colors.ts` 신규 — 객체 구조로 그룹화**

raw string을 그대로 상수화하여 Tailwind JIT가 컴파일 타임에 클래스를 추출할 수 있도록 한다 (동적 문자열 조합은 JIT가 못 잡으므로 금지).

```ts
export const PNL_COLORS = {
  rise: {
    text: "text-[var(--rise)]",
    bg: "bg-[var(--rise)]",
    bgSoft: "bg-[var(--rise)]/10",
    border: "border-[var(--rise)]",
    borderSoft: "border-[var(--rise)]/30",
  },
  fall: {
    text: "text-[var(--fall)]",
    bg: "bg-[var(--fall)]",
    bgSoft: "bg-[var(--fall)]/10",
    border: "border-[var(--fall)]",
    borderSoft: "border-[var(--fall)]/30",
  },
} as const;
```

**왜 객체 구조인가**: 31개 호출부에서 `PNL_COLORS.rise.text`, `PNL_COLORS.fall.bgSoft` 형태로 의미가 자명하고, 향후 변형 추가 시 같은 키 패턴 유지가 쉽다.

**2. 동적 분기 헬퍼는 기존 `signColor()`만 사용**

`signColor()` (format.ts:53)는 이미 0/양/음 분기 + fallback을 처리하는 표준 헬퍼. 내부에서 `PNL_COLORS.rise.text` / `PNL_COLORS.fall.text`를 참조하도록 변경.

추가 헬퍼(예: `signBg()`)는 만들지 않는다 — 호출부에서 `isBuy ? PNL_COLORS.rise.bg : PNL_COLORS.fall.bg` 형태로 직접 분기.

**3. Tailwind JIT 호환성**

`text-[var(--rise)]` 같은 arbitrary value 클래스는 Tailwind JIT가 정적 string에서 추출. 동적 보간(`text-[var(--${dir})]`)은 금지.

### 주요 변경 파일

- `app/src/lib/constants/colors.ts` — **신규**. `PNL_COLORS` 객체 export.
- `app/src/lib/format.ts` — `signColor()` 내부.
- `app/src/lib/constants/trading.ts` — `RESULTS` 배열.
- `app/src/components/records/TradeDetail.tsx` (4곳)
- `app/src/components/records/TradeCard.tsx` (3곳)
- `app/src/components/records/TradeBasicForm.tsx` (2곳)
- `app/src/components/records/TradeEditPanel.tsx` (3곳)
- `app/src/components/analysis/SummaryCards.tsx` (2곳)
- `app/src/components/analysis/DiversificationPanel.tsx` (2곳)
- `app/src/components/analysis/WinRateBar.tsx` (2곳)
- `app/src/components/analysis/ReviewQualityPanel.tsx` (3곳)

`cn()` 또는 템플릿 리터럴로 합성된 부분(`bg-[var(--rise)]/10 text-[var(--rise)] border-[var(--rise)]/30`)은 `cn(PNL_COLORS.rise.bgSoft, PNL_COLORS.rise.text, PNL_COLORS.rise.borderSoft)`로 분해.

## 구현 체크리스트

- [x] `app/src/lib/constants/colors.ts` 신규 작성 (`PNL_COLORS` 객체)
- [x] `app/src/lib/format.ts` `signColor()` — `PNL_COLORS` 참조로 교체
- [x] `app/src/lib/constants/trading.ts` `RESULTS` — `PNL_COLORS` 참조로 교체
- [x] `app/src/components/records/TradeDetail.tsx` 4곳 교체
- [x] `app/src/components/records/TradeCard.tsx` 3곳 교체
- [x] `app/src/components/records/TradeBasicForm.tsx` 2곳 교체
- [x] `app/src/components/records/TradeEditPanel.tsx` 3곳 교체
- [x] `app/src/components/analysis/SummaryCards.tsx` 2곳 교체
- [x] `app/src/components/analysis/DiversificationPanel.tsx` 2곳 교체
- [x] `app/src/components/analysis/WinRateBar.tsx` 2곳 교체
- [x] `app/src/components/analysis/ReviewQualityPanel.tsx` 3곳 교체
- [x] `grep -rn "var(--rise)\|var(--fall)" app/src` — `globals.css`/`colors.ts` 외 잔존 raw 문자열 0건 확인
- [x] `pnpm tsc --noEmit` 통과
- [x] 거래 기록·분석 탭에서 빨강/파랑 색상 시각 회귀 없음을 dev 서버에서 확인

## 검증 방법

1. **타입 체크**: `pnpm -C app exec tsc --noEmit`
2. **잔존 raw string 확인**:
   ```bash
   grep -rn "var(--rise)\|var(--fall)" app/src
   ```
   → `app/src/app/globals.css`(`:root` 정의)와 `app/src/lib/constants/colors.ts`(상수 정의) 외에는 매치되지 않아야 함.
3. **시각 회귀 확인** (`pnpm -C app dev`):
   - 거래 기록 페이지: 매수(빨강 bg) / 매도(파랑 bg) 카드, 인라인 PnL 색상
   - 거래 상세 footer: 결과 뱃지 (SUCCESS=빨강, FAIL=파랑, BREAKEVEN=muted)
   - 거래 편집 폼: 매수/매도 탭의 active/inactive 색상
   - 분석 탭: 손익 요약 카드, 분산 패널, 승률 바, 리뷰 품질 패널의 양/음 색상

## 우려사항 / 리스크

- **Tailwind JIT 추출 실패 위험**: `trading.ts`의 `RESULTS[i].color`가 이미 같은 패턴으로 production에서 동작 중이므로 기술적 위험은 낮음. 그래도 dev 빌드에서 1차 시각 확인 필수.
- **스코프 inflation 금지**: `signBg()` 같은 추가 헬퍼는 만들지 않는다. 백로그 명시는 "클래스 문자열만 상수화" — API 설계 변경은 별도 작업.
