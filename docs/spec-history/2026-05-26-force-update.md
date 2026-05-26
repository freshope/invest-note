# Spec: 앱 강제 업데이트 (Force Update)

> 완료: 2026-05-26

## 배경 / 문제

invest-note 는 Capacitor 단일 배포(iOS/Android) 앱이다. 옛 번들 사용자를 새 번들로 강제 이동시키는 메커니즘이 없어, BE legacy `/api/*` alias 제거(backlog.md)나 호환성 깨는 변경을 안전하게 진행할 수 없다. 백로그 `모바일앱 (v2.5) 잔여` 의 "강제 업데이트 메커니즘" 을 구현한다.

**한계(설계상 불가피):** 이 메커니즘은 *체크 로직이 포함된 번들* 부터만 동작한다. 이미 배포된 옛 번들은 엔드포인트를 호출하지 않으므로 강제할 수 없다. 이번 릴리즈가 향후 강제 업데이트의 baseline 이 된다.

## 목표 (완료 기준)

1. BE 환경변수에 `MIN_SUPPORTED_VERSION` 을 추가한다.
2. BE가 **최소 지원 버전(단일) + 플랫폼별 스토어 URL** 을 인증 없이 응답하는 `GET /app-config` 엔드포인트를 제공한다.
3. 네이티브 앱 실행 시 현재 버전(`App.getInfo().version`)이 최소 지원 버전보다 낮으면 해제 불가능한 전체 화면 오버레이가 뜨고, "업데이트" 버튼이 해당 플랫폼 스토어를 연다. ESC·외부 클릭·Android 하드웨어 백버튼 모두 차단.
4. 안전장치: env 미설정 시 강제하지 않는다(no-force). 네트워크 실패 시에도 강제하지 않는다(fail-open). web 플랫폼은 체크하지 않는다.
5. BE pytest + FE 버전 비교 유닛 테스트 통과, `pnpm -C fe exec tsc --noEmit` 통과.

## 설계

### 접근 방식

- **저장소:** BE env. `MIN_SUPPORTED_VERSION`(단일, 양 플랫폼 공통) + `STORE_URL_IOS` / `STORE_URL_ANDROID`. 미설정 → 빈 문자열 → 강제 안 함.
- **비교 단위:** `versionName`(semver "1.1.13"). `App.getInfo().version` 이 iOS `CFBundleShortVersionString` / Android `versionName` 임(definitions.d.ts:42-44). build/versionCode 는 플랫폼별로 갈리고 재심사 시 변동되어 사용하지 않음.
- **단일 min 버전:** lockout 방지는 "양 스토어 모두 신버전 승인 후에만 min 을 올린다" 운영 규칙(배포 노트)으로 처리.
- **하드 업데이트만:** 강제(해제 불가)만 구현. "최신 버전"·소프트(권장) 업데이트는 제외.
- **오버레이는 Radix Dialog 가 아닌 plain fixed `inset-0` div**: ESC·외부 클릭이 본래 동작하지 않음(자동 차단). Android 백버튼만 명시적으로 swallow.

### BE 응답 shape (CamelModel)

```json
{
  "minSupportedVersion": "1.1.13",
  "storeUrl": { "ios": "https://apps.apple.com/app/id...", "android": "https://play.google.com/store/apps/details?id=app.pixelwave.investnote" }
}
```
- `minSupportedVersion` 빈 문자열("") → 강제 안 함. FE 는 `storeUrl[platform]` 로 스토어 링크 선택.

### 주요 변경 파일

**BE**
- `be/src/invest_note_api/config.py` — Settings 에 3개 필드 추가: `min_supported_version=""`, `store_url_ios=""`, `store_url_android=""`.
- `be/src/invest_note_api/schemas/app_config.py` (신규) — CamelModel: `StoreUrls`(ios, android) + `AppConfigResponse`(minSupportedVersion, storeUrl).
- `be/src/invest_note_api/routers/app_config.py` (신규) — public router, `GET /app-config`, `Depends(get_settings)` 만.
- `be/src/invest_note_api/main.py` — 라우터 등록 (legacy `/api/*` 루프 제외).
- `be/tests/test_app_config.py` (신규).

**FE**
- `fe/src/lib/version.ts` (신규) — `compareVersions`, `isUpdateRequired`.
- `fe/src/lib/api/app-config.ts` (신규) — 인증 불필요 `fetchAppConfig()`.
- `fe/src/components/providers/ForceUpdateGate.tsx` (신규).
- `fe/src/app/layout.tsx` — 게이트 마운트.
- `fe/src/lib/version.test.ts` (신규).

### 배포 노트 (운영 체크리스트)

- Coolify BE 시크릿에 `STORE_URL_IOS`, `STORE_URL_ANDROID` 를 먼저 설정한 뒤 `MIN_SUPPORTED_VERSION` 을 올린다(빈 URL 모달 방지).
- 단일 min 버전이므로 양 스토어(App Store·Play) 모두 신버전 승인 후에만 `MIN_SUPPORTED_VERSION` 을 올린다.
- Apple App ID 미발급. 발급 후 `STORE_URL_IOS` 에 주입 — 코드 하드코딩 X.

## 구현 체크리스트

- [x] BE: `config.py` Settings 3개 필드 추가
- [x] BE: `schemas/app_config.py` CamelModel 추가
- [x] BE: `routers/app_config.py` public `GET /app-config` 추가
- [x] BE: `main.py` 라우터 등록 (legacy 루프 제외)
- [x] BE: `tests/test_app_config.py` → 3 passed
- [x] FE: `lib/version.ts` + `__tests__/version.test.ts`
- [x] FE: `lib/api/app-config.ts`
- [x] FE: `components/providers/ForceUpdateGate.tsx` (백버튼 swallow 포함)
- [x] FE: `app/layout.tsx` 게이트 마운트
- [x] FE: `pnpm -C fe test` (144 passed) + `pnpm -C fe exec tsc --noEmit` (clean)

## 우려사항 / 리스크

- **lockout 위험:** env 기본 ""·fail-open 2중 방어 + "양 스토어 승인 후 min 인상" 운영 규칙. no-force 를 BE 테스트로 강제.
- **baseline 한계:** 이번 릴리즈 이전 번들은 강제 불가. 정상 동작이며 문서화로 처리.
