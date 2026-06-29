# Spec: 해외 종목 한글명 적재(name_ko) + 거래 표시명 한글 우선

> 완료: 2026-06-28

## 배경 / 문제

해외(US) 주식의 종목명이 등록 경로에 따라 다르게 표시된다. 개별 등록(수동)은 `stocks.asset_name`(US=영문, 예 "Apple Inc.")을, 토스 일괄등록은 PDF 파싱 한글명(예 "애플")을 각각 `trades.asset_name`에 박제한다. `trades.asset_name`은 저장 시점 denormalize 박제 후 표시 시 마스터와 join하지 않으므로, 경로별 박제 문자열이 그대로 화면에 노출된다. US 한글명은 마스터의 canonical 컬럼이 아니라 검색 전용·희소한 `stock_aliases(source='naver')`에만 존재한다.

## 목표

- `stocks`에 `name_ko` 컬럼이 생기고, Naver 백필(`backfill_us_aliases`)이 US 한글명을 `name_ko`에도 적재한다.
- 거래 목록/상세 표시명이 `COALESCE(name_ko, asset_name)`로 한글 우선 표시된다(한글 없으면 영문 fallback).
- 저장값·계산/그룹핑 키(`asset_name`)는 불변이며, 기존 FE 계산 소비처에 영향이 없다.

## 설계

### 접근 방식

- **표시는 별도 nullable 필드(옵션 b)**: 응답에서 `asset_name`을 덮어쓰지 않고 `name_ko` 필드를 추가. `asset_name`은 FE에서 그룹핑/매칭 키로 광범위 사용(`lib/holdings.ts:41`, `lib/analysis/realized-pnl.ts:34`, `lib/analysis/concentration.ts:53`)이라 덮으면 계산 키 오염.
- **표시 해소는 읽기 응답에서만**: 저장값/그룹키(`trade_identifier`=`ticker_symbol or asset_name`, `trade_types.py:60`) 원본 불변. calc 경로(`SELECT *`)는 name_ko 키 부재 → 기본 None → 무영향.
- **JOIN 키**: trades는 stocks를 FK 안 함(020 의도)이나 `(country_code, ticker)`로 논리 LEFT JOIN. country는 기존 필터 규약 `COALESCE(NULLIF(t.country_code,''),'KR')`(`trades_repo.py:117`) 사용.
- **적재 소스는 Naver 백필만**. 토스 import 시점 수확·import 영문 저장 통일·검색 name_ko 매칭은 범위 밖(후속).

### 주요 변경 파일

- `api/alembic/versions/0011_stocks_name_ko.py` (신규) — `stocks.name_ko` Text nullable add/drop + **기존 US 한글명 일회성 backfill**(stock_aliases source='naver' → stocks.name_ko, min(alias)로 결정적). down_revision=`0010_import_staging`.
- `api/src/invest_note_api/services/stock_seed.py` — `set_name_ko(conn, names, *, country_code)` executemany 헬퍼 추가(upsert_aliases와 co-locate).
- `api/src/invest_note_api/services/stock_seed.py:697-699` — `upsert_aliases` 직후 `set_name_ko(conn, names, country_code=COUNTRY_US)` 호출(기존 alias 적재 유지).
- `api/src/invest_note_api/domain/trade_types.py:119` — `Trade.name_ko: str | None = None` (TradeWithAccount 상속).
- `api/src/invest_note_api/db_ops/trades_repo.py:121-133, 186-201` — 두 read SELECT에 `LEFT JOIN stocks ... ON (country_code, ticker)` + `s.name_ko AS name_ko`. calc 경로 `SELECT *`는 변경 금지.
- `app/src/types/database.ts:33` — `Trade.name_ko?: string | null`.
- `app/src/components/records/TradeHeaderCard.tsx:23` — `Pick<Trade, ...>`에 `"name_ko"` 추가.
- `app/src/lib`(또는 records 유틸) — `tradeDisplayName(trade) => trade.name_ko ?? trade.asset_name` 헬퍼.
- `app/src/components/records/{TradeCard,TradeHeaderCard,TradeList,TradeDetail}.tsx` — 표시 지점만 헬퍼로 교체.

## 구현 체크리스트

- [x] 마이그레이션 `0011_stocks_name_ko.py` 작성(컬럼 + 기존 US 한글명 일회성 backfill) + 로컬 downgrade/upgrade 검증 (운영 적용은 사용자 confirm 후)
- [x] `set_name_ko` 헬퍼 추가 (stock_seed.py — upsert_aliases와 co-locate)
- [x] `backfill_us_aliases`에서 `set_name_ko` 호출 (alias 적재 유지)
- [x] `Trade.name_ko` 도메인 필드 추가
- [x] `trades_repo` 두 read SELECT에 stocks LEFT JOIN + name_ko (calc 경로 불변)
- [x] BE 테스트: 전체 929 passed (name_ko 노출·fallback·JOIN 검증 + 백필 name_ko 적재 신규)
- [x] FE `Trade` 타입 + `TradeHeaderCard` Pick에 name_ko 추가
- [x] `tradeDisplayName` 헬퍼 + 4개 컴포넌트(TradeCard/TradeHeaderCard/TradeList/TradeDetail) 표시 지점 교체
- [x] 타입 체크 통과 (`pnpm -C app exec tsc --noEmit`) + FE 전체 270 passed
- [x] 통합 확인(로컬 DB): 마이그레이션 후 US name_ko 495개 채워짐, AAPL='애플', KR=0. JOIN으로 거래 표시 한글화 + name_ko NULL은 영문 fallback. (운영은 마이그레이션 적용 후 동일 동작)

## 보유종목/포트폴리오 뷰 확장 (완료)

`/portfolio/summary`는 이미 `list_trades_with_account`(위에서 JOIN 추가됨)를 호출해 **name_ko를 이미 받고** 있었고, 집계(`domain/portfolio.py`)에서 버려질 뿐이었음 → SQL 변경 없이 pass-through 배선만 추가.

- `domain/portfolio.py` — `Lot.name_ko`(필수, `first.name_ko`로 채움), `Position.name_ko`(기본 None), `_lot_to_positions` pos_map seed + Position 생성에 carry-through. `merge_quotes`는 `dataclasses.replace`라 자동 보존.
- `schemas/portfolio_response.py` — `PositionResponse.name_ko`(CamelModel → `nameKo` 직렬화). withQuotes 무영향(non-quote 경로에서 set).
- `app/src/lib/portfolio.ts` — `Position.nameKo?`(optional → 버전 스큐 안전, 정규화 불필요).
- `app/src/components/home/HoldingCard.tsx` — `displayName = nameKo ?? assetName`로 헤더 렌더 + aria-label.
- 테스트: `test_portfolio_logic`에 name_ko 전파/None 2건, `HoldingCard.test.tsx` 신규(한글/fallback 2건). BE 931 / FE 272 통과.

## 후속 / 범위 밖 (사용자 인지용)

- **신규 종목 tail**: `set_name_ko`가 `backfill_us_aliases`(naver_checked_at IS NULL 신규 종목)에서 호출되므로, 앞으로 처음 조회되는 US 종목은 자동 적재. 기존 532 checked 종목은 마이그레이션 일회성 복사로 해소.
- **분석 탭 집중도(범위 밖)**: `lib/analysis/concentration.ts`는 `list_trades`(JOIN 없는 SELECT *) 경로라 `Position.name_ko`가 항상 None → 집중도 라벨은 영문 유지. 같은 US 종목이 홈(한글)/분석(영문)으로 갈림. 해소하려면 list_trades SQL을 `t.* + name_ko JOIN`으로 재작성(calc-path·별도 탭이라 이번 범위 밖, `Position.name_ko` 주석으로 트랩 명시).
- **표시명 라벨 잔여**: 자산배분 도넛은 한글화 완료(`portfolio.ts` allocation `nameKo || assetName`). `missing_quote_tickers`는 여전히 asset_name(키 아닌 임시 라벨, 선택적).

## 우려사항 / 리스크

- **name_ko NULL / ticker NULL** → asset_name fallback(퇴행 없음).
- **기존 토스 거래**(asset_name 이미 한글) → name_ko 없으면 stored 한글 fallback(불변). 단 해당 US ticker에 name_ko가 있으면 **표시는 마스터 한글명 우선**(브로커 파싱명과 다른 한글 변형일 수 있음). 크래시·영문퇴행은 아니나 "완전 무변경"은 아님 — 마스터명을 canonical로 보여주는 의도된 동작.
- **KR 종목** → name_ko 비움, asset_name(이미 한글) fallback으로 동일 표시.
- **커버리지 한계** → name_ko는 Naver 백필 대상(인기주+SP500+거래이력)에 한정 → 롱테일 US는 영문 표시(구조적 상한).
- **저장값 불변식** → 표시 해소는 읽기 응답 2곳 + FE 헬퍼에서만. 저장/그룹키 asset_name 원본 불변.
- **ticker 대소문자 정합** → stocks/trades US ticker 대문자 가정. 통합 테스트로 확인.
