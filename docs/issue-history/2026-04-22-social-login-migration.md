> 완료: 2026-04-22

# Spec: 소셜 로그인 마이그레이션 (Google / Kakao)

## 배경 / 문제

향후 Capacitor 기반 모바일앱 배포를 위한 사전 작업. 현재 이메일/패스워드 인증을 소셜 로그인 3종(Google/Apple/Kakao)으로 전환한다. Apple 앱스토어 가이드라인 4.8에 따라 다른 소셜 로그인 제공 시 Sign in with Apple 필수. 테스트 사용자만 있는 현 시점이 마이그레이션 부담이 가장 적은 적기.

## 목표

- Google/Kakao 소셜 로그인으로 회원가입·로그인이 동작한다 (Apple은 iOS 배포 직전 추가)
- 이메일/패스워드 인증 코드가 완전히 제거된다
- 기존 라우트 가드(미들웨어)가 소셜 세션과 호환되어 동작한다
- 백로그/로드맵에 모바일앱 배포 후속 단계가 반영된다

## 설계

### 접근 방식

- Supabase Dashboard에서 3개 OAuth provider 등록 (사용자 사전 작업)
- 클라이언트 Supabase SDK(`@supabase/ssr`의 `createBrowserClient`)로 OAuth 흐름 시작
- Server Route Handler에서 PKCE code → session 교환 (`exchangeCodeForSession`)
- 미들웨어는 그대로 유지 (정적 export 전환은 후속 3단계로 분리)
- 이메일/패스워드 관련 코드 삭제 (`/api/auth/*`, authApi, 로그인 폼 mode 토글)

### 주요 변경 파일

**신규**
- `src/lib/supabase/client.ts` — 브라우저 Supabase 클라이언트 singleton
- `src/app/auth/callback/route.ts` — OAuth code → session 교환

**수정**
- `src/app/login/page.tsx` — 이메일/패스워드 폼 제거, 소셜 버튼 3개로 재작성
- `src/lib/api-client.ts` — `authApi` export 제거 (149~163줄)
- `src/lib/supabase/middleware.ts` — `/api/auth/*` 특수 처리 제거
- `docs/backlog.md` — 모바일앱 배포 후속 단계 추가
- `docs/roadmap.md` — Capacitor/모바일 배포 방향성 추가

**삭제**
- `src/app/api/auth/signin/route.ts`
- `src/app/api/auth/signup/route.ts`
- `src/app/api/auth/signout/route.ts`
- `src/app/auth/confirm/route.ts` (이메일 인증 콜백)

**기타**
- 로그아웃 호출부를 `supabase.auth.signOut()`로 일괄 변경 (settings 등 grep 후 수정)

## 구현 체크리스트

- [x] Supabase Dashboard에 Google/Kakao provider 등록 (사용자 작업)
- [x] `src/lib/supabase/client.ts` 추가 — 브라우저 Supabase 클라이언트
- [x] `src/app/auth/callback/route.ts` 추가 — OAuth code 교환
- [x] `src/app/login/page.tsx` 재작성 — 소셜 버튼 2개 (Google/Kakao)
- [x] 로그아웃 호출부를 `supabase.auth.signOut()`로 변경
- [x] `src/lib/api-client.ts`에서 `authApi` export 제거
- [x] `src/lib/supabase/middleware.ts` — `/api/auth/*` 특수 처리 제거
- [x] `/api/auth/signin`, `/api/auth/signup`, `/api/auth/signout` 삭제
- [x] `src/app/auth/confirm/route.ts` 삭제
- [x] 테스트 사용자 정리 (Supabase Dashboard 수동)
- [x] `docs/backlog.md`에 모바일 2/3단계 항목 추가
- [x] `docs/roadmap.md`에 Capacitor/모바일 방향성 반영
- [x] 타입 체크 통과 (`pnpm tsc --noEmit`)
- [x] 로컬 환경에서 Google/Kakao 로그인/로그아웃 동작 확인

## 우려사항 / 리스크

- **Apple 로그인 미포함**: Apple Developer Program ($99/년) 가입 필요. iOS 앱 배포(3단계) 직전에 추가 예정. App Store 심사 4.8 규정상 필수.
- **Kakao redirect URI 정합성**: Kakao Developers 콘솔에 Vercel 도메인 + Supabase 콜백 URL 정확히 등록 필요. 미스매치 시 로그인 실패.
- **PKCE 흐름 검증**: `@supabase/ssr` 기본이 PKCE이므로 callback route에서 cookie 정상 설정되는지 확인 필요.
- **모바일 OAuth deep link는 본 단계 범위 외**: 3단계(Capacitor)에서 redirect URL을 `capacitor://localhost`로 추가 등록 + Browser 플러그인 흐름 추가 필요.
