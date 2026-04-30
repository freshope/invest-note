# Spec: BE simplify Tier 2 — 헬퍼 추출 + dead code 제거

## 배경 / 문제

`/simplify be 전체 조사` Tier 2 항목 중 도메인 시그니처 변경이 없는 정리 작업을 마무리한다 (`docs/backlog.md` 참고). Tier 1(2026-04-30 완료)에 이어 백엔드 도메인의 작은 중복·미사용 코드를 정리해 가독성과 유지보수성을 개선한다.

조사 결과 현재 상태(파일·라인 기준):

- **dead code (4건)** — 프로덕션 caller가 없고 테스트에서만 호출됨
  - `db_ops/trades_repo.py:290 list_trades_in_range` — caller 0건
  - `domain/holdings.py:42 compute_lot_quantity` — `tests/test_holdings.py`에서만 호출
  - `domain/holdings.py:56 find_latest_buy_strategy` — `tests/test_holdings.py`에서만 호출
  - `domain/holdings.py:104 compute_flexible_holding_days` — `tests/test_holdings.py`에서만 호출
- **`to_kst_ms` 중복 (4건)** — `int(to_kst(dt).timestamp() * 1000)` 패턴
  - `domain/realized_pnl.py:146`, `domain/trade_walker.py:115`
  - `domain/holdings.py:107`, `domain/holdings.py:133` (둘 다 dead `compute_flexible_holding_days` 내부 → Step 1에서 함께 삭제)
- **`half_up_int` 중복 (3건)** — `math.floor(x + 0.5)` 패턴 (정수 HALF_UP 반올림)
  - `domain/realized_pnl.py:131`
  - `domain/holdings.py:126` (dead `compute_flexible_holding_days` 내부 → Step 1에서 함께 삭제)
  - `domain/analysis/rules.py:54 _round` (이미 private 헬퍼로 존재)
  - 별도: `domain/trade_import.py:23` Decimal `quantize(ROUND_HALF_UP)` — 의미가 다름(소수점 둘째 자리 반올림). **건드리지 않음**.
- **position key f-string 중복 (3건)** — `f"{ticker}:{country}"` 패턴
  - `domain/portfolio.py:150`, `domain/portfolio.py:243`, `domain/analysis/concentration.py:60`
  - 별도 shape: `db_ops/trades_repo.py:28` lock_key(4-튜플 `user:account:ticker:country`), `domain/portfolio.py:83 _lot_key_of`(3-튜플 `ticker:country:account`) — 의미·튜플 구성이 달라 **공통화 대상 아님**
- **`strip_comma_number` 미사용 (3건)** — `utils/numbers.py:6`에 헬퍼 존재하나 `external/quotes.py:50,66,67`에서 raw `.replace(",", "")` 사용

## 목표

- `domain/holdings.py`에서 production caller가 없는 함수 3개 + `db_ops/trades_repo.py:list_trades_in_range` 삭제. `tests/test_holdings.py`의 해당 테스트 클래스도 함께 삭제. 산 코드(`compute_holding_summary`, `compute_flexible_breakdown`) 테스트는 유지.
- `to_kst_ms(dt) -> int` 헬퍼를 `domain/trade_utils.py`에 추가, 잔존 2개 사이트 교체.
- `half_up_int(x: float) -> int` 헬퍼를 `utils/numbers.py`에 추가, 잔존 2개 사이트(`realized_pnl.py:131`, `analysis/rules.py:_round`) 교체.
- `position_key(ticker, country) -> str` 헬퍼를 `domain/trade_utils.py`에 추가, 3개 사이트(`portfolio.py` 2곳, `analysis/concentration.py` 1곳) 교체.
- `external/quotes.py`의 raw `.replace(",", "")` 3곳을 `strip_comma_number`로 교체.
- 외부 API 응답 동작·schema 동일. `cd api && poetry run pytest -q` 통과.

## 설계

### 접근 방식

5개 Step으로 분할, 각 Step 독립 commit. **dead code 제거를 가장 먼저 수행**해 후속 Step의 교체 대상 사이트 수를 줄이고 잘못된 사이트(이미 삭제된 함수 내부)를 만지는 것을 방지한다.

새 헬퍼는 기존 의미와 100% 일치하는 형태로만 추출한다 (시그니처·반환 타입·rounding 동작 동일). 의미가 다른 형태(Decimal HALF_UP, 4-튜플 lock_key, 3-튜플 lot_key)는 건드리지 않는다.

### 주요 변경 파일

- `api/src/invest_note_api/domain/holdings.py` — Step 1: 3개 함수 삭제
- `api/src/invest_note_api/db_ops/trades_repo.py` — Step 1: `list_trades_in_range` 삭제
- `api/tests/test_holdings.py` — Step 1: 3개 테스트 클래스 + 사용하지 않게 된 import 삭제
- `api/src/invest_note_api/domain/trade_utils.py` — Step 2: `to_kst_ms` 신규, Step 4: `position_key` 신규
- `api/src/invest_note_api/domain/realized_pnl.py` — Step 2: `to_kst_ms` 사용, Step 3: `half_up_int` 사용
- `api/src/invest_note_api/domain/trade_walker.py` — Step 2: `to_kst_ms` 사용
- `api/src/invest_note_api/utils/numbers.py` — Step 3: `half_up_int` 신규
- `api/src/invest_note_api/domain/analysis/rules.py` — Step 3: 기존 private `_round` 제거 후 공유 헬퍼 사용
- `api/src/invest_note_api/domain/portfolio.py` — Step 4: `position_key` 사용 (2곳)
- `api/src/invest_note_api/domain/analysis/concentration.py` — Step 4: `position_key` 사용
- `api/src/invest_note_api/external/quotes.py` — Step 5: `strip_comma_number` import 후 3곳 교체

### 재사용 함수

- `api/src/invest_note_api/utils/numbers.py:6 strip_comma_number` — Step 5에서 사용
- `api/src/invest_note_api/domain/trade_utils.py:11 to_kst` — `to_kst_ms`가 내부에서 호출
- `api/src/invest_note_api/domain/trade_utils.py:MS_PER_DAY` — `half_up_int` 사용처(realized_pnl.py)에서 동일 의미 유지

## 구현 체크리스트

- [ ] Step 1 — `db_ops/trades_repo.py`에서 `list_trades_in_range` 삭제
- [ ] Step 1 — `domain/holdings.py`에서 `compute_lot_quantity`, `find_latest_buy_strategy`, `compute_flexible_holding_days` 삭제. 사용하지 않게 된 import (`math`, `MS_PER_DAY`, `to_kst`, `trade_to_group_key`) 정리. **`is_same_group`은 살아 있는 `compute_holding_summary`에서 계속 사용하므로 유지**.
- [ ] Step 1 — `tests/test_holdings.py`에서 `TestComputeLotQuantity`, `TestComputeFlexibleHoldingDays`, `TestFindLatestBuyStrategy` 클래스 + 해당 import 제거
- [ ] Step 1 — `cd api && poetry run pytest -q` 통과 + commit
- [ ] Step 2 — `domain/trade_utils.py`에 `to_kst_ms(dt: datetime) -> int` 추가
- [ ] Step 2 — `domain/realized_pnl.py:146`, `domain/trade_walker.py:115`에서 `to_kst_ms` 사용
- [ ] Step 2 — `cd api && poetry run pytest -q` 통과 + commit
- [ ] Step 3 — `utils/numbers.py`에 `half_up_int(x: float) -> int` 추가
- [ ] Step 3 — `domain/realized_pnl.py:131` 인라인 표현 교체
- [ ] Step 3 — `domain/analysis/rules.py`의 private `_round` 제거하고 호출부 모두 `half_up_int`로 교체
- [ ] Step 3 — `cd api && poetry run pytest -q` 통과 + commit
- [ ] Step 4 — `domain/trade_utils.py`에 `position_key(ticker: str | None, country: str) -> str` 추가
- [ ] Step 4 — `domain/portfolio.py:150,243`, `domain/analysis/concentration.py:60`에서 `position_key` 사용
- [ ] Step 4 — `cd api && poetry run pytest -q` 통과 + commit
- [ ] Step 5 — `external/quotes.py`에 `strip_comma_number` import 추가, 3곳(line 50/66/67) 교체. **`str(...)` 래핑 제거하고 `strip_comma_number(item.get("closePrice"))` 형태로 직접 호출** — `strip_comma_number`는 None/숫자를 그대로 통과시키므로 후속 `float(raw)` 변환과 호환되고, 기존 `str(None)` → `"None"` 잠재 버그를 자연스럽게 회피
- [ ] Step 5 — `cd api && poetry run pytest -q` 통과 (특히 `tests/test_quotes.py`) + commit
- [ ] spec-current → spec-history 이동, backlog 항목 제거

## 검증 방법

각 Step 후:

```bash
cd api && poetry run pytest -q
```

전체 통과 + warning 증가 없음 확인. 회귀 테스트 추가는 불필요(기존 테스트가 동작 동등성 검증).

dead code 제거 후 grep으로 잔존 참조 0건 재확인:

```bash
cd api && grep -rn "compute_lot_quantity\|find_latest_buy_strategy\|compute_flexible_holding_days\|list_trades_in_range" src/ tests/
```

Step 5 후 `external/quotes.py`에 raw `.replace(",", "")` 잔존 0건 확인:

```bash
cd api && grep -n 'replace(",", ""' src/invest_note_api/external/quotes.py
```

## 우려사항 / 리스크

- **dead code 테스트 함께 삭제**: 외부에서 import해 사용하는 곳이 없음을 grep으로 확인했으므로 안전. 만약 향후 동일 로직이 필요해지면 `compute_holding_summary`(보유수량+WAC를 한 순회로 계산)가 상위 호환이므로 그것을 사용하면 됨.
- **`strip_comma_number` 의미 차이**: 기존 `str(item.get("closePrice", "")).replace(",", "")`는 항상 str 반환. `strip_comma_number(item.get("closePrice"))`는 입력이 str이면 쉼표 제거 + strip한 str을, 그 외(None/int/float)는 그대로 통과. 후속 `float(raw)`는 int/str 모두 처리 가능하므로 1:1 동작 동일. 단 기존 코드의 `str(None)` → `"None"` 케이스(falsy 단축평가에서만 발생 가능)는 신규 헬퍼에서 None 통과로 처리되어 더 안전.
- **`half_up_int` 위치 선택**: `utils/numbers.py`(import 부담 작음) vs `domain/trade_utils.py`(rounding이 시간 도메인에 종속). `_round`가 `analysis/rules.py`에서 일반 비율 round에도 쓰이므로 도메인 중립적 위치인 `utils/numbers.py`가 적합.
- **`position_key`가 만드는 키 형태**: 기존 인라인 `f"{lot['ticker']}:{lot['country']}"`와 정확히 같은 문자열 출력해야 함. dict lookup 키로 쓰이는 사이트들이라 한 글자라도 다르면 silent breakage. 헬퍼 구현 시 `f"{ticker}:{country}"` 그대로 유지.
