# Spec: `body: dict` + `validate_body` 패턴 제거

> 완료: 2026-04-30

## 배경 / 문제

`api/src/invest_note_api/routers/{trades,accounts}.py`의 4개 엔드포인트가 `body: dict`로 raw 요청을 받은 뒤 `validate_body(Model, body)`로 수동 검증하는 보일러플레이트 패턴을 사용 중. FastAPI는 typed body 파라미터(`data: TradeCreate`)로 같은 검증을 자동 수행하므로, 헬퍼와 보일러플레이트를 모두 제거할 수 있다.

부수 효과: 검증 실패 시 status code가 `400` → `422`로 변경됨(FastAPI 표준 + 이미 `validation_error_handler`가 422로 응답하도록 등록되어 있음). 사용자가 422 전환을 승인.

## 목표

- 4개 엔드포인트가 typed body 파라미터로 검증을 받는다.
- `errors.validate_body` 함수와 `from invest_note_api.errors import ... validate_body` import가 코드베이스에서 완전히 제거된다.
- 검증 실패 응답은 `status=422` + `{"error": "메시지"}` 형식으로 일관 처리된다(메시지 추출 로직은 기존 `validation_error_handler`가 동일하게 수행).
- 기존 테스트가 422로 갱신되어 모두 통과한다 (`pnl/typing/lint` 회귀 없음).

## 설계

### 접근 방식

**1) 라우터 시그니처 변경** — 4곳 모두 `body: dict` → `data: <Model>`로 변경하고 함수 본문 내 `data = validate_body(...)` 줄을 삭제. 함수 내부의 사용 패턴(`data.attribute`, `data.model_dump(exclude_unset=True)`, `data.model_fields_set`)은 그대로 유지된다.

**2) `validate_body` 제거** — `api/src/invest_note_api/errors.py`에서 `validate_body` 함수와 `from pydantic import ... ValidationError` import 제거. `BaseModel` import는 다른 사용처가 없으면 같이 제거.

**3) 기존 `validation_error_handler` 활용** — `errors.py:33-36`에 이미 등록되어 있고, `RequestValidationError`를 422 + `{"error": first_msg}`로 변환. 별도 작업 불필요.

**4) 테스트 status 갱신** — `validate_body` 경유 검증 실패를 검증하던 테스트들을 422로 변경. 비-Pydantic 검증(예: `APIError("보유 수량 부족", 400)`)은 그대로 400 유지. 두 부류를 구분하기 위해 우선 코드 변경 후 `pytest`를 돌려 실패 케이스만 정확히 422로 갱신한다.

### 주요 변경 파일

- `api/src/invest_note_api/errors.py` — `validate_body` 제거, `ValidationError`/`BaseModel` import 정리
- `api/src/invest_note_api/routers/trades.py:131-137` (POST `/api/trades`) — `body: dict` → `data: TradeCreate`, `validate_body(...)` 줄 삭제, import에서 `validate_body` 제거
- `api/src/invest_note_api/routers/trades.py:260-272` (PATCH `/api/trades/{trade_id}`) — `body: dict` → `data: TradeUpdate`, `validate_body(...)` 줄 삭제
- `api/src/invest_note_api/routers/accounts.py:47-53` (POST `/api/accounts`) — `body: dict` → `data: AccountCreate`, `validate_body(...)` 줄 삭제, import에서 `validate_body` 제거
- `api/src/invest_note_api/routers/accounts.py:70-77` (PATCH `/api/accounts/{account_id}`) — `body: dict` → `data: AccountUpdate`, `validate_body(...)` 줄 삭제
- `api/tests/test_trades.py` — Pydantic 검증 실패 케이스(`test_invalid_body_400`, `test_create_future_trade_400`, `test_patch_free_text_5001_chars_400` 등 — pytest 실행 결과로 확정)를 422로 갱신
- `api/tests/test_accounts.py` — Pydantic 검증 실패 케이스(`test_create_account_empty_name`, `test_create_account_cash_balance_over_max`, line 218-225, `test_update_account_invalid_name_returns_400`)를 422로 갱신

## 구현 체크리스트

- [x] `errors.py`: `validate_body` 함수 + 미사용 import 제거 (`ValidationError`, `BaseModel`, `ERR_VALIDATION_FALLBACK` 모두 제거)
- [x] `routers/trades.py` POST: typed body 적용 + import 갱신
- [x] `routers/trades.py` PATCH: typed body 적용
- [x] `routers/accounts.py` POST: typed body 적용 + import 갱신
- [x] `routers/accounts.py` PATCH: typed body 적용
- [x] pytest 실행 → 실패 케이스 식별 (8개)
- [x] 식별된 Pydantic 검증 테스트 422로 갱신 + 함수명도 `_400` → `_422`로 변경
- [x] `cd api && poetry run pytest -q` 전체 실행 — 234 passed
- [x] `pnpm tsc` 프론트 타입체크 통과
- [x] `grep -rn "validate_body" api/src api/tests` → 출력 0줄 확인

## 검증 방법

1. **단위 테스트**: `cd api && poetry run pytest -q` — 전부 통과
2. **수동 호출**: 개발 서버 띄운 뒤 잘못된 body로 POST/PATCH 호출 → 422 + `{"error": "..."}` 응답 확인
   ```bash
   curl -X POST http://localhost:8000/api/accounts -H "Authorization: Bearer <token>" \
     -H "Content-Type: application/json" -d '{"name":"  "}'
   # 기대: HTTP 422, body {"error":"계좌 이름을 입력해주세요."}
   ```
3. **프론트엔드 회귀**: 계좌/거래 생성·수정 폼에서 일부러 빈 값/초과 값 입력 → 기존과 동일한 에러 메시지가 토스트에 표시되는지 확인 (`api-client.ts`가 `res.ok`로만 분기하므로 status 변경이 문구에 영향 없음)

## 우려사항 / 리스크

- **외부 API 계약 변경**: 4개 엔드포인트의 검증 실패 status가 400 → 422로 바뀜. 모바일/웹 앱은 동일 코드(`api-client.ts:res.ok`)를 사용하므로 영향 없음. 외부 컨슈머는 없음. 메시지 포맷(`{"error": "..."}`)은 동일.
- **테스트 분류 실수**: `assert status_code == 400` 중 비즈니스 로직 검증(`APIError(..., 400)`)과 Pydantic 검증을 혼동하면 잘못된 테스트를 422로 바꿀 위험. 코드 변경 후 pytest 실행으로 실패 케이스만 정확히 식별하는 절차로 방지.
- **응답 메시지 미세 차이 가능성**: `validate_body`는 `e.errors()[0]["msg"]`만 추출해 반환. `validation_error_handler`도 같은 패턴(`exc.errors()[0]["msg"]`). 동일하므로 메시지 변경 없음.
