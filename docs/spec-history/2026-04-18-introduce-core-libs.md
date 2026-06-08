> 완료: 2026-04-18

# spec: 핵심 라이브러리 도입 (zod / react-hook-form / tanstack-query / date-fns-tz)

## 목표

수동으로 반복 구현된 날짜 변환, API 검증, 폼 상태 관리, 서버 상태 페칭 패턴을
검증된 라이브러리로 대체하여 코드 신뢰성과 유지보수성을 높인다.

## 도입 라이브러리

| 라이브러리 | 버전 | 용도 |
|---|---|---|
| `zod` | latest | API 요청/응답 런타임 스키마 검증 |
| `react-hook-form` | latest | 폼 상태 관리 |
| `@hookform/resolvers` | latest | RHF ↔ zod 연결 |
| `@tanstack/react-query` | latest | 서버 상태 캐싱 / 재검증 |
| `@date-fns/tz` | latest | KST 타임존 변환 (date-fns v4 플러그인) |

## 구현 단계

### Step 0 — 패키지 설치
```bash
pnpm add zod react-hook-form @hookform/resolvers @tanstack/react-query @date-fns/tz
```

### Step 1 — @date-fns/tz: 타임존 유틸 교체
**파일:** `src/lib/trade-utils.ts`

- `toKST(utcDate)`: `new Date(utcDate.getTime() + 9h)` ms 트릭 →
  `toZonedTime(utcDate, "Asia/Seoul")` 로 교체
- `groupByDate()`, `formatDateLabel()` 영향 없음 (toKST 결과만 사용)

**파일:** `src/lib/analysis/period.ts`

- `periodToRange()` 내 `Date.UTC + getMonth` 수동 계산 →
  `subMonths`, `startOfYear`, `startOfDay`, `endOfDay` (date-fns) +
  `toZonedTime`/`fromZonedTime` 조합으로 교체
- `filterByPeriod()` 내 toKST 호출 → 직접 zoned time으로 비교

### Step 2 — zod: API 서버 스키마 정의
**파일:** `src/lib/api-server/validators.ts` (기존 함수 유지 or 내부 구현만 교체)

- `VALID_*` 상수 배열을 `z.enum([...])` 스키마로 선언
- 기존 parse* 함수들을 zod 스키마 기반으로 재구현:
  - `parseTradedAt` → `z.string().transform(parseTradedAt)` 방식
  - `parsePositiveNumber` → `z.coerce.number().positive()`
  - `parseCashBalance` → 쉼표 제거 후 `z.coerce.number().min(0)`
- export: `TradeUpdateSchema`, `AccountUpdateSchema` (PATCH 핸들러에서 사용)

**파일:** `src/app/api/trades/[id]/route.ts`

- PATCH 핸들러 상단에서 `TradeUpdateSchema.safeParse(await req.json())`
- 기존 분기별 validate 로직 제거, zod 결과로 단순화

### Step 3 — @tanstack/react-query: QueryClient Provider 설정
**파일:** `src/components/providers/QueryProvider.tsx` (신규)

- `QueryClient` 생성 + `QueryClientProvider` 래핑
- `staleTime: 30_000` 기본값

**파일:** `src/app/layout.tsx`

- `QueryProvider`를 루트 레이아웃에 추가

### Step 4 — @tanstack/react-query: usePortfolioSummary 교체
**파일:** `src/hooks/usePortfolioSummary.ts`

- `useEffect + fetch + cancelled flag` 패턴 →
  `useQuery({ queryKey: ["portfolio", "summary"], queryFn: ... })`
- 커스텀 이벤트 `"portfolio:refresh"` →
  `useQueryClient().invalidateQueries(["portfolio"])` 로 대체
- 반환 타입 동일 유지 (`{ data, loading, error }`)

### Step 5 — @tanstack/react-query: useAnalysisData 교체
**파일:** `src/hooks/useAnalysisData.ts`

- `useEffect + Promise.all + AbortController` 패턴 →
  `useQueries([summary, behavior, suggestions])` 로 대체
- queryKey에 period 포함: `["analysis", "summary", period]` 등
- 반환 타입 동일 유지

### Step 6 — react-hook-form: TradeMetaBuyForm 교체
**파일:** `src/components/records/TradeMetaBuyForm.tsx`

- 5개 useState → `useForm<TradeMetaBuySchema>()`
- zod 스키마: `TradeMetaBuySchema` (strategy, emotion, reasoning_tags, buy_reason)
- `tradesApi.update()` 성공 시 `invalidateQueries(["trade", id])`

### Step 7 — react-hook-form: TradeMetaSellForm 교체
**파일:** `src/components/records/TradeMetaSellForm.tsx`

- 8개 useState + 수동 숫자 포맷팅 →
  `useForm<TradeMetaSellSchema>()` + `Controller`로 통합
- profitLossDisplay 이중 상태 제거 (register + value transform)
- zod 스키마: `TradeMetaSellSchema` (result, strategy, emotion, profit_loss, 텍스트 3개)

## 완료 기준

- [x] `pnpm tsc --noEmit` 타입 에러 없음
- [x] `pnpm vitest run` 기존 테스트 63개 통과
- [x] 거래 상세 → 메타 수정 → 저장 정상 동작 (수동 확인 필요)
- [x] 분석 대시보드 → 기간 변경 시 데이터 재페치 정상 (수동 확인 필요)
- [x] 포트폴리오 요약 캐싱 동작 확인 (DevTools Network)

## 브랜치

`feature/introduce-core-libs` (develop에서 분기)
