# Spec: 어드민 패널 (admin/) 1차 증분

> 완료: 2026-06-18

## Context

운영자가 사용자·거래·종목·NPS 매칭 큐 등 DB 데이터를 웹에서 직접 확인/관리할 수단이 없다. 현재 어드민 기능은 FastAPI `/admin/seed/*`·`/admin/reconcile/nps` 4개 엔드포인트(정적 `X-Admin-Token`)뿐이고 UI가 없다. 루트에 **별도 Next.js 어드민 앱**을 추가해 Supabase Studio 스타일 레이아웃(사이드바+테이블 중심)으로 대시보드와 핵심 테이블 CRUD를 제공한다.

`/spec-start` 1차 증분이므로 모든 테이블을 한 번에 만들지 않고, 부트스트랩(레이아웃·인증·대시보드) + 핵심 테이블 서브셋만 구현하고 반복 가능한 per-table 패턴을 확립한다.

### 확정된 설계 결정 (사용자 확인 완료)
- **데이터 접근:** admin Next.js → FastAPI `/admin/*` CRUD → asyncpg. 직결 제너릭 에디터 X. 기존 검증/비즈니스 로직 재사용.
- **인증:** **기존 Supabase 인증 재사용** (app과 동일한 Supabase 구글 OAuth → JWT). 단, **Supabase 종속을 최소·격리**하여 추후 app과 함께 탈-Supabase 가능하게 설계. (NextAuth·정적 admin 토큰·BFF 도입 안 함.)
- **CRUD 범위:** 대시보드 + 핵심 서브셋부터.

## 목표 (완료 기준)

1. 루트 `admin/` Next.js 앱이 `pnpm -C admin dev`로 뜨고, Supabase 구글 로그인 → `ADMIN_EMAILS` allowlist 통과 → 어드민 셸 진입이 동작한다.
2. **시행 경계는 API**: allowlist에 없는 계정은 로그인돼도 모든 어드민 API에서 403. FE는 **클라이언트 가드**로 로그인 리다이렉트(미인증/비-admin이 SPA 정적 파일을 로드해도 데이터 호출이 전부 403).
3. 대시보드에서 주요 카운트(users/accounts/trades/stocks/nps_unmatched)가 표시된다.
4. 핵심 테이블 조회 + 운영 대상 테이블(아래 범위표) 편집/삭제 동작.
5. `pnpm -C admin exec tsc --noEmit` 통과, `cd api && poetry run pytest -q` 통과.

## 설계

### 인증 — 기존 Supabase JWT 재사용 (2-tier) + 종속 격리

```
브라우저(admin Next.js, Supabase JS 구글 OAuth)
   │   Authorization: Bearer <Supabase JWT>   (app과 동일 패턴)
   ▼
FastAPI /admin/*   ← require_admin = get_current_user + ADMIN_EMAILS allowlist
   ▼
Postgres (invest_note_admin BYPASSRLS pool)
```

- 어드민은 app처럼 같은 Supabase 프로젝트로 구글 로그인 → Bearer JWT를 FastAPI에 직접 전달. **NextAuth·정적 X-Admin-Token·서버 BFF 불필요.**
- FastAPI는 기존 `get_current_user`(JWKS 검증)를 **그대로 재사용**하고, 관문만 추가:

```python
# 신규: 기존 검증 위에 allowlist 게이트만. provider-neutral(email 클레임 기준).
async def require_admin(user = Depends(get_current_user), settings = Depends(get_settings)):
    if not user.email or user.email not in settings.admin_emails:
        raise APIError(ERR_FORBIDDEN, 403)
    return user
```

#### Supabase 종속 최소·격리 전략 (사용자 핵심 요구)
- **BE:** 어드민이 **새로운 Supabase 결합을 추가하지 않는다.** 기존 `get_current_user`/`decode_supabase_jwt`(`auth/jwt.py`)에 올라타고, 어드민 관문은 **provider-neutral `email` 클레임**만 본다. 추후 탈-Supabase 시 `auth/jwt.py` JWKS 소스 한 곳 교체로 app+admin 동시 전환.
- **FE:** 모든 Supabase 사용을 **단일 모듈 `admin/src/lib/auth/`** 뒤에 격리. provider-neutral 인터페이스(`signInWithGoogle()`, `getAccessToken()`, `getUser()`, `signOut()`, `subscribe()`)만 노출하고, 컴포넌트·api-client는 `@supabase/supabase-js`를 직접 import 하지 않는다 → 교체 시 이 모듈만 수정.
- **Env:** Supabase 전용 env는 한 그룹으로 묶고 주석 표기(`# --- Supabase Auth (추후 제거 대상) ---`)하여 제거가 기계적이게.
- 기존 `/admin/seed/*`·`/admin/reconcile/*`(정적 `X-Admin-Token`)는 **건드리지 않는다**(머신/운영 트리거 경로 유지). 신규 어드민 CRUD만 `require_admin` 사용. → FastAPI는 의도적으로 인증 3종(앱 JWT / 머신 X-Admin-Token / 어드민 JWT+allowlist) 공존. drift 아님.
- **라우트 가드 = 클라이언트 전용(UX), Next.js middleware 미사용.** app은 localStorage(PKCE) 세션 + `output:"export"`라 server/edge middleware가 토큰을 못 보고 export 하에선 실행도 안 됨. 쿠키 기반 `@supabase/ssr`+Node 런타임을 쓰면 격리 목표와 반대로 Supabase 결합이 늘어남 → admin은 **static-export SPA + 클라이언트 가드**로 가고, 실제 접근 차단은 API `require_admin`(403)이 담당.
- allowlist 키는 `email`(운영 친화) 사용. email은 가변이므로 필요 시 Supabase `sub`(UUID)로 교체 가능 — 의식적 선택.

### RLS 우회 (인증과 무관한 별개 landmine — 반드시 해소)

`trades`/`accounts`/`custom_tags`는 **FORCE ROW LEVEL SECURITY**. 앱 역할 `invest_note_app`은 비-superuser owner라 GUC 미주입 plain acquire 시에도 정책상 `current_user_id()=NULL` → **0행**. 어드민 cross-user 조회 불가.

- **Alembic 신규 revision**(부모=현재 head): `invest_note_admin` 역할 생성(`BYPASSRLS` + 필요한 GRANT). baseline 변경 금지.
- FastAPI에 **admin 전용 pool**(`invest_note_admin` 접속, `ADMIN_DATABASE_URL`) 추가. user-scoped 테이블 접근은 이 pool 사용.
- `ADMIN_DATABASE_URL` 미설정 시 admin CRUD 라우트는 명확한 에러(운영 SSOT는 Coolify env, [[project_env_production_drift.md]]).

### 1차 증분 CRUD 범위표

| 테이블 | 범위 | 비고 |
|--------|------|------|
| users | 읽기 전용 | Auth FK |
| accounts | 읽기 전용 | cross-user 가시성(admin pool) |
| trades | 읽기 전용 | PnL cascade 위험([[project_be_buy_meta_cascades_to_sell]]) — 쓰기는 후속 spec |
| custom_tags | 읽기 전용 | |
| stocks | 읽기 + 수정 | 글로벌 마스터, 삭제 제외 |
| nps_unmatched | 풀 CRUD | 기존 reconcile 큐, `resolved_ticker` 편집 |
| kis_tokens | 제외 | 시크릿 — 노출 금지 |

> user-scoped 쓰기를 1차에서 읽기 전용으로 둔 이유: trades 편집은 매칭 SELL 자동 갱신/PnL 재계산 cascade가 있어 raw row 편집이 무결성을 깬다. 안전한 쓰기는 비즈니스 로직 경유 후속 spec.

### 주요 변경/신규 파일

**BE (api/)**
- `api/alembic/versions/0002_admin_role.py` — `invest_note_admin` BYPASSRLS 역할 + GRANT (신규)
- `api/src/invest_note_api/auth/admin.py` — `require_admin`(get_current_user + allowlist) 추가
- `api/src/invest_note_api/config.py` — `admin_emails`, `admin_database_url`, CORS에 admin origin
- `api/src/invest_note_api/db.py` — admin pool 생성/획득 헬퍼(`acquire_admin`)
- `api/src/invest_note_api/main.py` — lifespan에서 admin pool 초기화
- `api/src/invest_note_api/routers/admin.py` — 핵심 테이블 list/CRUD 엔드포인트(`require_admin`, 페이지네이션·검색)
- `api/src/invest_note_api/db_ops/admin_repo.py` — admin pool 기반 read + nps_unmatched/stocks 쓰기 (신규)
- `api/src/invest_note_api/schemas/admin.py` — list/통계/응답 스키마 (신규)
- `api/tests/test_admin_crud.py` — allowlist 가드·비-admin 403·RLS 우회 조회·nps CRUD 회귀 (신규)

**Admin FE (admin/) — 신규 앱**
- `pnpm-workspace.yaml` — `packages`에 `"admin"` 추가
- `admin/package.json`,`tsconfig.json`,`next.config.ts`,`postcss.config.mjs`,`components.json`,`src/app/globals.css`
- `admin/src/lib/auth/` — **Supabase 격리 모듈**(provider-neutral 인터페이스). app `lib/supabase/client.ts`·`AuthProvider`·`getBearerHeader` 패턴 참고
- `admin/src/lib/api.ts` — FastAPI 클라이언트(`getAccessToken()`로 Bearer 주입)
- 클라이언트 가드(예: `(dash)/layout.tsx`에서 세션·allowlist 확인 후 리다이렉트) — **middleware.ts 미사용**(static-export SPA)
- `admin/src/app/layout.tsx` + `admin/src/components/layout/Sidebar.tsx`,`Topbar.tsx` — Supabase 스타일 셸(사이드바·다크 대응)
- `admin/src/app/login/page.tsx` + `admin/src/app/auth/callback/` — 구글 로그인/콜백
- `admin/src/app/(dash)/page.tsx` — 대시보드(카운트 카드)
- `admin/src/app/(dash)/<table>/page.tsx` — 테이블별 목록/상세(react-query + date-fns + lucide)
- `admin/src/components/base/*` — shadcn 래퍼(Button/Table/Dialog/Input/Select 등, AGENTS.md 규칙)
- `admin/src/components/providers/QueryProvider.tsx` — react-query
- `admin/.env.example` — Supabase env는 별도 그룹+주석(추후 제거 대상)

### 환경변수 (신규)
- BE: `ADMIN_EMAILS`(쉼표구분), `ADMIN_DATABASE_URL`, CORS에 admin origin
- Admin FE: `NEXT_PUBLIC_SUPABASE_URL`,`NEXT_PUBLIC_SUPABASE_ANON_KEY`(app과 동일 프로젝트 재사용, 격리 그룹), `NEXT_PUBLIC_API_BASE_URL`
- Supabase 대시보드에 admin 콜백 redirect URL 추가(예: `http://localhost:3001/auth/callback`) — auth 설정 SSOT는 대시보드([[project_supabase_oauth_only]])

## 구현 체크리스트

- [x] `admin/` Next.js 앱 스캐폴드(Next 16/React 19/Tailwind v4/shadcn new-york) + pnpm-workspace 등록
- [x] `admin/` static-export 설정(`output:"export"`, web-only, Capacitor 없음)
- [x] Supabase 격리 auth 모듈(`lib/auth/`) + 구글 로그인/콜백 + allowlist 클라이언트 가드(middleware 미사용)
- [x] Supabase 스타일 레이아웃 셸(Sidebar/Topbar) + base/ 래퍼 + QueryProvider
- [x] FastAPI 클라이언트(`lib/api.ts`, Bearer 주입)
- [x] BE `require_admin`(allowlist) + config(`admin_emails`,`admin_database_url`,CORS)
- [x] Alembic `0002_admin_role`(BYPASSRLS) + admin pool(`acquire_admin`) + lifespan 초기화
- [x] BE admin list/CRUD 엔드포인트 + admin_repo + 스키마 (범위표 준수)
- [x] 대시보드 카운트 페이지
- [x] 핵심 테이블 페이지: users/accounts/trades/custom_tags(읽기), stocks(읽기+수정), nps_unmatched(CRUD)
- [x] BE pytest(allowlist 403·RLS 우회 조회·nps CRUD) 통과
- [x] `pnpm -C admin exec tsc --noEmit` 통과

## 우려사항 / 리스크

- **사용자 풀 공유:** 어드민이 app과 같은 Supabase user pool. allowlist(`require_admin`)로 게이트 — 신뢰 도메인은 분리 안 됨(사용자 수용, 탈-Supabase 시 함께 정리).
- **RLS 우회 역할:** BYPASSRLS는 admin pool 한정, `require_admin` allowlist 게이트 뒤에서만 도달.
- **운영 env 드리프트**([[project_env_production_drift.md]]): `ADMIN_EMAILS`·`ADMIN_DATABASE_URL` 운영값은 Coolify SSOT. git `.env`로 디버깅 판단 금지.
- **trades 쓰기 보류:** 1차는 무결성 위험으로 user-scoped 쓰기 제외.
- 배포(Coolify admin 서비스)는 이번 증분 범위 밖 — 로컬 dev까지 검증.
- 제안 브랜치: `feature/admin-panel`.

## 검증 (end-to-end)

1. `pnpm -C admin dev` → admin 포트(예: 3001, app 3000과 충돌 회피) 접속 → 구글 로그인. allowlist 계정만 진입, 비-allowlist는 403/차단.
2. `cd api`에서 신규 Alembic revision 적용(`make migrate`), `ADMIN_EMAILS`·`ADMIN_DATABASE_URL` 설정 후 `make dev`.
3. 대시보드 카운트 표시. trades 페이지에서 **여러 사용자 행**이 보이는지(RLS 우회) 확인.
4. nps_unmatched에서 `resolved_ticker` 편집/삭제 반영 확인.
5. FE에서 `@supabase/supabase-js`를 import 하는 곳이 `lib/auth/` 한 곳뿐인지 확인(격리).
6. `cd api && poetry run pytest -q` · `pnpm -C admin exec tsc --noEmit` 통과.
