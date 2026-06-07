# Spec: KIS 트랙 1 — 기존 데이터 공급처 확대 (KIS Open API provider 추가)

## 배경 / 문제

현재 BE 외부 데이터는 Naver(시세·검색·교차검증·종가 gap)·data.go.kr(종목마스터·시총·종가)·Yahoo(시세 fallback)에 의존한다. Naver 는 비공식 API 라 차단/변경 리스크가 있고, data.go.kr 게이트웨이는 간헐 404(~50% 성공률)로 불안정하다. 2026-06-07 사전 조사로 KIS Open API(한국투자증권)가 공식 소스로서 시세·일별종가·종목마스터·교차검증을 모두 커버할 수 있음을 확인했다. 2026-06-07 도입된 공급자 env registry 패턴에 KIS 를 새 공급자로 추가한다.

- 사전 조사 근거: `docs/backlog.md` "v2 — KIS API 연동" 섹션 (KIS 트랙 1)
- BE 단독 작업, FE 변경 없음
- 사용자 확정 사항: 가능한 모든 공급처에 추가, 시세 화면 노출 포함, 서비스용 appkey 발급 완료

## 목표

- `QUOTE_PROVIDERS=kis,...` 설정 시 KIS 국내주식 현재가로 시세가 조회된다 (registry 등록만으로 env 전환·무배포 복귀 가능).
- `DAILY_PRICE_PROVIDER=kis` 또는 `DAILY_PRICE_GAP_PROVIDER=kis` 설정 시 KIS 기간별 시세로 일별 종가 backfill 이 동작한다.
- `STOCK_SEED_SOURCES` 에 `kis` 를 포함하면 KIS 종목마스터 파일로 종목 seed 가 동작한다 (data.go.kr 대체 공급선).
- 교차검증이 provider 토글 가능해지고 `kis` 구현이 추가된다 (Naver 고정 의존 해소 — 백로그 "공급자 env 토글 제외 잔존" 항목).
- 모든 신규 코드는 httpx.MockTransport 기반 pytest 로 커버되고, appkey 실호출 검증을 통과한다.

## 설계

### 접근 방식

- **기존 env registry 패턴 준수**: `provider_registry.resolve_chain` + 도메인별 registry dict 에 fetch 함수 등록. 신규 추상화 없음.
- **인증은 공용 모듈 1개**: `external/kis.py` 에 토큰 발급(`POST /oauth2/tokenP`, client_credentials)·in-process 캐시(`asyncio.Lock`, 만료 전 재사용)·공통 요청 헬퍼(`authorization`/`appkey`/`appsecret`/`tr_id` 헤더)를 둔다. 실전/모의 도메인과 TR ID prefix(T↔V) 분기는 `KIS_ENV`(real|mock) 로 처리.
  - 토큰 정책: 유효 ~24h, 6h 내 재요청 시 기존 토큰 반환, **발급 1분당 1회 제한(EGW00133)** → 캐시 + lock 으로 중복 발급 차단.
  - 멀티워커 시 워커별 발급 경합 리스크 있음 — 현재 단일 워커 배포 전제(Preview staging TTLCache 와 동일 전제). spec 범위 밖, 멀티워커 전환 시 재설계.
- **시세**: `external/quotes.py` 에 `_fetch_kis(client, code) -> QuoteResult | None` 추가 (국내주식 현재가 `inquire-price`, TR `FHKST01010100`). rate limit(실전 ~20req/s, 재검증 필요)은 기존 TTLCache 45s + single-flight 가 완충.
- **일별 종가**: `daily_price_seed.py` 의 `_PRIMARY_REGISTRY`/`_GAP_REGISTRY` 에 kis fetcher 추가 (기간별 시세 `inquire-daily-itemchartprice`, TR `FHKST03010100`, 호출당 최대 ~100건 → 구간 분할 페이징).
- **종목 마스터**: `stock_seed.py` registry 에 `kis` 소스 추가. KIS 종목마스터 파일(`kospi_code.mst`/`kosdaq_code.mst`, fixed-width zip 다운로드, EUC-KR 인코딩 주의 — 기존 REST JSON 과 다른 파싱). 반환 shape 은 기존 소스와 동일(`{ticker, asset_name, market}`).
  - 검색 확대는 별도 API 가 아니라 이 seed → `STOCK_SEARCH_PROVIDER=db` 경로로 흡수 (KIS 에 이름 검색 API 없음).
- **교차검증**: `crossvalidate_stocks_with_naver` 를 provider registry 구조로 일반화(`CROSSVALIDATE_PROVIDER` env, 기본 `naver` 유지, 함수명 `crossvalidate_stocks` 로 변경)하고 KIS 구현 추가. **구현 변경(2026-06-07):** 종목별 REST 조회 대신 종목마스터 파일 1회 다운로드 일괄 대조 — 수천 건 per-ticker 호출(rate limit 소모)이 사라짐.
- **시총/marcap 보류**: data.go.kr 은 bulk 응답인 반면 KIS 는 종목별 호출이라 전종목 시총 = 수천 호출. 이번 범위에서 제외, `update_marcap` 은 data.go.kr 유지.
- KIS API 의 정확한 URL/TR ID/응답 필드는 구현 시 공식 문서(apiportal.koreainvestment.com, github.com/koreainvestment/open-trading-api)에서 확정한다. 사전 조사 수치(rate limit 20/s, 토큰 정책 등)는 재검증 필요.

### 주요 변경 파일

- `be/src/invest_note_api/config.py` — `kis_app_key`/`kis_app_secret`/`kis_env` 설정 추가
- `be/src/invest_note_api/external/kis.py` — 신설: 토큰 캐시 + 공통 요청 헬퍼
- `be/src/invest_note_api/external/constants.py` — KIS 도메인/타임아웃 상수
- `be/src/invest_note_api/external/quotes.py` — `_fetch_kis` + `_QUOTE_REGISTRY` 등록
- `be/src/invest_note_api/services/daily_price_seed.py` — kis primary/gap fetcher 등록
- `be/src/invest_note_api/services/stock_seed.py` — kis 종목마스터 소스 + 교차검증 provider 토글
- `be/tests/test_kis.py` — 신설: 토큰 캐시/헬퍼 테스트
- `be/tests/test_quotes.py`, `be/tests/test_stock_seed.py`, `be/tests/test_daily_price_seed.py` — provider 케이스 추가

## 구현 체크리스트

- [x] 1. `config.py` — `kis_app_key`/`kis_app_secret`/`kis_env`(real|mock) 설정 + `kis_env` 정규화 + 테스트
- [x] 2. `external/kis.py` 신설 — 토큰 발급/캐시(asyncio.Lock) + 공통 요청 헬퍼(도메인 분기) + `tests/test_kis.py`
- [x] 3. `external/quotes.py` — `_fetch_kis` 구현 + `_QUOTE_REGISTRY` 등록 + `test_quotes.py` 케이스(성공/실패 fallback/등록 검증)
- [x] 4. `services/daily_price_seed.py` — `fetch_kis_daily_closes` 구현 + `_PRIMARY_REGISTRY`/`_GAP_REGISTRY` 등록 + 테스트
- [x] 5. `services/stock_seed.py` — `fetch_kis_master`(.mst zip 파싱) + seed registry 등록 + 테스트
- [x] 6. `services/stock_seed.py` — 교차검증 provider 토글(`CROSSVALIDATE_PROVIDER`, 기본 naver) + KIS 마스터 일괄 대조 구현 + 테스트
- [ ] 7. appkey 실호출 검증 — 시세/일별종가/마스터 파일 각 1회 점검 (검증 후 결과 기록)
- [ ] 8. BE 전체 테스트 통과 (`cd be && poetry run pytest -q`)

## 우려사항 / 리스크

- **시세 화면 노출 약관 리스크**: KIS Open API 는 본인 거래 목적용 — 받은 시세의 앱 사용자 재제공은 약관/KRX 시세 라이선스 위반 소지. **사용자가 인지하고 포함 결정함(2026-06-07).** 차후 KIS 공식 확인 권장. env 전환만으로 즉시 복귀 가능(`QUOTE_PROVIDERS` 에서 kis 제거).
- **rate limit 공유 한도**: 서비스 appkey 1개에 실전 ~20req/s(재검증 필요) — Naver/Yahoo 엔 없던 제약. 시세는 TTLCache+single-flight 가 완충하나 KIS 1차 전환 후 장중 병목 모니터링 필요. seed/batch 는 무관.
- **토큰 발급 1분당 1회(EGW00133)**: 캐시 미스 시 동시 요청이 발급을 중복 시도하면 throttle — lock 으로 차단하되, 프로세스 재시작 직후 1회 실패 가능성 있음(재시도 backoff 고려).
- **멀티워커 전제**: in-process 토큰 캐시는 단일 워커 전제. 멀티워커 배포 전 공유 저장소 필요(백로그 "Preview staging 멀티 워커 대응" 과 동일 계열).
- **.mst 파싱 취약성**: fixed-width 포맷/EUC-KR — 컬럼 오프셋 변경 시 조용히 깨질 수 있어 파싱 검증 테스트 필수.
- **모의(mock) 환경 미검증 영역**: 모의투자는 일부 시세 API 미지원 가능 — 실호출 검증은 실전 도메인 기준.
