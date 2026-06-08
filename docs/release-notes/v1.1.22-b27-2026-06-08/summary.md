# 출시 노트 요약 — v1.1.22_27

> 작성일: 2026-06-08
> 비교 기준: fe-v1.1.21_26 (2026-06-08, 백엔드 인프라 릴리즈)
> 대상 빌드: v1.1.22_27 (준비 중 — release/fe-v1.1.22_27, 태그 전)

## Git 로그 (fe-v1.1.21_26..HEAD, --no-merges)
| 해시 | 날짜 | 메시지 |
|------|------|--------|
| c6eb96b | 2026-06-08 | chore: bump version fe-v1.1.22_27 |
| 949e92b | 2026-06-08 | docs: issue-* → spec-* 경로 복원 + 참조 갱신 |
| 2359198 | 2026-06-08 | docs: issue-current → spec-history 이동 (OTA spec) |
| 9530d76 | 2026-06-08 | docs: OTA v1 완료 후 백로그 업데이트 |
| 582f250 | 2026-06-08 | docs(ota): be/.env.example LIVE_UPDATE_MANIFEST_URL 예시 |
| ed08cae | 2026-06-08 | feat(ota): Capacitor 자체 호스팅 OTA 라이브 업데이트 v1 |
| fdf3735 | 2026-06-08 | docs: 해외(미국) 주식 v2 방향 확정 + 선행검증 |
| b2aaaae | 2026-06-08 | docs: KIS 앱키 만료·로테이션 가시화 백로그 추가 |

## 동기간 spec-history 항목
- 2026-06-08-capacitor-ota-live-update.md — Capacitor 자체 호스팅 OTA 라이브 업데이트 v1. 웹 자산을 스토어 재심사 없이 OTA 로 교체하는 인프라(`@capgo/capacitor-updater` 플러그인 + R2 JSON 매니페스트 + 결정 API). 사용자 비노출.

## 분류표
| 라벨 | 항목 | 출시 노트 반영 |
|------|------|----------------|
| INTERNAL→IMPROVE(프레이밍) | OTA 라이브 업데이트 v1 — 향후 웹 자산 개선/수정을 스토어 재심사 없이 빠르게 전달 가능 | ✓ (사용자 가치=빠른 업데이트로 프레이밍) |
| INTERNAL | 문서: 해외주식 v2 방향·KIS 앱키 백로그·issue→spec 경로 복원·OTA 사양/결정/백로그 | ✗ |
| INTERNAL | 버전 bump (fe 1.1.22_27, be 1.1.22) | ✗ |

→ 순수 사용자 가시 기능(신규 화면/액션) 없음. OTA 는 비노출 인프라이나, 사용자 체감 가치(앞으로 더 빠른 업데이트 전달)가 정직하게 성립하여 그 각도로만 노트에 반영.

## 검증 결과
- app-store-ko.md: 약 110자 / 4000자 한도 — OK
- play-store-ko.md: 약 60자 / 500자 한도 — OK
- 내부 식별자/커밋 해시/PR 번호 없음
- INTERNAL 항목 본문 미혼입 (OTA 는 "업데이트 방식 개선"으로만 표현, 플러그인/R2 등 내부 비노출)
- 대상 버전 v1.1.22_27 폴더명·summary·노트 본문 일치 (노트 본문엔 버전 미기재 — 톤 컨벤션)

## 배포 체크리스트 (실행 순서대로)
1. **DB 마이그레이션: 불필요** — `supabase/migrations/` 변경 없음(diff 확인).
2. **BE 배포: 필요** — `be/src/.../routers/live_update.py`·`config.py`·`main.py` 신규/변경(OTA 결정 API). main push 시 Coolify 자동 배포. ⚠️ **구버전 앱과 하위호환**: 신규 `POST /live-update/manifest` 는 순수 추가 엔드포인트라 기존 경로 무영향 — breaking 아님.
3. **MIN_SUPPORTED_VERSION: 변경 불필요** — 현재값 유지(빈 값/OFF 또는 기존값). OTA 는 추가 엔드포인트일 뿐 기존 API 스키마/경로 변경 없음 → 구버전 앱 호환 깨짐 신호 없음.
4. **모바일 스토어 제출: 필요** — `fe/` 변경(플러그인 심기 + capacitor.config + provider). **이 빌드(플러그인 포함)가 스토어 승인·라이브돼야 OTA 가 비로소 동작**한다.

**OTA 고유 선행 운영(스토어 제출 전/병행):**
- 운영 BE 에 `LIVE_UPDATE_MANIFEST_URL` env 주입(Coolify) — 비우면 fail-open(OTA 비활성, 앱 정상).
- Cloudflare R2 버킷·커스텀 도메인·릴리즈 `.env` 준비 후 `node scripts/publish-ota.mjs` 첫 발행(레일 점검). 실제 OTA 적용은 스토어 빌드 라이브 + 다음 발행부터.

## 다음 빌드를 위한 메모
- post-store 검증: 실기기 스큐 매트릭스(구네이티브+신웹 차단→force-update 폴백 / builtin 중복 없음)·부팅 실패 자동 롤백·checksum 무결성 — `docs/backlog.md` "OTA post-store 검증".
- OTA v2: 서명/E2E 암호화·단계 롤아웃(%)·델타 업데이트·통계 대시보드 — `docs/backlog.md` "OTA v2 확장".
- release-notes 최상위에 과거 버전 폴더 다수 존재(보관 규칙상 `old/` 이동 대상이나 이번 릴리즈에선 미실행 — 별도 정리 권장).
