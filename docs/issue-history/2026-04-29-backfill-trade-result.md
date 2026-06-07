# Spec: trades.result legacy NULL 백필

> 완료: 2026-04-29

## 배경 / 문제

`trades.result` 컬럼은 nullable·default 없음으로 정의되어 있어, SOT 통합 커밋 이전에 생성된 SELL row는 `result`가 NULL 상태로 잔존한다. 이로 인해 dual-truth가 발생한다:

- 분석 API (`aggregate.py`)는 NULL row를 win-rate 계산에서 **제외**한다 (`api/src/invest_note_api/domain/analysis/aggregate.py:85`).
- Trade Summary API (`/{trade_id}/summary`)는 `sell.result or derive_result_from_pnl(breakdown.pnl)` 형태로 NULL을 PnL 부호로 **fallback** 채워 응답한다 (`api/src/invest_note_api/routers/trades.py:246`).

→ 같은 SELL이 분석 탭에서는 win-rate에서 빠지고 거래 상세에서는 SUCCESS/FAIL로 표시되는 모순 발생.

## 목표

- `result IS NULL AND profit_loss IS NOT NULL` 인 SELL row를 PnL 부호 기반(`derive_result_from_pnl`과 동일 규칙)으로 일괄 백필하는 마이그레이션이 적용된다.
- `routers/trades.py`의 `derive_result_from_pnl` fallback 호출이 제거되고, summary 응답은 DB에 저장된 `result` 값을 그대로 사용한다.
- 백필 후 분석 탭과 거래 상세의 result 표기가 일치(single source of truth)한다.
- 기존 백엔드 테스트 통과.

## 설계

### 접근 방식

1. **신규 마이그레이션** `017_backfill_sell_result_from_pnl.sql`
   - 단일 `UPDATE trades` 문
   - 조건: `trade_type = 'SELL' AND result IS NULL AND profit_loss IS NOT NULL`
   - 값: `CASE WHEN profit_loss > 0 THEN 'SUCCESS' WHEN profit_loss < 0 THEN 'FAIL' ELSE 'BREAKEVEN' END::trade_result`
   - 규칙은 `domain/realized_pnl.py:84-89`의 `derive_result_from_pnl`과 동일.

2. **fallback 제거** — `api/src/invest_note_api/routers/trades.py:245-246`
   - `"result": sell.result or derive_result_from_pnl(breakdown.pnl),` → `"result": sell.result,`
   - 관련 주석 삭제.
   - `derive_result_from_pnl` 함수 자체는 `compute_group_pnl()` (realized_pnl.py:182) 등에서 계속 사용되므로 보존. import는 다른 사용처가 없으면 제거.

### 주요 변경 파일

- `supabase/migrations/017_backfill_sell_result_from_pnl.sql` — 신규 (UPDATE 문)
- `api/src/invest_note_api/routers/trades.py` — fallback 제거 (L245-246), 미사용 import 정리

## 구현 체크리스트

- [x] `supabase/migrations/017_backfill_sell_result_from_pnl.sql` 생성
- [x] `api/src/invest_note_api/routers/trades.py` fallback 제거 및 미사용 import 정리
- [x] 백엔드 테스트 통과 확인 (`cd api && poetry run pytest -q`)
- [x] `docs/backlog.md` 해당 항목 제거 (spec-finish 시점)

## 우려사항 / 리스크

- `profit_loss=NULL` 잔존 row는 백필 대상 외. fallback 제거 후 분석/요약 양쪽 모두 NULL로 일관 처리되어 dual-truth 해소.
- supabase 마이그레이션 적용은 기존 절차(`supabase db push` 등)와 동일.
- 마이그레이션은 idempotent (`IS NULL` 조건으로 재실행 안전).
