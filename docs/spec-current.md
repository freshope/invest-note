# 신규 가입자 활성화 개선 — 계좌등록/거래등록 허들 통합 사양서

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
- [ ] BE: 마이그레이션 리비전 작성(적용은 confirm-gate) + passthrough + pytest 통과
- [ ] 모든 FE 단위 `pnpm -C app exec tsc --noEmit` 통과 + 동작 시나리오 확인
- [ ] `docs/decisions.md` 갱신(account_number 추가 + 매칭 규칙)
- [ ] 두 ★검토 결론 반영(번호 매칭 자동선택 / Select 렌더 타이밍 / account_hint 정규화)
- [ ] spec → spec-history 이동 준비
