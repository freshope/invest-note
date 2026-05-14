> 완료: 2026-04-24

# Spec: FE 인라인 상수 정리

## 배경 / 문제

`app/` 워크스페이스 곳곳에 인라인 리터럴(에러 코드, 폼 검증 길이, 라벨 맵, Zod enum 튜플, 수수료/세율, API 경로 등)이 흩어져 있어 같은 값이 2~5곳에서 반복되거나 백엔드와 동기화가 어려운 상태다. 기존 상수 파일(`query-keys.ts`, `auth/oauth-config.ts`, `analysis/period.ts`, `records/constants.ts`)이 이미 자리잡고 있으므로, 그 패턴을 따라 도메인별로 상수를 모으고 사용처를 일괄 교체해 유지보수성을 높인다. Python(api/) 측은 별도 spec으로 분리한다.

## 목표

- FE 전 범위에서 중복 리터럴/비즈니스 임계값/환경 식별자가 한 곳에 정의되고, 사용처는 모두 import해서 사용한다.
- `pnpm tsc --noEmit` 통과, 기존 테스트 모두 통과, 로그인(에러)·거래 작성·분석 대시보드 스모크 정상.
- 도메인별 9개 커밋으로 분할되어 리뷰/롤백이 쉽다.

## 설계

### 접근 방식

- **응집성 우선**: `auth/`, `analysis/`, `records/` 등 기존 도메인 폴더 안에 상수를 두고, 도메인이 폴더에 없는 값(검증 길이, query 옵션, storage key, 거래 수수료)만 `app/src/lib/constants/`에 신규 모듈로 분리.
- **명명**: 단일 값은 `UPPER_SNAKE_CASE`, 그룹은 `as const` 객체 + `keyof typeof` 유니온 (기존 `query-keys.ts` 스타일).
- **api-client.ts 라우트**: 같은 파일 내 `ROUTES` 객체로만 정리 — 외부 파일 분리는 import 사이클·가치 대비 위험 큼.
- **의도 보존**: parsePeriod fallback("all")과 대시보드 기본 기간("3m")은 의미가 다르므로 분리 유지. React Query의 의도적 staleTime override(StockSearchInput 60s, TradeBasicForm 0)는 그대로 둠.

### 신규/수정 파일

**신규**
- `app/src/lib/auth/errors.ts` — `AUTH_ERROR_CODE.OAUTH_FAILED` + login redirect 헬퍼 2종(슬래시 변형)
- `app/src/lib/constants/validation.ts` — `VALIDATION_LIMITS` (계좌명/종목명/거래소 길이)
- `app/src/lib/constants/query.ts` — `QUERY_DEFAULT_STALE_TIME_MS`, `QUERY_DEFAULT_RETRY`, `QUERY_STOCK_SEARCH_STALE_TIME_MS`
- `app/src/lib/constants/market.ts` — `COUNTRY_CODES`, `COUNTRY_LABEL`, `DEFAULT_COUNTRY_CODE`
- `app/src/lib/constants/trading.ts` — `COMMISSION_RATE`, `SELL_TAX_RATE`
- `app/src/lib/constants/storage.ts` — `STORAGE_KEYS.LAST_ACCOUNT_ID`

**수정**
- `app/src/components/providers/CapacitorDeepLinkHandler.tsx` (oauth_failed 5곳)
- `app/src/app/auth/callback/page.tsx` + `__tests__/page.test.tsx` (oauth_failed 1+2곳)
- `app/src/components/settings/AccountFormPanel.tsx` (계좌명 50)
- `app/src/components/records/TradeBasicForm.tsx` (asset_name 100, exchange 50, 수수료/세율, last-account key, country zod enum)
- `app/src/components/providers/QueryProvider.tsx` (staleTime/retry)
- `app/src/lib/analysis/period.ts` + `app/src/components/analysis/AnalysisDashboard.tsx` (DEFAULT_ANALYSIS_PERIOD)
- `app/src/components/records/constants.ts` (STRATEGY_LABELS/EMOTION_LABELS 파생 + *_VALUES 튜플)
- `app/src/components/records/TradeDetail.tsx`, `TradeCard.tsx`, `TradeMetaSellForm.tsx`, `TradeEditPanel.tsx`, `TradeMetaBuyForm.tsx` (라벨/zod enum 인라인 제거)
- `app/src/components/records/StockSearchInput.tsx`, `trade-display.tsx`, `trade-formatters.ts` (국가 라벨)
- `app/src/lib/api-client.ts` (상단 ROUTES 객체 + 18곳 내외 경로 교체)

## 구현 체크리스트

### Phase 1 — Auth 에러 코드
- [x] `app/src/lib/auth/errors.ts` 생성 (`AUTH_ERROR_CODE`, `LOGIN_OAUTH_FAILED_PATH`, `LOGIN_OAUTH_FAILED_PATH_NO_SLASH`)
- [x] `CapacitorDeepLinkHandler.tsx` 5곳 + `auth/callback/page.tsx` 1곳 + 테스트 2곳 교체
- [x] `pnpm test app/auth/callback` 통과 확인
- [x] 커밋: `refactor(auth): extract oauth_failed error code constant`

### Phase 2 — 폼 검증 길이
- [x] `app/src/lib/constants/validation.ts` 생성
- [x] `AccountFormPanel.tsx` 50 → `VALIDATION_LIMITS.ACCOUNT_NAME_MAX` (zod + maxLength)
- [x] `TradeBasicForm.tsx` asset_name 100, exchange 50 교체
- [x] 커밋: `refactor(forms): centralize input length limits`

### Phase 3 — React Query 기본 옵션
- [x] `app/src/lib/constants/query.ts` 생성
- [x] `QueryProvider.tsx` staleTime/retry 상수화
- [x] `StockSearchInput.tsx` 60_000 → `QUERY_STOCK_SEARCH_STALE_TIME_MS`
- [x] 커밋: `refactor(query): extract react-query default options`

### Phase 4 — 분석 기본 기간
- [x] `analysis/period.ts`에 `DEFAULT_ANALYSIS_PERIOD: Period = "3m"` + parsePeriod 의미 차이 주석 1줄
- [x] `AnalysisDashboard.tsx` `useState<Period>("3m")` 교체
- [x] 커밋: `refactor(analysis): extract default analysis period constant`

### Phase 5a — Records 라벨 통합
- [x] `records/constants.ts`에 `STRATEGY_LABELS`/`EMOTION_LABELS` 파생 export 추가 (`Record<string,string>` 유지, strict 타입은 별도 spec)
- [x] `TradeDetail.tsx`, `TradeCard.tsx`, `TradeMetaSellForm.tsx`, `TradeEditPanel.tsx`의 인라인 객체 제거 → import
- [x] 커밋: `refactor(records): consolidate strategy/emotion label maps`

### Phase 5b — Zod enum 단일 소스
- [x] `records/constants.ts`에 `STRATEGY_VALUES`, `EMOTION_VALUES`, `REASONING_TAG_VALUES`, `TRADE_RESULT_VALUES` 튜플 export
- [x] `TradeBasicForm.tsx`, `TradeMetaBuyForm.tsx`, `TradeMetaSellForm.tsx`, `TradeEditPanel.tsx`의 `z.enum([...])` 교체
- [x] 커밋: `refactor(records): unify zod enums via constants`

### Phase 6 — 시장/국가 라벨
- [x] `lib/constants/market.ts` 생성
- [x] `StockSearchInput.tsx`, `trade-display.tsx`, `trade-formatters.ts`의 국가 라벨 import (배지 className은 인라인 유지)
- [x] 커밋: `refactor(records): centralize country labels`

### Phase 7 — 수수료/세율
- [x] `lib/constants/trading.ts` 생성
- [x] `TradeBasicForm.tsx` `calcCommission`/`calcTax` 계수 import
- [x] 커밋: `refactor(trading): extract commission/tax rate constants`

### Phase 8 — localStorage 키
- [x] `lib/constants/storage.ts` 생성
- [x] `TradeBasicForm.tsx` `LAST_ACCOUNT_KEY` 교체
- [x] 커밋: `refactor(storage): centralize localStorage keys`

### Phase 9 — API 라우트 정리 (api-client.ts 내부)
- [x] `api-client.ts` 상단에 `ROUTES` 객체 정의 (accounts/trades/portfolio/stocks/analysis 5섹션, 동적 경로는 함수)
- [x] 18곳 내외 인라인 경로 교체
- [x] 커밋: `refactor(api-client): consolidate route paths into ROUTES object`

### Phase 10 — 검증
- [x] `pnpm tsc --noEmit` 통과
- [x] `pnpm test` 전체 통과
- [x] 수동 스모크: 로그인(에러 케이스 redirect) → 거래 작성(자동 계산값 동일) → 분석 대시보드 진입 정상

## 우려사항 / 리스크

- **trailing slash 변형**: `/login?error=` vs `/login/?error=` 두 가지가 공존 — `errors.ts`에 두 상수 분리해서 export, 사용처는 grep으로 매핑.
- **테스트 하드코딩**: `auth/callback/__tests__/page.test.tsx`에 `"oauth_failed"` 문자열 존재 — Phase 1에서 동일 커밋에 포함해 깨짐 방지.
- **Zod enum 튜플 타입**: `z.enum(STRATEGY_VALUES)`는 readonly tuple 받음 (Zod v3 호환). 빌드로 확인.
- **`STRATEGY_LABELS` 타입 강화 보류**: 첫 커밋은 `Record<string,string>` 유지(기존 fallback 코드 흐름 보존). strict `Record<StrategyType,string>` 전환은 별도 spec.
- **`parsePeriod` fallback 미변경**: URL 무효값 → "all" / 대시보드 진입 → "3m"의 의미 차이 유지.
- **API 라우트 18곳 일괄 교체**: 동일 파일 내 변경이지만 PR diff 검토 시 매핑 한 줄씩 확인 필요. 변경 전후 계좌 list 호출 1회 수동 검증.
- **제외 항목**(명시): Python(api/), `BUY`/`SELL` 같은 2-튜플 Literal, Tailwind 토큰(z-index/duration), 단발성 매직 넘버(useDebounce 300 등), KAKAO_BG/AUTH_ERROR_MSG 같은 컴포넌트 내부 상수, FE에 존재하지 않는 한도(종목코드 30/자유텍스트 5000).

## 검증

```bash
cd app
pnpm tsc --noEmit
pnpm test
pnpm build  # 정적 export까지 깨지지 않는지
```

수동 스모크 (`pnpm dev`):
1. `/login` 진입 후 OAuth 실패 redirect URL에 `error=oauth_failed` 유지되는지
2. 거래 등록 폼에서 종목명 100자 / 계좌명 50자 입력 한도 동작
3. 분석 대시보드 첫 진입 시 기간 탭이 "3개월" 선택 상태
4. `/api/...` 호출 5종(accounts/trades/portfolio/stocks/analysis) 네트워크 응답 정상

## 브랜치

`feature/extract-fe-constants` (develop에서 분기)
