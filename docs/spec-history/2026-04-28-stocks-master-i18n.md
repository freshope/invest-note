# Spec: stocks 마스터 테이블 국제화 + KIND 데이터 소스 전환

> 완료: 2026-04-28

## 배경 / 문제

현재 `kr_stocks` 테이블은 KRX 정보데이터시스템(`data.krx.co.kr`)의 OTP 엔드포인트로 시드되는데, 정책 변경으로 OTP 발급이 막혀 시드 갱신이 불가능해졌다 (HTTP 200 + `LOGOUT` 응답 확인). 동시에 `docs/decisions.md:43-48`의 v2 계획대로 해외 주식 지원을 향한 사전 작업으로, 한국 전용 `kr_stocks`를 다국적 마스터 `stocks` 테이블로 일반화한다.

데이터 소스는 KRX의 다른 공식 사이트인 KIND(`kind.krx.co.kr/corpgeneral/corpList.do`)로 교체한다. 검증 결과 인증 불필요·GET 한 번이며, 어제 상장된 KONEX 종목까지 잡히는 T+1 이내 신선도를 가진다.

## 목표

- `kr_stocks` 테이블이 `stocks`로 rename되고, `country_code`/`currency`/`exchange` + KIND 메타데이터 컬럼을 가진 `(country_code, ticker)` 복합 PK 스키마로 동작한다
- `seed_stocks.py` (rename됨)가 KIND 엔드포인트로 KOSPI/KOSDAQ/KONEX 전 종목을 idempotent하게 UPSERT한다
- 기존 `routers/trades.py`의 import preview가 새 스키마로도 ticker 해석에 성공한다 (회귀 없음)
- 프론트의 `kr_stocks` 노출 문자열이 새 표현으로 갱신된다

## 설계

### 접근 방식

1. **마이그레이션 015** 한 개로 rename + 컬럼 추가 + PK 변경을 atomically 처리한다. 기존 데이터는 `country_code='KR'`로 backfill되며 손실 없음.
2. **PK는 `(country_code, ticker)` 복합 PK**. 기존 ticker 단일 PK를 drop하고 신규 PK 추가. `market` CHECK 제약은 해외 시장 추후 확장을 위해 제거 (값 자유 — 시드 단계에서 정규화 책임).
3. **KIND 파서는 stdlib만** 사용 (`urllib` + `re` + EUC-KR 디코딩). BeautifulSoup 의존성 추가 안 함. KIND 시장구분 값(`유가/코스닥/코넥스`)을 `KOSPI/KOSDAQ/KONEX`로 매핑.
4. **레포 계층 시그니처 확장**: `lookup_by_names(asset_names, country_code='KR')` 형태로 country를 받아 join. 호출부(`ticker_resolver.py` → `routers/trades.py`)는 trades의 `country_code`를 그대로 전달. 한국 외 country는 일단 빈 결과로 폴백 (MVP 정책 유지).

### 새 스키마 (마이그레이션 015 결과)

```sql
create table public.stocks (
    country_code  text        not null default 'KR',
    ticker        text        not null,
    asset_name    text        not null,
    market        text        not null,         -- CHECK 제거 (KOSPI/KOSDAQ/KONEX/NYSE/NASDAQ 등 자유)
    currency      text        not null default 'KRW',
    exchange      text,                          -- 거래소 코드 (예: 'KRX', 'NYSE'). 한국은 NULL 또는 'KRX'
    sector        text,                          -- KIND 업종
    main_products text,                          -- KIND 주요제품
    listed_at     date,                          -- KIND 상장일
    fiscal_month  text,                          -- KIND 결산월 (예: '12월')
    ceo_name      text,                          -- KIND 대표자명
    homepage      text,                          -- KIND 홈페이지
    region        text,                          -- KIND 지역
    updated_at    timestamptz not null default now(),
    primary key (country_code, ticker)
);
create index stocks_asset_name_idx on public.stocks(asset_name);
```

### 주요 변경 파일

- `supabase/migrations/015_rename_kr_stocks_to_stocks.sql` *(신규)* — rename + 컬럼 추가 + PK 변경 + 인덱스 rename. 기존 row는 `country_code='KR'` 자동 backfill
- `api/scripts/seed_stocks.py` *(rename + 재작성)* — `seed_kr_stocks.py`를 rename. KIND `corpList.do` 호출, EUC-KR HTML 테이블 파싱, market 값 매핑, 새 컬럼 채워서 UPSERT
- `api/src/invest_note_api/db_ops/stocks_repo.py` *(rename)* — `kr_stocks_repo.py`를 rename. `lookup_by_names`에 `country_code='KR'` 파라미터 추가, SQL의 `kr_stocks` → `stocks` + `where country_code = $2`
- `api/src/invest_note_api/broker_import/ticker_resolver.py` — import 경로 갱신, `lookup_by_names` 호출 시 `country_code` 전달
- `api/src/invest_note_api/routers/trades.py:386,421` — resolver 호출부에서 trade의 `country_code`를 전달 (기존 변수 그대로 사용)
- `app/src/components/records/ImportTradesPanel/PreviewStep.tsx:79` — "kr_stocks에 없음" 문구를 "주식 마스터에 없음"으로 갱신

## 구현 체크리스트

- [x] `supabase/migrations/015_rename_kr_stocks_to_stocks.sql` 작성 (rename + 컬럼 추가 + PK 교체)
- [x] 로컬 Supabase에 마이그레이션 적용 후 데이터 보존 확인 (`select count(*) from stocks where country_code='KR'`)
- [x] `api/src/invest_note_api/db_ops/kr_stocks_repo.py` → `stocks_repo.py` rename, `country_code` 파라미터 추가
- [x] `api/src/invest_note_api/broker_import/ticker_resolver.py` import 경로 갱신, country 전달
- [x] `api/src/invest_note_api/routers/trades.py:386,421` resolver 호출부 시그니처 갱신
- [x] `api/scripts/seed_kr_stocks.py` → `seed_stocks.py` rename, KIND 엔드포인트로 재작성 (`_fetch_kind`, `_parse_kind_html`, market 매핑, KIND 메타데이터 칼럼 채우기)
- [x] `app/src/components/records/ImportTradesPanel/PreviewStep.tsx:79` 문구 갱신
- [x] `cd api && poetry run python scripts/seed_stocks.py` 실행 — 3개 시장 모두 UPSERT 성공 확인
- [x] `cd api && poetry run pytest -q` — 기존 테스트 회귀 없음
- [x] `pnpm -C app exec tsc --noEmit` — 타입 체크 통과
- [x] import preview 수동 테스트 — 한국 종목이 정상적으로 ticker 해석되는지 확인

## 검증 (E2E)

1. **마이그레이션 적용 후 데이터 보존**:
   ```sql
   select country_code, count(*) from public.stocks group by 1;  -- KR | (이전 kr_stocks row 수)
   ```
2. **KIND 시드 idempotent**:
   ```bash
   cd api && poetry run python scripts/seed_stocks.py
   # 두 번 실행해도 row 수 동일, updated_at만 갱신
   ```
3. **신규 컬럼 채워짐**:
   ```sql
   select sector, listed_at, ceo_name from public.stocks where ticker='005930';  -- 삼성전자
   ```
4. **routers/trades.py 회귀**: 기존 import preview 흐름이 한국 종목에 대해 ticker 해석 성공
5. **타입 체크 + 백엔드 테스트** 모두 통과

## 우려사항 / 리스크

- **PK 변경 위험**: 기존 row의 `country_code` 기본값 `'KR'`이 정확히 들어가야 한다. 마이그레이션 내에서 `alter column ... set default` 후 `update where country_code is null`로 명시적 backfill 보장.
- **KIND 종목코드 형식**: 일부 신규 상장(스팩 등)은 `0131D0` 같은 영숫자 혼합. 새로 시드되면서 영숫자 ticker가 추가됨. `trades.ticker_symbol` 컬럼은 text라 호환되지만, 기존 사용자 데이터에 영향 없음을 확인 필요.
- **CHECK 제약 제거**: `market` CHECK를 제거하면 잘못된 값이 들어갈 위험. 시드 스크립트에서 정규화 + 단위 테스트로 보완 (별도 spec으로 미룸).
- **lookup_by_names 시그니처 변경**: `country_code` 기본값을 `'KR'`로 두어 기존 호출부는 무수정 작동 (그러나 명시적으로 전달하도록 본 spec에서 정리).
