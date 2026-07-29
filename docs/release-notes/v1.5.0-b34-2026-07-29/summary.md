# 출시 노트 요약 — v1.5.0_34

> 작성일: 2026-07-29
> 비교 기준: app-v1.4.0_33 (2026-07-03) — **마지막 네이티브 제출 태그**. v1.4.1/v1.4.2/v1.4.3 은 모두 OTA web-only 라 스토어 노트가 없었고, 그 누적 변경을 이번 제출에 함께 담는다.
> 대상 빌드: app-v1.5.0_34 (준비 중 — 📱 네이티브 변경, 스토어 재심사 필요)
> 동반 백엔드: api-v1.3.18 (같은 릴리즈 브랜치에서 함께 태깅)

## Git 로그 (app-v1.4.0_33..HEAD, --no-merges)

누적 범위가 커밋 70여 개라 **사용자 가시 항목과 이번 릴리즈 핵심만** 싣는다. 나머지(원장 재설계·어드민·리팩토링·문서)는 `old/v1.4.1-b33`, `old/v1.4.2-b33`, `v1.4.3-b33` summary 에 이미 기록돼 있다.

| 해시 | 날짜 | 메시지 |
|------|------|--------|
| d46396f | 2026-07-29 | chore: bump version app-v1.5.0_34 |
| 1ec2710 | 2026-07-29 | feat(app): 계좌 등록 증권사에 카카오페이증권 추가 |
| b37fb08 | 2026-07-28 | feat(push): Firebase Admin 단일 채널로 푸시 전송 통합 |
| f837b4d | 2026-07-28 | fix(app): Android 백버튼으로 앱 종료되지 않는 문제 수정 |
| 2ebba77 | 2026-07-28 | fix(config): 푸시 시크릿 base64 디코드 지원 |
| 612cbb5 | 2026-07-22 | feat(notifications): 게시판 처리 알림 → 푸시 전환 + 알림 이력 페이지 |
| 861635d | 2026-07-16 | feat(import): 암호 걸린 거래내역서 파일 안내·검증 추가 |
| 3354917 | 2026-07-16 | fix(board): 제출 폼 연타 시 중복 등록 방지 (동기 ref 락) |
| ca21ea5 | 2026-07-16 | refactor(import): preview·commit 판단 공유 plan 통합 + 이미 등록됨 표시 |
| de1c0dd | 2026-07-16 | feat(import): 한국투자증권 거래내역서 파서 추가 |
| f3686a5 | 2026-07-05 | fix(board): 탈퇴 회원 댓글도 '탈퇴한 회원'으로 표시 |
| e0af36c | 2026-07-05 | fix(board): 탈퇴 회원 게시글 작성자를 '탈퇴한 회원'으로 표시 |
| d419470 | 2026-07-05 | feat(app): 자산추이 표시 단위(일/주/월) 선택 추가 |
| cd04026 | 2026-07-08 | fix(import): 원장 인덱스 락 제거 + ticker 재해소 재커밋 dead-end 해소 |
| 0df16ea | 2026-07-03 | fix(api): 일괄등록 커밋 동시 재커밋 중복 방어 |

## 동기간 spec-history 항목

- `2026-07-29-push-firebase-unify.md` — 푸시 전송을 FCM 직접 구현 + APNs 직접 구현 2채널에서 Firebase Admin SDK 단일 채널로 통합. 시크릿 6개 → 1개, iOS APNs 라우팅 위임.
- `2026-07-22-board-notifications.md` — 게시판 처리 통지(답변·상태변경·공지)를 인앱 배지+폴링에서 푸시 알림으로 전환하고 알림 이력 페이지 신설.
- `2026-07-06-admin-import-ledger.md` — 어드민 거래내역서 원장 조회(사용자 비가시).
- `2026-07-03-import-ledger.md` — 일괄등록 소스를 staging → append-only 원장으로 재설계(내부 구조).

## 분류표

| 라벨 | 항목 | 출시 노트 반영 |
|------|------|--------------|
| NEW | 게시판 답변·상태변경 푸시 알림 + 알림 이력 화면 (612cbb5, b37fb08) — 이번 네이티브 빌드에서 처음 실제 동작 | ✓ |
| NEW | 자산추이 표시 단위(일/주/월) 선택 (d419470) | ✓ |
| NEW | 한국투자증권 거래내역서 파서 (de1c0dd) | ✓ |
| NEW | 카카오페이증권 계좌 등록 (1ec2710) | ✓ |
| IMPROVE | 일괄등록 '이미 등록됨' 표시 (ca21ea5) | ✓ |
| IMPROVE | 암호 걸린 거래내역서 파일 사전 안내 (861635d) | ✓ |
| IMPROVE | 탈퇴 회원 게시글·댓글 '탈퇴한 회원' 표시 (e0af36c, f3686a5) | ✓ |
| FIX | Android 백버튼으로 앱 종료되지 않던 문제 (f837b4d) | ✓ |
| FIX | 게시판 제출 폼 연타 중복 등록 (3354917) | ✓ |
| FIX | 일괄등록 중복 등록·재커밋 실패 (0df16ea, cd04026, 05281ae, ef52950, af732eb) | ✓ (묶어서 1줄) |
| INTERNAL | 푸시 전송 채널 Firebase Admin 통합 자체 (b37fb08, 2ebba77) — 사용자에겐 '알림' 으로만 보임 | ✗ (NEW 에 흡수) |
| INTERNAL | 거래내역서 원장 2-스테이지 재설계 + 마이그레이션 0014~0018 | ✗ |
| INTERNAL | 어드민 패널 대시보드·사용자 목록·원장 조회 (앱 사용자 비가시) | ✗ |
| INTERNAL | 테스트·문서·린트·버전 bump | ✗ |

## 검증 결과

- app-store-ko.md: 602자 / 4000자 한도 ✅
- play-store-ko.md: 266자 / 500자 한도 ✅
- 내부 식별자·커밋 해시·PR 번호 노출 없음 ✅
- INTERNAL 항목이 스토어 본문에 섞이지 않음 ✅
- 대상 버전(1.5.0 / build 34)이 폴더명·본 문서·`make version-check` 3곳에 일관 반영 ✅

## 배포 체크리스트 (출시 노트 외 운영 작업)

1. **DB 마이그레이션**: **불필요** — 이번 BE 릴리즈 범위(`api-v1.3.17..HEAD`)에 `api/alembic/versions/` 신규·수정 없음.
   - 단, 이번 푸시 기능이 사용하는 `notifications`/`device_tokens` 테이블은 **직전 릴리즈(api-v1.3.16)의 0019·0020** 에서 생성된다. 컨테이너는 마이그레이션 자동 적용을 하지 않으므로 운영 head 가 `0020_device_tokens` 인지 먼저 확인할 것(미적용이면 이번 배포 전에 선행).
2. **BE 배포**: **필요** — `services/push/` 신설 및 `push_sender.py` 제거, `config.py` 시크릿 필드 교체, `pyproject.toml` 의존성 변경(firebase-admin 추가, httpx 0.27→0.28). main push 시 Coolify 자동 배포.
   - **env 선행 작업(필수)**: Coolify 에 `GOOGLE_APPLICATION_CREDENTIALS_JSON` 을 **줄바꿈 없는 한 줄 JSON**(`jq -c .`)으로 주입. 미주입 시 `push_enabled=False` 로 **에러 없이 조용히 no-op** 이라 실패를 눈치채기 어렵다. 기존 `FCM_*`/`APNS_*` 는 제거 가능(남아 있어도 `extra="ignore"` 라 무해).
   - **Firebase Console 선행 작업**: Cloud Messaging 에 **APNs 인증키 `.p8` 업로드**. 없으면 iOS 는 토큰만 받고 알림이 도착하지 않는다.
3. **MIN_SUPPORTED_VERSION**: 현재 `1.3.0` — **변경 불필요**. 이번 BE 변경은 앱이 쓰는 API 스키마·엔드포인트를 건드리지 않는다(변경 범위는 푸시 전송 내부 + 어드민 라우터 import). 구버전 앱(1.4.3_33)과 하위호환 확인 완료.
4. **모바일 스토어 제출**: **필요** — `@capacitor/push-notifications` → `@capacitor-firebase/messaging` 네이티브 플러그인 교체, iOS `GoogleService-Info.plist` 추가. OTA 로는 전달 불가하며 빌드 번호를 33 → **34** 로 올렸다.

**실행 순서**: (운영 head 0020 확인) → Coolify env 주입 + Firebase APNs `.p8` 업로드 → main push(BE 자동 배포) → 스토어 제출 → **양 스토어 라이브 확인 후** `.env` `OTA_REQUIRED_NATIVE` 1.1.23 → **1.5.0** 갱신.

## 다음 빌드를 위한 메모

- **`OTA_REQUIRED_NATIVE` 갱신 필수**: 현재 `.env` 값이 `1.1.23` 으로 오래 방치돼 있다. 스토어 라이브 확인 후 `1.5.0` 으로 올리지 않으면, 다음 OTA 번들(신규 Firebase 플러그인 전제)이 구 네이티브(1.4.3_33)에도 내려가 푸시가 무동작한다. 단 올리는 순간 1.4.3 이하 기기는 **이후 모든 OTA** 에서 제외된다.
- **iOS `aps-environment` 미검증**: `App.entitlements` 가 `development` 로 남아 있다. "Firebase 가 자동 라우팅한다"는 전제는 실측된 적이 없다. 아카이브 후 `codesign -d --entitlements - App.app` 으로 확인하고, `development` 로 남으면 `production` 으로 교체 후 재제출할 것. 어긋나면 프로덕션 발송이 **에러 없이 소실**된다.
- **첫 실발송 검증 미완**: 이 프로젝트에서 푸시가 실제로 도달한 적이 아직 0건이다. BE 배포 직후 첫 발송은 신 빌드가 아니라 **스토어에 깔린 1.4.3_33 구 플러그인 클라이언트**로 간다. 데모/리뷰어 계정으로 어드민 답변 1건을 발생시켜 구 바이너리 단말에서 수신·탭까지 확인한 뒤 라이브로 간주할 것. (Android 실기기 / iOS 실기기 스모크 2건이 spec 의 미완 항목으로 남아 있다)
- 구버전 iOS 의 raw-APNs 토큰은 첫 발송 시 `InvalidArgumentError` → 자동 삭제된다. 별도 정리 작업 불필요.
