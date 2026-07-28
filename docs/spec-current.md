# Spec: 푸시 전송 Firebase Admin 단일 채널 통합

브랜치: `feature/push-firebase-unify`

## Context / 배경

현재 푸시는 BE `services/push_sender.py` 가 **두 채널을 직접 구현**한다 — Android 는 FCM HTTP v1(서비스계정 JWT 를 손으로 서명 → OAuth2 토큰 교환 → REST), iOS 는 `api.push.apple.com` 에 `.p8` ES256 JWT 를 직접 서명해 HTTP/2 로 전송. 그 결과:

- env 시크릿이 6개(`FCM_SERVICE_ACCOUNT_JSON` + `APNS_KEY_P8`/`KEY_ID`/`TEAM_ID`/`BUNDLE_ID`/`USE_SANDBOX`)로 늘고, 멀티라인 시크릿 base64 우회까지 얹혀 있다.
- iOS 는 `aps-environment`(development/production)와 APNs 호스트(sandbox/prod)를 사람이 맞춰야 하고, 어긋나면 조용히 실패한다.
- 실제 전송이 한 번도 검증된 적 없다(PostHog push 0건).

**목표:** `firebase-admin` SDK 한 채널로 통합한다. iOS APNs 라우팅은 Firebase 가 위임 처리하므로 sandbox/prod 매칭 고민이 사라지고, 시크릿은 서비스계정 JSON 하나로 줄어든다. 같은 워크스페이스의 today-alive `api/app/services/push/` 가 이미 이 구조로 동작 중이라 그 패턴을 레퍼런스로 삼는다(단, 아래 4개 차이를 반드시 반영 — faithful copy 금지).

**완료 기준:** 어드민이 게시판 글에 답변하면 → 글쓴이 기기(Android 실기기)에 푸시가 도착하고, 탭하면 알림 이력이 열린다. iOS 는 사용자 Firebase Console 작업 후 동일 검증.

## 설계

### 접근 방식

`push_sender.py` 단일 모듈 → `services/push/` 패키지(어댑터 패턴). today-alive 구조를 따르되 invest-note 사정에 맞춘 **4가지 필수 차이**:

1. **`send()` 에 `data` 인자 추가.** today-alive 시그니처는 `send(*, token, title, body)` 로 data 가 없다. invest-note 는 딥링크 페이로드 전체(`build_data_payload`: notification_id/source/type/board_type/ref_id)가 FCM `data` 로 실려야 한다 → 원본 그대로 복사하면 딥링크가 조용히 유실된다.
2. **`asyncio.to_thread()` 래핑.** `messaging.send()` 는 동기(blocking) I/O. today-alive 는 전스택 sync 스케줄러라 문제없지만 invest-note 는 async 라우트(`admin_board._notify_post_owner`)에서 호출하므로 감싸지 않으면 이벤트루프가 막힌다.
3. **`push_enabled` early-return 게이트 유지.** today-alive 는 자격증명이 없으면 `_load_credentials()` 가 `RuntimeError` 를 던진다. invest-note 의 기존 계약은 "시크릿 없으면 DB·네트워크 접근 전에 조용히 no-op" 이므로, 어댑터를 만들기 **전에** 반환한다(기존 `test_push_no_op_without_secrets` 유지).
4. **`token_invalid` → 토큰 삭제 배선 신규 구축.** invest-note 엔 이 경로가 아예 없다(현재는 경고 로그만). `device_tokens_repo.delete_token` 은 존재하나 전송 경로에서 호출되지 않는다. 특히 **기존 iOS raw-APNs 토큰(64 hex)을 FCM 에 넘기면 `UnregisteredError` 가 아니라 `exceptions.InvalidArgumentError`** 가 나므로, 3종(`UnregisteredError`/`SenderIdMismatchError`/`InvalidArgumentError`)을 모두 `token_invalid` 로 매핑해야 cutover 후 stale row 가 자연 정리된다.

**게이트는 하나(`push_enabled` = 자격증명 존재)로 유지한다.** today-alive 의 `PUSH_PROVIDER` env 는 도입하지 않는다 — `push_enabled` 와 어긋날 수 있는 게이트가 둘이 되고 Coolify env 만 늘어난다. 테스트는 `send_to_user(..., adapter=DummyPushAdapter())` 주입으로 대체한다(today-alive `emergency_service` 의 `adapter or get_push_adapter()` 패턴).

### 주요 변경 파일

**BE**
- `api/src/invest_note_api/services/push/base.py` (신규) — `PushResult`(success/provider_message_id/token_invalid/error) + `PushAdapter` Protocol, `send(*, token, title, body, data)`
- `api/src/invest_note_api/services/push/firebase.py` (신규) — `FirebasePushAdapter`. 자격증명은 `google_application_credentials_json` 에서 로드, `firebase_admin._apps` idempotent guard, `APNSConfig(sound="default")` 유지(현 `_send_apns` 동작 보존), 예외 3종 → `token_invalid`
- `api/src/invest_note_api/services/push/dummy.py` (신규) — 테스트 주입용
- `api/src/invest_note_api/services/push/__init__.py` (신규) — `send_to_user`, `build_data_payload`, `get_push_adapter` 재노출
- `api/src/invest_note_api/services/push_sender.py` (삭제) — 로직은 `push/__init__.py` 의 `send_to_user` 로 이동
- `api/src/invest_note_api/config.py` — `google_application_credentials_json` 추가 + base64 validator 목록에 등록, `push_enabled` 를 이 필드 기준으로 단순화. **제거**: `fcm_service_account_json`, `apns_key_p8`, `apns_key_id`, `apns_team_id`, `apns_bundle_id`, `apns_use_sandbox`, `fcm_enabled`, `apns_enabled`
- `api/pyproject.toml` — `firebase-admin = "^7.4"` 추가. `pyjwt` 는 auth(`jwt.py`)가 쓰므로 **제거 금지**, `httpx` 도 시세 경로가 쓰므로 유지
- `api/src/invest_note_api/routers/admin_board.py` — import 경로만 `services.push` 로 변경(호출 시그니처 동일)
- `api/tests/test_push_sender.py` — APNs `.p8` 테스트 2건 제거(필드 삭제), base64 테스트는 새 필드명으로 이관, `token_invalid → delete_token` 호출 테스트 신규
- `api/.env.example`, `api/.env.production` — `FCM_*`/`APNS_*` 블록 → `GOOGLE_APPLICATION_CREDENTIALS_JSON`

**FE**
- `app/src/lib/push/registerPush.ts` — `@capacitor/push-notifications` → `@capacitor-firebase/messaging`. 매핑: `requestPermissions()` 유지 / `register()` → `getToken()` / `registration` → `tokenReceived` / `pushNotificationActionPerformed` → `notificationActionPerformed`. 기존 `started` 모듈 가드·best-effort 예외 삼킴 그대로
- `app/package.json` — `@capacitor-firebase/messaging` 추가, `@capacitor/push-notifications` 제거. `firebase` npm 도 추가(아래 "구현 중 확정" 참고)
- 무변경: `PushRegistration.tsx`, `api-client.ts` `registerPushToken`, 딥링크 페이로드 소비(현재도 안 함 → 신규 구현 안 함)

**네이티브**
- Android: `app/android/app/google-services.json` **이미 존재** → 선행조건 없음
- iOS: `App.entitlements` 의 `aps-environment=development` **유지**(Firebase 자동 라우팅). `AppDelegate.swift` 는 `didRegisterForRemoteNotificationsWithDeviceToken` 포워딩이 이미 있어 무변경

## 구현 체크리스트

- [x] `config.py` — `google_application_credentials_json` 추가 + validator 등록, APNs/FCM 필드·프로퍼티 제거
- [x] `pyproject.toml` — `firebase-admin` 추가 후 `poetry lock && poetry install`
- [x] `services/push/base.py` + `dummy.py`
- [x] `services/push/firebase.py`
- [x] `services/push/__init__.py` — `send_to_user`(to_thread 래핑 + token_invalid 삭제), `build_data_payload` 이관 / `push_sender.py` 삭제 / `admin_board.py` import 갱신
- [x] `api/tests/test_push.py`(rename) 정리 + token_invalid 테스트 → **1032 passed, 22 skipped**, `ruff check` 통과
- [x] `.env.example` / `.env.production` 갱신
- [x] `app/package.json` 플러그인 스왑 + `pnpm install`
- [x] `registerPush.ts` 재작성 → `tsc --noEmit` 통과, `pnpm test` **315 passed**, `pnpm build` 통과
- [x] `npx cap sync android`(플러그인 11개 인식) + `./gradlew :app:assembleDebug` 통과
- [x] iOS: `GoogleService-Info.plist` 배치 + Xcode 타깃 등록(`project.pbxproj` 에 PBXFileReference/PBXBuildFile/Resources 추가) → `npx cap sync ios` + `xcodebuild` **BUILD SUCCEEDED**, 산출 번들에 plist 포함·`FIRMessaging` 링크·구 `CapacitorPushNotifications` 잔존 0 확인
- [ ] Android 실기기 스모크(토큰 등록 → 어드민 답변 → 수신 → 탭)
- [ ] iOS 실기기 스모크(동일)

## 구현 중 확정된 사항 (플랜 대비 변경)

1. **httpx `^0.27` → `^0.28`.** `firebase-admin` 이 `httpx[http2]==0.28.1` 을 하드핀해 버전 충돌.
   코드베이스의 httpx 사용은 전부 표준 형태(`AsyncClient(timeout/headers/transport)`,
   `MockTransport`, `ASGITransport(app=)`)라 0.28 breaking change(`proxies=`·`app=` 단축) 해당
   없음 — 전체 1032 테스트 통과로 확인.
2. **`firebase` npm 추가함.** optional peer 지만 플러그인의 web 구현(`dist/esm/web.js`)이
   `firebase/messaging` 을 정적 import 해서 next build 가 module-not-found 로 실패했다.
   추가 후 빌드 통과. 네이티브에서는 web 구현이 로드되지 않는다.
3. **`factory.py` 미생성.** `PUSH_PROVIDER` 를 안 두기로 해서 팩토리가 항상 한 종류만 반환 —
   `send_to_user` 안의 지연 import 로 대체(어댑터 주입은 `adapter=` 인자).
4. **`test_push_sender.py` → `test_push.py` 로 rename** (`push_sender` 모듈이 사라져 이름이 오도).
5. **base64 시크릿 처리 제거.** 서비스계정 JSON 은 `private_key` 의 개행이 JSON `\n` 이스케이프라
   **원래 한 줄로 표현 가능** → .env 파서를 깨뜨리지 않는다. 따라서 `config.py` 의 base64 디코드
   validator(`_decode_b64_secret`)를 없애고 값을 그대로 쓴다. `.env.production` 값도 한 줄 JSON 으로
   변환. (멀티라인이던 APNs `.p8` PEM 이 사라져 base64 우회 자체가 불필요해졌다.)

## 사용자 선행조건

Firebase Console `invest-note-494103` — **iOS 앱 등록 + plist 전달 완료**(2026-07-28). plist 는 `App/App/` 배치에 더해 Xcode App 타깃 Copy Bundle Resources 에 등록했고, 빌드 산출 번들에 포함되는 것까지 확인했다.

⚠️ **남은 확인:** Cloud Messaging 에 **APNs 인증키 `.p8` 업로드**(BE 에서 제거한 `APNS_*` 가 여기로 이동). 이게 없으면 iOS 는 FCM 토큰은 받아도 실제 알림이 도착하지 않는다.

Coolify: `GOOGLE_APPLICATION_CREDENTIALS_JSON` 에 서비스계정 JSON 을 **줄바꿈 없는 한 줄**로 주입(`jq -c . service-account.json`). 인코딩·변환 없음. 기존 `FCM_SERVICE_ACCOUNT_JSON`/`APNS_*` 는 제거. 미주입 시 푸시는 조용히 no-op(안전 실패).

## 우려사항 / 리스크

- **릴리즈 함정(중요):** 신규 Capacitor 네이티브 플러그인이라 `make release-scope` 가 **web-only 로 오판**한다 → OTA 로 내보내면 동작 불가. 반드시 **네이티브 릴리즈 + 양 스토어 재심사**. 릴리즈 전 `app/package.json` diff 에서 `@capacitor*` 신규 항목 확인.
- **릴리즈 후 순서:** 양 스토어에 이 바이너리가 **라이브로 확인된 뒤에만** `OTA_REQUIRED_NATIVE` 를 인상한다(스토어 라이브 마케팅 버전이 출처). OTA 번들은 기존 버전번호를 재사용하지 않는다(재사용 시 기존 설치가 새 콘텐츠를 못 받음).
- **기존 iOS 토큰:** `registerPush` 는 커밋 612cbb5 로 이미 릴리즈에 나갔으므로 `device_tokens` 에 raw-APNs 토큰 row 가 있을 수 있다. 위 4번 배선으로 첫 전송 시 자동 삭제된다 — 별도 backfill/마이그레이션은 만들지 않는다.
- **검증 순서:** Android 가 선행조건 없이 끝까지 검증 가능하므로 BE → FE → Android 를 먼저 완주하고, iOS 는 plist 수령 후 마지막 단계로 분리한다.
- **범위 밖(무변경):** `notifications`/`device_tokens` 테이블, 알림 이력 UI, 딥링크 라우팅, `MIN_SUPPORTED_VERSION`.
