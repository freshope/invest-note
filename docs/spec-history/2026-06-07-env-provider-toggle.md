# Spec: 외부 데이터 공급자 env 토글 구조

> 완료: 2026-06-07

## 배경 / 문제

KIS Open API 도입(시세)과 향후 공급처 추가에 대비해, 모든 외부 데이터의 공급처를 환경변수로 선택/우선순위 지정 가능한 registry 구조로 리팩토링한다. 현재 시세 fallback 체인(`quotes.py`)·종목 마스터 파이프라인(`stock_seed.py`)·일별 종가 tail-gap(`daily_price_seed.py`)은 공급자 순서가 코드에 하드코딩되어 있어, 공급처를 추가·교체하려면 코드 수정이 필요하다. 종목 검색만 유일하게 `STOCK_SEARCH_PROVIDER` env 토글 전례가 있다.

**동작 보존 리팩토링** — 기본 env 값에서 현재와 완전히 동일하게 동작해야 한다. FE 변경 없음.

## 목표

- 데이터 종류별 공급처가 env 로 전환된다 (배포 설정만으로 공급자 교체/순서 변경).
- 새 공급자를 registry 에 등록하면 env 변경만으로 활성화된다 (예: KIS 도입 시 `QUOTE_PROVIDERS=kis,naver,yahoo`).
- 기본 env 에서 기존 테스트 전부 무수정 통과 (동작 보존 증명).

## 설계

### env 변수 최종안

| 변수명 | 형식 | 기본값 | 적용 |
|---|---|---|---|
| `QUOTE_PROVIDERS` | 콤마 우선순위 체인 | `naver,yahoo` | 시세 (naver=realtime→basic 내부, yahoo=.KS/.KQ 내부) |
| `STOCK_SEARCH_PROVIDER` | 단일 선택 | `naver` | 종목 검색 — **기존 유지, 변경 없음** |
| `STOCK_SEED_SOURCES` | 콤마 체인, **첫 항목=authority** | `data_go_kr,stock_prices,securities` | 종목 마스터 seed |
| `DAILY_PRICE_PROVIDER` | 단일 선택 | `data_go_kr` | 일별 종가 primary |
| `DAILY_PRICE_GAP_PROVIDER` | 단일 선택, `none`=비활성 | `naver` | 일별 종가 T+1 tail-gap 보충 |
| `NPS_PROVIDER` | 단일 선택 | `odcloud` | NPS (registry-of-one) |

### 접근 방식 (핵심 패턴 3단)

1. **리터럴 기본값 + optional 인자**: 체인 함수(`_fetch_kr_price`, `_build_pipeline`, `backfill_closes` 등)에 공급자 순서 인자를 추가하되 기본값은 현재 동작과 동일한 리터럴 → 기존 테스트 무수정 통과.
2. **entry point threading**: 함수 내부에서 `get_settings()` 를 읽지 않는다 (`Settings()`는 `supabase_url` 필수라 단위 테스트가 깨짐). 라우터는 `Depends(get_settings)`, 배치 `main()` 은 `Settings()` 에서 읽어 인자로 전달.
3. **도메인 내 dict registry + 공통 resolver**: 각 모듈에 `{"naver": fn, ...}` registry. 신규 `external/provider_registry.py` 의 `resolve_chain(names, registry, *, domain)` 이 이름→함수 변환, unknown 이름은 `ValueError` (서버·배치 공통 코드패스 검증). config.py 는 도메인 모듈 import 금지 (순환 회피) — 이름 문자열만 방출.

콤마 리스트는 pydantic `list[str]`(JSON 파싱)이 아니라 **str 필드 + 파싱 property** (`quote_provider_list`, `stock_seed_source_list`).

### 토글 제외 (명시적 결정)

- `update_marcap`(always-run)·`crossvalidate_stocks_with_naver` — seed 의 고정 단계로 유지, 주석으로 결정 기록.
- NPS 의 OAS discovery 내부 로직 — odcloud 구현 디테일.

### 주요 변경 파일

- `be/src/invest_note_api/config.py` — provider 필드 + 파싱 property
- `be/src/invest_note_api/external/provider_registry.py` (신규) — `resolve_chain`
- `be/src/invest_note_api/external/quotes.py` — 공급자 함수 분리 + registry
- `be/src/invest_note_api/routers/{stocks,portfolio,analysis,assets,admin}.py` — settings threading
- `be/src/invest_note_api/services/{stock_seed,daily_price_seed,nps_seed}.py` — registry + optional 인자
- `be/.env.example` — 신규 변수 문서화

## 구현 체크리스트

- [x] `config.py` — provider 필드 5개 + 파싱 property 2개 + 한국어 주석
- [x] `external/provider_registry.py` (신규) — `resolve_chain` 헬퍼
- [x] `external/quotes.py` — `_fetch_naver`/`_fetch_yahoo` 분리, `_QUOTE_REGISTRY`, providers 인자
- [x] `routers/stocks.py` — get_quotes 에 settings 주입 + providers 전달
- [x] `routers/portfolio.py` — summary 시세 호출에 providers 전달
- [x] `routers/analysis.py` — dashboard 시세 호출에 providers 전달
- [x] `routers/assets.py` — quotes providers + backfill primary/gap provider 전달
- [x] `services/stock_seed.py` — `_SOURCE_REGISTRY`, `_build_pipeline(api_key, sources=...)`, `seed(..., sources=None)`, `main()` threading
- [x] `services/daily_price_seed.py` — `_PRIMARY_REGISTRY`/`_GAP_REGISTRY`, `backfill_closes` provider 인자, `seed_daily_prices` threading
- [x] `services/nps_seed.py` — `_NPS_REGISTRY`, `seed_nps(..., provider="odcloud")`, `main()` threading
- [x] `routers/admin.py` — seed 트리거 3곳에 source/provider 전달
- [x] `main.py` — lifespan 에서 `validate_quote_providers` startup fail-fast (시세 요청 경로는 gather 가 예외를 삼켜 조용히 null 이 되므로 부팅 검증 필요 — 리뷰 반영)
- [x] `.env.example` — 신규 변수 5개 문서화
- [x] 테스트 추가 — quotes providers 순서/unknown, stock_seed sources/authority, daily_price gap none/unknown, config property 파싱, startup 검증, 라우터 토글 통합 1건
- [x] 전체 테스트 통과 (`cd be && poetry run pytest -q` — 445 passed)

## 우려사항 / 리스크

- **죽은 registry 위험** (env 만 있고 아무도 전달 안 함) → 라우터 4곳 + 배치 3곳 threading 을 체크리스트로 강제, 라우터 통합 테스트로 검증
- 함수 내부 `get_settings()` 호출 금지 → 리터럴 기본값 패턴 고수
- quotes 공급자 함수 분리 시 출력 변동 → 기존 `_try_endpoint`+parse fn 의 thin wrapper 로만 구성
- admin 라우터는 백로그상 제거 예정이지만 현존하므로 일관성 위해 threading 포함 (소규모)
