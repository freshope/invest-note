# admin/auth 위생 정리 — X-Admin-Token 트리거 인프라 제거 + BE-auth #3/#4

> 완료: 2026-07-01

> activation-register-flow 가 메인에서 `spec-current.md` 를 점유 중이라 충돌 회피용 별도 파일.
> 완료 후 `spec-history/2026-07-01-admin-auth-hygiene.md` 로 이동.

## 배경

두 백로그 항목을 응집된 "admin/auth 위생 정리"로 묶어 처리한다(코드 품질 라운드).

1. **미사용 admin 라우터 + ADMIN_TOKEN 인프라 제거** (backlog) — Coolify cron 이 CLI(`python -m ...stock_seed`/`nps_seed`)로만 seed 하고, `POST /admin/seed/*`·`/admin/reconcile/nps` HTTP 트리거는 호출되지 않음(admin FE·cron 모두 미사용 검증됨).
2. **어드민 BE-auth 코드리뷰 후속 #3/#4** (backlog) — 저severity 위생.

## ★ 백로그 서술 정정 (중요)

백로그는 "`routers/admin.py` **삭제** + `main.py` include 제거"라 했으나, 이는 **어드민 패널(2026-06-26 라이브)이 생기기 전 서술**이다. 현재 `admin.py` 에는 어드민 웹 패널 CRUD(`require_admin` = JWT+allowlist)가 **공존**한다. 파일을 지우면 어드민 패널이 죽는다.

→ **파일 삭제가 아니라 X-Admin-Token 트리거 인프라만 정밀 제거**한다. `main.py` 의 `include_router(admin.router)` 는 **유지**한다.

## 제거 / 보존 매트릭스 (코드 검증 완료)

### 제거

| 파일 | 제거 대상 |
|------|-----------|
| `api/src/invest_note_api/routers/admin.py` | 엔드포인트 4개: `trigger_seed_stocks`·`trigger_seed_nps`·`trigger_seed_daily_prices`·`trigger_reconcile_nps` / 래퍼 3개: `run_seed`·`run_seed_nps`·`run_seed_daily_prices` / 고아 import: `require_admin_token`·`BackgroundTasks`·`logging`+`logger`·`Settings`+`get_settings`·`seed`+`validate_seed_sources`·`seed_nps`+`reconcile_nps_unmatched`·`seed_daily_prices` |
| `api/src/invest_note_api/auth/admin.py` | `require_admin_token` 함수 + 전용 import `hmac`·`Header`·`Annotated` |
| `api/src/invest_note_api/config.py` | `admin_token: str = ""` 필드 + 주석 2줄 |
| `api/.env.example` | `ADMIN_TOKEN=` (line 177) + 주석 |
| `api/tests/test_stock_seed.py` | `require_admin_token` 섹션(`_admin_client`, `/admin/seed/stocks` 403/200 테스트) |
| `api/tests/test_nps_seed.py` | admin 토큰 섹션(`/admin/seed/nps`·`/admin/reconcile/nps` 테스트) |
| `api/tests/test_daily_price_seed.py` | `/admin/seed/daily-prices` 섹션 |

### 보존 (절대)

- 어드민 패널 CRUD 전부: `/stats`·`/user-growth`·`/me`·`/deletion-stats`·`/{table}`·`stocks PATCH`·`nps-unmatched` CRUD
- `require_admin` 함수 (auth/admin.py) + `ERR_FORBIDDEN`
- `config.py` `admin_emails`·`admin_email_set`
- `main.py` `include_router(admin.router)` (+ admin_board 선등록 순서)
- `services/daily_price_seed.py` `seed_daily_prices` 함수 — 호출처 없어져도 보존(백로그 명시, pre-warm 재활성 여지). **파일 자체 무수정**
- `services/stock_seed.py`·`nps_seed.py` CLI `__main__` 진입점 — cron 이 사용

### ★ /admin/reconcile/nps 제거 안전성 (검증됨)

`nps_seed.py` CLI `main()`(line 403)이 `seed_nps` **앞에서 `reconcile_nps_unmatched` 를 선행 호출**한다(docstring: "admin /seed/nps 래퍼와 동일 순서"). → 관리자가 `nps_unmatched.resolved_ticker` 를 채우면 **다음 nightly CLI seed 에서 자동 반영**되므로 HTTP 트리거 제거로 stranding 되지 않는다. 상실되는 것은 "즉시 반영" 편의뿐(다음 seed 대기 or CLI 수동 실행).

## 작업 단위

### 1. [BE] routers/admin.py — 트리거 제거
- 엔드포인트 4 + 래퍼 3 삭제, 고아 import 정리. 패널 CRUD·`require_admin` import 보존.
- verify: `pnpm`-무관. `poetry run pytest tests/test_admin*.py -q`(있으면) + import 에러 없음.
- 의존: 없음

### 2. [BE] auth/admin.py — require_admin_token 제거
- `require_admin_token` + `hmac`·`Header`·`Annotated` import 삭제. `require_admin` 보존.
- 의존: 1(admin.py 가 더 이상 import 안 함)

### 3. [BE] config.py + .env.example — admin_token 제거
- `admin_token` 필드·주석 삭제, `.env.example` `ADMIN_TOKEN=` 삭제. `admin_emails` 보존.
- 의존: 1,2

### 4. [BE] 테스트 절단
- 3개 파일에서 admin 트리거 섹션만 삭제(seed 서비스 테스트 보존). `admin_token=` 참조가 테스트 어디에도 안 남게(config 필드 제거 후 `Settings(admin_token=...)` 깨짐 방지).
- verify: `cd api && poetry run pytest -q` **전체 통과** — 특히 `require_admin` 패널 테스트 통과가 "패널 안 죽음" 가드.

### 5. [BE] #3 — 콜백 실패 generic 에러 페이지
- `routers/auth.py` `callback_get`/`callback_post`: `_handle_callback` 실패(APIError) 시 raw JSON 대신 **generic HTML 에러 페이지**(client 분기 없음, "로그인 실패 — 앱에서 다시 시도" 수준) 응답. 성공 시 RedirectResponse 유지.
- verify: 콜백에 잘못된 state → JSON 아닌 HTML 응답. 기존 성공 흐름 회귀 없음.
- 의존: 없음

### 6. [FE/admin] #4 — skip 재확인
- `admin` `signInWithGoogle` dormant-503 catch: **변경 없음**(env 미설정 시에만 발생 = dead, 배포 체크리스트 커버). skip 유지 근거만 확인. ✅

## ★ 스코프 경계 / 후속 (의식적 결정)

- **#3 은 `APIError` 만 잡는다** — state 만료/소비·미설정(401/400/503)은 HTML 로 통일하지만, IdP 토큰 교환 중 httpx 에러·`_handle_callback` DB 에러 등 **non-APIError 500 은 여전히 전역 핸들러의 JSON** 으로 나간다. 백로그 #3 이 지목한 "만료 state" 는 커버됨. broad-except 확대는 스코프 밖(advisor "minimal" 권고).
- **reconcile 선행 순서 회귀 가드 손실** — 제거한 `run_seed_nps` 테스트가 유일한 순서 검증이었고 CLI `main._run` 은 로컬함수+`Settings()`+`asyncio.run` 이라 구조상 테스트 곤란(기존에도 무테스트). reconcile **로직**은 `test_nps_seed.py` 서비스 테스트로 계속 보호. 순서 검증 미보강은 의식적 결정.
- **운영 후속(사용자 실행)**: Coolify prod env 의 `ADMIN_TOKEN` 제거 — `Settings(extra="ignore")` 라 **crash 없음**(harmless-stale), 위생 목적 선택. [[feedback_no_prod_command_execution]] 준수해 명령만 안내.

## 완료 조건
- [x] `cd api && poetry run pytest -q` 전체 통과 (944 passed, 패널 `test_admin_crud.py` 실행 테스트 포함)
- [x] `admin_token`/`ADMIN_TOKEN`/`require_admin_token` 잔여 참조 0 (코드·config·env·배포파일; docs 는 historical) + ruff 통과
- [x] 어드민 패널 CRUD·`require_admin`·`seed_daily_prices` 함수 무손상 (패널 테스트로 실증)
- [x] #3 콜백 실패 시 HTML 에러 페이지 (b11 테스트 assertion)
- [ ] (activation 머지 후) `docs/decisions.md` 에 트리거 제거 + reconcile 즉시반영 편의 상실 기록
