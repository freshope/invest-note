> 완료: 2026-04-21

# Spec: 거래 등록 프로세스 개선

## 배경 / 문제

거래 등록 폼의 사용자 경험에 4가지 마찰이 있다: (1) 계좌 기본값이 없어 매번 선택해야 함, (2) 매도 시 보유하지 않은 종목도 검색·선택 가능해 사후 에러로만 차단됨, (3) 거래소(exchange) 저장 흐름이 암묵적이고 `Position` 엔터티에 누락됨, (4) 종목 선택 후 드롭다운이 다시 열리며 포커스가 input에 남아 다음 필드로 이동하지 않음.

## 목표

- 거래 등록 진입 시 마지막으로 사용한 계좌가 자동 선택된다.
- 매도 토글 시 서버 검색 대신 **해당 계좌의 보유 종목 목록**에서만 선택 가능하다.
- 종목 선택·변경 시 거래소(exchange) 값이 자동 채워지고 저장된다 — 매수(외부 검색), 매도(보유 종목) 모두 동일.
- 종목 선택 후 드롭다운이 즉시 닫히고 다시 열리지 않으며, 포커스가 가격 입력란으로 이동한다.

## 설계

### 접근 방식

1. **계좌 기본값**: `localStorage` 키 `invest-note:last-account-id`에 저장. 마운트 후 `accounts`에 존재하는 ID일 때만 `setValue("account_id", ...)`로 주입. 제출 성공 시 저장.
2. **매도 시 보유 종목 선택기**: `usePortfolioSummary()`의 `positions`를 재사용. 신규 `HoldingSelectInput` 컴포넌트가 `accountIds.includes(accountId)`로 필터링하여 리스트 노출. 서버 검색 UI는 매도 모드에서 렌더하지 않음.
3. **거래소 흐름 보강**: `Position` 인터페이스에 `exchange: string | null` 추가, `buildPositions`가 trade.exchange를 lot 단위로 추적하여 최신 값을 보관. `HoldingSelectInput` 선택 콜백이 `SelectedStock { name, code, market, exchange }` 계약을 따라 `TradeBasicForm`에 전달.
4. **드롭다운 재표시 버그**: `justSelectedRef` 플래그로 `handleSelect` 직후의 `useEffect` 한 사이클을 건너뜀. 포커스 이동: `onSelectComplete` 콜백 추가, `priceInputRef`로 가격 `Input`에 focus.

### 주요 변경 파일

- `src/components/records/TradeBasicForm.tsx` — localStorage 기본값 로직, SELL 분기로 HoldingSelectInput 렌더, priceInputRef 및 포커스 이동
- `src/components/records/StockSearchInput.tsx` — `justSelectedRef` 플래그, `onSelectComplete` 콜백
- `src/components/records/HoldingSelectInput.tsx` — **신규**: 보유 종목 전용 선택기
- `src/lib/portfolio.ts` — `Position.exchange` 필드 추가, `buildPositions`에 exchange 추적
- `src/components/base/Input.tsx` — (필요 시) `forwardRef` 지원 추가

## 구현 체크리스트

- [x] `src/lib/portfolio.ts` — `Position.exchange` 필드 및 `buildPositions` lot 추적 로직 추가
- [x] `src/components/base/Input.tsx` — `forwardRef` 적용 확인/추가
- [x] `src/components/records/StockSearchInput.tsx` — `justSelectedRef` 기반 재표시 버그 수정 + `onSelectComplete` 콜백 추가
- [x] `src/components/records/HoldingSelectInput.tsx` — 보유 종목 선택기 신규 작성
- [x] `src/components/records/TradeBasicForm.tsx` — localStorage 기본값, SELL 분기, priceInputRef 연결, onSelectComplete 전달
- [x] 매수/매도 등록 end-to-end 동작 확인 (브라우저)
- [x] 타입 체크 통과 (`pnpm tsc --noEmit`)

## 우려사항 / 리스크

- `Position.exchange` 필드 추가가 다른 소비자(`TradeDetail`, `PortfolioSummary` 등)에 영향을 줄 수 있음 — 선택적(optional) 속성이 아닌 `string | null`로 두고 소비자 영향 확인 필요.
- localStorage는 SSR hydration 타이밍에 주의 — 초기 렌더는 빈 값으로 시작하고 `useEffect`에서 주입하는 방식이 안전.
- 매도 시 보유 종목이 없는 계좌로 토글하면 선택기가 비어 등록 자체가 불가능 — 명시적 안내 문구 필요.
