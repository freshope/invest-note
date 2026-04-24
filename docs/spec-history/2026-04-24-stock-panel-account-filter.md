> 완료: 2026-04-24

# Spec: 종목 패널 계좌 필터 추가 (거래 탭과 상태 공유)

## 배경 / 문제

현재 계좌 필터는 거래 탭(`TradeList`) 안에서만 동작하고, 상태가 컴포넌트 로컬 `useState`에 갇혀 있어 페이지/패널 전환 시 초기화됩니다. 종목 패널(`StockPanel` / `StockDetail`)에는 계좌 필터 UI 자체가 없어, 멀티 계좌 사용자가 특정 계좌의 거래만 보고 싶어도 종목 단위로는 걸러볼 수 없습니다. 거래 탭과 종목 패널이 계좌 필터 선택값을 공유하면 일관된 뷰 경험을 줄 수 있습니다.

## 목표

- 종목 패널 헤더 하단에 계좌 필터가 보이고 선택 시 거래 리스트 / 성과 요약(총 거래·승률·총 손익)이 해당 계좌 기준으로 계산된다.
- 거래 탭과 종목 패널의 계좌 필터가 **동일한 선택값을 공유**한다 (한쪽에서 A 계좌 선택 시 다른 쪽도 A 계좌로 표시).
- 공용 `AccountFilter` 컴포넌트가 `src/components/shared/`에 존재하며 거래 탭·종목 패널 양쪽에서 임포트해 사용한다.
- `accounts.length >= 2` 조건일 때만 필터 UI 노출(기존 거래 탭 동작 유지).
- 선택된 계좌가 삭제되면 양쪽 모두 자동으로 "전체"로 복귀한다.

## 설계

### 접근 방식

1. **Context 기반 공유 상태** — `AccountFilterProvider`를 신설해 `selectedAccountId` 한 값만 전역으로 보관. 기본값 `"all"`. `app/src/components/providers/AccountFilterProvider.tsx`에 배치하고 `useAccountFilter()` 훅을 함께 export.
2. **Mount 순서** — `app/(app)/layout.tsx`에서 `<AccountFilterProvider>`를 `<DetailPanelProvider>`의 **바깥**에 래핑.
3. **공용 UI 컴포넌트 이동** — 기존 `records/AccountFilter.tsx`를 `src/components/shared/AccountFilter.tsx`로 이동. API는 controlled (`{ accounts, value, onChange }`) 유지.
4. **"삭제된 계좌 → all 복귀" 로직 공유** — Provider 파일에 `useEnsureValidAccount(accounts)` 훅을 같이 제공. 각 사용처(TradeList, StockPanel)가 자기가 아는 `accounts`를 넘겨 호출.
5. **종목 패널 필터 적용 지점** — `DetailPanelProvider.tsx`의 `StockPanel` 내부 `filteredTrades` useMemo에 `(selectedAccountId === "all" || t.account_id === selectedAccountId)` 조건 추가.
6. **StockDetail 확장** — `accounts` prop을 새로 받아 sticky 헤더 하단에 `AccountFilter` 삽입. `accounts`는 StockPanel이 payload에서 그대로 pass-through.

### 주요 변경 파일

- `app/src/components/providers/AccountFilterProvider.tsx` — 신설. Context + `AccountFilterProvider` + `useAccountFilter` + `useEnsureValidAccount`.
- `app/src/components/shared/AccountFilter.tsx` — 신설(이동). 기존 `records/AccountFilter.tsx` 내용 그대로.
- `app/src/app/(app)/layout.tsx` — `DetailPanelProvider` 바깥에 `AccountFilterProvider` 래핑.
- `app/src/components/records/TradeList.tsx` — 로컬 `useState`/방어 `useEffect` 제거, `useAccountFilter` + `useEnsureValidAccount` 사용, import 경로 변경.
- `app/src/components/panels/DetailPanelProvider.tsx` — StockPanel에서 context 읽기, `filteredTrades`에 accountId 조건 추가, `<StockDetail>`에 `accounts` pass-through, `useEnsureValidAccount(accounts)` 호출.
- `app/src/components/stocks/StockDetail.tsx` — `accounts` prop 추가, 헤더 sticky 블록 하단에 `AccountFilter` 렌더.
- `app/src/components/records/AccountFilter.tsx` — 삭제(이동 완료 후).

## 구현 체크리스트

- [x] `docs/spec-current.md` 사양서 저장
- [x] `app/src/components/providers/AccountFilterProvider.tsx` 신설 — `AccountFilterProvider`, `useAccountFilter`, `useEnsureValidAccount` export
- [x] `app/src/components/shared/AccountFilter.tsx` 신설 — 기존 `records/AccountFilter.tsx` 내용 이동
- [x] `app/src/app/(app)/layout.tsx` — `AccountFilterProvider`를 `DetailPanelProvider` 바깥에 래핑
- [x] `app/src/components/records/TradeList.tsx` — 로컬 상태 제거, context hook 전환, import 경로 갱신
- [x] `app/src/components/stocks/StockDetail.tsx` — `accounts` prop 추가, 헤더 하단 AccountFilter 렌더
- [x] `app/src/components/panels/DetailPanelProvider.tsx` — StockPanel에서 context 읽기, `filteredTrades` 조건 3요소화, `StockDetail`로 `accounts` pass-through
- [x] `app/src/components/records/AccountFilter.tsx` 삭제
- [x] 타입 체크 통과 (`cd app && pnpm tsc --noEmit`)

## 우려사항 / 리스크

- 홈 → 종목 패널 진입 시 이전 계좌 필터 유지 — "같은 선택값 공유" 요구사항과 일치하므로 의도된 동작.
- `accounts.length < 2`일 때 필터 UI는 숨김이지만 context 값은 유지 — 일관성 측면에서 의도적. `useEnsureValidAccount`가 삭제된 계좌의 경우 "all"로 복귀시켜 안전성 확보.
- TradePanel 영향 없음 — 단일 거래만 표시하고 자체 필터 UI가 없음.
