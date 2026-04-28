# 기술 결정 로그

중요한 설계/기술 선택 기록. "왜 이렇게 했지?"를 다시 묻지 않기 위해.

---

## 2026-04-28 | 라이트 모드 전용 — 다크 모드 제거

- **맥락:** 설정 탭의 "화면" 섹션에 시스템/라이트/다크 3종 토글이 있었고 next-themes로 동적 전환했음. 단일 디자인 일관성 확보와 다크 variant 색 결정·검증 비용 절감을 위해 라이트 모드 단일화 결정.
- **결정:** 테마 토글 UI(`AppearanceSection`), `next-themes` 의존성, `ThemeProvider` 래퍼, `globals.css`의 `.dark { ... }` CSS 변수 블록 및 `@custom-variant dark` 선언, 그리고 11개 컴포넌트의 `dark:` Tailwind 프리픽스 26곳을 모두 제거. `ThemedToaster` → `AppToaster`로 리네임하고 sonner 기본값(light)을 활용해 prop 단순화.
- **이유:** 디자인 토큰을 `:root` 단일 소스로 관리. 컴포넌트마다 dark variant 색을 별도 결정·QA할 필요 없음. `next-themes` 제거로 번들 사이즈와 hydration 비용 소폭 감소. `<html suppressHydrationWarning>` 같은 회피 코드도 함께 제거됨.
- **트레이드오프:** 다크 모드 재도입 시 `dark:` 프리픽스 재추가와 `.dark` CSS 변수 블록 복원이 필요. 기존 사용자의 `localStorage["theme"]` 값은 next-themes가 사라져 무시되므로 별도 마이그레이션 코드는 두지 않음. shadcn 컴포넌트 동기화 시 원본 `dark:` 클래스와 diff가 발생할 수 있으나 본 프로젝트는 `src/components/base/` 래퍼 경유 사용이라 영향 제한적.

---

## 2026-04-27 | MVP 해외 주식 제외 — 신규 진입 차단, 기존 데이터 호환 유지

- **맥락:** MVP는 국내 주식 매매 기록과 분석에 집중한다. 기존 코드에는 US/Yahoo 검색·시세와 USD 합산 전제가 남아 있어 환율 미적용 총자산·분석 왜곡이 발생할 수 있음.
- **결정:** MVP에서는 신규 해외 주식 검색, 시세 조회, 신규 매수 등록을 차단한다. `country_code` 타입과 기존 US/OTHER 데이터 렌더링은 유지해 과거 데이터 조회와 보유분 매도 흐름은 깨지지 않게 한다.
- **트레이드오프:** 기존 해외 보유분은 v2 전까지 신규 시세가 `null`일 수 있다. v2에서 해외 주식을 재도입할 때 Yahoo 등 provider, USD/KRW 환율, 크로스 통화 분석 정합성을 함께 설계한다.

---

## 2026-04-26 | 미래 거래 등록 차단 — 입력 경계에서 거절, 분석 필터 상한 유지

- **맥락:** 분석 기간 필터는 "all"에서도 `now` 이후 거래를 제외한다. 사용자가 미래 거래를 등록할 수 있으면 기록에는 보이지만 분석에는 빠지는 상태가 생겨 혼란이 발생할 수 있음.
- **결정:** 신규 거래 등록에서 미래 `traded_at`을 차단한다. 프론트는 캘린더와 zod 검증으로 사전 차단하고, FastAPI `TradeCreate` 스키마는 문자열/`datetime` 입력을 UTC로 정규화한 뒤 서버 현재 시각보다 미래면 400으로 거절한다. 분석 필터의 `now` 상한은 기존/외부 유입 데이터 방어용으로 유지한다.
- **트레이드오프:** 미래 예약 거래/계획 거래는 MVP 범위에서 지원하지 않는다. 향후 CSV 임포트나 계획 거래 기능이 생기면 별도 데이터 타입 또는 명시적인 import 정책이 필요하다.

---

## 2026-04-25 | asyncpg UUID→str 타입 경계 — 라우터 입력 경계에서 변환

**맥락:** asyncpg는 PostgreSQL UUID 컬럼을 `uuid.UUID` 객체로 반환. Pydantic 모델(`Trade`)은 `_uuid_to_str` validator로 자동 str 변환되지만, 일반 dataclass(`Account`)는 type hint를 강제하지 않아 `account.id`가 UUID 객체로 남음. `build_account_snapshots`에서 `by_account.get(account.id)`가 str 키와 타입 불일치 → 항상 빈 배열 반환 → `stock_evaluation = 0`.
**결정:** 라우터 입력 경계 `_account_from_row`에서 UUID 필드를 str로 변환. 도메인 함수 `build_account_snapshots`에도 `str(account.id)` 방어 처리 유지.
**이유:** 타입 강제가 없는 dataclass는 입력 경계에서 정규화해야 런타임 타입 불일치를 막을 수 있음. 도메인의 `str()` 호출은 라우터 외 경로(테스트, 직접 호출)에서 UUID가 들어올 경우의 안전망.
**트레이드오프:** asyncpg를 사용하는 다른 dataclass 변환 함수에도 동일 패턴 적용 필요. Pydantic 모델로 전환하면 validator로 중앙화 가능하나 현재는 도메인 모델을 경량 dataclass로 유지.

---

## 2026-04-24 | TOCTOU race — pg_advisory_xact_lock 선택

- **맥락:** trades 라우터의 `list_trades → validate → write` 흐름에서 동시 SELL 요청이 같은 보유량 스냅샷을 읽고 둘 다 validate를 통과해 음수 보유량이 발생 가능. `FOR UPDATE`를 걸 행이 없고(보유량은 trades 집계로 유도), `SERIALIZABLE` 격리는 retry loop가 필요해 라우터 구조 변경 비용이 큼.
- **결정:** transaction-scoped advisory lock(`pg_advisory_xact_lock`) 사용. 키는 `TradeGroupKey(ticker, asset_name, country, account_id)` + `user_id`를 `hashtextextended`로 bigint 해시. create/update/delete 세 mutation 경로에 `list_trades` 이전 삽입.
- **이유:** xact 변종은 트랜잭션 종료 시 자동 해제 → Supavisor transaction mode pooler에서 session-level 변종(`pg_advisory_lock`) 대비 leak 없음. 마이그레이션 불필요(Postgres 11+ 내장). 기존 `TradeGroupKey` 도메인 타입 재사용으로 그룹 경계 일관성 유지.
- **트레이드오프:** 해시 충돌 시 불필요한 직렬화 발생(정합성 영향 없음, 64-bit 충돌 확률 무시 가능). lock_timeout 미설정 상태 — hang 방어용 `SET LOCAL lock_timeout` 후속 필요.

---

## 2026-04-25 | advisory lock timeout — SET LOCAL 2s + 전역 handler

- **맥락:** `feature/toctou-advisory-lock`에서 `pg_advisory_xact_lock` 도입 시 lock_timeout을 설정하지 않아, 운영에서 동일 그룹 동시 mutation이 몰리면 뒤 요청이 무한 대기하며 워커를 점유할 위험이 있었음 (트레이드오프 항목으로 명시됨).
- **결정:** `acquire_trade_group_lock` 내부에 advisory lock 직전 `SET LOCAL lock_timeout = '2s'` 실행. `LockNotAvailableError`(sqlstate 55P03) 발생 시 `main.py` 전역 exception handler에서 `409 Conflict` + 한국어 안내 메시지로 변환.
- **이유:** `SET LOCAL`은 트랜잭션 종료 시 자동 reset되므로 별도 RESET 불필요. 2s는 운영 hang 방어용 보수적 값 (일반 INSERT/UPDATE는 훨씬 빠름). 전역 handler 선택으로 `db_ops`가 `errors.APIError`를 import하지 않아 의존 방향 유지.
- **트레이드오프:** 같은 트랜잭션 내 INSERT/UPDATE row-lock 대기에도 2s 상한이 적용됨 (현재 코드베이스에서는 무해). 2s 값은 휴리스틱 — 운영 모니터링 후 조정 필요. 클라이언트(invest-note-ux)의 재시도 정책은 별도 처리 필요.

---

## 2026-04-24 | FE constants — 레이어 분리 + 중앙화 (BE co-location 미적용)

- **결정:** FE 상수는 BE처럼 도메인 폴더 내 co-location이 아닌 `app/src/lib/constants/` 중앙 폴더로 관리. 단일 파일에서만 쓰이는 UI 로컬 상수(색상, 애니메이션 ms, 탭 정의 등)는 컴포넌트 파일 내 유지.
- **이유:** FE UI는 여러 도메인 데이터를 혼합해서 보여주는 것이 본업이라 도메인 경계가 BE처럼 강하지 않음. co-location하면 어디에 둘지 애매한 상수가 생김. 현재 구조(레이어 분리 + 도메인 서브폴더)가 FE 특성에 맞는 절충안.
- **트레이드오프:** 상수가 늘어날수록 constants 파일 관리 필요. 여러 곳에서 쓰이는 상수만 선별 이관하고 단일 파일 전용은 로컬 유지 원칙 지킬 것.

---

## 2026-04-24 | BE 상수 co-location — 모놀리식 constants.py 배제

- **결정:** API 백엔드 상수를 단일 `constants.py`가 아닌 각 도메인 모듈에 인접 배치. `domain/trade_types.py`(enum 단일 소스), `domain/trade_utils.py`(KST·MS_PER_DAY), `external/constants.py`(URL·User-Agent·timeout), `auth/constants.py`(JWT·GUC 상수), `errors.py`(에러 메시지) 구조.
- **이유:** 모놀리식 파일은 상수 간 응집도 없이 크기만 커져 수정 범위 파악이 어려움. 도메인 경계 내 co-location이 변경 이유가 같은 상수를 함께 관리.
- **트레이드오프:** `schemas/` → `domain/` 단방향 import 규칙 필수 준수. 순환 import 발생 시 추적이 어려울 수 있음.

---

## 2026-04-23 | FastAPI CORS — Capacitor WebView origin 허용

- **결정:** `Settings.cors_origins` 기본값과 `.env.example`에 `capacitor://localhost`(iOS), `https://localhost`(Android, 포트 없음) 추가. `allow_credentials=True`, 고정 리스트 유지.
- **이유:** Capacitor WKWebView가 이 두 origin으로 페이지를 서빙해 기존 웹 origin만으로는 preflight 거부. 고정 2개라 regex 불필요.
- **트레이드오프:** production `CORS_ORIGINS` 환경변수에도 반드시 반영 필요.

---

## 2026-04-23 | OAuth Deep Link — `com.investnote.app://auth/callback`

- **결정:** reverse-DNS 형식 고정. 짧은 형식(`investnote://`) 배제.
- **이유:** Bundle ID와 일치, App Store 유니크성으로 하이재킹 위험 최소.
- **후속:** Universal Links 전환은 도메인·심사 확정 후 재검토.

---

## 2026-04-23 | Supabase 클라이언트 — `@supabase/supabase-js` + PKCE + implicit fallback

- **결정:** `@supabase/ssr` → `@supabase/supabase-js`의 `createClient`. `auth.flowType: 'pkce'` 명시. `CapacitorDeepLinkHandler`가 `?code=`(PKCE)와 `#access_token=`(implicit) 모두 수용.
- **이유:** `@supabase/ssr` 은 쿠키 기반 storage인데 Capacitor iOS `capacitor://localhost`에서 WebKit이 쿠키를 저장하지 않아 PKCE verifier 분실. `supabase-js`는 localStorage 기본이라 안정 persist. provider/버전 이슈로 implicit 응답 가능성 배제 불가라 fragment fallback 유지.
- **후속:** 서버측 세션 공유가 필요해지면 `@supabase/ssr` 재도입 검토 (현재 FastAPI Bearer로 불필요).

---

## 2026-04-23 | OAuth Deep Link 리스너 — 루트 레이아웃 상주

- **결정:** `CapacitorDeepLinkHandler` 단일 컴포넌트로 분리해 루트 `layout.tsx` 내 상주 마운트. `@capacitor/app`·`@capacitor/browser` dynamic import.
- **이유:** Cold start 시 `App.getLaunchUrl()`을 리스너 등록 전에 호출해야 이벤트 손실 방지. 루트 상주로 페이지 이탈/재진입 경쟁 상태 제거. dynamic import로 웹 번들에 플러그인 chunk 미포함.

---

## 2026-04-23 | Capacitor 셋업 — 설치 `app/`, appId `com.investnote.app`

- **결정:** Capacitor 8.x를 `app/` 워크스페이스 내부 설치. `webDir=out`. `ios/`, `android/` 네이티브 프로젝트 커밋.
- **이유:** Next.js export 결과물 경로 일치. 네이티브 커밋은 Capacitor 공식 권장 (재현성).
- **트레이드오프:** appId는 스토어 등록 후 변경 불가. 레포 크기 수 MB 증가.

---

## 2026-04-23 | iOS — CocoaPods 설치 (Homebrew)

- **결정:** 로컬에 CocoaPods 1.16.2를 `brew install cocoapods`.
- **이유:** Capacitor 8은 SPM 기본이지만 일부 플러그인이 CocoaPods 요구.

---

## 2026-04-22 | 정적 export + Next.js API Routes 제거 (Chunk D)

- **결정:** `output: 'export'` 정적 모드 전환. Server Component + Route Handler 전부 제거. FastAPI가 모든 API 커버.
- **이유:** Capacitor가 정적 번들을 WebView에서 직접 로드 — SSR/쿠키 기반 서버 기능 사용 불가.
- **트레이드오프:** 동적 라우트(`records/[id]`, `stocks/[country]/[ticker]`) 삭제 (패널 진입으로 대체, 딥링크 소실). 인증은 localStorage 기반. `NEXT_PUBLIC_API_BASE_URL` 미설정 시 모든 API 호출 실패.

---

## 2026-04-22 | 모노레포 — pnpm workspace (`app/` + `api/`)

- **결정:** 루트 pnpm workspace로 `app/`(Next.js)과 `api/`(FastAPI) 분리. 루트 `package.json`은 위임 스크립트만.
- **이유:** 단일 레포에서 코드·히스토리·이슈 공동 관리가 1인 팀에 적합. `app/`은 독립 레포 분리 여지 확보.
- **트레이드오프:** Vercel 배포 시 Root Directory를 `app`으로 수동 설정. `scripts/backfill-pnl.ts`는 `app/`에서 실행.

---

## 2026-04-22 | FastAPI 인증 — Supabase JWKS (ES256)

- **결정:** `PyJWKClient`로 `/auth/v1/.well-known/jwks.json` 공개키 조회해 ES256 검증. `@lru_cache`로 프로세스당 클라이언트 1개.
- **이유:** Supabase 권장. 시크릿 서버 저장 불필요, 키 로테이션 자동 반영.
- **트레이드오프:** cold start 시 JWKS 동기 HTTP 호출(~100ms), 이후 메모리 캐시.

---

## 2026-04-22 | FastAPI DB — asyncpg + RLS GUC 주입

- **결정:** asyncpg 풀. `acquire_for_user()` 가 transaction 안에서 GUC 2개(`role`, `request.jwt.claims`)를 `set_config`로 주입해 기존 RLS policy 재사용.
- **이유:** supabase-py는 트랜잭션 미지원 + SQL 표현력 제한. GUC 주입으로 `auth.uid()` 자동 동작 → SQL에 `WHERE user_id` 명시 불필요.
- **트레이드오프:** 요청마다 `set_config` 1회 추가 (단일 SELECT로 통합).

---

## 2026-04-22 | Supabase Pooler — Session mode (port 5432)

- **결정:** Supavisor Session Pooler (5432). `statement_cache_size=0`.
- **이유:** Direct Connection은 IPv6-only로 로컬/Render 접속 불가. Transaction Pooler(6543)는 `SET LOCAL`이 connection 반환 후 다른 요청에 영향 가능. Session Pooler는 connection당 1세션 보장.
- **트레이드오프:** 동시 접속 증가 시 풀 소진 가능. MVP 수준에선 문제없음.

---

## 2026-04-20 | SELL avg_buy_price DB 저장

- **결정:** SELL 등록·재계산 시 `profit_loss`와 `avg_buy_price`를 함께 계산·저장 (migration 007: `avg_buy_price numeric NULL` 추가).
- **이유:** 조회 시점 WAC 재계산 제거. `recalcGroupPnL` 같은 흐름에서 처리되어 추가 비용 없음.
- **트레이드오프:** 백필 스크립트 1회 실행.

---

## 2026-04-20 | 수정 불가 필드 확장 — 삭제 후 재등록 정책

- **결정:** account_id, ticker_symbol, asset_name, country_code를 수정 불가로 확장. 잘못 입력한 거래는 삭제 후 재등록.
- **이유:** cross-group 재계산(이전 그룹 + 새 그룹 양쪽 검증) 로직이 복잡하고 edge case 많음. 단순 정책이 서버 로직·정합성 모두 유리. 계좌·종목 변경 빈도는 극히 낮음.
- **보완:** TradeEditPanel에 읽기 전용 표시 + 안내.

---

## 2026-04-20 | WAC fallback 완전 제거

- **결정:** `buildPnlMap`, `buildPositions`, `computeFlexibleBreakdown` 에서 WAC fallback 제거하고 저장값(`profit_loss`, `avg_buy_price`) 직접 사용. `computeRealizedPnL` 은 테스트용으로 export 유지.
- **이유:** `recalcGroupPnL`이 CUD 때마다 갱신해 정합성 보장됨. 중복 연산 제거, `computeFlexibleBreakdown`이 O(n) → O(1).
- **트레이드오프:** `recalcGroupPnL` 실패로 null 남은 행은 손익 0 표시. legacy oversell matched_qty 불일치 케이스는 spec 수용.

---

## 2026-04-24 | 거래·종목 상세 패널 — 2-슬롯 + open/payload 분리 구조 (mode 제거)

- **결정:** `mode` 단일 상태 제거. `tradePayload`/`stockPayload`(콘텐츠) + `tradeOpen`/`stockOpen`(애니메이션) 분리. 동일 타입 재오픈 시 `key` 증가로 portal remount → z-order 재정렬.
- **이유:** `mode` SSOT는 두 타입이 동시에 열릴 수 없어 Stock → Trade 이동 시 Stock이 닫혀 뒤로가기가 1단계. 2-슬롯 구조에서는 각 타입이 독립적으로 open/close되어 최대 2번 뒤로가기로 원래 페이지 복귀 가능.
- **트레이드오프:** `createPortal`의 DOM 추가 순서가 z-order를 결정하므로 동일 타입 재오픈 시 key remount 필수. `open=false` 후 `PANEL_ANIMATION_MS+50ms` 타이머로 payload null 처리해 슬라이드 아웃 중 콘텐츠 유지.

---

## 2026-04-19 | 거래·종목 상세 패널 상태 — Context SSOT (2026-04-24에 2-슬롯으로 대체)

- **결정:** `DetailPanelProvider`(app/layout)에서 단일 `mode: "trade" | "stock" | null` 관리. 호출자는 `openTrade()`/`openStock()`만 호출.
- **이유:** `mode` 단일 상태로 동시 오픈이 구조적으로 불가능 — 런타임 가드 없이 mutual-exclusive 보장. 무한 중첩 문제 해결.
- **트레이드오프:** 수정/삭제 시 두 패널 모두 닫힘 (이전엔 하위 패널만).

---

## 2026-04-17 | 시세 API — 비공식 API

- **결정:** 네이버 금융(KR). Yahoo Finance(US)는 2026-04-27 결정에 따라 MVP에서 제외하고 v2로 이동. KIS Open API는 v2.
- **트레이드오프:** 응답 포맷 깨질 수 있음.

---

## 2026-04-17 | 평균단가 — WAC (가중평균단가)

- **결정:** 보유 종목 평균단가를 WAC로 계산.
- **이유:** 한국 증권사 대부분이 WAC — 사용자 익숙도 높음.
- **트레이드오프:** FIFO 대비 세금 계산 정확도 낮음 (세금은 MVP 외).

---

## 2026-04-17 | 분석 탭 WAC — 순수 가격 기준 (수수료 제외)

- **결정:** `portfolio.ts`와 `realized-pnl.ts` 모두 BUY commission을 WAC에서 제외. 수수료는 매도 시점에 `- commission - tax`로 별도 차감.
- **이유:** 포트폴리오 `avgBuyPrice` 표시와 실현손익 계산 기준 통일.
- **트레이드오프:** BUY 수수료가 큰 계좌에서 실현손익 약간 과대계상 가능.

---

## 2026-04-17 | 자산 탭 제거 → 홈 통합

- **결정:** 별도 자산 탭 없이 홈(`/`)에 보유 종목 현황 통합.
- **이유:** 탐색 depth 감소 — 모바일 UX 적합.
- **트레이드오프:** 보유 종목이 많아지면 홈이 길어짐.

---

## 2026-04-17 | 탭 구조 — 홈/기록/분석/설정 (자산 대신 분석)

- **결정:** 4개 탭, "자산" 대신 "분석".
- **이유:** 매매 패턴 분석이 핵심 목표. 자산 현황은 홈으로 커버.

---

## 2026-04-17 | 분석 탭 — 감정/전략 룰 resultCount 가드

- **결정:** `losing_strategy`, `emotion_fomo_low_winrate` 룰 모두 `resultCount >= 3` 가드.
- **이유:** `result` 미입력 거래만 있으면 `winRate=0`으로 오발동. false positive 방지.

---

## 2026-04-17 | CSV 임포트 — UI만 선구현

- **결정:** `CsvUploadButton` UI만. 파싱/임포트 로직은 포맷 정의 후 구현.
- **이유:** 컬럼 매핑 미확정 상태에서 로직 먼저 짜면 낭비.
