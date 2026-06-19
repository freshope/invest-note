# Supabase Auth 종속성 제거 Phase 2a — expand 토대 (BE 토큰 검증 경로) 사양서

작성: 2026-06-19 | 근거: `_workspace/auth-phase2-design.md`(advisor 검토 완료 설계 노트), `_workspace/auth-decoupling-research.md`, `docs/spec-history/2026-06-19-auth-decoupling-phase1.md`(어댑터 토대), `docs/decisions.md`(2026-06-19 Auth Phase 1).

라이브러리(사용자 지정): **PyJWT**(BE 자체 토큰 비대칭 서명/검증 — 이미 `pyjwt[crypto]` 보유, 신규 0). **Authlib**(IdP OAuth/OIDC 중개)는 **Phase 2b 전용 — 2a에 도입하지 않는다.**

---

## 배경 / 목적

탈-Supabase의 마지막 축 Auth 를 "BE 가 토큰 발급 주체"가 되는 token-broker 모델로 옮기는 Phase 2 의 **첫 sub-phase(2a)**. 목표(사용자): "API 중심으로 구현하여 추후 IdP 교체에 백엔드 배포만으로 대응."

Phase 2 전체는 거대하고 위험(로그인 전면 재설계 + 구 앱 호환 + 데이터 손실 함정)하므로 **sub-phase 로 분할**하여 위험을 단계로 격리한다.

### Sub-phase 분할 (전체 개요)

| sub | 범위 | 위험 격리 |
|-----|------|----------|
| **2a (이 스펙)** | identity import 마이그레이션 + issuer registry 검증 확장 + BE 토큰 비대칭 서명/JWKS 서빙 | **구 앱 무영향(prod dormant).** 클라이언트는 BE 토큰을 발급받지 않음 — 검증 경로만 추가, 유닛테스트로만 가동. expand 의 토대. |
| 2b (개요) | OAuth 중개 flow(`/auth/login`→IdP→callback→딥링크 일회용 code→`/auth/token`) + refresh 토큰 BE 이관 + FE neutral `lib/auth` 전환(401→refresh→retry, 콜사이트 무변경) | 여기서부터 BE 토큰이 실제 발급·사용. Authlib·refresh 테이블은 2b 에서만 추가. |
| 2c (개요) | contract — 구 앱 sunset 후 Supabase 토큰 검증 제거 | force-update + **양 스토어 승인 후에만**([[project_force_update]]). |

→ **이 스펙은 2a 만 상세 분해.** 2b/2c 는 본 문서 말미 "후속 sub-phase 개요" 참조.

### 왜 2a 가 expand-safe 인가 (구현자 안전선 — 절대 넘지 말 것)

- 2a 는 **BE 토큰의 검증 경로만 추가**한다. **어떤 클라이언트도 BE 토큰을 발급받지 않는다**(실사용 발급 = OAuth 중개 = 2b).
- 따라서 2a 의 BE 토큰 경로는 prod 에서 **dormant** 이고 **유닛테스트로만** 검증된다.
- expand 단계는 Supabase 토큰 검증을 **절대 깨면 안 된다** — issuer registry 는 Supabase + BE 두 issuer 를 **둘 다** 검증한다. 구 앱(Supabase 토큰)은 무회귀.
- ⚠️ **2a 배포 위험(리더 지시) + 가드:** registry 도입 = 기존 Supabase 검증 경로가 registry 분기로 바뀐다. 하지만 registry 는 **2계층**(명시 BE 엔트리 + Supabase **default fallback, `oidc_issuer=""`→iss skip**)이라 2a 배포 시 실트래픽 100% 가 Phase 1 과 byte-for-byte 동일하게 fallback 검증된다. → **Supabase iss 문자열이 2a 에서 load-bearing 아님**(틀릴 iss 자체가 없음). iss 강제(Supabase 명시 엔트리 승격)는 **2a 이후 별도 활성화 단계**(A1 실측 후). 이게 2a 를 진짜 안전한 expand 로 만든다.

---

## 범위 (Scope)

**포함:**
- **마이그레이션(스키마):** `auth_identities` 매핑 테이블 `(provider, provider_id) → user_id` 생성(Alembic). 작성만, 적용은 사용자 confirm.
- **데이터 적재(인제스트):** Supabase `auth.identities` export → `auth_identities` 적재 스크립트 + rollback-guarded 검증. 작성만, 적용은 사용자 confirm. 운영자 export 가 선행 조건.
- **issuer registry:** `decode_oidc_jwt` 를 `iss` discriminator 기반 registry 로 확장 — Supabase issuer + BE issuer 각각 `{jwks_uri, issuer, audience}` 선택 후 검증. **per-issuer audience**(Supabase=`authenticated`, BE=별도 aud). 단일 글로벌 audience 금지.
- **Supabase iss 핀 활성화:** registry 가 iss 를 discriminator 로 쓰므로 `oidc_issuer` 가 더는 빈 값일 수 없음. 실제 iss 문자열 **경험적 확인**(blocking) 후 설정.
- **BE 토큰 서명:** ES256(또는 RS256) 비대칭 서명 발급 헬퍼 + BE 자체 JWKS 엔드포인트(`/.well-known/jwks.json` 류). 키 저장/회전/kid 결정.
- `conftest.make_jwt` 의 iss 핀 주입(기존 Supabase 경로 테스트 무회귀) + BE 토큰 발급/검증 유닛.
- `docs/decisions.md` 갱신(BE 서명 alg·키 관리·issuer registry·iss 핀 활성화 트레이드오프).

**제외 (명시적):**
- 2b 일체: OAuth 중개 라우터(`/auth/login`·callback·`/auth/token`), Authlib 도입, refresh 토큰 테이블·회전, FE `lib/auth` 전환·refresh 흡수, 딥링크 일회용 code.
- 2c 일체: Supabase 토큰 검증 제거, force-update 가드.
- **BE 토큰의 실사용 발급** — 2a 는 self-mint(테스트)만. 라우터로 노출하지 않는다.
- FE 변경 일체 — 2a 는 BE only.

## 가정 (Assumptions)

- BE 서명 알고리즘 = **ES256**(EC P-256). 짧은 키·빠른 서명. RS256 도 verifier 가 동일 경로(JWKS)로 흡수 가능하나 1차는 ES256 으로 고정(decisions 기록). 키는 env(`BE_TOKEN_SIGNING_KEY` PEM, `BE_TOKEN_KID`)에서 로드 — DB 저장 아님(2a 는 단일 키, 회전은 2b 에서 kid 다중화).
- BE issuer 문자열 = 우리가 정하는 안정 값(예: `https://api.invest-note...` 또는 설정값). Supabase issuer 와 충돌하지 않는 고유 문자열.
- Supabase issuer 문자열은 **코드 파생 추정값 `{supabase_url}/auth/v1`** 이나, **실제 access token 의 `iss` 클레임 디코드로 확정 전에는 prod 활성화 금지**(T1 참조).
- `auth.identities` export 는 운영자가 Supabase 대시보드/SQL 로 수행(외부 절차). 코드 태스크는 export 산출물(CSV/JSON)을 입력으로 가정.

---

## ⚠️ 최대 함정 체크리스트 (구현 전 필독)

| # | 함정 | 가드 |
|---|------|------|
| **P1 (HINGE — 2a 에서 중화됨)** | **iss 핀 잘못 설정 → 전 사용자 100% lockout.** Supabase 를 iss 강제 명시 엔트리로 올리면 실제 iss 와 정확 일치 필요(trailing slash/버전 하나 틀려도 전원 차단). | **2a 가드 = fail-safe fallback 설계(리더 지시):** 2a 는 `oidc_issuer=""` 유지 → Supabase 가 **default fallback(iss skip)** 이라 iss 문자열이 load-bearing 아님 → 잘못 설정할 iss 자체가 없음. lockout 위험은 **미래 "Supabase 명시 엔트리 승격(iss 강제)" 단계로 이동**. 그 단계의 blocking verify = 실제 token 디코드(A1)로 iss 정확 문자열 확인 후에만 활성화. registry 의 iss discriminator(peek)는 **선택용**일 뿐, 보안 경계는 per-issuer JWKS+aud. |
| **P2 (HINGE)** | **identity 매핑 없이 BE 토큰 발급 → 기존 데이터 전부 고아화(확실).** 새 IdP sub 로 새 user row 생성 시 trades/accounts/custom_tags 가 원래 UUID 에 묶여 고아. | `(provider, provider_id) → 기존 user UUID` 매핑이 **반드시 선행**. BE 토큰 `sub` = 원래 UUID. email 매칭 금지(fragile fallback, Kakao email optional). 적재 검증 = 카운트 매칭(아래 P3). **2a 는 발급 안 하지만 매핑 인프라를 먼저 깔아 2b 가 안전하게 올라타게 함.** |
| **P3** | identity 적재 누락/중복 → 일부 사용자만 고아화(부분 손실, 더 발견 어려움). ⚠️ **동수(==) 비교는 false rollback 함정**: `auth.identities` 는 user 당 다행 가능(Google+Apple 링크 → 행수 > 사용자 수), `public.users` 는 lazy provisioning(첫 authenticated 요청 시 생성, db.py:18-34)이라 미접속 가입자는 `auth.users` 에만 존재(`public.users` < `auth.users`). 동수 비교는 정상 데이터를 거부해 전체 적재를 막는다. | rollback-guarded 적재 검증(**동수 비교 금지**): ① **anti-orphaning(핵심 load-bearing):** `public.users` 의 **모든** `id` 가 `auth_identities` 에 ≥1 매핑(기존 앱 데이터 보유자 고아화 방지 — 유일한 핵심 가드) ② **완전성:** 적재 행수 = export 파일 행수(silent drop 없음) ③ `(provider, provider_id)` 유니크. 셋 다 통과 못 하면 **트랜잭션 롤백**. |
| **P4** | registry 가 Supabase 검증을 깨면 expand 가 아니라 즉시 lockout. | registry 는 **양쪽 issuer 검증**. 기존 Supabase 경로 테스트 전부 green 이 무회귀 gate. BE 토큰 추가는 신규 케이스로만. |
| **P5** | BE 토큰 HS256 사용 → verifier 가 대칭/비대칭 분기 필요(verifier 분기 = 설계 노트 금지). | **ES256/RS256 비대칭 + BE 자체 JWKS 서빙** → registry 가 BE 토큰을 Supabase 와 **동일 경로**(JWKS)로 검증. HS256 절대 금지. |
| **P6** | per-issuer audience 누락 → BE 토큰을 `aud="authenticated"` 로 검증하면 거부되거나, Supabase 토큰을 BE aud 로 검증하면 거부. | registry 항목별 `{jwks_uri, issuer, audience}`. Supabase aud=`authenticated`(`AUTH_ROLE`), BE aud=별도 값. dependency 가 단일 `oidc_audience` 주입하던 구조를 registry 선택으로 교체. |
| **P7** | iss 핀 켜는 순간 기존 테스트 토큰(iss 클레임 없음)이 전부 InvalidIssuer 로 깨짐. | Phase 1 이 추가한 `make_jwt(iss=...)` 활용 — conftest 기본 토큰에 핀된 Supabase iss 주입. 기존 auth 테스트 전체 green 확인이 verify. |
| **P8** | BE JWKS 엔드포인트가 auth 미들웨어보다 늦게 mount → BE 가 자기 토큰 검증 시 자기 JWKS 못 가져옴(순환). | JWKS 엔드포인트는 **무인증·공개** + auth 라우터보다 먼저 mount. `PyJWKClient` 캐시가 자기-HTTP fragility 흡수. verify 로 mount 순서/무인증 접근 확인. |

---

## BE 작업 단위 (api/) — 2a 상세 분해

### A1. [BE] Supabase `iss` 실측 — 미래 활성화 단계 입력 (코드/배포 블로커 아님)
- **코드 변경 아님 — 경험적 확인.** 실제 운영 Supabase access token 1건을 확보해 `iss` 클레임 정확 문자열 + header `alg` 를 디코드 확인한다(서명 미검증 디코드 또는 jwt.io).
- 결과를 `_workspace/01_planner_summary.md` 가정 섹션에 기록 → **iss 강제 활성화 단계(2a 이후 별도 단계)의 입력**. header `alg` 는 A5 의 `JWT_ALGORITHMS` 포함 검증에 사용.
- ⚠️ **2a 의 코드/배포 블로커 아님**: 2a registry 는 Supabase 를 `issuer=None`(iss skip) default fallback 으로 두므로(A4) 실측 iss 가 필요 없다. **이 단계는 미래 "Supabase 를 명시 엔트리로 승격"(iss 강제) 단계 + Q1 에만 필요.** 토큰 확보가 늦어도 2a 진행은 막히지 않는다.
- verify: 디코드한 iss 문자열·alg 가 기록됨 + `{supabase_url}/auth/v1` 파생값과 일치 여부 명시(불일치면 실측값 우선).
- 의존: 없음 (운영자/사용자 협조 — 토큰 1건 확보)

### A2. [BE] `auth_identities` 매핑 테이블 마이그레이션 (작성만, 적용 confirm)
- 신규 Alembic 리비전(`0004_auth_identities`, down_revision=`0003_board_tables`). 테이블:
  - `auth_identities(provider text, provider_id text, user_id uuid not null references users(id) on delete cascade, created_at timestamptz default now())`
  - PK 또는 UNIQUE `(provider, provider_id)`. index on `user_id`.
  - 소유자/role 은 [[project_migration_table_owner]] 규칙(앱 role `invest_note_app` 단일 실행) 준수.
- **upgrade/downgrade 양방향** 작성(downgrade 가 rollback guard 의 일부).
- ⚠️ **적용 금지** — `alembic upgrade` 는 사용자 confirm 후에만([[feedback_no_db_reset_without_confirm.md]] 정신). 스펙/태스크에 "작성만" 명시.
- verify: `cd api && poetry run alembic upgrade head --sql` (오프라인 SQL 생성으로 문법 검증, 실제 DB 미적용) + downgrade SQL 도 생성.
- 의존: 없음

### A3. [BE] `auth.identities` 적재 스크립트 + rollback-guarded 검증 (작성만, 적용 confirm)
- 신규 `api/scripts/import_auth_identities.py`: 운영자 export(CSV/JSON, `provider`·`provider_id`(또는 `identity_data.sub`)·`user_id`)를 읽어 `auth_identities` 에 적재.
- **단일 트랜잭션 + 검증 후 commit**(실패 시 rollback, P3). ⚠️ **동수(==) 비교 금지**(false rollback — P3 상세):
  - ① **anti-orphaning(핵심):** 적재 후 `public.users` 의 **모든** `id` 가 `auth_identities` 에 ≥1 매핑 보유. (기존 앱 데이터 보유자 고아화 방지 — 유일한 load-bearing 가드.)
  - ② **완전성:** 적재된 행수 = export 파일 행수(인제스트 중 silent drop 없음). ※ `auth.users`/`users` 수와의 동수 비교 아님.
  - ③ `(provider, provider_id)` 중복 없음(UNIQUE 위반 시 즉시 abort).
  - 세 검증 통과 못 하면 `ROLLBACK` + 명확한 실패 리포트 출력.
- **`provider_id` 컬럼은 Supabase `auth.identities.provider_id` 를 그대로 담는다**(provider 별 sub 의미 주석 명시): Google=OIDC sub, Kakao=Kakao 숫자 user id(2b userinfo `id` 와 일치해야), Apple=Service ID 재사용으로 sub 보존. 2b 런타임 매칭이 `(provider, IdP sub)` 로 조회하므로 의미가 어긋나면 재적재 필요.
- Apple = Supabase Service ID 재사용이므로 Apple identity 의 `provider_id`(sub)는 그대로 보존된다(설계 결정, 별도 변환 없음).
- ⚠️ **실행 금지** — 스크립트는 작성만, 운영 DB 적재는 사용자 confirm 후([[feedback_no_prod_command_execution.md]]). dry-run 모드(`--dry-run`: 검증만, commit 안 함) 기본 제공.
- verify: 합성 fixture(소량 export + 임시 sqlite/테스트 PG)로 ① 정상 적재 ② 카운트 불일치 시 rollback ③ 중복 시 abort 3케이스 유닛 — `cd api && poetry run pytest tests/test_import_auth_identities.py -q`
- 의존: A2 (테이블 스키마)

### A4. [BE] `auth/jwt.py` — 2계층 issuer registry 로 `decode_oidc_jwt` 확장 (fail-safe)
**핵심 설계(리더 지시): discriminator(peek) ≠ enforcement(iss 강제). 보안 경계는 per-issuer JWKS + per-issuer audience 이고, iss 강제는 defense-in-depth(2a 비활성).**
- `decode_oidc_jwt` 를 **2계층 registry** 로 확장:
  - **미검증 iss peek**: `jwt.decode(token, options={"verify_signature": False})` 로 `iss` 클레임만 먼저 읽어 **config 선택**(검증 아님).
  - **(1) 명시 엔트리** = iss 를 정확히 아는 issuer 만. **2a 에선 BE issuer 하나뿐**(우리가 mint → 문자열 확신). `{jwks_uri, issuer(강제), audience}` 전부 강제.
  - **(2) default fallback** = 명시 엔트리에 안 맞는 **모든** 토큰 → 현재 Supabase verifier(`jwks_uri=supabase`, `audience=AUTH_ROLE`, **`issuer=None`→iss skip**). ⚠️ **fallback 은 `InvalidTokenError` 거부가 아니다** — Phase 1 과 byte-for-byte 동일 검증.
  - 선택된 config 로 기존 검증(`_get_jwks_client` → `get_signing_key_from_jwt` → `jwt.decode(audience=, issuer=)`) 수행.
- → **2a 배포 시 실트래픽 100% = default = Phase 1 동일.** BE 엔트리는 유닛(A8)에서만 가동(dormant). **Supabase iss 문자열이 2a 에서 load-bearing 아님**(P1 중화).
- per-issuer audience(P6): Supabase=`AUTH_ROLE`, BE=별도.
- registry 구성은 `Settings` 에서 빌드(A5). `AuthenticatedUser` 반환 shape 무변경.
- ⚠️ rename/시그니처 변경 시 `dependency.py` 동기 갱신(A6) — A4 단독 verify 는 import 클린까지.
- verify: `cd api && python -c "import invest_note_api.auth.jwt"` (import 클린) + A8 에서 green.
- 의존: A5 (registry 설정 소스). **A1 의존 아님**(default fallback 이라 실측 iss 불요).

### A5. [BE] `config.py` — issuer registry 설정 + BE 토큰 서명 키
- `config.py`:
  - ⚠️ **`oidc_issuer` 는 Phase 1 빈 값(`""`) 그대로 유지 — 2a 에서 Supabase iss 핀 활성화 금지.** registry 의 Supabase default fallback 이 `issuer=None`(iss skip)으로 동작해야 하므로, 빈 값이 fail-safe 의 hinge. **iss 강제 활성화(Supabase 를 명시 엔트리로 승격)는 2a 이후 별도 단계**(A1 실측 + 별도 활성화). `supabase_audience`(=`AUTH_ROLE`, 기존 `oidc_audience`) 유지.
  - `be_token_issuer: str` 추가(BE 발급 토큰 iss — **유일한 명시 엔트리**). `be_token_audience: str` 추가(BE aud, Supabase 와 구분).
  - `be_token_signing_key: str`(ES256 PEM private key, env) + `be_token_kid: str`(JWKS kid).
  - `be_jwks_uri` 또는 BE issuer→jwks 매핑 property. registry 빌드 property(명시 엔트리=BE only + default=Supabase) 또는 dependency 조립.
  - ⚠️ `be_token_signing_key` 빈 값 처리: 2a dormant 이므로 빈 값 허용(없으면 명시 BE 엔트리 비활성 → 전 토큰 default fallback, Supabase 경로 무영향). fail-fast 는 2b(실사용)에서.
  - **`JWT_ALGORITHMS` 가 Supabase 광고 alg(A1 header `alg`) + BE alg(ES256) 둘 다 포함하는지 명시 검증**(한쪽 누락 시 해당 issuer 토큰이 조용히 거부됨, P5/P6 인접 함정).
- verify: `cd api && poetry run pytest tests/test_app_config.py -q`
- 의존: 없음 (`oidc_issuer` 빈 값 유지라 **A1 의존 아님**)

### A6. [BE] `auth/dependency.py` — registry 경유 검증으로 갱신
- `decode_oidc_jwt` 호출을 registry 기반 시그니처로 갱신(단일 `audience`/`issuer` 주입 → registry/settings 전달). except 절 동일(`InvalidTokenError` 등). ⚠️ **2a 는 unknown iss → 거부 아님, default(Supabase) fallback**(A4). 401 은 서명/aud 검증 실패 시에만. 기존 Supabase 경로가 default 로 그대로 통과하는지 확인.
- verify: `cd api && poetry run pytest tests/test_me.py -q` (기존 Supabase 경로 무회귀, P4·P7 — **테스트 무수정** 통과: 2a default 가 Phase 1 동일)
- 의존: A4, A5

### A7. [BE] `auth/be_token.py` 신규 — BE 토큰 ES256 서명/JWKS 서빙
- 신규 `api/src/invest_note_api/auth/be_token.py`:
  - `mint_be_token(sub: UUID, email: str | None, *, settings) -> str`: ES256 서명, `iss=be_token_issuer`, `aud=be_token_audience`, `sub=원래 UUID`, exp/iat, header `kid=be_token_kid`. **라우터 노출 금지(2a)** — 헬퍼/테스트 전용.
  - `build_be_jwks(settings) -> dict`: private key 에서 public JWK(EC, kid 포함) 생성.
- 신규 라우터 또는 기존 무인증 라우터(health 류)에 BE JWKS 엔드포인트 추가(예: `/auth/.well-known/jwks.json`). **무인증·공개, auth 라우터보다 먼저 mount**(P8). `be_token_signing_key` 빈 값이면 빈 keys(또는 404) — dormant 안전.
- verify: `cd api && poetry run pytest tests/test_be_token.py -q` (mint → build_be_jwks 의 public key 로 검증 round-trip 성공 + kid 일치)
- 의존: A5

### A8. [BE] issuer registry 통합 테스트 — Supabase + BE 양 issuer 검증
- ⚠️ **2a 는 default-fallback 모드(`oidc_issuer=""`)가 기본.** `conftest.make_jwt` 의 기존 토큰(iss 클레임 없음)은 **그대로 default fallback 으로 통과해야 함**(P7) — make_jwt 에 iss 강제 주입 금지, Phase 1 호출 무회귀.
- 신규 `tests/test_issuer_registry.py`(또는 test_me 확장). **2a default 모드 케이스(①~④):**
  - ① Supabase iss(또는 iss 없음) + 올바른 Supabase aud → 200(default fallback, Phase 1 무회귀).
  - ② BE iss + ES256(`mint_be_token`) + BE aud → 인증 성공(BE 명시 엔트리가 registry 로 검증, prod-dormant 경로 유닛 가동).
  - ③ **unknown iss(임의 문자열) + 유효 Supabase 서명/aud → 200**(default fallback). unknown iss + 잘못된 서명 → 401. ⚠️ "unknown→401" 은 default 모드에서 **틀림**(그건 활성화 모드 동작).
  - ④ aud 교차(Supabase iss + BE aud, 또는 BE iss + Supabase aud) → 401(per-issuer aud 격리, P6 — fallback 이어도 aud 는 강제).
  - **(참고) 활성화 모드 케이스(2a 비활성, 미래 단계 회귀 가드용으로만 작성·skip 또는 명시 분리):**
  - ⑤ `Settings(oidc_issuer=<실측 Supabase iss>)` 로 Supabase 를 명시 엔트리 승격 시: iss 불일치/iss 없음 → 401. **이건 활성화 모드 테스트로 명시 재분류** — 2a default 동작 아님.
  - 케이스는 `Settings(be_token_*=...)`/(⑤는 `oidc_issuer=...`) 별도 app 빌드(`_make_delete_client` 패턴) + `make_jwt(iss=...)`.
  - ⚠️ **BE iss 케이스는 자기 JWKS 를 HTTP fetch 못 함**(유닛 중 라이브 서버 없음): `PyJWKClient`/signing key 를 patch·주입(Phase 1 Supabase JWKS mock 패턴 재사용). **실제 self-fetch 도달성은 A8 아닌 Q4(엔드포인트 무인증 200) 책임.**
- verify: `cd api && poetry run pytest tests/test_issuer_registry.py tests/test_me.py tests/test_app_config.py -q`
- 의존: A4, A5, A6, A7

---

## QA 작업 단위 (단위별 분리 — addBlockedBy 로 즉시 unblock)

### Q1. [QA] A1 iss 문자열 경험적 확인 게이트
- 디코드한 Supabase iss 정확 문자열이 기록됐고, registry/fixture 가 이 값을 단일 출처로 쓰는지 확인(추정값 하드코딩 잔존 없음). P1 가드.
- 의존: A1

### Q2. [QA] identity 마이그레이션 + 적재 shape·rollback guard
- A2 스키마: `(provider, provider_id)` UNIQUE·`user_id` FK cascade·소유자 role 확인. upgrade/downgrade SQL 양방향 생성됨.
- A3 적재: dry-run 동작, 카운트 불일치/중복 시 rollback·abort(P3) 유닛 통과. email 매칭 코드 잔존 없음(P2).
- "작성만, 적용은 confirm" 명시가 스크립트/태스크에 박혀 있는지.
- 의존: A2, A3

### Q3. [QA] issuer registry fail-safe default + per-issuer aud
- A8 케이스 전부 green. **default-fallback 정확성(리더 지시 핵심):** Supabase/iss-없음/unknown-iss 토큰이 유효 서명·aud 면 200(P4·P7). **unknown iss → 거부 아님(fallback)** 확인 — "unknown→401" 박제 금지(이전 함정 정정).
- BE 토큰 ES256 round-trip(P5). aud 교차 401(P6). 활성화 모드(⑤) 케이스가 2a default 와 분리 명시됐는지.
- ⚠️ **`oidc_issuer=""` 유지 확인**(2a 에서 Supabase iss 핀 활성화 안 됨 — fail-safe hinge). 활성화돼 있으면 unsafe.
- grep 불변식: `decode_oidc_jwt` 가 2계층 registry 경유. HS256 심볼 없음. BE 토큰 mint 가 라우터 미노출(2a dormant).
- 의존: A6, A8

### Q4. [QA] BE JWKS 서빙 mount·무인증·dormant 안전
- JWKS 엔드포인트 무인증 접근 200, auth 라우터보다 먼저 mount(P8). `be_token_signing_key` 빈 값 시 Supabase 경로 무영향(dormant) 확인.
- 의존: A7

### Q5. [QA] 2a 최종 통합 게이트 — BE 전체 무회귀
- `cd api && poetry run pytest -q` 전체 green. 기존 Supabase 인증 100% 무회귀(expand-safe 입증).
- decisions.md 갱신 확인(D1). spec → spec-history 이동 준비.
- **DB 마이그레이션·적재 미적용 상태 명시**(사용자 confirm 대기).
- 의존: Q1, Q2, Q3, Q4, D1

---

## 정합성 / 문서

### D1. [DOC] `docs/decisions.md` — Phase 2a 결정 기록
- BE 서명 alg = ES256(트레이드오프: 짧은 키/빠름 vs RS256 호환성), 키 관리(env PEM 단일 키, 회전은 2b kid 다중화).
- **2계층 issuer registry**: discriminator(iss peek=선택) ≠ enforcement(iss 강제), 보안 경계 = per-issuer JWKS + per-issuer aud(별도 verifier 금지·동일 JWKS 경로). **명시 엔트리(BE only) + Supabase default fallback(`oidc_issuer=""`→iss skip).** ⚠️ **2a 는 Supabase iss 강제 비활성(fail-safe)** — Phase 1 `oidc_issuer=""` 유지. iss 강제(Supabase 명시 엔트리 승격)는 **별도 활성화 단계**(A1 실측 후, lockout 위험 격리). 트레이드오프: 2a 배포 무해 vs iss defense-in-depth 지연.
- identity import = `auth.identities` export 매핑(email 매칭 금지), Apple Service ID 재사용(sub 보존).
- verify: 파일 내용 확인
- 의존: A4, A5 (결정 확정 후)

---

## 의존 그래프 (2a 요약)

```
A5(config) ─┬→ A4(registry) ─┐
            │                 ├→ A6(dependency) ─┐
            └→ A7(BE token/JWKS) ─────────────────┤
A2(스키마) → A3(적재)                              ├→ A8(registry 테스트)
A1(iss 실측, 독립) ─ Q1                            │
QA: Q1←A1  Q2←A2,A3  Q3←A6,A8  Q4←A7  D1←A4,A5     │
                                       └→ Q5(최종 게이트)←Q1,Q2,Q3,Q4,D1
```
- ⚠️ **A1 은 2a 코드/배포 블로커 아님**(리더 fail-safe 지시). default fallback(`oidc_issuer=""`)이라 실측 iss 불요 — A4/A5 의 A1 의존 **제거**. A1 은 미래 iss 강제 활성화 단계 + Q1 입력으로만.
- A5 가 registry 라인 진입점(A4·A7 이 settings 소비).
- A2→A3(identity)는 registry 라인과 독립 → 병렬 가능.
- BE only. FE 변경 없음(2a).

## 완료 조건 (2a)

- [ ] A1 Supabase iss·alg 실측·기록 (미래 활성화 단계 입력 — 2a 코드/배포 블로커 아님)
- [ ] A2 매핑 테이블 마이그레이션 작성(적용은 confirm 대기)
- [ ] A3 적재 스크립트 + rollback guard 3케이스 통과(적용은 confirm 대기)
- [ ] A4~A8 모든 단위 verify 통과
- [ ] issuer registry green: **default fallback 정확성**(Supabase/iss-없음/unknown-iss → 유효 서명이면 200, **거부 아님**) + BE 명시 엔트리 검증 + aud 교차 거부 (P4·P5·P6·P7)
- [ ] **`oidc_issuer=""` 유지**(2a Supabase iss 핀 비활성 — fail-safe hinge). 활성화 모드 케이스는 2a default 와 분리 명시
- [ ] BE 전체 `poetry run pytest -q` 무회귀 (expand-safe, 테스트 무수정 통과)
- [ ] grep 불변식: HS256 없음 / email 매칭 없음 / BE 토큰 mint 라우터 미노출(dormant)
- [ ] `docs/decisions.md` 갱신 (D1)
- [ ] DB 마이그레이션·적재 미적용 상태 명시 + 사용자 confirm 대기
- [ ] spec → `spec-history/2026-06-19-auth-decoupling-phase2a.md` 이동 준비

---

## 외부 작업 (코드 아님 — 운영자 수행, 선행 조건/배포 절차)

| 작업 | 시점 | 비고 |
|------|------|------|
| Supabase access token 1건 확보(iss 디코드용) | A1 선행 | 실 사용자/리뷰어 계정 로그인 토큰. iss 클레임 확인용. |
| Supabase `auth.identities` export(CSV/JSON: provider, provider_id/sub, user_id) | A3 적재 선행 | 대시보드 SQL editor 또는 `auth.identities` SELECT. |
| `auth_identities` 마이그레이션 적용(`alembic upgrade`) | A2 후, 적재 전 | **사용자 confirm 필수.** |
| 적재 스크립트 실행(운영 DB) | A3 후 | **사용자 confirm 필수.** dry-run 선행. |
| BE 토큰 서명 키쌍(ES256 EC P-256) 생성 + env 주입(`BE_TOKEN_SIGNING_KEY`, `BE_TOKEN_KID`) | A7 사용 전 | 운영 Coolify env(SSOT, [[project_env_production_drift]]). 2a dormant 라 빈 값 허용. |
| (2b 선행) IdP 콘솔 redirect_uri 에 BE callback 추가(expand 동안 Supabase callback 과 **둘 다**) | 2b | Google/Kakao/Apple 각각. |
| (2b 선행) BE 로 OAuth client secret 이전(현재 Supabase 보유) + Apple client secret(서명 JWT) 생성 | 2b | Apple Service ID 재사용(sub 보존). |

---

## 후속 sub-phase 개요 (2b / 2c — 상세 분해는 별도 스펙)

### 2b — OAuth 중개 + FE 전환 + refresh (개요)
- **BE:** Authlib 도입(Google OIDC discovery / Kakao OAuth2+userinfo / Apple JWT-client-secret — 라이브러리 비균일 주의). `/auth/login?provider=` → IdP 리다이렉트(redirect_uri=BE) → callback: code 교환 + `(provider, sub)→UUID`(A2/A3 매핑 사용) + BE access/refresh 발급 → `app.pixelwave.investnote://auth/callback?code=<일회용>` 딥링크 → `/auth/token` 일회용 code→BE 토큰 교환. refresh 토큰 DB 저장·회전([[project_kis_rate_limits]] `kis_tokens` 패턴), `/auth/refresh`. BE 토큰 실사용 발급 시작 → `be_token_signing_key` fail-fast 활성화.
- **FE:** `lib/auth` 를 BE 토큰 모델로 전환 — `getAccessToken` 이 순수 getter 아니게(401→BE refresh→retry 흡수, 콜사이트 무변경). 딥링크 핸들러가 일회용 code→`/auth/token`. supabase-js 의존 축소.
- **함정:** Authlib 비균일, refresh 회전 경쟁, 딥링크 토큰 직접 노출 금지(일회용 code), Apple sub 연속성(Service ID 재사용 검증).

### 2c — contract (개요)
- registry 에서 Supabase issuer 제거(BE issuer 단독). supabase-js 완전 제거. **force-update 로 구 앱 sunset 후 + 양 스토어 승인 후에만**([[project_force_update]]). 양 스토어 라이브 바이너리 확인이 gate.
