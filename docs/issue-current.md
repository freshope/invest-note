# Capacitor OTA 라이브 업데이트(자체 호스팅) v1 사양서

## 배경 / 목적

- FE 는 `fe/next.config.ts` 가 `output: "export"` 인 정적 SPA → `fe/capacitor.config.ts` `webDir: "out"` 로 웹 번들 전체를 네이티브 앱에 동봉한다. 따라서 **웹 자산(JS/HTML/CSS) 한 줄만 고쳐도 스토어 재심사**가 필요하다.
- 웹 자산 수정 빈도가 네이티브 변경보다 압도적으로 높으므로 OTA(Over-The-Air) 로 재심사를 우회한다. Apple §2.5.2 / §3.3.2 는 JS/HTML/CSS·자산만 교체하는 OTA 를 허용한다.
- 플러그인 `@capgo/capacitor-updater`(오픈소스, MPL-2.0)를 도입한다. 다운로드 / checksum 검증 / 원자적 교체 / 부팅 실패 시 자동 롤백을 플러그인이 처리한다.
- 백엔드는 **자체 호스팅**: 매니페스트 결정 API 는 기존 FastAPI(Coolify), 번들 zip 은 Cloudflare R2(CDN 전면, 무료 egress). Capgo Cloud 미사용.

연결: roadmap "스토어 재심사 비용 절감 / 빠른 핫픽스 배포". 기존 force-update(`docs/issue-history/2026-05-26-force-update.md`)와 직교적으로 연동한다.

## 페이징(중요)

플러그인은 네이티브 코드를 추가하므로, 이 OTA 셸을 심는 **스토어 1회 제출**이 OTA 동작의 전제다.

- **v1 목표 = "제출 가능한 상태"까지** = 코드 완성 + 로컬/CI 검증(`pytest` / `tsc` / `cap sync` 성공).
- "실제 라이브 OTA 동작 확인"(다운로드→원자적 교체→롤백, 버전 스큐 매트릭스 실기기 검증)은 **스토어 빌드가 라이브된 이후의 후속 단계**다. 본 사양의 verify 기준은 이 경계를 각 단위에 명시한다.

## 범위 (Scope)

**포함 (v1)**

1. FE 플러그인 통합: `@capgo/capacitor-updater` 설치 + `capacitor.config.ts` `CapacitorUpdater` 설정(`updateUrl`, `autoUpdate`) + 부팅 시 `notifyAppReady()` 호출(미호출 시 자동 롤백되므로 필수).
2. BE 매니페스트 결정 엔드포인트: 기기 POST body 를 받아 `{version, url, checksum}`(업데이트 있음) 또는 url 키 없는 200(업데이트 없음)을 응답. **checksum(SHA256) 포함 필수**.
3. 릴리즈 파이프라인: `@capgo/cli bundle zip --json` 으로 호환 zip + SHA256 생성 → R2 업로드 → 매니페스트 JSON 을 R2 에 **원자적으로 flip**(업로드·검증 후).
4. 버전 스큐 게이팅: 번들이 요구하는 `required_native_version` > 기기 네이티브 버전이면 OTA 차단(해당 번들 미반환). 기존 force-update 는 독립 하드 플로어로 유지.
5. 무결성: checksum 검증(플러그인 자체). env 계약에 R2 신규 인프라 추가. `docs/decisions.md` 결정 기록.

**제외 (v2 이후)**

- 서명 / E2E 암호화(번들 무결성 checksum 은 v1 포함, TLS 는 Cloudflare 충족).
- 단계 롤아웃(%): v1 은 100% 일괄 + 자동롤백 + 빠른 재푸시.
- 델타 업데이트, 채택률 통계 대시보드, 채널(QA/prod) 분리.
- 신규 shadcn 컴포넌트: **없음**(OTA 는 화면 비노출, force-update gate 는 기존 `base/Button` 사용). base 래퍼 작업 단위 없음.

## 가정 (Assumptions)

- `version_name`(요청 body) = **현재 설치된 OTA 번들 버전 또는 `"builtin"`** 이며, 네이티브 버전이 아니다. 네이티브 버전은 `version_build`(versionName) / `version_code`(versionCode)로 전달된다. (Capgo 공식 docs 기준, be-engineer 가 설치 후 실측 재검증.)
- 스큐 게이트가 비교할 "기기 네이티브 버전"은 `App.getInfo().version`(= ForceUpdateGate 가 이미 쓰는 값)과 동일한 마케팅 버전이며, 요청 body 의 `version_build` 에 담긴다. (be-engineer 설치 후 `version_build` vs `version_code` 중 어느 것이 마케팅 버전인지 실측 확정.)
- R2 매니페스트 객체는 public-read(HTTPS)로 공개 → BE 는 R2 자격증명 없이 읽기만 한다.
- Supabase 마이그레이션/RLS 변경 없음(SSOT 를 R2 JSON 으로 채택 — 아래 결정 2).

## 핵심 설계 결정 (근거와 함께 확정)

### 결정 1 — Capgo self-hosted updateUrl 계약 (출처: Capgo 공식 docs `plugin/self-hosted/auto-update`, 2026-06-08 확인)

플러그인이 앱 오픈 시마다 `updateUrl` 로 **POST** 하는 body:

```jsonc
{
  "platform": "ios" | "android" | "electron",
  "device_id": "UUID",
  "app_id": "APPID_FROM_CAPACITOR_CONFIG",   // app.pixelwave.investnote
  "custom_id": "런타임 set 값(미설정 시 빈/누락)",
  "plugin_version": "PLUGIN_VERSION",
  "version_build": "VERSION_NUMBER_FROM_NATIVE_CODE",  // 네이티브 versionName
  "version_code": "VERSION_CODE_FROM_NATIVE_CODE",     // 네이티브 versionCode
  "version_name": "현재 설치된 OTA 번들 버전 | \"builtin\"",
  "version_os": "OS 버전",
  "is_emulator": boolean,
  "is_prod": boolean
}
```

응답(업데이트 있음):

```json
{ "version": "1.2.3", "url": "https://.../bundle.zip", "checksum": "sha256_hex" }
```

- **업데이트 없음**: **`200 {"kind": "up_to_date"}`** 로 한다. ★ 2026-06-08 fe-engineer 가 플러그인 네이티브 소스(Android `CapacitorUpdaterPlugin.java:4212-4498`, iOS `CapacitorUpdaterPlugin.swift:3393-3440`)를 실측해 **본 결정의 초안("url 키 없는 빈 200")을 정정**: 빈 200/`{}`/204/empty-body 는 모두 플러그인이 `failed` 로 정규화해 매 부팅 다운로드 실패를 통지한다. 깨끗한 no-update 는 반드시 `kind:"up_to_date"`(스큐 차단 시 `kind:"blocked"` 도 가능 — 둘 다 non-failure). 근거: `_workspace/03_fe_changes.md` (1)-4.
- `message`/`error` 키 추가 시 버전이 set 되지 않고 로그에만 표시된다.
- `version` 은 semver, zip 은 루트에 `index.html` 또는 루트 단일 폴더 내 `index.html` 구조여야 한다.

### 결정 2 — 매니페스트 발행 상태 SSOT = R2 JSON (추천), 대안 Postgres

**채택: R2 의 단일 JSON 객체**(예 `s3://<bucket>/manifest/latest.json`, **플랫폼 공통 단일 파일**). 발행된 번들의 `{version, url, checksum, required_native_version}` 을 담는다. 웹 번들은 iOS/Android 동일하고 `version-check` 가 마케팅 버전 플랫폼 패리티를 강제하므로 플랫폼별 분리 불필요(릴리즈 스크립트 PUT 1회). BE 는 `platform` 필드와 무관하게 동일 manifest 를 읽는다.

| 후보 | 장점 | 단점 |
|------|------|------|
| **(b) R2 JSON ✅** | 릴리즈 스크립트가 **이미 보유한 R2 write 자격증명**으로 zip 업로드 직후 PUT 한 번으로 원자적 flip. BE 는 자격증명 없이 HTTPS GET. **Supabase 마이그레이션/RLS 변경 불필요(사용자 confirm 회피)**. | 발행 이력 쿼리/트랜잭션 부재(v1 은 통계·서버측 롤백 미포함이라 무방, 롤백은 클라이언트측 자동). |
| (a) Postgres 테이블 | 이력·트랜잭션, 향후 통계 확장 용이 | 테이블 추가 = 마이그레이션/RLS 변경 → **사용자 confirm 필수**. BE 가 admin flip 엔드포인트 필요(인증·원자성 부담). v1 범위 초과. |
| (c) env/config | 가장 단순 | 발행마다 Coolify env 수정+재배포 → 원자적 flip 불가, 운영 수동 개입. 기각. |

원자성: 릴리즈 스크립트가 ① zip PUT → ② HEAD/checksum 재검증 → ③ manifest JSON PUT 순서. manifest flip 은 zip 가용·검증 **후**에만 일어나므로, 기기가 manifest 의 url 을 받는 시점엔 zip 이 반드시 존재한다.

### 결정 3 — 버전 스킴 / required_native_version

- 번들 `version` = `fe/package.json` 의 마케팅 버전(semver). Capgo 가 semver 를 요구하고, 기존 bump 흐름(`make bump-* fe`)과 단일 출처를 공유한다.
- **웹 전용 OTA 릴리즈** = `make bump-patch fe`(마케팅 버전 +1) **without `bump-build`**(빌드 번호·네이티브 재빌드 없음). manifest `version` 이 이 값을 따른다.
- `required_native_version`: 발행 시점에 manifest 에 **명시 기록**. 기본값 = 현재 네이티브 마케팅 버전. 웹 변경이 새 네이티브 기능(플러그인 추가 등)을 요구할 때만 수동 상향.
- **force-update(`min_supported_version`)와 직교**: 전자는 스토어 강제 하드 플로어(`/app-config`), 후자는 "이 번들을 안전히 돌릴 수 있는 최소 네이티브"다. 둘은 별개 임계값으로 절대 합치지 않는다.

### 결정 4 — R2 자격증명 보관

- R2 write 토큰(account id / access key / secret / bucket / public base URL)은 **릴리즈 스크립트만** 사용한다.
- 보관처: **프로젝트 루트 gitignored `.env`(릴리즈 전용)** 또는 CI secret. fe 의 public build env(`NEXT_PUBLIC_*`, `.env.development.local`)에 **절대 넣지 않는다**(번들 누출 방지). 기존 `NEXT_PUBLIC_SITE_URL` 유지 규칙·`.env.local`(production build 누출) 금지 관례 존중.
- BE 는 R2 자격증명 불필요(manifest public-read GET) → BE env 에는 **manifest base URL 만**(또는 platform별 URL 패턴) 추가.

## 작업 단위

> 의존 순서: **0(인프라, 사용자) → 1(BE 계약) → 2(FE 플러그인, updateUrl 정합) → 3(릴리즈 스크립트) → 4(QA)**. BE 매니페스트 응답 shape 가 FE/CLI/스크립트의 단일 진실이므로 BE 가 선행한다.

---

### 0. [INFRA · 사용자 수동] R2 버킷 / 자격증명 / env 주입
- **우리(코드) 아님 — 사용자 수동 운영 스텝.** 사양은 무엇이 필요한지만 명시한다.
- Cloudflare R2 버킷 생성, public-read(또는 CDN 도메인) 설정, CORS 헤더(앱이 zip 다운로드 허용).
- 릴리즈용 R2 access key/secret 발급 → 루트 gitignored `.env`(또는 CI secret)에 주입.
- Coolify BE 환경변수에 manifest base URL 주입.
- 스토어 제출(플러그인 심은 빌드 1회) — v1 코드 완성 후.
- verify: (운영) 버킷에 테스트 객체 PUT/GET 성공, manifest URL HTTPS 200.
- 의존: 없음. (단위 1~3 의 코드 작성과 병렬 가능, **실배포 검증은 이 스텝 완료 후**.)

### 1. [BE] 매니페스트 결정 엔드포인트 — `be/src/invest_note_api/schemas/live_update.py` (신규)
- Capgo 요청 body(AppInfos)와 응답(`{version,url,checksum}` / no-update) 스키마 정의. CamelModel 이 아닌 **snake_case 그대로**(Capgo 계약은 snake_case) — `_base.py` 패턴과 분리 주의, 별도 `BaseModel` 사용.
- verify: `cd be && poetry run pytest tests/test_live_update.py -q` (다음 단위에서 테스트 작성, 본 단위는 import 가능성만)
- 의존: 없음

### 2. [BE] 매니페스트 결정 라우터 — `be/src/invest_note_api/routers/live_update.py` (신규)
- `POST /live-update/manifest`(인증 없음, public — force-update `/app-config` 패턴 따름). 플랫폼 공통 단일 R2 manifest JSON(httpx, `app.state.http_client`)을 GET → 발행 번들 `{version,url,checksum,required_native_version}` 로드.
- **결정 로직**:
  - `effective_installed = version_build if version_name == "builtin" else version_name` (신규 스토어 설치는 `version_name="builtin"` → builtin 번들의 웹 버전 = 동봉된 네이티브 마케팅 버전이므로 `version_build` 로 대체. 미처리 시 첫 부팅마다 중복 다운로드 발생).
  - ① `required_native_version <= 기기 네이티브 버전(= version_build)` 아니면 no-update(스큐 차단, force-update 가 폴백).
  - ② 발행 `version` > `effective_installed` 일 때만 `{version,url,checksum}` 반환.
  - ③ 그 외 url 키 없는 200.
- semver 비교는 기존 BE util 재사용/없으면 최소 구현. fail-open: manifest GET 실패 시 no-update(앱 부팅 차단 금지).
- `main.py` 의 `include_router` + legacy `/api` alias 목록에 등록. (1 파일 원칙 예외: 라우터 등록 1줄은 main.py 동반 — be-engineer 가 라우터 파일과 함께 처리.)
- **⚠️ MERGE-BLOCKING be-engineer 노트**: 플러그인 설치 후 **반드시** ① `version_build` vs `version_code` 중 `App.getInfo().version`(마케팅 버전)과 일치하는 필드를 실측 확정 — 이 가정이 뒤집히면 스큐 게이트·builtin 대체가 둘 다 오작동한다. pytest 스큐 케이스는 **추정 필드가 아니라 확정된 필드**로 작성. ② no-update 의 204 vs empty-body 실동작 확정, ③ 요청 body 필드명/케이스 실측 재검증.
- verify: `cd be && poetry run pytest tests/test_live_update.py -q` — 케이스: 스큐 차단(구네이티브), 정상 업데이트, 동일/최신 시 no-update, **`version_name=="builtin"` 신규설치 시 중복 미반환**, manifest 조회 실패 fail-open, no-update 응답에 url 키 부재.
- 의존: 단위 1

### 3. [BE] env 추가 — `be/src/invest_note_api/config.py`
- `live_update_manifest_base_url: str = ""`(빈 값이면 라우터가 no-update fail-open). 필요 시 platform별 패턴.
- verify: `cd be && poetry run pytest tests/test_app_config.py -q`(Settings 로딩 회귀) + 단위 2 테스트가 이 설정 사용.
- 의존: 단위 2 와 병렬 가능(라우터가 참조하므로 통합 전 머지).

### 4. [FE] 플러그인 설치 + Capacitor 설정 — `fe/capacitor.config.ts`
- `pnpm -C fe add @capgo/capacitor-updater` 후 `plugins.CapacitorUpdater` 블록 추가: `updateUrl: "<BE>/live-update/manifest"`, `autoUpdate: true`. updateUrl 은 단위 2 경로와 정합.
- verify: `pnpm -C fe exec tsc --noEmit` + `npx cap sync`(네이티브 동기화 성공). (라이브 다운로드는 스토어 빌드 후.)
- 의존: 단위 2(updateUrl 경로 확정)

### 5. [FE] 부팅 시 notifyAppReady() 호출 — `fe/src/components/providers/LiveUpdateReady.tsx` (신규) + 마운트 1줄
- 앱 마운트 직후 `CapacitorUpdater.notifyAppReady()` 호출(네이티브에서만, web no-op). 미호출 시 플러그인이 새 번들을 실패로 간주해 자동 롤백하므로 **필수**.
- ForceUpdateGate 와 동일 provider 계층에 마운트(루트 layout/provider 1줄 추가).
- 신규 shadcn 없음 → base 래퍼 불필요.
- verify: `pnpm -C fe exec tsc --noEmit` + 수동(스토어 빌드 후): 앱 재실행 시 직전 번들 유지(롤백 안 됨) 확인.
- 의존: 단위 4

### 6. [RELEASE] OTA 발행 스크립트 — `scripts/publish-ota.mjs` (또는 `.sh`) 신규
- 흐름: `pnpm -C fe build` → **`npx @capgo/cli bundle zip --json`**(호환 zip + SHA256, 표준 zip 금지) → JSON 에서 `version`/`checksum` 파싱 → R2 zip PUT → HEAD/checksum 재검증 → manifest JSON PUT(원자적 flip, `required_native_version` 포함).
- `@capgo/cli` 를 `fe` devDependency 로 추가. R2 자격증명은 루트 `.env`(결정 4)에서 로드. Makefile 편입은 thin wrapper 타깃 추가(루트 Makefile 은 `~/workspace/devtools/Makefile.common` wrapper — 신규 타깃은 프로젝트 Makefile 측에 둘지 be-engineer/release 담당이 판단, 직접 Makefile.common 수정 금지).
- verify: zip 산출물에 `index.html` 루트 구조 존재 + `--json` checksum 이 업로드 객체와 일치(드라이런). 실 R2 업로드는 단위 0 완료 후.
- 의존: 단위 1(매니페스트 shape), 단위 4(@capgo/cli·빌드 산출 정합)

### 7. [DOCS] 결정 기록 — `docs/decisions.md`
- 자체호스팅 OTA 채택 / R2 SSOT(결정 2) / required_native_version vs min_supported_version 직교(결정 3) / CLI zip 강제(결정 1) 기록.
- verify: 문서 리뷰(트레이드오프·기각안 포함).
- 의존: 단위 1~6 결론 확정 후.

### 8. [QA] 정합성 + 스큐 매트릭스
- **코드 정합(v1 내 검증 가능)**:
  - BE 응답 shape(`version/url/checksum`, no-update url 부재) ↔ Capgo 계약 일치.
  - FE `updateUrl` ↔ BE 라우터 경로 일치. `notifyAppReady()` 마운트 존재.
  - 릴리즈 스크립트 zip 구조(`index.html` 루트) + checksum 일치.
  - force-update(`min_supported_version`) 경로 무변경 회귀(`test_app_config.py`).
- **메모리 함정 체크**: ForceUpdateGate fail-open 유지, BE 응답 snake_case(Capgo) vs 기존 CamelModel 혼선 없음, R2 토큰이 fe public env 에 누출 안 됨.
- **스큐 매트릭스(대부분 post-store, v1 은 기준만 명시)**:
  - 구네이티브 + 신웹(번들 `required_native_version` > 기기) → OTA 차단, force-update 가 적정 시 강제. (BE 단위 2 pytest 로 결정 로직은 v1 검증 가능)
  - 신네이티브 + 구웹 → OTA 정상 적용.
  - 신규 스토어 설치(`version_name=="builtin"`) → 동봉 버전과 발행 버전 동일 시 중복 다운로드 없음.
  - 부팅 실패 번들 → `notifyAppReady()` 미달 시 자동 롤백(실기기, post-store).
- verify: 위 정합 항목 통과 + 매트릭스 중 BE 결정 로직은 pytest, 실기기 항목은 후속 단계 todo 로 명시.
- 의존: 단위 1~6

## 완료 조건

- [ ] 모든 코드 단위 verify 통과(`pytest` / `tsc` / `cap sync` / zip 드라이런).
- [ ] BE no-update 응답 = `200 {"kind":"up_to_date"}` (빈 200/`{}`/204 금지) — 결정 1(2026-06-08 실측 정정) 준수.
- [ ] `required_native_version` 과 `min_supported_version` 분리 유지 — 결정 3.
- [ ] R2 토큰 fe public env 미누출 — 결정 4.
- [ ] `docs/decisions.md` 갱신.
- [ ] **(MERGE-BLOCKING)** be-engineer 실측 노트 3건(필드 케이스 / no-update 동작 / `version_build` vs `version_code` 의미) 회신 — 스큐 게이트·builtin 대체의 전제. pytest 스큐 케이스는 확정 필드로 작성.
- [ ] `version_name=="builtin"` 신규설치 중복 다운로드 없음(단위 2 pytest).
- [ ] **v1 경계 명시**: 라이브 OTA·실기기 스큐 매트릭스는 스토어 제출(단위 0) 이후 후속.
- [ ] spec → `docs/issue-history/2026-06-08-capacitor-ota-live-update.md` 이동 준비.
