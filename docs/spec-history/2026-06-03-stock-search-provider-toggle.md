> 완료: 2026-06-03

# Spec: 종목 검색 provider 토글 (Naver ↔ DB)

## 배경 / 문제

`scripts/seed_stocks.py`의 data.go.kr 종목 적재가 게이트웨이 응답 불안정성으로 바로 신뢰하기 어렵다.
일정 기간 모니터링 후 적용하기로 하고, 그동안 사용자 대면 **종목 검색**은 이전의 안정적인 Naver
자동완성 방식으로 되돌린다. data.go.kr 기반 로컬 DB 검색 코드는 폐기하지 않고 환경변수로 즉시
전환 가능하게 유지해, 모니터링이 끝나면 코드 변경 없이 db로 복귀한다.

확인 결과: stock 데이터는 검색 외에도 거래 import의 종목명→ticker 매칭, NPS seed, marcap 갱신에서
사용된다. 모두 batch/seed 성격이라 검색을 Naver로 돌려도 깨지지 않으므로 **이번 범위는 검색
엔드포인트 토글로 한정**한다(사용자 결정).

## 목표

- `GET /stocks/search`가 `STOCK_SEARCH_PROVIDER` 값에 따라 Naver(`search_kr`) 또는 로컬
  DB(`stocks_repo.search`)로 동작한다.
- 미설정 시 기본값은 `naver` (이전 방식 복귀).
- `db`로 바꾸면 코드 변경 없이 로컬 DB 검색으로 즉시 복귀한다.
- 응답 shape(`{code, name, market, exchange}`)는 동일 — FE 변경 없음.

## 설계

### 접근 방식

Naver 구현(`external/naver_search.py`의 `search_kr`)은 이미 존재하므로 재연결만 한다.
`Settings`에 provider 플래그 1개 추가, 라우터에서 분기. `pool`/`http_client` 모두 주입.

### 주요 변경 파일

- `be/src/invest_note_api/config.py` — `stock_search_provider: str = "naver"` 추가
- `be/src/invest_note_api/routers/stocks.py` — provider 분기 + `search_kr`/`get_settings` 배선
- `be/tests/test_stocks.py` — 기존 DB-path 테스트는 db provider 고정 + naver 경로/기본값 테스트 추가
- `be/.env.example` — `STOCK_SEARCH_PROVIDER` 문서화

### 손대지 않는 것

ticker_resolver/trades.py, nps_seed, stock_seed marcap, FE, seed 파이프라인.

## 구현 체크리스트

- [x] `config.py`에 `stock_search_provider` 추가
- [x] `routers/stocks.py` provider 분기 배선
- [x] `tests/test_stocks.py` db provider 고정 + naver 경로/기본값 테스트
- [x] `.env.example` 변수 문서화
- [x] BE 테스트 통과 (`cd be && poetry run pytest tests/test_stocks.py -q`) — 12 passed, 전체 372 passed

## 우려사항 / 리스크

- 기본값 `naver` 전환 시 기존 DB-path 테스트가 깨지므로 provider를 db로 override 필요.
- Naver 외부 라이브 호출이라 지연/실패 노출 가능(실패는 빈 리스트로 흡수 — 의도된 트레이드오프).
- import 매칭·NPS는 여전히 로컬 stocks(stale 가능) 의존 — 범위 밖, 별도 추적.
