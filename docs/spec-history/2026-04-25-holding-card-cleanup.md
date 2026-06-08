> 완료: 2026-04-25

# Spec: 홈 탭 보유 종목 카드 정리

## 배경 / 문제

홈 탭의 보유 종목 카드(`HoldingCard`)가 표시하는 정보를 사용자 의도에 맞춰 정리한다.

- 확정손익 라인은 보유 종목 카드 본 목적(현재 보유분 모니터링)과 무관해 시각 노이즈가 됨.
- 카드 하단 노트가 매수 거래 시 `buy_reason`을, 매도 거래 시 `reflection_note`/`sell_reason`을 섞어 가장 최근 항목으로 덮어쓰므로 표시가 일관되지 않음 — 매수 의사결정 근거를 빠르게 다시 확인하는 용도로 통일.
- 현재가에서 수익/손실 상태가 한눈에 보이지 않음 (현재는 평가금액 우측 미실현손익만 색상 표시 중).

## 목표

- 보유 종목 카드에 "확정손익" 행이 더 이상 표시되지 않는다.
- 카드 하단 노트는 가장 최근 BUY 거래의 `buy_reason`만 표시한다 (SELL 거래의 `reflection_note`/`sell_reason`은 카드에 노출되지 않음).
- 현재가 셀에 매수단가 대비 수익률/손실률(`%`)이 인라인으로 같이 표시되며, 색상이 손익 방향에 따라 적용된다 (수익=`--rise`, 손실=`--fall`).

## 설계

### 접근 방식

1. `Position` 타입에서 카드에서만 쓰이던 `realizedPnL`, `lastNoteType` 필드를 제거한다.
2. `buildPositions`에서 SELL 분기의 노트 추적(`reflection_note`/`sell_reason` → `lastNote`) 코드를 제거한다.
3. `HoldingCard.tsx`: 확정손익 행 삭제; 현재가 셀에 인라인 수익률+색상 추가; 노트 섹션 단순화.

### 주요 변경 파일

- `app/src/lib/portfolio.ts` — `Position`에서 `realizedPnL`, `lastNoteType` 제거; SELL 분기 노트 추적 제거
- `app/src/components/home/HoldingCard.tsx` — 확정손익 행 삭제; 현재가 셀 수익률 인라인 추가; 노트 섹션 단순화

## 구현 체크리스트

- [x] `Position` 타입에서 `realizedPnL`, `lastNoteType` 필드 제거 (`app/src/lib/portfolio.ts:7-24`)
- [x] `buildPositions` 내부 lot/posMap 타입에서 `realizedPnL`, `lastNoteType` 제거 및 관련 누적 코드 정리
- [x] SELL 분기에서 `reflection_note`/`sell_reason` → `lastNote` 갱신 로직 삭제
- [x] `HoldingCard`에서 `realizedPnL`/`lastNoteType` 분해·사용 제거
- [x] 확정손익 행 삭제
- [x] 현재가 셀에 수익률 인라인 표시 + 색상 (null/0 가드 포함)
- [x] 노트 섹션: 배지 라벨 "매수 근거"로 고정, `lastNote`만 조건으로 사용
- [x] `pnpm tsc --noEmit` 통과 확인

## 우려사항 / 리스크

- `avgBuyPrice === 0` 또는 `currentPrice === null`일 때 NaN/Infinity 가드 필요
- 색상 패턴은 기존 `text-[var(--rise)]` / `text-[var(--fall)]` 컨벤션 그대로 (다크모드 자동 호환)
