# Spec: FE simplify Round 4 — useEffect 안티패턴 정리

> 완료: 2026-05-03

## 배경 / 문제

`docs/backlog.md` "FE simplify (Round 1 이후 deferred) → useEffect 안티패턴" 카테고리의 5개 항목을 한 번에 처리한다. 모두 "외부 입력에 반응해 폼/패널 state를 effect 안에서 set" 한다는 공통 안티패턴이며, React 공식 권장 패턴(이벤트 핸들러 직접 처리, 부모 key 교체, derived state)으로 치환한다.

직전 Round 3 (`docs/spec-history/2026-05-03-fe-simplify-round3-state-structure.md`) 가 컴포넌트 분리/스타일 정리였다면, Round 4 는 **렌더 → effect → setState 사이클이 만드는 흐릿한 데이터 흐름**을 끊는다. effect 가 줄면 (1) 사용자 의도(수동 입력)가 자동 동기화에 덮이는 회귀를 막고, (2) 패널 reset 의 "왜 지금 이 setState 가 도는가" 추적 비용이 사라지고, (3) `eslint-disable` / `openRef` 같은 보조 장치의 존재 이유가 명확해진다.

> **Round 1 회귀 사례 (2026-04-30)**: 한 번 단순화했다가 복원된 적 있음. 본 Round 는 항목별 부수 영향을 spec 본문에 명시하고, 수동 QA 에서 회귀 트리거 케이스(특히 rapid reopen)를 강제 체크한다.

## 목표

- `TradeBasicForm` 의 두 useEffect (commission/tax 자동계산, localStorage 계좌 복원)가 모두 사라지고, `eslint-disable-next-line react-hooks/exhaustive-deps` 가 제거된다. 사용자 수동 수정이 자동 계산에 덮이지 않는다.
- `TradeFormPanel`, `ImportTradesPanel` 의 reset useEffect 가 사라지고, 부모(`TradeList`) 가 단조증가 key 로 인스턴스 마운트 사이클을 통제한다.
- `useEnsureValidAccount` 가 `useEffectiveAccountId` derive 헬퍼로 대체되어 setState-in-effect 가 사라지고, 세 컨슈머(`TradeList` / `DetailPanelProvider::StockPanelContent` / `StockDetail`) 가 모두 derived 값을 사용한다.
- 타입 체크와 기존 테스트가 통과한다. `TradeBasicForm.test.tsx` 시나리오는 회귀 없이 그대로 통과한다.

## 설계

### 항목 1 — `TradeBasicForm` commission/tax effect 제거 + dirty 가드

#### 접근

이벤트 핸들러(가격/수량 Controller `onChange`, trade_type Tabs `onValueChange`) 에서 `recalcFees` 헬퍼를 호출한다. 사용자가 수수료/제세금 input 을 직접 수정한 경우 자동 계산을 끄기 위해 `getFieldState("commission" | "tax").isDirty` 스냅샷을 가드로 둔다.

> **왜 `getFieldState` 인가** (`formState.dirtyFields` 가 아닌): `dirtyFields` 는 구독 기반이라 컴포넌트 리렌더에 영향을 주지만, 본 케이스는 한 시점의 dirty 여부 조회만 필요하다. `getFieldState` 는 RHF 권장 비구독 스냅샷 API. `setValue` 를 옵션 없이 호출하면 dirty 마킹되지 않으므로 자동 계산값은 영원히 dirty=false 로 남고, 사용자가 Controller 의 `field.onChange` 를 거쳐 입력한 순간만 dirty=true 로 잠긴다 — 이것이 "수동 입력 보호"의 정확한 의미다.

#### 변경 (전/후)

before — `TradeBasicForm.tsx:157-167`:
```ts
useEffect(() => {
  const total = (price || 0) * (quantity || 0);
  if (total > 0) {
    setValue("commission", calcCommission(total));
    setValue("tax", tradeType === "SELL" ? calcTax(total) : 0);
  } else {
    setValue("commission", 0);
    setValue("tax", 0);
  }
}, [price, quantity, tradeType, setValue]);
```

after:
```ts
const { control, getValues, getFieldState, setValue, ... } = useForm<FormValues>({...});

const recalcFees = useCallback((nextPrice: number, nextQty: number, nextType: TradeType) => {
  const total = (nextPrice || 0) * (nextQty || 0);
  if (!getFieldState("commission").isDirty) {
    setValue("commission", total > 0 ? calcCommission(total) : 0);
  }
  if (nextType === "SELL") {
    if (!getFieldState("tax").isDirty) {
      setValue("tax", total > 0 ? calcTax(total) : 0);
    }
  } else {
    setValue("tax", 0);
  }
}, [getFieldState, setValue]);

// 가격 Controller onChange:
//   const next = parseNumberInput(e.target.value);
//   field.onChange(next);
//   recalcFees(next, getValues("quantity"), getValues("trade_type"));
//
// 수량 Controller 도 동일.
// trade_type Tabs onValueChange 에서 recalcFees(getValues("price"), getValues("quantity"), v).
```

#### tax 의 trade_type 전환 처리

BUY 로 전환 시 tax 입력 필드 자체가 unmount 된다(`tradeType === "SELL" &&` 조건부). 사용자가 SELL 에서 수동 수정한 tax 를 BUY 로 가도 보존하면, 다음 SELL 전환 시 stale 한 값이 보일 수 있고 의미상 혼란을 준다. 따라서 trade_type 변경 시 tax 는 dirty 무시하고 0 으로 강제 리셋. commission 은 BUY/SELL 모두 표시되므로 dirty 가드 유지.

#### 부수 영향

- effect 사이클 1 단계 단축. watch 호출 자체는 다른 곳에서도 쓰므로 그대로.
- 자동 계산값이 dirty 마킹되지 않아 향후 dirty 검사 로직이 들어와도 수동/자동 구분이 자연.

---

### 항목 2 — `TradeBasicForm` localStorage 복원 effect → 동기 defaultValues

#### 접근

react-hook-form 7.72 의 `AsyncDefaultValues` 시그니처는 Promise 전용이므로, 동기 함수형 `defaultValues` 는 작동하지 않는다. 대신 컴포넌트 본문에서 `localStorage` 를 동기 read 해 객체 형태 `defaultValues` 를 만든다. `useForm` 은 첫 렌더 스냅샷만 사용하므로 매 렌더 객체 재생성이 무해하다 — `useState` lazy / `useMemo` 모두 불필요.

#### SSR 안전성

`TradeBasicForm` 은 `FullScreenPanel` 의 `createPortal(..., document.body)` 안에 렌더되며, FullScreenPanel 은 `mounted=false` 동안 `null` 반환. 즉 서버에서는 렌더되지 않음. 그래도 `typeof window === "undefined"` 가드는 방어적으로 유지(테스트 setup 변경, future SSR 경로 추가 대비).

#### 변경 (전/후)

before — `TradeBasicForm.tsx:80-92, 123-130`:
```ts
useForm({ defaultValues: { ..., account_id: "", ... } });

useEffect(() => {
  const stored = window.localStorage.getItem(STORAGE_KEYS.LAST_ACCOUNT_ID);
  if (stored && accounts.some((a) => a.id === stored)) {
    setValue("account_id", stored);
  }
// eslint-disable-next-line react-hooks/exhaustive-deps
}, []);
```

after:
```ts
function getInitialAccountId(accounts: Account[]): string {
  if (typeof window === "undefined") return "";
  const stored = window.localStorage.getItem(STORAGE_KEYS.LAST_ACCOUNT_ID);
  return stored && accounts.some((a) => a.id === stored) ? stored : "";
}

useForm({
  resolver: zodResolver(schema),
  defaultValues: {
    trade_type: "BUY",
    account_id: getInitialAccountId(accounts),
    asset_name: "",
    // ... 동일
  },
});
// useEffect 와 eslint-disable 모두 삭제.
```

#### 부수 영향

- 마운트 직후 setValue → 폼 재렌더 1 사이클 절약. UI 는 "처음부터 pre-select" 로 자연.
- `TradeBasicForm.test.tsx` 의 `afterEach: localStorage.clear()` 는 그대로 유효(테스트 시작 시 "" 반환).
- (선택) 회귀 방어 테스트 추가 권장: "localStorage 에 유효한 ID 가 있으면 폼 마운트 시 해당 계좌 pre-select".

---

### 항목 3 — `TradeFormPanel` 이중 reset effect → 부모 단조증가 key bump

#### 접근 (백로그 제안 교정)

백로그가 제시한 `key={open ? "open" : "closed"}` 또는 `{open && <Panel/>}` 는 `FullScreenPanel` 의 2단계 lifecycle (`mounted` → `visible` → transitionEnd → `mounted=false`) 을 죽인다. open=false 가 된 순간 부모가 자식을 즉시 unmount 시키면 슬라이드 아웃 애니메이션이 끊겨 jump cut 발생. 본 spec 은 백로그 의도를 살리되 패턴을 **부모 단조증가 key bump** 로 교정한다.

핵심: 닫는 동안 같은 instance 가 유지되어 자기 lifecycle 로 슬라이드 아웃하고, **다음 오픈 시점**에만 부모가 key 를 ++ 하여 새 instance 를 마운트한다.

#### 변경 (전/후)

before — `TradeFormPanel.tsx:34-41`:
```ts
useEffect(() => {
  if (open) {
    // eslint-disable-next-line react-hooks/set-state-in-effect
    setStep("basic");
    setTradeId("");
    setTradeType("BUY");
  }
}, [open]);
```

after — **위 useEffect 통째로 삭제**. step/tradeId/tradeType 의 useState 초기값(`"basic"` / `""` / `"BUY"`)이 새 instance 마다 fresh 적용. `openRef` 동기화 effect (라인 48-49) 는 **유지** — stale-promise 방어로 마운트 패턴과 별개 문제(닫는 동안 마운트는 살아 있고 응답이 도착하는 케이스).

before — `TradeList.tsx:23, 96-98, 106-110`:
```ts
const [formOpen, setFormOpen] = useState(false);
<button onClick={() => setFormOpen(true)}>...</button>
<TradeFormPanel open={formOpen} onOpenChange={setFormOpen} accounts={accounts} />
```

after:
```ts
const [formOpen, setFormOpen] = useState(false);
const [formKey, setFormKey] = useState(0);
const openForm = useCallback(() => {
  setFormKey((k) => k + 1);
  setFormOpen(true);
}, []);

<button onClick={openForm}>...</button>
<TradeFormPanel
  key={formKey}
  open={formOpen}
  onOpenChange={setFormOpen}
  accounts={accounts}
/>
```

#### 왜 작동하는가

- 닫을 때: 부모는 key 유지 + `formOpen=false` 만 전달. 자식 `TradeFormPanel` 인스턴스는 살아 있고 내부 `FullScreenPanel` 이 `mounted=true` + `visible=false` 상태로 슬라이드 아웃. transitionEnd 에서 자기 자신이 `mounted=false` 로 unmount.
- 다시 열 때: 부모가 `formKey` ++ → 이전 `TradeFormPanel` 인스턴스 unmount(이미 mounted=false 라 null 렌더링이라 시각적 영향 없음) → 새 인스턴스 fresh state 마운트 → 새 FullScreenPanel 슬라이드 인.

#### 부수 영향

- `openRef` 동기화 effect: 그대로 유지(별개 문제).
- 메타 단계까지 진행 후 닫고 다시 열면 항상 "basic" 단계로 돌아가는 현재 의도가 useState 초기값으로 자연 보장.

---

### 항목 4 — `ImportTradesPanel` setTimeout reset → 부모 key bump

#### 접근

항목 3 과 동일 패턴. 300ms setTimeout 의도("닫힘 애니메이션 동안 step 깜박임 방지")는 부모 key bump 로 자연 보존됨 — 닫는 동안 *기존 인스턴스* 는 자기 state(예: `step="result"`)를 유지한 채 슬라이드 아웃하고, 다음 오픈 시 *새 인스턴스* 가 fresh 상태(`"account"`)로 시작.

#### 변경 (전/후)

before — `ImportTradesPanel/index.tsx:42-52`:
```ts
useEffect(() => {
  if (!open) {
    const timer = setTimeout(() => {
      setStep("account");
      setSelectedAccountId("");
      setPreview(null);
      setResult(null);
    }, 300);
    return () => clearTimeout(timer);
  }
}, [open]);
```

after — **useEffect 통째로 삭제**. step / selectedAccountId / preview / result / isLoading 모두 useState 초기값으로 새 인스턴스마다 fresh 시작.

before — `TradeList.tsx:24, 42, 113-117`:
```ts
const [importOpen, setImportOpen] = useState(false);
<CsvUploadButton onClick={() => setImportOpen(true)} />
<ImportTradesPanel open={importOpen} onOpenChange={setImportOpen} accounts={accounts} />
```

after:
```ts
const [importOpen, setImportOpen] = useState(false);
const [importKey, setImportKey] = useState(0);
const openImport = useCallback(() => {
  setImportKey((k) => k + 1);
  setImportOpen(true);
}, []);
<CsvUploadButton onClick={openImport} />
<ImportTradesPanel
  key={importKey}
  open={importOpen}
  onOpenChange={setImportOpen}
  accounts={accounts}
/>
```

#### 부수 영향

- 300ms 매직넘버 사라짐(애니메이션 duration 변경 시 수정 부채 한 곳 줄어듦).
- `ImportTradesPanel/AccountStep.tsx` 의 자동 단일 계좌 선택 effect 는 본 round 범위 외(다음 simplify round 에서 별도 평가).

---

### 항목 5 — `useEnsureValidAccount` setState-in-effect → `useEffectiveAccountId` derive

#### 접근

setState-in-render 패턴(공식 store rule)은 다른 컴포넌트(Provider) 의 state 를 건드리는 지점이라 회색지대. derive 헬퍼 `useEffectiveAccountId` 가 더 단순하고 정확하다 — 컨슈머가 항상 "정상화된" 값을 사용하면 글로벌 state 가 stale 한 채로 잠시 남아도 어떤 컨슈머에게도 stale 이 노출되지 않는다.

```ts
// AccountFilterProvider.tsx
export function useEffectiveAccountId(accounts: Account[]): string {
  const { selectedAccountId } = useAccountFilter();
  if (selectedAccountId === ACCOUNT_FILTER_ALL) return ACCOUNT_FILTER_ALL;
  return accounts.some((a) => a.id === selectedAccountId)
    ? selectedAccountId
    : ACCOUNT_FILTER_ALL;
}
// 기존 useEnsureValidAccount export 삭제.
```

#### 컨슈머 변경 범위 (3곳)

| 파일 | 변경 |
|---|---|
| `TradeList.tsx` | `useEnsureValidAccount` import 제거. `useAccountFilter` 의 `selectedAccountId` 대신 `useEffectiveAccountId(accounts)` 사용. `setSelectedAccountId` 는 그대로. filter logic + `<AccountFilter value=...>` 모두 effective 값. |
| `DetailPanelProvider.tsx::StockPanelContent` | `useEnsureValidAccount` import 제거. `useAccountFilter().selectedAccountId` → `useEffectiveAccountId(accounts)` 교체. filter logic 에서 effective 값 사용. |
| `StockDetail.tsx` | `useAccountFilter` 에서 `selectedAccountId, setSelectedAccountId` 받되, 추가로 `useEffectiveAccountId(accounts)` 호출. `isFiltered` 비교 + `<AccountFilter value=...>` 에 effective 사용. setter 는 그대로. |

#### 왜 setter 는 그대로 유지하는가

`<AccountFilter value={effectiveAccountId} onChange={setSelectedAccountId} />` 패턴이 자연스럽다. stale 한 raw 가 컨텍스트에 남아 있어도 UI 는 effective(="all")을 표시. 사용자가 다른 계좌를 선택하면 setter 가 raw 를 덮어써 글로벌 state 정상화. derive 가 자동 정상화를 안 하더라도 *사용자가 한 번이라도 필터를 건드리는 순간* 자연 해소되며, UI 는 처음부터 정상 표시.

#### 부수 영향 / 위험

- **글로벌 raw `selectedAccountId` 가 stale 인 채로 남을 수 있음**: 어떤 컨슈머도 raw 를 직접 신뢰하지 않으므로(모두 `useEffectiveAccountId` 경유) 영향 없음. 단, **향후 새 consumer 가 raw 를 직접 read 하면 stale 을 볼 수 있다**. 본 spec 우려사항에 명시하고, 컨벤션으로 "filter 비교/표시는 항상 `useEffectiveAccountId`" 를 명시.
- effect 1 개가 사라져 마운트 직후 invalid → ALL 전환 시 발생하던 추가 렌더 1 회 절약.

### 주요 변경 파일

- `app/src/components/records/TradeBasicForm.tsx` — 두 useEffect 삭제, `recalcFees` 추가 + 가격/수량/trade_type 핸들러에서 호출, `getInitialAccountId` 추가 후 defaultValues 에 사용. `getFieldState` 를 useForm destructure 에 추가.
- `app/src/components/records/TradeFormPanel.tsx` — reset useEffect 삭제 (`openRef` 동기화 effect 는 유지).
- `app/src/components/records/ImportTradesPanel/index.tsx` — setTimeout reset useEffect 삭제.
- `app/src/components/records/TradeList.tsx` — `formKey` / `importKey` state + `openForm` / `openImport` 콜백 추가, 각 패널에 `key={...}` 부여. `useEnsureValidAccount` import 제거, `useEffectiveAccountId` 로 교체.
- `app/src/components/providers/AccountFilterProvider.tsx` — `useEnsureValidAccount` 삭제, `useEffectiveAccountId` 신설.
- `app/src/components/panels/DetailPanelProvider.tsx` — `useEnsureValidAccount` import 제거, `StockPanelContent` 에서 `useEffectiveAccountId` 사용.
- `app/src/components/stocks/StockDetail.tsx` — `useEffectiveAccountId` import 추가, `isFiltered` / `<AccountFilter value>` 에 적용.
- `app/src/components/records/__tests__/TradeBasicForm.test.tsx` — (선택) localStorage pre-select 회귀 방어 테스트 1 건 추가.

### 재사용 / 참고

- `STORAGE_KEYS.LAST_ACCOUNT_ID` (`app/src/lib/constants/storage.ts`) — `getInitialAccountId` 에서 그대로 사용.
- `calcCommission` / `calcTax` (`TradeBasicForm.tsx` 내부) — `recalcFees` 에서 그대로 사용.
- `FullScreenPanel` (`app/src/components/base/FullScreenPanel.tsx`) — 2 단계 lifecycle 구조가 부모 key bump 패턴이 동작하는 근거.
- 직전 Round 3 spec (`docs/spec-history/2026-05-03-fe-simplify-round3-state-structure.md`) — 톤/구조 참고.

## 구현 체크리스트 (항목별 작은 커밋)

- [x] **(커밋 1) 항목 1 — commission/tax 자동계산을 이벤트 핸들러 + dirty 가드로 이전**
  - [x] `TradeBasicForm.tsx` commission/tax effect 삭제, `recalcFees` 헬퍼 추가
  - [x] 가격/수량/trade_type 핸들러에서 `recalcFees` 호출
  - [x] `useForm` destructure 에 `getFieldState` 추가
  - [x] 수동 QA: 자동 계산, 수동 수정 보호, BUY↔SELL 전환 시 tax 처리
- [x] **(커밋 2) 항목 2 — localStorage 복원 effect 제거**
  - [x] `getInitialAccountId(accounts)` 헬퍼 추가, `defaultValues.account_id` 에 사용
  - [x] mount useEffect + `eslint-disable-next-line react-hooks/exhaustive-deps` 삭제
  - [x] (선택) 테스트 추가: localStorage 에 유효 ID 있을 때 pre-select
  - [x] 수동 QA: localStorage 빈 상태 / 유효 / 무효 ID 케이스
- [x] **(커밋 3) 항목 3 — TradeFormPanel reset effect 제거 + 부모 key bump**
  - [x] `TradeFormPanel.tsx` reset useEffect 삭제 (`openRef` 동기화는 유지)
  - [x] `TradeList.tsx` 에 `formKey` state + `openForm` 콜백 추가, `<TradeFormPanel key={formKey} />` 적용
  - [x] 수동 QA: 닫기 후 재오픈 시 step 초기화, rapid reopen 시 jump cut 인지 가능 여부
- [x] **(커밋 4) 항목 4 — ImportTradesPanel setTimeout 제거 + 부모 key bump**
  - [x] `ImportTradesPanel/index.tsx` setTimeout useEffect 삭제
  - [x] `TradeList.tsx` 에 `importKey` state + `openImport` 콜백 추가, `<ImportTradesPanel key={importKey} />` 적용
  - [x] 수동 QA: 결과 단계 도달 후 닫기/재오픈 시 첫 단계로 초기화, rapid reopen
- [x] **(커밋 5) 항목 5 — useEnsureValidAccount → useEffectiveAccountId**
  - [x] `AccountFilterProvider.tsx` 에 `useEffectiveAccountId` 추가, `useEnsureValidAccount` 삭제
  - [x] `TradeList.tsx`, `DetailPanelProvider.tsx::StockPanelContent`, `StockDetail.tsx` 컨슈머 교체
  - [x] 수동 QA: 계좌 삭제 후 records / stock 패널에서 "전체" 폴백
- [x] **(공통)** `pnpm -C app exec tsc --noEmit` 통과
- [x] **(공통)** `pnpm -C app test` 통과
- [x] **(공통)** `docs/backlog.md` 의 useEffect 안티패턴 5 개 항목 체크 / 제거 + Round 4 spec 링크 추가

## 우려사항 / 리스크

- **rapid reopen jump cut (항목 3·4)**: 닫는 도중 즉시 재오픈하는 패턴에서 새 인스턴스 마운트로 인한 "jump cut" 가능성. Round 1 회귀 사례(2026-04-30) 가 있으므로 수동 QA 에서 명시적으로 확인. 인지 가능 수준이면 fallback 으로 `key` bump 시점을 transitionEnd 이후로 미루는 변형 적용 — 다만 그러면 "이전 패널이 다 사라질 때까지 새 패널을 못 여는" UX 가 되어 trade-off. 첫 시도는 단순 `openForm-bump` 로 진행.
- **dirty 영구 잠김 (항목 1)**: 사용자가 한 번이라도 수수료/제세금을 수동 수정하면 가격 변경에도 자동 계산이 영구 비활성. "리셋" 출구는 폼 자체의 reset 뿐. 백로그 가이드 "사용자 수동 수정 보호 플래그 검토" 를 따른 결과로 의도된 동작이지만, UX 우려 시 추가 reset 트리거(예: stock 변경 시 dirty 해제)를 후속 작업으로.
- **stale raw selectedAccountId (항목 5)**: 글로벌 컨텍스트의 raw 값이 stale 한 채로 남을 수 있음. 모든 현재 컨슈머가 effective 경유라 무영향. 향후 신규 컨슈머가 raw 를 직접 read 하면 stale 노출 가능 — 컨벤션으로 "filter 비교/표시는 `useEffectiveAccountId`" 명시.
- **백로그 제안의 부정확성 (항목 3·4)**: `key={open ? "open" : "closed"}` 또는 `{open && <Panel/>}` 그대로는 `FullScreenPanel` lifecycle 을 죽임. 본 spec 의 "단조증가 key bump" 는 백로그 의도를 살리되 패턴을 교정한 것. 다음 round 에서 같은 토론을 반복하지 않도록 본 spec 본문에 결정 근거 명시.
- **`AccountStep.tsx` 의 자동 단일 계좌 선택 effect**: 본 round 범위 외. 다음 simplify round 에서 별도 평가.
- **Round 1 회귀 (2026-04-30)** 사례 인용: 한 번 단순화했다가 복원된 적 있음. 본 round 의 모든 항목은 부수 영향을 명세화했지만, 수동 QA 누락 시 동일 회귀 가능성. 체크리스트 강제.

## 검증 방법

1. `pnpm -C app exec tsc --noEmit` — 타입 체크.
2. `pnpm -C app test` — 기존 테스트 통과 (`TradeBasicForm.test.tsx` 회귀 없음, 신규 1 건 추가 시 통과).
3. 로컬 개발 서버 (`pnpm -C app dev`) 에서 항목별 수동 QA:
   - **항목 1**: 가격/수량 입력 → 수수료 자동 계산 확인. 수수료 수동 999 입력 → 가격 변경 시 999 유지. SELL 전환 → tax 자동 계산 / dirty 보호 동일 확인. BUY 로 전환 시 tax input unmount + 내부 0 강제 리셋.
   - **항목 2**: localStorage 빈 상태 → 패널 오픈 → 계좌 미선택. 계좌 A 로 거래 저장 후 재오픈 → A pre-select. DevTools 로 stored ID 를 존재하지 않는 UUID 로 교체 → 재오픈 시 미선택 (가드 동작). 시크릿 모드 첫 진입에서 hydration warning 무발생.
   - **항목 3**: 거래 등록 패널을 메타 단계까지 진행 → 닫기 → 재오픈 시 "basic" 단계 초기화. **rapid reopen**: 슬라이드 아웃 도중 즉시 FAB 누름 → jump cut 인지 가능 여부.
   - **항목 4**: 일괄 등록 패널을 결과 단계까지 진행 → 닫기 → 재오픈 시 "account" 단계로 초기화. rapid reopen.
   - **항목 5**: 계좌 A 선택 → 설정에서 A 삭제 → records 탭 진입 시 AccountFilter 가 "전체" 로 표시 + 거래 모두 노출. StockDetail 패널 / Stock panel 에서도 동일 폴백 확인.
