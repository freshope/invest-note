# Spec: 해외주식(US) 지원 — Phase A (기반 plumbing)

## 배경 / 문제

로드맵 v2 항목 "해외 주식 지원(Yahoo Finance, USD/KRW 환율, 크로스 통화 분석 정합성 포함)"의
첫 슬라이스. 코드베이스는 이미 다국가 확장을 염두에 두고 설계됨 — `trades`/`stocks`/
`daily_close_prices` 에 `country_code`/`exchange`/`currency`, 포지션 키 `TICKER:COUNTRY`,
분석 `by_country` 집계, 시세 key 포맷 `code:country`, FE `QuoteMap.currency` 가 모두 존재.

**핵심 제약(분할 근거):** 대시보드 총액(`build_totals`, FE `applyQuotesToTotals`)은 항상
모든 포지션을 합산한다. 따라서 "해외 매수 차단 해제"와 "통화 인지 KRW 환산 합산"은 분리
불가능하게 커플링되어 있다 — 차단을 푸는 순간 FX 환산 없이 USD+KRW 숫자가 **조용히** 더해져
총액이 틀린다(에러 없음). 그래서 epic 은 vertical slice 가 아니라 **레이어**로 나눈다.

**Phase A 의 안전성:** 현재 해외 거래는 dormant(해외 BUY 스키마 차단 + 브로커 import USD skip +
seed 에 비-KR 거래 없음). Phase A 는 거래를 활성화하지 않으므로 합산 정합성을 건드리지 않는다.
순수 인프라/유틸만 추가 → 기존 KRW 동작 무변경.

이번 브랜치 범위: **Phase A 만**. Phase B(거래 활성화+통화 인지 합산), Phase C(USD import)는
`docs/backlog.md` 에 epic 으로 기록하고 각각 별도 issue-start 로 진행.

## 목표

- 종목 검색 API 가 US 종목(country_code="US")도 반환한다 (BE).
- US 티커 시세를 Yahoo 로 조회해 `currency="USD"` 와 함께 반환한다.
- USD/KRW 환율을 조회·캐시하는 서비스/엔드포인트가 동작한다 (향후 KRW 환산 합산용).
- FE 에 통화 인지 금액 포맷 유틸(₩/$ 분기)이 준비된다 (단위 테스트 통과).
- 위 모두 기존 KRW 경로·총액 합산에 영향이 없다 (회귀 없음).

향후 표시 전략(사용자 확정): **KRW 환산 단일 총액** — Phase A 의 FX 인프라가 이를 뒷받침.

**Phase A 비목표(=Phase B):** 해외 BUY 차단 해제, 통화 인지 walker/합산/분석, FE 검색
필터 해제·통화 표시 와이어링, 거래 입력/상세 화면 통화 표시.

## 설계

### 접근 방식

1. **US 시세 — Yahoo provider 확장.** `_fetch_yahoo` 는 현재 `.KS/.KQ` suffix + `currency`
   하드코딩(`CURRENCY_KRW`). US 는 suffix 없는 티커로 `YAHOO_CHART_URL` 조회하고 응답
   `meta.currency` 를 그대로 사용. `fetch_quotes_by_keys` 가 지금은 KR entry 만 처리(비-KR
   null) — US entry 를 US fetch 로 라우팅. `_try_endpoint`/`_parse_yahoo_chart_price` 가
   `currency` 를 인자/응답에서 받도록 일반화(현재 KRW 고정).

2. **USD/KRW 환율 — 신규 모듈.** `external/fx.py` 에서 Yahoo `KRW=X`(chart v8) 조회 +
   TTL 캐시(시세 캐시 패턴 재사용). 라우터 `GET /fx/rate?base=USD&quote=KRW` 또는
   `/stocks/fx`. 무료·API 키 불필요. Phase B 의 KRW 환산 합산이 소비할 단일 진실원.

3. **US 종목 마스터 seed.** `upsert_stocks` 는 이미 `country_code`/`currency`/`exchange`
   파라미터화 완료. `seed_stocks.py` 에 US 소스 추가 — nasdaqtrader.com 공개 심볼 디렉터리
   (`nasdaqlisted.txt` + `otherlisted.txt`: symbol·name·exchange, 무료). 볼륨이 크므로
   (~8천) 보통주/ETF 위주 필터 권장. `country_code="US"`, `currency="USD"` 로 upsert.

4. **종목 검색 country 확장.** `stocks_repo.search` 는 `country_code` 파라미터 보유(기본 KR).
   검색 라우터/서비스가 US 결과도 포함하도록 — country 파라미터 수용 또는 KR+US 병합.
   FE 필터는 그대로 두므로(Phase B 에서 해제) **사용자 가시 변화 없음** — 안전.

5. **FE 통화 포맷 유틸(준비만).** `lib/format.ts` 의 `formatPnL`/`fmt` 후행 "원" 하드코딩을
   통화 파라미터화한 신규 유틸 추가(기존 함수는 KRW 기본 유지로 호출부 무변경). 와이어링은
   Phase B. `country_code`/`currency` → 기호(₩/$) 매핑 헬퍼.

### 주요 변경 파일

- `be/src/invest_note_api/external/quotes.py` — Yahoo US fetch + `fetch_quotes_by_keys`
  비-KR 라우팅, `currency` 일반화
- `be/src/invest_note_api/external/fx.py` *(신규)* — USD/KRW 환율 조회+캐시
- `be/src/invest_note_api/routers/stocks.py` — FX 엔드포인트 + 검색 country 확장
- `be/src/invest_note_api/db_ops/stocks_repo.py` — 검색 country 병합(필요 시)
- `be/scripts/seed_stocks.py` — US 종목 소스 추가
- `be/src/invest_note_api/services/stock_seed.py` — US 소스 파서(필요 시)
- `fe/src/lib/format.ts` — 통화 인지 포맷 유틸 + 기호 매핑
- 테스트: `be/tests/test_quotes*.py`, `be/tests/test_fx*.py`(신규),
  `fe/src/lib/__tests__/format.test.ts`

## 구현 체크리스트

작은 단위(1 항목 ≈ 1 파일)로, 의존 순서대로:

- [x] **A1. FX 조회 모듈** `external/fx.py` — Yahoo `KRW=X` + TTL 캐시. `tests/test_fx.py`.
- [x] **A2. FX 엔드포인트** `routers/stocks.py` — `GET /stocks/fx`. `tests/test_stocks.py::TestStocksFx`.
- [x] **A3. US 시세 provider** `quotes.py` — Yahoo US fetch(meta.currency) +
      `fetch_quotes_by_keys` US 라우팅(`_entry_fetch_fn`). KR 회귀 + US fetch 테스트.
- [x] **A4. US 종목 검색** `stocks_repo.search_multi` + `routers/stocks.py` — KR+US 병합
      (FE 필터 유지로 가시 변화 없음). 검색 테스트.
- [x] **A5. US 종목 seed** `stock_seed.py`(`_parse_nasdaqtrader`/`fetch_nasdaq_us`/`seed_us`) +
      `scripts/seed_us_stocks.py` — nasdaqtrader 소스, US upsert. 파서 단위 테스트(네트워크 격리).
- [x] **A6. FE 통화 포맷 유틸** `lib/format.ts` — `formatMoney`/`formatPnLCurrency`/
      `currencyForCountry`/`currencySymbol` + ₩/$ 매핑. `format.test.ts` 단위 테스트.
- [x] **A7. backlog epic 기록** `docs/backlog.md` — Phase B/C 항목 추가.
- [x] BE 테스트 통과 (`cd be && poetry run pytest -q`) — 529 passed.
- [x] FE 타입 체크 통과 (`pnpm -C fe exec tsc --noEmit`) + FE 테스트 (166 passed).

## 우려사항 / 리스크

- **US 종목 데이터 볼륨/품질:** nasdaqtrader 디렉터리는 ~8천 심볼. 보통주/ETF 필터·정제
  필요. 첫 구현은 인기 종목 위주 부분 seed 로 시작 가능.
- **Yahoo 비공식 API:** US chart 엔드포인트도 비공식 — 레이트리밋/포맷 변동 가능. 기존
  Naver/Yahoo 와 동일한 graceful fallback(null) 패턴 유지.
- **해외 SELL latent 경로(기존 이슈):** 해외 BUY 만 차단되고 해외 SELL 은 스키마 통과(수동
  입력 도달 가능, 단 선행 BUY 없으면 실제 포지션 미생성). Phase A 가 악화시키지 않음 —
  통화 인지 합산과 함께 Phase B 에서 처리.
- **메모리 정정 필요(Phase B 용):** `feedback_fe_trade_sort_for_calc` 의 "portfolio.ts 전부
  dead code" 는 부분 오류 — `applyQuotesToTotals`/`applyQuotesToSnapshots` 는 live(BE 결과에
  시세 overlay). Phase B 통화 인지 합산 시 죽은 `buildTotals` 가 아닌 이 live 함수를 수정해야
  함. 구현 진입 시 메모리 정정 예정.

## Phase B — 정합성 슬라이스 (이 브랜치에서 이어서 완료)

> 사용자 요청("순차적으로 계속 진행")으로 Phase B 를 같은 브랜치에 이어 구현. 차단 해제 +
> 통화 인지 KRW 환산은 분리 불가 커플링이라 한 덩어리로 진행.

설계 결정: per-position 값은 native($) 유지·합산만 KRW 환산 / `pnl_map` 을 KRW 로 한 번 변환해
다운스트림 무변경 / 현재 환율(historical 은 backlog) / 현금 KRW 단일 / 응답 shape 무변경
(Position.country 로 통화 derive) / FX 실패 시 US 제외 + missing 노출.

- [x] **B1.** 해외 BUY 차단 해제(`schemas/trade.py`) + `domain/trade_types`
      `currency_for_country`/`to_krw` 헬퍼 + 단위 테스트(`test_fx_convert.py`).
- [x] **B2.** `realized_pnl.build_pnl_map_krw` — SELL profit_loss 통화→KRW.
- [x] **B3.** `build_totals`/`build_account_snapshots`/`concentration` KRW 환산 + 환율 없는
      US 제외·`missing_quote_tickers` 노출. (`holding_invested_amount` 은 단일통화 차트라 native 유지.)
- [x] **B4.** 라우터 fx 주입 — `portfolio`/`analysis` 가 비-KR 거래 시 `fetch_usdkrw` 조회.
- [x] **B5.** BE 통화 혼재 회귀 테스트(`test_portfolio_logic.py::TestCurrencyConversion`).
- [x] **B6.** FE overlay KRW 환산 — `applyQuotesToTotals`/`applyQuotesToSnapshots` + `toKRW`.
- [x] **B7.** `useFxRate` 훅(`GET /stocks/fx`) + `HomeDashboard` 주입(해외 보유 시만 enable).
- [x] **B8.** `StockSearchInput` KR 필터 해제(US 선택 가능) + `HoldingCard` native 통화 표시.
- [x] **B9.** FE 통화 혼재 테스트(`portfolio.test.ts`) + `format.test.ts`.
- [x] BE `pytest -q` 528 passed · FE `tsc`·`test` 169 passed.

남은 후속(비범위, backlog 기록): Phase C(import), 거래 입력/상세 폼 통화 라벨(cosmetic),
historical-FX 정밀화, 분석 size 분포 통화 정밀도, 해외 SELL UX.

## 2026-06-09 정책 재확정 — 거래등록 입력 모델 (달러·원화 직접입력)

> 기본 정책 재변경(`docs/decisions.md` 2026-06-09): 원화기준 통합표시 + 달러 보조는 그대로,
> 거래 등록은 **환율 직접입력 → 체결 원화 직접입력**으로 변경.

- [x] **B11.** `TradeBasicForm` — 해외 거래 입력칸을 `환율(USD/KRW)` → **`체결 원화(KRW)`** 로 교체.
      제출 시 `exchange_rate = 체결원화 / (price×quantity)` 역산해 BE 전송(BE 계약·`029` 마이그레이션 무변경).
      체결 원화 = 원금(가격×수량)만, 수수료·제세금은 USD 유지. 기본값은 현재 시세 환율 기준 제안값(수정 가능),
      US 미입력 시 zod superRefine 검증. FE `tsc` 통과 · `pnpm test` 173 passed.

## Phase C (비범위)

- **Phase C — import + 엣지:** Samsung/Toss USD 파서 활성화, 해외 세율/수수료 규칙, 엣지케이스.

## Phase D — 해외주식 잔여 작업 (정합/기능/UX)

> Phase A/B 로 거래 활성화 + 통화 인지 KRW 환산 합산이 완료됐고, 2026-06-09 입력모델
> 재설계로 등록폼이 통화 인지가 됐다. Phase D 는 그 위에 남은 **공백(일별종가 US 미지원),
> SPOF(US 시세 단일 공급자), 비대칭(수정 폼·TradeUpdate 통화 미인지), 정밀도(분석 size 분포
> native 혼입)** 를 메운다. Phase C(브로커 USD import)는 별도 진행 — 본 섹션 비범위.

### 배경 / 문제 (코드 사실 기반)

- **D1 일별종가 공백:** `services/daily_price_seed.py::backfill_closes` 는 KR 전용이다.
  primary 는 env `DAILY_PRICE_PROVIDER`(=data_go_kr) 로 국가 무관 고정 주입되고
  (`routers/assets.py:86-95`), tail-gap 보충은 `if gap_fetch is not None and country_code == "KR"`
  (`daily_price_seed.py:405`) 로 KR 에서만 돈다. 게다가 early-return 가드가
  `if not tickers or not api_key`(`:336`) 로 **data.go.kr api_key 부재 시 incomplete** 처리 →
  US 는 데이터 0건 + `incomplete=True`. 결과: `/assets/history`(country 스코프, default KR,
  `assets.py:96-98`)에서 US 는 빈 series.
  - **FE 현실(원 지침 정정):** 작업 지침은 "미니차트가 `isKrStockCode` 게이팅"이라 했으나
    **코드는 다르다.** `StockDetail.tsx:46` 의 `metaCodes = isKrStockCode(...) ? [ticker] : []`
    는 `useStockMeta(metaCodes)`(:49) → **시총/연금 뱃지 메타 쿼리 전용**(`StockMetaBadges`,
    :114)이지 차트가 아니다. StockDetail 에는 미니차트 자체가 없다(차트 import 없음).
    자산추이는 "자산 추이" 버튼(`onAssetHistoryPress`, :88-99, **country 게이팅 없음**) →
    `openAssetHistory` → `AssetHistoryView`(`components/assets/AssetHistoryView.tsx`)가
    `useAssetHistory({country})`(`hooks/useAssetHistory.ts`, country 를 BE 에 그대로 전달,
    게이팅 없음)로 그린다. **즉 FE 는 US 를 막지 않는다** — BE(D1-2)가 US series 를 채우면
    자산추이는 **FE 코드 변경 없이** 작동한다. 따라서 D1-3 은 신규 게이팅 해제가 아니라
    **검증/배너 확인 단위**로 축소.

- **D2 US 시세 SPOF:** US quote 는 `external/quotes.py::_fetch_yahoo_us` 단일 공급자
  (`_entry_fetch_fn:278-279`, US→`_fetch_yahoo_us` 만). Yahoo 실패 시 `_get_cached`(`:283`)가
  `result=None` 을 **무조건 캐시에 기록**(`:315 state.cache[key] = result`)해 US 평가액이
  TTL(`QUOTE_CACHE_TTL`) 동안 통째로 missing. 반면 FX 는 방금 stale-유지로 고침
  (`external/fx.py:114-125`: fetch 실패 시 None 을 박지 않고 직전 성공값 `cached` 반환).
  quote 도 동일 의도 적용 대상.

- **D3 수정 폼 통화 비인지:** `components/records/TradeEditPanel.tsx` 는 가격·수량을 **실제
  편집**한다(`:187-214`, Controller name="price"/"quantity"). 라벨은 "가격 (원)" 하드코딩
  (`:188`)이고 `onSubmit`(`:126-142`)은 `exchange_rate`/체결원화를 patch 에 **미포함**.
  → US 거래를 수정하면 price(USD)는 바뀌는데 환율은 기존값 고정이라, 등록폼(B11)이 박제한
  체결환율과 어긋나며 KRW 원가·실현손익이 조용히 틀어진다. (주: `TradeMetaBuyForm.tsx`/
  `TradeMetaSellForm.tsx` 는 전략·감정·태그·메모만 다루고 가격·환율 미편집 → D3 표면 아님.)

- **D4 TradeUpdate 비대칭:** `schemas/trade.py::TradeCreate` 에는 `_foreign_requires_exchange_rate`
  validator(`:131-137`)가 있으나 `TradeUpdate`(`:140-173`)는 없다. `exchange_rate` 는
  `pnl_affecting=True`(`db_ops/trades_repo.py:276`)라 patch 시 `validate_mutation` 경로
  (`routers/trades.py:425-431`)를 타지만, 그 함수는 oversell 만 본다. patch body 에 country_code
  가 없으므로(스키마 자체 검증 불가), 라우터가 이미 읽는 `existing`(`trades.py:417`, country_code 보유)
  으로 가드해야 한다.

- **D5 분석 size 분포 native 혼입 + as_of 미노출:** `routers/analysis.py:138-139`
  `_size_bucket(t.total_amount)` — `total_amount` 는 native(USD 거래는 달러 그대로,
  `trade_types.py:121` + exchange_rate 별도)라 USD BUY 가 KRW 버킷에 native 로 들어가 어긋난다
  (backlog `분석 size 분포 통화 정밀도` 항목). KRW 환산 필요(`to_krw(value, currency, usdkrw)`
  헬퍼 존재, `trade_types.py:71`). 별개로, 평가액이 어느 환율로 환산됐는지 투명성을 위해
  `FxRate.as_of` 노출 — 단 FE 는 이미 B7 `useFxRate` 가 `as_of` 를 가지므로 **FE-only 표시**로
  닫을 수 있다(BE 응답 shape 무변경).

### 설계 결정 (불변 제약)

- 거래 시점 환율 박제 → 원가·실현손익 = KRW 고정, 평가액 = 현재환율. native(USD) 보조 필드.
- FE 는 원화 primary + 달러 괄호(`MoneyText`).
- **기존 KR 경로 무변경** — D1/D2 는 country 분기로 US 만 새 경로, KR 은 한 줄도 안 건드린다.
- shape drift 가드: BE 응답 shape 변경은 D5 에서만(그조차 FE-only 로 회피 가능). 나머지는 무변경.

### 구현 체크리스트 (의존 순서 · 1 단위 ≈ 1~2 파일)

#### D1 [P1] US 일별종가 공급자 (가장 큰 공백)

- [ ] **D1-1 [BE] Yahoo daily-closes fetch + 파서** `services/daily_price_seed.py`
  - Yahoo chart v8 로 US daily closes backfill. **주의:** `YAHOO_CHART_URL`(constants.py:34)은
    이미 `?interval=1d&range=1d` 가 박혀 있어 historical 엔 부적합 → `range`(예 `2y`)/`interval=1d`
    를 받는 **새 URL 상수/빌더** 추가. 응답 파싱도 quote 와 다르다 — `_parse_yahoo_chart_price`
    는 `meta.regularMarketPrice`(현재가 1점)만 읽으므로, daily 는 `timestamp[]` +
    `indicators.quote[0].close[]`(epoch→KST date, null close skip)를 파싱하는 **새 함수** 필요.
    반환 형태는 기존 `fetch_*_daily_closes` 와 동일(`[{ticker, close_date, close_price}]`).
  - `_fetch_yahoo_us_closes(client, ticker, begin, end)` 추가 → registry 등록 불필요(국가 분기로 호출).
  - verify: `cd be && poetry run pytest tests/test_daily_price_seed.py -q` (네트워크 격리 파서 단위 테스트 + 범위 밖 행 가드)
  - 의존: 없음
- [ ] **D1-2 [BE] backfill_closes US 라우팅** `services/daily_price_seed.py`
  - `country_code == "US"` 일 때: env primary/gap 을 **우회**하고 `_fetch_yahoo_us_closes` 를
    primary 로, gap 없음. early-return 가드(`:336 not api_key`)가 US 를 막지 않도록 분기
    (US 는 data.go.kr api_key 불필요). KR 분기(`gap`, market 라우팅)는 무변경.
  - verify: `cd be && poetry run pytest tests/test_daily_price_seed.py -q` (US 라우팅이 yahoo 호출·KR 은 기존 경로 유지 회귀)
  - 의존: D1-1
- [ ] **D1-3 [FE/QA] US 자산추이 동작 확인 + incomplete 배너 점검** (게이팅 해제 불필요)
  - FE 는 이미 country-agnostic(위 배경 참조) → **코드 변경 없을 가능성 큼.** 실제 확인 사항:
    (a) US 종목 상세 "자산 추이" 진입 → D1-2 후 series 가 그려지는지, (b) 콜드스타트 시 일시
    `incomplete` 배너(`AssetHistoryView.tsx:212`) 문구가 US 맥락에 어색하지 않은지,
    (c) `isKrStockCode` 메타 쿼리(:46)는 **건드리지 말 것**(US ticker 를 `/stocks/meta` 로
    보내면 docstring 경고대로 가비지 → KR 6자리 전용 유지). 손볼 게 없으면 QA 체크로 닫고
    summary 에 "FE 무변경" 기록.
  - verify: `pnpm -C fe exec tsc --noEmit`(변경 시) + 동작 시나리오(US 자산추이 series 렌더)
  - 의존: D1-2

#### D2 [P1] US 시세 graceful fallback (SPOF 완화)

- [ ] **D2-1 [BE] quote stale-유지** `external/quotes.py`
  - `_get_cached`(`:283`)에서 fetch 결과가 `None`(실패)일 때, 기존 non-None 캐시 엔트리를
    **덮지 않고**, **현재 호출자와 후속 호출자 모두** 직전 성공값을 TTL 내 받는다
    (fx.py:114-125 의 `return cached` 시맨틱과 동일 — 현재 요청도 missing 으로 두지 말 것).
    **단 구분 필요:** "None = 정상(해당 심볼 데이터 없음)" vs "None = fetch 실패".
    `_fetch_yahoo_us` 는 실패와 데이터없음을 모두 None 으로 반환하므로, 실패 시그널을 명시
    (예: 예외 전파 또는 sentinel)하도록 fetch_fn 계약 조정 후 stale 유지. KR 경로(naver/kis
    fallback 으로 이미 다중 공급자)는 동작 변화 최소화.
  - verify: `cd be && poetry run pytest tests/test_quotes.py -q` (**동시 요청 + 연속 호출** 테스트: 1차 성공→캐시, 2차 실패→직전값 유지, single-flight inflight 경합 확인. 단일 호출 테스트만으론 부족)
  - 의존: 없음 (D1 과 병렬 가능)

#### D4 [P2] TradeUpdate foreign 환율 검증 (D3 의 BE 선행)

- [ ] **D4-1 [BE] PATCH 해외 환율 가드** `routers/trades.py` (권장) 또는 `schemas/trade.py`
  - patch 에 `exchange_rate` 가 있고 `existing.country_code` 가 해외(non-KRW)인데 값이 1.0 이면
    400. `existing` 은 이미 `:417` 에서 읽으므로 라우터 가드가 자연스럽다(`validate_mutation`
    은 oversell 전용 유지 — 책임 분리). create 의 `_foreign_requires_exchange_rate` 와 대칭.
  - verify: `cd be && poetry run pytest tests/test_trades_api.py -q` (US 거래 patch exchange_rate=1.0 → 400, 정상 환율 → 200, KR patch 무영향 회귀)
  - 의존: 없음
- [ ] **D4-2 [BE] price/qty 정정 시 환율 일관 검증(선택)** — D3-FE 가 체결원화 역산으로
    exchange_rate 를 항상 동봉하면 D4-1 가드로 충분. 별도 단위 불필요 시 생략, summary 에 기록.

#### D3 [P2] 거래 수정 UI 통화 인지 — 방향 ① (등록폼 B11 미러)

> **방향 결정:** ① 통화 인지 편집(체결 원화 재입력→환율 역산). 근거: TradeEditPanel 이 이미
> 가격·수량을 편집(`:187-214`)하므로 ②(차단) 는 "수정은 되는데 US 만 막힘"의 비일관을 낳는다.
> 등록폼 B11 이 동일 역산(`체결원화 / (price×quantity) = exchange_rate`)을 확립했으니 재사용.

- [ ] **D3-1 [FE] TradeEditPanel 통화 인지** `components/records/TradeEditPanel.tsx`
  - US 거래일 때: 가격 라벨을 "가격 ($)" 로, 추가로 "체결 원화(KRW)" 입력칸 노출(B11 패턴).
    제출 시 `exchange_rate = 체결원화 / (price×quantity)` 역산해 patch 에 동봉. KR 거래는
    현행 "가격 (원)" 무변경. 체결원화 미입력 US 는 zod superRefine 거부(B11 과 동일).
    수수료·제세금은 native 유지. (trade.country_code / exchange_rate 가 prop 으로 들어오는지
    확인해 기본 제안값 = price×quantity×기존환율 채움.)
  - verify: `pnpm -C fe exec tsc --noEmit` + `pnpm -C fe test`(역산 단위 + US/KR 분기 렌더) + 동작 시나리오(US 거래 가격 수정→체결원화 재입력→저장→KRW 원가 일관)
  - 의존: D4-1 (PATCH 가 역산된 exchange_rate 를 수용·검증해야 함)

#### D5 [P3] 분석 size 분포 KRW 환산 + FX as_of 노출

- [ ] **D5-1 [BE] size_dist KRW 환산** `routers/analysis.py:138-139`
  - `_size_bucket(t.total_amount)` → `_size_bucket(to_krw(t.total_amount, currency_for_country(t.country_code), usdkrw))`.
    `usdkrw` 는 이미 `:100-103` 에서 조회됨(해외 보유 시). 환산 불가(usdkrw None) USD 거래는
    버킷에서 제외(None skip) — 조용한 혼입 방지. KR 거래는 to_krw 가 그대로 통과(영향 없음).
  - verify: `cd be && poetry run pytest tests/test_analysis_api.py -q` (USD BUY 가 KRW 환산 버킷에 들어가고, usdkrw 없으면 제외되는 회귀)
  - 의존: 없음
- [ ] **D5-2 [FE] FX as_of 표시** (FE-only — BE shape 무변경)
  - 평가액/환산 영역에 환율 기준 시각 노출. B7 `useFxRate` 의 `FxRate.as_of` 를 그대로 표시
    (해외 보유 시만). 어느 컴포넌트(HomeDashboard 환산 합계 근처)인지 구현 시 확정.
  - verify: `pnpm -C fe exec tsc --noEmit` + 동작 시나리오(해외 보유 시 "환율 기준: HH:MM" 류 표기)
  - 의존: 없음

### 의존 그래프

```
D1-1(BE) → D1-2(BE) → D1-3(FE)        # US 일별종가: fetch/파서 → 라우팅 → FE 게이팅 해제
D2-1(BE)                               # US 시세 stale (독립, D1 과 병렬)
D4-1(BE) → D3-1(FE)                    # PATCH 환율 가드 먼저, 그 위에 수정 폼 역산
D5-1(BE)                               # size_dist 환산 (독립)
D5-2(FE)                               # FX as_of 표시 (독립, BE shape 무변경)
```

병렬 가능 진입점: D1-1 / D2-1 / D4-1 / D5-1 / D5-2.

### 완료 조건

- [ ] D1~D5 모든 단위 verify 통과
- [ ] BE 전체 회귀 `cd be && poetry run pytest -q` 무회귀 / FE `pnpm -C fe exec tsc --noEmit` + `pnpm -C fe test`
- [ ] 기존 KR 경로 동작 무변경(D1/D2 country 분기, D5 to_krw KR 통과 회귀로 확인)
- [ ] `docs/backlog.md` `분석 size 분포 통화 정밀도` 항목 D5 완료로 체크
- [ ] `docs/decisions.md` 갱신 — D2 quote stale-유지(SPOF 완화) 및 D3 수정폼 방향①(차단 대신 통화 인지) 결정 기록(트레이드오프 있는 선택)
- [ ] Phase D 완료 후 spec → `docs/issue-history/` 이동 준비
