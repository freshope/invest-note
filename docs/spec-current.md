# Spec: 일괄 등록 첫 단계를 "내 계좌 선택"으로 변경

## 배경 / 문제

거래 일괄 등록(`ImportTradesPanel`)의 현재 흐름은 **증권사 선택 → 파일 업로드 → 미리보기(여기서 계좌 선택) → 결과**의 4단계다. 사용자는 ① 첫 화면에서 "삼성증권/토스증권" 중 증권사를 고르고, ② 파일을 올린 뒤, ③ 미리보기 단계에서 "어느 계좌에 넣을지"를 또 골라야 한다.

`account.broker`(예: "삼성증권")는 이미 계좌 등록 시 저장되어 있으므로, 사용자가 "내 계좌"를 먼저 고르면 증권사는 자동으로 결정된다. 첫 단계를 계좌 선택으로 바꾸면 (1) 입력 단계가 1개 줄고, (2) "어느 계좌에 등록되는지"가 시작 시점부터 명확해진다.

## 목표

- 일괄 등록 첫 단계가 "내 계좌 선택"으로 동작한다.
- 계좌를 선택하면 해당 계좌의 `broker`로부터 `BROKER_OPTIONS` 키(`samsung_xlsx`/`toss_pdf`)가 자동 도출되고, **별도 증권사 선택 단계는 사라진다**.
- 일괄 등록 미지원 증권사 또는 broker 미설정 계좌는 첫 단계에서 **비활성** + 사유 안내.
- 미리보기 단계에서는 더 이상 계좌 Select가 노출되지 않고, 이미 선택된 계좌 정보만 표시된다.
- 등록된 계좌가 0개일 때는 첫 단계에서 "먼저 계좌를 등록하세요" 안내가 보인다.

## 설계

### 접근 방식

- `Step` 타입: `"broker" | "file" | "preview" | "result"` → `"account" | "file" | "preview" | "result"`
- 첫 단계 컴포넌트 `BrokerStep` → 신규 `AccountStep`으로 교체.
  - 입력: `accounts: Account[]`, `selectedAccountId`, `onSelect`, `onNext`
  - 각 계좌 카드에 `BrokerLogo`(@/components/base/BrokerLogo) + 계좌명 + 증권사명 표시
  - `findBrokerKeyByAccountBroker(account.broker)`로 매칭되지 않으면 카드 비활성 + "이 증권사는 일괄 등록을 지원하지 않습니다" 캡션
- `index.tsx`의 broker 관련 상태(`selectedBrokerKey`, `detectedBrokerKey`)를 모두 제거하고 `selectedAccountId` 단일 상태로.
  - `effectiveBrokerKey` = 선택 계좌의 broker로부터 derive
  - `effectiveBroker` = `BROKER_OPTIONS.find(b => b.key === effectiveBrokerKey)`로 그대로 derive
- `handleFileSelect`에서 `account_hint` 기반 자동 매칭 로직 제거(이미 1단계에서 계좌 결정됨). preview 응답의 `broker_key`는 noop.
- `PreviewStep`: 계좌 Select 제거. 선택된 계좌 1줄 표시(이름·증권사). props에서 `onAccountChange`는 제거하고 `selectedAccountId`만 유지. hint 불일치 조건은 기존 자동 매칭(`accounts.find(a => a.name?.includes(hint))`)의 역과 동일: `preview.account_hint && selectedAccount && !selectedAccount.name?.includes(preview.account_hint)`이면 노란 경고 박스 노출(차단 X).
- `AccountStep` 진입 직후 "지원되는(매칭 가능한) 계좌"가 정확히 1개이면 자동 선택(전체 계좌 수 기준이 아닌 eligible 기준).
- 단계 타이틀 매핑: `"증권사 선택"` → `"계좌 선택"`.
- `brokers.ts`에 `findBrokerKeyByAccountBroker(broker: string | null): BrokerKey | null` 헬퍼 추가.
- `BrokerStep.tsx` 파일 삭제.

### 주요 변경 파일

- `app/src/components/records/ImportTradesPanel/index.tsx` — Step 타입, 상태, 단계 흐름, 타이틀 변경
- `app/src/components/records/ImportTradesPanel/AccountStep.tsx` — **신규**: 계좌 선택 UI
- `app/src/components/records/ImportTradesPanel/BrokerStep.tsx` — **삭제**
- `app/src/components/records/ImportTradesPanel/PreviewStep.tsx` — 계좌 Select 제거, 선택된 계좌 표시 + hint 불일치 경고
- `app/src/components/records/ImportTradesPanel/brokers.ts` — `findBrokerKeyByAccountBroker` 헬퍼 추가

### 백엔드 영향

없음. `/import/preview`는 broker_key를 query로 받고, `/import/commit`은 `account_id`만 받음. API 시그니처 변경 없음.

## 구현 체크리스트

- [x] `brokers.ts`에 `findBrokerKeyByAccountBroker(broker: string | null): BrokerKey | null` 헬퍼 추가 (label 매칭)
- [x] `AccountStep.tsx` 신규 작성: 계좌 카드 리스트, 미지원/미설정 계좌 비활성 + 안내, 계좌 0개 시 안내, eligible 계좌가 정확히 1개면 진입 시 자동 선택
- [x] `index.tsx`: Step 타입을 `"account" | "file" | "preview" | "result"`로 변경
- [x] `index.tsx`: broker 관련 상태(`selectedBrokerKey`/`detectedBrokerKey`) 제거, `effectiveBrokerKey`를 선택 계좌의 broker로부터 derive
- [x] `index.tsx`: `handleFileSelect`의 `account_hint` 자동 매칭 로직 제거, preview의 broker_key는 noop
- [x] `index.tsx`: 단계 타이틀 매핑 업데이트 ("계좌 선택"으로 변경)
- [x] `index.tsx`: 패널 닫을 때 리셋 로직에서 broker 상태 항목 제거, `useState<Step>` 초기값과 `setStep` 리셋 모두 `"account"`로 변경
- [x] `PreviewStep.tsx`: Select UI 제거하고 선택된 계좌 정보 1줄로 표시. props에서 `onAccountChange` 제거. hint 불일치 시 노란 경고 박스
- [x] `BrokerStep.tsx` 삭제 전 `grep -rn "BrokerStep" app/src`로 import 잔재 확인 → 파일 삭제 + `index.tsx`의 import 정리
- [x] 타입 체크 통과 (`pnpm -C app exec tsc --noEmit`)

## 검증 방법

1. `pnpm dev` 기동된 상태에서 http://localhost:3000 → 거래 → 일괄 등록 진입
2. 첫 화면 계좌 리스트 확인 — 삼성/토스: 활성, 그 외/미설정: 비활성 + 안내, 0개 상태: 안내 메시지
3. 삼성증권 계좌 선택 → 다음 → .xlsx 업로드 → 미리보기에 선택 계좌 표시, Select 없음 확인
4. 토스증권 계좌 선택 → .pdf 업로드 → 동일 검증
5. `account_hint`와 다른 계좌를 선택한 흐름 — 미리보기 경고 박스 노출
6. `pnpm -C app exec tsc --noEmit` 통과
7. 등록 완료 후 거래 목록에 신규 거래 반영(회귀 없음)

## 우려사항 / 리스크

- `account.broker`가 `BROKER_OPTIONS.label`과 정확히 일치해야 매칭됨. 현재 `AccountFormPanel`은 `BROKERS` 그리드 선택만 허용하므로 안전. 매칭 실패 시 비활성으로 자연스럽게 흡수.
- 파일에서 추출한 `account_hint`와 사용자가 선택한 계좌가 다를 수 있음 → 차단하지 않고 경고만.
- 미리보기 응답의 `broker_key`가 첫 단계에서 도출된 키와 다를 가능성(파싱 오감지) → 무시. 차단은 향후 별도 결정.
