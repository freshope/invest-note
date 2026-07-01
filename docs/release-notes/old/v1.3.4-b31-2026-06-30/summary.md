# 출시 노트 요약 — v1.3.4_31 (+ api-v1.3.10)
> 작성일: 2026-06-30
> 비교 기준: app-v1.3.3_31 (2026-06-29)
> 대상 빌드: app-v1.3.4_31 (준비 중, OTA web-only — 스토어 제출 없음) · api-v1.3.10
> 모드: store-notes:skip (OTA web-only → 스토어 노트 미생성, summary.md 만)

## Git 로그 (app-v1.3.3_31..HEAD, --no-merges)
| 해시 | 날짜 | 메시지 |
|------|------|--------|
| 7a71c4c | 2026-06-30 | chore: bump version app-v1.3.4_31 |
| 2b59a1d | 2026-06-30 | chore(auth): .env.example 에 BE_APP_WEB_REDIRECT_URL 추가 (BE-#3 누락분) |
| d6df6fc | 2026-06-29 | refactor(auth): 코드리뷰 — orphan 제거 + write 가드 + 콜백 라우팅 공유 |
| c4bd107 | 2026-06-29 | fix(auth): 코드리뷰 — be_token_issuer 부팅 검증 + verify_key KeyError 방어 |
| a58ca39 | 2026-06-29 | docs: 탈-Supabase 2c 가역 코드 제거 결정 + runbook 진행 로그 |
| 9ab8390 | 2026-06-29 | refactor(auth): supabase-js 물리 제거 + 웹 BE flow 복구 (2c #2) |
| f60d396 | 2026-06-29 | feat(auth): 웹 BE flow client=web 분기 추가 (개발 편의, 운영 dormant) (2c #3) |
| 276825a | 2026-06-29 | feat(auth): Supabase 검증 fallback 제거 — BE 토큰 단독 검증 (2c #1) |

## 동기간 spec-history 항목
- `2026-06-29-auth-2c-remove-supabase.md` — 탈-Supabase Auth Phase 2c 가역 코드 제거. BE Supabase 검증 fallback 제거(#1, BE 토큰 단독 검증), 웹 BE flow client=web 분기(#3, 운영 dormant), supabase-js 물리 제거 + 웹 BE flow 복구(#2).

## 분류표
| 라벨 | 항목 | 출시 노트 반영 |
|------|------|--------------|
| INTERNAL | 2c #1 Supabase 검증 fallback 제거 (BE 토큰 단독 검증) | ✗ (인증 인프라) |
| INTERNAL | 2c #3 웹 BE flow client=web 분기 (운영 dormant) | ✗ (개발 편의·dormant) |
| INTERNAL | 2c #2 supabase-js 물리 제거 + 웹 BE flow 복구 | ✗ (인증 인프라·번들 정리) |
| INTERNAL | 코드리뷰 fix (be_token_issuer 검증·verify_key 방어·orphan·write가드·콜백헬퍼) | ✗ (견고성·정리) |
| INTERNAL | docs(decisions/runbook/spec-history) · .env.example · bump | ✗ |

→ **사용자 가시(NEW/IMPROVE/FIX) 항목 0.** 2c는 인증을 BE 토큰-브로커로 전환한 cutover(이미 라이브) 이후의 **잔존 Supabase 코드 제거**라, 정상 사용자(신 바이너리)의 로그인 동작·화면 결과는 무변화. 스토어 노트가 없는 것도 이 때문(+OTA web-only).

## 검증 결과
- app-store-ko.md: 해당 없음 (store-notes:skip)
- play-store-ko.md: 해당 없음 (store-notes:skip)
- 대상 버전(app 1.3.4_31 / api 1.3.10)이 폴더명·summary.md 에 일치. version-check 통과(app 3곳 1.3.4 build 31).

## 배포 체크리스트 (출시 노트 외 운영 작업 — 실행 순서대로)
1. **DB 마이그레이션: 불필요** — `api/alembic/` 변경 없음(코드만).
2. **BE 배포: 필요** — `api/` 런타임(auth jwt/dependency/config/constants/routers) 변경. main push 시 Coolify 자동 배포. 신규 env `BE_APP_WEB_REDIRECT_URL`(운영은 빈 값 유지 = client=web dormant-503 의도, 주입 불요).
   - ⚠️ **BE-#1(Supabase fallback 제거)은 구앱 하위호환 깨짐(breaking)**: 배포 즉시 Supabase 토큰을 든 구앱이 모든 BE 요청 401. force-update(MIN=1.3.0)가 1.2.x 구앱을 막지만, `ForceUpdateGate`가 비차단 오버레이 + fail-open이라 그 모수(PostHog 14d ~26%·63명)를 완전히 막지 못함 → 정상 케이스는 오버레이 뒤 401, fail-open은 안내 없는 깨진 앱. **legacy~0 게이트 미충족 상태에서 사용자 결정으로 배포 진행.** 롤백 = `276825a` revert 재배포.
3. **MIN_SUPPORTED_VERSION: 현재 `1.3.0` 유지 (변경 불필요)** — app-v1.3.4 는 OTA web-only 라 스토어에 새 네이티브 바이너리가 없음(native versionName 은 1.3.0_31 유지). MIN 인상은 양 스토어 승인된 네이티브 버전 대상이어야 하므로 1.3.4 로 올릴 수 없음. 구앱 차단은 기존 MIN=1.3.0 이 담당.
4. **모바일 스토어 제출: 불필요** — OTA web-only(`✅ 재심사 불필요`). OTA 번들 배포로 반영, 빌드 번호 31 유지. 누적 변경은 다음 네이티브 제출 때 스토어 노트로 묶임.

**실행 순서**: (마이그레이션 없음) → BE 배포(main push, env 변경 없음) → OTA 번들 배포(web 자산).

## 다음 빌드를 위한 메모
- **BE-#1 배포 게이트 강행**: 6/30 측정 legacy 14d 26.4%(flat)·7d 1.4%·3d 0%. 활성 코어는 100% BE flow지만 비활성 구앱 꼬리(63명)가 미배수. 배포 후 락아웃 모니터링 필요(`scratchpad/monitor_be_flow.sh`).
- **더 안전했던 미실행 옵션**: issuer-logging(decode_oidc_jwt 가 BE vs fallback 어느 issuer로 검증했는지 로깅) → 24h = 실제 401 볼륨(native_build 는 proxy). 배포 후라도 추가하면 실측 가능.
- **2c 비가역 단계 잔여**: `SUPABASE_*` env 제거·`supabase/` 디렉토리·클라우드 정리·PIPA. 코드의 `supabase_url`/`secret_key`/`delete_user`(계정삭제 IdP) 유지가 이 단계 의존.
- 웹 BE flow(client=web)는 운영 dormant — 개발 시 `BE_APP_WEB_REDIRECT_URL` 로컬 설정 시에만 활성.
