> 완료: 2026-06-27

# 토스증권 해외(USD) 거래 임포트 지원 사양서

## 배경 / 목적

`broker_import/toss_pdf.py` 는 "달러 거래내역" 섹션 행을 `_DATA_LINE_RE`(`\(A?\d{6}\)`, 6자리 KRX 코드 요구)로만 매칭한다. USD 행은 종목코드가 ISIN(`US69608A1088`)이라 정규식에 걸리지 않아 `usd_skip_count` 조차 증가하지 않는다. 결과적으로 해외 위주 명세서 업로드 시 **"신규 0·중복 0·건너뜀 0·에러 0"** 의 침묵 누락이 발생한다.

목적: 토스 달러 섹션을 파싱하여 **USD 네이티브 거래**(`country_code="US"`, `currency="USD"`)로 임포트한다. 원화 추출/기존 테스트 29개 무회귀 유지.

연결: `docs/backlog.md` 일괄등록 파서 확장 라인, 메모리 `project_broker_import_parsers`(해외 Phase2), `feedback_broker_parser_fixture_tests`(실파일 회귀 필수).

## 통화 의미론 (제품 결정 — 확정)

- 토스 달러 섹션의 **모든 금액 컬럼은 원화 환산값**이다. 환율(원/달러)로 나눠 USD 네이티브로 복원한다.
- 복원 대상은 **price·commission·tax 세 필드 전부**. `domain/trade_types.py:88` `krw_normalized_trade` 가 price·commission·tax 를 모두 `× exchange_rate` 로 KRW 환원하므로, 셋 중 하나라도 KRW 로 남겨두면 원가가 ~1370배로 부풀고 `build_merge_patch` 비교가 깨진다.
  - `price_usd = 원화단가 / 환율`, `commission_usd = 원화수수료 / 환율`, `tax_usd = 원화제세금 / 환율`
  - 예: 팔란티어 원화단가 40,641 ÷ 1,370.30 → price ≈ 29.66 USD, qty = 0.030345
- `exchange_rate` = 행의 환율(원/달러, 예 1370.30). `schemas/trade.py:exchange_rate_error` 규칙상 US 거래는 `exchange_rate != 1.0` 필수(1.0/누락이면 native 를 KRW 로 오인 집계).
- 라운드트립 불변식: `price_usd × exchange_rate ≈ 원화단가` (검증 기준).

## 범위 (Scope)

포함:
- 토스 PDF 달러 섹션 파싱 → USD 네이티브 `ParsedTrade`
- `ParsedTrade` 에 `country_code`, `exchange_rate` 필드 추가, 라우터가 행별로 staging
- 라우터의 `country_code=DEFAULT_COUNTRY` 하드코딩 제거 + line-913 방어 가드를 실제 USD 처리로 치환
- commit insert_row 가 `exchange_rate` 를 실어 INSERT
- preview 응답에 `foreign_count`(해외 staged 행 수) 추가, FE PreviewStep 의 "해외 미지원" 고지 조건부 치환
- 두 해외포함 샘플 회귀 테스트

제외:
- 토스 외 증권사(samsung/shinhan/mirae/kb)의 해외 임포트 — 국내전용 유지
- 신규 US 종목 자동 등록/마스터 적재 — 미해결 종목은 기존처럼 `unresolved_ticker_count` 로 노출
- ISIN → ticker 변환(외부 조회) — name 매칭 폴백만
- FE 거래/보유 카드의 USD 표시 신규 구현 — 수동 US 입력 경로가 이미 렌더하므로 QA 확인만

## 가정 (Assumptions)

- USD 섹션의 미해결 종목 다수 예상은 정상(ISIN 미사용 + stocks 마스터에 US 종목명 부재 가능). QA-A2 에서 `lookup_by_names` 가 US 종목을 실제로 반환하는지 기대치를 확정한다.
- 진짜 skip(환전·이체 등 비거래 행)이 USD 섹션에 섞여 있으면 `usd_skip_count` 로 남기되, 임포트된 거래는 더 이상 skip 이 아니다(아래 카운터 재정의).

## 작업 단위

### 1. [BE] `api/src/invest_note_api/broker_import/base.py` — ParsedTrade 필드 추가
- `ParsedTrade` 에 `country_code: str = "KR"`, `exchange_rate: float = 1.0` 추가. 기존 `currency` 필드는 유지하되, **다운스트림 권위는 `country_code`**(`currency_for_country`)임을 주석으로 명시(currency 는 표시/디버그용, drift 주의).
- verify: `cd api && poetry run pytest tests/test_broker_parsers.py -q` (무회귀)
- 의존: 없음

### 2. [BE] `api/src/invest_note_api/broker_import/toss_pdf.py` — USD 섹션 파싱
- USD 전용 컬럼맵: 헤더 `거래일자 거래구분 종목명(종목코드) 환율 거래수량 거래대금 정산금액 단가 수수료 제세금 변제/연체합 잔고 잔액` — KRW 에 있던 **거래세 컬럼이 없고 환율 컬럼이 값으로 채워진다**. KRW용 `_HEADER_EXCLUDED`(환율 제외)를 USD 에 재사용 금지 — USD 전용 컬럼맵/제외셋 분리.
- `_DATA_LINE_RE` 의 name 경계를 ISIN(영숫자 12자) 허용으로 확장. 단 **ISIN 은 ticker_hint 로 쓰지 않는다**(`mirae_pdf` 의 영숫자 A0080G0 선례 — 숫자코드만 hint). ISIN 행은 `ticker_hint=None` → name 매칭 폴백.
- **glued 토큰 디-글루 선행**: `1,370.300.004568`(환율+소수수량 공백 없이 붙음)을 컬럼맵 인덱싱 **전에** 환율 앵커(`\d{1,3}(,\d{3})*\.\d{2}`, 소수 2자리)로 분리. 디-글루를 인덱싱 뒤에 하면 환율 이후 모든 컬럼 인덱스가 밀린다.
- USD 행 → `country_code="US"`, `currency="USD"`, `exchange_rate=환율`, `price/commission/tax = 원화값/환율`.
- USD 섹션의 `usd_skip_count` 증가 로직 제거(거래로 전환). 비거래 행만 skip 유지.
- verify: `cd api && poetry run pytest tests/test_broker_parsers.py -q`
- 의존: 단계 1

### 3. [BE-test] `api/tests/test_broker_parsers.py` — USD 회귀 테스트
- 샘플(루트 `sample/`, macOS **NFD 파일명** 주의 — 직접 open 안 하면 조용히 0 매칭):
  - `sample/토스_거래내역서_20240811_20250810_1.pdf` (KRW 주식 0 + USD 구매 648)
  - `sample/거래내역서_토스_해외포함_20250613_20260612_1.pdf` (KRW 15 + USD 구매 2)
- 검증: USD 거래 건수 · `price_usd = 원화단가/환율` 라운드트립(`price×exchange_rate ≈ 원화단가`) · `commission_usd`/`tax_usd` 도 USD(라운드트립) · `currency=="USD"` · `country_code=="US"` · ISIN 이 ticker_hint 로 안 쓰임(`ticker_hint is None`) · 기존 KRW 29개 무회귀.
- verify: `cd api && poetry run pytest tests/test_broker_parsers.py -q`
- 의존: 단계 2

### 4. [BE] `api/src/invest_note_api/routers/trades.py` — 행별 country/exchange_rate staging
- preview 스테이징(L766~783): `"country_code": DEFAULT_COUNTRY` → `pt.country_code`. `exchange_rate` 키 추가(`pt.exchange_rate`). `exchange` 는 계속 `resolved["exchange"]`.
- commit(L908~917): non-KRW raise 가드를 **실제 처리로 치환** — US 행은 `exchange_rate` 를 insert_row 에 실어 INSERT. 단 방어 가드 유지: US 행인데 `exchange_rate==1.0`/누락이면 `exchange_rate_error` 와 동일 의미로 commit_error 처리(침묵 통과 금지).
- insert_row(L918~932)에 `"exchange_rate": row["exchange_rate"]` 추가. `db_ops/trades_repo.py` insert 는 이미 `exchange_rate` 컬럼 지원(L208/238) — 키만 전달하면 됨.
- `foreign_count` 집계(staged 중 `country_code != "KR"` 행 수) → preview 응답에 포함.
- verify: `cd api && poetry run pytest tests/ -q -k "import or trade"` + 동작 시나리오(샘플 preview→commit USD 거래 INSERT 확인)
- 의존: 단계 2

### 5. [BE] `api/src/invest_note_api/schemas/trade_import.py` + `domain/trade_import.py` — 응답 shape
- `ImportPreviewResponse` 에 `foreign_count: int = 0` 추가. `usd_skip_count` 의미 재정의(임포트된 USD 는 더 이상 skip 아님 — 진짜 비거래 skip 만) 주석 명시. `usd_skip_count` 필드 자체는 하위호환 유지.
- `domain/trade_import.ImportSummary` 의 `usd_skip_count` 주석 동기화(제거하지 않음 — 다른 경로 참조 확인 후 결정).
- verify: `cd api && poetry run pytest tests/ -q -k import`
- 의존: 단계 4

### 6. [FE] `app/src/lib/api-client.ts` — ImportPreviewResponse 타입 동기화
- `ImportPreviewResponse` 인터페이스에 `foreign_count: number;` 추가(BE shape 일치). `usd_skip_count` 주석 갱신.
- verify: `pnpm -C app exec tsc --noEmit`
- 의존: 단계 5

### 7. [FE] `app/src/components/records/ImportTradesPanel/PreviewStep.tsx` — 해외 고지 조건부화
- 현재 모든 브로커에 무조건 노출되는 "해외(미국 등) 거래는 아직 일괄 등록을 지원하지 않습니다…" 블록을 `foreign_count > 0` 일 때 **"해외 거래 N건 포함됨(USD)"** 안내로 치환. `foreign_count === 0` 이고 해외 미지원 브로커면 기존 고지 유지(제보 버튼 포함).
- 신규 shadcn 컴포넌트 도입 없음(기존 마크업 재사용) → base/ 래퍼 작업 불필요.
- verify: `pnpm -C app exec tsc --noEmit` + `pnpm -C app test src/components/records/__tests__/PreviewStep.test.tsx` + 동작 시나리오(USD 포함 preview 시 신규 안내 노출)
- 의존: 단계 6

### 8. [QA] BE 파서 shape — 단계 2·3 검증
- USD `ParsedTrade`: `country_code=="US"`·`currency=="USD"`·`exchange_rate>1`·price/commission/tax USD 라운드트립·ISIN 비-hint. 두 샘플 건수 일치. KRW 무회귀.
- 메모리 함정: `feedback_broker_parser_fixture_tests`(실파일), `project_broker_import_parsers`(ISIN/영숫자 hint 금지), NFD 파일명.
- verify: `cd api && poetry run pytest tests/test_broker_parsers.py -q`
- 의존: 단계 3

### 9. [QA] BE 라우터/응답 shape — 단계 4·5 검증
- preview staged 행: USD 행 `country_code="US"`+`exchange_rate` 실림. commit insert_row 에 `exchange_rate` 전달 → INSERT 후 `exchange_rate_error` 위반 없음(US rate≠1.0). `foreign_count` 정확. line-913 가드 침묵통과 없음.
- QA-A2: `lookup_by_names` 가 USD 섹션 종목을 반환하는지 / 대부분 unresolved 인지 실측 기대치 확정.
- verify: `cd api && poetry run pytest tests/ -q -k "import or trade"`
- 의존: 단계 5

### 10. [QA] BE↔FE 정합 + 통합 — 단계 7 검증
- `foreign_count`(BE int) ↔ FE `number` 타입 일치. PreviewStep 분기 동작. 임포트된 USD 거래가 기존 US-trade UI(거래 카드/보유)에서 정상 렌더(수동 US 입력과 동일 경로) — 신규 구현 아닌 **확인**.
- verify: `pnpm -C app exec tsc --noEmit` + `pnpm -C app test`
- 의존: 단계 7

### 11. [DOC] `docs/decisions.md` — 결정 로그
- USD 네이티브 복원(price/commission/tax 전부 ÷환율)·exchange_rate 출처(행 환율)·`usd_skip_count` 재정의·`foreign_count` 신설·ISIN 비-hint 결정 기록(트레이드오프 포함).
- verify: 문서 리뷰
- 의존: 단계 9

## 완료 조건
- [x] 단계 1~10 verify 통과 (BE pytest + FE tsc/test) — BE 880 passed, FE tsc+268 passed
- [x] 두 해외포함 샘플 USD 건수·USD 라운드트립·currency/country·ISIN 비-hint 검증
- [x] 기존 KRW 테스트 29개 무회귀
- [x] `docs/decisions.md` 갱신
- [x] spec → `docs/spec-history/2026-06-27-toss-overseas-import.md` 이동 준비
- [x] (추가) 🔴 차단결함 #12 — resolve_tickers country-scoped 매칭(US→KR ETF 오매칭) 수정·실측 검증
- [ ] (follow-up, backlog) US 내 종목명 매칭 잔존 리스크 → ISIN 코드 매칭 전환 (해외 종목 ISIN 적재)
