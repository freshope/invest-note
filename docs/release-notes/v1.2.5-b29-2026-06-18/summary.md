# 출시 노트 요약 — v1.2.5_29 (app) · api-v1.3.1 · admin-v0.1.1

> 작성일: 2026-06-18
> 비교 기준: app-v1.2.4_29 (2026-06-16) / 운영 main 대비
> 대상 빌드: app v1.2.5_29 (OTA web-only, build 29 유지) · api 1.3.1 · admin 0.1.1 — 준비 중(release 브랜치)
> 모드: store-notes:skip (OTA web-only → 스토어 노트 미생성, summary 만)

## Git 로그 (app-v1.2.4_29..HEAD, --no-merges)

| 해시 | 날짜 | 메시지 |
|------|------|--------|
| 4dfe0af | 2026-06-18 | chore: bump version app-v1.2.5_29 |
| a544e6f | 2026-06-18 | refactor(api): 마이그레이션을 invest_note_app 단일 role 로 실행 |
| af51475 | 2026-06-18 | docs: spec-current → spec-history/2026-06-18-remove-rls.md 이동 |
| 3de6c75 | 2026-06-18 | docs: RLS 제거 반영 — roadmap·backlog |
| d81e928 | 2026-06-18 | fix(api): code-review 후속 — pnl_sync user_id scope 외 |
| c518fbe | 2026-06-18 | refactor(api): RLS 제거 — 앱 레이어 user_id 필터로 단일화 |
| 55943c2 | 2026-06-18 | docs: spec-current → spec-history/2026-06-18-admin-panel.md |
| 85fbb7e | 2026-06-18 | docs: 어드민 패널 설계 결정 기록 |
| e13cddb | 2026-06-18 | fix(admin): 명시적 null PATCH 422 거부 + dead code 제거 |
| 873deff | 2026-06-18 | feat(admin): 어드민 패널 1차 증분 + 로컬 dev 포트/스택 정비 |
| 0077c8d | 2026-06-17 | feat(app): PostHog 전역 예외 자동 추적 활성화 |
| (그 외) | 2026-06-16~17 | alembic 전환·FORCE RLS(035/036)·표준 PG RLS contract 등 — api-v1.3.0 라인 |

## 동기간 spec-history 항목

- `2026-06-17-alembic-migrations.md` — supabase CLI → Alembic 마이그레이션 도구 전환
- `2026-06-18-admin-panel.md` — 어드민 패널 1차 증분 (인증 재사용·격리)
- `2026-06-18-remove-rls.md` — RLS 전면 제거, 사용자 격리를 앱 레이어 user_id 필터로 단일화

## 분류표

| 라벨 | 항목 | 출시 노트 반영 |
|------|------|---------------|
| INTERNAL | RLS 전면 제거 (DB 격리 → 앱 레이어 user_id 필터) | ✗ — 사용자 가시 변화 없음(외부 API 계약 불변) |
| INTERNAL | 어드민 패널 1차 증분 (운영자용, 정적 SPA) | ✗ — 앱 사용자 비대면(운영자 도구) |
| INTERNAL | Alembic 마이그레이션 도구 전환 + role 단일화 | ✗ |
| INTERNAL | PostHog 전역 예외 자동 추적 (app) | ✗ — 사용자 비가시(분석 계측) |
| INTERNAL | FORCE RLS(035/036)·표준 PG RLS — api-v1.3.0 라인 | ✗ — 대부분 운영 적용 완료(2026-06-17) |

**→ 이번 빌드에 사용자 가시(NEW/IMPROVE/FIX) 변경 0건.** app OTA 번들은 분석 계측(PostHog 예외 추적)만 담고 화면/동작 변화 없음. 다음 네이티브 제출 시 `since app-v1.2.4_29`(또는 마지막 네이티브 태그)로 묶어 스토어 노트 작성.

## 검증 결과

- app-store-ko.md / play-store-ko.md: **해당 없음 (store-notes:skip)**
- 버전 일치: app 3곳 1.2.5 build 29 (`make version-check` 통과) · api 1.3.1 · admin 0.1.1 — 폴더명·태그와 일치
- 대표 태그: `app-v1.2.5_29` (모바일 우선)

## 배포 체크리스트 (출시 노트 외 운영 작업)

이 릴리즈는 **마이그레이션 순서가 일반과 반대**다 — 아래 순서 엄수.

1. **DB 마이그레이션: 필요 — `0002_drop_rls`** (prod 현재 `0001_baseline` → `0002_drop_rls`). RLS 정책·FORCE·`current_user_id()` 제거.
   - ⚠️ **마이그레이션 선행 금지(일반 규칙의 예외).** RLS 제거 특성상 마이그레이션을 먼저 적용하면 *구 BE가 RLS에 의존*(`list_accounts` 무필터)하여 **cross-user leak**. 반대로 코드 먼저면 사이 구간은 "조회 0행" 기능 blip(leak 아님).
   - 실행 role: **`invest_note_app`(app role)로 충분** — prod 객체는 app 소유(2026-06-17 lift-shift + a544e6f baseline role 통일). superuser(postgres)로 해도 무방.
   - prod api 컨테이너에 alembic 미포함(Dockerfile src-only) → `docker exec <prod_db> psql` 로 `0002_drop_rls` upgrade SQL 적용 + `alembic_version`을 `0002_drop_rls`로 갱신(baseline stamp 관행). 접근법: memory `project_prod_db_access`.
2. **BE 배포: 필요** — api 1.3.1 (RLS 제거 + admin 라우트). main push 시 Coolify 자동 배포. 외부 API 계약 불변 → 스토어 라이브 앱과 하위호환.
3. **MIN_SUPPORTED_VERSION: 변경 불필요** — 현재값 빈 값(OFF). RLS 제거는 응답 shape·엔드포인트 불변이라 구버전 앱 호환.
4. **모바일 스토어 제출: 불필요** — OTA web-only(빌드 29 유지). app 1.2.5 는 OTA 번들 배포로 반영. admin 정적 SPA 배포는 범위 밖(별도/미배포 — ADMIN_EMAILS 미설정 시 라우트 무통과라 안전).

**실행 순서 (이 릴리즈 특수):**
1. `git push origin develop && git push origin main` → Coolify 새 BE 자동 배포
2. **즉시** prod DB에 `0002_drop_rls` 적용 + `alembic_version` 갱신 → RLS off, 정상화
3. OTA 번들 배포 (app 1.2.5)
4. (정리) Coolify `ADMIN_DATABASE_URL` 제거(미사용) + invest_note_admin 비밀번호 회전

## 다음 빌드를 위한 메모

- **0002_drop_rls 마이그레이션 docstring/스펙이 "superuser 필요"로 기술**됨(작성 시점 dev 객체가 postgres 소유였던 근거). a544e6f 로 baseline role 통일 + prod 객체 app 소유라 실제론 **app role 로 충분** — 다음에 docstring 정합화 검토(기능 영향 없음, superuser 도 동작).
- **라우터 인라인 user_id 필터 회귀 가드 미비**(backlog 등록). 현재 실DB 격리 테스트는 repo 함수만 커버, `get_trade_count` 등 라우터 인라인 쿼리 미커버 → HTTP+실DB e2e 후속.
- app OTA 누적: 이번 빌드는 사용자 가시 변화 0(분석 계측만). 다음 **네이티브 제출** 때 `since app-v1.2.4_29`(또는 마지막 네이티브 태그)로 OTA-only 누적 변경을 묶어 스토어 노트 작성.
