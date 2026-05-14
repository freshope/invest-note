# Spec: 자유 텍스트 5000자 제한

> Completed: 2026-04-26

## Background / Problem

거래 메타 자유 텍스트 필드에는 현재 길이 제한이 없어 과도한 입력이 API/DB에 그대로 저장될 수 있다. 백로그의 제한 요구를 API validation, DB CHECK, 프론트 UX에 동일하게 반영한다.

## Goals

- `buy_reason`, `sell_reason`, `reflection_note`, `improvement_note`를 5000자로 제한한다.
- 각 입력에 작은 보조 톤의 `현재글자수/5000` 카운터를 표시한다.
- 90% 이상 입력 시 카운터를 경고색으로 표시한다.
- API 테스트와 프론트 타입 체크가 통과한다.

## Design

### Approach

프론트 제한값은 `VALIDATION_LIMITS`에 추가하고 관련 zod schema, `Textarea maxLength`, 카운터 표시가 모두 같은 상수를 사용한다. API는 Pydantic `TradeUpdate`에서 같은 제한을 검증한다. DB는 신규 마이그레이션에서 기존 초과 데이터를 5000자로 정리한 뒤 CHECK 제약을 추가한다.

### Primary Files

- `api/src/invest_note_api/schemas/trade.py` - 자유 텍스트 PATCH validation 추가
- `supabase/migrations/010_add_trade_free_text_length_checks.sql` - DB CHECK 제약 추가
- `app/src/components/records/*` - 자유 텍스트 카운터와 프론트 validation 적용

## Implementation Checklist

- [x] API validation 및 테스트 추가
- [x] DB CHECK migration 추가
- [x] 프론트 상수, schema, maxLength, 카운터 UI 추가
- [x] Type check passes (`pnpm -C app exec tsc --noEmit`)
- [x] API test passes (`cd api && poetry run pytest tests/test_trades.py -q`)

## Risks / Open Questions

- 기존 DB에 5000자 초과 데이터가 있으면 migration에서 5000자로 잘린다.
