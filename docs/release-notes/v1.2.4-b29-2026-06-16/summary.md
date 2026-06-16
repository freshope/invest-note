# 출시 노트 요약 — v1.2.4_29

> 작성일: 2026-06-16
> 비교 기준: app-v1.2.3_29 (2026-06-15)
> 대상 빌드: v1.2.4_29 (release/app-v1.2.4_29 브랜치, bump 커밋 완료 — 태그 전)
> 모드: store-notes:skip (OTA web-only — 스토어 노트 생략, summary만)

## Git 로그 (app-v1.2.3_29..HEAD, --no-merges)

| 해시 | 날짜 | 메시지 |
|------|------|--------|
| b71a4ed | 2026-06-16 | chore: bump version app-v1.2.4_29 |
| 32dcbc7 | 2026-06-16 | docs(decisions): Supabase DB 종속성 제거(포터블 RLS, expand/contract) 결정 기록 |
| b7b1377 | 2026-06-16 | feat(api): RLS auth.uid 분기·auth.users FK 제거 (contract, 적용 보류) |
| fc869c6 | 2026-06-16 | feat(api): RLS를 표준 PostgreSQL 객체로 치환 (무중단 expand) |
| 92007c9 | 2026-06-16 | chore(supabase): 이메일 회원가입 비활성화로 bounce 어뷰징 차단 |
| 711401e | 2026-06-15 | feat(app): PostHog 버전별 점유율용 앱 버전 super property 등록 |

## 동기간 spec-history 항목

- 없음 (이번 구간 신규 spec 파일 없음 — 결정은 docs/decisions.md 2026-06-16 항목에 기록)

## 분류표

| 라벨 | 항목 | 출시 노트 반영 |
|------|------|--------------|
| INTERNAL | RLS를 표준 PostgreSQL 객체로 치환 (expand) — Supabase 고유 객체 의존 제거, 사용자 가시 변화 없음 | ✗ |
| INTERNAL | RLS contract 마이그레이션 추가 (적용 보류, migrations_pending) | ✗ |
| INTERNAL | 이메일 회원가입 비활성화 (OAuth 전용 — 봇 bounce 어뷰징 차단, 정상 사용자 동선 무영향) | ✗ |
| INTERNAL | PostHog 앱 버전 super property (분석 계측 — 사용자 가시 변화 없음) | ✗ |
| INTERNAL | 버전 bump / 결정 로그 문서화 | ✗ |

→ **사용자 가시(NEW/IMPROVE/FIX) 항목 없음.** 이번 릴리즈는 BE 인프라(DB 종속성 제거)·인증 설정·분석 계측 전용.

## 검증 결과

- app-store-ko.md: 해당 없음 (store-notes:skip)
- play-store-ko.md: 해당 없음 (store-notes:skip)
- 대상 버전(1.2.4 / build 29)이 폴더명·본 summary·버전 파일 3곳(`make version-check` 통과)과 일치
- INTERNAL 항목만 존재 — 스토어 본문 대상 없음

## 배포 체크리스트 (실행 순서대로)

1. **DB 마이그레이션: 필요** — 신규 `supabase/migrations/033_portable_rls_expand.sql`.
   **BE 배포(main push) 전에 먼저** 운영 DB에 적용: `supabase db push --linked` (033만 적용됨).
   - ⚠️ `supabase/migrations_pending/034_portable_rls_contract.sql` 은 `migrations/` 밖이라 `supabase db push` 가 스캔하지 않음 → **이번에 적용되지 않음**. 신 BE 전면 배포·안정 확인 후 `migrations/` 로 이동해 별도 push.
2. **BE 배포: 필요** — `api/src` 런타임(db.py·constants·accounts·me.py) + `pyproject.toml` 변경. main push 시 Coolify 자동 배포. expand(033) 적용 상태에서 구 BE·신 BE 모두 동작(롤백 안전).
3. **MIN_SUPPORTED_VERSION: 불필요** — 현재값 빈 값(OFF). 이번 변경은 전부 하위호환(expand/contract 설계가 구버전 BE/앱 호환 보장) → breaking 신호 없음, 게이트 인상 불필요.
4. **모바일 스토어 제출: 불필요** — app 변경은 OTA web-only(빌드 29 유지). OTA 번들 배포로 반영, 스토어 재심사 없음. 누적 변경은 다음 네이티브 제출 때 스토어 노트로 묶임.

**실행 순서**: 033 마이그레이션 (`supabase db push --linked`) → BE 배포 (main push) → OTA 번들 배포(app). 신 BE 안정 확인 후 → 034 contract 별도 적용.

## 다음 빌드를 위한 메모

- **034 contract 적용**이 이번 릴리즈의 미완 후속: 신 BE 라이브·스모크 확인 후 `migrations_pending/034` → `migrations/` 이동, 커밋, push, `supabase db push`. 적용 시 `auth.uid()` 분기·`auth.users` FK 제거로 디커플 완료(이후 구 BE 롤백 불가).
- **Phase 2**(별도): 실제 DB 이관(Supabase → 표준 PostgreSQL), 마이그레이션 도구 supabase CLI → Alembic 등 검토.
- 로컬 dev DB는 검증 중 `supabase db reset` 으로 초기화됨 — 종목 시드 재적재 완료(KR/US), 데모 데이터·재로그인은 사용자가 진행.
- 다음 네이티브(스토어) 제출 시 `release-notes` 를 `since app-v1.2.3_29`(또는 마지막 네이티브 제출 태그)로 돌려 그동안의 OTA-only 누적 변경을 스토어 노트로 묶을 것.
