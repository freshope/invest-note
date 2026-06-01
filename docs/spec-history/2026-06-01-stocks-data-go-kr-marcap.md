> 완료: 2026-06-01

# Spec: stocks 데이터 적재 data.go.kr 단일화 + 시가총액 + 웹 라우터 실행

## 배경 / 문제

현재 종목 마스터 적재(`be/scripts/seed_stocks.py`)는 data.go.kr(KRX상장종목정보, authority) + FDR(FinanceDataReader, fallback) 2소스 구성이며, CLI로만 실행되고 스케줄이 미설정 상태다(backlog 이월). FDR을 폐기하고 data.go.kr 공식 OpenAPI로 단일화하며, 시가총액·시총순위를 보강하고, 적재를 웹 라우터로 트리거(+스케줄)할 수 있게 한다. **데이터 적재·스케줄에 집중하고 UI/검색 응답 shape은 건드리지 않는다**(시총순위 아이콘 노출은 후속 FE 작업).

**국민연금 보유 적재는 조사 후 보류 → backlog 이관**(odcloud 자동 fetch가 연도별 uddi 상이로 자동화 부적합 + 연 1회 데이터. 조사 결과는 `docs/backlog.md` "종목 메타데이터" 참고).

확정 결정: ① 시가총액+순위 저장, ② 라우터 인증은 env `ADMIN_TOKEN` 헤더, ③ 백그라운드 실행 후 즉시 202.

## 목표

- FDR이 코드·의존성에서 완전히 제거된다(import 0, `pyproject.toml` seed 그룹 정리).
- data.go.kr **KRX상장종목정보 + 증권상품시세(ETF/ETN) + 주식시세(시총)** 3개 서비스로 종목 coverage·시가총액이 적재된다.
- `stocks.marcap`(bigint), `stocks.marcap_rank`(int)가 매 적재마다 갱신된다(주식 KOSPI+KOSDAQ 대상 순위, ETF/ETN은 null).
- `POST /admin/seed/stocks`가 `ADMIN_TOKEN` 헤더 검증 후 백그라운드 적재를 시작하고 즉시 202를 반환한다.
- 외부 cron/Coolify scheduled task 일배치 실행 명령이 문서화된다.
- 기존 종목 검색(`/stocks/search`) 응답 shape·동작이 변하지 않는다.

## 설계

### 데이터 소스와 상호보완 원칙

기존 fingerprint/authority/preserve 프레임워크를 확장한다. 각 소스는 **서로 다른 필드를 채워** 상호보완한다:

| 소스 | data.go.kr | 채우는 것 | 권한 |
|------|-----------|----------|------|
| KRX상장종목정보 `getItemInfo` (15094775, 기존) | 주식 종목코드·종목명·market | 주식 canonical name authority |
| 증권상품시세 `getETFPriceInfo`/`getETNPriceInfo` (15094806, 신규) | ETF/ETN coverage·name·시총 | ETF/ETN coverage + marcap |
| 주식시세 `getStockPriceInfo` (15094808, 신규) | 주식 시가총액 | marcap enrichment (이름 미변경) |
| Naver(기존) | 이름 변형 별칭·market 교차검증 | enrichment |

> 스파이크: KRX상장종목정보 `getItemInfo`가 ETF/ETN을 이미 포함하는지 실측 확인. 포함하면 증권상품시세는 marcap 전용, 미포함이면 ETF/ETN coverage까지 담당.

### 스키마 (신규 마이그레이션)

- `024_stocks_marcap.sql` — `alter table stocks add column marcap bigint, add column marcap_rank integer, add column marcap_as_of date;` (삼성전자 ≈ 4×10¹⁴ → bigint 필수)

### seed 리팩토링 (최소 이동)

`seed_stocks.py`는 최근 안정화(36a3b27, 55bb63c)됨 → **검증된 fetch/upsert/fingerprint 로직은 byte-for-byte 보존**, 위치만 이동.

- 모듈 본체를 `be/src/invest_note_api/services/stock_seed.py`로 이동(import 가능). `scripts/seed_stocks.py`는 thin shim(`from invest_note_api.services.stock_seed import main; main()`).
- **FDR 제거**: `fetch_finance_data_reader`, `_FDR_MARKET_MAP`, `_build_pipeline` `_fdr`, `pyproject.toml` seed 그룹 finance-datareader 삭제.
- 신규 fetcher: `fetch_securities_products()`(ETF/ETN), `fetch_stock_prices()`(marcap). 둘 다 **basDt(직전 영업일) 날짜키** — FSC T+1(~13:00 KST) 발행이라 당일 조회는 빈 응답. 직전 영업일 + 휴장 fallback. basDt(YYYYMMDD str)는 `_basdt_to_date`로 date 변환(marcap_as_of date 컬럼).
- marcap 적재는 coverage fingerprint-skip을 **우회하는 always-run 단계**(시총 매일 변동). 적재 후 window function으로 순위 재계산:
  ```sql
  update stocks s set marcap_rank = r.rn
  from (select ticker, row_number() over (order by marcap desc nulls last) rn
        from stocks where country_code='KR' and is_active and market in ('KOSPI','KOSDAQ') and marcap is not null) r
  where s.ticker=r.ticker and s.country_code=$1;
  ```

### 라우터 + 인증

- `config.py`: `admin_token: str = ""` 추가. `.env.example`에 `ADMIN_TOKEN=` + 주석.
- `require_admin_token`(헤더 `X-Admin-Token`, settings.admin_token과 constant-time 비교, 미설정/불일치 시 403). 신규 패턴.
- `routers/admin.py`: `POST /admin/seed/stocks` → guard → `BackgroundTasks.add_task(run_seed)` → `202 {"status":"started"}`. `main.py`에 등록(legacy `/api/*` alias 제외).
- **연결 관리(핵심)**: `run_seed`는 `Depends(get_pool)`를 쓰지 **않고** CLI처럼 자체 `asyncpg.connect()`. seed가 session advisory lock을 수 분 보유 → 풀 차용 시 요청 풀 고갈 + lock leak 방지.

### 스케줄

외부 cron / Coolify scheduled task가 매일 ~14:00 KST(FSC T+1 이후) 호출:
```
curl -fsS -X POST -H "X-Admin-Token: $ADMIN_TOKEN" https://<api>/admin/seed/stocks
```
중복 실행=advisory lock, 무변경 소스=fingerprint-skip 가드.

## 구현 체크리스트 ✅ 완료

- [x] `024_stocks_marcap.sql` 마이그레이션 (marcap bigint, marcap_rank, marcap_as_of)
- [x] seed 모듈을 `services/stock_seed.py`로 이동 + `scripts/seed_stocks.py` thin shim (로직 보존)
- [x] FDR 제거 (fetcher·pipeline·pyproject seed 의존성)
- [x] `fetch_securities_products()` (증권상품시세 ETF/ETN, basDt 직전영업일, coverage 파이프라인 + marcap) + 활용신청 스파이크
- [x] `fetch_stock_prices()` + marcap always-run 단계 + marcap_rank window 갱신 (+ `_basdt_to_date` date 변환)
- [x] `config.admin_token` + `.env.example` + `require_admin_token`
- [x] `routers/admin.py` `POST /admin/seed/stocks` (자체 connect, BackgroundTasks, 202) + main.py 등록
- [x] 신규 fetcher 단위테스트 (httpx mock), basDt fallback·`_basdt_to_date` 테스트
- [x] 스케줄 cron 명령 docs, FDR 제거 decisions.md 기록
- [x] `cd be && poetry run pytest -q` 통과 (341 passed, FE 무변경 → tsc 불필요)
- [x] 3개 mutation SQL(`_UPDATE_MARCAP_SQL`/`_RECALC_RANK_SQL` 등) throwaway Postgres 실행 검증 — marcap_as_of date 버그 발견·수정

## 보류 → backlog 이관

- 국민연금 보유 적재(`nps_holding` 컬럼 + `/admin/seed/nps` 업로드) — `docs/backlog.md` "종목 메타데이터" 참고.
- 종목명 옆 마켓/시총순위/국민연금 아이콘 표시(FE) — 동일.

## 우려사항 / 리스크

- **data.go.kr 키 hard 의존성 격상**: FDR 제거 후 키 없음/미승인 = coverage 0. 증권상품시세·주식시세는 **서비스별 활용신청 별도 필요** — 누락 시 `SERVICE_KEY_IS_NOT_REGISTERED`.
- **basDt 날짜 로직**: 휴장/T+1 지연 → 직전 영업일 fallback 필수.
- **신규 fetcher 응답 키 스파이크 미해소**: `srtnCd`/`itmsNm`/`mrktTotAmt` 추정 — 실서버 1회 확인 필요(코드에 ⚠️ 주석).
- **seed 모듈 이동 회귀 위험**: 로직 변경 최소화, 위치 이동 위주.

## 검증

- FDR 완전 제거: `grep -ri financedatareader be/src be/scripts be/pyproject.toml` 0건.
- `cd be && poetry run pytest -q` → 341 passed.
- mutation SQL: throwaway Postgres에서 marcap·marcap_rank(주식만/ETF·ETN null) 실행 검증 완료.
- `POST /admin/seed/stocks`: 누락/오류 토큰 → 403, 정상 → 202 즉시 반환.
- 배포 후 실 키로 seed 1회 실행 → ETF/ETN coverage·marcap 채워짐 확인(실 API 필드 스파이크 해소).
- `/stocks/search` 응답 shape·동작 불변(회귀).
