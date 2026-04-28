# Spec: 테마 설정 제거 — 라이트 모드 전용

> 완료: 2026-04-28

## 배경 / 문제

설정 탭(`/settings`)의 "화면" 섹션에서 시스템/라이트/다크 3가지 테마를 토글할 수 있다. 앱을 라이트 모드 단일 디자인으로 고정하기로 결정함에 따라, 테마 토글 UI와 next-themes 기반 동적 테마 인프라(ThemeProvider, ThemedToaster, .dark CSS 변수, dark: Tailwind 프리픽스)를 모두 제거한다. 결과적으로 사용자는 항상 라이트 모드만 보게 된다.

## 목표

- 설정 탭에서 "화면" 섹션이 사라지고 테마를 변경할 수 있는 UI가 없다.
- 시스템 다크 모드 환경에서도 앱은 라이트 색상으로만 렌더링된다.
- `next-themes` 의존성과 관련 코드(ThemeProvider, ThemedToaster의 동적 theme 분기, `Theme` 타입 등)가 코드베이스에 남지 않는다.
- 타입 체크(`pnpm tsc`)와 기존 테스트가 통과한다.

## 설계

### 접근 방식

1. **테마 토글 UI 제거**: 설정 페이지에서 `AppearanceSection`을 사용하지 않고, 컴포넌트 파일과 테스트 파일을 삭제한다.
2. **ThemeProvider 제거**: `next-themes` 래퍼가 불필요하므로 `ThemeProvider` 컴포넌트를 삭제하고 `layout.tsx`에서 사용을 제거한다. `<html suppressHydrationWarning>`도 제거(next-themes가 런타임에 클래스를 주입할 때만 필요).
3. **ThemedToaster 단순화**: `useTheme`/`resolvedTheme` 분기를 제거하고 `theme="light"`를 고정 전달한다. 컴포넌트명은 그대로 두되 내부에서 next-themes 의존성을 제거한다(외부 호출부 영향 최소화).
4. **CSS 정리**: `globals.css`에서 `@custom-variant dark (&:is(.dark *));` 선언과 `.dark { ... }` 블록(99~131라인) 제거. `:root`만 남겨 라이트 색상으로만 동작.
5. **`dark:` Tailwind 프리픽스 제거**: 11개 파일에서 26개 위치의 `dark:` 프리픽스 클래스를 모두 삭제. (Tailwind v4에서 `@custom-variant dark`가 없으면 무시되지만, 죽은 코드 잔존 방지를 위해 명시적으로 제거)
6. **상수 파일 삭제**: `src/lib/constants/theme.ts` 삭제. (`DEFAULT_THEME`, `THEME_ATTRIBUTE`, `Theme` 타입 모두 더 이상 참조되지 않음)
7. **의존성 정리**: `app/package.json`에서 `next-themes` 제거 후 `pnpm install`.

### 주요 변경 파일

- `app/src/app/(app)/settings/page.tsx` — `AppearanceSection` import와 "화면" `<section>` 블록(47~55라인) 삭제
- `app/src/components/settings/AppearanceSection.tsx` — **파일 삭제**
- `app/src/components/settings/__tests__/AppearanceSection.test.tsx` — **파일 삭제**
- `app/src/components/providers/ThemeProvider.tsx` — **파일 삭제**
- `app/src/components/providers/ThemedToaster.tsx` — `useTheme` 의존성 제거, `theme="light"` 고정
- `app/src/app/layout.tsx` — `ThemeProvider` import/wrapper 제거, `suppressHydrationWarning` 제거
- `app/src/app/globals.css` — `@custom-variant dark` 및 `.dark { ... }` 블록 제거
- `app/src/lib/constants/theme.ts` — **파일 삭제**
- `app/package.json` — `next-themes` dependency 제거 (이후 `pnpm -C app install`)
- `dark:` 프리픽스 제거 대상 (11파일 / 26위치):
  - `app/src/components/ui/button.tsx` (라인 7, 13, 17, 19)
  - `app/src/components/ui/tabs.tsx` (라인 61, 62, 63)
  - `app/src/components/ui/input.tsx` (라인 12)
  - `app/src/components/ui/select.tsx` (라인 44)
  - `app/src/components/ui/textarea.tsx` (라인 10)
  - `app/src/components/ui/toggle.tsx` (라인 9)
  - `app/src/components/ui/calendar.tsx` (라인 212)
  - `app/src/components/records/trade-display.tsx` (라인 41, 43)
  - `app/src/components/records/StockSearchInput.tsx` (라인 28)
  - `app/src/components/analysis/severity-styles.ts` (라인 5, 6, 9, 12, 13, 16, 19, 20, 23)
  - `app/src/components/analysis/ReasoningBreakdown.tsx` (라인 23, 25 등 3곳)

## 구현 체크리스트

- [x] `app/src/app/(app)/settings/page.tsx`에서 `AppearanceSection` 사용 제거
- [x] `AppearanceSection.tsx` + 테스트 파일 삭제
- [x] `ThemeProvider.tsx` 삭제, `layout.tsx`에서 사용 제거 (`suppressHydrationWarning` 함께 제거)
- [x] `ThemedToaster.tsx`에서 `useTheme` 제거하고 `theme="light"` 고정
- [x] `globals.css`에서 `@custom-variant dark` + `.dark { ... }` 블록 제거
- [x] `src/lib/constants/theme.ts` 삭제
- [x] shadcn/ui 래퍼 대상 컴포넌트(`ui/button.tsx`, `ui/tabs.tsx`, `ui/input.tsx`, `ui/select.tsx`, `ui/textarea.tsx`, `ui/toggle.tsx`, `ui/calendar.tsx`)의 `dark:` 클래스 제거
- [x] 비-UI 컴포넌트(`records/trade-display.tsx`, `records/StockSearchInput.tsx`, `analysis/severity-styles.ts`, `analysis/ReasoningBreakdown.tsx`)의 `dark:` 클래스 제거
- [x] `app/package.json`에서 `next-themes` 제거 → `pnpm -C app install`
- [x] 타입 체크 통과 (`pnpm -C app exec tsc --noEmit`)
- [x] 테스트 통과 (`pnpm -C app test`) — 9 files / 124 tests passed
- [x] 개발 서버 실행 후 설정 탭에서 "화면" 섹션이 사라졌는지, 시스템 다크 모드에서도 라이트 모드로 렌더링되는지 시각 확인

## 우려사항 / 리스크

- shadcn/ui 컴포넌트 래퍼의 `dark:` 클래스를 제거하면, 향후 shadcn 컴포넌트 업데이트 시 diff가 커질 수 있다. 다만 본 프로젝트에서 사용하는 것은 `src/components/base/` 래퍼이므로 직접 사용 컴포넌트가 영향 받지는 않는다.
- `next-themes` 패키지 제거 시 lockfile(pnpm-lock.yaml)에도 변경이 발생한다.
- Capacitor의 status bar 등 네이티브 테마 연동 코드는 현재 없으므로 별도 처리 불필요.

## 검증 방법

1. `pnpm -C app exec tsc --noEmit` — 타입 에러 없음
2. `pnpm -C app test` — 기존 테스트 통과 (AppearanceSection 테스트 삭제 확인)
3. `pnpm -C app dev` 후 브라우저에서:
   - `/settings` 진입 → "화면" 섹션이 보이지 않음
   - macOS 시스템 다크 모드 토글 → 앱은 항상 라이트 색상 유지
   - localStorage에 `theme` 키가 새로 생성되지 않음(기존 값이 있어도 무시)
4. `grep -rn "dark:" app/src` → 결과 없음
5. `grep -rn "next-themes\|useTheme\|DEFAULT_THEME" app/src` → 결과 없음
