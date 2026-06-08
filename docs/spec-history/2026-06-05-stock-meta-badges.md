# Spec: 종목 메타 뱃지 (마켓 / 시총순위 / 국민연금 보유)

> 완료: 2026-06-05

## 배경 / 문제

종목명 옆에 직관적인 메타 정보 뱃지를 붙여 사용자가 종목의 성격(어느 시장, 시총 규모, 국민연금 보유 여부)을 한눈에 파악하게 한다. 데이터는 이미 `stocks` 테이블에 모두 적재되어 있으나(`market`, `marcap_rank`, `nps_holding`) 현재 어떤 API 응답에도 노출되지 않아 BE 노출 + FE 뱃지 렌더가 필요하다. 뱃지 클릭 시 설명을 Popover로 띄운다.

## 목표

- 홈 보유종목 카드 / 종목 상세 / 거래 카드 / 거래 상세에서 종목명 옆에 마켓·시총순위·국민연금 뱃지가 **값이 있을 때만** 표시된다.
- 뱃지를 탭하면 바텀시트로 설명이 뜨고, 카드의 클릭/스와이프 동작은 트리거되지 않는다.
- 국민연금 held/major 는 라벨 텍스트로 구분된다: `연금보유` / `연금 5%+` (채움·색 동일 muted).
- `pytest`(BE), `tsc --noEmit`(FE) 통과.

## 설계

### 접근 방식

`/stocks/quote`(배치 시세) 패턴을 미러링한 **배치 메타 엔드포인트 + overlay 훅**으로 구현한다. 종목 메타는 거의 정적(일 단위 갱신)이므로 실시간 quote 경로나 portfolio/summary lite 계약은 건드리지 않는다.

- **데이터 흐름**: 각 화면의 상위 컴포넌트가 보이는 종목 코드를 모아 `useStockMeta(codes)` 한 번 호출 → `metaMap`(useMemo) → 각 카드에 `meta` prop overlay. (거래 리스트 N+1 방지: 개별 TradeCard가 아니라 상위 TradeList에서 일괄 조회.)
- **KR 필터**: `portfolio.ts`는 ticker 없는 포지션에 한글명을 ticker로 채우므로, `useStockMeta` 호출 전 `country==="KR"` + `/^\d{6}$/` 로 필터해 가비지 코드를 보내지 않는다.
- **마켓 뱃지 출처 분기** (ExchangeBadge 충돌 회피): 홈/종목상세는 `meta.market`, 거래 카드/상세는 기존 `trade.exchange` 사용. TradeHeaderCard의 기존 `ExchangeBadge`는 클릭형 `MarketBadge`로 교체(KOSPI 중복 렌더 방지).
- **바텀시트** (Popover에서 변경, 2026-06-05): 모바일에서 Popover는 위치가 불안정하고(스크롤 리스트 내 collision shift) 뱃지별로 열고 닫아야 해서, 어떤 뱃지를 탭해도 **바텀시트 하나**가 열려 그 종목에 표시된 뱃지 전체 설명을 한 페이지로 보여준다. shadcn Drawer(vaul) 설치 + `base/Drawer` 래퍼 추가. 트리거 버튼은 카드의 클릭/스와이프 레이어 안에 중첩되므로 `onClick`·`onPointerDown` 양쪽에서 `stopPropagation`.
- **색상**: 정보성 뱃지는 muted 통일. `PNL_COLORS`(rise/fall 빨강·파랑)는 손익 전용이라 사용 금지.

### 응답 shape 계약 (snake_case 통일 — quote pass-through 와 일관)

`GET /stocks/meta?codes=005930,000660` (KR 전용, 6자리 bare ticker)

```json
{
  "005930": { "market": "KOSPI", "marcap_rank": 1, "nps_holding": "major", "nps_as_of": "2026-03-31" },
  "000660": { "market": "KOSDAQ", "marcap_rank": 12, "nps_holding": null, "nps_as_of": null }
}
```

```ts
export interface StockMeta {
  market: string;
  marcap_rank: number | null;
  nps_holding: "held" | "major" | null;
  nps_as_of: string | null;
}
export type StockMetaMap = Record<string, StockMeta>;
```

## 구현 체크리스트

**BE**
- [x] B1 `be/.../db_ops/stocks_repo.py` — `fetch_meta(conn, codes)` 배치 조회 (snake_case dict)
- [x] B2 `be/.../routers/stocks.py` — `GET /stocks/meta` (get_quotes 미러)
- [x] B3 `be/tests/test_stocks_repo.py` — fetch_meta 단위 테스트
- [x] B4 `be/tests/test_stocks.py` — TestStocksMeta (200/빈/401)

**FE**
- [x] F1 `fe/src/lib/api-client.ts` — StockMeta 타입 + stocksApi.meta
- [x] F2 `fe/src/lib/query-keys.ts` — stockMeta 키
- [x] F3 `fe/src/hooks/useStockMeta.ts` (신규) — useQuotes 미러
- [x] F4 `fe/src/components/stocks/StockMetaBadges.tsx` (신규) — 바텀시트 뱃지 (ui/drawer + base/Drawer 래퍼 추가)
- [x] F5 `fe/src/components/home/HoldingsList.tsx` — 코드 수집 + metaMap
- [x] F6 `fe/src/components/home/HoldingCard.tsx` — 뱃지 렌더
- [x] F7 `fe/src/components/records/TradeList.tsx` — 코드 수집 + metaMap
- [x] F8 `fe/src/components/records/TradeCard.tsx` — 뱃지 렌더
- [x] F9 `fe/src/components/stocks/StockDetail.tsx` — 단일 조회 + 뱃지
- [x] F10 `fe/src/components/records/TradeHeaderCard.tsx` — ExchangeBadge 교체 + 뱃지
- [x] F11 `fe/src/components/records/__tests__/TradeCard.test.tsx` (신규) — 뱃지 탭 propagation 테스트
- [x] 타입 체크 통과 (`pnpm -C fe exec tsc --noEmit`)

## 검증 결과 (2026-06-05)

- BE: `poetry run pytest -q` 417 passed (로컬 supabase 필요)
- FE: `tsc --noEmit` 통과, `pnpm -C fe test` 158 passed
- 실제 DB 검증: `fetch_meta` 로컬 supabase 실행 — market=KOSPI/KOSDAQ/ETF/ETN/KONEX, nps_holding ∈ {held, major, NULL} 확인
- 뱃지 탭 propagation: RTL 테스트로 onPress 미호출 + 바텀시트 열림(전체 섹션 렌더) 검증

## 우려사항 / 리스크

- propagation 회귀: TradeCard(스와이프+suppressClickRef) 최고위험 — 뱃지 탭 명시 테스트
- memo 깨짐: metaMap을 React Query data에 useMemo (F5/F7)
- 마켓 뱃지 출처 분기: 홈/상세=meta.market, 거래=trade.exchange
