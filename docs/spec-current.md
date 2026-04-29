# Spec: formatPctSigned 헬퍼 도입 + HoldingCard 마이그레이션

## 배경 / 문제

- `HoldingCard.tsx:104-105`에 `${pct > 0 ? "+" : ""}${pct.toFixed(2)}%` 인라인 패턴이 있음.
- 코드베이스 전체에서 동일 패턴은 이 한 곳뿐(다른 % 표시는 모두 부호 없는 비중·승률·비율).
- `formatPnL` 패턴(부호 + 포맷 + 단위)과 같은 형태의 헬퍼가 % 용으로는 부재.
- 백로그 라인 번호 주석(112-113)이 실제(104-105)와 어긋남.

## 목표

1. `formatPctSigned(n, decimals)` 헬퍼가 `app/src/lib/format.ts`에 존재하고 단위 테스트가 통과한다.
2. `HoldingCard.tsx`가 인라인 표현 대신 헬퍼를 사용한다.
3. 백로그 항목이 제거된다(완료 처리).
4. 타입 체크와 기존 테스트가 모두 통과한다.

## 설계

### 접근 방식

`formatPnL`(format.ts:5-10)을 그대로 미러링하되 % 용으로 일반화.

```ts
export function formatPctSigned(n: number, decimals: number = 2): string {
  const rounded = Number(n.toFixed(decimals));
  if (rounded === 0) return `${(0).toFixed(decimals)}%`;
  const sign = rounded > 0 ? "+" : "";
  return `${sign}${rounded.toFixed(decimals)}%`;
}
```

- `decimals` 기본값 2 → 호출부 단순화.
- `Number(n.toFixed(decimals))`로 먼저 반올림 → `-0` 정규화로 "-0.00%" 방지.
- 0은 부호 없이 `0.00%`(decimals=0이면 `0%`).

### 주요 변경 파일

- `app/src/lib/format.ts` — `formatPctSigned` export 추가
- `app/src/lib/__tests__/format.test.ts` — 단위 테스트 추가
- `app/src/components/home/HoldingCard.tsx` — 인라인 → 헬퍼 호출 교체
- `docs/backlog.md` — 완료 항목 제거

## 구현 체크리스트

- [x] `app/src/lib/format.ts`에 `formatPctSigned(n, decimals)` 추가
- [x] `app/src/lib/__tests__/format.test.ts`에 단위 테스트 추가
- [x] `app/src/components/home/HoldingCard.tsx` line 104-105를 헬퍼 호출로 교체
- [x] `docs/backlog.md`에서 해당 항목 제거
- [x] `pnpm -C app test src/lib/__tests__/format.test.ts` 통과
- [x] `pnpm -C app exec tsc --noEmit` 통과

## 우려사항 / 리스크

- **단일 사용처**: 직접 효익은 작음. 향후 등락률 표시 추가 대비 SOT 선점 — 사용자 인지된 결정.
- **`-0` 정규화 변경**: `HoldingCard`는 이미 사전 반올림하므로 실제 영향 없음.
