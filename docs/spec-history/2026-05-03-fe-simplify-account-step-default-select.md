# Spec: ImportTradesPanel/AccountStep 자동 단일 계좌 선택 effect 제거

> 완료: 2026-05-03

## 배경 / 문제

`ImportTradesPanel/AccountStep.tsx:25-28` 의 자동 단일 계좌 선택 effect 는 effect-setState 안티패턴 (외부 입력에 반응해 부모 state 를 setter 로 동기화). Round 4 fe-simplify 에서 deferred 된 후속 항목 (`docs/spec-history/2026-05-03-fe-simplify-round4-useeffect-antipatterns.md:250`).

탐색 결과 추가로 `eligibleAccounts` useMemo (line 20-23) 도 effect 안에서만 참조되고 렌더 트리는 인라인으로 `findBrokerKeyByAccountBroker` 를 호출하므로, effect 와 함께 dead code 가 됩니다.

## 목표

- `AccountStep` 의 useEffect / useMemo 모두 제거 (effect-setState 0개, dead memo 0개).
- 부모(`ImportTradesPanel`) 의 `useState` lazy initializer 로 "마운트 시점에 eligible 이 정확히 1개면 그 계좌를 default select" 결정.
- `TradeList` 의 `importKey++` 패턴과 자연 호환 (패널 열기 = 새 인스턴스 = lazy initializer 1회 실행).
- 헬퍼 `getInitialSelectedAccountId(accounts)` 단위 테스트로 회귀 방어.

## 설계

### 접근 방식

Round 4 항목 2 (`TradeBasicForm` 의 `getInitialAccountId` 헬퍼) 와 동일한 "부모 lazy initializer + 순수 헬퍼" 패턴.

```tsx
// ImportTradesPanel/index.tsx (컴포넌트 외부)
export function getInitialSelectedAccountId(accounts: Account[]): string {
  const eligible = accounts.filter(
    (a) => findBrokerKeyByAccountBroker(a.broker) !== null,
  );
  return eligible.length === 1 ? eligible[0].id : "";
}

// 컴포넌트 내부
const [selectedAccountId, setSelectedAccountId] = useState<string>(
  () => getInitialSelectedAccountId(accounts),
);
```

`AccountStep` 의 useEffect / useMemo 는 모두 삭제, `useEffect` / `useMemo` import 도 제거.

### 동작 변경 (의도적)

- **변경 전**: 패널 열린 동안 `accounts` 가 바뀌어 eligible 이 1개가 되면 mid-session 자동 선택.
- **변경 후**: 마운트 시점에만 결정. mid-session refetch 결과로 사용자가 비워둔 선택을 덮어쓰지 않음.

`RecordsPage` 가 `isLoading` Skeleton 으로 막은 후에야 `TradeList` → `ImportTradesPanel` 마운트되므로 첫 마운트 시점 `accounts` 는 항상 채워짐.

### 주요 변경 파일

- `app/src/components/records/ImportTradesPanel/index.tsx` — `getInitialSelectedAccountId` 헬퍼 export, `useState` lazy initializer 적용.
- `app/src/components/records/ImportTradesPanel/AccountStep.tsx` — useEffect / useMemo / 두 import 제거.
- `app/src/components/records/__tests__/ImportTradesPanel.test.tsx` — 신규. 헬퍼 단위 테스트 5 시나리오.
- `docs/backlog.md` — 본 항목 제거.

## 구현 체크리스트

- [x] `ImportTradesPanel/index.tsx` 에 `getInitialSelectedAccountId` 헬퍼 추가 + `useState` lazy initializer 적용
- [x] `AccountStep.tsx` 에서 useEffect / useMemo / 관련 import 제거
- [x] `__tests__/ImportTradesPanel.test.tsx` 신규 작성 (5 시나리오: eligible 0 / 1 / 2+ / ineligible 만 / 혼합)
- [x] `docs/backlog.md` 의 해당 항목 제거
- [x] 타입 체크 통과 (`pnpm tsc --noEmit`)
- [x] 테스트 통과 (`pnpm -C app test`)

## 우려사항 / 리스크

- mid-session 자동 선택이 사라지는 행동 변경이 있으나, 풀스크린 모달 컨텍스트에서 사용자가 패널 열린 채 다른 경로로 계좌를 추가하는 시나리오는 비현실적. 백로그 가이드 ("derive 또는 render-mount 시점 한 번만") 의 명시적 의도와 일치.
- `getInitialSelectedAccountId` 가 `findBrokerKeyByAccountBroker` 의존 — `lib/brokers.ts` ↔ `ImportTradesPanel/brokers.ts` 라벨 동기화 이슈는 별도 백로그 항목 (line 76) 으로 이미 추적 중이므로 본 작업 범위 외.

## 검증 방법

1. 타입 체크: `pnpm tsc --noEmit`
2. 단위 테스트: `pnpm -C app test src/components/records/__tests__/ImportTradesPanel.test.tsx`
3. 수동 QA (개발 서버):
   - 일괄 등록 가능한 계좌 1개만 등록 → 패널 열기 → 첫 단계에서 해당 계좌 자동 선택되어 다음 단계 버튼 활성 확인
   - 일괄 등록 계좌 2개 이상 → 패널 열기 → 어느 계좌도 선택 안 된 상태로 시작, 사용자 클릭으로 선택 확인
   - 미지원 증권사 계좌만 → 빈 상태 안내 표시 확인
   - 패널 닫고 재오픈 → 초기 상태로 fresh 시작 확인
