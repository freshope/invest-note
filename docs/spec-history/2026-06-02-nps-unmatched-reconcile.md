# 현재 작업 사양 — NPS 미매칭 과거사명 alias reconcile

> 완료: 2026-06-02 (테스트 370 passed, 로컬 실측 4건 reconcile 확인)

## 배경 / 문제
- NPS 적재는 종목코드가 없어 종목명으로 매칭한다. 재적재 후에도 잔여 미매칭(`nps_unmatched`) 69건이 남는다.
- 잔여의 두 부류:
  - **드리프트**: stocks 에 *현재명*으로 존재하나 NPS 는 *과거명*(엔씨소프트→stocks "NC", 휠라홀딩스→"미스토홀딩스", DGB금융지주→"iM금융지주", 디엘이앤씨→"DL이앤씨"). 자동 소스로 해소 불가 — Naver 자동완성은 *현재 등록명 prefix* 만 인덱스해 과거명으로 0건(재검증 4/69만 매칭).
  - **상폐**: stocks 부재(동원F&B·신세계건설·셀리버리 등). **영구 미매칭이 정상** — 어떤 ticker 에도 매칭 금지(데이터 오염).
- `nps_unmatched.resolved_ticker`(현재 코드 미사용, 025 마이그레이션에 reconcile 용도로 정의)를 큐레이터 입력으로 활용한다.

## 메커니즘 — 자기완결 reconcile
> ⚠️ NPS seed 는 fingerprint-skip(스냅샷 연1회 변경)이라 "다음 정기 적재가 반영"이 성립하지 않는다. `apply_snapshot` 은 prune 도 안 한다. 따라서 reconcile 은 **즉시 반영 + 행 삭제**까지 자기완결로 수행한다.

입력: 관리자가 SQL 로 `nps_unmatched.resolved_ticker` 를 채운다(상폐는 NULL 유지 → 영구 미매칭).

처리(`resolved_ticker` 채워진 행마다, 단일 트랜잭션):
1. `resolved_ticker` 가 `stocks` 에 실제 존재하는지 검증 — 없으면 skip(행 보존, `skipped_no_stock` 집계). 오타·상폐 가드.
2. `stock_aliases` upsert: `(ticker=resolved_ticker, alias=clean_name(nps_name), source='nps_reconcile')`. 미래 강제 재적재 재발 방지(durability 보험). `clean_name` 으로 등록하므로 `(주)엔씨소프트`(major)·`엔씨소프트`(held)가 alias 하나로 함께 해소.
3. `set_nps_holding({ticker}, holding_level, as_of)` — 즉시 반영(실효). `holding_level` 별 그룹화 호출(held→major 순서). **`as_of` 는 seed 와 동일하게 held 기준일로 통일** — 행별 `nps_as_of`(major 행은 major 기준일)를 그대로 쓰면 seed-매칭분과 날짜가 갈리므로, `stocks` 에 박힌 기준일(`max(nps_as_of) where nps_holding is not null`)을 조회해 사용.
4. 처리된 `nps_unmatched` 행 삭제 — stale 방지.

**2+3 둘 다 필요**: 실효는 3·4, alias(2)는 다음 강제 재적재의 `reset_nps_holding` 이 지워도 `resolve_tickers`(search 가 alias 포함)가 재매칭하게 하는 보험.

## 작업 분해 (1요청=1파일, 의존 순서)
1. **`db_ops/stocks_repo.py`** — repo 함수 2개 추가
   - `fetch_resolved_unmatched(conn, *, country_code)` → `resolved_ticker IS NOT NULL` 행 `[{nps_name, nps_as_of, holding_level, resolved_ticker}]`
   - `delete_nps_unmatched(conn, keys)` → 처리된 `(nps_name, nps_as_of)` 행 삭제(executemany)
   - 검증: 두 함수 멱등/쿼리 형태
2. **`services/nps_seed.py`** — `reconcile_nps_unmatched(db_url, *, country_code=DEFAULT_COUNTRY) -> dict`
   - 위 1~4. `stock_seed.upsert_aliases` 재사용(existing 필터 = stocks 없는 ticker 자동 skip = 상폐 가드 무료).
   - stocks 존재 검증은 `upsert_aliases` 결과 + 명시적 ticker 집합 비교로 `skipped_no_stock` 산출.
   - 반환 `{reconciled, aliases, skipped_no_stock}`.
   - 검증: 매핑 해소/상폐 skip/holding 반영 단위 테스트
3. **`routers/admin.py`** — `POST /admin/reconcile/nps`
   - `require_admin_token` + `get_settings`. **동기 실행(가벼움) → 200 + 통계 반환**(seed 의 202 background 와 달리 결과 즉시 확인 유용).
   - 검증: 토큰 거부/수락 테스트
4. **`tests/test_nps_seed.py`** — reconcile 단위 + 엔드포인트 토큰

## 검증 기준
- 단위: `resolved_ticker` 있고 stocks 존재 → alias 등록 + `set_nps_holding` + 행 삭제 호출. stocks 없으면 skip + 행 보존.
- 엔드포인트: 미토큰/오토큰 거부, 정상 토큰 200.
- `cd be && poetry run pytest -q` 그린.
- (로컬 실측) 잔여 드리프트 종목 `resolved_ticker` SQL UPDATE 후 reconcile → `nps_unmatched` 감소 + 해당 종목 `nps_holding` 반영 확인.

## 제외 (over-engineering 방지)
- 후보 추천 도구(사명변경은 유사도로 못 잡아 효용 0)
- 자동 ticker 추론(오매칭 위험 — ticker 확정은 큐레이터 몫)
- CSV 업로드(SQL UPDATE 로 충분, backlog 폴백 유지)
