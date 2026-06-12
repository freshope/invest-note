# 출시 노트 요약 — v1.1.23_28
> 작성일: 2026-06-09
> 비교 기준: fe-v1.1.22_27 (2026-06-08)
> 대상 빌드: v1.1.23_28 (준비 중 — release/fe-v1.1.23_28 브랜치, bump 완료)

## Git 로그 (fe-v1.1.22_27..HEAD, --no-merges)
| 해시 | 날짜 | 메시지 |
|------|------|--------|
| f7594dd | 2026-06-09 | chore: bump version fe-v1.1.23_28 |
| ad0c534 | 2026-06-09 | fix(ota): OTA manifest 요청/URL 견고성 보강 |
| 467cc0b | 2026-06-09 | chore: fe OTA 플래그 활성화 (fe_OTA := 1) |
| 6892d56 | 2026-06-08 | docs: release-notes 과거 버전 폴더 old/ 보관 |

## 동기간 spec-history 항목
- 없음

## 분류표
| 라벨 | 항목 | 출시 노트 반영 |
|------|------|----------------|
| IMPROVE | OTA manifest 요청/URL 견고성 보강 — capacitor.config.ts 의 API_BASE 를 프로덕션 리터럴로 하드코딩(dev/staging env 누출 방지), BE ManifestRequest 검증 완화(필드 누락 시 422 대신 fail-open) | ✓ (자동 업데이트 안정성으로 표현) |
| INTERNAL | fe OTA 플래그 활성화 (Makefile release-scope 판정용) | ✗ |
| INTERNAL | release-notes 과거 폴더 old/ 보관 (docs 정리) | ✗ |
| INTERNAL | 버전 bump | ✗ |

> 비고: 사용자 화면에 보이는 신규 기능/수정은 없음. 직전 1.1.22 에서 announce 한 OTA 자동 업데이트 메커니즘의 견고성 보강 연속 빌드. 정직하게 "자동 업데이트 안정성" 한 가지 테마로만 작성.

## 검증 결과
- app-store-ko.md: 한도 4000자 — 충분히 미달
- play-store-ko.md: 한도 500자 — 충분히 미달
- 내부 식별자/커밋 해시/PR 번호 노출 없음
- INTERNAL 항목 본문 미혼입
- 버전 표기(1.1.23 / 28) 폴더명·summary·양쪽 노트 일치

## 배포 체크리스트 (출시 노트 외 운영 작업 — 실행 순서대로)
1. **DB 마이그레이션: 불필요** — supabase/migrations/ 변경 없음
2. **BE 배포: 필요** — be/src/.../live_update.py 런타임 코드 + pyproject.toml 변경. main push 시 Coolify 자동 배포. (검증 완화 방향이라 스토어 구버전 앱과 하위호환)
3. **MIN_SUPPORTED_VERSION: 변경 불필요** — 현재값 빈 값(OFF) 유지. BE 변경이 검증을 완화하는 방향(필드 필수 제거)이라 구버전 클라이언트가 깨지는 breaking 신호 없음
4. **모바일 스토어 제출: 필요** — fe/capacitor.config.ts 네이티브 config 변경(versionCode 28 bump). 새 앱 빌드 + App Store/Play 제출 필요 (OTA web-only 아님)
- **실행 순서**: (마이그레이션 없음) → main push 로 BE 자동 배포 → 모바일 빌드/아카이브/스토어 제출

## 다음 빌드를 위한 메모
- capacitor.config.ts 의 API_BASE 하드코딩은 이번 네이티브 빌드가 스토어에 나가야 실제 적용됨(기존 스토어 바이너리는 종전 env-or-literal 값 유지 — 클린 빌드에선 실효 동일).
- 이번 빌드부터 OTA 견고성 보강이 반영되므로, 이후 web-only 변경은 OTA 번들 배포(빌드번호 유지)로 전달 가능.
