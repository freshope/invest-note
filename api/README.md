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

- `SUPABASE_URL` — `https://<ref>.supabase.co` (Supabase Dashboard → Project Settings → API)
- `DATABASE_URL` — Supabase Supavisor Session Pooler URL (IPv4 지원, port **5432**):
  ```
  postgresql://postgres.<project_ref>:<DB_PASSWORD>@aws-0-<region>.pooler.supabase.com:5432/postgres
  ```
  Dashboard → Project Settings → Database → Connection string (Session mode) 에서 확인.

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

# accounts 목록
curl -H "Authorization: Bearer <token>" http://localhost:8000/api/accounts
# → [{id, name, broker, cash_balance, trade_count, ...}, ...]

# accounts 생성
curl -i -X POST http://localhost:8000/api/accounts \
  -H "Authorization: Bearer <token>" -H "Content-Type: application/json" \
  -d '{"name":"테스트","broker":"키움","cash_balance":"1,000,000"}'
# → 201, {id, name, broker, cash_balance, ...}

# accounts 부분 수정
curl -i -X PATCH http://localhost:8000/api/accounts/<id> \
  -H "Authorization: Bearer <token>" -H "Content-Type: application/json" \
  -d '{"broker":"미래에셋"}'
# → 200, updated row (빈 body {} → 204)

# trade-count
curl -H "Authorization: Bearer <token>" http://localhost:8000/api/accounts/<id>/trade-count
# → {"count": 0}

# accounts 삭제 (거래 없는 계좌)
curl -i -X DELETE -H "Authorization: Bearer <token>" http://localhost:8000/api/accounts/<id>
# → 204 (거래 있으면 409)
```

### 6. 테스트 실행

```bash
poetry run pytest
```

## 배포

Render + Railway (예정 — 라우트 포팅 완료 후 진행)
