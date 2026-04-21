# Spec: 거래 상세 페이지 개선

## 배경 / 문제

거래 상세 페이지(`src/components/records/TradeDetail.tsx`)의 정보 가독성이 낮다. 핵심 숫자(단가·수량·금액)가 두 번째 박스에 평행 나열되어 한눈에 안 들어오고, 시장은 "주식/암호화폐/기타"만 표시되어 KOSPI/KOSDAQ 같은 거래소 구분이 없다. 검색 API가 거래소를 내려주지만 저장 흐름에서 버려지고 있다.

## 목표

- 상단 종목 카드에서 단가·수량·총액이 바로 보인다.
- 날짜·계좌·시장·수수료·제세금이 2열 컴팩트 그리드로 표시된다.
- 시장 값이 `주식·국내·KOSPI` 형태로 표시되고, 거래소 정보가 없는 기존 거래는 `주식·국내`로 표시된다.
- 신규 거래 생성 시 검색에서 선택한 종목의 거래소(exchange)가 DB에 저장된다.

## 설계

### 접근 방식

1. `trades.exchange text` 컬럼을 migration으로 추가. 기본값 없이 nullable.
2. `TradeBasicForm.onSelect`에서 버려지던 `stock.exchange`를 저장 payload에 포함.
3. `TradeDetail` 레이아웃 재구성:
   - 종목 헤더 카드에 총액(크게, rise/fall 색) + 단가×수량(작게, muted) 추가.
   - 기존 "기본 거래 정보" 박스에서 가격/수량/총액 행 제거, 나머지는 2열 컴팩트 그리드로 재배치.
   - 시장 값은 `[marketLabel, countryLabel, exchange].filter(Boolean).join("·")`로 결합.
4. 날짜 포맷은 기존 `"yyyy년 M월 d일 (EEE)"` 그대로 유지.

### 주요 변경 파일

- `supabase/migrations/008_add_exchange.sql` — `alter table trades add column exchange text`
- `src/types/database.ts` — `Trade` 인터페이스에 `exchange: string | null` 추가
- `src/components/records/TradeBasicForm.tsx` — 스키마/payload/onSelect에 exchange 추가
- `src/components/records/TradeDetail.tsx` — 종목 카드에 숫자 블록 추가, 기본 정보 박스 컴팩트화 + 시장 표기 변경

## 구현 체크리스트

- [x] `supabase/migrations/008_add_exchange.sql` 작성
- [x] 리모트 DB에 migration 적용
- [ ] `src/types/database.ts`의 `Trade` 인터페이스에 `exchange` 필드 추가
- [ ] `src/components/records/TradeBasicForm.tsx` zod 스키마에 `exchange` 추가, `onSelect`에서 `setValue`, create payload 포함
- [ ] `src/components/records/TradeDetail.tsx` 종목 헤더 카드에 단가·수량·총액 블록 추가
- [ ] `src/components/records/TradeDetail.tsx` 기본 정보 박스를 2열 컴팩트 그리드로 변경 + 시장+거래소 표기 로직 적용
- [ ] 타입 체크 통과 (`pnpm tsc --noEmit`)
- [ ] 수동 검증: 매수/매도, KOSPI/KOSDAQ/NYSE/NASDAQ, 기존(exchange null) 거래 상세 확인

## 우려사항 / 리스크

- 기존 거래는 `exchange`가 null이므로 UI fallback이 반드시 동작해야 함 — `filter(Boolean).join("·")` 패턴으로 처리.
- 해외 티커는 NYSE/NASDAQ/NYSE ARCA/AMEX/CBOE 중 정규화된 값만 저장됨(`/api/stocks/search/route.ts` EXCHANGE_MAP).
- migration 순서: 007까지 존재 → 008로 진행.
