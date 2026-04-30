# Spec: aggregate.py percentage 패턴 헬퍼 통합

## 배경 / 문제

`profile.py`에 이미 도입된 `_percent(numer, denom)` 헬퍼(0 분모 안전 처리)가
`aggregate.py`에서는 7개 위치에 동일 패턴이 인라인으로 중복 작성되어 있다.
공용 모듈로 추출해 두 파일이 공유하면 중복이 사라지고 0 분모 처리 누락 위험이 줄어든다.
기능 변경 없는 정리 작업.

## 목표

- `_percent` 헬퍼를 `domain/analysis/_math.py`로 이동, `profile.py`/`aggregate.py`가 공통 import
- `aggregate.py`의 7개 percentage 위치가 모두 `_percent` 호출로 통일
- 기존 테스트(`api/tests/test_analysis_logic.py`)가 변경 없이 통과 (수치 동일)

## 설계

### 접근 방식

1. `domain/analysis/_math.py` 신설 — `_percent(numer, denom)` 정의 (현재 `profile.py:42-43`과 동일 시그니처/로직)
2. `profile.py`는 자체 정의를 제거하고 `from ._math import _percent` import
3. `aggregate.py`는 `from ._math import _percent` import 후 7개 위치에 적용
   - `_win_rate` 헬퍼(line 75-76)도 내부 구현을 `_percent` 호출로 단순화 (외부 시그니처 유지)

### 주요 변경 파일

- `api/src/invest_note_api/domain/analysis/_math.py` — 신규. `_percent(numer, denom)` 정의
- `api/src/invest_note_api/domain/analysis/profile.py` — `_percent` 정의 제거, import로 대체 (line 42-43 삭제)
- `api/src/invest_note_api/domain/analysis/aggregate.py` — `_percent` import 후 7개 위치 적용:
  - line 75-76: `_win_rate` 내부를 `_percent(sum(1 for r in results if r == RESULT_SUCCESS), len(results))`로
  - line 89: `win_rate = _percent(win_count, len(sells_with_result))`
  - line 157: `strategy_adherence_rate = _percent(followed, len(judged))`
  - line 215-216: `missing_tag_rate = _percent(sum(1 for t in buys if not t.reasoning_tags), len(buys))`
  - line 218-219: `feeling_rate = _percent(sum(1 for t in buys if TAG_FEELING in (t.reasoning_tags or [])), len(buys))`
  - line 221-224: `reflection_rate = _percent(sum(1 for t in sells if t.sell_reason and t.sell_reason.strip()), len(sells))`
  - line 225: `result_input_rate = _percent(len(sells_with_result), len(sells))`

## 구현 체크리스트

- [x] `api/src/invest_note_api/domain/analysis/_math.py` 신규 생성 — `_percent` 정의
- [x] `profile.py`에서 `_percent` 제거 + `_math` import 추가
- [x] `aggregate.py`에 `_math` import 추가 + 7개 위치 (`_win_rate` 포함) 일괄 치환
- [x] `cd api && poetry run pytest tests/test_analysis_logic.py tests/test_analysis.py -q` 통과 확인 (50 passed)

## 검증

- 단위 테스트: `cd api && poetry run pytest tests/test_analysis_logic.py -q` — `missing_tag_rate`, `feeling_rate`, `reflection_rate`, `result_input_rate`, `win_rate`가 기존 기대값과 동일해야 함
- 통합 테스트: `cd api && poetry run pytest tests/test_analysis.py -q`
- 전체 백엔드 회귀: `cd api && poetry run pytest -q` (선택)

## 우려사항 / 리스크

- 기능 변경 없는 순수 리팩터. `_percent`는 `if denom else 0.0` 동일 시맨틱이므로 수치 차이가 발생할 여지가 없음.
- `_win_rate` 함수는 외부 시그니처 유지(`list[str] -> float`)하므로 호출 측 변경 불필요.
