> 완료: 2026-04-24

# Spec: Extract BE (FastAPI) Constants

## 배경 / 문제

FE는 `feature/extract-fe-constants`(3620e19, 2026-04-24)에서 상수 중앙화 완료. BE(`api/`)는 아직 매직 문자열/숫자가 분산되어 있음:
- `TradeType`/`StrategyType`/... 등 enum Literal이 `domain/trade_types.py`와 `schemas/trade.py`에 **완전 중복**
- `"KR"`, `"BUY"`, `"SELL"` 같은 리터럴이 20~30곳에 하드코딩
- `_MS_PER_DAY`, `ZoneInfo("Asia/Seoul")`, `User-Agent`, `timeout=5.0`, `"authenticated"` 등이 2~3 위치에 중복

## 목표

- `api/src/invest_note_api/` 내 2회 이상 반복되는 문자열/숫자 상수를 단일 정의로 통합
- 기존 API 응답/에러 메시지 텍스트 값 불변 (리팩터만)
- `poetry run ruff check api/` 통과, `poetry run pytest api/tests` 통과

## 설계

### 접근 방식

FE 패턴과 동일하게 **영역별 작은 커밋 스택**. 모놀리식 `constants.py` 대신 **기존 도메인 구조에 co-locate**:

| 영역 | 위치 |
|---|---|
| 도메인 enum (BUY/SELL/STRATEGY/…) | `domain/trade_types.py` (단일 소스) |
| 에러 메시지 상수 | `errors.py` 모듈 상단 |
| KST / MS_PER_DAY | `domain/trade_utils.py` |
| 외부 HTTP 상수 | `external/constants.py` (신설) |
| DEFAULT_PERIOD | `domain/analysis/period.py` |
| auth role / GUC 이름 | `auth/constants.py` (신설) |

### 주요 변경 파일

1. `domain/trade_types.py` + `schemas/trade.py` — enum 중복 제거
2. `domain/trade_types.py` + 호출처 7개 파일 — BUY/SELL/KR 상수화
3. `domain/trade_utils.py`, `domain/holdings.py`, `domain/analysis/holding_period.py`, `domain/analysis/period.py` — KST/MS_PER_DAY
4. `errors.py`, `routers/trades.py`, `routers/accounts.py`, `auth/dependency.py` — 에러 메시지 상수
5. `external/constants.py` (신설), `routers/stocks.py`, `external/quotes.py` — HTTP 상수
6. `domain/analysis/period.py`, `routers/analysis.py` — DEFAULT_PERIOD
7. `auth/constants.py` (신설), `db.py`, `auth/jwt.py`, `tests/conftest.py`, `tests/test_me.py` — auth 상수

## 구현 체크리스트

- [x] 1. enum Literal 중복 제거 (schemas → trade_types import)
- [x] 2. BUY/SELL 및 enum 값 명명 상수화 + 호출처 치환
- [x] 3. KST / MS_PER_DAY → `trade_utils.py` 중앙화
- [x] 4. 에러 메시지 상수 (`errors.py`) 추가 + 라우터/auth 치환
- [x] 5. 외부 HTTP 상수 모듈 (`external/constants.py`) 신설 + 치환
- [x] 6. `DEFAULT_PERIOD` 상수 + `routers/analysis.py` 치환
- [x] 7. auth role / GUC 상수 (`auth/constants.py`) 신설 + 치환
- [x] 8. `poetry run ruff check api/` 통과
- [x] 9. `poetry run pytest api/tests` 통과

## 우려사항 / 리스크

- Pydantic `Literal` import 경로 변경 시 schemas → domain 단방향만 허용 (순환 import 방지)
- 에러 메시지 문자열 값 변경 금지 (상수 이름만 부여)
- 테스트 내 하드코딩 `"BUY"`/`"KR"` 등은 수정하지 않음 (auth role 관련 conftest 제외)
