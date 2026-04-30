# Spec: trades_repo patch 필드 메타데이터 통합

> 완료: 2026-04-30

## 배경 / 문제

`api/src/invest_note_api/db_ops/trades_repo.py`에는 trade 필드 속성을 표현하는 세 개의
독립 컬렉션이 같은 파일에 공존한다.

- `_PATCH_ALLOWED` (set, line 151): patch_trade()가 받아들이는 필드 화이트리스트 (11개)
- `PNL_AFFECTING_FIELDS` (set, line 157): 수정 시 PnL 재계산이 필요한 필드 (7개)
- `SELL_AUTO_DERIVED_FIELDS` (frozenset, line 169): SELL에서 자동 산출되어 patch가 무시되는 필드 (3개)

세 셋이 부분 겹침을 가진 채 손으로 관리되고 있어 새 필드 추가/속성 변경 시 한 곳만 빠뜨려도
조용히 동작이 어긋난다 (예: PnL 재계산 누락, SELL 자동 산출 누락). 백로그에 동일 이슈가
"drift 위험"으로 등록돼 있다.

## 목표

- 필드 속성을 단일 dict (`TRADE_FIELD_META: dict[str, TradeFieldMeta]`)로 통합한다.
- 외부 import 인터페이스(`PNL_AFFECTING_FIELDS`, `SELL_AUTO_DERIVED_FIELDS`,
  `strip_sell_auto_derived`, `patch_trade`)는 동작/시그니처 그대로 유지한다.
- 기존 테스트(`api/tests/test_trades.py:428-504`) 모두 통과한다.
- `pytest -q` 통과.

## 설계

### 접근 방식

1. `trades_repo.py`에 frozen dataclass `TradeFieldMeta(patchable, pnl_affecting, sell_auto_derived)`를
   정의하고, 모든 trade patch 관련 필드를 `TRADE_FIELD_META: dict[str, TradeFieldMeta]`로 단일화한다.
2. 기존 세 셋은 그 dict에서 파생 (frozenset comprehension)해 모듈 변수로 노출. 이름은 그대로 유지하여
   외부 import (`routers/trades.py`)에 영향 없음. 내부 전용이던 `_PATCH_ALLOWED`도 동일하게 dict 파생으로 변경.
3. `patch_trade`, `strip_sell_auto_derived`는 새 파생 셋을 참조하도록 한 줄 수정.
4. 메타 dict의 키 집합이 곧 patchable 필드 집합(`_PATCH_ALLOWED`)이 되도록, patchable=False
   항목은 dict에 넣지 않는다 → 기존 11개 그대로.

### 필드 매트릭스 (TRADE_FIELD_META)

| field          | patchable | pnl_affecting | sell_auto_derived |
| -------------- | --------- | ------------- | ----------------- |
| market_type    | ✓         |               |                   |
| price          | ✓         | ✓             |                   |
| quantity       | ✓         | ✓             |                   |
| commission     | ✓         | ✓             |                   |
| tax            | ✓         | ✓             |                   |
| strategy_type  | ✓         | ✓             |                   |
| emotion        | ✓         | ✓             | ✓                 |
| reasoning_tags | ✓         | ✓             | ✓                 |
| buy_reason     | ✓         |               |                   |
| sell_reason    | ✓         |               |                   |
| result         | ✓         |               | ✓                 |

→ 기존 세 셋의 멤버와 1:1 일치. 동작 변화 없음.

### 주요 변경 파일

- `api/src/invest_note_api/db_ops/trades_repo.py` — `TradeFieldMeta` dataclass + `TRADE_FIELD_META`
  dict 추가, 세 셋을 dict 파생으로 교체.

## 구현 체크리스트

- [x] `db_ops/trades_repo.py` — `TradeFieldMeta` dataclass + `TRADE_FIELD_META` dict 정의 후
      `_PATCH_ALLOWED`/`PNL_AFFECTING_FIELDS`/`SELL_AUTO_DERIVED_FIELDS`를 dict 파생 frozenset으로 교체
- [x] 회귀 테스트 — `tests/test_trades.py` 36 passed
- [x] 전체 백엔드 테스트 — `pytest -q` 233 passed
- [x] `docs/backlog.md` — "patch 필드 메타데이터 통합" 항목 제거

## 우려사항 / 리스크

- 외부에서 `_PATCH_ALLOWED`를 import하는 곳이 없는지 확인됨(grep: 정의 1곳 + 참조 1곳, 모두 동일 파일).
- 파생 frozenset이 module import 시점에 평가되므로 실행 시점 의존 문제 없음.
- 새 dataclass 도입은 의존성 추가 없음 (`from dataclasses import dataclass`만).
