# Spec: 설정 탭 테마(라이트/다크/시스템) 전환 기능

## 배경 / 문제

투자노트 앱은 현재 라이트 테마 고정 상태입니다. `globals.css`에 다크 모드용 CSS 변수(`.dark { ... }`)와 `@custom-variant dark (&:is(.dark *));`가 모두 정의되어 있고 일부 컴포넌트는 이미 `dark:` 유틸리티를 사용 중이나, `<html>`에 `dark` 클래스를 토글하는 메커니즘과 사용자 선택 UI가 빠져 있습니다.

## 목표

- `/settings` 페이지에 "화면" 섹션이 추가되고, 시스템/라이트/다크 토글로 즉시 테마가 전환된다.
- 선택값이 localStorage에 저장되어 새로고침 및 앱 재실행 후에도 유지된다.
- "시스템" 선택 시 OS 다크 모드 변경에 자동 반응한다.
- 정적 export + Capacitor 환경에서 깜빡임(FOUC) 없이 초기 테마가 적용된다.
- sonner 토스트도 사용자 선택 테마를 따른다.

## 설계

### 접근 방식

- **`next-themes` 라이브러리 도입.** Tailwind v4 + 정적 export + Capacitor WebView와 호환. 인라인 스크립트로 FOUC 방지.
- **UI는 base/ToggleGroup 3-way.** 기존 래퍼(`app/src/components/base/ToggleGroup.tsx`) 즉시 활용. lucide-react의 `Monitor` / `Sun` / `Moon` 아이콘 사용.
- **다크 토큰 활용.** `app/src/app/globals.css`에 이미 정의된 `.dark { ... }` 토큰. CSS 변경 없음.
- **Toaster 동기화.** `ThemedToaster` 클라이언트 래퍼로 `useTheme().resolvedTheme`을 sonner `<Toaster>`에 전달.
- **하이드레이션 안전.** `<html suppressHydrationWarning>` + AppearanceSection의 `mounted` 가드.

### 주요 변경 파일

**신규**
- `app/src/components/providers/ThemeProvider.tsx`
- `app/src/components/providers/ThemedToaster.tsx`
- `app/src/components/settings/AppearanceSection.tsx`
- `app/vitest.setup.ts`
- `app/src/components/settings/__tests__/AppearanceSection.test.tsx`

**수정**
- `app/package.json` — `next-themes` 의존성 추가
- `app/src/app/layout.tsx`
- `app/src/app/(app)/settings/page.tsx`
- `app/vitest.config.ts`

## 구현 체크리스트

- [x] `app/package.json`에 `next-themes` 추가하고 `pnpm install`
- [x] `app/src/components/providers/ThemeProvider.tsx` 신규 작성
- [x] `app/src/components/providers/ThemedToaster.tsx` 신규 작성
- [x] `app/src/app/layout.tsx` 수정 — `suppressHydrationWarning`, `<ThemeProvider>` 래핑, `<ThemedToaster>` 교체
- [x] `app/src/components/settings/AppearanceSection.tsx` 신규 작성
- [x] `app/src/app/(app)/settings/page.tsx` 수정 — "화면" 섹션 삽입
- [x] `app/vitest.config.ts` 수정 — setupFiles 등록
- [x] `app/vitest.setup.ts` 신규 작성 — `matchMedia` 모킹
- [x] `app/src/components/settings/__tests__/AppearanceSection.test.tsx` 신규 작성
- [x] 타입 체크 통과 (`pnpm --filter app exec tsc --noEmit`)
- [x] 단위 테스트 통과 (`pnpm --filter app test`) — 119/119 passed

## 우려사항 / 리스크

- **하이드레이션 미스매치** — `<html suppressHydrationWarning>` + `mounted` 가드로 회피
- **iOS 상태바 색** — `@capacitor/status-bar` 미설치라 이번 범위 외, follow-up
