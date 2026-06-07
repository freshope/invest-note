# Spec: StrategyEmotionFields Controller 중첩 수정

> Completed: 2026-04-26

## Background / Problem

매수 메타 입력 폼에서 `strategy_type` Controller 안에 `emotion` Controller가 중첩되어 있다. 두 필드는 독립적인 폼 필드이므로 sibling Controller로 배치해 렌더 구조와 유지보수성을 개선한다.

## Goals

- `strategy_type`과 `emotion` Controller를 같은 렌더 레벨에 배치한다.
- 기존 전략/감정 선택 및 재클릭 해제 동작을 유지한다.
- 저장 payload의 `strategy_type`, `emotion` 형태를 변경하지 않는다.
- 타입 체크가 통과한다.

## Design

### Approach

`TradeMetaBuyForm`에서 두 Controller를 sibling으로 선언하고, 각 Controller의 현재 값과 change handler를 `StrategyEmotionFields`에 전달한다. `StrategyEmotionFields`에는 기존 `hideStrategy`와 대칭되는 `hideEmotion` 옵션만 추가한다.

### Primary Files

- `app/src/components/records/TradeMetaBuyForm.tsx` - 중첩 Controller를 sibling Controller 배치로 변경
- `app/src/components/records/StrategyEmotionFields.tsx` - 전략만 렌더링할 수 있도록 `hideEmotion` 옵션 추가

## Implementation Checklist

- [x] `TradeMetaBuyForm`의 `strategy_type`/`emotion` Controller 중첩 제거
- [x] Type check passes (`pnpm tsc --noEmit`)

## Risks / Open Questions

- None
