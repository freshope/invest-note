# Spec: PNL_COLORS 순환 import 구조적 가드

## 배경 / 문제

`app/src/lib/constants/trading.ts:9` 가 `app/src/lib/constants/colors.ts` 의 `PNL_COLORS` 를 import 한다. 현재는 단방향이라 순환 아님.

그러나 `colors.ts:30-33` 의 `getTradeTypeAccent(tradeType)` 가 `tradeType === "BUY"` 리터럴 비교를 사용하는데 — 누군가 가독성을 위해 `import { TRADE_TYPE } from "./trading"` 추가하는 순간 즉시 순환 발생. 그러면 모듈 로딩 순서에 따라 `PNL_COLORS` 가 `undefined` 가 되어 런타임 에러. 메모리(`feedback_circular_import_colors_trading.md`) 에 과거 인시던트로 기록되어 있음.

`colors.ts:31` 의 코멘트가 가드 역할을 하지만 코드 레벨에서 강제되지 않음.

## 목표

- `PNL_COLORS` 와 `PnlAccent` 타입을 leaf 모듈 `pnl-colors.ts` 로 추출.
- `trading.ts` 가 더 이상 `colors.ts` 를 import 하지 않음 (`pnl-colors.ts` 직접 import).
- `colors.ts` 는 `pnl-colors.ts` 에서 두 식별자를 re-export — 기존 사용처(8개) 의 import 경로 변경 없이 후방 호환.
- 결과: `pnl-colors.ts` 가 leaf 모듈, `trading.ts` 와 `colors.ts` 사이 직접 의존 없음 — 구조적으로 순환 발생 불가.
- `pnpm tsc`, `pnpm test` 통과.

> ESLint `import/no-cycle` 룰 활성화는 본 spec 비범위. backlog `feature/eslint-cleanup` 에서 처리(현재 `pnpm lint` 가 329 errors 상태라 룰 추가만 깔끔히 적용 어려움).

## 설계

### 옵션 A vs B 결정

- **옵션 A (모든 사용처 import 경로 일괄 변경)**: 9 파일 수정. colors.ts 가 PNL_COLORS 경유지 역할에서 완전히 빠짐.
- **옵션 B (re-export 유지)** ✅ **채택**: 3 파일 수정. colors.ts 가 re-export 만 함. 변경 폭 최소 + 핵심 위험(trading↔colors 직접 의존) 동일하게 제거.

옵션 B 채택 사유: 본 spec 의 목표는 "trading.ts 와 colors.ts 사이 직접 의존 끊기"이며 옵션 B 만으로 충족. 옵션 A 의 추가 정직성은 사용처 8 파일 변경 비용 대비 가치 낮음.

### 새 파일: `app/src/lib/constants/pnl-colors.ts`

`colors.ts` 의 `PNL_COLORS` / `PnlAccent` 정의를 옮김. 헤더 주석에 leaf 역할 명시.

### 변경 파일

- **`colors.ts`**: 정의 제거 → `pnl-colors` 에서 import 후 `export { PNL_COLORS, type PnlAccent }`. `getTradeTypeAccent` 유지. 더 이상 의미 없는 line 31 의 "역참조 순환" 경고 코멘트 제거.
- **`trading.ts`**: `import { PNL_COLORS } from "./colors"` → `"./pnl-colors"`.
- 컴포넌트/유틸 8 파일: 변경 없음 (re-export 통해 호환).

### 비범위

- ESLint `import/no-cycle` 룰 활성화 — backlog `feature/eslint-cleanup`
- `getTradeTypeAccent` 의 `"BUY"` 리터럴을 `TRADE_TYPE.BUY` 로 교체 — 현재 colors.ts → trading.ts 의존을 새로 만드는 변경. 본 spec 비범위.

## 구현 체크리스트

- [x] `pnl-colors.ts` 신규 (PNL_COLORS + PnlAccent 이전, leaf 역할 헤더 주석)
- [x] `colors.ts`: 정의 제거 + `pnl-colors` 에서 re-export, 가드 코멘트 정리
- [x] `trading.ts`: import 경로 변경
- [x] `pnpm tsc` ✅
- [x] `pnpm test` ✅ (124 passed)
- [x] 메모리 `feedback_circular_import_colors_trading.md` 업데이트 (구조적 가드 완료 + ESLint 후속 작업 메모)

## 검증

1. **타입 통과**: `pnpm tsc`
2. **테스트 통과**: `pnpm test`
3. **그래프 검증**:
   - `grep -n 'from.*colors' app/src/lib/constants/trading.ts` → `./pnl-colors` 만 매칭
   - `grep -n 'from.*trading' app/src/lib/constants/colors.ts` → 빈 결과

## 우려사항 / 리스크

- **re-export 의 미묘함**: `colors.ts` 가 여전히 PNL_COLORS 를 알고 있어, 미래 리팩토링 시 colors.ts 에서 trading 을 import 추가 → 사용처가 colors 를 통해 PNL_COLORS 받으면 순환 재발. 메모리 가드 + ESLint 룰 도입(별도 spec)으로 보완.
- **Tailwind JIT**: PNL_COLORS 의 정적 string 값은 그대로이므로 JIT 추출 영향 없음.
