> 완료: 2026-04-24

# Spec: BE Constants Cleanup (Follow-up)

## 배경 / 문제

`feature/extract-be-constants`(2026-04-24 merged)로 1차 정리를 완료했으나, 후속 조사에서 잔여 매직 리터럴이 확인됨.

- **Phase A (누락/버그)**: 이미 정의된 상수를 쓰지 않은 4곳
- **Phase B (신규 상수화)**: 2곳 이상 반복되는 리터럴(severity, link_section, US, 통화, 근거/회고, KST_OFFSET, PG no-op, 문자열 길이 제한)

## 목표

- Phase A 4건이 기존 상수로 교체된다
- Phase B 상수들이 단일 위치에서 정의되고 2곳 이상 호출처에서 재사용된다
- `poetry run ruff check api/` 통과, `poetry run pytest api/tests` 통과
- 공개 API 응답 텍스트/형식 동일 (리팩터만, 동작 변경 없음)

## 설계

### 접근 방식

작은 커밋 스택. Phase A(1커밋) → Phase B 영역별 5~6 커밋.
Phase B는 독립적이라 일부만 채택 후 나머지는 backlog로 넘겨도 됨.

### 주요 변경 파일

**Phase A — 4줄 치환**
- `domain/analysis/aggregate.py:154` — `'KR'` → `DEFAULT_COUNTRY`
- `routers/analysis.py:146,161` — `"SELL"/"BUY"` → `TRADE_TYPE_SELL/BUY`
- `domain/trade_types.py:69` — `country_code: str = "KR"` → `country_code: CountryCode = DEFAULT_COUNTRY`

**Phase B — 상수 추가 및 치환**
- `domain/analysis/rules.py` — `SEVERITY_*`, `SECTION_*` 모듈 상단 상수 + 10개 규칙·`_SEVERITY_ORDER` 치환
- `domain/trade_types.py` — `COUNTRY_US: CountryCode = "US"` 추가
- `routers/stocks.py`, `external/quotes.py` — `"US"` 치환
- `external/constants.py` — `CURRENCY_KRW`, `CURRENCY_USD` 추가; `quotes.py`의 `"KRW"/"USD"` 치환
- `domain/portfolio.py` — `NOTE_TYPE_REASON = "근거"`, `NOTE_TYPE_REFLECTION = "회고"` 상단 상수 + 2곳 치환
- `domain/trade_utils.py` — `KST_OFFSET = "+09:00"` 추가; `schemas/trade.py:53,54` 치환
- `db_ops/trades_repo.py` — `PG_UPDATE_ZERO`, `PG_DELETE_ZERO` 상수 + 기존 `_DELETE_ZERO`와 통일
- `routers/stocks.py`·`schemas/trade.py`·`external/quotes.py` — `MAX_CODE_LEN = 20`, `MAX_NAME_LEN = 50` 상수화 (위치: `schemas/trade.py`)

## 구현 체크리스트

### Phase A — 누락 수정

- [x] 1. `aggregate.py:154` — `'KR'` → `DEFAULT_COUNTRY`
- [x] 2. `routers/analysis.py:146,161` — BUY/SELL 상수 치환 + import
- [x] 3. `domain/trade_types.py:69` — Trade.country_code 기본값 상수화

### Phase B — 신규 상수화

- [x] 4. `rules.py` severity/link_section 상수화 + 치환
- [x] 5. `COUNTRY_US` 추가 + stocks.py/quotes.py 치환
- [x] 6. `CURRENCY_KRW/USD` 추가 + quotes.py 치환
- [x] 7. `NOTE_TYPE_*` 추가 + portfolio.py 치환
- [x] 8. `KST_OFFSET` 추가 + schemas/trade.py 치환
- [x] 9. `PG_UPDATE_ZERO`/`PG_DELETE_ZERO` 통일
- [x] 10. `MAX_CODE_LEN/NAME_LEN` 상수화 + 3개 파일 치환

### 검증

- [x] `poetry run ruff check api/` 통과
- [x] `poetry run pytest api/tests` 통과

## 우려사항 / 리스크

- `Trade.country_code` 타입을 `str` → `CountryCode`로 좁히면 DB에 `"KR"/"US"/"OTHER"` 외 값이 있을 경우 Pydantic 검증 실패. 실행 전 DB 값 확인 필요. 안전하지 않으면 타입은 `str` 유지, 기본값만 `DEFAULT_COUNTRY`로.
- `rules.py`의 severity/link_section 문자열이 API 응답으로 FE에 그대로 전달됨. 상수 이름만 부여하고 **문자열 값은 불변**.
- Phase B는 독립 커밋이라 중간 중단 가능. 필요 없는 항목은 backlog로 이동.
