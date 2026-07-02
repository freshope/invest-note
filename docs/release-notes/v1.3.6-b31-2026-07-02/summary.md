# 출시 노트 요약 — v1.3.6_31

> 작성일: 2026-07-02
> 비교 기준: app-v1.3.5_31 (2026-07-01 릴리즈 머지)
> 대상 빌드: v1.3.6_31 (준비 중 — release/app-v1.3.6_31 브랜치, bump 커밋 완료)
> 모드: `store-notes:skip` (OTA web-only — 빌드 31 유지, 스토어 노트 미생성)
> 마지막 네이티브 제출: app-v1.3.0_31 (build 30→31). 1.3.1~1.3.6 은 OTA-only 로 build 31 공유.

## Git 로그 (app-v1.3.5_31..HEAD, --no-merges)

| 해시 | 날짜 | 메시지 |
|------|------|--------|
| 26eb2ea | 2026-07-02 | chore: bump version app-v1.3.6_31 |
| 878a305 | 2026-07-02 | feat(settings): 계좌 삭제 안내·폼 필드 정비 |
| 053273a | 2026-07-02 | style(import): 일괄등록 안내 문구 줄바꿈·중앙정렬 정리 |
| a1408bc | 2026-07-01 | fix(import): 증권사-파일 미스매치 시 명확한 안내 (500/빈결과 → 400) |
| 7acc07e | 2026-07-01 | feat(forms): 폼 검증·제출 오류를 toast 로 통일 (모바일 가시성) |
| 3fe9f49 | 2026-07-01 | fix(records): FAB 등록 버튼 aria-hidden 포커스 경고 해소 |
| 2ae6c1b | 2026-07-01 | fix(records): 거래 등록 종목 칩 표시 개선 |
| 8802c89 | 2026-07-01 | fix(records): 등록 흐름 코드리뷰 반영 + 개발 검수 반영 |
| ff55344 | 2026-07-01 | refactor(admin): X-Admin-Token 트리거 인프라 제거 + 콜백 실패 HTML 응답 |
| b330f04 | 2026-07-01 | feat(records): 신규 가입자 활성화 개선 — 등록 허들 통합 + 계좌번호 매칭 |
| 8454d4c | 2026-07-01 | refactor(auth): 2c 최종 teardown — 런타임 Supabase 결합 제거 |

(docs 전용 커밋 4건 생략: 8fcaba8 / 7f8701d / 959bd3e / 8befc5f / 7084cf4)

## 동기간 spec-history 항목

- 2026-07-01-activation-register-flow.md — 신규 가입자 활성화 개선: 등록 허들 통합 + 내역서 계좌번호 매칭으로 올바른 계좌 자동선택
- 2026-07-01-auth-2c-teardown.md — 2c 최종 teardown: BE 런타임에서 Supabase 결합 완전 제거
- 2026-07-01-admin-auth-hygiene.md — 어드민 인증 위생 정리: X-Admin-Token 트리거 인프라 제거

## 분류표

| 라벨 | 항목 | 출시 노트 반영 |
|------|------|--------------|
| NEW/IMPROVE | 신규 가입자 활성화 개선 — 등록 허들 통합 + 내역서 계좌번호로 계좌 자동선택 | ✓ |
| IMPROVE | 폼 검증·제출 오류를 toast 로 통일 (모바일 가시성 향상) | ✓ |
| IMPROVE | 계좌 삭제 안내·폼 필드 정비 (설정) | ✓ |
| IMPROVE | 일괄등록 안내 문구 정리 (줄바꿈·중앙정렬) | ✓ |
| FIX | 일괄등록 증권사-파일 미스매치 시 명확한 안내 (500/빈결과 → 400) | ✓ |
| FIX | 거래 등록 종목 칩 표시 개선 | ✓ |
| INTERNAL | FAB 등록 버튼 aria-hidden 포커스 경고 해소 (a11y) | ✗ |
| INTERNAL | 등록 흐름 코드리뷰·개발 검수 반영 | ✗ |
| INTERNAL | 어드민 X-Admin-Token 트리거 인프라 제거 + 콜백 실패 HTML 응답 | ✗ |
| INTERNAL | 2c 최종 teardown — BE 런타임 Supabase 결합 제거 (배포 영향 有 → 아래 체크리스트) | ✗ |

분류: NEW/IMPROVE 4 · FIX 2 · INTERNAL 4

## 검증 결과

- app-store-ko.md: 해당 없음 (store-notes:skip)
- play-store-ko.md: 해당 없음 (store-notes:skip)
- 대상 버전 일치: 폴더명 v1.3.6-b31 = package.json/iOS/Android 1.3.6 build 31 = 태그 app-v1.3.6_31 ✓
- api 버전: pyproject.toml 1.3.12 (독립 SemVer, 모바일과 무관) ✓
- 작업 트리: 추적 파일 clean. untracked `supabase/` 는 Supabase CLI 로컬 산출물(.temp/signing_keys/snippets) — 릴리즈 무관

## 배포 체크리스트 (실행 순서대로)

1. **DB 마이그레이션: 필요** — 신규 `api/alembic/versions/0013_accounts_account_number.py`
   (accounts.account_number nullable TEXT 컬럼 추가). 이 프로젝트는 **Alembic 소유**(supabase 아님).
   신규 BE accounts_repo/router 가 이 컬럼을 참조하므로 **BE 배포(=main push)보다 먼저** 운영 DB 에 적용해야 함 — 순서 뒤바뀌면 계좌 조회에서 운영 500.
   적용 명령(운영 DB 대상, 사용자 confirm 후): `cd api && poetry run alembic upgrade head` — 운영 PG 는 호스트 포트 미publish 라 VPS SSH + 컨테이너 경유 실행. (컬럼 추가뿐이라 superuser 불필요, invest_note_app 경로 적용.)

2. **BE 배포: 필요** — api/src 런타임 대폭 변경:
   - account_number passthrough (accounts_repo/router/schema/portfolio)
   - 2c 최종 teardown — 런타임 Supabase 결합 제거 (identity_provider 삭제, be_token/config/main/auth/me 정리)
   - 어드민 X-Admin-Token 인프라 제거 (admin 라우터 -132줄)
   - trades 라우터 변경
   main push 시 Coolify 가 자동 배포 (Watch Paths). **마이그레이션 적용 후 push.**

3. **MIN_SUPPORTED_VERSION: 현재 `1.3.0` — 변경 검토 필요 (사용자 판단)**
   - 2c teardown 이 BE 런타임의 Supabase 결합을 **완전 제거**한다. auth 컷오버(1.3.2)보다 이전인 1.3.0/1.3.1 앱이 구 Supabase-direct 경로에 의존한다면 이번 BE 배포 후 깨질 수 있음.
   - account_number(schema optional 추가)·폼/toast 변경은 additive → 그 자체로는 breaking 아님.
   - MIN 을 올리기로 하면 `api/.env.production` 변경 → BE 재배포 수반. **양 스토어 라이브 앱 lockout 위험이 있으므로 신중히 판단** (자동 결정하지 않음).

4. **모바일 스토어 제출: 불필요** — OTA web-only, 빌드 31 유지. OTA 번들 배포로 반영. 누적 변경은 다음 네이티브 제출 때 `since app-v1.3.0_31` 로 묶어 스토어 노트 작성.

**실행 순서**: (1) 마이그레이션 0013 적용 → (2) main push = BE 자동 배포 → (3) OTA 번들 배포. 스토어 제출 없음.

## 다음 빌드를 위한 메모

- **다음 네이티브 제출 시**: `release-notes` 를 `since app-v1.3.0_31` 로 돌려 1.3.1~1.3.6 OTA-only 누적 변경을 한 번에 스토어 노트로 묶는다.
- **MIN_SUPPORTED_VERSION 결정 보류 중** — 2c teardown 배포 후 구버전 앱(1.3.0/1.3.1) 실동작 모니터링 권장. 문제 시 MIN 인상 검토.
- account_number 매칭은 FE-side, BE 는 raw passthrough. 유니크/인덱스 없음(재발급·사용자 스코프 엣지 고려) — 향후 중복/정규화 이슈 관찰.
