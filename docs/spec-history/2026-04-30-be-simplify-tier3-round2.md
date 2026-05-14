> 완료: 2026-04-30

# Spec: BE simplify Tier 3 Round 2

브랜치: `feature/be-simplify-tier3-round2`

## 배경 / 문제

BE simplify Tier 3 Round 1 (4 개 항목 A/B/C/D) 이 develop 에 머지된 뒤,
backlog 의 "BE simplify Tier 3 (Round 2 이후 deferred)" 섹션에 5 개 항목(E~I) 이 남아 있다.
탐색 결과 5 개 모두 동일하게 진행할 가치가 있는 것은 아니다 — 일부는 도메인 의미상
통합 비권장이고, 일부는 범위가 커서 별도 라운드로 나누는 것이 안전하다.
이번 Round 2 에서는 (a) 통합하지 않을 항목을 결정 기록으로 정리하고
(b) 위험 낮은 두 개 (G, I) 만 묶어 진행한다. H 는 Round 3 별도 spec.

## 목표

- E, F 를 "통합 미진행" 결정으로 `docs/decisions.md` 에 기록하고
  `docs/backlog.md` Tier 3 섹션에서 해당 두 줄 제거
- F 는 코드 동작 변경 없이 호출지점 docstring/주석만 명확화 (의도 차이 명시)
- G: `domain/portfolio.py` 의 `Lot` (현재 `dict[str, dict]` LotMap) 을
  Position 패턴을 따르는 frozen dataclass 로 교체. `build_account_snapshots`
  의 lot dict 접근도 attribute 접근으로 동기 변경.
- I: `_PREVIEW_ACCT = "__preview__"` placeholder 제거.
  `domain/trade_import.py` 에 신규 `PreviewSignature` frozen dataclass 추가하고
  preview 경로는 `make_preview_signature` / `trade_to_preview_signature` 로 분리.
  commit 경로는 기존 `make_signature` / `trade_to_signature` 유지.
- 모든 변경 후 `cd api && poetry run pytest -q` 통과.

## 설계

### 접근 방식

각 항목을 독립 커밋으로 분리해 review · revert 용이성 확보 (Round 1 패턴 준수).
시맨틱 변경은 없고 코드 조직과 타입 명확성을 개선한다.

H (모듈 글로벌 상태 → `app.state`) 는 의존성 주입 패턴 도입 + 라우터 시그니처
변경 + 테스트 픽스처 재구성이 필요해 회귀 위험이 G/I 합산보다 크다. Round 2 와
묶으면 commit 단위 롤백이 어려워지므로 본 Round 직후 Round 3 별도 spec 으로 분리.

### 항목별 변경 파일

**E0/F0. Round 2 결정 기록 + backlog 정리**
- `docs/decisions.md` (append): "2026-04-30 | aggregate.py 3 bucket loop 통합 미진행 / build_strategy_evaluations 호출 통합 미진행 — 도메인 의미 차이가 코드 라인 절감 가치를 상회"
- `docs/backlog.md` Tier 3 섹션에서 E, F 두 줄 제거 (G, H, I 만 남김)

**F1. `build_strategy_evaluations` 호출 의도 docstring/주석 명확화**
- `api/src/invest_note_api/domain/analysis/aggregate.py:99` 위에 주석:
  "trades = period-filtered. 기간별 strat_map/adherence_map snapshot 용"
- `api/src/invest_note_api/routers/analysis.py:94` 위에 주석:
  "all_trades = 전체. compute_profile 의 장기 일관성 평가용"
- `build_strategy_evaluations` docstring 에 "입력 trades 범위는 호출지점 의도에 따라 다르며 period 필터링 여부는 호출자 책임" 명시
- 코드 동작 변경 없음

**G1. `Lot` frozen dataclass 화 + 호출지 동기 변경**
- `api/src/invest_note_api/domain/portfolio.py:39` `LotMap = dict[str, dict]` → `LotMap = dict[str, Lot]`
- 신규 `@dataclass(frozen=True) class Lot` 정의 (필드: ticker, country, asset_name,
  account_id, exchange, running_qty, running_cost, realized_pnl, last_traded_at,
  last_note_type, last_note)
- `build_positions` (L101-142): 루프 내 가변 누산은 로컬 변수로 유지, walk 종료 시점에
  `Lot(...)` 1 회 생성 후 `lot_map[lot_key] = lot` 등록
  (frozen 위반 회피, dataclasses.replace 불필요)
- `build_positions` 의 lot_map.values() 소비 (L147-176): dict 접근 → attribute 접근
- `build_account_snapshots` (L223-255): `lot["running_qty"]` 등 dict 접근 → attribute 접근
- 외부 노출 없음 (`grep -rn "LotMap\|lot_map" api/src` → portfolio.py 한정 확인)

**I1. `PreviewSignature` 분리 + `_PREVIEW_ACCT` 제거**
- `api/src/invest_note_api/domain/trade_import.py`:
  - 신규 `@dataclass(frozen=True) class PreviewSignature` (account_id 제거,
    trade_date / identifier / trade_type / quantity / price 만 포함)
  - 신규 `make_preview_signature(...)` (account_id 인자 없음)
  - 신규 `trade_to_preview_signature(trade)` (account_id 인자 없음)
  - 기존 `TradeSignature` / `make_signature` / `trade_to_signature` 는 그대로 유지 (commit 경로용)
- `api/src/invest_note_api/routers/trades.py`:
  - L45 import 에 `make_preview_signature`, `trade_to_preview_signature` 추가
  - L345 `_PREVIEW_ACCT = "__preview__"` 삭제
  - L346 `trade_to_signature(t, _PREVIEW_ACCT)` → `trade_to_preview_signature(t)`
  - L378-386 `make_signature(account_id=_PREVIEW_ACCT, ...)` → `make_preview_signature(...)`
  - L470, L481 (commit 경로) 변경 없음
- 신규 테스트: `tests/test_trade_import_domain.py` 에 PreviewSignature 가
  account_id 무관하게 동등성 보장하는 case 1 개 추가 (선택)

## 구현 체크리스트

- [x] `docs/decisions.md` 에 E/F 통합 미진행 결정 기록 + `docs/backlog.md` E, F 두 줄 제거
- [x] `aggregate.py` / `analysis.py` 에 `build_strategy_evaluations` 호출 의도 주석 + docstring 보강 (F1)
- [x] `domain/portfolio.py` `Lot` frozen dataclass 추가 + `build_positions` walk 종료 시점에 1 회 생성 패턴으로 변경 (G1-1)
- [x] `build_account_snapshots` 의 lot dict 접근 → attribute 접근 (G1-2)
- [x] `domain/trade_import.py` `PreviewSignature` / `make_preview_signature` / `trade_to_preview_signature` 추가 (I1-1)
- [x] `routers/trades.py` import / preview 경로를 `make_preview_signature` 로 전환하고 `_PREVIEW_ACCT` 삭제 (I1-2)
- [x] `cd api && poetry run pytest -q` 전체 그린 확인
- [x] 항목별 독립 커밋 (`docs:` / `refactor(analysis):` / `refactor(portfolio):` / `refactor(trade_import):`)

## 검증

| 항목 | 명령 |
|---|---|
| G | `cd api && poetry run pytest -q tests/test_portfolio.py tests/test_portfolio_logic.py tests/test_holdings.py tests/test_realized_pnl.py` |
| I | `cd api && poetry run pytest -q tests/test_trade_import_domain.py tests/test_trades.py` |
| F | `cd api && poetry run pytest -q tests/test_analysis.py tests/test_analysis_logic.py` (no-op 회귀) |
| 전체 | `cd api && poetry run pytest -q` (각 commit 직전 그린 확인) |

## 우려사항 / 리스크

- **G**: walk_trades 루프 동안 `Lot` 인스턴스를 매 step 재생성하면 비용 증가 → walk 종료
  시점에 1 회 생성하는 패턴 강제. 누산 로컬 변수 분리 누락 시 `AttributeError` 또는
  `dataclasses.FrozenInstanceError` 발생. 기존 `test_portfolio.py` 가 lot_map 소비 경로
  (`build_account_snapshots`) 까지 커버하므로 그린 = 회귀 없음으로 간주.
- **I**: 기존 `trade_to_signature` / `make_signature` 는 commit 경로 (L470, L481) 에서
  계속 쓰이므로 함수 시그니처 변경 금지. 신규 함수 추가만 허용.
  `grep -rn "trade_to_signature\|make_signature" api/src api/tests` 로 호출지점 전수
  조사 결과 commit 경로 외 외부 사용 없음 확인됨.
- **F**: 단순 주석/docstring 추가라 회귀 없음.
- **공통**: 각 커밋이 독립적으로 revert 가능.

## 참고 (Round 3 — 별도 spec 예정)

- **H. 모듈 글로벌 상태 → `app.state`**:
  `external/quotes.py` 의 `_cache` / `_cache_lock` / `_inflight`,
  `routers/trades.py` 의 `_STAGING` 을 `Depends(get_quote_cache)` 등 의존성 주입
  패턴으로 이전. 라우터 시그니처 변경 (3 개 라우터) + `tests/test_quotes.py` 픽스처
  재구성 + 테스트 직접 주입 코드 (`test_trades.py:400`) 정리. 멀티 워커 배포 대비
  의의 있으나 현재 단일 워커 가정이라 즉시 위험은 낮음. 본 Round 직후 별도 spec.
