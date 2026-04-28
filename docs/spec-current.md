# Spec: 일괄 등록 종목명 매칭 — Naver API 단일화 + stocks 마스터 제거

## 배경 / 문제

거래명세서 일괄 등록의 종목명 → ticker 매칭이 **stocks 마스터의 exact match에 묶여** 다음 케이스가 실패한다:

1. **약칭 미일치** — "현대차"(거래명세서) vs "현대자동차"(KIND 마스터)
2. **마스터 누락** — KIND 시드(`corpgeneral/corpList.do`)는 일반 상장사만 포함, ETF/ETN/우선주/리츠 제외 → "TIGER 미국S&P500" 등 미존재
3. **변형/공백/대소문자 차이 일체 미허용** (한글 검색 정확성 의심)

KIND 외 어떤 공식 데이터 소스도 약칭 매핑은 제공하지 않으며, ETF 보강을 위한 KRX OTP는 이전 spec(`docs/spec-history/2026-04-28-stocks-master-i18n.md`)에서 인증 막힘으로 KIND로 우회한 이력이 있다. 마스터 데이터를 자체 시드로 유지하는 것은 **운영 비용은 높고 매칭 품질은 낮다**.

반면 이미 검색 자동완성(`routers/stocks.py:_search_kr`)에서 사용 중인 **Naver 검색 API(`ac.stock.naver.com/ac`)는 약칭/부분일치/ETF를 모두 자연스럽게 처리**하며 외부 의존성이 이미 도입되어 있다.

→ **일괄 등록 매칭은 Naver API 단일 경로로 단일화하고, stocks 마스터 테이블·시드·repo를 모두 제거**한다. 결정 배경과 향후 재도입 가능성은 문서로만 남긴다.

## 목표

- 일괄 등록 preview의 종목명 매칭이 `ticker_hints → Naver 검색 API → None` 흐름으로 동작
- "현대차" → 005380, "TIGER 미국S&P500" → 360750 매칭됨
- `public.stocks` 테이블, `seed_stocks.py`, `stocks_repo.py` 등 마스터 관련 코드/스키마/시드가 모두 제거됨
- 제거 결정과 향후 재도입 옵션이 `docs/decisions.md`, `docs/backlog.md`에 기록됨
- 회귀: 기존 routers/stocks.py의 `/api/stocks/quote`, `/api/stocks/search`는 외부 API 사용이라 영향 없음 — 테스트 통과

## 설계

### 접근 방식

**현재 흐름** (`broker_import/ticker_resolver.py:11-38`):
```
ticker_hints → stocks 테이블 exact match → None
```

**개선 후**:
```
ticker_hints → Naver 검색 API (한국 종목, 정확도 가드) → None
```

**Naver API 재사용 전략**:
- `routers/stocks.py:49-83`의 `_search_kr` 함수를 `external/naver_search.py`로 추출
- `find_first_kr_match(q) -> {code, name, exchange} | None` helper 추가 (검색 결과 중 가드 통과한 첫 매칭)
- `ticker_resolver.py`가 새 helper를 사용해 미해결 이름들을 `asyncio.gather`로 병렬 조회
- `routers/stocks.py`도 새 helper 또는 `_search_kr` 추출본 사용 (응답 형식 동일 유지)

**한국 종목 필터**:
- Naver 응답 `typeCode`(KOSPI/KOSDAQ/KONEX/ETF/ETN 등)가 한국 거래소이면 채택
- 미국 등 해외 종목은 무시 (현재 `country_code='KR'` 정책 유지)

**매칭 정확도 가드 (오매칭 방지)**:
- Naver는 부분일치도 반환 → "삼성"이 "삼성전자"로 자동 매칭되면 잘못된 등록 발생 가능
- 가드: 검색결과 `name`이 입력 `asset_name`과 **정확일치** 또는 **입력이 결과명의 prefix/완전포함**일 때만 채택
  - 예: 입력 "현대차", 결과 "현대자동차" → 입력이 결과의 부분문자열이지만 단축형이라 채택해야 하는 케이스
  - 가드 규칙: `input == result.name` 또는 `input in result.name` 또는 `result.name.startswith(input)` (한글 단축어 허용)
  - 단, 너무 짧은 입력(1~2자)은 위험 → 입력 길이 ≥ 3 일 때만 부분일치 채택
- 정확도 가드를 통과 못 하는 경우 미해결 처리하여 사용자가 수동 등록하도록 유도

**stocks 마스터 제거 (핵심 결정)**:
- DB: `016_drop_stocks.sql` 마이그레이션으로 `public.stocks` 테이블 drop (014/015는 보존)
- 코드: `seed_stocks.py`, `stocks_repo.py` 삭제. `ticker_resolver.py`에서 stocks_repo import/호출 제거
- 테스트: stocks 마스터 의존 테스트 정리 (현재 `test_stocks.py`는 quote/search만 테스트 — 영향 없음)
- `routers/stocks.py`는 그대로 유지 (외부 API 호출만 함)
- `domain/trade_types.py`의 `DEFAULT_COUNTRY` 상수는 trades.ticker_symbol과 country 표기에 여전히 사용되므로 유지

**미해결 메시지 갱신**:
- `routers/trades.py:420`의 `f"ticker 미해결: {pt.asset_name} — 주식 마스터에 없음"` → "Naver 검색 결과 매칭 실패" 같이 새로운 흐름을 반영
- 프론트엔드 `PreviewStep.tsx:79`의 안내 문구도 함께 갱신 (마스터 추가 권유 → 종목명 확인 권유)

### 주요 변경 파일

**제거**:
- `supabase/migrations/016_drop_stocks.sql` (**신규** drop 마이그레이션)
- `api/scripts/seed_stocks.py` (**삭제**)
- `api/src/invest_note_api/db_ops/stocks_repo.py` (**삭제**)

**보존 (역사 기록)**:
- `supabase/migrations/014_create_kr_stocks.sql` — 보존
- `supabase/migrations/015_rename_kr_stocks_to_stocks.sql` — 보존
- `docs/spec-history/2026-04-28-stocks-master-i18n.md` — 보존

**수정**:
- `api/src/invest_note_api/external/naver_search.py` (**신규**) — `_search_kr` 추출 + `find_first_kr_match` helper
- `api/src/invest_note_api/routers/stocks.py` — 새 helper로 위임 (응답 형식 동일 유지)
- `api/src/invest_note_api/broker_import/ticker_resolver.py` — stocks_repo 의존 제거, Naver 단일 경로 + 정확도 가드 + asyncio.gather 병렬
- `api/src/invest_note_api/routers/trades.py:420` — 미해결 에러 메시지 갱신
- `api/tests/test_ticker_resolver.py` (**신규**) — Naver mocking으로 매칭/가드/실패 케이스
- `app/src/components/records/ImportTradesPanel/PreviewStep.tsx` — 미해결 안내 문구 갱신
- `docs/decisions.md` — "stocks 마스터 제거 + Naver API 단일화" 결정 기록 (맥락/결정/이유/트레이드오프)
- `docs/backlog.md` — "마스터 도입 재검토 (요건: ETF/약칭 데이터 소스 확보 시)" 항목 추가

### 재사용할 기존 자산

- `routers/stocks.py:49-83` `_search_kr` — Naver 호출 로직 그대로 추출
- `external/constants.py` — `NAVER_SEARCH_URL`, `HTTP_TIMEOUT_SECONDS`, `USER_AGENT`
- `domain/trade_types.py` — `DEFAULT_COUNTRY`, `MAX_CODE_LEN`, `MAX_NAME_LEN`
- 기존 import preview 흐름 — `routers/trades.py:386`의 `resolve_tickers()` 호출 시그니처 유지 (단, `conn` 파라미터는 더 이상 필요 없음 → 시그니처 단순화 가능)

## 구현 체크리스트

- [ ] `api/src/invest_note_api/external/naver_search.py` 신규 — `_search_kr` 추출 + `find_first_kr_match(q)` helper
- [ ] `api/src/invest_note_api/routers/stocks.py` — 새 helper로 위임 (테스트 mock 경로도 함께 갱신 고려)
- [ ] `api/src/invest_note_api/broker_import/ticker_resolver.py` — stocks_repo 의존 제거 + Naver 단일 경로 + 정확도 가드 + asyncio.gather 병렬
- [ ] `api/src/invest_note_api/routers/trades.py:420` — 미해결 에러 메시지 갱신
- [ ] `api/src/invest_note_api/db_ops/stocks_repo.py` 삭제
- [ ] `api/scripts/seed_stocks.py` 삭제
- [ ] `supabase/migrations/016_drop_stocks.sql` 신규 — `drop table if exists public.stocks`
- [ ] `app/src/components/records/ImportTradesPanel/PreviewStep.tsx:79` — 미해결 안내 문구 갱신
- [ ] `api/tests/test_ticker_resolver.py` 신규 — Naver mocking으로 매칭/가드/실패 케이스 단위 테스트
- [ ] `api/tests/test_stocks.py` 기존 테스트 회귀 확인 (mock 경로가 `_search_kr`인지 새 helper인지 — 변경 시 함께 수정)
- [ ] `docs/decisions.md` — 결정 기록 추가
- [ ] `docs/backlog.md` — "마스터 재도입" 장기 후보 기록
- [ ] `cd api && poetry run pytest -q` — 백엔드 테스트 통과
- [ ] `pnpm tsc` — 타입 체크 통과

## 우려사항 / 리스크

- **부분 일치 오매칭** ("삼성" → "삼성전자"): 이름 정확도 가드(완전일치 또는 입력이 결과명의 부분문자열, 입력 길이 ≥ 3)로 완화. 보수적으로 운영 후 사용자 피드백 따라 후속에 수동 매칭 UI 검토.
- **외부 API 단일 의존성**: Naver API 다운/응답 형식 변경 시 일괄 등록 전체가 영향받음. 다만 `/api/stocks/search`도 동일 의존성이라 추가 위험 없음. 5초 timeout으로 hang 방지.
- **stocks 마스터의 다른 잠재 사용처**: 현재 의존성 grep 결과 5곳(seed/repo/resolver/migration 2개)에 한정되며 trades 테이블도 FK 없음. 시세/검색은 외부 API 사용으로 영향 없음. 제거 후 회귀 테스트로 검증.
- **데이터 손실**: drop 마이그레이션은 비가역 — 단, 마스터는 KIND에서 재시드 가능한 외부 데이터일 뿐 사용자 데이터가 아니므로 손실 영향 없음.
- **레이턴시**: 미매칭 종목 N건당 N회 외부 호출. asyncio.gather 병렬 + 5초 timeout. 현실적 워크로드(월 수십~수백 건) 범위에서 허용 가능.

## 검증 방법

1. **단위 테스트**:
   ```bash
   cd api && poetry run pytest tests/test_ticker_resolver.py tests/test_stocks.py -q
   ```
   - "현대차" → mocked Naver({code:"005380", name:"현대자동차"}) → 매칭 성공 (입력이 결과명의 부분문자열)
   - "TIGER 미국S&P500" → mocked Naver({code:"360750", name:"TIGER 미국S&P500"}) → 정확일치 매칭
   - "삼성" → mocked Naver({code:"005930", name:"삼성전자"}) → 부분문자열이지만 입력 길이 < 3 가드로 미매칭
   - Naver 빈 응답 → 미해결
   - HTTP 예외 → 미해결 (기존 stocks.py와 동일한 try/except 흐름)

2. **전체 백엔드 회귀**:
   ```bash
   cd api && poetry run pytest -q
   ```

3. **DB 마이그레이션 dry-run**:
   - `016_drop_stocks.sql`이 idempotent (`drop table if exists`)임을 확인
   - 로컬 supabase에 적용 후 다른 스키마 의존성 깨짐 없는지 확인

4. **수동 E2E**:
   - 거래명세서 샘플에 "현대차" 또는 "TIGER 미국S&P500" 포함된 케이스로 import preview → unresolved_ticker_count = 0
   - commit 후 trades 테이블에 ticker_symbol과 함께 정상 저장
