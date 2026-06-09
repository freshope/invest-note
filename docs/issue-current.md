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
