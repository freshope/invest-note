# 출시 노트 요약 — v1.3.0_31

> 작성일: 2026-06-20
> 비교 기준: app-v1.2.1_29 (직전 **스토어 제출** 네이티브 바이너리, 2026-06-14)
> 대상 빌드: v1.3.0_31 (준비 중 — release/app-v1.3.0_31 에서 bump 완료)

**중요 맥락:** 1.2.2~1.2.6 은 OTA(web-only, build 29 유지), 1.2.7_30 은 secure-storage 네이티브
추가분이나 디바이스 실측서 결함(secure storage hang + AuthProvider race) 발견 후 **미제출 폐기**.
따라서 마지막으로 **스토어에 제출된** 네이티브 바이너리는 1.2.1_29 이고, 1.3.0_31 이 그 이후
누적 사용자 가시 변경 + 탈-Supabase Auth 인프라(dormant)를 담은 **실제 출시 빌드**다.
app/play 노트는 1.2.7-b30 과 동일(같은 baseline 1.2.1).

## 분류표
| 라벨 | 항목 | 출시 노트 반영 |
|------|------|--------------|
| NEW | 종목 상세에서 바로 매수·매도 등록 (1.2.2) | ✓ |
| NEW | 사용자 정의 분석 태그 추가 (1.2.2) | ✓ |
| IMPROVE | 국내·해외 국기 아이콘 구분 (1.2.2) | ✓ |
| IMPROVE | 분석탭 국가 그래프 막대 너비 통일 (1.2.2) | ✓ |
| IMPROVE | 시세·일별 데이터 로딩 속도 (1.2.2) | ✓ |
| FIX | 해외 자산추이 거래일 ET 기준 정규화 (1.2.2) | ✓ |
| FIX | KST 자정 24:00→00:00 표시 (1.2.3) | ✓ |
| INTERNAL | 탈-Supabase Auth Phase 1·2a·2b-1·2b-2·2b-3·2b-4 (BE flow + secure-storage 네이티브) — **서버 플래그 default OFF 라 사용자 체감 동작 변화 0 (dormant)**. 이번 빌드의 네이티브 재제출 사유. | ✗ (dormant) |
| INTERNAL | 디바이스 실측 fix — secure storage thenable hang + AuthProvider flag race (51441c3, BE flow 활성 시에만 영향, 현재 dormant) | ✗ |
| INTERNAL | 어드민 패널·PostHog 예외/버전 추적·사용자정의태그 500 fix(이미 1.2.2 기능 안내) | ✗ |

## 검증 결과
- app-store-ko.md: 485자 / 4000 (1.2.7-b30 재사용, 동일 baseline)
- play-store-ko.md: 219자 / 500
- 내부 식별자/커밋 해시 없음, INTERNAL(auth) 항목 본문 미혼입
- 대상 버전(1.3.0/31) 폴더명·summary 일치
- dedup: 직전 **스토어 제출** 1.2.1 노트(미국주식/S&P500/검색) 항목 제외. 1.2.2/1.2.3 누적 포함.

## 배포 체크리스트 (실행 순서대로)
1. **DB 마이그레이션: 불필요** — 0004/0005/0006 은 이번 릴리즈 직전 **이미 운영 적용 완료**. 이번 app-only 빌드는 스키마 변경 없음.
2. **BE 배포: 불필요** — api 무변경(1.3.5/1.3.6 그대로 라이브). 이번은 app-only.
3. **MIN_SUPPORTED_VERSION: 변경 불필요** — git `.env.production` 빈 값(OFF), 운영 SSOT 는 Coolify. 이번 변경 dormant 라 breaking 없음.
4. **모바일 스토어 제출: 필요** — secure-storage 네이티브 플러그인 포함 빌드(빌드 30→31, 1.2.7_30 폐기 후 재빌드). 🔴 **디바이스 실측은 완료**(iOS/Android × Google/Kakao 로그인 token 200→/v1 200, cold start 영속). Apple provider 만 미검증(콘솔 설정 필요, cutover 전 별도).

**실행 순서**: (마이그레이션/BE 불필요) → 네이티브 빌드 → 스토어 제출.
※ 이번 릴리즈는 전부 dormant — 실제 BE flow 활성화(동결→백필→BE env→`BE_AUTH_ENABLED` flip)는 **별도 cutover**(spec-history 2b-3/2b-4 runbook). 이 출시는 secure-storage 네이티브를 기기에 보급하는 shell 단계.

## 다음 빌드를 위한 메모
- **app-v1.2.7_30 폐기**: 미제출(버그 포함). 1.3.0_31 이 대체.
- **Apple provider**: cutover 전 디바이스 실측 필요(콘솔 JWT-secret 설정 + redirect 등록).
- **cutover 미실행**: 보급 후 별도. `BE_AUTH_ENABLED` flip 은 백필 완료 후 hard precond.
- **PIPA**: user_profiles PII 확대 → 개인정보처리방침/Data Safety 갱신은 flip(실사용) 전 검토.
- **빌드번호 31**: 라이브(28대) 대비 단조 증가. App Store Connect/Play Console 실제 값으로 최종 확인 권장.
