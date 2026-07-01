# 보유종목 카드 "오늘 등락" 표시 사양서

> 완료: 2026-07-01

## 배경 / 목적
홈 보유종목 카드(`HoldingCard`)의 현재가 아래 등락율이 지금은 **누적 등락율**(현재가 vs 평균매수단가)이다.
사용자는 "현재가 옆 등락"이 **오늘(전일 종가 대비) 등락**이길 기대한다. 요구:

1. 누적 등락율을 우측 상단 "누적 수익 금액"(`unrealizedPnL`) **아래로 이동**.
2. 현재가 아래 등락율을 **오늘 기준**(전일 종가 대비 %)으로 교체.
3. 현재가/오늘등락율 색상을 오늘 등락율 기준으로 (상승=`--rise` 빨강 / 하락=`--fall` 파랑).

핵심 관건: "오늘 등락율" 데이터가 현재 BE 시세 응답에 없다 → BE 시세 파서에서 확보해야 한다.

## 범위 (Scope)
- 포함:
  - BE `quotes.py` 파서 4종(naver realtime/basic, yahoo KR, yahoo US, kis)에서 오늘 등락율(`change_pct`) 추출 → `/stocks/quote` 응답에 additive 노출.
  - FE `portfolio.ts`: `QuoteMap`/`Position` 타입 + `mergeQuotes` overlay.
  - FE `HoldingCard.tsx`: 레이아웃 재배치 + 오늘등락 색상.
- 제외:
  - DB 스키마/Alembic 변경 (없음 — 있으면 멈추고 리더 보고).
  - `/portfolio/summary` 응답에 changePct 추가 (BE lite 응답은 그대로 — 시세는 FE overlay 유지, [[project_portfolio_summary_lite_quotes]] 계약 준수).
  - 종목 상세(`StockDetail`)·기록 탭 등 다른 화면 (홈 카드만).
  - `lib/quotes.ts`(legacy 직접 fetch), `makePosition`/`quote()` 테스트 헬퍼 — optional 필드라 무변경.

## 확정 BE↔FE Shape (⚠ 최우선 정합 포인트)

`/stocks/quote` 는 raw `dict` 를 반환한다(`response_model` 없음, alias generator 없음).
FastAPI 는 camelCase 로 바꾸지 않는다 — 기존 wire 는 `as_of`/`traded_on` **snake_case**이고 FE `QuoteMap` 도 `as_of` 로 읽는다.

| 계층 | 필드명 | 타입 |
|------|--------|------|
| Wire (BE→FE, `/stocks/quote`) | `change_pct` (snake_case) | `number \| null` (없으면 키 자체 생략 가능) |
| FE `QuoteMap[key]` | `change_pct?` | `number \| null \| undefined` |
| FE `Position` (도메인) | `changePct?` | `number \| null \| undefined` |

- **wire 는 `change_pct`(snake_case)** — `as_of`/`traded_on` 관행과 일치. 리더 브리프의 "camelCase changePct 노출"은 FE 도메인 필드(`changePct`)를 wire 와 혼동한 표현이며, wire 가 camelCase 면 FE 가 `undefined` 로 읽어 **오늘등락이 영구히 중립 degrade(크래시 없이 조용히 죽음)**. 이 drift 차단이 본 스펙의 핵심.
- `change_pct` = **native 통화 기준 오늘 등락율(%)**, 전일 종가 대비. 부호 포함 float, 소수 유효. 확보 실패 시 `None`.

## 오늘 등락율 산출 원칙 (be-engineer 필독)

**원칙: ratio 필드를 신뢰하지 말고 전일종가로 계산하라.** 계산식이 부호-안전(sign-safe)하다.

- **Yahoo (KR/US)**: meta 에 ratio 필드 없음 → 계산 강제.
  `change_pct = (regularMarketPrice - previousClose) / previousClose * 100`.
  전일종가 필드는 `previousClose` 우선, 없으면 `chartPreviousClose`. 둘 다 없거나 0 이하면 `None`.
- **KIS (FHKST01010100)**: output 에 `prdy_ctrt`(전일 대비 등락율) 네이티브 존재 후보 → be-engineer 가 실응답으로 확인. 있으면 그대로 파싱(fallback 경로가 change_pct 를 null 로 버리지 않게). 없으면 `None`.
- **Naver (realtime/basic)**: ⚠ **부호 함정.** 일부 Naver 응답은 `fluctuationsRatio` 를 **무부호 크기**로 주고 방향은 별도 코드(`risingFalling` 등)로 준다 → 순진하게 파싱하면 하락 종목이 상승으로 뜬다.
  - 전일종가 필드(예: `previousClosePriceRaw`/전일종가)가 응답에 있으면 **그것으로 계산**(부호 함정 회피).
  - ratio 필드만 있으면, **실제 상승 종목과 하락 종목 양쪽의 실응답을 캡처해 부호를 검증한 뒤** 파서를 확정. 필드명 추측 금지 — 실응답 캡처가 verify 조건.

## degrade / 휴장일 원칙
- `change_pct` 확보 실패/None → 오늘등락 **미표시**(현재가만), 현재가 색상 **중립**(`signColor(_, "none")`, 즉 foreground). 라이브 앱 파손 금지 — 응답은 additive.
- 휴장일: `traded_on` 이 오늘이 아니어도 별도 0 처리 불필요. 소스가 주는 값(전일 종가 대비 최종 체결가) 그대로 표시.

## 작업 단위

### 1. [BE] `api/src/invest_note_api/external/quotes.py`
- `QuoteResult` TypedDict 에 `change_pct: float | None` 추가.
- 파서 시그니처 리플: `_parse_realtime_price`/`_parse_basic_price`/`_parse_yahoo_chart_price` 반환 `tuple[float, str|None]` → `tuple[float, str|None, float|None]`(price, traded_on, change_pct). `_try_endpoint` 언팩 + `QuoteResult` 4곳 생성(naver 경로 `_try_endpoint`, `_fetch_yahoo_us`, `_fetch_kis`) 갱신.
- yahoo: previousClose/chartPreviousClose 로 계산. naver: 위 부호 원칙. kis: `prdy_ctrt` 확인.
- 전 파서 경로가 `change_pct` 키를 항상 채운다(값 없으면 명시 `None`).
- verify: `cd api && poetry run pytest tests/test_quotes.py -q` (fixture 기반 파서 회귀 — rising/falling 양쪽 케이스 + change_pct null 케이스 추가). [[feedback_broker_parser_fixture_tests]] — 합성 행만으론 shape/부호 버그 못 잡으니 실응답 shape 픽스처 사용.
- 의존: 없음.

### 2. [QA-BE] quote 응답 shape + 파서 정합 검증
- `/stocks/quote` JSON 이 `change_pct`(snake_case) 로 나가는지(camelCase 아님) 확인.
- **4개 provider 경로 전부**(naver realtime/basic, yahoo KR, yahoo US, kis)가 `change_pct` 를 채우거나 명시 `None` 인지 — naver 만 확인하고 넘어가지 말 것.
- naver 부호: 하락 종목 픽스처에서 `change_pct < 0` 인지.
- verify: `cd api && poetry run pytest tests/test_quotes.py -q` 통과 + 응답 키 snake_case 육안 확인.
- 의존: 단계 1 (`addBlockedBy` 1).

### 3. [FE] `app/src/lib/portfolio.ts`
- `QuoteMap` 타입에 `change_pct?: number | null` 추가 (optional — legacy `lib/quotes.ts`·테스트 헬퍼 무변경 유지).
- `Position` 인터페이스에 `changePct?: number | null` 추가 (optional — BE portfolio lite 응답엔 필드 없음 → 초기엔 undefined, mergeQuotes 만 채움).
- `mergeQuotes`: quote 존재 브랜치에서 `changePct: quote.change_pct ?? null` 추가. quote null 브랜치(`if (!quote) return pos`)는 무변경(degrade).
- verify: `pnpm -C app exec tsc --noEmit` + `pnpm -C app test src/lib/__tests__/portfolio.test.ts`.
- 의존: 단계 1 (wire 필드명 확정 후 — `addBlockedBy` 1).

### 4. [FE] `app/src/components/home/HoldingCard.tsx`
- position 구조분해에 `changePct` 추가.
- 우측 상단(line 98–122): `unrealizedPnL` <p> 아래에 **누적 등락율**(`priceChangePct`) <p> 추가 — `formatPctSigned(priceChangePct)`, `signColor(priceChangePct, "muted")`, `priceChangePct !== null` 가드.
- 현재가 열(line 126–151): 현재가 텍스트 색상 `signColor(priceChangePct,...)` → **`signColor(changePct, "none")`** 로 교체(오늘등락 기준). 현재가 아래 pct 를 `priceChangePct` → **`changePct`** 로 교체, `formatPctSigned(changePct)` + `signColor(changePct, "muted")`.
- ⚠ 가드는 **`changePct != null`(loose)** 사용 — optional 이라 `number | null | undefined`. `!== null` 쓰면 undefined 가 통과해 `formatPctSigned(undefined)` 크래시.
- `priceChangePct` 계산 로직(line 55–58)은 유지(누적 등락율 = 이동한 값).
- verify: `pnpm -C app exec tsc --noEmit` + 동작 시나리오: (a) changePct 양수 → 현재가/오늘등락 빨강, (b) 음수 → 파랑, (c) null → 오늘등락 미표시·현재가 중립, (d) 우측 상단에 누적 등락율 표시.
- 의존: 단계 3 (`addBlockedBy` 3).

### 5. [QA-FE] Position↔QuoteMap 정합 + 카드 검증
- `mergeQuotes` 가 `change_pct`(wire)→`changePct`(도메인) 매핑 정확한지.
- HoldingCard 가드 `!= null` 확인(undefined 안전).
- 색상 규칙: 상승 `--rise`(빨강)/하락 `--fall`(파랑) 한국 관행 준수([[feedback_circular_import_colors_trading]] PNL_COLORS 경유).
- 레이아웃: 우측 상단 누적등락 이동 + 현재가 아래 오늘등락. mobile-first.
- verify: `pnpm -C app exec tsc --noEmit` + `pnpm -C app test` (portfolio 테스트).
- 의존: 단계 3, 4 (`addBlockedBy` 3, 4).

## 완료 조건
- [x] 단계 1: `test_quotes.py` 통과 (rising/falling/null 케이스).
- [x] 단계 2: 4 provider 경로 change_pct + wire snake_case 확인.
- [x] 단계 3: `tsc` + `portfolio.test.ts` 통과.
- [x] 단계 4: `tsc` + 동작 시나리오 4종.
- [x] 단계 5: shape 정합 + 색상/레이아웃 검증.
- [x] `docs/decisions.md` 갱신 불요 (기존 snake_case passthrough·degrade 관행 재사용, 신규 트레이드오프 결정 없음). 단, wire `change_pct` naming 은 summary 에 확정 기록.
- [x] spec → `docs/spec-history/2026-07-01-holding-today-change.md` 이동 준비.
