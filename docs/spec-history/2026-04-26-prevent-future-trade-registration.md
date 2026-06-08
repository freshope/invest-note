# Spec: 미래 거래 등록 차단

> Completed: 2026-04-26

## Background / Problem

분석 기간 필터는 "all"에서도 현재 시점 이후 거래를 제외한다. 이 동작은 유지하되, 사용자가 미래 거래를 등록할 수 있으면 분석 결과와 기록 목록 사이에 혼란이 생길 수 있으므로 신규 등록 단계에서 미래 거래를 차단한다.

## Goals

- 신규 거래 등록 폼에서 미래 날짜를 선택하거나 제출할 수 없다.
- FastAPI POST `/api/trades`가 미래 `traded_at` 요청을 거절한다.
- 분석 기간 필터의 `now` 상한 동작은 변경하지 않는다.

## Design

### Approach

프론트는 캘린더와 zod 스키마에서 미래 날짜를 사전 차단한다. 서버는 `TradeCreate`의 `traded_at` 파싱 직후 UTC 현재 시각과 비교해 우회 요청을 400으로 거절한다. `TradeUpdate`는 날짜 수정 필드가 없으므로 변경하지 않는다.

### Primary Files

- `app/src/components/records/TradeBasicForm.tsx` - 미래 날짜 선택/제출 차단
- `api/src/invest_note_api/schemas/trade.py` - 미래 `traded_at` 검증 추가
- `api/tests/test_trades.py` - 미래 거래 등록 거절 테스트
- `docs/backlog.md` - 분석 필터 명시화 이슈 문구 정리

## Implementation Checklist

- [x] `TradeBasicForm` 캘린더와 zod 검증에서 미래 날짜 차단
- [x] `TradeCreate` 서버 검증에서 미래 `traded_at` 차단
- [x] API 테스트 추가
- [x] 백로그 문구를 필터 동작 유지 기준으로 정리
- [x] Type check passes (`pnpm -C app exec tsc --noEmit`)
- [x] API tests pass (`cd api && poetry run pytest -q`)

## Risks / Open Questions

- 기존 DB나 향후 CSV 임포트로 유입된 미래 거래는 이번 작업 범위에서 수정하지 않는다.
