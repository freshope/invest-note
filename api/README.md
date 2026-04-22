# api — FastAPI Backend

Python(FastAPI) 백엔드.

- Supabase JWT 검증 미들웨어
- asyncpg 직접 연결 (트랜잭션 지원)
- 분석 로직 9개 + Next.js API Routes 16개 재작성 (진행 중)

## 로컬 실행

### 1. Python 3.12 + poetry 설치

```bash
# brew로 설치 (macOS)
brew install python@3.12 poetry

# 또는 pyenv
brew install pyenv
pyenv install 3.12
pyenv local 3.12  # api/ 디렉터리 내에서
```

### 2. 의존성 설치

```bash
cd api
poetry install
```

### 3. 환경변수 설정

```bash
cp .env.example .env.local
```

`.env.local` 파일을 열어 다음 값을 채웁니다:

- `SUPABASE_JWT_SECRET` — Supabase Dashboard → Project Settings → API → **JWT Secret** (anon key와 다름)
- `SUPABASE_URL` — `https://<ref>.supabase.co`

### 4. 서버 실행

```bash
PYTHONPATH=src poetry run uvicorn invest_note_api.main:create_app --factory --reload --port 8000

# 또는 Makefile 사용
make dev
```

### 5. 동작 확인

```bash
# 헬스체크
curl http://localhost:8000/healthz
# → {"status":"ok"}

# 인증 테스트 (브라우저 콘솔에서 토큰 추출)
# const { data: { session } } = await supabase.auth.getSession();
# session.access_token 값을 복사
curl -H "Authorization: Bearer <token>" http://localhost:8000/me
# → {"user_id":"<uuid>","email":"<email>"}
```

### 6. 테스트 실행

```bash
poetry run pytest
```

## 배포

Render + Railway (예정 — 라우트 포팅 완료 후 진행)
