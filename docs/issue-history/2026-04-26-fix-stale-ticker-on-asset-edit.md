# Spec: 자동완성 후 종목명 수정 시 stale ticker 초기화

> Completed: 2026-04-26

## Background / Problem

거래 등록 폼에서 자동완성 또는 보유종목 선택 후 종목명을 수동 수정하면 이전 `ticker_symbol`, `country_code`, `exchange`가 남아 잘못된 종목 그룹으로 저장될 수 있다.

## Goals

- BUY 자동완성 선택 후 종목명을 직접 바꾸면 ticker 관련 필드를 초기화한다.
- SELL 보유종목 선택 후 종목명을 직접 바꿔도 동일하게 ticker 관련 필드를 초기화한다.
- 자동완성/보유종목을 다시 선택하면 ticker 관련 필드가 정상적으로 다시 채워진다.

## Design

### Approach

선택된 종목명을 `TradeBasicForm`에서 추적하고, 사용자가 입력한 종목명이 선택된 이름과 달라지는 순간 `ticker_symbol`, `country_code`, `exchange`를 초기화한다. `HoldingSelectInput`은 수동 입력을 부모 form에 전달하도록 `onChange` prop을 추가한다.

### Primary Files

- `app/src/components/records/TradeBasicForm.tsx` - 선택 종목명 추적 및 ticker 초기화 정책 적용
- `app/src/components/records/HoldingSelectInput.tsx` - SELL 수동 입력을 부모 form에 동기화
- `app/src/components/records/__tests__/TradeBasicForm.test.tsx` - BUY/SELL 회귀 테스트 추가

## Implementation Checklist

- [x] `TradeBasicForm`에서 선택 종목명과 수동 입력 변경을 구분해 ticker 관련 필드 초기화
- [x] `HoldingSelectInput`에 `onChange`를 추가해 SELL 입력을 form 값과 동기화
- [x] BUY/SELL 수동 수정 회귀 테스트 추가
- [x] Type check passes (`pnpm tsc --noEmit`)

## Risks / Open Questions

- `TradeBasicForm`은 여러 provider와 API mock이 필요한 client component라 테스트 mock 범위를 최소화한다.
