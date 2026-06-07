> 완료: 2026-04-21

# Spec: 시장 항목을 헤더 뱃지 3종으로 분리

## 배경 / 문제

거래 상세(`TradeDetail.tsx`)와 거래 수정(`TradeEditPanel.tsx`)에서 시장 정보가 "기본 거래 정보" 카드 내 `CompactRow`로 별도 표시되고 있다. 헤더 종목 코드 옆에 시장 타입/국가/거래소 뱃지로 분리하여 시각적 위계를 정리하고 정보 칸을 절약한다.

## 목표

- 거래 상세/수정 페이지의 헤더 종목 코드 옆에 `[시장 타입] [국가] [거래소]` 형태의 뱃지가 표시된다.
- "기본 거래 정보" 카드의 `시장` 행이 제거된다.
- 비-주식(CRYPTO/ETC) 또는 거래소 누락 케이스에서도 깨지지 않는다.

## 설계

### 접근 방식

헤더 종목 코드 옆에 세 종류 뱃지를 나열한다:

- **시장 타입 뱃지**(`MarketTypeBadge`): `MARKET_LABELS[market_type]` — 항상 표시
- **국가 뱃지**(기존 `CountryBadge` 재사용): STOCK이고 KR/US일 때만
- **거래소 뱃지**(`ExchangeBadge`): STOCK이고 `exchange` 값이 있을 때만

뱃지 스타일 토큰은 기존 `CountryBadge`와 동일(`text-[11px] font-bold px-1.5 py-0.5 rounded-md`). 색상은 무채색 톤으로 국가 뱃지(파랑/주황)와 충돌 방지.

`buildMarketDisplay`는 사용처가 사라지므로 삭제, `MARKET_LABELS`는 export로 변경.

### 주요 변경 파일

- `src/components/records/trade-display.tsx` — `MarketTypeBadge`, `ExchangeBadge` 추가, `buildMarketDisplay` re-export 제거
- `src/components/records/trade-formatters.ts` — `MARKET_LABELS` export, `buildMarketDisplay` 삭제
- `src/components/records/TradeDetail.tsx` — 헤더에 뱃지 3개 추가, `시장` CompactRow 삭제, 사용 안 하는 변수 정리
- `src/components/records/TradeEditPanel.tsx` — 동일 변경

## 구현 체크리스트

- [x] `trade-formatters.ts`: `MARKET_LABELS` export, `buildMarketDisplay` 삭제
- [x] `trade-display.tsx`: `MarketTypeBadge`, `ExchangeBadge` 추가 + re-export 정리
- [x] `TradeDetail.tsx`: 헤더에 뱃지 3개 적용, 시장 CompactRow 삭제, import/변수 정리
- [x] `TradeEditPanel.tsx`: 헤더에 뱃지 3개 적용, 시장 CompactRow 삭제, import 정리
- [x] 타입 체크 통과 (`pnpm tsc --noEmit`)

## 우려사항 / 리스크

- 거래소 값(`exchange`)이 자유 문자열이라 길이가 길 경우 헤더가 줄바꿈될 수 있음 → `flex-wrap`으로 대응.
- 다크 모드 색상 대비 확인 필요.
