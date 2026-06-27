> 완료: 2026-06-27

# 토스 해외 거래 ISIN 코드 매칭 (OpenFIGI) 사양서

## 배경 / 목적

토스 해외(USD) 거래 import(2026-06-27 완료, `spec-history/2026-06-27-toss-overseas-import.md`)는 현재 **한글 종목명 매칭**으로 종목을 식별한다 — 원리적 오매칭 리스크 + 미해결 노이즈(샘플 648건 중 101 제외). 목적: 토스가 제공하는 **ISIN 코드로 정확 매칭**하도록 전환한다.

**소스 조사 결과(2026-06-27, OpenFIGI 공식 문서/약관 직접 확인):**
- OpenFIGI `/v3/mapping` 이 `idType: ID_ISIN` 입력 → `ticker` + `exchCode` 반환. 라이선스 clean(FIGI public domain, 상업 이용·재배포 허용, 출처표기 불요), CUSIP 미출력으로 라이선스 함정 구조적 회피.
- ⚠️ **출력에 ISIN 없음**(입력 전용) → 마스터 전체 ISIN 백필 불가. **import 시점에 미해결 ISIN만 ISIN→ticker 해소 + 캐시**가 정합 아키텍처(사용자 승인).
- Rate limit: 무키 25req/분·10건/요청, 무료키 25req/6초·100건/요청. `OPENFIGI_API_KEY` 옵션.

## 아키텍처 (확정)

import 시점: 토스 USD 행 ISIN → (1) `isin_ticker_map` 캐시 조회 → (2) 미스면 OpenFIGI 배치 해소 → (3) 캐시 저장 → (4) ticker+exchCode 로 US 마스터(`stocks`) 매칭. ISIN 해소 실패 시에만 기존 종목명 매칭 폴백(또는 unresolved). **ISIN 매칭이 종목명 매칭보다 우선.**

## 범위

포함: OpenFIGI 페처, ISIN→ticker 캐시 테이블, toss_pdf ISIN 전달, resolver ISIN 분기, env, 테스트.
제외: `stocks.isin` 컬럼(캐시 테이블로 분리), 토스 외 증권사, FE 변경(import 결과는 기존 US 거래 경로로 렌더 — 변경 없음).

## 작업 단위

### 1. [BE] alembic `0008_isin_ticker_map` — 캐시 테이블
- `isin_ticker_map`: `isin text PK`, `ticker text`, `exch_code text`, `country_code text`, `name text`, `resolved bool NOT NULL`(negative cache — 미해결 ISIN 재조회 방지), `source text DEFAULT 'openfigi'`, `resolved_at timestamptz DEFAULT now()`. head=0007 위 0008.
- `op.add_column`/`op.create_table` 표준 API. nullable/신규 테이블이라 superuser 불요. 운영 적용은 사용자 confirm.
- verify: `cd api && poetry run pytest -q -k import` (마이그레이션 로드)
- 의존: 없음

### 2. [BE] `external/openfigi.py` — ISIN→ticker 페처
- `async map_isins(isins: list[str], *, api_key: str | None) -> dict[str, OpenFigiResult | None]`. POST `https://api.openfigi.com/v3/mapping`, body `[{"idType":"ID_ISIN","idValue": isin}, ...]`. 배치 ≤10(무키)/100(키), rate-limit 페이싱(무키 25/분, 키 25/6s), 429 백오프.
- 결과에서 `ticker`·`exchCode`·`name`·`securityType` 추출. 다건 매칭 시 우선순위(미국 거래소 우선, securityType=Common Stock/ETP). 미해결 ISIN → None.
- `OPENFIGI_API_KEY` 미설정이어도 동작(무키 경로). 네트워크 실패 graceful(예외 삼키고 미해결 처리, import 전체 실패 금지).
- verify: `cd api && poetry run pytest tests/test_openfigi.py -q` (httpx mock)
- 의존: 없음

### 3. [BE] `broker_import/toss_pdf.py` — ISIN 전달
- `ParsedTrade`(base.py)에 `isin: str | None = None` 추가(**ticker_hint 와 분리** — ticker_hint 는 "이미 ticker"(KR 6자리), isin 은 "조회 필요"라 의미 충돌 방지).
- USD 행 파싱에서 버리던 ISIN 복원: `_parse_usd_name`/`_parse_usd_line`(현 `ticker_hint=None`)이 `isin=<ISIN>` 전달. ticker_hint 는 계속 None.
- verify: `cd api && poetry run pytest tests/test_broker_parsers.py -q` (무회귀 + isin 추출)
- 의존: 없음

### 4. [BE] `broker_import/ticker_resolver.py` + `db_ops` — ISIN 우선 해소
- `resolve_tickers` 가 isin 있는 항목은: 캐시(`isin_ticker_map`) 조회 → 미스 ISIN 모아 OpenFIGI 배치 → 캐시 upsert(해소/미해결 모두) → ticker 로 `stocks`(country=exchCode 매핑, 기본 US) 조회해 code/exchange 확정. ISIN 미해결 시 종목명 매칭 폴백.
- exchCode→country/exchange 매핑(예: UN/UW/UQ=US NYSE/Nasdaq). 매칭 키는 (country, ticker).
- 호출부 `routers/trades.py:693~` 에서 isin 정보 전달(현재 name→country 전달 구조에 isin 추가). conn 으로 캐시 R/W.
- verify: `cd api && poetry run pytest tests/test_ticker_resolver.py tests/ -q -k "import or trade or resolver"`
- 의존: 1, 2, 3

### 5. [BE] `config.py` — env
- `OPENFIGI_API_KEY: str | None = None`(옵션). `.env.example` 에 주석 추가. 미설정 시 무키 경로.
- verify: 로드 확인
- 의존: 2

### 6. [QA] 실 OpenFIGI 커버리지 + 정합 검증
- **실 OpenFIGI 호출**(무키)로 토스 10개 ISIN 해소율 실측 — 특히 `KYG3731B1086`(케이맨 설립·미국 상장 게임하우스), `US69608A1088`(팔란티어) 등. 해소된 ticker 가 US 마스터에 존재·정확한지(PLTR/TSLA 등). 종목명 매칭 대비 오매칭 제거 확인.
- 캐시 hit/miss 동작(2회차 OpenFIGI 미호출), negative cache(미해결 재조회 방지), ISIN 미해결 시 종목명 폴백, 기존 KRW/종목명 매칭 무회귀.
- preview→commit 시 USD 거래가 ISIN-해소 ticker 로 staged·INSERT(실 DB INSERT→read-back→롤백, 기존 QA 패턴).
- verify: `cd api && poetry run pytest -q` 전체 + 실 OpenFIGI 스팟체크 스크립트
- 의존: 4, 5

## 완료 조건
- [x] 토스 ISIN OpenFIGI 해소·정확 ticker 매칭 실측(케이맨 KYG3731B1086→GMHS 포함, 11/11)
- [x] ISIN 우선·종목명 폴백·캐시(positive/negative) 동작
- [x] 기존 토스 import(종목명 경로)·KRW 무회귀(US 누출 0)
- [x] OPENFIGI_API_KEY 미설정 무키 경로 동작
- [x] 전체 pytest green (896 passed / 3 skipped)
- [x] 실측 성과: 종목명 매칭 미해결 101 → ISIN 경로로 0 (GOOGL Class-A·GMHS·BROS 정밀 해소)
- [ ] (운영) 0008_isin_ticker_map 마이그레이션 운영 DB 적용 — 사용자 confirm 후
