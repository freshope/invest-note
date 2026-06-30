# 탈-Supabase Auth — 운영 cutover Runbook (B안: 심사-cutover 디커플)

Phase 2 BE 토큰-브로커로의 **운영 전환** 절차. 코드·마이그레이션·바이너리 출시는 완료(dormant)된 상태에서,
실제 전환을 **서버 플래그 flip**으로 수행한다. 순서 자체가 gapless(데이터 무손실)의 핵심이다.

> 운영 명령은 직접 실행하지 않고 제시·확인 후 사용자가 실행한다. DB 접근은 [project_prod_db_access].

## 0. 전제 (모두 충족돼야 시작)

- [x] 마이그레이션 `0004_auth_identities` / `0005_user_profiles` / `0006_auth_token_store` 운영 적용
- [x] secure-storage shell 바이너리(`app-v1.3.0_31`) 스토어 **승인·배포(LIVE)**
- [x] 라이브 바이너리에서 **디바이스 BE 로그인 1회 성공**(crypto.subtle S256 + secure storage round-trip)
- [x] BE dormant 코드 운영 배포 (auth 라우터 mount, flag default OFF)
- [x] IdP redirect URI 등록: `https://invest-note-api.pixelwave.app/auth/callback` (Google/Kakao/Apple, additive)
- [x] `api/.env.production` BE 블록 스테이징 (Coolify 미주입)
- [ ] **보급률** — 새 바이너리가 충분히 깔린 뒤 진행(저보급 시 검증표본 적고 구앱 신규가입 갭만 길어짐)

## 핵심 불변식 (왜 이 순서인가)

1. **`/auth/*` 라우터는 `BE_AUTH_ENABLED`를 무시한다** (플래그는 FE app-config 게이트일 뿐).
   `/auth/callback`을 기능 활성화하는 건 **Coolify에 signing key + provider secret이 존재하느냐**다.
   → BE env 주입은 **freeze + 백필 이후**에만.
2. **백필 importer는 insert-only** (`INSERT ... ON CONFLICT (provider, provider_id) DO NOTHING`).
   대상 `auth_identities`에 (provider, sub)가 이미 있으면 **틀린 user를 가리켜도 교정하지 않는다.**
   → 백필 시점 `auth_identities`는 **반드시 비어 있어야** 하고, 그 전에 **어떤 BE 로그인도 발생하면 안 된다**
   (런타임 신규생성 2b-3이 행을 남기면 백필이 불가역 오염 → 기존자 고아화).
3. **freeze가 백필보다 먼저** — 동결~export 사이 신규가입자가 생기면 매핑 없이 남아 고아화.

## 1. freeze — Supabase 신규가입 동결

Supabase 대시보드 → Authentication → **Allow new signups OFF** (클라우드가 SSOT, [project_supabase_oauth_only]).
기존 로그인은 유지, 신규 신원 생성만 거부.

## 2. export — 운영 Supabase → CSV 2개

`api/scripts/export_supabase_auth.sql`의 [1]·[2] 쿼리를 운영 Supabase에 실행(SQL Editor Download CSV 또는 psql `\copy`).
산출: `identities.csv`(provider, provider_id, user_id) / `users.csv`(user_id, email, display_name, avatar_url, email_verified, providers, last_sign_in_at).

> ⚠️ **Dashboard CSV 함정(실측 2026-06-26):** SQL Editor → Download CSV 는 NULL 을 빈값이 아닌 **문자열 `null`** 로
> 출력한다(`users.csv` 의 avatar_url/display_name/last_sign_in_at). 그대로 import 하면 `_opt_dt` 가
> `fromisoformat('null')` ValueError, `_opt_str` 은 `"null"` 문자열을 그대로 저장한다. → **import 전 standalone
> `null` 필드를 빈값으로 치환**하거나 처음부터 psql `\copy`(NULL=빈값)로 뽑을 것. `identities.csv` 는 영향 없음.
> (로컬 리허설은 `docker exec psql \copy` 라 이 함정이 안 보였다.) 치환 예:
> ```python
> import csv
> rows = list(csv.DictReader(open("users.csv")))
> for r in rows:
>     for k, v in r.items():
>         if v == "null": r[k] = ""
> w = csv.DictWriter(open("users.clean.csv","w",newline=""), fieldnames=rows[0].keys()); w.writeheader(); w.writerows(rows)
> ```

## 3. 선행 점검 (commit 전 필수)

```sql
-- (앱 DB) auth_identities 가 비어 있는가 — 불변식 #2. 0이어야 함.
SELECT count(*) FROM auth_identities;

-- (앱 DB) Supabase 신원 없는 public.users — 데모/직접 seed 계정 탐지([project_review_demo_account]).
-- 운영 export 의 user_id 집합과 비교. 있으면 백필 abort → cutover 전 정리하거나 export 에 수동 매핑 추가.
SELECT id FROM public.users
WHERE id NOT IN ( <identities.csv 의 user_id 목록> );
```

## 프로덕션 DB 접속 (4·5 공통, 실측 2026-06-26)

import 스크립트는 `get_settings().database_url` 을 쓰는데 `config.py` 가 `env_file=".env.local"`(로컬 :64340)
이라 **그냥 돌리면 로컬에 붙어 전원 orphan abort**(가드가 wrong-DB 를 잡아주는 안전망). prod PG 는 호스트포트
미publish([project_prod_db_access]) → **컨테이너 IP SSH 터널 + `DATABASE_URL` env override** 로 붙는다:

```bash
# ① VPS: prod PG(postgres:18-alpine, Coolify 컨테이너명 예: qx3w9lhb...) IP 확인
docker inspect -f '{{range .NetworkSettings.Networks}}{{.IPAddress}}{{end}}' <PG_CONTAINER>
# ② Mac: 터널 (이 터미널 열어둔 채)
ssh -N -L 5433:<PG_IP>:5432 root@vultr
# ③ Mac: 아래 4·5 실행 전 이 env 를 export (env var 가 .env.local 보다 우선 → prod 로 붙는다)
export DATABASE_URL='postgresql://invest_note_app:<PW>@127.0.0.1:5433/invest_note?sslmode=require'
```
> ⚠️ `<PW>` 는 `.env.production` 이 아니라([project_env_production_drift] drift 위험) **API 컨테이너
> `printenv DATABASE_URL` 의 진짜 DSN** 에서 가져온다. `sslmode=require` 는 터널 위에서도 OK(암호화만 요구,
> 호스트 검증 안 함 → 127.0.0.1 불일치 무관). dry-run 이 prod 에서 통과하면 그 자체가 "올바른 DB+coverage" 증명.
> (대안: API 컨테이너 `aipp48...`(/app)에 docker cp — 단 `scripts/` 는 이미지에 없고 `src/invest_note_api/services/`
> 만 있으니 래퍼를 `/app/scripts/` 에 cp 해야 sys.path `_API_SRC=/app/src` 가 맞는다.)

## 4. dry-run (profiles 먼저)

```bash
cd api   # 먼저 위 '프로덕션 DB 접속' 의 DATABASE_URL 을 export 했는지 확인
poetry run python scripts/import_user_profiles.py   users.csv      --dry-run   # export ⊆ public.users
poetry run python scripts/import_auth_identities.py identities.csv --dry-run   # public.users ⊆ export(coverage)
```
둘 다 통과해야 commit. (⚠️ identities dry-run은 INSERT를 건너뛰므로 FK/오염은 commit 시에만 드러남 → 불변식 #2 사전 확인이 그래서 중요)

## 5. commit (identities → profiles)

```bash
poetry run python scripts/import_auth_identities.py identities.csv --commit
poetry run python scripts/import_user_profiles.py   users.csv      --commit
```
검증: `auth_identities` distinct user_id == public.users 수, freshope 등 실 유저가 **자기 실제 sub로** 매핑됐는지 확인.

## 6. BE env 주입 (Coolify, 플래그는 아직 false)

`api/.env.production`의 BE 블록 값을 Coolify env에 주입([project_env_production_drift] — Coolify가 SSOT):
`BE_TOKEN_SIGNING_KEY`(운영 전용 ES256)·`BE_TOKEN_KID`·`BE_TOKEN_ISSUER`·`BE_TOKEN_AUDIENCE`(=`invest-note-app`, 비면 기동 실패)·
`BE_OAUTH_REDIRECT_BASE`(=`https://invest-note-api.pixelwave.app`)·`GOOGLE_*`·`KAKAO_*`·`APPLE_*`(.p8 포함).
**`BE_AUTH_ENABLED`은 아직 false 유지.**

## 7. flip — `BE_AUTH_ENABLED=true` (gapless 임계점)

Coolify env `BE_AUTH_ENABLED=true`. **반드시 5(백필) 완료 후**(hard precondition).
즉시·원자적으로 플러그인 보유 기기가 BE flow로 전환. 직후 **freshope 기기로 로그인 라운드트립 1회 확인.**
이상 시 즉시 `BE_AUTH_ENABLED=false`로 롤백.

## 롤백

- `BE_AUTH_ENABLED=false` → 클라이언트 즉시 Supabase flow 복귀.
- 필요 시 Supabase 신규가입 재허용(freeze 해제).
- 백필(auth_identities/user_profiles)은 additive라 원복 불필요(무해).
- ⚠️ flip~롤백 사이 BE flow로 가입한 진짜 신규는 앱DB-only → Supabase flow 로그인 불가(저트래픽 시 거의 0).

## cutover 후 상태

- 네이티브(새 바이너리) = BE 토큰-브로커 인증. 웹·구 바이너리·**어드민 패널** = Supabase(2c까지 공존).
- 기존자 데이터 보존(auth_identities sub→원래 UUID), flip 시 **1회 재로그인** 필요.
- 신규 가입: 새 바이너리는 BE 런타임 생성(2b-3), 구 바이너리는 막힘(2c force-update로 해소).
- Supabase 존속(default fallback + 웹). 물리 제거는 **2c**(force-update 양 스토어 승인 후, 비가역).

## 2c (별도, 신앱 안정 후)

force-update([project_force_update]) 양 스토어 승인 → Supabase default fallback 제거 · supabase-js 물리 제거 ·
`SUPABASE_*` env·`supabase/` 디렉토리·클라우드 정리 · 웹 BE flow 복구(딥링크 대체) · PIPA 고지.

> ⚠️ **어드민 패널은 2c에서 깨진다.** 어드민 로그인/토큰 획득은 전적으로 supabase-js 의존
> (`signInWithOAuth` → `getSession().access_token`)이라, supabase-js·`SUPABASE_*` env 제거 시
> 토큰 발급 경로가 사라져 모든 `/admin/*`가 401. **검증 경로는 무관** — 어드민은 일반 앱과 동일한
> `require_admin → get_current_user → decode_oidc_jwt`(+ `ADMIN_EMAILS` allowlist)를 공유하고,
> 발급(issuance)만 Supabase에 묶여 있다. **2c 전에** `admin/src/lib/auth/`(3파일)의 Supabase 구현을
> BE 토큰 플로우로 교체할 것(Supabase 결합이 이 디렉토리에 격리돼 있어 교체 면적은 좁음).

## 2c 실행 로그

순서: 게이트 확인 → **force-update bump**(구앱 sunset) → 전파 대기 → 재측정(legacy~0 게이트) → 가역 코드 제거 → 배포·소킹 → 비가역 클라우드 정리 → PIPA.
판정 지표: PostHog 활성 유저(최근 14일, person별 최신 native_build) 중 `legacy_supabase(<=30)` 비중. 빌드31(=app-v1.3.0~1.3.3, OTA web-only라 native_version 1.3.0 고정)이 BE flow 경계.

| 날짜 | 단계 | 결과 |
|------|------|------|
| 2026-06-29 | 게이트 확인 | 어드민 BE-auth 라이브 / 빌드31 양 스토어 출시 / store URL 양쪽·beAuthEnabled=true 운영 확인 |
| 2026-06-29 | 베이스라인 측정 | BE_flow(>=31) 70.0% · legacy(<=30) **26.2%(63명)** · unknown 3.8% → fallback 제거 no-go |
| 2026-06-29 | **force-update bump** | Coolify `MIN_SUPPORTED_VERSION 0.0.0→1.3.0` 적용·재배포, `/app-config` 반영 확인. 1.2.x 구앱(모두 force-gate 보유)에 강제 업데이트 시작 |
| 2026-06-29 (bump 직후) | 윈도우별 재측정 | legacy 비중 14d **26.2%(63명)** / 7d 2.1% / 4d 1.1% / 2d 0%. 활성 코어(2~4d)는 사실상 100% BE flow지만, 급감은 bump 효과가 아니라 **구앱 사용자가 최근 비활성**이기 때문(짧은 윈도우가 비활성 꼬리를 누락). 14d의 63명이 진짜 위험 모수(복귀 시 락아웃). bump 전파 더 필요 → **#1 배포 보류(사용자 판단), 코드만 완성** |
| 2c 코드 작업 | feature `feature/auth-2c-remove-supabase` | #1 BE fallback 제거 / #2 FE supabase-js 제거·웹 폐기 진행 중(spec `docs/spec-current.md`). 코드·테스트·독립 커밋까지만, 배포는 별도 게이트 |
| (대기) | 전파 재측정 후 배포 판단 | 며칠 후 7d/14d 재측정 → legacy 수렴 확인 시 #1 배포 **GO** 재판단 |

> ⚠️ #1(BE fallback 제거)의 **배포**만 legacy~0 게이트에 묶인다. #2(FE supabase-js 제거·웹 폐기)와 코드 작성 자체는 가역이라 게이트 전 진행 가능(배포만 보류).
> ⚠️ **force-update는 BE 진입을 차단하지 못한다(확인 2026-06-29):** `ForceUpdateGate`는 children 비차단 오버레이(layout.tsx 형제) + fail-open(app-config 미수신 시 통과)이라, 오버레이 뒤/장애 시 구앱이 Supabase 토큰으로 BE 호출을 계속한다 → #1 배포를 force-update만 믿고 당기면 안 된다.
> **게이트 정의 확정:** `legacy~0` = PostHog 측정 가능한 force-gate 보유 구앱(빌드 ≤30) 비중 ~0. force-gate 없는 초구버전(2026-05-26 이전 번들)은 통제·측정 불가 → **수용된 잔여 위험으로 게이트에서 제외(무시)**.

---
관련: `docs/spec-history/2026-06-20-auth-decoupling-phase2b3-2b4.md`(설계 원본), `_workspace/auth-phase2-design.md`, `docs/decisions.md`(2026-06-19~20).
