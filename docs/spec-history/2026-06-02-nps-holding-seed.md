# Spec: 국민연금(NPS) 보유종목 적재 — odcloud API 자동화 (BE 전용)

> 완료: 2026-06-02

## 배경 / 문제

종목명 옆에 "국민연금 보유" 메타(아이콘)를 표시하려면 `stocks.nps_holding` 데이터가 필요하다.
2026-06-01 "odcloud 자동 fetch 불가" 보류 판정은 2026-06-02 재조사로 **오판**임을 실호출로 확인했다
(`infuser.odcloud.kr/oas/docs` discovery + `api.odcloud.kr` fetch → 자동화 가능, `docs/decisions.md` 2026-06-02).
구조적 제약: NPS 응답에 **종목코드가 없다**(종목명/발행기관명만) → 종목명→ticker 매칭 필요,
시점 사명 드리프트로 ~5% 미매칭(실측 정확 93.6%→주석정제 후 94.8%). 미매칭은 폐기 않고 reconcile 큐에 적재.

## 목표

- `POST /admin/seed/nps` 호출 시 최신 NPS 스냅샷을 API로 받아 전체 KR 종목의 `nps_holding`(null/`'held'`/`'major'`)·`nps_as_of`를 일괄 재계산한다.
- 종목명→ticker 매칭은 `stocks_repo.search`(stocks + stock_aliases) 재사용, 미매칭은 `nps_unmatched`에 적재한다.
- `seed_source_state`(`nps_held`/`nps_major` 2행)로 동일 스냅샷 중복 적재를 skip한다.
- 빈 스냅샷(전체보유 0건)이면 전체 리셋을 막는다.

## 설계

### 접근 방식
- 신규 `nps_seed.py`: discovery(soft dependency, 실패 시 fallback uddi 상수) → fingerprint 비교 → fetch → 부기 주석 정제 → 매칭 → apply(트랜잭션: 전체 null 리셋 → held → major 덮어쓰기[major 우선]).
- 적재 실행은 기존 `seed()`처럼 자체 `asyncpg.connect` + advisory lock(요청 풀 미차용).
- 데이터셋: `held`=3070507(`종목명`, 연1회), `major`=15106890(`발행기관명`, 분기). `nps_as_of`=held 기준일.
- **중복방지(2행)**: `source='nps_held'`/`'nps_major'` fingerprint(각 uddi+as_of 해시). 둘 다 동일 → 전체 skip. 하나라도 변경 → 양쪽 fetch + 조인트 재적용.

### 주요 변경 파일
- `supabase/migrations/025_stocks_nps.sql` — `stocks.nps_holding`/`nps_as_of` + `nps_unmatched` 테이블 (신규)
- `be/src/invest_note_api/services/nps_seed.py` — discovery/fetch/match/apply (신규)
- `be/src/invest_note_api/db_ops/stocks_repo.py` — `reset_nps_holding`/`set_nps_holding`/`upsert_nps_unmatched`
- `be/src/invest_note_api/routers/admin.py` — `POST /admin/seed/nps` + `run_seed_nps`
- `be/tests/test_nps_seed.py` — 단위 테스트 (신규)

## 구현 체크리스트

- [x] `025_stocks_nps.sql` — `nps_holding`/`nps_as_of` 컬럼 + `nps_unmatched(nps_name, nps_as_of, holding_level, resolved_ticker null, created_at, PK(nps_name,nps_as_of))`
- [x] `nps_seed.py` discovery — infuser OAS 파싱 + `max(20\d{6})` 정렬 + fallback uddi 상수
- [x] `nps_seed.py` fetch — `api.odcloud.kr` 페이지네이션(perPage 1200, totalCount 경계) + serviceKey 로깅 안전
- [x] `nps_seed.py` fingerprint 2행(`nps_held`/`nps_major`) — 둘 다 동일 시 skip
- [x] `nps_seed.py` 이름정제 `(배당)(무상)(전환)`·`무상(보)` 제거
- [x] `nps_seed.py` 매칭 — `stocks_repo.search` 재사용, 미매칭 수집
- [x] `nps_seed.py` apply — 빈스냅샷 가드 + 트랜잭션 리셋/held/major(우선) + `nps_as_of` + fingerprint 갱신
- [x] `stocks_repo.py` — reset/set/upsert_unmatched 함수
- [x] `admin.py` — `POST /admin/seed/nps` (X-Admin-Token, 202, BackgroundTasks)
- [x] `test_nps_seed.py` + `cd be && poetry run pytest -q` 통과

## 우려사항 / 리스크

- 매칭 정확도 ~5% 미매칭(구조적) → `nps_unmatched` reconcile. trgm(rank5) 오매칭 위험 주의.
- as_of 단일 컬럼(held 기준 통일, major 보조).
- 로컬 DB stale(024 이전) → 실 매칭률 재측정은 마이그레이션+리시드 후(별개 운영).
- fingerprint skip vs 마스터 리시드 → 강제 재적재는 `seed_source_state` nps 행 삭제.
- **joint(단일 컬럼) 유지 결정(2026-06-02)**: held/major를 단일 `nps_holding`에 담고 전체 reset 후 재구성하므로 둘은 항상 함께 fetch+적용해야 한다(reset이 공유 컬럼을 비움). 독립 실행하려면 `nps_held_as_of`/`nps_major_as_of` 2컬럼 분리가 필요하나, 단일 컬럼 단순성을 우선. 트레이드오프: major 분기 갱신 시 held 재매칭 낭비 + major 종목 as_of가 held 날짜로 표기.
