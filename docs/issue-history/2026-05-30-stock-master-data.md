# Spec: 종목 검색 자체 데이터 운영 (stocks 마스터 재도입 + 다중 소스 주기 적재)

> 완료: 2026-05-30

> 검토(review) 성격. deliverable = ① 다중 소스 적재 아키텍처, ② 테이블 설계,
> ③ 검색 전략, ④ 주기 갱신, ⑤ 1차 구현 + 결정 게이트.

## Context (배경 / 왜 지금)

현재 종목 검색·일괄 import 매칭은 **Naver 비공식 자동완성 API 단일 경로**다
(`external/naver_search.py`, `routers/stocks.py:/search`, `broker_import/ticker_resolver.py`).

자체 마스터(`stocks`)는 과거 운영하다 **2026-04-28 폐기**됨 (`docs/decisions.md:307-312`,
`016_drop_stocks.sql`). 폐기 사유: ① Coverage 부족(KIND 가 일반 상장사만 → ETF/ETN/우선주 누락),
② Matchability 부족(`lookup_by_names` 정확 일치만 → 약칭 "현대차↔현대자동차" 실패). Naver 자동완성이
둘 다 해결해 단일화함. `docs/backlog.md:30` 의 재도입 트리거 중 **① ETF/약칭 소스 확보**를 동기로 재추진.

**사용자 확정 요구사항:**
| 항목 | 결정 |
|------|------|
| 동기 | ETF/약칭 커버 소스 확보 |
| 런타임 Naver | **완전 대체** (검색·import 요청은 로컬 DB 만, 외부 호출 0) |
| 적용 범위 | 인터랙티브 검색(`/stocks/search`) + 일괄 import 매칭(`ticker_resolver`) |
| 시장 범위 | 해외 포함 **설계** (적재는 KR 부터) |
| 시세 | 범위 제외 (계속 외부 API) |
| **적재 주기** | **단발성 아님 — 주기적 갱신** (신규 상장/상폐/메타 반영) |
| **소스 다중화** | **단일 소스 의존 금지 — 여러 소스 교차 참조로 약칭·완성도 향상** |
| **Naver 적재** | **필요 시 Naver 데이터도 적재** (런타임 아닌 batch enrichment) |

### 핵심 통찰 — "런타임 완전 대체 + Naver 적재"의 양립

Naver 를 **런타임 fallback 이 아니라 적재(batch) 단계의 enrichment 소스**로 쓴다. 그러면:
- **검색/import 요청은 로컬 DB 만** 조회 → "완전 대체" 충족, 외부 의존·지연 0.
- Naver 가 가진 **약칭·부분일치 해소 능력을 offline 으로 흡수**해 `stock_aliases` 에 적재 →
  폐기 사유였던 matchability gap 을 정면 해소. (이전 폐기 결정의 반대 논거를 그대로 무력화.)

---

## 1. 다중 소스 적재 아키텍처 (핵심)

소스를 **역할별로 분리**하고, 각 소스는 행을 생산하는 fetcher 로 구현. 과도한 프레임워크 없이
**fetcher 함수 리스트 + merge 규칙**으로 단순하게.

| 소스 | 역할 | 산출물 | 권위(authority) |
|------|------|--------|------|
| **공공데이터포털 금융위 KRX상장종목정보**<br>(data.go.kr/15094775) | Coverage 주축 | 전 종목 (ticker/명/시장) | `stocks` 존재·is_active 의 **권위** |
| **KRX 정보데이터시스템**<br>(data.krx.co.kr ETF/ETN 목록) | ETF/ETN 보강 | ETF/ETN ticker/명 | Coverage 보조 (공공데이터 누락분) |
| **Naver** (ac.stock.naver.com / api.stock.naver.com) | **약칭·메타 enrichment** | alias→ticker, 시장/거래소 보정 | `stock_aliases` + null 메타 채움 (stocks 존재·삭제엔 미관여) |
| FinanceDataReader / pykrx | (선택) 개발 초기 검증·대조 + **명칭 변형 alias** | 전 종목 대조용 | 운영 권위 아님 — 교차 검증 + 변형명 alias 공급 |

**적재 권위 규칙 (다중 소스 충돌 방지):**
- **존재/상폐 판정 = Coverage 소스(공공데이터+KRX)만 권위.** Coverage pass 가 touch 한 ticker 만 `is_active=true`.
- **canonical `asset_name` = 공공데이터 권위.** 다른 소스(KRX/FDR/Naver)가 같은 ticker 에 **다른 이름**을 주면
  → stocks.asset_name 은 덮지 않고 그 변형명을 **`stock_aliases` 로 등록** (검색만 가능, 표시명은 canonical 유지).
- **Naver/enrichment pass 는 절대 stocks 를 생성/삭제하지 않는다** — 기존 ticker 의 ① `stock_aliases` 추가,
  ② null 인 exchange/market/sector 보정만. (소스 노이즈가 마스터 무결성 오염하는 것 방지.)
- 동일 ticker 다중 소스 → 공공데이터를 기본 권위, KRX 가 ETF/ETN 분류 보정.

### 라이선스 (검토 결과 — 소스 선택의 결정 변수)
- **KRX 공식 OpenAPI(openapi.krx.co.kr)는 "비상업적 목적만" 명시** → 스토어 게시 앱엔 결격 소지 →
  **운영 coverage 는 공공데이터포털(상업적 OK)** 채택, KRX 는 정보데이터시스템 공개 목록(ETF/ETN)만 보조 사용.
- Naver 는 이미 현 시스템이 쓰는 의존이라 추가 위험 없음 (적재용으로 사용량 오히려 감소).
- FDR/pykrx 는 스크래핑 회색지대 → **개발 초기 교차 검증용**으로만, 운영 권위는 공식 소스.

### 약칭(alias) 수급 전략 — 다중 소스 흡수
약칭은 어떤 단일 공식 소스에도 완전하지 않음 → **4중 축**으로 자체 소유:
1. **교차 소스 명칭 변형 (Naver 외 소스 간):** 동일 ticker 인데 소스별 `asset_name` 이 다르면, **canonical(공공데이터
   권위명) 외의 변형 명칭을 alias 로 등록** (`source` = 해당 소스명 'data_go_kr'|'krx'|'fdr' 등). 예: 공공데이터 "삼성전자"
   ↔ 다른 소스 "삼성전자보통주", 우선주 표기 변형 "삼성전자우"/"삼성전자우선주". **공식 소스 간 표기 차이를 무료로 흡수.**
2. **수동 시드:** 대형주 구어체 약칭 수십 건 (현대차, 삼전, 네카오 등) — 초기 부트스트랩.
3. **Naver replay:** (수동 약칭 후보 ∪ 운영 미해결 검색 로그)를 batch 에서 Naver 자동완성에 질의 →
   resolve 되면 `stock_aliases(alias→ticker, source='naver')` 적재. Naver 의 약칭 해소력을 offline 축적.
4. **운영 로그:** 로컬 검색 0건 결과 쿼리를 로깅 → 다음 batch 의 Naver replay 입력으로 환류 (점진 완성).

모든 alias 는 적재 시 `alias_chosung` 계산 → 초성 검색에도 포함. canonical 명칭과 동일한 변형은 중복 제외.

## 2. 주기 갱신 (periodic refresh)

- **메커니즘:** 멱등 적재 스크립트 `be/scripts/seed_stocks.py` 를 **스케줄 실행**.
  배포가 Coolify self-hosted (memory `project_deploy_targets`) 이므로 **Coolify scheduled task / host cron**
  으로 `poetry run python scripts/seed_stocks.py` 주기 호출 (예: 1일 1회 장 마감 후). 대안: Supabase `pg_cron`.
- **멱등성:** `on conflict (country_code, ticker) do update` UPSERT (폐기본 `seed_stocks.py` 패턴 재사용).
- **상폐 soft-delete:** Coverage pass 시작 시각 `run_start` 기록 → pass 후
  `update stocks set is_active=false where country_code='KR' and updated_at < run_start` (이번 run 에 안 보인 종목).
  검색은 `is_active=true` 만 노출. **하드 삭제 안 함** (과거 거래 종목명 표시 보존).
- **운영비 명시:** 주기 batch 유지가 이전 폐기의 "마스터 유지 비용" 실체. cron 1개 + 멱등 스크립트로 최소화.

## 3. 테이블 설계 (014/015 이력 재활용)

신규 `supabase/migrations/020_recreate_stocks.sql`:

```sql
create extension if not exists pg_trgm;

create table public.stocks (
    country_code  text not null default 'KR',
    ticker        text not null,
    asset_name    text not null,
    name_chosung  text,                 -- 초성 인덱스 ("삼성전자"→"ㅅㅅㅈㅈ"), 적재 시 계산
    currency      text not null default 'KRW',
    exchange      text,                 -- 'KRX'
    market        text not null,        -- KOSPI/KOSDAQ/KONEX/ETF/ETN (014 의 CHECK 제거 — ETF/ETN 수용)
    sector        text,
    is_active     boolean not null default true,   -- 상폐 soft-delete
    updated_at    timestamptz not null default now(),
    primary key (country_code, ticker)
);
create index stocks_name_trgm_idx on public.stocks using gin (asset_name gin_trgm_ops);
create index stocks_chosung_idx   on public.stocks (name_chosung);
create index stocks_active_idx    on public.stocks (country_code, is_active);

-- 약칭(약칭/별칭) — 외부 공식 소스에 없는 구어체 약칭을 자체 소유
create table public.stock_aliases (
    country_code  text not null,
    ticker        text not null,
    alias         text not null,
    alias_chosung text,                             -- 약칭 초성 ("현대차"→"ㅎㄷㅊ"), 적재 시 계산
    source        text not null default 'manual',   -- 'manual' | 'naver' | 'data_go_kr' | 'krx' | 'fdr' (교차 소스 변형명)
    created_at    timestamptz not null default now(),
    primary key (country_code, ticker, alias),
    foreign key (country_code, ticker) references public.stocks (country_code, ticker) on delete cascade
);
create index stock_aliases_alias_idx   on public.stock_aliases (alias);
create index stock_aliases_chosung_idx on public.stock_aliases (alias_chosung);
```

설계 메모:
- **해외 대비:** (country_code, ticker) 복합 PK (015 방향 유지). 적재는 KR 만.
- **market CHECK 제거:** 014 의 CHECK 가 ETF/ETN 막았음(폐기 사유) → 제거.
- **RLS 불필요:** stocks/aliases 는 public read-only 마스터. trades 가 FK 참조 안 함 → 거래 데이터 무영향.

## 4. 검색 전략 (matchability — 로컬만으로)

`stocks_repo.search()` 우선순위 (모두 `is_active=true` 필터):
1. ticker 정확일치 (`ticker = q`)
2. 종목명 prefix (`asset_name ILIKE q||'%'`) — 최우선 정렬
3. 별칭 일치 (`stock_aliases.alias ILIKE q||'%'`) — Naver/수동 흡수분
4. **초성 일치 (q 가 전부 초성일 때)** — 종목명 `name_chosung LIKE q||'%'` **+ 약칭 `alias_chosung LIKE q||'%'`** 둘 다.
   예: "ㅅㅅㅈㅈ"→삼성전자(종목명), "ㅎㄷㅊ"→현대차→현대자동차(약칭 초성)
5. 부분일치 (`asset_name ILIKE '%'||q||'%'`, pg_trgm GIN) — "전자"→삼성전자 폴백
6. dedup + 우선순위 정렬 + LIMIT 10. **응답 shape = 기존 `StockSearchResult`(code/name/market/exchange) 유지 → FE 무변경.**

- 초성 계산: 적재 시 Python 한글 유니코드 분해 헬퍼(외부 의존 불필요). **종목명·약칭 동일 헬퍼로 계산.**

## 5. 주요 변경 파일

**BE (be/):**
- `supabase/migrations/020_recreate_stocks.sql` — stocks/stock_aliases + pg_trgm (신규)
- `be/scripts/seed_stocks.py` — **다중 소스 멱등 적재**(공공데이터+KRX coverage → Naver enrichment → 초성 계산 →
  상폐 soft-delete). 폐기본(`git show decc141~1:api/scripts/seed_stocks.py`)의 UPSERT 패턴 출발점으로
  소스 fetcher 분리 + ETF/ETN 추가. **주기 실행 진입점.**
- `be/scripts/sources/` (또는 단일 파일 내 함수) — `fetch_data_go_kr()`, `fetch_krx_etf_etn()`,
  `fetch_naver_aliases(queries)` fetcher (과한 추상화 지양, 함수 단위)
- `be/src/invest_note_api/db_ops/stocks_repo.py` — `search()`(fuzzy/초성/alias) + `lookup_by_names()` 재도입 (신규)
- `be/src/invest_note_api/routers/stocks.py` — `/search` 를 `search_kr`(Naver)→`stocks_repo.search`(DB) 교체
- `be/src/invest_note_api/broker_import/ticker_resolver.py` — `find_first_kr_match`(Naver)→`stocks_repo.lookup_by_names`(DB)
- `be/src/invest_note_api/external/naver_search.py` — **런타임 검색·import 에서 제거, 적재 스크립트로 이동/재사용**.
  (시세 `quotes.py` 는 Naver 유지, 범위 외.) dead code 여부 확인 후 정리.
- `be/tests/test_stocks.py`, `be/tests/test_ticker_resolver.py` — DB 기반 재작성

**FE (fe/):** 변경 없음 (응답 shape 유지). 회귀 확인만.

## 6. 구현 체크리스트 (의존 순서)

- [x] **결정 게이트:** ETF/약칭 소스 확인 → 권장 소스 채택. data.go.kr 403(키 활성화 지연)으로 **FDR fallback** 채택
- [x] 마이그레이션 `020`(stocks/aliases + pg_trgm) → 실 DB 검증. 추가: `021`(fingerprint), `022`(naver_checked), `023`(source)
- [x] `seed_stocks.py` 다중 소스 **순차 병합**(authority overwrite → 하위 preserve+변형명) + 초성 + fingerprint skip
- [x] coverage: **FDR로 주식 2878 + ETF 1130 적재**(스파이크: ETF 포함 확인). ETN 은 FDR 미지원 → **이월(backlog)**
- [x] **교차 소스 변형명 alias:** 동일 ticker 명칭 차이를 `stock_aliases`(source 구분)로 등록
- [x] Naver enrichment 재설계: **종목별 교차검증**(이름 변형 별칭 + 시장 교차검증, 종목당 1회). 검색-miss 환류는 도입 후 제거
- [x] 상폐 soft-delete (소스 union 미포함 ticker → is_active=false, fingerprint skip 양립)
- [x] `stocks_repo.search()` + `lookup_by_names()` 구현 (ticker/prefix/alias/초성/trgm)
- [x] `routers/stocks.py:/search` DB 조회 교체 (응답 shape 동일)
- [x] `ticker_resolver` DB 조회 교체, 미해결 None 유지
- [x] `naver_search.py` 런타임 제거 (seed enrichment 용으로만 유지, 시세 경로 무영향)
- [ ] 주기 실행 설정: Coolify scheduled task / cron 1일 1회 → **이월(backlog, ops)**
- [x] 테스트 재작성: `test_stocks.py`/`test_ticker_resolver.py`(DB), `test_stocks_repo.py` 신규 (328 통과)
- [ ] `be/sample/` 실제 거래내역서 import 매칭 회귀 → **이월(seed 데이터/키 필요로 blocked)**
- [x] `docs/decisions.md` 결정 역전 기록(2026-04-28→재도입), `backlog.md` 정리

> 이월 항목(backlog 기록): ① ETN 보강(별도 소스), ② data.go.kr 키 활성화 후 공식 소스 전환, ③ 주기 실행 설정, ④ market 분류 불일치 검토, ⑤ be/sample import 회귀.

## 7. 우려사항 / 리스크

- **(상) 데이터 소스 라이선스:** KRX 공식 OpenAPI 비상업 제약 → 공공데이터 + 정보데이터시스템 공개 목록으로 회피.
- **(상) Naver 적재 합법성/안정성:** 비공식 API 라 포맷 변경·차단 가능. **런타임 아닌 batch 라 장애 시 검색은 무중단**
  (기존 alias 유지). enrichment 실패는 graceful skip.
- **(중) 약칭 초기 커버리지:** Naver 흡수 전엔 수동 시드 수준 → 초기 검색 품질 < Naver. replay 누적으로 수렴.
- **(중) 다중 소스 정합:** 동일 종목 명칭/시장 불일치 → §1 권위 규칙(공공데이터 권위, Naver 비관여)으로 결정.
- **(중) 주기 batch 운영비:** cron + 멱등 스크립트로 최소화. 실패 알림/모니터링 후순위 고려.
- **(하) pg_trgm 한글 정밀도:** prefix/초성/alias 1차, trgm 폴백.

## 8. 검증 (E2E)

- `cd be && poetry run pytest tests/test_stocks.py tests/test_ticker_resolver.py -q`
- `supabase db reset` 후 `poetry run python be/scripts/seed_stocks.py`:
  - `select market, count(*) from stocks where is_active group by market` → KOSPI/KOSDAQ/KONEX/**ETF/ETN** 적재 확인
  - `select source, count(*) from stock_aliases group by source` → manual/naver 적재 확인
- 멱등성: seed 2회 연속 실행 후 행수 동일 확인
- 상폐 soft-delete: 가짜 ticker 삽입 후 seed → `is_active=false` 전환 확인
- 수동 `/stocks/search`: `q=삼성` / `q=ㅅㅅㅈㅈ`(종목명 초성) / `q=ㅎㄷㅊ`(약칭 초성) / `q=현대차`(약칭/Naver흡수) / `q=TIGER`(ETF) 기대 결과
- `be/sample/` 일괄 import → ticker 매칭률 Naver 시절 대비 확인
