# Spec: BE simplify Tier 3 Round 1

브랜치: `feature/be-simplify-tier3-round1`

## 배경 / 문제

BE simplify Tier 2 완료 후 backlog 에 deferred 된 9 개 Tier 3 항목 중,
저위험·범위 명확·의존성 적은 4 개를 Round 1 으로 분리해 처리한다.
나머지 5 개(시맨틱 위험 / 범위 큼 / 별도 설계 필요)는 backlog 에 그대로 두고
Round 2 이후로 넘긴다.

## 목표

- 계좌 row → dict 변환 헬퍼 중복 3 곳을 1 곳에서 정의 + 호출지 정리
- `_fetch_kr_price` 두 endpoint try/except 블록을 `_try_endpoint` 헬퍼로 통합
- `_is_changed` 7 필드 sequential check 를 `(attr, comparator)` lookup table 로 압축
- `_size_bucket` 6 단 if 캐스케이드 를 `_HOLDING_BUCKETS` 패턴(typed lookup table) 으로 통일
- 모든 변경 후 `cd api && poetry run pytest -q` 통과
- backlog.md Tier 3 섹션에서 완료된 4 개 제거, 남은 5 개 그대로 유지

## 설계

### 접근 방식

각 항목을 독립 커밋으로 분리한다 (review 용이성). 시맨틱 변경은 없고
코드 조직만 정리한다. Tier 2 의 `position_key`/`half_up_int`/`to_kst_ms`
헬퍼 추출 패턴을 그대로 따른다.

### 항목별 변경 파일

**A. 계좌 row 변환 헬퍼 통합**
- 신규 헬퍼 `account_row_to_dict(row)` 를 `db_ops/accounts_repo.py` (신규) 에 추가.
  책임: cash_balance Decimal→float 변환. uuid 변환은 호출자 책임으로 분리.
- `routers/accounts.py:_row_to_dict` (L19-23) → 헬퍼 사용
- `routers/portfolio.py:_account_from_row` (L34-41) → 헬퍼 사용 + uuid 변환은 그대로
- `routers/trades.py` (L113-116) accounts 인라인 변환 → 헬퍼 사용

**B. `_fetch_kr_price` 두 endpoint dedup**
- `external/quotes.py:_fetch_kr_price` (L44-79)
- `_try_endpoint(client, url, parse_fn, log_label)` 내부 헬퍼 추출
- realtime/basic 두 호출이 동일 헬퍼를 다른 `parse_fn` 람다로 호출
- 동작 변경 없음 — `tests/test_quotes.py` 통과 확인

**C. `_is_changed` lookup table화**
- `db_ops/pnl_sync.py:_is_changed` (L21-43)
- `_COMPARE_FIELDS: list[tuple[str, Callable[[Any, Any], bool]]]` 로 7 필드 메타화
- `profit_loss`, `avg_buy_price` → `_float_eq`, 나머지 5 개 → `operator.eq`
- `any(not cmp(getattr(existing, f), getattr(entry, f)) ...)` 로 압축

**D. `_size_bucket` typed lookup table 화**
- `routers/analysis.py:_size_bucket` (L50-61)
- `_SIZE_BUCKETS: list[tuple[float, str]]` (sentinel `float("inf")`) 정의
- `_HOLDING_BUCKETS` 와 동일 패턴, label 문자열 동일 유지

## 구현 체크리스트

- [x] A1. `api/src/invest_note_api/db_ops/accounts_repo.py` 신규 + `account_row_to_dict` 정의
- [x] A2. `routers/accounts.py:_row_to_dict` 헬퍼 사용
- [x] A3. `routers/portfolio.py:_account_from_row` 헬퍼 사용
- [x] A4. `routers/trades.py` accounts 인라인 변환 헬퍼 사용
- [x] B. `external/quotes.py:_fetch_kr_price` 두 endpoint 를 `_try_endpoint` 헬퍼로 통합
- [x] C. `db_ops/pnl_sync.py:_is_changed` 7 필드 lookup table 압축
- [x] D. `routers/analysis.py:_size_bucket` 을 `_SIZE_BUCKETS` typed table + 루프로 변경
- [x] `cd api && poetry run pytest -q` 통과 (250 passed)
- [x] `docs/backlog.md` Tier 3 섹션에서 완료 4 개(A·B·C·D) 제거
- [x] 각 항목별 독립 커밋 (`refactor(api): ...`)

## 우려사항 / 리스크

- A: `portfolio.py` 의 uuid str 변환은 헬퍼 외부에 그대로 두어 단일 책임 유지
- B: realtime 응답은 `data.datas[0]` 가 있을 수도/없을 수도 있어 `parse_fn` 람다가 둘을 모두 처리해야 함
- C: 비교 함수 메타정보가 lookup table 에 들어가야 하므로 단순 attr 리스트로는 부족
- D: label 문자열 동일성 검증 필요 — 분석 응답 스키마에 직접 노출되는 값
- 회귀 위험: 모두 구조 변경 없는 형식 정리 — `pytest -q` 로 검증

## Round 2 이후 deferred (backlog.md 유지)

- E. `aggregate.py` 3 버킷 루프 통합 (시맨틱 위험)
- F. `build_strategy_evaluations` 입력 범위 정리 (의도 명확화 필요)
- G. `domain/portfolio.py` `Lot` 데이터클래스화 (호환성 검증 비용)
- H. 모듈 글로벌 상태 → `app.state` (범위 큼, 모든 테스트 영향)
- I. `routers/trades.py` `_PREVIEW_ACCT` placeholder 제거 (signature 모델 변경)
