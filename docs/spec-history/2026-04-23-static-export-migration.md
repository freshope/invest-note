# Spec: 정적 export 전환 + Next.js `/api/*` 제거 (Chunk D)

> 완료: 2026-04-23

## 배경 / 문제

Capacitor 기반 iOS/Android 모바일 앱 배포를 위해 Next.js를 정적 export(`output: 'export'`) 모드로 전환. Chunk A(2026-04-22)에서 FastAPI 클라이언트 컷오버 완료, FastAPI 라우터 100% 포팅 완료. 남은 과제: 쿠키 세션 기반 Server Component 5개와 auth callback Route Handler 제거, Next.js `/api/*` 전체 삭제, `output: 'export'` 활성화. 클라이언트 인증 가드(`useAuth`/`AuthProvider`)가 존재하지 않아 순수 신규 작업이 포함됨.

## 목표

- `pnpm --filter app build` → `app/out/` 정적 자산 생성 성공
- 로그인/홈/기록/설정/분석 기능 모두 정상 동작
- Next.js `/api/*` 호출 0건, FastAPI(Bearer) 또는 Supabase JS(auth)만 사용
- 인증 가드는 클라이언트 측 `useAuth` + `onAuthStateChange`로 처리

## 설계

### 접근 방식

- **AuthProvider 신설** (`components/providers/AuthProvider.tsx`): Supabase 브라우저 세션 + `onAuthStateChange`로 `{ user, loading }` 제공
- **`(app)/layout.tsx` Client 전환 + AuthGuard**: 개별 페이지 인증 게이트 5곳 일괄 제거
- **동적 라우트 2개 삭제** (`records/[id]`, `stocks/[country]/[ticker]`): 이미 모두 패널 기반 진입 — 정적 export 불가로 삭제. `TradeCard` fallback만 패널로 교체
- **auth callback → Client Component 전환**: Route Handler → `page.tsx` + 브라우저측 `exchangeCodeForSession`
- **HoldingsList 잔존 fetch 교체** (Chunk A 누락): `tradesApi.list()`로 교체
- **server-only 코드 일괄 제거**: `app/api/`, `lib/api-server/`, `lib/supabase/server.ts`, `middleware.ts`, `proxy.ts`
- **`next.config.ts`**: `output: "export"`, `trailingSlash: true`, `images.unoptimized: true`

### 주요 변경 파일

- `app/src/components/providers/AuthProvider.tsx` — 신설: Supabase 세션 컨텍스트
- `app/src/hooks/useAuth.ts` — 신설: AuthProvider 소비 훅
- `app/src/app/layout.tsx` — AuthProvider 주입
- `app/src/app/(app)/layout.tsx` — Client 전환 + AuthGuard
- `app/src/app/(app)/page.tsx` — 인증 게이트 제거
- `app/src/app/(app)/records/page.tsx` — Client 전환 + `tradesApi.list()`
- `app/src/app/(app)/settings/page.tsx` — Client 전환 + 클라이언트 집계
- `app/src/app/login/page.tsx` — 로그인 상태 홈 리다이렉트 추가
- `app/src/components/records/TradeCard.tsx` — fallback router.push 제거
- `app/src/components/home/HoldingsList.tsx` — `tradesApi.list()` 사용
- `app/src/app/auth/callback/page.tsx` — 신설: OAuth 코드 교환
- `app/next.config.ts` — output 설정

## 구현 체크리스트

### Phase 1 — 클라이언트 인증 인프라
- [x] `src/components/providers/AuthProvider.tsx` 신설
- [x] `useAuth()` export (AuthProvider에서 함께)
- [x] `src/app/layout.tsx`에 `<AuthProvider>` 주입

### Phase 2 — Chunk A 누락분
- [x] `src/components/home/HoldingsList.tsx` → `tradesApi.list()` 교체

### Phase 3 — AuthGuard 적용
- [x] `src/app/(app)/layout.tsx` → `"use client"` + AuthGuard
- [x] `src/app/login/page.tsx` → 로그인 상태 홈 리다이렉트

### Phase 4 — Server Component 클라이언트 전환
- [x] `src/app/(app)/page.tsx` — 인증 게이트 제거
- [x] `src/app/(app)/records/page.tsx` — Client 전환
- [x] `src/app/(app)/settings/page.tsx` — Client 전환

### Phase 5 — 동적 라우트 제거
- [x] `TradeCard.tsx:46` fallback `router.push` → `onPress?.()` 교체
- [x] `src/app/(app)/records/[id]/page.tsx` 삭제
- [x] `src/app/(app)/stocks/[country]/[ticker]/page.tsx` 삭제

### Phase 6 — auth callback 전환
- [x] `src/app/auth/callback/page.tsx` 신설
- [x] `src/app/auth/callback/route.ts` 삭제

### Phase 7 — server-only 코드 삭제
- [x] `src/app/api/` 전체 삭제
- [x] `src/lib/api-server/` 전체 삭제
- [x] `src/lib/supabase/server.ts` 삭제
- [x] `src/lib/supabase/middleware.ts` 삭제
- [x] `src/proxy.ts` 삭제

### Phase 8 — 빌드 검증
- [x] `app/next.config.ts` output 설정 추가
- [x] `pnpm tsc --noEmit` 통과
- [x] `pnpm build` 성공 (모든 라우트 ○ Static)
- [ ] 브라우저 수동 테스트 (로그인/홈/기록/설정/분석) — 사용자 진행

### Phase 9 — 문서
- [x] `docs/backlog.md` Chunk D 항목 `[x]` 마킹
- [x] `docs/decisions.md` 항목 추가

## 우려사항 / 리스크

- OAuth PKCE flow: 서버 쿠키 → 브라우저 localStorage. 실제 Google/Kakao 플로우 테스트 필수
- `NEXT_PUBLIC_API_BASE_URL` 미설정 시 모든 API 호출 실패 — 배포 문서 업데이트 필요
- Capacitor redirect URL (`window.location.origin`)은 3단계(Capacitor 래핑)에서 처리
- `stocks/[country]/[ticker]` 딥링크 소실 — 모바일 앱 타겟이므로 허용
