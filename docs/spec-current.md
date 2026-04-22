# Spec: FastAPI 클라이언트 컷오버 (로컬 E2E)

## 배경 / 문제

`docs/backlog.md`의 **2단계 FastAPI 백엔드 분리**에서 라우터 포팅(P1a/P1b/P2/P3)까지 `develop`에 merge 완료. 배포는 이번 chunk에서 제외하고, 프론트엔드 통신 레이어를 FastAPI로 전환해 **로컬 E2E로 응답 파리티를 검증**한다. 검증이 끝나면 남은 chunk(SSR 컷오버, Next.js `/api/*` 제거)를 안전하게 진행할 수 있다.

## 목표

- `NEXT_PUBLIC_API_BASE_URL` 환경변수로 FastAPI origin 주입이 가능하고, 값이 비어있으면 기존 Next.js `/api/*`로 자동 fallback 된다(롤백 스위치).
- 브라우저(Client Components)에서 호출되는 `/api/*` 요청 전부가 Supabase JWT `Authorization: Bearer` 헤더를 달고 나간다.
- 로컬에서 Next.js(:3000) + FastAPI(:8000)를 동시 구동했을 때 홈/기록/분석/설정/거래 등록 흐름이 모두 FastAPI 응답으로 동작하고, DevTools Network 탭에서 호출 대상 origin이 `localhost:8000`으로 확인된다.
- 응답 파리티 sanity check(Next.js vs FastAPI) 수동 비교가 완료된다.
- `docs/backlog.md`에 2단계의 남은 chunk(배포, SSR 컷오버, Next.js `/api/*` 제거)가 명시적으로 기록된다.

## 설계

### 접근 방식

1. **env 플래그**: `NEXT_PUBLIC_API_BASE_URL`. 값 있음 → FastAPI origin, 빈 값 → 상대경로. Next.js 라우트가 아직 살아있는 이번 chunk 동안은 완전한 롤백 스위치 역할.
2. **Auth**: `app/src/lib/supabase/client.ts`의 브라우저 클라이언트에서 `auth.getSession()`으로 `access_token`을 꺼내 `Authorization: Bearer <token>` 헤더 주입. `getSession()`은 localStorage 기반이라 network I/O 없음.
3. **공통 fetcher 일원화**: 현재 `apiFetch`(api-client) + raw `fetch()`가 4곳(usePortfolioSummary, useAnalysisData, StockSearchInput, TradeBasicForm)에 산재. 전부 `apiFetch`로 모아 base URL + auth를 한 곳에서 처리.
4. **api-client.ts 확장**: `portfolioApi`, `stocksApi`, `analysisApi` 래퍼 추가. 기존 타입 재활용.
5. **SSR 비변경**: `(app)/page.tsx`, `records/page.tsx`, `settings/page.tsx` 등 서버 컴포넌트의 Supabase 직접 조회는 Chunk C에서 별도 처리. 이번 chunk는 `'use client'` 파일만 건드림.

### 주요 변경 파일

- `docs/backlog.md` — 2단계 서브 체크박스를 완료/미완료로 갱신하고 남은 chunk(배포, SSR 컷오버, Next.js `/api/*` 제거)를 서브 항목으로 명시.
- `app/.env.local.example` — `NEXT_PUBLIC_API_BASE_URL=` 라인 추가(주석으로 `http://localhost:8000` 예시).
- `app/src/lib/api-client.ts` — `apiFetch`에 base URL prefix + `Authorization: Bearer` 주입 로직. `portfolioApi` / `stocksApi` / `analysisApi` 래퍼 추가.
- `app/src/hooks/usePortfolioSummary.ts` — `fetch('/api/portfolio/summary')` → `portfolioApi.summary()`.
- `app/src/hooks/useAnalysisData.ts` — `fetchJson()` 3곳 → `analysisApi.summary/behavior/suggestions(period)`.
- `app/src/components/records/StockSearchInput.tsx` — `fetch('/api/stocks/search?q=...')` → `stocksApi.search(query)`.
- `app/src/components/records/TradeBasicForm.tsx` — `fetch('/api/portfolio/holding?...')` → `portfolioApi.holding(params)`.

## 구현 체크리스트

- [ ] `docs/backlog.md` — 2단계 서브 항목 갱신(완료 표시 + 남은 chunk 명시).
- [ ] `app/.env.local.example` — `NEXT_PUBLIC_API_BASE_URL=` 추가.
- [ ] `app/src/lib/api-client.ts` — `apiFetch`에 base URL + Bearer 주입, `portfolioApi`/`stocksApi`/`analysisApi` 래퍼 추가.
- [ ] `app/src/hooks/usePortfolioSummary.ts` — `portfolioApi.summary()` 사용.
- [ ] `app/src/hooks/useAnalysisData.ts` — `analysisApi.summary/behavior/suggestions()` 사용.
- [ ] `app/src/components/records/StockSearchInput.tsx` — `stocksApi.search()` 사용.
- [ ] `app/src/components/records/TradeBasicForm.tsx` — `portfolioApi.holding()` 사용.
- [ ] 타입 체크 통과 (`pnpm --filter app tsc --noEmit` 또는 `pnpm --filter app lint`).
- [ ] 로컬 E2E 수동 검증 — FastAPI(:8000) + Next.js(:3000) 동시 구동, 홈/기록/분석/설정/거래 등록 흐름 확인, Network 탭에서 `localhost:8000/api/*`로 요청 + `Authorization: Bearer` 헤더 확인.
- [ ] 롤백 스위치 확인 — `.env.local`에서 `NEXT_PUBLIC_API_BASE_URL` 제거 후 기존 `/api/*`로 fallback 되는지 확인.

## 우려사항 / 리스크

- **`getSession()` 매 호출 오버헤드**: localStorage 기반이라 network 없음. 영향 미미.
- **토큰 만료/리프레시**: `@supabase/ssr` 브라우저 클라이언트가 내부에서 자동 갱신. `getSession()`이 갱신된 토큰 반환.
- **SSR 파일에서 실수 호출**: `apiFetch`는 `'use client'` 파일 전용. 서버 컴포넌트에서 호출 시 `createClient()`(브라우저)가 런타임 에러로 드러남. 추가 가드는 두지 않음(과방어 회피).
- **CORS**: FastAPI `cors_origins` 기본값이 `http://localhost:3000` 포함이라 로컬 추가 설정 불필요.
- **`NEXT_PUBLIC_*` 빌드타임 인라인**: 배포 chunk에서 Vercel 환경변수로 주입 필요(기록만 해둠).
