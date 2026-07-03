# 거래내역서 원장(ledger) — 캡처/물질화 2-스테이지 분리 사양서

> 결정 근거: `docs/decisions.md` 2026-07-02 「거래내역서 원장(ledger) 도입」.
> **성격: BE 전용.** 조회 API·재구성 엔진·FE 노출은 스코프 밖.

## 배경 / 목적

거래내역서에서 추출 가능한 정보를 **무손실로** 기록해, (a) 지금 안 쓰는 필드를 추후 기능이 쓰고, (b) `trades` 손상 시 **객관적 거래 사실**을 재생성한다. 그리고 파일 업로드→원장 적재를 **일괄등록과 분리**해, 원장을 임포트의 단일 소스로 만든다.

## 아키텍처 — 2-스테이지

```
[Stage 1: 캡처 — 일괄등록과 무관, 서비스로 분리]
파일 업로드 → 파서(모든 행 raw) → import_ledger_entries (append 적재)
                                  └ import_batches + 원본파일 R2 (90일 TTL)

[Stage 2: 물질화 — 일괄등록]
import_ledger_entries 읽기 → ticker 해소 → 거래 판별
   → trade-signature dedup/merge(기존 로직 재사용) → trades INSERT
   → trades.source_ledger_entry_id 로 provenance 링크
```

- **원장 = 얇게**: raw + 최소 식별 필드 + provenance 만. 분류·실행결과·해소결과는 넣지 않음(Stage 2 산출).
- **원장 = SoT**: `import_staging`(0010) 대체. preview 는 원장을 읽고, commit 은 원장→trades. staging 만료 버그 구조적 해소.
- **재실행 idempotent**: trade-signature dedup 이 중복 trade 생성을 막음.

## 스키마 (Alembic 신규 리비전 `0014`, 현재 head `0013_accounts_account_number` 뒤)

> ★ **리비전 파일 작성까지만. `alembic upgrade` 실행은 사용자/리더 확인 후.** (기존 0004~0013 관례)
> 신규 테이블 2개 + `trades` 컬럼 1개 — superuser 불요, `invest_note_app` owner(0003 패턴).

### `import_batches` — 파일 1건 (파일 메타)
| 컬럼 | 타입 | 비고 |
|---|---|---|
| id | uuid PK | |
| user_id | uuid NOT NULL, FK→users **ON DELETE CASCADE** | |
| broker_key | text NOT NULL | samsung_xlsx 등 |
| parser_version | text NOT NULL | drift 감지·재파싱 판단 |
| filename / content_type / size_bytes | text / text / bigint | |
| storage_key | text NULL | R2 key (파기 후 NULL) |
| content_sha256 | text NOT NULL | 같은 파일 재업로드 dedup |
| account_hint | text NULL | 파일 추출 원문 계좌번호 |
| account_id | uuid NULL, FK→accounts **ON DELETE SET NULL** | 등록 시 채움(어느 계좌로) |
| committed_at | timestamptz NULL | 등록 시 채움 — 미리보기만 한 배치와 구분 |
| created_at / parsed_at | timestamptz | |

인덱스: `(user_id, created_at DESC)`, **UNIQUE `(user_id, content_sha256)`**(파일 dedup).
> **파일 삭제는 R2 lifecycle 이 소유**(앱 정리 잡·만료 컬럼 없음), storage_key 읽기는 90일 경과분 만료(404) 관용. account_id·committed_at 은 등록(commit) 생애주기 마커 — 캡처는 여전히 독립(NULL 로 시작).

### `import_ledger_entries` — 행 1건 (**append-only**, dedup 안 함)
| 컬럼 | 타입 | 비고 |
|---|---|---|
| id | uuid PK | |
| batch_id | uuid NOT NULL, FK→import_batches **ON DELETE CASCADE** | provenance |
| user_id | uuid NOT NULL, FK→users **ON DELETE CASCADE** | |
| source_row_no | integer NOT NULL | provenance |
| traded_at_raw | text NULL | 원문 문자열 |
| traded_at | timestamptz NULL | (미사용, Stage 2 가 raw 에서 도출) |
| trade_type | text NULL | BUY/SELL — **거래 행 식별 키**(비거래=NULL) |
| asset_name / ticker_hint / isin / country_code | text NULL | 식별 힌트 |
| quantity / price | numeric NULL | 식별 필드 |
| commission / tax | numeric(18,2) NULL | 물질화 필요 파서 산출값(tax=세목 합산). 원문 세목은 raw 에 |
| exchange_rate | numeric(18,6) NULL | 물질화 필요(USD 원가 환산) |
| raw | jsonb NOT NULL | **행 원문 전체(원문 토큰) + 세금 항목별** |
| created_at | timestamptz | |

인덱스: `(batch_id)`. **유니크/dedup 제약 없음** — 원장은 append-only.
> **원장은 거래 dedup 을 하지 않는다**(2026-07-03 재설계, decisions.md). 모든 행을 그대로 적재(무손실). 파일 통째 재업로드만 sha256 로 skip. 같은 거래의 중복 제거는 **물질화(Stage 2)의 trade-signature dedup/merge(계좌 단위)** 가 담당. 거래 행 식별은 `trade_type IS NOT NULL`.
> 원장에 **없는** 것(의도): dedup_key·disposition·trade_id·row_kind·resolved_ticker(전부 raw 또는 Stage 2 산출).

### `trades` 컬럼 추가
- `source_ledger_entry_id` uuid NULL, FK→import_ledger_entries **ON DELETE SET NULL** — provenance(어느 원장 행에서 물질화됐는지).

## 범위 (Scope) — BE, 1요청=1파일, 의존 순서

포함:
1. **[BE] Alembic `0014`** — `import_batches` + `import_ledger_entries` + `trades.source_ledger_entry_id`(upgrade 금지 플래그). → 검증: 로컬 일회용 DB 스모크, `alembic heads` 단일.
2. **[BE] 파서 "모든 행" raw 방출** — `base` 계약을 `ParseResult.rows[]`(raw 전체 + optional 식별 필드)로 변경, 4파서(samsung/toss KRW·USD/shinhan/mirae) 반영. 세금 항목별 원문 키. 거래 인식 행은 식별 필드 추출(trade_type 채움), 비거래 행은 raw 만. → 검증: `tests/test_broker_parsers.py` 실 샘플로 전 행이 raw 로 캡처되는지, 거래 행 식별 필드 정확한지.
3. **[BE] Stage 1 캡처 서비스** — `broker_import` 서비스: 파일 bytes → 파싱 → (날짜 오류 파일 거절) → R2 저장 + `import_batches`(sha256 dedup) + `import_ledger_entries` bulk **INSERT(append, dedup 없음)**, `(user,sha256)` 재업로드만 스킵. 라우터/일괄등록과 독립. → 검증: 같은 파일 2회 → batch 1개·행 중복 0; 같은 거래 다른 파일 → 두 렌더링 모두 append.
4. **[BE] Stage 2 물질화 rewire** — 일괄등록 preview/commit 을 `import_staging` 대신 **원장 읽기**로 교체. 기존 ticker 해소·trade-signature dedup·`build_merge_patch` 정정 머지 **재사용**(재작성 아님). commit 시 `trades.source_ledger_entry_id` 채움. → 검증: 원장 기반 preview 카운트/커밋 결과가 기존과 동등, 재커밋 idempotent.
5. **[Ops] R2 lifecycle 규칙(수동)** — Cloudflare R2 콘솔에서 버킷 lifecycle 규칙 추가: **prefix `import_source/` 객체를 90일 후 만료(삭제)**. ⚠️ 버킷 전체 아님 — `broker_statement/`(제보)·OTA 매니페스트가 같은 버킷이라 prefix 스코프 필수. 앱-side 정리 잡 없음. **현재 storage_key 를 읽는 코드(다운로드 엔드포인트) 없음** → 404 관용은 자동 충족; 향후 원장 원본 다운로드 추가 시 만료(404)를 관용하도록 구현. → 검증: 규칙 문서화(이 항목) + 만료 후 원장 무결(파일만 사라지고 행 유지)은 cascade 테스트와 무관하게 R2 소관.
6. **[BE] 무손실·정합 pytest** — 실 샘플 4종: 원장 raw → 파생 재구성이 원 파싱값과 일치(b 가드), dedup(파일/거래) 회귀, cascade delete(user→batch·원장·파일 + trades.source_ledger_entry_id SET NULL). 
7. **[BE·후속 리비전] `import_staging` 드롭** — Stage 2 rewire·검증 완료 후 별도 리비전으로 `import_staging`(0010) DROP + `import_staging_repo`·라우터·테스트 참조 제거. (prod 적용 테이블이라 위험 분리)
8. **[DOC]** decisions.md(완료). 개인정보처리방침(pixelwave-web) 갱신 flag — 출시 전 별도.

제외 (이번 스코프 아님):
- replay/재구성 **실행 엔진**·원장 조회 API·FE 노출.
- **상대계좌 PII 마스킹** — 별도 스펙(사용자 지시로 제외, raw 에 그대로).
- PDF 자유텍스트/서식 등 행 구분 불가 부분 영속화(90일 원본 파일이 커버).
- 비거래 행 의미적 dedup(파일 sha256 수준만).
- 마스킹 내역서 대응·계좌명 파싱.

## 핵심 함정 / 불변식

- **파서(2)가 스키마(1)·캡처(3)보다 선행** — raw 가 부분적이거나 일부 행을 누락하면 원장이 무손실이 아니다.
- **원장 = append-only, dedup 없음** — 모든 행 그대로 적재(무손실). 중복 trade 방지는 물질화(Stage 2) trade-signature(계좌 단위). 정정본 재업로드 → 그 파일 등록 시 `build_merge_patch` 로 trades 갱신(**IMPORT 금액필드 PATCH-잠금**[[project_trade_origin]] 이라 재업로드가 정정 채널).
- **정정 범위 한계** — signature(date+identifier+type+qty+price) 밖 필드(commission/tax/time)만 갱신. **수량·단가 변경은 새 행+새 trade** → "삭제 후 재등록" 정책이 담당.
- **파일 삭제는 R2 lifecycle** — 앱은 만료 잡을 두지 않음. storage_key 접근은 만료 관용.
- **numeric 정밀도** — 식별 numeric 컬럼은 dedup/조회용, 진실은 `raw` 원문 문자열(jsonb 는 float 아닌 **문자열**로 저장).
- **staging 드롭은 후속 리비전** — Stage 2 rewire 와 같은 변경에 묶지 않음(prod 위험 분리).
- **traded_at** — `traded_at_kst_full` 있을 때만 시각 보존(기존 관례), 없으면 날짜.
- 참조: [[feedback_broker_parser_fixture_tests]], [[project_broker_import_parsers]], [[project_import_staging_durable]], [[project_alembic_migrations]], [[feedback_fe_trade_sort_for_calc]], [[project_broker_statement_submission]].
