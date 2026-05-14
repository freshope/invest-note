> 완료: 2026-04-22

# Spec: FastAPI 스켈레톤 + Supabase JWT 인증 (P1a)

## 배경 / 문제

모바일앱 배포 2단계 = **FastAPI 백엔드 분리** (전체 16개 라우트 + 14개 로직 파일 + 인증 + 컷오버). 단일 spec으로 진행하기엔 너무 커서 **3단계로 분할**:

| 단계 | 범위 |
|---|---|
| **P1a (이번 spec)** | FastAPI 스켈레톤 + Supabase JWT 검증 |
| P1b | accounts CRUD 5개 라우트 (asyncpg + Pydantic) |
| P2 | trades + portfolio + 시세 (8개 라우트, recalcGroupPnL 트랜잭션) |
| P3 | analysis 3종 + Next.js 컷오버 |

본 작업은 `api/` 디렉터리 안에서만 작업 — Next.js 동작은 변경 없음. 배포는 라우트가 어느 정도 포팅된 후속 단계에서 진행.

## 목표

- `api/` 에 FastAPI 프로젝트가 동작한다 (`poetry install` → `poetry run uvicorn ...`)
- `GET /healthz` 가 200을 반환한다 (인증 불필요)
- `GET /me` 가 `Authorization: Bearer <supabase_jwt>` 를 검증해 `{ user_id, email }` 을 반환한다
- 잘못된/만료된 토큰은 401을 반환한다
- CORS가 `http://localhost:3000` (Next.js dev)에 대해 허용된다
- pytest로 `/healthz`, `/me` (정상/401) 케이스를 검증한다

## 설계

### 접근 방식

- **인증 모델**: Bearer 토큰 — Next.js 클라이언트가 `supabase.auth.getSession()` 으로 JWT 추출 → `Authorization` 헤더로 전달. FastAPI는 Supabase HS256 secret으로 검증
- **DB 접근**: 본 단계 미연결. asyncpg 풀은 P1b(accounts)에서 도입
- **의존성**: `pyjwt[crypto]`, `pydantic-settings`, `httpx`, `pytest-asyncio`
- **인증 헬퍼**: `get_current_user` FastAPI dependency — Next.js `requireUser()` 와 1:1 대응
- **Python 버전**: 3.12

### 주요 변경 파일

- `api/pyproject.toml` — poetry 의존성 정의 (신규)
- `api/.python-version` — 3.12 (신규)
- `api/.gitignore` — Python 표준 (신규)
- `api/.env.example` — `SUPABASE_JWT_SECRET`, `SUPABASE_URL`, `CORS_ORIGINS` (신규, 커밋)
- `api/src/invest_note_api/main.py` — FastAPI 앱 + CORS + 라우터 등록 (신규)
- `api/src/invest_note_api/config.py` — pydantic-settings env 로딩 (신규)
- `api/src/invest_note_api/auth/jwt.py` — `decode_supabase_jwt`, `AuthenticatedUser` dataclass (신규)
- `api/src/invest_note_api/auth/dependency.py` — `get_current_user` Depends (신규)
- `api/src/invest_note_api/routers/health.py` — `/healthz` (신규)
- `api/src/invest_note_api/routers/me.py` — `/me` (신규)
- `api/tests/conftest.py` — `TestClient` fixture + 테스트용 JWT 헬퍼 (신규)
- `api/tests/test_health.py` — `/healthz` 200 (신규)
- `api/tests/test_me.py` — 헤더 없음/Bearer invalid/만료/정상 (신규)
- `api/README.md` — 로컬 실행 가이드 추가 (갱신)

## 구현 체크리스트

- [x] `api/pyproject.toml` + `.python-version` + `.gitignore` 작성
- [x] `poetry install` 로 lock 파일 생성
- [x] `api/.env.example` 작성
- [x] `config.py` (pydantic-settings)
- [x] `auth/jwt.py` (decode + AuthenticatedUser)
- [x] `auth/dependency.py` (get_current_user)
- [x] `routers/health.py`
- [x] `routers/me.py`
- [x] `main.py` (앱 + CORS + 라우터 등록)
- [x] `tests/conftest.py` (fixture + JWT 헬퍼)
- [x] `tests/test_health.py`
- [x] `tests/test_me.py` (4 케이스)
- [x] `poetry run pytest` 통과
- [x] `poetry run uvicorn invest_note_api.main:app --reload --port 8000` 로컬 기동 + `curl localhost:8000/healthz` 200 확인
- [x] 브라우저 콘솔 토큰 추출 → `curl -H "Authorization: Bearer <token>" localhost:8000/me` 정상 응답 확인
- [x] `api/README.md` 로컬 실행 가이드 추가

## 우려사항 / 리스크

- JWT Secret은 anon/publishable key와 다른 값 — `.env.local` 만 사용, `.env.example` 빈 값 유지
- Supabase 기본 HS256 가정. 향후 RS256 전환 시 `pyjwt.PyJWKClient` 로 교체 필요
- `allow_origins=["*"]` + `allow_credentials=True` 는 함께 쓸 수 없으니 명시적 origin 리스트 유지
- HTTPS dev 환경이면 `https://localhost:3000` 도 CORS origin에 포함 필요
- Python 3.12 미설치 시 `pyenv` 또는 `mise` 로 설치 필요
