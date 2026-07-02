# 다크 테마 추가 (팔레트 중심) 사양서

> 승인 플랜: `~/.claude/plans/flickering-seeking-hartmanis.md` 를 spec-current 형식으로 분해한 것.
> **FE 전용 작업 — BE(FastAPI) 변경 없음.** 구현 fe-engineer, 검증 integration-qa.

## 배경 / 목적

`docs/backlog.md` "다크 테마 추가" 항목(2026-07-02 실현가능성 조사 완료)을 구현한다.
투자노트는 2026-04-25에 완전한 다크 모드가 있었으나 2026-04-28(`ca2610b`)에 "라이트 전용"으로 제거됐다.
단 CSS 변수 인프라(`globals.css :root` shadcn 토큰)는 유지돼 컴포넌트 ~270곳이 이미 `bg-muted`/`text-foreground`
같은 토큰 기반이다. 즉 **`.dark {}` 팔레트만 채우면 대부분 자동 적용**된다.

**원칙(사용자 요구):** 테마는 최대한 팔레트(CSS 변수)로 컨트롤하고 개별 `dark:` 처리는 최소화한다.
단순 revert(옛 `dark:` 26곳 재살포)가 아니라, 반복 semantic 색을 **팔레트 토큰으로 승격**한다.
`PNL_COLORS`(`app/src/lib/constants/pnl-colors.ts`)가 `--rise`/`--fall`을 `.text/.bg/.bgSoft/.border`로
토큰화한 패턴을 표준으로 삼아 `SEMANTIC_COLORS` 상수를 만들고, soft 배경은 알파(`bg-[var(--success)]/10`)로 표현한다.
→ 프로젝트 커스텀 컴포넌트의 `dark:` 프리픽스 **0개** 목표, 색 조정은 팔레트 한 곳에서만.

## 범위 (Scope)

**포함:**
- 팔레트 복원(`ca2610b`의 옛 `.dark` 블록 재사용) + `@custom-variant dark` 복원 + 신규 semantic 토큰
- 테마 인프라 복원(next-themes, ThemeProvider, ThemedToaster, layout 배선)
- **설정 탭 테마 선택 메뉴(시스템/라이트/다크 3-way)** — 필수 사용자 요구
- semantic 색 토큰 승격(severity-styles, ADHERENCE_CONFIG, CountryBadge, import 패널)
- Tier 2: TradeCard 배경 토큰화 · 차트 fallback hex 토큰화
- Tier 3: Capacitor 상태바 다크 대응

**제외 (명시):**
- **브로커 배지 대비 조정 — 하지 않는다** (사용자 확정. 일회성 브랜드색이라 팔레트 오염 방지 위해 그대로 둠)
- 카카오/구글 OAuth 브랜드색 승격 (일회성 브랜드색)
- shadcn 원본(`ui/*.tsx`)의 표준 `dark:` 프리픽스 (래퍼 경유라 영향 제한적, 유지)
- BE 변경 일체

## 사전 확인 결과 (현황)

- `next-themes`: package.json 미존재 → 설치 필요
- `ThemeProvider.tsx` / `theme.ts` / `AppearanceSection.tsx`(+테스트): 미존재 → `ca2610b~1`에서 복원
- `AppToaster.tsx`: 존재 → `ThemedToaster.tsx`로 교체
- `base/ToggleGroup.tsx` + `ui/toggle-group.tsx`: **이미 존재** → 래퍼 신규 생성 불필요
- `globals.css`: `@custom-variant dark` 없음, `.dark` 블록 없음, semantic 토큰(`--success` 등) 없음
- 설정 페이지 현재 섹션: 자산 관리 / 소식 / 고객 지원 / 약관·정책 / 계정 (옛 "내 정보" 섹션 없음)

## 작업 단위

> 입도 규칙: Tier가 아니라 **파일이 단위**(1 요청 = 1 파일). intra-tier 는 컴파일/참조 순서로 의존을 건다.
> **1a 팔레트가 모든 것의 토대 — 가장 먼저.**

### Tier 1a — 팔레트 (관문)

#### 1. [FE] `app/src/app/globals.css` — 팔레트 + semantic 토큰
- `@import` 다음 줄에 `@custom-variant dark (&:is(.dark *));` 복원
  - ⚠️ **함정: 이게 없으면 `.dark` 토큰이 Tailwind 유틸(`bg-*` 등)에 안 먹는다. 필수.**
- `ca2610b~1`의 옛 `.dark {}` 블록 복원 (`--background:#17171C`, `--card:#1E1E24`, `--muted:#2C2C34` 등 옛 값 그대로)
- `--fall`을 **다크에서만** 밝게 조정(어두운 배경 대비 확보, 예: `#4C9AEE` 계열). `--rise`는 옛대로 유지 가능
- **신규 semantic 토큰**을 `:root`와 `.dark` 양쪽에 추가 + `@theme inline`에 `--color-*` 매핑:
  - `--success`(green), `--warning`(amber), `--info`(blue), `--danger`(=`--destructive` 재사용 검토)
  - light/dark 값 신규 결정 필요(옛 `.dark`엔 없던 토큰)
- **Tier 2를 위해 `--chart-6/7/8` 토큰도 여기서 신설** (`:root`+`.dark`+`@theme`): 보라/그린/오렌지 계열
  (AllocationTabs fallback `#A78BFA`/`#34D399`/`#FB923C` 승격 대상)
- **`--surface-subtle` 토큰 신설** (`:root`+`.dark`+`@theme`): light=`#F7F8FA`(현 TradeCard 값 그대로), dark=어두운 등가색.
  ⚠️ `--card`(순백 `#FFFFFF`)로 매핑하지 말 것 — 라이트 모드에서 카드가 순백으로 바뀌는 회귀. `#F7F8FA`는 `--card`와 다른 미묘한 회색
- verify: `pnpm -C app exec tsc --noEmit` (CSS는 타입 무관하나 후속 참조 기반) + preview에서 `.dark` 클래스 수동 토글 시 배경 전환 확인
- 의존: 없음

### Tier 1b — 인프라 복원 (파일별 분리)

#### 2. [FE] `app/package.json` — next-themes 설치
- `next-themes` 설치. **Next 16.2.3 / React 19 클린 설치 검증 필수** (peer dep 경고/충돌 확인)
- ⚠️ 설치 후 `pnpm -C app install` 재실행으로 lockfile 정합
- verify: `pnpm -C app list next-themes` 성공 + `pnpm -C app exec tsc --noEmit`
- 의존: 없음 (1a와 병렬 가능)

#### 3. [FE] `app/src/lib/constants/theme.ts` — 복원
- `ca2610b~1` 그대로: `DEFAULT_THEME="system"`, `THEME_ATTRIBUTE="class"`, `type Theme`
- verify: `pnpm -C app exec tsc --noEmit`
- 의존: 없음

#### 4. [FE] `app/src/components/providers/ThemeProvider.tsx` — 복원
- `ca2610b~1` 그대로: next-themes `ThemeProvider` 래핑 (attribute=class, defaultTheme=system, enableSystem, disableTransitionOnChange)
- verify: `pnpm -C app exec tsc --noEmit`
- 의존: 2(next-themes), 3(theme.ts)

#### 5. [FE] `app/src/components/providers/ThemedToaster.tsx` — 복원 (AppToaster 대체)
- `ca2610b~1`의 `ThemedToaster.tsx` 복원: `useTheme().resolvedTheme`로 sonner `theme` 연동
- 기존 `AppToaster.tsx` 제거 (이 파일이 만든 orphan)
- verify: `pnpm -C app exec tsc --noEmit`
- 의존: 2(next-themes)

#### 6. [FE] `app/src/app/layout.tsx` — 배선
- `ThemeProvider`로 트리 래핑, `AppToaster` import → `ThemedToaster`로 교체
- `<html>`에 **`suppressHydrationWarning` 복원** ⚠️ (누락 시 FOUC + hydration 경고 — Blind spot)
- `viewport.themeColor`를 light/dark 미디어쿼리 배열로 복원 (현재 단일 `#7C3AED`)
- ⚠️ **AGENTS.md: layout/viewport/metadata 되돌리기 전 `app/node_modules/next/dist/docs/` 확인** (Next 16 breaking)
- verify: `pnpm -C app exec tsc --noEmit` + `pnpm -C app build` (또는 dev 부팅) 무경고
- 의존: 4(ThemeProvider), 5(ThemedToaster)

#### 7. [FE] `app/src/components/settings/AppearanceSection.tsx` (+테스트) — 복원
- `ca2610b~1` 그대로: `useTheme()` 기반 시스템/라이트/다크 3-way `ToggleGroup`
  (`@/components/base/ToggleGroup` — **이미 존재**, mounted 가드로 hydration 안전)
- 테스트 `__tests__/AppearanceSection.test.tsx`도 함께 복원
- verify: `pnpm -C app test -- AppearanceSection` + `pnpm -C app exec tsc --noEmit`
- 의존: 2(next-themes), 3(theme.ts)

#### 8. [FE] `app/src/app/(app)/settings/page.tsx` — "화면" 섹션 삽입
- `AppearanceSection` import + `<section>` (`<h2 className={SECTION_LABEL}>화면</h2>`) 추가
- ⚠️ **삽입 위치: 현재 구조 기준 "자산 관리" 섹션 다음.** (옛 ca2610b diff는 stale — "내 정보" 섹션은 현재 없음.
  옛 diff 위치를 그대로 따르지 말 것)
- verify: `pnpm -C app exec tsc --noEmit` + 설정 화면에서 3-way 토글 노출·전환 동작
- 의존: 7(AppearanceSection)

### Tier 1c — semantic 색 토큰 승격 (파일별 분리)

#### 9. [FE] `app/src/lib/constants/semantic-colors.ts` — 신규 (SEMANTIC_COLORS)
- `PNL_COLORS` 패턴 복제: `SEMANTIC_COLORS.success/warning/info`(필요 시 `danger`) 각각 `.text/.bg/.bgSoft/.border`
  - ⚠️ Tailwind JIT 정적 추출 — 동적 보간 금지, 정적 string으로 나열
  - leaf 모듈 유지(다른 프로젝트 모듈 import 금지 → 순환 방지)
- verify: `pnpm -C app exec tsc --noEmit`
- 의존: 1(팔레트에 토큰 정의됨)

#### 10. [FE] `app/src/components/analysis/severity-styles.ts` — semantic 토큰 적용
- `bg-blue-50` 등 하드코딩 → `SEMANTIC_COLORS.info/warning/danger` 참조, **`dark:` 없이**
- verify: `pnpm -C app exec tsc --noEmit`
- 의존: 9

#### 11. [FE] `app/src/lib/constants/trading.ts` — ADHERENCE_CONFIG semantic 토큰
- FOLLOWED(green)/DEVIATED(orange) → `SEMANTIC_COLORS.success`/`warning` 토큰
- ⚠️ **함정(feedback_circular_import_colors_trading): trading.ts↔colors.ts 순환 금지.** semantic-colors.ts는 leaf라 안전하나 import 방향 확인
- verify: `pnpm -C app exec tsc --noEmit`
- 의존: 9

#### 12. [FE] `app/src/components/records/trade-display.tsx` — CountryBadge semantic 토큰
- CountryBadge KR blue → `SEMANTIC_COLORS.info` (알파 배경으로 다크 자동 대응)
- verify: `pnpm -C app exec tsc --noEmit`
- 의존: 9

#### 13. [FE] import 패널 semantic 토큰 통일
- `app/src/components/records/ImportTradesPanel/*` + `shared/ImportSourceBadge.tsx`의
  `text-green-600`/`bg-*-50`/기존 잔존 `dark:` → semantic 토큰으로 통일
- verify: `pnpm -C app exec tsc --noEmit`
- 의존: 9

### Tier 2 — 폴리시

#### 14. [FE] `app/src/components/records/TradeCard.tsx` — CARD_SURFACE 토큰화
- `CARD_SURFACE = "bg-[#F7F8FA]"`(line 25) → `bg-[var(--surface-subtle)]` (토큰은 1a에서 신설됨. 순수 consumer)
- ⚠️ **`bg-card`로 매핑 금지** — `#F7F8FA`는 `--card`(순백)와 다른 미묘한 회색. `bg-card` 사용 시 라이트 모드에서 카드가 순백으로 바뀌는 회귀(Q3 시각 QA가 놓치기 쉬움). 반드시 `--surface-subtle` 경로
- 다크에서 흰 회색 카드 깨짐 방지 — 다크 지원의 사실상 필수
- verify: `pnpm -C app exec tsc --noEmit` + preview **라이트(회색 유지)+다크(어두운 등가색)** 양쪽 카드 배경 확인
- 의존: 1 (`--surface-subtle` 토큰)

#### 15. [FE] `app/src/components/home/AllocationTabs.tsx` — 차트 fallback hex 토큰화
- `#A78BFA`/`#34D399`/`#FB923C`(line 22-24) → `var(--chart-6/7/8)` 참조 (토큰은 1a에서 신설됨)
- verify: `pnpm -C app exec tsc --noEmit` + preview 다크에서 차트 색 확인
- 의존: 1

### Tier 3 — 네이티브 (Capacitor)

#### 16. [FE] Capacitor StatusBar 다크 대응
- `@capacitor/status-bar` 설치 여부 확인 → 없으면 추가(package.json)
- `resolvedTheme` 변화에 반응하는 클라이언트 훅/effect로 StatusBar `style`(텍스트색)+배경 전환
  (웹 no-op, 네이티브만 동작)
- `capacitor.config.ts` SplashScreen `backgroundColor` 다크 대응 검토 — **가능 범위만, 과설계 금지**
  (네이티브 스플래시는 정적이라 시스템 다크 자동전환 제한적)
- verify: `pnpm -C app exec tsc --noEmit` + (가능 시) 시뮬레이터/실기기 StatusBar 다크 전환 확인
- 의존: 6(layout에 ThemeProvider 배선 완료 후 resolvedTheme 사용 가능)

### 문서

#### 17. [FE] `docs/decisions.md` — 결정 로그 갱신
- 기록할 트레이드오프 결정:
  1. semantic 색 **승격 대상/금지 정책** (반복 semantic만 팔레트로, 브랜드색·브로커 배지·OAuth 색은 제외 — 팔레트 오염 방지)
  2. `--fall` **다크 명도 신규값** 조정 이유(어두운 배경 대비)
  3. 단순 revert 대신 semantic 토큰 승격 방향 채택 이유
- verify: 문서 반영 확인
- 의존: 9, 1 (정책·값 확정 후)

## QA 작업 단위 (integration-qa · incremental)

#### Q1. [QA] 팔레트 + 인프라 검증
- `pnpm -C app exec tsc --noEmit` + `pnpm -C app test` 통과
- `@custom-variant dark` 존재 확인, `.dark` 토글 시 배경/텍스트 전환
- 설정 탭 3-way 토글(시스템/라이트/다크) 노출·전환·**localStorage 지속** 확인
- `suppressHydrationWarning` 복원 확인(FOUC/hydration 경고 없음)
- 의존(blockedBy): 1, 6, 7, 8

#### Q2. [QA] semantic 토큰 검증
- severity(분석)·adherence·CountryBadge·import 패널을 라이트/다크 양쪽 preview 확인
- **프로젝트 커스텀 컴포넌트 `dark:` 프리픽스 0개** 목표 달성 확인(grep)
- BE 응답 shape 무관(FE 전용)이나 semantic 색이 데이터 상태와 정합한지 확인
- 의존(blockedBy): 10, 11, 12, 13

#### Q3. [QA] Tier 2/3 시각 검증
- 라이트/다크 전 화면 시각 QA: 홈(포트폴리오·차트), 기록(TradeCard·CountryBadge·import), 분석(severity·adherence), 설정(토글)
- 금융 수치 가독성·대비, 카드 배경, 등락색(rise/fall) 대비 중점
- ⚠️ **TradeCard 라이트 회귀 확인: 카드 배경이 순백이 아니라 미묘한 회색(`#F7F8FA`) 유지되는지** (`--surface-subtle` 오매핑 시 순백 회귀)
- 차트 fallback 색 다크 대비
- (가능 시) 시뮬레이터/실기기 Capacitor StatusBar 다크 전환
- 의존(blockedBy): 14, 15, 16

## 완료 조건
- [ ] 모든 구현 단위 verify 통과 (`tsc --noEmit`, `pnpm -C app test`)
- [ ] Q1/Q2/Q3 QA 통과 (라이트/다크 양쪽 시각 검증)
- [ ] 프로젝트 커스텀 컴포넌트 `dark:` 프리픽스 0개
- [ ] `docs/decisions.md` 갱신 (단위 17)
- [ ] `docs/backlog.md` "다크 테마 추가" 항목 체크
- [ ] `spec-current.md` → `docs/spec-history/2026-07-02-dark-theme.md` 이관 준비
