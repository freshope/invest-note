# Spec: 자산 추이 backfill 빈-범위 재질의 차단(B) + 종목 병렬화

> 완료: 2026-06-04

## Context / 배경

`GET /assets/history` 가 종가가 이미 적재돼 있어도 매 요청 12초까지 걸린다. 원인은
`backfill_closes`(daily_price_seed.py)의 skip 조건이 **달력상 어제(`yesterday`)** 와
비교(`begin > yesterday`)하는데, 어제가 비거래일(예: 2026-06-03 지방선거 휴장)이면
종목 watermark(6/2) < yesterday(6/3) 이라 **데이터가 있어도 fetch 가 발사**된다.
게다가 휴장일 응답은 거래일이 없어 `rows=[]` → `if rows:`(daily_price_seed.py:183)가
거짓 → upsert 안 됨 → watermark 영구 정체 → **매 요청 26종목을 순차로 data.go.kr 재질의**.

실측(개발 DB, 26종목): backfill = 전체의 93%(3.58s), compute 0.02s·quotes 0.17s·
get_closes 0.06s 는 모두 무관. backfill 반복 측정 run1~4 모두 발사(1.1~3.1s),
게이트웨이 지연/간헐 404 재시도 시 12s+.

영향: ① 페이지 지연, ② **data.go.kr 호출 쿼터** 가 트래픽(유저×오픈횟수×종목수)에
비례해 무한 증가 — 휴장일에 쿼터 소진 위험.

## 목표 (완료 기준)

1. 종가가 적재돼 있고 어제가 비거래일이어도 `backfill_closes` 가 **두 번째 요청부터
   data.go.kr 를 호출하지 않는다**(쿨다운 내). → 12초 지연 제거.
2. data.go.kr 호출 수가 **트래픽과 무관**하게 "종목수 × (쿨다운 주기당 1회)" 상한으로 묶인다.
3. 신규 추가 종목은 cron 없이도 첫 요청에서 1회 적재 후 이후 skip 된다.
4. 종목별 data.go.kr fetch 가 **병렬**(동시성 상한 가드)로 실행돼 콜드 경로 wall-clock 단축.
5. data.go.kr T+1 늦은 발행을 놓치지 않는다(쿨다운 경과 후 1회 재probe).
6. BE 테스트 통과(`cd be && poetry run pytest -q`).

## 설계

### 접근 방식 (방향 B + 종목 병렬화)

**B — "확인 완료" 마커 (코드베이스의 `naver_checked_at` 패턴 미러링, stock_seed.py:613-615)**

진행 상태를 "종가 존재 여부(upsert 된 행)"와 분리해, "어디까지 data.go.kr 를 조회했나"를
별도 상태로 기록한다. 빈 응답이어도 기록 → 무한 재질의 차단.

- 신규 테이블 `daily_price_sync_state(country_code, ticker, checked_through_date, checked_at)`.
- `backfill_closes` skip 판정(종목별):
  - `begin = max(earliest, watermark+1)` (watermark = 실데이터 max close_date — 그대로 유지)
  - `begin > yesterday` → skip (정상 평일: 실데이터로 어제까지 채움)
  - 그 외, `checked_through_date >= yesterday` **이고** `checked_at` 이 쿨다운 내(최근) → skip
    (휴장/빈 범위를 최근 확인함 → API 불필요)
  - 그 외 → fetch 대상
- fetch 성공 시(빈 응답 포함) `checked_through_date = yesterday`, `checked_at = now` upsert.
- **fetch 예외(네트워크 실패) 시에는 sync_state 를 갱신하지 않는다**(다음 요청 재시도 보장) +
  `incomplete=True`.
- 쿨다운 상수(예: `timedelta(hours=6)`)로 늦은 발행(T+1 ~14:00 KST) 재probe 허용 +
  호출 수 상한. 값은 튜닝 가능(우려사항 참고).

**종목 병렬화 (Semaphore + gather, stock_seed.py:601-626 idiom 미러링)**

`for ticker: await fetch` 순차 루프를 동시 실행으로 전환하되, **asyncpg 단일 커넥션은
동시 쿼리 불가**이므로 단계 분리:

1. (DB, 순차) `get_watermarks` + `get_sync_state` + market 조회 — 루프 전 일괄.
2. (네트워크, 병렬) fetch 대상 종목만 `asyncio.Semaphore(_BACKFILL_CONCURRENCY)` + `gather`
   로 `fetch_daily_closes` 동시 호출. conn 미사용.
3. (DB, 순차) 결과를 순차로 `upsert_closes` + `upsert_sync_state`. 예외 종목은 incomplete.

동시성 상한 상수 `_BACKFILL_CONCURRENCY`(예: 8, `_NAVER_CONCURRENCY` 선례) 로 게이트웨이
429 가드.

### 주요 변경 파일

- `supabase/migrations/027_daily_price_sync_state.sql` — 신규 테이블(전역 참조 데이터,
  RLS 미적용, 026 패턴 미러링). PK `(country_code, ticker)`.
- `be/src/invest_note_api/db_ops/daily_prices_repo.py` — `get_sync_state(conn, tickers,
  country_code) -> dict[str, {checked_through_date, checked_at}]`, `upsert_sync_state(conn,
  rows, country_code)` 추가.
- `be/src/invest_note_api/services/daily_price_seed.py` — `backfill_closes` 재작성
  (sync_state skip + 3단계 분리 + Semaphore/gather 병렬). `_BACKFILL_CONCURRENCY`,
  `_BACKFILL_RECHECK_COOLDOWN` 상수 추가.
- `be/tests/test_daily_price_seed.py` — 기존 `test_backfill_routes_endpoint_by_market`
  업데이트(get_sync_state mock 추가) + 신규 테스트.

### 구현 체크리스트 (1항목 = 1파일 단위, 순서대로)

- [x] `supabase/migrations/027_daily_price_sync_state.sql` 작성(026 미러링, RLS 미적용)
- [x] `daily_prices_repo.py` 에 `get_sync_state` / `upsert_sync_state` 추가
- [x] `daily_price_seed.py` `backfill_closes` 재작성(마커 skip + 3단계 분리 + 병렬) +
      상수 2개 추가
- [x] `test_daily_price_seed.py` 업데이트 + 신규 테스트:
      ① 빈 범위 마커 skip(2회차 호출에서 fetch 미발생),
      ② 쿨다운 경과 시 재probe,
      ③ 신규 종목 1회 fetch,
      ④ fetch 예외 시 sync_state 미갱신·incomplete=True,
      ⑤ 병렬 fetch 동작(동시성 상한 내)
- [x] BE 테스트 통과(`cd be && poetry run pytest -q`) — 412 passed
- [x] 로컬 재현 검증: 휴장일(today=06-04) 조건 backfill 1.37s → 2회차 0.01s

## 우려사항 / 리스크

- **쿨다운 값 트레이드오프**: 짧으면(예: 3h) 늦은 발행을 빨리 반영하나 호출 수↑,
  길면(예: 6h) 쿼터↓·반영 지연↑. 오늘 점은 라이브 시세를 쓰므로 과거 점(T) 종가의
  일시적 carry-forward 표시(incomplete)만 영향 → 6h 기본값 제안, 운영 보며 조정.
- **마이그레이션 적용**: 로컬(supabase db) + 운영(Coolify/Supabase)에 027 적용 필요.
  운영 적용은 사용자 확인 후(직접 실행 금지 정책).
- **asyncpg 단일 커넥션 동시성**: 병렬은 fetch(네트워크)만, upsert(DB)는 순차 — 반드시 분리.
- **신규 종목 1회 비용**: 신규 종목은 첫 요청에서 전체 이력 fetch(불가피). 병렬화로 완화.
- cron(방향 ①)은 이번 범위에서 제외 — 마커 적용 후 콜드스타트 지연이 남으면 후속 검토.

## 검증 (Verification)

1. 단위 테스트: `cd be && poetry run pytest tests/test_daily_price_seed.py -q` (신규 5케이스 포함).
2. 전체: `cd be && poetry run pytest -q` 회귀 없음.
3. 로컬 재현(개발 DB, today=2026-06-04 / yesterday=06-03 휴장, 26종목):
   `backfill_closes` 를 연속 2회 호출 → 1회차는 26종목 probe(빈 응답 후 마커 기록),
   **2회차는 fetch 0건·≈0s**(쿨다운 내 skip) 확인. (앞선 조사에서 쓴 타이밍 스크립트 재사용.)
