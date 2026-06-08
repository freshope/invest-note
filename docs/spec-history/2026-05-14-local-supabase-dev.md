> 완료: 2026-05-14

# Spec: 로컬 Supabase 개발 환경 도입

## 배경 / 문제

현재 BE/FE의 `.env.local`이 클라우드 Supabase(`phynizbvzzsvprawxkvd.supabase.co`)를 가리키고 있어, 로컬 개발이 운영 DB·Auth와 직접 연결된다. 결과적으로 (1) 인터넷·운영 인프라 의존, (2) 마이그레이션 검증을 운영에서 수행해야 하는 위험, (3) 테스트 데이터가 운영과 섞이는 문제가 발생한다.

`supabase/` 디렉터리에 `config.toml`과 17개 마이그레이션이 이미 존재하고 Supabase CLI 2.98.2가 설치되어 있으므로, 로컬 Supabase 스택(`supabase start`)으로 전환할 수 있는 토대가 있다. 본 작업은 BE/FE의 dev 환경을 로컬 Supabase로 전환한다.

## 목표

- `supabase start` → BE → FE(`pnpm -C fe dev`) 순서로 실행하면 클라우드 Supabase 없이 로컬에서 회원가입·로그인·계좌/거래 CRUD가 정상 동작한다.
- BE의 JWT 검증 코드(`auth/jwt.py`)는 변경 없이 로컬 Supabase가 발급한 ES256 JWT를 검증할 수 있다.
- 클라우드 환경 영향 없음 (`.env.production`, `ci.yml`, 운영 코드 경로 동일).

## 설계

### 접근 방식

1. **JWT 알고리즘 호환**: 로컬 Supabase에 ES256 비대칭 서명 키를 활성화한다. `supabase gen signing-key --algorithm ES256`으로 키 페어를 생성하고 `config.toml`의 `[auth].signing_keys_path`에 등록한다.
2. **환경변수 전환**: BE/FE의 `.env.local`을 로컬 Supabase 엔드포인트(`http://127.0.0.1:64321`, `postgresql://postgres:postgres@127.0.0.1:64322/postgres`)로 갱신한다. 클라우드 값은 이미 `.env.production`에 보존되어 있어 별도 백업 불필요.
3. **포트 충돌 회피**: 다른 Supabase 프로젝트가 기본 포트(54321 대역)를 점유 중이라 invest-note는 64321 대역으로 운영 (API 64321 / DB 64322 / Studio 64323 / Inbucket 64324 / Analytics 64327 / Pooler 64329 / shadow 64320).
4. **시크릿 격리**: `signing_keys.json`은 비공개 키를 포함하므로 `supabase/.gitignore`에 추가한다.
5. **시드 데이터**: 만들지 않는다. FE 회원가입 또는 Supabase Studio에서 수동 생성.

### 주요 변경 파일

- `supabase/signing_keys.json` (신규, git 추적 안 함)
- `supabase/.gitignore` — `signing_keys.json` 추가, `.env` 제외 + `!.env.example` 예외
- `supabase/config.toml` — `[auth].signing_keys_path` 활성화, 포트 64321 대역, Google/Kakao OAuth provider 추가
- `supabase/.env.example` (신규) — OAuth credentials 가이드
- `supabase/.env` (신규, gitignored) — OAuth credentials placeholder
- `be/.env.local`, `be/.env.example`
- `fe/.env.local`, `fe/.env.example`
- `docs/decisions.md`

### 변경하지 않는 항목

- `be/src/invest_note_api/auth/jwt.py`, `auth/constants.py`, `db.py`
- `fe/src/lib/supabase/client.ts`
- `.env.production` (BE/FE)
- `.github/workflows/ci.yml`

## 구현 체크리스트

- [x] `supabase gen signing-key --algorithm ES256` → `supabase/signing_keys.json` 생성
- [x] `supabase/.gitignore`에 `signing_keys.json` 추가
- [x] `supabase/config.toml`의 `[auth].signing_keys_path` 활성화
- [x] `supabase start` → 17개 마이그레이션 자동 적용 + 로컬 스택 기동
- [x] `supabase status -o env` 결과에서 anon/service_role 키 확보
- [x] `be/.env.local` 갱신
- [x] `be/.env.example` 갱신
- [x] `fe/.env.local` 갱신
- [x] `fe/.env.example` 갱신
- [x] `docs/decisions.md`에 결정 기록
- [x] BE: `/healthz` 200 확인
- [x] FE: 회원가입 → 로그인 → `/me` 200 확인
- [x] 타입 체크: `pnpm -C fe exec tsc --noEmit`
- [x] BE 테스트: `cd be && poetry run pytest -q`

## OAuth 보강 (2026-05-14)

로컬 Supabase 는 Google/Kakao OAuth 를 별도 선언 필요 (클라우드 Dashboard 설정은 미반영).

- `supabase/config.toml` — `[auth.external.google]`, `[auth.external.kakao]` 추가, `redirect_uri = "http://127.0.0.1:64321/auth/v1/callback"` 명시.
- `supabase/.env` (gitignored) — credentials 환경변수 placeholder.
- `supabase/.env.example` — 사용법/redirect URI 등록 절차.
- `supabase/.gitignore` — `.env` 무시 + `!.env.example` 예외.

**사용자 후속 작업:**
1. `supabase/.env` 에 실제 Google/Kakao OAuth credentials 입력 (클라우드 Dashboard 에 등록된 값과 동일하게 재사용 가능).
2. Google Cloud Console / Kakao Developers 의 OAuth redirect URI 화이트리스트에 `http://127.0.0.1:64321/auth/v1/callback` 추가.
3. `supabase stop && supabase start`.

## CORS 보강 (2026-05-14)

FE 를 `http://127.0.0.1:3000` 으로 접속하는 케이스 대응. `be/.env.local` 의 `CORS_ORIGINS` 에 `http://127.0.0.1:3000` 와 `https://127.0.0.1:3000` 추가. `--reload` uvicorn 은 `.env.local` 변경을 자동 감지하지 않으므로 BE 프로세스 재시작이 필요하다.

## 우려사항 / 리스크

- 로컬 Supabase 첫 시작 시 Docker 이미지 다운로드 오래 걸림 (1회만).
- 로컬 Auth 사용자는 비어있어 회원가입 다시 필요 (의도된 격리).
- 클라우드 전환 필요 시: `cp be/.env.production be/.env.local && cp fe/.env.production fe/.env.local`.
- OAuth credentials 미입력 상태에서 SNS 로그인 시도 → "로그인 중 오류가 발생했습니다" (Google/Kakao 가 dummy/빈 client_id 거부).
- BE Settings 가 `@lru_cache` 로 캐시되어 `.env.local` 변경 시 BE 프로세스 재시작 필요 (uvicorn `--reload` 는 `.py` 만 감지).
