# 분석 탭 PnL 표시 패턴 통합

## 목표

분석 탭 3개 breakdown 컴포넌트(`EmotionBreakdown` / `StrategyBreakdown` / `ReasoningBreakdown`)의 PnL 인라인 표시 패턴을 공용 컴포넌트 `PnLLine` + `formatPnL` 헬퍼로 통합한다.

## 배경

현재 세 컴포넌트가 동일한 인라인 패턴을 반복하고 있어, 표시 규칙(부호/색/포맷) 변경 시 세 곳 동시 수정이 필요하다. 백로그 "분석 탭 성능 / 유지보수" 섹션 명시 항목.

```tsx
{item.avgPnL !== 0 && (
  <span className={cn("ml-1.5", item.avgPnL > 0 ? "text-[var(--rise)]" : "text-[var(--fall)]")}>
    {item.avgPnL > 0 ? "+" : ""}{fmt(Math.round(item.avgPnL))}원
  </span>
)}
```

## 변경 대상

- `app/src/lib/format.ts` — `formatPnL(value: number): string` 추가, round 후 0 가드(`-0` 정규화)
- `app/src/lib/__tests__/format.test.ts` — `formatPnL` 단위 테스트 5개 추가
- `app/src/components/analysis/PnLLine.tsx` — 신규 (공용 컴포넌트)
- `app/src/components/analysis/EmotionBreakdown.tsx` — `<PnLLine value={item.avgPnL} />` 교체
- `app/src/components/analysis/StrategyBreakdown.tsx` — 동일
- `app/src/components/analysis/ReasoningBreakdown.tsx` — 동일

## 구현 단계

1. `format.ts`에 `formatPnL` 추가 (Math.round + 0 가드 + 양수 부호 + `fmt` 호출 + "원" 접미)
2. `PnLLine.tsx` 작성 (값 0이면 null 반환, 양/음 색상 클래스 적용)
3. 3개 breakdown 컴포넌트의 인라인 블록을 `<PnLLine>`으로 교체
4. 각 파일에서 사용하지 않는 `cn`, `fmt` import 정리
5. `formatPnL` 단위 테스트 추가 (양수/음수/0/소수 round/-0 정규화)
6. 타입 체크와 단위 테스트 실행

## 부수 개선 — `-0` 표시 버그 수정

`Math.round(-0.4)`가 `-0`을 반환해 `toLocaleString`이 `"-0"`을 출력하던 잠재 버그를 발견. 변경 전 인라인 패턴에도 존재하던 회귀 아님. `formatPnL`에서 `rounded === 0 ? "0원"` 가드로 `±0` 모두 부호 없이 "0원" 정규화.

표시 변경: `avgPnL = ±0.4` 같은 round-to-zero 값에서 부호("+"/"−") 노이즈 제거.

## 완료 기준

- `pnpm tsc` 통과
- `pnpm test` 통과 — 96 테스트 (기존 91 + 신규 5)
- 분석 탭 진입 시 양수/음수/0 PnL 표시 정상 (round-to-zero 부호 제거 외 회귀 없음)

## 후속 과제 (이번 spec 범위 외)

- 분석 API `.limit(1000)` 가드 — FIFO PnL 매칭에 영향, 별도 설계 필요
- tempo 식 단순화 — 백/프 정합성 + SCALPING 페널티 제거
