# 출시 노트 요약 — v1.2.7_30

> 작성일: 2026-06-20
> 비교 기준: app-v1.2.1_29 (직전 **스토어 제출** 네이티브 바이너리, 2026-06-14)
> 대상 빌드: v1.2.7_30 (준비 중 — release/app-v1.2.7_30 에서 bump 완료)

**중요 맥락:** 빌드 번호가 1.2.1~1.2.6 동안 _29 로 고정(OTA web-only). 즉 마지막으로
**스토어에 제출된** 네이티브 바이너리는 1.2.1_29 이고, 1.2.2~1.2.6 의 사용자 가시 변경은
OTA 로만 전달됐다(스토어 미제출). 이번 1.2.7_30 은 secure-storage 네이티브 플러그인 추가로
**네이티브 재제출**이 필요하므로, 그동안 OTA 로 나간 사용자 가시 변경을 누적해 스토어 노트를 작성.

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
| INTERNAL | 탈-Supabase Auth Phase 1·2a·2b-1·2b-2·2b-3·2b-4 (BE flow + secure-storage) — **서버 플래그 default OFF 라 사용자 체감 동작 변화 0 (dormant)** | ✗ (dormant) |
| INTERNAL | secure-storage 네이티브 플러그인 추가 + cap sync (이번 재심사 사유) | ✗ |
| INTERNAL | 어드민 패널·누적 사용자 차트·멀티 게시판(어드민) | ✗ (앱 비가시) |
| INTERNAL | RLS 제거 → 앱 레이어 user_id 필터, supabase CLI→Alembic 전환 | ✗ |
| INTERNAL | PostHog 예외 추적·버전 super property, KIS 레이트리밋 상향 | ✗ |
| INTERNAL | 사용자 정의 태그 재추가 시 500 수정(이미 1.2.2 에서 기능 안내됨) | ✗ |

## 검증 결과
- app-store-ko.md: 한도 4000자 내 (정중체, 직전 노트 톤 일치)
- play-store-ko.md: 한도 500자 내
- 내부 식별자/커밋 해시 없음, INTERNAL 항목 본문 미혼입
- 대상 버전(1.2.7/30) 폴더명·summary 일치
- dedup: 직전 **스토어 제출** 1.2.1 노트(미국주식/S&P500/검색) 항목은 제외. 1.2.2/1.2.3 노트는 OTA 라 스토어 미제출 → 이번에 누적 포함.

## 배포 체크리스트 (실행 순서대로)
1. **DB 마이그레이션: 필요** — 신규 `0004_auth_identities` / `0005_user_profiles` / `0006_auth_token_store` (Alembic). api 1.3.5 는 dormant 라 **기동에는 불필요**하나 이번 릴리즈 스키마이며 **cutover flip 전 적용 필수**. 적용: `api/alembic` (dry-run→confirm). 0001~0003 은 기존 배포에서 적용됨.
2. **BE 배포: 필요** — api 1.3.4→1.3.5 (`be_auth_enabled` 플래그, auth_identity, app_config passthrough). main push 시 Coolify 자동 배포. **하위호환**(플래그 default OFF·BE 토큰 env 미주입 → dormant, 구앱 무영향).
3. **MIN_SUPPORTED_VERSION: 변경 불필요** — git `.env.production` 빈 값(OFF), 운영 SSOT 는 Coolify. 이번 변경은 dormant 라 breaking 없음 → 유지.
4. **모바일 스토어 제출: 필요** — secure-storage 네이티브 플러그인 추가(빌드 29→30). 🔴 **제출 전 디바이스 실측 1회**(secure storage round-trip / WebCrypto S256) — 코드로 못 잡음.

**실행 순서**: 마이그레이션(0004/0005/0006) → BE 배포(main push, 자동) → 디바이스 실측 → 스토어 제출.
※ 단 이번 릴리즈는 전부 dormant — 실제 BE flow 활성화(동결→백필→BE env→플래그 flip)는 **별도 cutover** 단계(spec-history 2b-3/2b-4 runbook).

## 다음 빌드를 위한 메모
- **cutover 미실행**: 이번 출시는 secure-storage 네이티브를 기기에 보급하는 shell 단계. BE flow 활성화는 보급 후 별도 진행(`BE_AUTH_ENABLED` flip).
- **빌드 번호**: 30 은 직전 라이브 29 대비 단조 증가 — App Store Connect / Play Console 실제 값으로 최종 확인 권장(특히 Play versionCode).
- **PIPA**: user_profiles PII 확대 → 개인정보처리방침/Data Safety 갱신은 flip(실사용) 전 검토(backlog ⑥).
