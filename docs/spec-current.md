# 현재 작업 사양: 데이터 접근 레이어 API 통일

## 목표

프로젝트 전반의 데이터 접근 경로를 `src/app/api/**/route.ts` 기반으로 통일한다.
추후 API를 독립 프로젝트(백엔드 서버)로 분리할 계획이 있기 때문.

현재 DB 접근이 Server Actions / Server Components / API Routes 세 경로로 분산됨 →
API Route 단일 경로로 통일 후 분석탭 구현 진행.

---

## 신규 API 엔드포인트

| 엔드포인트 | 메서드 | 기존 대체 대상 |
|-----------|-------|--------------|
| `/api/accounts` | GET | `settings/page.tsx` SELECT |
| `/api/accounts` | POST | `settings/actions.ts` `createAccount` |
| `/api/accounts/[id]` | PATCH | `settings/actions.ts` `updateAccount` |
| `/api/accounts/[id]` | DELETE | `settings/actions.ts` `deleteAccount` |
| `/api/accounts/[id]/trade-count` | GET | 삭제 전 거래 수 확인 |
| `/api/trades` | GET | `records/page.tsx`, `stocks/**`, `api/portfolio/stock-trades` 통합 (`?ticker=&country=` 필터 지원) |
| `/api/trades` | POST | `records/actions.ts` `createTrade` |
| `/api/trades/[id]` | GET | `records/[id]/page.tsx` |
| `/api/trades/[id]` | PATCH | `records/actions.ts` `updateTrade` / `updateTradeMetadata` |
| `/api/trades/[id]` | DELETE | `records/actions.ts` `deleteTrade` |
| `/api/auth/signin` | POST | `auth/actions.ts` `signIn` |
| `/api/auth/signup` | POST | `auth/actions.ts` `signUp` |
| `/api/auth/signout` | POST | `auth/actions.ts` `signOut` |

유지: `/api/portfolio/summary`, `/api/stocks/search`, `/api/stocks/quote`

---

## 공용 헬퍼 (신규)

- `src/lib/api-server/auth.ts` — `requireUser()` (인증 + supabase 클라이언트 반환)
- `src/lib/api-server/errors.ts` — `jsonError(msg, status)`, `HttpError`
- `src/lib/api-server/server-fetch.ts` — Server Component에서 내부 API 호출 헬퍼 (쿠키 전달, `API_BASE_URL` 지원)
- `src/lib/api-client.ts` — 클라이언트 공용 타입 안전 fetch 래퍼

---

## Mutation UX 변경

- Server Actions (`useActionState` + `form action`) → 클라이언트 `onSubmit` + `api.*` 호출
- `revalidatePath()` → `router.refresh()`
- 폼 에러/로딩 상태: `useState` 로컬 관리

---

## 작업 순서

- [ ] 1. 공용 헬퍼 파일 생성
- [ ] 2. accounts API Route 구현
- [ ] 3. settings 페이지·컴포넌트 API 전환
- [ ] 4. trades API Route 구현
- [ ] 5. records 페이지·컴포넌트 API 전환
- [ ] 6. stocks/portfolio 페이지 전환
- [ ] 7. auth API Route + login 페이지 전환
- [ ] 8. 정리 (actions.ts 삭제, stock-trades 제거, supabase/client.ts 삭제)
- [ ] 9. 검증

---

## 완료 기준

- [ ] 모든 Supabase 직접 호출이 `src/app/api/**` 로만 존재
- [ ] Server Actions 파일 전부 삭제
- [ ] Server Components에서 `createClient()` import 없음
- [ ] 브라우저 네트워크 패널: 페이지당 호출이 `/api/*` 로만 구성
- [ ] `pnpm typecheck`, `pnpm lint` 통과
