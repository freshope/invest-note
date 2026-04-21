# Spec: 거래 수정 페이지 개선 — 상세 페이지와 통일성

## 배경 / 문제

2026-04-21 릴리즈에서 `TradeDetail`(`src/components/records/TradeDetail.tsx`) 레이아웃이 크게 개선됐다 (종목 헤더 카드 · 총액 prominence · 2열 compact meta grid · `시장·국내·KOSPI` 조합 표기). 그러나 상세에서 "수정" 버튼으로 열리는 `TradeEditPanel`(`src/components/records/TradeEditPanel.tsx`)은 이전 UI 그대로라, 동일 거래에 대해 상세→수정으로 넘어가는 순간 시각 언어가 완전히 달라진다.

## 목표

- 수정 패널 상단이 상세 페이지와 동일한 **종목 헤더 카드**(색 strip + 종목명 + 매수/매도 pill + ticker + 국내/해외 뱃지 + 총액 + `price × quantity` 줄)로 시작한다.
- 헤더 카드의 총액은 `가격`·`수량` 입력값에 **실시간 반응**한다.
- 별도 `거래 유형` 필드는 제거되고 헤더 카드의 매수/매도 pill로 흡수된다.
- 날짜 · 계좌 · 시장(`주식·국내·KOSPI` 형태) 세 항목이 2열 compact grid 카드로 표시된다 (현재 수정 패널에 없는 `시장` 항목도 노출).
- 가격/수량/수수료/제세금 입력 필드와 저장 동작은 기능적으로 이전과 동일.

## 설계

### 접근 방식

1. `TradeDetail`에서 private으로 정의된 표시 로직을 공용 모듈로 분리:
   - `src/components/records/trade-display.tsx` (신규) — `MARKET_LABELS`, `buildMarketDisplay(trade)`, `CompactRow`, `CountryBadge` export.
   - `TradeDetail`이 이 모듈을 import하도록 교체 (중복 제거 + 단일 소스).
2. `TradeEditPanel` 재구성 — 아래 순서로 상단부 교체:
   1. **종목 헤더 카드** — `TradeDetail`과 동일 마크업. 총액·`price × quantity` 라인은 `watch("price_display")`, `watch("quantity_display")`를 `parseRaw`로 변환해 **실시간 계산한 값**으로 렌더.
   2. **기본 거래 정보 카드** (compact 2열 grid) — `날짜`, `계좌`, `시장` 세 항목만 (수수료·제세금은 입력 필드이므로 제외).
   3. **금액 입력 필드** — 기존 `가격`, `수량`, `수수료`, `제세금(매도)` 입력을 세로 stack 유지.
   4. 구분선 이후 기존 "회고 / 결과" 또는 "근거 / 감정" 섹션은 그대로 유지.
3. 실시간 총액: `parseRaw(watch("price_display")) * parseRaw(watch("quantity_display"))`.
4. 기존 `거래 유형` 박스, `종목`/`날짜`/`계좌` `ReadOnlyField` 3개, 미사용 `ReadOnlyField` 헬퍼 삭제.

### 주요 변경 파일

- `src/components/records/trade-display.tsx` — (신규) `MARKET_LABELS`, `buildMarketDisplay`, `CompactRow`, `CountryBadge` 공용 export.
- `src/components/records/TradeDetail.tsx` — 공용 모듈 사용으로 전환 (렌더 결과 동일 유지).
- `src/components/records/TradeEditPanel.tsx` — 상단부 재구성 (헤더 카드 + compact grid), `ReadOnlyField` 제거, 실시간 총액.

## 구현 체크리스트

- [ ] `src/components/records/trade-display.tsx` 생성 — `MARKET_LABELS`, `buildMarketDisplay(trade)`, `CompactRow`, `CountryBadge` export
- [ ] `src/components/records/TradeDetail.tsx` 공용 모듈 사용으로 교체 (렌더 동일)
- [ ] `src/components/records/TradeEditPanel.tsx` 상단부 교체 — `거래 유형` 박스 + `종목`/`날짜`/`계좌` ReadOnly 3개 제거 → 헤더 카드 + 2열 compact grid
- [ ] `TradeEditPanel`에서 `watch`로 실시간 총액 계산 후 헤더 카드에 주입
- [ ] 미사용 `ReadOnlyField` 헬퍼 제거
- [ ] 타입 체크 통과 (`pnpm tsc --noEmit`)
- [ ] 수동 검증: 매수/매도, KOSPI/NASDAQ/exchange null 거래, 가격·수량 실시간 반영

## 우려사항 / 리스크

- 공용 모듈 이관 시 `TradeDetail` 렌더 결과가 달라지지 않도록 className·배색 토큰 그대로 유지 필요.
- 실시간 총액 계산에서 `parseRaw`가 잘못된 입력(빈 문자열, 쉼표만)을 `0`으로 처리 → 입력 중 0원 표시될 수 있음. 현재 허용 가능한 UX로 판단.
