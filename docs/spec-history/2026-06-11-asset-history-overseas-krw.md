> 완료: 2026-06-11

# 자산추이 해외(US) 보유 KRW 환산 통일 사양서

> code-review finding A 후속. 자산추이(/assets/history) 전체·계좌뷰 + 종목뷰 모두에서
> 해외(US) 보유를 원화(KRW)로 환산해 포함한다. 환산 책임을 FE → BE 로 이관한다.

## 배경 / 목적

- **현황(불일치):** BE `routers/assets.py` 의 `country` 쿼리 기본값이 `'KR'` 이라 전체/계좌뷰
  (ticker=None)도 `country='KR'` 스코프로 처리 → US 보유를 통째로 제외, 곡선이 KR-only.
  반면 같은 화면 대시보드 합계(`merge_quotes(usdkrw)` + FE overlay)는 US 포함이라 **두 수치가 어긋난다.**
- **종목뷰만 부분 보정:** FE `AssetHistoryView.tsx` 가 US 종목뷰(`isUsStock`)에서만
  `asset-history-convert.ts` + `useFxRate` 로 현재 환율 KRW 환산. 전체/계좌뷰는 `rate=null` 이라 환산 안 함.
- **목적:** 환산을 BE 로 일원화해 전체/계좌/종목 모든 뷰에서 KRW 단위로 통일하고, 대시보드 합계와
  자산추이 총액의 단위·포함범위를 일치시킨다(finding A 해소).

## 확정된 설계 결정 (사용자 승인 — 변경 금지)

1. **환율 정책: 현재 환율(spot) 일괄 적용.** 일자별 historical FX 미적재이므로 모든 과거 일자
   US 평가액에 '오늘 usdkrw' 하나를 곱한다(종목뷰 현행과 동일 철학). FE 에 '현재 환율 기준
   (일자별 아님)' 고지 유지.
2. **범위: 전체/계좌뷰 + 종목뷰 모두 BE 에서 KRW 환산.** FE 의 환산(convert) + fxBlocked +
   useFxRate 환산 책임을 BE 로 이관, FE 에서 제거.

## 가정 (Assumptions)

- 해외=US 만 존재(OTHER 통화는 현재 없음, `currency_for_country` 가 KR/OTHER→KRW 처리).
- usdkrw 는 `fx.usdkrw_if_foreign` / `fetch_usdkrw`(spot) 으로 1회 조회. 거래 시점 `exchange_rate`
  는 사용하지 않는다(결정 1과 일관 — 모든 과거 일자에 동일 spot 적용).

## 범위 (Scope)

- 포함:
  - `compute_asset_history` 가 종목별 통화 인식 + usdkrw 1개로 KRW 합산. 종목 식별 키를
    `ticker+country` 로 일관화(`closes`/`live_quotes`/qty steps 동기).
  - `assets.py` 전체/계좌뷰 country 필터 제거 → 거래를 country 별로 분리해 backfill/get_closes/
    quotes 를 country 별 수행 후 합치기. usdkrw 는 해외 보유 시에만 1회 조회. `invested_amount`
    도 spot KRW 환산.
  - 응답에 `usdkrw`(float|None) + `has_foreign`(bool) 노출. AssetHistoryResponse + FE 타입 동기.
  - FE: `AssetHistoryView` 에서 환산/`useFxRate`/`asset-history-convert` 제거, BE KRW 값 직접
    사용. 고지 문구는 `response.usdkrw` 기반으로 재구성. USD 보조 병기는 종목뷰만 `value/usdkrw` 역산.
  - `asset-history-convert.ts` + 그 테스트 **삭제**.
- 제외:
  - 일자별 historical FX 적재(결정 1로 명시 보류).
  - 대시보드 합계(`/portfolio/summary`, `merge_quotes`) 자체 변경 — 이미 US 포함이라 무변경.
  - OTHER 국가/통화 신규 지원.
  - 현금/예수금 포함(자산 = 보유 종목 평가액 유지).

## 핵심 설계 결정 (다운스트림 correctness — 반드시 준수)

- **D1. closes 행에 country 태깅:** `get_closes` 반환은 `{ticker, close_date, close_price}` 뿐이라
  country 차원이 없다. 라우터가 country 별로 호출하므로, **merge 전에 각 행에 `country` 를 추가**
  해서 compute 로 넘긴다. compute 는 `(ticker, country)` 로 `closes_by_ticker` 를 만든다.
  → US/KR 티커 문자열 충돌(숫자형 티커 등) 방지.
- **D2. qty steps gid = `(ticker or asset_name) + country`:** `asset_name` fallback 은 유지하되
  country 를 키에 합성. ticker 없는 KR 보유가 깨지지 않게 fallback 보존.
- **D3. 통화 환산은 `to_krw(value, currency, usdkrw)` 재사용:** 직접 곱(`× rate`) 금지.
  `to_krw` 는 USD인데 usdkrw=None 이면 None 반환 → "조용한 USD-as-KRW 합산"을 구조적으로 차단.
  None 이면 그 종목 기여 제외 + `incomplete=True`(KR 은 항상 환산 성공이라 영향 없음).
- **D4. 단일 US 종목뷰 + usdkrw=None → flat-zero 곡선 금지:** US 기여 제외 시 US-only 종목뷰는
  매일 total=0(0 일직선)으로 빈 차트보다 나쁜 UX. 응답 `has_foreign=True` 플래그로 FE 가
  `(has_foreign && usdkrw==null)` 일 때 0 차트 대신 '환율 불가' 안내를 띄운다. 혼재 all/account뷰는
  KR 곡선 + incomplete 로 충분.
- **D5. invested_amount spot 환산:** `holding_invested_amount` 는 `cost_basis_native` 를 단일 통화
  가정으로 합산(혼재 스코프에서 native USD+KRW 무가산 버그). 곡선과 단위를 맞추려면 spot 으로
  KRW 환산해야 한다(거래 시점 환율 아님 — D 결정/결정1 일관).

## 작업 단위

### 1. [BE] `be/src/invest_note_api/domain/asset_history.py` — compute 통화-aware KRW 합산

- `compute_asset_history` 시그니처에 `usdkrw: float | None = None` 추가.
- `_qty_steps_by_ticker` → gid 를 `(ticker or asset_name):country` 합성 키로 변경(D2). 반환 키 또는
  내부 매핑에서 gid→country 를 보존(통화 판정용).
- `closes` 입력에 `country` 필드 추가 가정 → `closes_by_ticker` 를 `(ticker, country)` 키로 구성(D1).
  `live_quotes` 키도 `position_key(ticker, country)` 와 동일 형식으로 일관화.
- 일자별 합산: gid 의 country → `currency_for_country` → `to_krw(qty*price, currency, usdkrw)`(D3).
  None 이면 기여 제외 + `incomplete=True`.
- 종목뷰 items 의 `close` 는 **native(USD) 유지**, `value`/`change` 는 KRW. `qty` 유지.
- 함정: **G1**(종목별 sort_for_calc→walk_trades 분리 유지 — 한 walker 다종목 금지),
  **통화혼재 silent sum**(D3 to_krw 로 방지), **ticker+country 키 동기**(steps/closes/live_quotes 3축).
- verify: `cd be && poetry run pytest tests/test_asset_history.py -q`
  (호출부 시그니처 변경으로 기존 테스트 갱신 + 신규 케이스: KR-only / US-only(usdkrw 적용) /
   혼재 일자별 KRW 합산 / usdkrw=None 시 US 제외+incomplete / ticker+country 충돌(동일 ticker 문자열
   US·KR 동시 보유가 분리 합산되는지)).
- 의존: 없음

### 2. [BE] `be/src/invest_note_api/routers/assets.py` — country 분리 파이프라인 + fx + 응답 필드

- `get_asset_history` 에 `fx_state: FxCacheState = Depends(get_fx_cache_state)` 주입(portfolio 패턴).
- 전체/계좌뷰: `list_trades_with_account` 의 `country=` push 제거(ticker 지정 종목뷰는 유지 가능).
  로드한 전체 거래를 `trade_country(t)` 로 KR/US 그룹 분리.
- country 그룹별로 `backfill_closes`/`get_closes`/`fetch_quotes_by_keys` 를 각각 country_code 로 수행
  (US=Yahoo provider, KR=data.go.kr) 후 결과 합치기. `get_closes` 결과 각 행에 해당 country 태깅(D1).
- `live_quotes` 를 `position_key(tk, country)` 키로 합산(compute 키 일관, D1).
- `usdkrw = await usdkrw_if_foreign(trades, fx_state, http_client, providers=settings.fx_provider_list)`
  — 해외 보유 있을 때만 1회 조회(None 가능).
- `has_foreign = any(currency_for_country(trade_country(t)) != CURRENCY_KRW for t in trades)`.
- `invested_amount`: 혼재 스코프면 native 합산 금지(D5). country 분리 후 US 기여를 spot 환산 —
  단위 2단계와 일치하도록 보정(권장: `holding_invested_amount` 를 country 별 호출 후 US×usdkrw,
  usdkrw=None 이면 US 기여 제외; 상세는 구현 시 portfolio 헬퍼 형태 확인).
- `compute_asset_history(..., usdkrw=usdkrw)` 호출.
- 응답에 `usdkrw`, `has_foreign` 추가.
- 함정: backfill/get_closes/quotes 가 country 별이라 **다른 country 결과를 한 country_code 로 섞으면
  silent 결측**. country 별 호출/태깅 누락 주의. 종목뷰(단일 country)도 동일 환산 경로 통과.
- verify: `cd be && poetry run pytest tests/test_assets_router.py -q`
  (전체뷰 US+KR 혼재 응답 / usdkrw=None 응답 has_foreign=True+incomplete / usdkrw·has_foreign 필드 존재).
- 의존: 단계 1

### 3. [BE] `be/src/invest_note_api/schemas/asset_response.py` — 응답 스키마 필드 추가

- `AssetHistoryResponse` 에 `usdkrw: float | None = None`, `has_foreign: bool = False` 추가.
  docstring 에 의미 기재(usdkrw: KRW 환산 spot 환율, None=환율 미상; has_foreign: 스코프 해외 보유 존재).
- verify: `cd be && poetry run pytest tests/test_assets_router.py -q`(2단계와 동반, camelCase 직렬화
  `usdkrw`/`hasForeign` 확인).
- 의존: 단계 2(같이 진행 — 응답 dict 키와 정합)

### 4. [FE] `fe/src/lib/api-client.ts` — AssetHistoryResponse 타입 동기

- `AssetHistoryResponse` 에 `usdkrw: number | null`, `hasForeign: boolean` 추가.
- (params/assetsApi.history 는 country 여전히 전달 가능 — 종목뷰용. 무변경.)
- verify: `pnpm -C fe exec tsc --noEmit`
- 의존: 단계 3

### 5. [FE] `fe/src/components/assets/AssetHistoryView.tsx` — 환산 제거 + BE 값 직접 사용

- `useFxRate` import/호출 제거(이 뷰의 fx fetch 자체 삭제). `asset-history-convert` import/호출 제거.
- `series`/`dailySeries`/`items`/`investedAmount` 를 `data.series`/`data.items`(KRW 그대로) 에서 도출.
  `dailySeries` 는 items 역순 change 매핑만 유지(환산 제거).
- 환산 가드 재구성: `fxBlocked` → `data.hasForeign && data.usdkrw == null`(D4). US-only 종목뷰의
  0 일직선 방지 — fxBlocked 면 차트/표 대신 '환율 불러오면 표시' 안내(기존 UX 유지).
- USD 보조 병기(`displayNativeUsd`): 종목뷰(`isStockView && country==='US'`) + `data.usdkrw != null`
  일 때만 `display.value / data.usdkrw` 역산(권장안 — 권장6).
- 고지 문구: 환율 기준 표기를 `data.usdkrw`(useFxRate 아님) 로 전환, `formatFxRate(data.usdkrw)`.
  '현재 환율 기준(일자별 아님)' 고지 유지. fxBlocked/incomplete 문구 통합·정리.
- 함정: **한국식 색상(상승=빨강)** — 기존 `signColor`/`PNL_COLORS` 유지, western 색(상승=초록) 도입 금지.
  이중환산 금지(rate 곱이 한 군데라도 남으면 안 됨 — convert 호출 전부 제거 확인).
- verify: `pnpm -C fe exec tsc --noEmit` + 동작 시나리오(전체뷰 US 포함 KRW 곡선 표시 / US 종목뷰 환율
  미상 시 안내·0차트 아님 / 고지 문구 usdkrw 반영).
- 의존: 단계 4

### 6. [FE] `asset-history-convert.ts` + 테스트 삭제

- `fe/src/components/assets/asset-history-convert.ts` 삭제(값이 KRW 로 오면 4개 함수 전부 항등).
- `fe/src/components/assets/__tests__/asset-history-convert.test.ts` 삭제.
- 잔여 import 0 확인(5단계에서 제거됨).
- verify: `pnpm -C fe exec tsc --noEmit` + `pnpm -C fe test`
- 의존: 단계 5(뷰에서 참조 제거 후 삭제)

### 7. [QA] 정합성 검증

- BE 응답 shape(`series`/`items`/`incomplete`/`asOf`/`investedAmount`/`usdkrw`/`hasForeign`)
  ↔ FE `AssetHistoryResponse` 타입 일치.
- **finding A 정합(핵심):** 동일 usdkrw·동일 보유에서 대시보드 합계(`merge_quotes(usdkrw)`)
  ↔ 자산추이 오늘 점 총액(`series[-1].value`) 일치. 두 경로가 같은 spot·같은 포함범위인지.
- 통화 혼재 함정: US/KR 동일 ticker 문자열이 분리 합산되는지, usdkrw=None 시 US 제외+incomplete+
  has_foreign=True 인지.
- 색상 규칙(상승=빨강) 회귀 없음.
- verify: `cd be && poetry run pytest -q` + `pnpm -C fe exec tsc --noEmit` + `pnpm -C fe test`
- 의존: 단계 1~6

## 완료 조건

- [x] 1~6 각 단위 verify 통과
- [x] BE 전체 회귀 `cd be && poetry run pytest -q` (590 passed, 2 skipped)
- [x] FE `pnpm -C fe exec tsc --noEmit` + `pnpm -C fe test` (tsc OK, 182 passed)
- [x] 대시보드 합계 ↔ 자산추이 오늘 점 총액 정합(QA) — 포함범위·usdkrw 소스 일치 확인, 오늘 점 시세 소스 분기는 backlog 후속(QA I-2)
- [x] `docs/decisions.md` 갱신 — "자산추이 해외 보유 KRW 환산을 BE 로 이관, spot 일괄 적용
      (historical FX 보류)" 결정·트레이드오프 기록
- [x] spec → `docs/issue-history/2026-06-11-asset-history-overseas-krw.md` 이동 준비
