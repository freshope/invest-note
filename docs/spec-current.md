# Spec: 콤마 숫자 파싱 헬퍼 통합

## 배경 / 문제

백엔드에서 동일한 "쉼표 포함 숫자 문자열 → 숫자" 변환 코어를 3개 파일이 각자 보유하고 있어, 정규화 규칙이 바뀔 때 여러 파일을 동시에 수정해야 한다.

- `api/src/invest_note_api/schemas/trade.py:29-48` — `_comma_positive`/`_comma_non_negative`
- `api/src/invest_note_api/schemas/account.py:10-23` — `_parse_cash`
- `api/src/invest_note_api/broker_import/base.py:9-16` — `parse_number`

세 헬퍼는 반환 타입(`float`/`Decimal`), 실패 처리(예외/0.0 폴백), 범위 검증이 모두 다르므로 완전 통합 대신 공통 코어만 추출한다.

## 목표

- 신규 공용 모듈 `api/src/invest_note_api/utils/numbers.py`에 쉼표·공백 정규화 헬퍼 1개 도입.
- 위 3개 파일의 콤마 처리 코어가 새 헬퍼를 호출하도록 변경.
- 각 헬퍼의 외부 동작(반환 타입, 예외 메시지, 0 폴백)은 변경하지 않음 (순수 리팩터).
- 신규 단위 테스트 + 기존 테스트 전부 통과.

## 설계

### 접근 방식

공통점인 "문자열 입력의 쉼표·공백 제거" 한 줄만 추출.

```python
def strip_comma_number(value: object) -> object:
    """숫자 파싱 직전 정규화: 문자열이면 ',' 제거 후 strip, 그 외는 그대로 반환."""
    if isinstance(value, str):
        return value.replace(",", "").strip()
    return value
```

각 호출 측은 이 헬퍼 호출 후 자신의 변환·검증 로직 유지.

**범위 외:** `external/quotes.py:49,65,66`의 inline 호출 — `.strip()` 없고 빈 문자열 처리 의도가 다름.

### 주요 변경 파일

- `api/src/invest_note_api/utils/__init__.py` — 신규 (빈 파일)
- `api/src/invest_note_api/utils/numbers.py` — 신규
- `api/src/invest_note_api/schemas/trade.py`
- `api/src/invest_note_api/schemas/account.py`
- `api/src/invest_note_api/broker_import/base.py`
- `api/tests/test_utils_numbers.py` — 신규
- `docs/backlog.md` — 항목 제거

## 구현 체크리스트

- [ ] `api/src/invest_note_api/utils/__init__.py` 신규
- [ ] `api/src/invest_note_api/utils/numbers.py` 신규: `strip_comma_number`
- [ ] `api/tests/test_utils_numbers.py` 신규: 단위 테스트
- [ ] `schemas/trade.py` 리팩터
- [ ] `schemas/account.py` 리팩터
- [ ] `broker_import/base.py` 리팩터
- [ ] `cd api && poetry run pytest -q` 전체 통과
- [ ] `docs/backlog.md`에서 해당 항목 제거

## 우려사항 / 리스크

- 외부 동작 차이 0을 유지하기 위해 예외 메시지·반환 타입·0 폴백 경로를 그대로 보존.
- `parse_number`의 비문자열 경로 동작이 변하지 않는지 단위 테스트로 검증.
