# 출시 노트 요약 — v1.3.8_32

> 작성일: 2026-07-02
> 비교 기준: app-v1.3.7_31 (2026-07-02) — 직전 OTA. 1.3.5~1.3.7 변경은 이미 OTA로 사용자에게 전달됨.
> 대상 빌드: v1.3.8_32 (준비 중 — release/app-v1.3.8_32 브랜치, bump 커밋 완료)
> 성격: **네이티브 재빌드 + 스토어 제출/재심사 필요** (OTA 아님)

## 네이티브 판정 근거

- `@capacitor/status-bar@^8.0.2` 가 다크테마 커밋(6eb741c)에서 **신규 추가된 네이티브 플러그인**.
- 현재 스토어 라이브 바이너리는 build `_31`(v1.3.0 제출분, 2026-06-20) — 이 플러그인 미포함. OTA 번들은 JS만 교체하므로 네이티브 플러그인을 추가할 수 없음.
- 따라서 상태바 테마 동기화를 실제로 켜려면 build `_32` 네이티브 빌드 + 스토어 재심사 필요.
- (release-scope 의 `ios|android|capacitor.config` 파일 grep 은 package.json 신규 네이티브 의존성을 못 잡음 — `npx cap sync` 미커밋이라 네이티브 프로젝트 파일 변경이 없었음. web-only 오판의 원인.)

## Git 로그 (app-v1.3.7_31..HEAD, --no-merges)

| 해시 | 날짜 | 메시지 |
|------|------|--------|
| 6eb741c | 2026-07-02 | feat(theme): 다크 테마 추가 (팔레트 중심) |
| 85c79c9 | 2026-07-02 | fix(a11y): warning 텍스트 대비 amber-600/orange-600 → 700 (라이트 AA) |
| c83db21 | 2026-07-02 | fix(seed): recalc_group_pnl user_id 인자 누락 수정 |
| bd9b296 | 2026-07-02 | chore(env): .env.example 죽은 SUPABASE_URL·SUPABASE_SECRET_KEY 제거 |
| 563c9d9 | 2026-07-02 | test: 죽은 supabase_url= Settings 인자 정리 |
| 8222e54 | 2026-07-02 | docs(env): .env.example BE_AUTH_ENABLED true·주석 갱신 |
| 52ae195 | 2026-07-02 | fix(test): conftest 미사용 os import 제거 (ruff F401) |
| 3d16508 | 2026-07-02 | chore(lint): eslint advisory warnings 4건 해소 |
| (그 외 docs/backlog·decisions·release-notes·import 가이드 갱신 다수) | | |

## 동기간 spec-history 항목

- `2026-07-02-dark-theme.md` — 팔레트 토큰 기반 다크 테마. globals.css `:root`/`.dark`, ThemeProvider·StatusBarThemeSync(상태바 색 동기화), 설정 > 화면 모드(밝게/어둡게/시스템), semantic-colors 확장.

## 분류표

| 라벨 | 항목 | 출시 노트 반영 |
|------|------|---------------|
| NEW | 다크 테마 (설정 > 화면 모드) + 상태바 색 자동 동기화 (네이티브) | ✓ |
| IMPROVE | 라이트 모드 경고 텍스트 색 대비 강화 (amber/orange 600→700, WCAG AA) | ✓ |
| INTERNAL | seed 인자 수정, .env.example 정리, 죽은 import/상수 정리, eslint warning 해소, docs 갱신, api 테스트 다수 | ✗ |

- 사용자 가시: NEW 1 · IMPROVE 1
- 베이스라인이 app-v1.3.7_31 인 이유: 1.3.5~1.3.7 변경은 이미 OTA로 사용자에게 전달됨 → 이번 스토어 빌드의 실질 신규는 다크 테마(상태바 동기화 포함).

## 검증 결과

- app-store-ko.md / play-store-ko.md: 글자 수는 커밋 전 `LC_ALL=en_US.UTF-8 wc -m` 로 확인 (하단 배포 보고 참조).
- 대상 버전 1.3.8_32: package.json / iOS MARKETING_VERSION / Android versionName 3곳 일치, iOS CURRENT_PROJECT_VERSION = Android versionCode = 32. 폴더명·본 summary·스토어 노트 일치.
- 마이그레이션: 신규 없음.

## 배포 체크리스트 (실행 순서대로)

1. **DB 마이그레이션: 해당 없음** — `app-v1.3.7_31..HEAD` 에 신규/수정 마이그레이션 파일 없음.
2. **BE 배포: 불필요** — api 변경은 `tests/`·`.env.example`·`scripts/seed_demo_data.py` 뿐이라 런타임/의존성 변화 없음. (main push 시 Coolify 가 api/ watch 로 재빌드를 트리거할 수 있으나 배포 런타임 동작 동일.)
3. **MIN_SUPPORTED_VERSION: 변경 불필요** — 현재값 `1.3.0`. api 소스·응답 스키마 변경 없어 구버전 앱 하위호환 유지.
4. **모바일 스토어 제출: 필요 (재심사)** — `@capacitor/status-bar` 신규 네이티브 플러그인 포함. build `_32` 새 빌드 + App Store / Play 제출. `make build app` 이 `npx cap sync` 로 플러그인을 네이티브에 등록함.

**실행 순서**: 마이그레이션(없음) → BE 배포(없음) → 네이티브 빌드/아카이브 → 스토어 제출/재심사. OTA 번들 배포 단계 없음(네이티브 빌드에 포함).

## 다음 빌드를 위한 메모

- **제출 전 실기기 검증 필수**: 다크 모드에서 iOS/Android 상태 표시줄 색이 실제로 화면에 맞춰 어두워지는지 확인 (fail-open 이라 미동작해도 크래시는 없어 코드 검증만으론 못 잡음).
- `@capacitor/status-bar` 는 현재 Podfile/android capacitor gradle 에 미등록 — `make build app` 의 `npx cap sync` 가 등록. 빌드 후 네이티브 프로젝트 변경분을 커밋할지 확인.
- 버전 드리프트 치유됨: 직전 1.3.7 OTA 핫픽스가 package.json 만 올려 ios/android 가 1.3.6 에 남아 있었음 → 이번 bump 로 3곳 모두 1.3.8 정렬.
- api 테스트/tooling 변경은 별도 태그 없이 main 에 병합됨 (app-only 확정). 다음 실제 api 릴리즈 scope 에 자연 포함.
