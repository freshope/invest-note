# 기술 결정 로그

중요한 설계/기술 선택을 기록합니다. "왜 이렇게 했지?"를 나중에 다시 묻지 않기 위해.

---

## 2026-04-23 | Capacitor 셋업 — 설치 위치 `app/`, appId `com.investnote.app`

- **결정:** Capacitor 8.x를 `app/` 워크스페이스 내부에 설치. `appId=com.investnote.app`, `appName=투자노트`, `webDir=out`. iOS/Android 네이티브 프로젝트는 `app/ios/`, `app/android/`로 생성하고 git 커밋.
- **이유:**
  - 설치 위치: `webDir`가 Next.js export 결과물인 `app/out/` 을 상대 경로 `out`으로 가리켜야 하고, `cap` CLI는 `capacitor.config.ts` 기준으로 동작.
  - appId: 무난한 역도메인(`com.investnote.app`) 선택 — 개인 도메인 소유 여부와 무관하게 스토어 등록 가능.
  - 네이티브 커밋: Capacitor 공식 권장. 네이티브 설정·플러그인 변경이 버전 관리되어 재현성 확보.
- **트레이드오프:**
  - appId는 App Store/Play Console 등록 후 변경 불가 — 스토어 등록 전 변경 가능 시점에 재확인 필요.
  - 네이티브 디렉토리 커밋으로 레포 크기 증가(수 MB). 빌드 산출물(Pods/build/.gradle/assets/public)은 Capacitor 자동 생성 `ios/.gitignore`·`android/.gitignore`가 커버.
- **후속 작업:** OAuth deep link(Custom URL Scheme + Capacitor Browser), Apple Sign-in, 푸시·생체인증, FastAPI CORS 허용(Capacitor WebView origin `capacitor://localhost` / `https://localhost`), 앱 아이콘·스플래시 리소스 — 별도 spec.

---

## 2026-04-23 | iOS 의존성: CocoaPods 설치 (Homebrew)

- **결정:** 로컬 개발 머신에 CocoaPods 1.16.2를 `brew install cocoapods` 로 설치.
- **이유:** `cap add ios` 가 Swift Package Manager(Capacitor 8 기본) + CocoaPods 혼합 환경을 지원. 일부 플러그인이 여전히 CocoaPods를 요구하므로 사전 설치가 안전.
- **트레이드오프:** Homebrew의 `ruby` 4.0.3 + `libyaml` 추가 설치(약 60MB). 향후 SPM 전용 플러그인만 사용한다면 불필요해질 가능성 있음.

---

## 2026-04-22 | 정적 export 전환 + Next.js API Routes 제거 (Chunk D)

- **결정:** Next.js를 `output: 'export'` 정적 모드로 전환. Server Component + Route Handler 전부 제거.
- **이유:** Capacitor 모바일 앱은 정적 번들을 WebView에서 직접 로드하므로 SSR/쿠키 기반 서버 기능 사용 불가. FastAPI 백엔드가 모든 API 엔드포인트를 커버하므로 Next.js API Routes 필요 없음.
- **트레이드오프:**
  - 동적 라우트 `records/[id]`, `stocks/[country]/[ticker]`는 삭제 (정적 열거 불가 + 이미 패널 기반 진입). 딥링크 소실.
  - 인증이 localStorage 기반으로 이동 (`createBrowserClient`). 실제 OAuth 플로우 테스트 필요.
  - `NEXT_PUBLIC_API_BASE_URL` 미설정 시 모든 API 호출 실패 — 배포 시 필수 설정.
- **향후:** 3단계(Capacitor 래핑)에서 OAuth deep link + `window.location.origin` → Capacitor URL scheme 처리.

---

## 2026-04-17 | 시세 API: 비공식 API 사용

- **결정:** 네이버 금융(KR), Yahoo Finance(US) 비공식 API 사용
- **이유:** KIS Open API 연동은 인증 절차가 복잡하고 MVP 범위 초과
- **트레이드오프:** 언제든 응답 포맷이 깨질 수 있음
- **향후:** v2에서 KIS 공식 API로 교체 예정

---

## 2026-04-17 | 평균단가: WAC(가중평균단가) 방식

- **결정:** 보유 종목 평균단가를 WAC 방식으로 계산
- **이유:** 한국 증권사 대부분이 WAC 방식 사용 — 사용자 익숙도 높음
- **트레이드오프:** FIFO 방식 대비 세금 계산 정확도 낮음 (세금 계산은 MVP 외)

---

## 2026-04-17 | 자산 탭 제거 → 홈 대시보드에 통합

- **결정:** 별도 자산 탭(`/assets`) 없이 홈(`/`)에 보유 종목 현황 통합
- **이유:** 탭을 분리하면 탐색 depth가 늘어남. 홈에서 한눈에 보는 게 모바일 UX에 적합
- **트레이드오프:** 보유 종목이 많아지면 홈이 길어질 수 있음

---

## 2026-04-17 | CSV 임포트: UI만 선구현

- **결정:** `CsvUploadButton` UI는 구현했으나 파싱/임포트 로직은 미구현 (alert placeholder)
- **이유:** 포맷 정의(컬럼 매핑)가 확정되지 않은 상태에서 로직을 먼저 짜면 낭비
- **향후:** 임포트 포맷 확정 후 구현 — `docs/backlog.md` 참고

---

## 2026-04-17 | 데이터 접근 레이어: API Route 단일화

- **결정:** 모든 DB 접근을 `src/app/api/**/route.ts`로 통일. Server Actions 완전 제거, Server Component도 `serverFetch()` 헬퍼로 내부 API 경유
- **이유:** 추후 API를 독립 백엔드 서버로 분리할 계획 — 분리 시점에 `API_BASE_URL` 환경변수만 교체하면 핸들러 본체를 그대로 이식 가능
- **트레이드오프:** Server Actions 대비 네트워크 홉 1회 추가 (SSR → 내부 API). 성능 차이는 미미하나 분리 유연성이 더 중요
- **공용 헬퍼:** `requireUser()`, `serverFetch()`, `api-client.ts` 래퍼로 보일러플레이트 최소화

---

## 2026-04-17 | API 서버 유틸: 공용 validators.ts 추출

- **결정:** Route Handler들이 공유하는 파싱/검증 함수를 `src/lib/api-server/validators.ts`로 통합
- **이유:** `parsePositiveNumber`, `parseCashBalance`, `VALID_TRADE_TYPES` 등이 accounts/trades 4개 파일에 중복 정의되어 있었음 — 한 곳에서 수정하면 전체 반영
- **포함 항목:** account 상수(MAX_NAME_LENGTH 등), trade enum 배열(VALID_STRATEGIES 등), 숫자 파서, `parseTradedAt`(KST +09:00 보정 포함)

---

## 2026-04-17 | 탭 구조: 분석 탭 포함

- **결정:** 홈 / 기록 / 분석 / 설정 4개 탭 (초기 계획의 "자산" 탭 대신 "분석" 탭)
- **이유:** 매매 패턴 분석이 핵심 목표 중 하나. 자산 현황은 홈으로 커버 가능
- **현재 상태:** 분석 탭(`/analysis`) Phase A+B+C 구현 완료 (2026-04-17)

---

## 2026-04-17 | 분석 탭 WAC: 순수 가격 기준 (수수료 제외)

- **결정:** `portfolio.ts`와 `realized-pnl.ts` 모두 BUY commission을 WAC에서 제외 — 순수 매수가 기준 평균단가 사용
- **이유:** 포트폴리오 화면의 `avgBuyPrice` 표시와 분석 탭의 실현손익 계산 기준을 통일. 수수료는 매도 시점에 별도 차감(`- commission - tax`)으로 처리됨
- **트레이드오프:** BUY 수수료가 큰 계좌(예: 대형 거래)에서는 실현손익이 실제보다 약간 과대계상될 수 있음
- **향후:** 수수료 현황을 별도 패널로 노출하는 방안 backlog에 추가

---

## 2026-04-18 | mutation 후 router.refresh() + invalidateQueries 병용

**맥락:** TanStack Query 도입 후 `router.refresh()` 없이 `invalidateQueries`만 사용했더니 Server Component로 렌더링된 거래/계좌 목록이 mutation 후 갱신되지 않는 regression 발생
**결정:** mutation(거래 생성/수정/삭제, 계좌 추가/수정/삭제) 후 `queryClient.invalidateQueries()` + `router.refresh()` 를 함께 호출
**이유:** `invalidateQueries`는 TanStack Query 캐시만 무효화 — Server Component(RSC)는 별도로 `router.refresh()`가 있어야 재렌더됨
**트레이드오프:** `router.refresh()`가 전체 페이지 Server Component를 재페치하므로 느릴 수 있음. 향후 Server Component를 Client Component로 전환하거나 캐시 태그 revalidation으로 교체 가능

---

## 2026-04-19 | 거래상세·종목상세 패널 상태 — Context SSOT

**맥락:** `TradeDetailPanel`과 `StockDetailPanel`이 서로를 자식으로 렌더해 패널이 무한 중첩되던 문제. 두 패널이 동일 `z-[100]` portal로 쌓이며 DOM 누적.
**결정:** 패널 오픈 상태를 호출자 로컬 state에서 끌어올려 `DetailPanelProvider` (app/layout 수준)에서 단일 `mode: "trade" | "stock" | null` 상태로 관리. Provider가 두 `<FullScreenPanel>`을 직접 소유하고, 호출자는 `openTrade()`/`openStock()`만 호출.
**이유:** `mode` 단일 상태로 동시 오픈이 구조적으로 불가능 — 런타임 가드 없이 mutual-exclusive 보장. 기존 `FullScreenPanel`·`useSnapshotWhileOpen` 재사용으로 슬라이드 아웃 애니메이션 유지.
**트레이드오프:** 이전에는 종목 패널에서 거래를 수정하면 거래 패널만 닫히고 종목 패널로 복귀했으나, 현재는 수정/삭제 시 두 패널 모두 닫힘. 단순한 동작이지만 UX 차이 존재. pathname 변경 시 자동 close + 애니메이션 완료 후 payload null 리셋 추가.

---

## 2026-04-20 | SELL avg_buy_price DB 저장

**맥락:** SELL profit_loss를 DB에 저장하기 시작하면서 WAC 평균단가(avg_buy_price)도 동일 시점에 함께 저장할 필요 발생. 종목상세 breakdown 카드가 avg_buy_price를 표시하는데, 저장 없이는 매번 런타임 WAC 재계산에 의존.
**결정:** SELL 등록·재계산 시 `profit_loss`와 `avg_buy_price`를 함께 계산·저장. DB 컬럼 `avg_buy_price numeric NULL` 추가 (migration 007).
**이유:** 조회 시점 재계산 제거 → 정적 표시 가능. profit_loss 저장과 동일한 흐름(`recalcGroupPnL`)에서 처리되어 추가 비용 없음.
**트레이드오프:** 컬럼 하나 추가. 백필 스크립트 1회 실행 필요. 종목상세 breakdown이 저장값을 쓰도록 하는 후속 작업(`computeFlexibleBreakdown`) 은 별도 backlog.

---

## 2026-04-20 | 수정 불가 필드 확장 — 삭제 후 재등록 정책

**맥락:** SELL profit_loss 저장 도입 후 PATCH에서 account_id/ticker/country 변경 시 "이전 그룹 + 새 그룹" 양쪽을 검증·재계산해야 하는 cross-group 로직이 필요해짐. 기존에는 traded_at·profit_loss만 수정 불가였음.
**결정:** account_id, ticker_symbol, asset_name, country_code를 수정 불가 필드로 확장. `TradeUpdateSchema`에서 제거. 잘못 입력한 거래는 삭제 후 재등록.
**이유:** cross-group 재계산 로직이 복잡하고 edge case(두 그룹 중 하나 oversell 등)가 많음. "삭제 후 재등록" 단순 정책이 서버 로직을 크게 줄이고 데이터 정합성 보장이 쉬움. 실제 사용 패턴에서 계좌·종목 변경 빈도는 극히 낮음.
**트레이드오프:** UI에서 해당 필드 수정 불가 → 사용자가 인지해야 함. TradeEditPanel에 읽기 전용 표시 + 안내 추가로 UX 보완.

---

## 2026-04-20 | 프리젠테이션 계층 WAC fallback 완전 제거

**맥락:** `feature/persist-realized-pnl`로 SELL 행에 `profit_loss`/`avg_buy_price`가 저장되고 거래 CUD 시 `recalcGroupPnL`이 항상 갱신해 정합성을 보장. 프리젠테이션 읽기 경로는 여전히 WAC fallback(`computeRealizedPnL` 조건 호출, `sellPnL` fallback)을 유지하고 있었음.
**결정:** `buildPnlMap`, `buildPositions`, `computeFlexibleBreakdown` 세 곳에서 WAC fallback을 제거하고 저장값(`profit_loss`, `avg_buy_price`)을 직접 읽는다. `computeRealizedPnL`은 테스트/검증용으로 export 유지.
**이유:** 중복 연산 제거, 코드 단순화. `computeFlexibleBreakdown`은 O(n) 전체 trades 루프에서 O(1) 필드 읽기로 간소화됨.
**트레이드오프:** `recalcGroupPnL` 실패로 null이 남은 행이 있으면 손익 0 표시. 사용자가 데이터 정합성 보장을 확인한 상태에서 적용. legacy oversell matched_qty 불일치 케이스에서 breakdown 내 sellAmount/costBasis가 pnl과 산술적으로 맞지 않을 수 있음(spec 수용).

---

## 2026-04-22 | 모노레포 구조 선택 — pnpm workspace app + api 분리

**맥락:** FastAPI 백엔드 분리(2단계) 진입 전, 현재 단일 Next.js 프로젝트를 프론트엔드(`app/`)와 백엔드(`api/`)로 분리할 구조가 필요해짐.
**결정:** pnpm workspace를 사용해 `app/`(Next.js)과 `api/`(FastAPI, 예정) 두 패키지를 모노레포로 관리. 루트 `package.json`은 위임 스크립트만 보유.
**이유:** 별도 레포보다 단일 레포에서 코드·히스토리·이슈를 함께 관리하는 게 팀(1인) 규모에 적합. pnpm workspace는 Node.js 툴링 공유와 루트 스크립트 위임이 간단. `app/`은 독립 레포로 분리 가능하도록 자체 `.gitignore` 보유.
**트레이드오프:** `app/node_modules/`가 별도 생성됨(pnpm 로컬 링크). Vercel 배포 시 Root Directory를 `app`으로 변경해야 함(수동). `scripts/backfill-pnl.ts`는 `app/` 디렉터리에서 실행해야 `.env.local` 경로가 맞음.

---

## 2026-04-22 | FastAPI 인증: Supabase JWKS(ES256) 선택

**맥락:** FastAPI 백엔드에서 Supabase 발급 JWT를 검증하는 방법으로 HS256(JWT Secret 대칭키)과 ES256/JWKS(비대칭키 공개키 검증) 두 가지 선택지가 있었음. Supabase 대시보드 UI 변경(Publishable/Secret Key 노출)으로 기존 JWT Secret 방식이 deprecated 징후였음.
**결정:** `PyJWKClient`로 Supabase JWKS 엔드포인트(`/auth/v1/.well-known/jwks.json`)에서 공개키를 가져와 ES256 서명 검증. `_get_jwks_client(uri)`에 `@lru_cache`를 적용해 프로세스당 클라이언트 1개 유지.
**이유:** Supabase 권장 방식 — 공개키 검증이므로 서버에 시크릿을 저장하지 않아도 됨. 키 로테이션 시 JWKS 엔드포인트가 자동 갱신되어 재배포 불필요. 제3자 백엔드에 적합한 비대칭키 방식.
**트레이드오프:** 최초 요청(cold start) 시 JWKS 엔드포인트에 동기 HTTP 호출 발생(~100ms). `cache_keys=True`로 이후 요청은 메모리 조회. 비동기 이벤트 루프 블로킹 가능성 있으나 키 캐시 이후엔 무의미한 수준.

---

## 2026-04-17 | 분석 탭: 감정/전략 룰 resultCount 가드

- **결정:** `losing_strategy`, `emotion_fomo_low_winrate` 룰 모두 `resultCount >= 3` 가드 적용
- **이유:** `result` 미입력 거래만 있을 경우 `winRate=0`이 되어 규칙이 오발동하는 false positive 방지
- **적용 범위:** `EmotionStats`에 `resultCount` 필드 추가, `StrategyStats`의 기존 `resultCount`와 동일한 패턴

---

## 2026-04-22 | FastAPI DB 드라이버: asyncpg + Supabase RLS GUC 주입

**맥락:** FastAPI 백엔드에서 Postgres에 직접 붙는 방법으로 supabase-py(REST API 경유)와 asyncpg(직접 연결) 두 선택지가 있었음. 기존 Next.js는 supabase-js 클라이언트로 RLS를 적용했으나, FastAPI는 독립 서버이므로 쿠키 기반 세션을 재사용할 수 없음.
**결정:** asyncpg 풀을 사용하고, `acquire_for_user()` context manager가 transaction 내부에서 두 GUC를 주입해 기존 RLS policy를 재활용:
```sql
SELECT set_config('role', 'authenticated', true),
       set_config('request.jwt.claims', '{"sub":"<uid>","role":"authenticated"}', true)
```
**이유:** supabase-py는 트랜잭션 지원이 없고 REST API 경유라 SQL 표현력이 제한됨. asyncpg는 명시적 SQL + 트랜잭션 지원으로 복잡한 쿼리에 유리. GUC 주입으로 `auth.uid()` 함수가 올바르게 동작해 RLS policy(`auth.uid() = user_id`)가 자동 적용 — SQL에 `WHERE user_id` 명시 불필요.
**트레이드오프:** Supabase 내장 함수(`auth.uid()`)에 의존하므로 순수 Postgres 환경에서는 동작 안 함. 모든 요청마다 GUC 세팅 쿼리 1회 추가 (1-RTT, `set_config` 2개를 단일 SELECT로 통합해 최소화).

---

## 2026-04-22 | Supabase Pooler: Session mode (port 5432) 선택

**맥락:** asyncpg로 Supabase에 연결할 때 Direct Connection / Session Pooler(5432) / Transaction Pooler(6543) 세 가지 선택지 존재. Transaction Pooler가 처음 계획이었으나 실제 연결 테스트에서 Session Pooler가 필요함이 확인됨.
**결정:** Supabase Supavisor Session Pooler (port **5432**) 사용.
**이유:** Direct Connection은 Supabase IPv6-only 직접 연결 문제로 로컬/Render 환경에서 접속 불가. Transaction Pooler(6543)는 `SET LOCAL`이 connection 반환 후 다른 요청에 영향을 줄 수 있음. Session Pooler는 connection당 1 세션이 보장되어 `SET LOCAL`이 transaction scope에 안전하게 격리됨. `statement_cache_size=0` 설정으로 pgbouncer/Supavisor 호환 유지.
**트레이드오프:** Session Pooler는 connection 재사용 횟수가 Transaction Pooler보다 적어 동시 접속이 많을 때 풀 소진 가능. MVP 트래픽 수준에서는 문제없음. 운영 트래픽 증가 시 Transaction Pooler + `SET SESSION`/connection-level GUC 방식으로 전환 검토.
