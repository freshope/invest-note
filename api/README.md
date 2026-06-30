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
# 브라우저 콘솔에서 Supabase JWT 추출
# const { data: { session } } = await supabase.auth.getSession();
# session.access_token 값을 복사
TOKEN="<your_supabase_jwt>"

# 헬스체크
curl http://localhost:8000/healthz
# → {"status":"ok"}

# 인증 확인
curl -H "Authorization: Bearer $TOKEN" http://localhost:8000/me
# → {"user_id":"<uuid>","email":"<email>"}
```

#### Accounts (P1b)

```bash
# 계좌 목록
curl -H "Authorization: Bearer $TOKEN" http://localhost:8000/v1/accounts

# 계좌 생성
curl -i -X POST http://localhost:8000/v1/accounts \
  -H "Authorization: Bearer $TOKEN" -H "Content-Type: application/json" \
  -d '{"name":"테스트","broker":"키움","cash_balance":"1,000,000"}'
# → 201

# 계좌 수정
curl -i -X PATCH "http://localhost:8000/v1/accounts/<id>" \
  -H "Authorization: Bearer $TOKEN" -H "Content-Type: application/json" \
  -d '{"broker":"미래에셋"}'
# → 200 (빈 body {} → 204)

# 계좌 삭제 (거래 없는 계좌)
curl -i -X DELETE -H "Authorization: Bearer $TOKEN" "http://localhost:8000/v1/accounts/<id>"
# → 204 (거래 있으면 409)

# 거래 수
curl -H "Authorization: Bearer $TOKEN" "http://localhost:8000/v1/accounts/<id>/trade-count"
# → {"count": 0}
```

#### Trades (P2)

```bash
# 거래 목록
curl -H "Authorization: Bearer $TOKEN" http://localhost:8000/v1/trades

# ticker + country 필터
curl -H "Authorization: Bearer $TOKEN" \
  "http://localhost:8000/v1/trades?ticker=005930&country=KR"

# 거래 생성 (BUY)
curl -i -X POST http://localhost:8000/v1/trades \
  -H "Authorization: Bearer $TOKEN" -H "Content-Type: application/json" \
  -d '{
    "trade_type": "BUY",
    "market_type": "STOCK",
    "account_id": "<account_id>",
    "asset_name": "삼성전자",
    "ticker_symbol": "005930",
    "country_code": "KR",
    "exchange": "KOSPI",
    "traded_at": "2026-04-22T10:00:00",
    "price": 70000,
    "quantity": 10,
    "commission": 0,
    "tax": 0
  }'
# → 201, {id, trade_type, ...}

# 거래 단건 조회
curl -H "Authorization: Bearer $TOKEN" "http://localhost:8000/v1/trades/<trade_id>"

# 거래 수정 (PnL 영향 필드 포함 시 recalc 실행)
curl -i -X PATCH "http://localhost:8000/v1/trades/<trade_id>" \
  -H "Authorization: Bearer $TOKEN" -H "Content-Type: application/json" \
  -d '{"price": 71000}'
# → 204

# 거래 삭제
curl -i -X DELETE -H "Authorization: Bearer $TOKEN" "http://localhost:8000/v1/trades/<trade_id>"
# → 204

# 매도 거래 요약 (PnL + 보유일 + 전략 평가)
curl -H "Authorization: Bearer $TOKEN" \
  "http://localhost:8000/v1/trades/<sell_trade_id>/summary"
# → {pnl, result, holdingDays, strategyEvaluation, breakdown}
```

#### Portfolio (P2)

```bash
# 보유 수량 조회
curl -H "Authorization: Bearer $TOKEN" \
  "http://localhost:8000/v1/portfolio/holding?accountId=<id>&assetName=삼성전자&ticker=005930&country=KR"
# → {quantity, avgBuyPrice}

# 포트폴리오 요약 (positions + snapshots + totals + 실시간 시세)
curl -H "Authorization: Bearer $TOKEN" http://localhost:8000/v1/portfolio/summary
# → {totals, positions, snapshots, hasAccounts, hasTrades}
```

#### Stocks (P2)

```bash
# 시세 조회 (복수 가능, KR/US 혼합)
curl -H "Authorization: Bearer $TOKEN" \
  "http://localhost:8000/v1/stocks/quote?symbols=005930:KR,AAPL:US"
# → {"005930:KR": {price, currency, as_of}, "AAPL:US": {price, currency, as_of}}

# 종목 검색 (한글/종목코드 → KR, 영문 → US)
curl -H "Authorization: Bearer $TOKEN" \
  "http://localhost:8000/v1/stocks/search?q=삼성"
# → [{code, name, market, exchange}, ...]

curl -H "Authorization: Bearer $TOKEN" \
  "http://localhost:8000/v1/stocks/search?q=apple"
# → [{code, name, market, exchange}, ...]

# Analysis (period: 1m | 3m | 6m | ytd | all)
curl -H "Authorization: Bearer $TOKEN" \
  "http://localhost:8000/v1/analysis/dashboard?period=3m"
# → {
#   period,
#   summary:     {totalTrades, sellTrades, winRate, totalProfitLoss, byStrategy[], byEmotion[], byTag[], ...},
#   behavior:    {profile:{tempo,...}, inputRates, holdingPeriodDist[], positionSizeDist[], concentration},
#   suggestions: {suggestions:[{id, severity, title, body, metric?, linkSection?}]},
# }
```

### 6. 테스트 실행

```bash
poetry run pytest
```

## 마이그레이션 (Alembic)

스키마 마이그레이션은 Alembic(`api/alembic`)이 단일 소유한다. supabase 는 Auth(GoTrue) 전용.

- 적용: `make migrate` (= `poetry run alembic upgrade head`)
- 새 마이그레이션: `make migrate-new name="add xxx"` → 생성된 `alembic/versions/*.py` 의 `upgrade()` 에 `op.execute("...")` 로 raw SQL 작성 → `make migrate` (ORM/autogenerate 미사용)
- 연결 URL: `MIGRATION_DATABASE_URL`(없으면 `DATABASE_URL`). **superuser + direct 5432** 필요(`pg_trgm`·role 조작) — `.env.local` 에 설정. 앱 role `invest_note_app` 은 NOSUPERUSER 라 마이그레이션 불가.
- 신규/빈 DB 는 baseline 적용 **전** `invest_note_app` 역할을 먼저 생성해야 한다(스키마 밖 부트스트랩). 운영 DB 는 호스트 포트 미publish 라 `docker exec` 컨텍스트에서 실행.

## 배포

Coolify (self-hosted) — `api.invest-note.pixelwave.app`
