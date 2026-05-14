# Spec: BE simplify Round 5 — 재사용 / 잔여 정리

> 완료: 2026-05-03

## 배경 / 문제

`docs/backlog.md` 의 "BE simplify > 재사용 / 잔여" 섹션에는 Round 1~4 에서 미처리된 후속 항목 7개가 남아 있다. 이전 4개 라운드와 동일한 패턴(작은 단위 정리, 동작 불변, 기존 pytest 회귀로 검증)으로 안전하게 묶어 처리할 수 있는 5개 항목 + decisions 기록 1건을 Round 5 로 일괄 처리한다. `is_manual_input` 필드 폐기는 BE+FE 동기 변경이 필요해 별도 spec 으로 분리하고, `_parse_realtime_price`/`_parse_basic_price` 통합은 응답 구조 차이로 미진행 결정한다.

## 목표

- 라우터 3곳에 흩어진 accounts SELECT 가 `accounts_repo` 단일 헬퍼/컬럼 SOT 로 흡수된다.
- `trade_import.py` signature 4함수의 중복이 줄고 라우터 두 곳의 KST 일자 파싱 try/except 가 헬퍼로 흡수된다.
- 분석 dist 빌드 2 곳이 `collections.Counter` 로 단순화되고 bucket 헬퍼가 통합된다.
- `trade_types.py` decimal validator 3개의 공통 변환 로직이 단일 헬퍼로 추출된다.
- `EMOTION_UNTAGGED` / `TAG_UNTAGGED` 가 Literal 타입으로 명시되고, dist 키 타입이 `EmotionType | Literal["UNTAGGED"]` 로 좁혀진다.
- `external/quotes._parse_*` 통합 미진행 사유가 `decisions.md` 에 기록되어 백로그에서 제거된다.
- 기존 백엔드 pytest 251 케이스가 모두 통과한다.

## 설계

### 접근 방식

이전 라운드 패턴(1 항목 = 1 커밋, 동작 불변, pytest 회귀로 검증)을 그대로 따른다. 신규 테스트는 추가하지 않으며 기존 테스트 통과로 회귀를 검증한다. 영향 표면이 가장 좁은 항목부터 진행한다 (E → D → C → B → A → F).

### 주요 변경 파일

**A. accounts SELECT 통합 + 컬럼 SOT**
- `api/src/invest_note_api/repositories/accounts_repo.py` — `list_accounts(conn)` 헬퍼 신설, 기존 `RETURNING_COLS` 재활용
- `api/src/invest_note_api/routers/accounts.py:27` — 인라인 SELECT → `list_accounts()` 호출
- `api/src/invest_note_api/routers/portfolio.py:82` — `SELECT *` → `list_accounts()` 호출
- `api/src/invest_note_api/routers/trades.py:128` — `SELECT *` → `list_accounts()` 호출

**B. trade_import signature 4함수 + KST 일자 파싱 헬퍼 통합**
- `api/src/invest_note_api/domain/trade_import.py:45-105` — `make_signature` / `make_preview_signature` / `trade_to_signature` / `trade_to_preview_signature` 통합. `account_id: str | None` 파라미터로 단일화 또는 공통 헬퍼 추출. (4→2 함수 목표)
- `api/src/invest_note_api/routers/trades.py:359-362, 401-405` — KST 일자 파싱 try/except → `trade_import.parse_kst_date(s: str) -> date | None` 헬퍼로 흡수

**C. analysis dist 빌드 Counter 도입 + bucket 헬퍼**
- `api/src/invest_note_api/domain/analysis/aggregate.py:59-70, 112-131` — `_holding_bucket` / `_size_bucket` 가 동일한 "정렬된 buckets 리스트에서 첫 매치 label 반환" 패턴이므로 `_first_bucket_label(value, buckets)` 일반 헬퍼로 통합. dist 누산은 `Counter(...)` 로 치환.

**D. trade_types decimal validator 공통 헬퍼**
- `api/src/invest_note_api/domain/trade_types.py:102-125` — `_decimal_to_float` / `_decimal_to_float_optional` / `_decimal_to_int_optional` 의 공통 변환부를 `_to_number(v, *, target, optional)` 헬퍼로 추출. 각 validator 는 헬퍼 호출만.

**E. EMOTION_UNTAGGED / TAG_UNTAGGED Literal 타입**
- `api/src/invest_note_api/domain/trade_types.py:14, 37-38` — `UntaggedLiteral = Literal["UNTAGGED"]` 정의, `EMOTION_UNTAGGED: UntaggedLiteral = "UNTAGGED"` / `TAG_UNTAGGED: UntaggedLiteral = "UNTAGGED"` 타입 명시. `EmotionBucket = EmotionType | UntaggedLiteral`, `ReasoningTagBucket = ReasoningTag | UntaggedLiteral` 노출.
- `api/src/invest_note_api/domain/analysis/aggregate.py:171, 199` — dist 키 타입을 `EmotionBucket` / `ReasoningTagBucket` 으로 명시.
- `api/src/invest_note_api/schemas/analysis_response.py:17` — `EmotionStatsResponse.type` / `TagStatsResponse.tag` 의 `str` 을 새 Bucket 별칭으로 좁힘.

**F. decisions.md 기록 (_parse_realtime/_basic 미진행)**
- `docs/decisions.md` — 2026-05-03 추가 항목으로 `_parse_realtime_price` / `_parse_basic_price` 통합 미진행 결정 기록.
- `docs/backlog.md` — `재사용 / 잔여` 섹션에서 `_parse_*` 항목 제거.

**완료 처리 (마지막)**
- `docs/backlog.md` — 완료된 5개 항목 제거, 잔여 항목(`is_manual_input` 폐기)만 남기고 Round 5 처리 노트 추가.
- `docs/spec-current.md` → `docs/spec-history/2026-05-03-be-simplify-round5-reuse.md`.

## 구현 체크리스트

- [x] **E.** Literal 타입 명시 (`UntaggedLiteral`, `EmotionBucket`, `ReasoningTagBucket`) + 사용처 타입 좁힘
- [x] **D.** `_decimal_to_*` 3 validator 공통 헬퍼 추출
- [x] **C.** `_first_bucket_label` 일반 헬퍼 + `Counter` 기반 dist 빌드
- [x] **B.** trade_import signature 4함수 통합 + `parse_kst_date` 헬퍼로 trades.py KST 파싱 흡수
- [x] **A.** `accounts_repo.list_accounts` 헬퍼 + 라우터 3곳 인라인 SELECT 흡수
- [x] **F.** `decisions.md` 기록 + `backlog.md` 의 `_parse_*` 항목 제거
- [x] 백엔드 pytest 통과 (`cd api && poetry run pytest -q`) — 251 cases passed

## 우려사항 / 리스크

- **B (trade_import 통합)** — 4함수 시그니처/반환 타입(TradeSignature vs PreviewSignature)이 달라 통합 후 가독성 저하 시 보수적 형태(공통 헬퍼만 추출)로 후퇴.
- **D (decimal validator)** — Pydantic 2.x `field_validator` 가 헬퍼 등록을 받아주는지 검증 필요. 안되면 함수 본문만 공통화.
- **E (Literal 타입)** — wire 호환은 동일 문자열이라 깨지지 않음. FE 타입 (`app/src/lib/analysis/aggregate.ts:17-22` 의 `type: string` / `tag: string`) 좁힘은 본 라운드 범위 외 — 별도 FE 후속 작업으로 둠.
- 모든 변경은 동작 불변 — 기존 251 pytest 케이스가 회귀 검증 책임.

## 후속 작업 (별도 spec)

- `SellBreakdown.is_manual_input` 필드 폐기 (BE+FE 동기 변경) — backlog 에 남아 있음.
- FE `app/src/lib/analysis/aggregate.ts` 의 `EmotionStats.type`, `TagStats.tag` 를 `EmotionType | "UNTAGGED"` / `ReasoningTag | "UNTAGGED"` 로 좁히기 — Round 5 BE 변경의 wire format 자체는 동일하므로 비차단 후속.

## 검증

```
cd api && poetry run pytest -q
```

기존 251 케이스 모두 통과.
