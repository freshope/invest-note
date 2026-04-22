# Spec: FastAPI accounts CRUD (P1b)

## 배경 / 문제

P1a에서 FastAPI 스켈레톤과 Supabase JWT(ES256/JWKS) 인증까지 구현 완료. 이제 첫 도메인 라우터로 accounts CRUD를 포팅해 FastAPI가 실제 DB와 연결되는 구조를 만든다. asyncpg 풀을 도입하고, Supabase의 기존 RLS policy를 재활용해 권한 격리를 처리한다. Next.js 프론트 컷오버와 배포는 본 단계 범위 밖 (P2/P3).

## 목표

- asyncpg 풀이 FastAPI lifespan에서 생성·해제된다 (statement_cache_size=0)
- `acquire_for_user(pool, user_id)`가 transaction 내부에서 `SET LOCAL role = 'authenticated'` + `request.jwt.claims` 주입으로 RLS를 활성화한다
- 5개 엔드포인트가 동작한다:
  - `GET /api/accounts` — 목록 + 각 계좌의 `trade_count`
  - `POST /api/accounts` — 계좌 생성 (201)
  - `PATCH /api/accounts/{id}` — 부분 업데이트 (빈 body 204, 404)
  - `DELETE /api/accounts/{id}` — 삭제 (trades 존재 시 409, 204)
  - `GET /api/accounts/{id}/trade-count` — 거래 수 조회
- 에러 응답이 `{"error": "<메시지>"}` 포맷으로 통일된다 (Next.js 호환)
- Pydantic 스키마가 Next.js zod 스키마와 등가로 검증한다 (name trim/max50, broker nullable/empty→null, cash_balance 쉼표 허용/상한)
- pytest가 라우트 주요 경로를 FakePool로 검증하고 전체 통과한다
- 다른 유저의 계좌 id로 접근 시 RLS가 자동 차단 (404)

## 설계

### 접근 방식

1. **DB 접근**: asyncpg 풀 + Supabase Supavisor transaction pooler. `statement_cache_size=0` 필수
2. **권한**: Next.js RLS 재활용. `acquire_for_user()`가 transaction 내부에서 JWT claims를 GUC로 주입 → `auth.uid()`가 올바르게 동작 → policy(`auth.uid() = user_id`)가 자동 적용
3. **에러 포맷**: `APIError` 예외 + 전역 핸들러로 `{"error": msg}` 변환. FastAPI 내장 `HTTPException` 사용 중단. dependency.py의 401도 `APIError`로 교체
4. **검증**: Pydantic `field_validator(mode="before")`로 zod transform 재현. `AccountUpdate.model_fields_set`으로 "빈 body 204" 판별
5. **테스트**: `FakePool` / `FakeConnection` 클래스로 asyncpg 인터페이스 mock (`SET LOCAL` / `set_config` 호출은 no-op). `dependency_overrides`로 주입

### 주요 변경 파일

- `api/pyproject.toml` — `asyncpg = "^0.30"` 의존성 추가
- `api/.env.example` — `DATABASE_URL=` 템플릿 (Supabase pooler URL 주석 예시)
- `api/src/invest_note_api/config.py` — `database_url: str` 필드 추가
- `api/src/invest_note_api/errors.py` (신규) — `APIError` + `api_error_handler`
- `api/src/invest_note_api/auth/dependency.py` — `HTTPException` → `APIError`
- `api/src/invest_note_api/db.py` (신규) — `create_pool`, `get_pool`, `acquire_for_user`
- `api/src/invest_note_api/schemas/account.py` (신규) — `AccountCreate`, `AccountUpdate`
- `api/src/invest_note_api/main.py` — `lifespan(pool)` + 핸들러 등록 + accounts 라우터 등록
- `api/src/invest_note_api/routers/accounts.py` (신규) — 5개 엔드포인트
- `api/tests/fake_pool.py` (신규) — FakePool/FakeConnection
- `api/tests/conftest.py` — pool override fixture 추가
- `api/tests/test_accounts.py` (신규) — 5개 라우트 케이스
- `api/README.md` — DB 설정 + 5개 엔드포인트 curl 예시

## 구현 체크리스트

- [ ] `api/pyproject.toml`에 `asyncpg` 추가 + `poetry lock --no-update`
- [ ] `api/.env.example`에 `DATABASE_URL=` 템플릿 추가
- [ ] `api/src/invest_note_api/config.py`에 `database_url` 필드 추가
- [ ] `api/src/invest_note_api/errors.py` 작성 (APIError + 전역 핸들러)
- [ ] `api/src/invest_note_api/auth/dependency.py` HTTPException → APIError 교체
- [ ] `api/src/invest_note_api/db.py` 작성 (pool, get_pool, acquire_for_user)
- [ ] `api/src/invest_note_api/schemas/account.py` 작성 (AccountCreate, AccountUpdate)
- [ ] `api/src/invest_note_api/main.py` — lifespan + handler + router 등록
- [ ] `api/src/invest_note_api/routers/accounts.py` — 5개 엔드포인트 구현
- [ ] `api/tests/fake_pool.py` 작성
- [ ] `api/tests/conftest.py` — pool override fixture 추가
- [ ] `api/tests/test_accounts.py` — 5개 라우트 핵심 케이스
- [ ] `poetry run pytest` 전체 통과
- [ ] `api/README.md` — DB 설정 + curl 예시 갱신
- [ ] 로컬 기동 (`uvicorn`) + 5개 엔드포인트 curl 검증
- [ ] RLS 격리 검증 (다른 유저의 계좌 id로 404 확인)

## 우려사항 / 리스크

- **Supavisor transaction mode + asyncpg**: `statement_cache_size=0` 필수. 누락 시 prepared statement 에러
- **`SET LOCAL` 누수**: 반드시 transaction 내부에서만. `acquire_for_user`가 `conn.transaction()` 블록을 감싸 자동 리셋 보장
- **`auth.uid()` 의존**: Supabase 내장 함수 (001 migration에 이미 존재). 순수 Postgres 환경에서는 동작 안 함 (MVP 수용)
- **RLS가 row 숨길 때 404 통일**: 존재X와 남의 계좌를 구분하지 않음 (유저 존재 여부 누출 방지)
- **DATABASE_URL 평문 password**: `.env.local`은 gitignored (`.gitignore`에서 `!.env.example`만 예외)
- **PATCH 동적 SQL 인젝션**: 컬럼명은 `{"name", "broker", "cash_balance"}` 화이트리스트, 값은 파라미터 바인딩
- **broker null vs omitted**: `model_fields_set`으로 구분. 프론트 실제 payload 향후 UI 검증 시 재확인
- **Decimal → float 변환**: 상한 9999999999999999.99는 double 표현 한계 근처이나 현재 표시 규모는 안전
