# 신규 가입자 활성화 개선 — 계좌등록/거래등록 허들 통합 사양서

> **완료: 2026-07-01**

> **개정 이력**: 초안(결론 A=account_number 미추가) → **개정(사용자 결정으로 결론 A 뒤집음: account_number 추가 + 내역서→계좌 번호 매칭 구현)**. 아래는 개정판.

## 배경 / 목적

PostHog 퍼널 분석: 앱열람 280 → 로그인 238(85%) → 계좌등록 170(로그인의 71%) → 거래등록 102(계좌의 60%).
진짜 병목은 로그인이 아니라 **②계좌등록(29% 이탈)·③거래등록(40% 이탈)** 두 허들이며 각 68명이 증발한다.

원인(코드 확인됨):
- 홈 빈 상태(`EmptyState` no-accounts)가 계좌 없을 때 `/settings`로 보내 "계좌추가 먼저"를 강요 → 탭을 넘나드는 2단 여정.
- 거래폼 계좌 Select(`TradeBasicForm`)가 계좌 0개면 빈 드롭다운 = 막다른 길.
- 등록 진입점이 헤더 CSV 버튼(발견성 낮음, 사용 5명) + FAB(+) 로 이원화.

목표: 계좌등록과 거래등록을 하나의 흐름으로 통합해 신규 사용자의 첫 활성화(trade_recorded OR account_added OR trades_imported)까지의 마찰을 제거한다.

> 활성화 판정은 `account_added` 단독이 아니라 위 3개 이벤트의 합집합으로 본다(`account_added`는 import 경로 등을 과소계수).

## 두 ★검토 항목 결론

### 결론 A (개정) — accounts 스키마에 `account_number` 필드: **추가한다 (Alembic 마이그레이션)**

사용자 결정으로 초안의 defer 를 뒤집음. 내역서의 계좌번호로 사용자 계좌를 매칭해, 계좌가 여러 개여도 올바른 계좌를 안전하게 자동선택한다.

- **accounts.account_number (nullable text) 컬럼 추가** — Alembic 마이그레이션. 현재 head `0012_board_reads` 뒤에 신규 리비전.
  - ★**마이그레이션 적용은 사용자/리더 확인 후** 실행한다. be-engineer 는 리비전 파일 작성까지 가능, `alembic upgrade` 실행 금지(스펙 플래그).
  - 컬럼 추가만 — 인덱스/유니크 제약 없음(같은 번호를 재사용/재발급하는 엣지, 사용자별 스코프라 유니크 강제 부적절).
- **매칭은 FE-side**: accounts 목록이 이미 trades 쿼리에 번들되어 FE 가 보유. 별도 매칭 엔드포인트 만들지 않음(speculative).
- **BE 는 passthrough 만**: (a) Account 응답에 `account_number` 노출, (b) `AccountCreate`/`AccountUpdate` 가 `account_number` optional 수용·저장. 검증은 길이 제한(예: 64자) 수준.

#### ★account_hint 실측 결과 (매칭 규칙의 근거 — 파서 정규식 + 실 샘플 픽스처 확인 완료)

파서 4종 모두 **마스킹 없는 전체 계좌번호**를 추출한다(`tests/test_broker_parsers.py` 실 샘플 픽스처 검증값):

| broker | 정규식 (`broker_import/*.py`) | 실 추출값 예시 |
|--------|------------------------------|----------------|
| samsung_xlsx | `(\d{7,}-\d{2,})` | `7157197877-14` |
| toss_pdf | `계좌\s*번호\s+([\d\-]+)` | `101-01-024891` |
| shinhan_pdf | `계좌번호\s*:\s*([\d\-]+)` | `270-26-192214` |
| mirae_pdf | `계좌번호\s+(\d{3}-\d{9})` | `584-566838640` |

- 모든 정규식이 `\d`/`[\d\-]` 만 캡처 → 마스킹(`*`) 문자를 포함하지 않는다. 실측값 4개 전부 전체번호(비마스킹). **정규화 후 전체 문자열 동일성 매칭이 4개 broker 전부 가능**.
- **정규화 규칙 확정**: `normalizeAccountNumber(s) = 숫자만 남김(하이픈·공백·기타 제거)`. 저장은 파싱 원문(raw) 유지, **비교 시점에 양쪽을 정규화해 동일성 판정**(대소문자·구분자 차이 흡수). samsung 의 접미 `-14`(상품구분 추정)도 저장·파싱이 동일 규칙이라 일관.
- **정규화 위치**: **FE-side**(비교 시점). 매칭이 FE 이고 BE 는 순수 passthrough → 표시값 충실 + 결합도 최소. 공용 헬퍼로 FE 에 둔다.
- **마스킹/추출실패 fallback**: 현행 4개 파서는 비마스킹이라 fallback 불필요. 단 향후 마스킹 내역서·추출 실패로 `account_hint`가 null/부분값이면 → 자동매칭 skip → 기존 수동 계좌 선택 흐름으로 폴백(스펙에 방어 명시).

### 결론 B — `settings/AccountFormPanel.tsx` 재사용: **재사용한다 (onCreated 콜백 + account_number 필드 추가)**

- `AccountFormPanel`은 `FullScreenPanel` 기반 독립 패널이고 `accountsApi.create`(반환 `Account`, id 포함)로 생성 + 무효화 + 닫기까지 수행. 중첩 패널은 `ImportTradesPanel → BrokerStatementPanel` 선례 있어 안전.
- 재사용을 위해 두 가지 증분:
  1. 선택적 `onCreated?: (account: Account) => void` prop 추가 — `onSubmit` 생성 분기에서 `const created = await accountsApi.create(input); onCreated?.(created)`.
  2. **`account_number` 입력 필드(optional)** 추가 — 수동 계좌도 향후 매칭 가능하게. import 신규계좌 확인 스텝에서 파싱된 값 prefill.
- **★핵심 함정(Select 렌더 타이밍)**: 거래폼 계좌 Select 는 `accounts` prop(trades 쿼리 번들)으로 렌더 → 생성 직후 refetch 착지 전 `accounts.find(...)` undefined → "계좌를 선택하세요"로 보임. → **생성 account 로컬 옵티미스틱 병합 또는 refetch await 후 주입** 필요.

## 범위 (Scope)

포함:
1. [FE] 등록 진입점 통합 — CSV 버튼 제거, FAB(+) → [거래내역서 업로드 / 매수 / 매도] 3택 chooser. **(완료)**
2. [BE] accounts.account_number 마이그레이션 + Account/AccountCreate/AccountUpdate passthrough (+ pytest).
3. [FE] 내역서 업로드 시 계좌번호 매칭 — 일치 자동선택 / 불일치 신규계좌 확인 등록.
4. [FE] AccountFormPanel onCreated + account_number 필드.
5. [FE] 수동 등록 인라인 계좌등록 배선 (account_number 포함).
6. [FE] 빈 상태 → 거래등록 유도.
7. [FE] 최근/보유 종목 빠른선택 칩.
8. [DOC] decisions.md 에 account_number 추가 결정 + 매칭 규칙 + 트레이드오프 기록.

제외 (이번 스코프 아님):
- 수동 등록 위자드(단계별 분할).
- 단가 자동제안, 거래성공 후 자산추이 착지, meta step 스킵, import 실패 폴백.
- account_number 유니크 제약/인덱스, 별도 매칭 BE 엔드포인트, 마스킹 내역서 부분매칭 알고리즘.

## 작업 단위

### 1. [FE] 등록 진입점 통합 — chooser  ✅ 완료
- 파일: `app/src/components/records/TradeList.tsx`. (내용은 초안대로 구현 완료 — 유지)

### 2. [BE] accounts.account_number 컬럼 + passthrough
- 파일: `api/alembic/versions/00XX_accounts_account_number.py` (신규 리비전, down_revision=`0012_board_reads`), `api/src/invest_note_api/db_ops/accounts_repo.py`, `api/src/invest_note_api/routers/accounts.py`, `api/src/invest_note_api/schemas/account.py`
- 변경:
  - 마이그레이션: `ALTER TABLE accounts ADD COLUMN account_number text` (nullable). ★**적용(upgrade)은 사용자/리더 확인 후** — 리비전 파일만 작성.
  - `accounts_repo`: `RETURNING_COLS`·`UPDATABLE_COLS` 에 `account_number` 추가.
  - `routers/accounts.create_account`: INSERT 에 account_number 포함.
  - `schemas/account`: `AccountCreate`/`AccountUpdate` 에 `account_number: str | None = None`(길이 검증 ~64자, 빈 문자열→None 정규화). 저장은 raw(숫자만 강제하지 않음 — 표시 충실, 정규화는 FE 비교 시점).
- verify: `cd api && poetry run pytest tests/test_accounts*.py -q` (없으면 tests/test_trades.py accounts 관련) — create/list/update 응답에 account_number 왕복 확인.
- 의존: 없음

### 3. [FE] 내역서 업로드 계좌번호 매칭
- 파일: `app/src/components/records/ImportTradesPanel/index.tsx` (+ `AccountStep.tsx`) (+ 공용 헬퍼 `normalizeAccountNumber`, 예: `app/src/lib/account.ts`)
- 변경:
  - 흐름: broker(파서) 선택 → file → **preview(account_id 없이 호출, 이미 optional)** → 응답 `account_hint` 로 매칭.
    - **일치**(사용자 accounts 중 `normalize(account_number) === normalize(account_hint)`) → 해당 계좌 자동선택(선택됨 표시) → commit.
    - **불일치/신규**(매칭 없음, account_hint 존재) → 신규계좌 확인 스텝: `AccountFormPanel`(작업4)에 broker + account_number prefill, 사용자 계좌명 편집/확인 후 생성 → 그 id 로 commit.
    - **account_hint 없음/추출실패** → 기존 수동 계좌 선택 흐름 폴백. 기존 계좌 수동 매핑 옵션도 노출(잘못 매칭 대비).
  - 계좌명 기본값(신규): `account_hint` 있으면 `"{broker} {정규화 뒤 4자리}"`, 없으면 broker display name.
- verify: `pnpm -C app exec tsc --noEmit` + 동작: (a) 번호 일치 자동선택, (b) 다계좌 중 정확한 계좌 선택, (c) 불일치→신규 확인 등록, (d) 힌트 없음→수동 폴백.
- 의존: 단계 2(account_number 노출), 단계 4(AccountFormPanel prefill)

### 4. [FE] AccountFormPanel onCreated + account_number 필드
- 파일: `app/src/components/settings/AccountFormPanel.tsx`
- 변경:
  - 선택적 `onCreated?: (account: Account) => void` prop 추가 (초안 결론 B).
  - schema/폼에 `account_number`(optional) 입력 필드 추가 — settings 수동 생성·수정에도 노출. prefill(예: `defaultAccountNumber` prop 또는 `account` prop 경유) 지원해 import 신규계좌 확인 스텝에서 파싱값 채움.
  - `onSubmit`: create/update input 에 account_number 포함, 생성 시 반환 캡처 → `onCreated?.(created)`.
  - 기존 settings 사용처(신규 prop 미전달) 동작 불변.
- verify: `pnpm -C app exec tsc --noEmit` + settings 계좌 추가/수정에 번호 필드 왕복, 기존 회귀 없음.
- 의존: 단계 2

### 5. [FE] 수동 등록 인라인 계좌등록 배선 (TradeBasicForm)
- 파일: `app/src/components/records/TradeBasicForm.tsx` (+ 필요 시 `TradeFormPanel.tsx`)
- 변경:
  - 계좌 Select(:349-373)에 "+ 새 계좌 추가" 추가, 0계좌면 빈 Select 대신 CTA.
  - `AccountFormPanel`(작업4) 중첩 오픈. `onCreated(account)` 에서 ★타이밍 함정 처리: 로컬 옵티미스틱 병합 또는 refetch await 후 `setValue("account_id", account.id)` → Select 즉시 선택 표시.
- verify: `pnpm -C app exec tsc --noEmit` + 0계좌 인라인 생성→즉시 선택→등록 성공.
- 의존: 단계 4, 단계 1

### 6. [FE] 빈 상태 → 거래등록 유도
- 파일: `app/src/components/home/EmptyState.tsx`
- 변경: no-accounts/no-trades 두 variant 모두 거래등록 흐름 유도(/settings 제거). import-deeplink 선례 따라 거래폼 딥링크 추가 → CTA→/records 이동 후 chooser/폼 자동 오픈. `empty_state_cta_clicked`(variant 인자) 정합 유지.
- verify: `pnpm -C app exec tsc --noEmit` + 빈상태 CTA→거래폼 도달.
- 의존: 단계 5, 단계 1

### 7. [FE] 최근/보유 종목 빠른선택 칩
- 파일: `app/src/components/records/TradeBasicForm.tsx` (+ 신규 hook/컴포넌트 `StockQuickChips`)
- 변경: 종목 입력 위 칩. BUY=최근 거래종목(trades)+보유, SELL=보유만(`usePortfolioSummary`). 클릭→`handleStockSelect`. **0건이면 렌더 안 함**.
- verify: `pnpm -C app exec tsc --noEmit` + 칩 노출/클릭/SELL 보유만/0건 미표시.
- 의존: 없음

### 8. [DOC] decisions.md 기록
- 파일: `docs/decisions.md`
- 변경: account_number **추가** 결정 기록 — 배경(다계좌 안전 자동선택), 매칭 규칙(전체번호 정규화 동일성, FE-side, 저장 raw), 마이그레이션 confirm-gate, 트레이드오프(유니크 미강제·마스킹 미지원·재발급 엣지), 향후(마스킹/부분매칭·인덱스).
- verify: 문서 반영 확인.
- 의존: 없음

## QA 단위 (incremental — 각 구현 태스크에 blockedBy)

- QA-1: chooser 라우팅 (blockedBy 1) — 이미 구현됨, 회귀 확인.
- QA-2: [BE] account_number 왕복 — create/list/update 응답 shape, 마이그레이션 리비전 정합(head 체인), pytest 통과. (blockedBy 2)
- QA-3: import 매칭 E2E — 번호 일치 자동선택 / 다계좌 정확 선택 / 불일치 신규 확인 등록 / 힌트없음 수동 폴백. preview `account_hint` shape↔FE 타입, normalize 규칙 검증. (blockedBy 3)
- QA-4: 인라인 계좌등록 — onCreated 후 Select 즉시 선택(★타이밍), account_number 필드 왕복, 등록 성공. (blockedBy 4,5)
- QA-6: 빈상태 CTA→거래폼 도달, empty_state_cta_clicked 정합. (blockedBy 6)
- QA-7: chips 소스 — SELL=보유만, 0건 미표시, 클릭 채움. (blockedBy 7)

각 QA 는 BE 응답 shape ↔ FE 타입 일치(account_number, preview account_hint, accountsApi.create 반환 Account)·색상(매수 rise/매도 fall)·모바일 320~430px 확인.

## 완료 조건
- [x] BE: 마이그레이션 리비전 작성(적용은 confirm-gate) + passthrough + pytest 통과
- [x] 모든 FE 단위 `pnpm -C app exec tsc --noEmit` 통과 + 동작 시나리오 확인
- [x] `docs/decisions.md` 갱신(account_number 추가 + 매칭 규칙)
- [x] 두 ★검토 결론 반영(번호 매칭 자동선택 / Select 렌더 타이밍 / account_hint 정규화)
- [x] spec → spec-history 이동 준비

---

# 개발 검수 반영 (2026-07-01)

> 브랜치 `feature/activation-register-flow` 활성화 feature의 개발 검수 5건 부분 재실행. 위 본 사양(단위 1~8)은 유지, 아래는 검수 append. **전부 FE — 신규 BE 태스크 없음.**

## 사전 확인 (BE 영향 판정 · 실측)

- **BE 변경 불필요(확인만 완료)**:
  - `AccountUpdate.account_number` passthrough 존재 — `api/src/invest_note_api/schemas/account.py:97,114` (`_parse_account_number`, raw 저장·64자 제한). item 5 의 hint→account_number 자동기입에 그대로 사용 가능.
  - `accountsApi.update(id, input)` 존재 — `app/src/lib/api-client.ts:146`. **`AccountInput.name` 은 필수(string)** → 부분 update 시 `name: acc.name` 동봉 필수(생략 시 name 유실 위험).
  - `accounts.account_number` 마이그레이션(0013) 적용 완료 — 추가 마이그레이션 불필요.
- **★item 5 계좌 표시명 검토 결론 — 파서/preview 는 계좌 표시명을 주지 않는다**:
  - `ParseResult`/`ParsedTrade`(`broker_import/base.py:74,82`)·`ImportPreviewResponse`(`schemas/trade_import.py:16`) 모두 `account_hint`(계좌번호)만 보유, 계좌 **표시명(계좌명/상품명) 필드 없음**. 파서 4종 정규식도 계좌번호만 캡처.
  - → 신규 계좌명은 **FE fallback 포맷만** 사용: `"{증권사명}-{정규화 뒷4자리}"`, 힌트 없으면 증권사명. **BE 파서 계좌명 추출은 스코프 밖**(broker별 상이·복잡도 큼, 요구 대비 과투자).

## ★미커밋 코드리뷰 수정(F1~F5) 보존 규칙 (clobber 금지)

item 5 가 `ImportTradesPanel/index.tsx`·`PreviewStep.tsx` 를 크게 바꾸므로, 워킹트리의 미커밋 리뷰 수정을 **삭제가 아니라 새 스텝 구조로 이관**한다:
- `index.tsx`: `handleFileSelect`(단일계좌=매칭 생략 후 scoped preview+자동선택), `hintMismatch` 계산, `handleSelectAccount`(oversell 재-preview).
- `PreviewStep.tsx`: `hintMismatch` 경고 배너, Select `disabled={isLoading}`.
- `TradeBasicForm.tsx`: `handleStockSelect` 의 `setValue(..., shouldValidate)` (item 2/3/4 는 이 함수를 건드리지 않음 — 보존).
- `lib/deeplink-signal.ts` + `import/trade-form-deeplink.ts`(팩토리) — 이번 5건과 무관, 손대지 않음.

## 작업 단위 (검수)

### C1. [FE] RegisterChooser 배경 통일
- 파일: `app/src/components/records/RegisterChooser.tsx`
- 결정: **매수/매도 모두 채움(fill-both)**. 매수=`PNL_COLORS.rise.bg`(현행 유지), 매도=`PNL_COLORS.fall.bg`(solid·흰 텍스트·아이콘 원 `bg-white/20`)로 매수 hero 와 대칭. 거래내역서 업로드는 중립 카드 유지.
  - `PNL_COLORS.fall.bg`=`bg-[var(--fall)]` 존재 확인됨(`pnl-colors.ts:22`).
  - ★의식적 트레이드오프: 기존 "매수=단독 hero 강조" 의도를 버리고 매수·매도를 동등 primary 로 제시(둘 다 첫 활성화 유도 동선). 대안(전부 배경 없음)은 두 주요 액션의 시각적 어포던스 상실로 기각.
  - 색상 규칙 준수: 매수=rise / 매도=fall.
- verify: `pnpm -C app exec tsc --noEmit` + 시각 확인(매수 빨강 채움·매도 파랑 채움·업로드 중립, 320~430px).
- 의존: 없음

### C2. [FE] TradeBasicForm 종목 변경 시 가격/수량/수수료/제세금 0 초기화
- 파일: `app/src/components/records/TradeBasicForm.tsx` (`clearStockSelection`)
- 변경: `clearStockSelection` 에 초기화 추가 — 총액은 파생(자동)이므로 별도 초기화 불필요.
  - `price`, `quantity`: `setValue(name, 0)`.
  - `commission`, `tax`: ★**`resetField(name, { defaultValue: 0 })`** 로 초기화(단순 `setValue` 는 dirty 플래그가 남아, 이전에 수수료/세금을 수동편집했다면 이후 price/qty 입력 시 `recalcFees` 가 skip → 0 고정되는 버그. resetField 로 dirty 까지 clear 해야 auto-recalc 복귀). `useForm` 구조분해에 `resetField` 추가.
- ★명시 결정:
  - `clearStockSelection` 은 **매수/매도 탭 전환(line 327)** 에서도 호출 → 탭 토글 시 입력한 가격/수량/수수료/세금도 0 이 됨(현행은 유지). 탭 전환이 종목도 리셋(`asset_name=""`)하므로 fresh 입력으로 간주, **의도된 동작으로 확정**.
  - chip/보유선택 경로(`handleStockSelect` 직접 호출)는 `clearStockSelection` 을 안 거침 → 그 경로의 종목 교체 시 숫자 초기화 안 됨. **이번 스코프는 텍스트 종목 변경(clearStockSelection 경로)만** — chip/보유선택 초기화는 요구에 없어 제외(필요 시 후속).
- verify: `pnpm -C app exec tsc --noEmit` + 동작: (a) 종목명 수정→가격/수량/수수료/세금 0, (b) 수수료 수동편집 후 종목변경→새 price/qty 입력 시 수수료 auto-recalc 복귀(dirty clear 검증), (c) 탭 전환 시 숫자 0.
- 의존: 없음 (단, 동일 파일 C3/C4 와 순차 — C2 먼저)

### C3. [FE] 계좌 Select 항목 우측에 account_number 표시
- 파일: `app/src/components/records/TradeBasicForm.tsx` (계좌 Select: SelectTrigger·SelectItem)
- 결정: **item-layout 방식**(공유 `AccountChip` 미변경 — blast radius 최소). SelectItem/Trigger 를 `flex items-center justify-between` 로 감싸 좌측 `AccountChip`, 우측에 `account_number`(muted·`text-xs`·`tabular-nums`·truncate). **`account_number` 가 null/빈 값이면 우측 span 렌더 안 함**.
  - 표시값: raw `account_number` 그대로(정규화·마스킹 없음). 길면 truncate.
  - PreviewStep 계좌 Select 는 item 5(C5)에서 카드 스텝으로 대체되므로 여기서는 손대지 않음(중복/충돌 회피).
- ★맥락(버그 아님): 기존 계좌 대부분 `account_number=null` → 당분간 우측 빈칸. C5 의 hint 자동기입이 채워야 실효 → C3↔C5 상호 보완(상호의존 note).
- verify: `pnpm -C app exec tsc --noEmit` + 동작: 번호 있는 계좌 우측 표시 / null 계좌 미표시 / 트리거·드롭다운 양쪽.
- 의존: C2 (동일 파일 순차)

### C4. [FE] "새 계좌 추가"를 "계좌" Label 행 우측으로 이동
- 파일: `app/src/components/records/TradeBasicForm.tsx` (계좌 섹션 Label 행)
- 변경: `<Label>계좌 *</Label>` 행을 `flex items-center justify-between` 로 — 좌측 Label, 우측 "+ 새 계좌 추가" 버튼(현행 `setAccountPanelOpen(true)` 동작 유지). Select 아래의 기존 "새 계좌 추가" 버튼(현 424~433) 제거. 0계좌 dashed CTA(현 391~399) 는 본문에 유지(빈 상태 진입점).
- verify: `pnpm -C app exec tsc --noEmit` + 동작: 라벨 행 한 줄(라벨 좌/추가 우), 아래 중복 버튼 없음, 클릭→패널 오픈, 0계좌 CTA 유지.
- 의존: C3 (동일 파일 순차)

### C5. [FE] 거래내역서 등록 흐름 재설계 — 계좌선택 카드 스텝 신설
- 파일: (신규) `app/src/components/records/ImportTradesPanel/AccountSelectStep.tsx`, (수정) `ImportTradesPanel/index.tsx`, `ImportTradesPanel/PreviewStep.tsx`
- 새 스텝머신: `broker → file → **account(카드) → preview → commit**`.
  - **C5a [FE] AccountSelectStep.tsx (신규 카드 컴포넌트)**: 계좌 목록 카드 + "신규 등록" 카드. 각 카드에 broker 로고·계좌명·`account_number`(있으면). 선택 상태(radio-like). 기본 선택 = 매칭 계좌 있으면 그 카드, 없으면 "신규 등록" 카드. 사용자 선택 가능. 매칭/미매칭/힌트없음 안내 배너(현 PreviewStep 의 matchState 문구 이관). 0계좌면 "신규 등록" 카드만. 순수 presentational(선택·확정 콜백 상향).
    - verify: `pnpm -C app exec tsc --noEmit`.
    - 의존: 없음
  - **C5c [FE] PreviewStep.tsx 정리**: 임베드된 계좌 Select 제거 → 확정 계좌를 **읽기전용 표시**(AccountChip + "계좌 변경" 링크로 account 스텝 back). `hintMismatch` 경고 배너는 account 스텝으로 이관(잔여 필요 시 유지). oversell/카운트 표시는 유지.
    - verify: `pnpm -C app exec tsc --noEmit`.
    - 의존: C5a
  - **C5b [FE] index.tsx 스텝머신 재배선 + hint 자동기입(통합)**:
    - `Step` 타입에 `"account"` 추가. `file` → 파일 선택 시 1차 preview(account 없이)로 `account_hint` 확보·`matchedAccount` 계산 → `account` 스텝. **단일계좌 최적화 이관**: `accounts.length===1` 이면 account 스텝 스킵하고 그 계좌 scoped preview 후 바로 `preview`(현 handleFileSelect 로직 이관).
    - `account` 스텝 확정("다음"):
      - **기존 계좌 선택** → 그 계좌 scoped 재-preview(oversell/카운트 갱신, 현 `handleSelectAccount` 로직 이관) → `preview`.
      - **"신규 등록" 카드** → `AccountFormPanel` prefill(계좌명 fallback `"{broker}-{뒷4자리}"`, broker, `account_number=hint`) → 생성 → scoped preview → `preview`(신규는 보유0이라 재-preview 생략 여지, 엔지니어 판단).
    - **★★ hint→account_number 자동기입 게이트 (데이터 오염 방지 — 최우선 불변식)**:
      1. write 조건: picked 기존 계좌의 `account_number` 가 **null/빈 값일 때만** `accountsApi.update(id, { name: acc.name, account_number: hint })`. **이미 다른 번호가 있으면(=hintMismatch) write 금지, 경고만**(정확한 번호를 오염시키지 않음).
      2. write 시점: tentative 선택이 아니라 **commit 확정 직전**(back-nav 로 계좌 바꾸면 엉뚱한 계좌에 쓴 잔재 방지).
      3. write 후 accounts 소스 쿼리(trades 번들) **invalidate 필수**(stale 방지).
      4. `AccountInput.name` 필수 → `acc.name` 동봉(name 유실 방지).
      5. 조용히 쓰지 말고 **toast 고지**("이 계좌에 계좌번호를 저장했어요" 류).
    - **back-nav 재배선**: `preview → account → file → broker`(현 preview→file 을 preview→account 로). importKey remount 리셋이 새 `account` 스텝 상태(선택·validatedAccountId 등)도 비우는지 확인.
    - verify: `pnpm -C app exec tsc --noEmit`.
    - 의존: C5a, C5c
- 전체 verify(동작): (a) 단일계좌 account 스텝 스킵, (b) 다계좌 매칭 자동선택 카드, (c) 미매칭 기존계좌 선택→commit 시 번호 자동기입+toast+매칭 유지(재실행 시 매칭), (d) 이미 다른 번호 보유 계좌 선택→경고·write 안 함, (e) 신규 카드→계좌명 fallback prefill 생성→등록, (f) oversell 재-preview 이관 확인, (g) back-nav 5스텝.
- 의존: 없음(하위 C5a→C5c→C5b 순)

### C6. [DOC] decisions.md — hint 자동기입 결정 기록
- 파일: `docs/decisions.md`
- 변경: item 5 의 **미매칭 기존계좌 선택 시 account_hint→account_number 자동기입** 결정 기록 — 배경(추후 자동매칭), 오염 방지 게이트(null 일 때만·commit 시점·mismatch 경고), 계좌 표시명은 파서 미제공→FE fallback 포맷, 트레이드오프.
- verify: 문서 반영 확인.
- 의존: C5b

## QA 단위 (검수 — 각 구현에 blockedBy)

- QA-C1: RegisterChooser 매수/매도 채움·색상(rise/fall)·업로드 중립·모바일. (blockedBy C1)
- QA-C2: 종목 변경→가격/수량/수수료/세금 0, **dirty clear 후 auto-recalc 복귀**, 탭 전환 초기화. (blockedBy C2)
- QA-C3: 계좌 Select 우측 account_number 표시/ null 미표시/ 트리거·드롭다운. (blockedBy C3)
- QA-C4: 새 계좌 추가 라벨 행 우측 배치·중복 버튼 없음·클릭 동작. (blockedBy C4)
- QA-C5: import 5스텝 E2E — 단일계좌 스킵 / 다계좌 매칭 자동 카드 / 미매칭 선택→**번호 자동기입(null 일 때만)·toast·재매칭** / 다른번호 보유→**경고·write 없음** / 신규 카드 fallback 계좌명 / **oversell 재-preview 이관** / hintMismatch 경고 이관 / back-nav. preview `account_hint` shape↔FE 타입, `AccountInput.name` 동봉 확인. (blockedBy C5b)

각 QA: BE 응답 shape ↔ FE 타입 일치 · 색상 규칙(매수 rise/매도 fall) · 모바일 320~430px.

## 완료 조건 (검수)
- [x] C1~C5 `pnpm -C app exec tsc --noEmit` 통과 + 동작 시나리오
- [x] item 5 hint 자동기입 오염 방지 게이트(null-only·commit 시점·mismatch 경고·invalidate·name 동봉) 반영
- [x] 미커밋 F1~F5 리뷰 수정 이관(삭제 아님) 확인
- [x] `docs/decisions.md` 갱신(C6)
- [x] BE 변경 없음 확인(passthrough/마이그레이션 기존 사용)
