# Spec: 내 자산 변화 페이지 (계좌별/종목별 일별 자산 추이)

## 배경 / 문제

`docs/backlog.md` "자산 변화 페이지" 항목 구현. 계좌별·종목별 **일별 자산(평가액) 추이**를 차트로 보고, 차트 아래 목록으로 확인하는 페이지를 추가한다. 일별 자산 = 그 날 보유 수량 × 그 날 종가. 종가는 신규 테이블에 2년치 저장하고, 없으면 data.go.kr API로 적재한다. 당일은 라이브 시세를 쓴다.

진입점: 메인(홈) 헤더 우측 아이콘 → 계좌별 자산 변화 페이지 / 종목 상세 종목명 우측 아이콘 → 종목별 자산 변화 페이지.

### 확정 사항 (사용자 결정 + 실측)
- **백필**: 진입 시 동기 적재(종목별 watermark = 저장된 `max(close_date)`, 그 이후~어제만 채움). 게이트웨이 현재 정상(실측 6/6, 과거 저성공률은 쿼터 이슈).
- **차트**: 한 화면 ~3개월 창 + y축 자동. 좌/우 스와이프 팬(최대 2년). recharts 커스텀 윈도우 슬라이스, **Brush 미사용**.
- **범위**: 전체 한 번에(계좌별 + 종목별 + 진입 아이콘 2곳).
- **linchpin 실측 검증 완료**: `getStockPriceInfo` + `likeSrtnCd`+`beginBasDt`/`endBasDt` 범위 조회 지원, `clpr`(종가)·`basDt` 반환, 거래일만 응답(캘린더 불필요).

## 목표 (완료 기준)
- 홈 헤더 아이콘 → `/assets` 진입 시 계좌(필터 반영)의 일별 자산 추이 차트 + 목록 표시.
- 종목 상세 아이콘 → `/assets?ticker=...` 진입 시 해당 종목 일별 평가액 추이 표시.
- 차트 3개월 창 좌/우 스와이프 팬(최대 2년), 스케일 변화 없음, tooltip/active-dot 등 포커스 컨트롤 없음.
- 종가 누락일은 진입 시 data.go.kr 적재(watermark 증분). 당일 점은 라이브 시세.
- `pnpm -C fe exec tsc --noEmit` 통과, `cd be && poetry run pytest -q` 통과.

## 설계

### 핵심 알고리즘 (서버 읽기 시점 계산, 계좌뷰/종목뷰 공통)
1. 스코프(계좌 필터 or 단일 종목) 거래를 `sort_for_calc` 로 walk → 종목별 수량 step function.
2. 날짜 범위 = `[max(스코프 최초 매수일, 오늘-2년), 오늘]`.
3. 거래일 집합 = 적재된 종가 `close_date` 합집합(∪ 오늘).
4. 각 거래일 d: `자산(d) = Σ_종목 qty(d) × close≤d(종목)` (종목별 직전 종가 carry-forward).
5. d=오늘: 저장 종가 대신 `fetch_quotes_by_keys` 라이브 시세.
6. O(날짜수 × 종목수), 날짜수 ≤ ~500 → Python 직접 계산.

> 자산 = **보유 종목 평가액**(현금 잔고 제외 — 과거 현금 이력 없음). 응답·목록에 명시.

### 주요 변경 파일

**BE — 데이터층**
- `supabase/migrations/026_daily_close_prices.sql` — PK `(country_code, ticker, close_date)`, `close_price numeric(15,2)`, `(ticker, close_date desc)` 인덱스. `stocks` 테이블 RLS/grant 미러.
- `be/src/invest_note_api/services/daily_price_seed.py` — `fetch_daily_closes(api_key, ticker, begin, end)`(getStockPriceInfo 범위, `_get_with_retry`/`_extract_items`/`_basdt_to_date` 재사용, `clpr`→close·`srtnCd` 정확 일치 필터) + `backfill_closes(conn, tickers, earliest)`(종목별 watermark 이후만 fetch→upsert, 실패 skip+flag) + `prune_older_than(conn, cutoff)`.
- `be/src/invest_note_api/db_ops/daily_prices_repo.py` — `get_watermarks` / `get_closes` / `upsert_closes`(executemany on-conflict) / `prune_older_than`.

**BE — 엔드포인트**
- `be/src/invest_note_api/domain/asset_history.py` — 핵심 알고리즘 순수 함수(`walk_trades`/`sort_for_calc` 재사용).
- `be/src/invest_note_api/schemas/asset_response.py` — `CamelModel`(`series:[{date,value}]`, `items`, `incomplete`, `asOf`).
- `be/src/invest_note_api/routers/assets.py` — `GET /assets/history?accountId=&ticker=` (스코프 산출 → backfill → get_closes → 오늘 시세 → asset_history 계산). `accountId` 는 `list_trades_with_account` 재사용. `main.py` 등록.
- `be/src/invest_note_api/routers/admin.py` — (옵션) `POST /admin/seed/daily-prices` 사전 적재(동일 fetcher, cron pre-warm).

**FE**
- `fe/src/lib/api-client.ts`(+`query-keys.ts`, 응답 타입) — `assetsApi.history({accountId, ticker})` + ROUTES.
- `fe/src/hooks/useAssetHistory.ts` — `useQuery`(usePortfolioSummary 참고).
- `fe/src/components/assets/AssetHistoryChart.tsx` — recharts `LineChart`, 3개월 윈도우 슬라이스 + 터치 스와이프 팬, y축 자동, Tooltip/grid/active-dot 제거, `dynamic(ssr:false)`.
- `fe/src/components/assets/AssetHistoryList.tsx` — series 표(날짜·자산·전일대비 / 종목뷰는 +종가·수량).
- `fe/src/components/assets/AssetHistoryPage.tsx` + `fe/src/app/(app)/assets/page.tsx` — `?ticker` 유무로 계좌뷰/종목뷰 분기. 계좌뷰는 `AccountFilter`+`useEffectiveAccountId`. `PageHeader` 뒤로가기.
- `fe/src/components/home/HomeDashboard.tsx` — 메인 헤더 `actions` 아이콘 → `/assets`.
- `fe/src/components/stocks/StockDetail.tsx` — 종목명 옆 아이콘 → `/assets?ticker=&country=&name=`.

> BottomNav 미변경(진입은 헤더 아이콘 2곳).

## 구현 체크리스트 (의존 순서)

**Phase 1 — BE 데이터층**
- [ ] `026_daily_close_prices.sql` (stocks RLS/grant 미러) → verify: 마이그레이션 적용·테이블 생성
- [ ] `daily_price_seed.py` fetcher → verify: 실측 응답 shape mock 단위테스트
- [ ] `daily_prices_repo.py` (watermark/get/upsert/prune) → verify: 단위테스트/쿼리 리뷰

**Phase 2 — BE 엔드포인트**
- [ ] `domain/asset_history.py` → verify: 합성 거래+종가 단위테스트
- [ ] `schemas/asset_response.py` + `routers/assets.py` + `main.py` 등록 → verify: `GET /assets/history` pytest
- [ ] (옵션) admin `POST /admin/seed/daily-prices` → verify: 202

**Phase 3 — FE**
- [ ] api-client `assetsApi.history` + query-keys + 타입 + `useAssetHistory` → verify: tsc
- [ ] `AssetHistoryChart.tsx` 커스텀 팬 차트 → verify: 렌더·스와이프 팬
- [ ] `AssetHistoryList.tsx` + `AssetHistoryPage.tsx` + `app/(app)/assets/page.tsx` → verify: 양쪽 모드 로드
- [ ] 홈 헤더 진입 아이콘 → `/assets` → verify: 네비게이션
- [ ] StockDetail 종목명 옆 아이콘 → `/assets?ticker=` → verify: 네비게이션

**Phase 4 — 검증**
- [ ] `pnpm -C fe exec tsc --noEmit` + `cd be && poetry run pytest -q` 통과
- [ ] gstack 으로 계좌뷰/종목뷰 진입·차트 팬·목록 실측

## 우려사항 / 리스크
- **콜드스타트 백필 지연**: 최초 진입 시 보유종목 × 2년 fetch. watermark로 1회만 무겁고 이후 가벼움. 일부 실패는 `incomplete` 플래그로 부분 표시.
- **종가 결측/상폐**: carry-forward 보간으로 연속성 유지. 상폐는 마지막 종가 유지(억지 적재 금지).
- **차트 팬**: recharts 네이티브 팬 없음 → 커스텀 윈도우+터치. 모바일 320~430px 튜닝 필요.
- **현금 제외**: 자산=종목 평가액. UI에 의미 명시.
