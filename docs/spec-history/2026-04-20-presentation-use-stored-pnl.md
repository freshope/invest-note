> 완료: 2026-04-20

# Spec: 프리젠테이션 계층에서 저장된 손익/평단가 사용

**브랜치**: `feature/presentation-use-stored-pnl` (develop 기반)

## 배경 / 문제

`feature/persist-realized-pnl` 이후 `trades` 테이블 SELL 행에 `profit_loss`와 `avg_buy_price`가 저장되고 거래 등록/수정/삭제 시 `recalcGroupPnL`이 항상 갱신한다(정합성 보장). 그러나 프리젠테이션 계층은 여전히 `buildPnlMap`, `buildPositions`, `computeFlexibleBreakdown`에서 WAC를 매번 재계산하거나 fallback 분기를 유지하고 있다. 저장값을 직접 사용해 중복 연산과 fallback 경로를 제거한다(`docs/backlog.md:30-32` 후속 작업).

## 목표

- `buildPnlMap`이 저장된 `profit_loss`만 반환하고 WAC fallback을 호출하지 않는다.
- `buildPositions`의 SELL 처리에서 `trade.avg_buy_price` 저장값을 사용하고 `sellPnL` fallback을 사용하지 않는다.
- 거래 상세 패널의 "거래 결과 (자동 계산)" 카드가 `computeFlexibleBreakdown`의 WAC 루프 없이 저장값으로 즉시 렌더된다.
- 홈/분석/종목상세/거래상세 수치가 변경 전과 동일하게 표시된다.
- 타입 체크·유닛 테스트 통과.

## 설계

### 접근 방식

저장값 정합성이 보장된다는 전제(사용자 확인) 아래, 프리젠테이션 읽기 경로의 fallback을 모두 제거하고 저장된 컬럼을 그대로 사용한다. 쓰기 경로(`computeGroupPnL`, `recalcGroupPnL`, `validateMutation`)는 변경하지 않는다. 오픈 포지션 평단가(미매도 보유분)와 FIFO 보유일수는 저장 대응이 없으므로 현 로직 유지.

### 주요 변경 파일

- `src/lib/analysis/realized-pnl.ts` — `buildPnlMap` fallback/`needsFallback` 제거, `getPnL` 단순화, `computeRealizedPnL`에 "테스트/디버깅용" 주석
- `src/lib/portfolio.ts` — `buildPositions` SELL 분기에서 `trade.avg_buy_price` 사용, `sellPnL` import 제거
- `src/lib/holdings.ts` — `computeFlexibleBreakdown` 재작성(allTrades 인자 제거, 저장값으로 `SellBreakdown` 구성)
- `src/app/api/trades/[id]/summary/route.ts` — `computeFlexibleBreakdown(sell)` 호출로 축소
- `src/lib/analysis/__tests__/analysis.test.ts` — `buildPnlMap` 저장값 반환 테스트 추가
- `src/lib/__tests__/holdings.test.ts` (신규) — `computeFlexibleBreakdown` 저장값 테스트
- `docs/backlog.md` — 해당 후속 항목 체크/제거

## 구현 체크리스트

- [x] `src/lib/analysis/realized-pnl.ts`: `buildPnlMap` fallback 제거 + `getPnL` 단순화
- [x] `src/lib/portfolio.ts`: `buildPositions` SELL 분기 저장값 사용 + `sellPnL` import 제거
- [x] `src/lib/holdings.ts`: `computeFlexibleBreakdown` 재작성 (allTrades 인자 제거)
- [x] `src/app/api/trades/[id]/summary/route.ts`: `computeFlexibleBreakdown` 호출부 정리
- [x] `src/lib/analysis/__tests__/analysis.test.ts`: `buildPnlMap` 저장값 테스트 추가
- [x] `src/lib/__tests__/holdings.test.ts`: `computeFlexibleBreakdown` 저장값 테스트 신설
- [x] `docs/backlog.md`: `buildPositions avg_buy_price 우선 사용` / `computeFlexibleBreakdown avg_buy_price 반영` 항목 정리
- [x] 타입 체크 통과 (`pnpm tsc --noEmit`)
- [x] 유닛 테스트 통과 (`pnpm test`)
- [x] 수동 검증: 홈 / 기록 / 거래 상세(SELL) / 종목 상세 / 분석 요약의 손익·평단 표시가 이전과 동일

## 우려사항 / 리스크

- **legacy null 데이터**: 백필 미완료 SELL 행이 있으면 저장값이 null → 평단/손익이 0으로 표시됨. 사용자가 정합성을 확인한 상태라 fallback은 제거하되, 첫 수동 검증에서 0원 표시 SELL 존재 여부를 중점 점검.
- **matched_qty 불일치 가능성**: 과거 oversell legacy 데이터는 저장 `profit_loss`가 `matched_qty < sell.quantity`로 계산됨. 새 `computeFlexibleBreakdown`은 `sell.quantity` 기준으로 `sellAmount/costBasis`를 표시 → 총액이 `profit_loss`와 산술적으로 맞지 않을 수 있음. 신규 등록은 oversell이 차단되어 문제없음. legacy 존재 시 후속 cleanup 작업으로 처리.
- **오픈 포지션 평단**: 미매도 보유분 평단은 여전히 `buildPositions` 내부 running WAC로 계산. 본 작업 범위 아님.
