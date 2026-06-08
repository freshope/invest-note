> 완료: 2026-04-21

# Spec: trades.exchange NOT NULL 전환

## 배경 / 문제

`trades.exchange`는 008 마이그레이션에서 nullable(`text`)로 추가되었다. 기존 데이터 정합성은 확인 완료. 신규 거래에서 `null`이 섞이지 않도록 DB 레벨 NOT NULL 제약을 걸고, TS 타입·validation·폼의 느슨한 nullable 처리를 일관되게 정리한다.

## 목표

- DB `trades.exchange`에 NOT NULL 제약 적용
- 값 미상인 경우(예: KR 네이버 `typeCode` 빈 값) `null` 대신 빈 문자열 `""`로 저장
- `ExchangeBadge` 등 표시부는 값이 비어 있으면 렌더 생략
- 관련 TS 타입 `string | null` → `string`으로 일관 정리
- 타입 체크 및 개발 서버 상의 등록/조회 흐름이 정상 동작

## 설계

### 접근 방식

- **DB**: `ALTER TABLE trades ALTER COLUMN exchange SET NOT NULL;` (방어용 `UPDATE … = ''` 선행)
- **값 정책**: 미상 거래소는 `""` 로 저장 (null 아님)
- **표시 정책**: `ExchangeBadge`는 `exchange`가 falsy면 null 반환 (기존 방어 유지)
- **검색 API**: KR 네이버 경로에서 `typeCode || null` → `typeCode || ""`
- **Validation**: 서버·폼 모두 `z.string().max(50).default("")` — 빈 문자열 허용
- **파생 타입**: `Position.exchange`, `Trade.exchange`, `StockResult.exchange` 등 전부 `string`

### 주요 변경 파일

- `supabase/migrations/009_exchange_not_null.sql` — 신규 마이그레이션
- `src/app/api/stocks/search/route.ts:48` — `typeCode || ""` fallback
- `src/types/database.ts:63` — `Trade.exchange: string`
- `src/lib/api-client.ts:86` — `TradeCreateInput.exchange: string`
- `src/components/records/StockSearchInput.tsx:13,20` — `exchange: string`
- `src/lib/portfolio.ts:12,52,77,89,112,145,160` — 타입·가드 정리
- `src/components/records/trade-display.tsx:28-31` — `ExchangeBadge` props 타입 좁힘, falsy 가드 유지
- `src/lib/api-server/validators.ts:96` — `TradeCreateSchema.exchange` 갱신
- `src/components/records/TradeBasicForm.tsx:40,88-99,183,214,305,324` — 스키마·defaults·submit·setValue 정리

## 구현 체크리스트

- [x] `supabase/migrations/009_exchange_not_null.sql` 생성 (backfill 방어 + NOT NULL)
- [x] `src/app/api/stocks/search/route.ts` KR fallback을 `""`로 수정
- [x] `src/types/database.ts` `Trade.exchange: string` 로 좁힘
- [x] `src/lib/api-client.ts` `TradeCreateInput.exchange: string`
- [x] `src/components/records/StockSearchInput.tsx` 타입 좁힘
- [x] `src/lib/portfolio.ts` 타입·가드 정리 (빈 문자열이면 덮어쓰지 않는 가드 유지)
- [x] `src/components/records/trade-display.tsx` `ExchangeBadge` 타입 좁힘 + falsy 가드 유지
- [x] `src/lib/api-server/validators.ts` `TradeCreateSchema.exchange = z.string().max(50).default("")`
- [x] `src/components/records/TradeBasicForm.tsx` 스키마·defaults·submit·setValue 업데이트 (null → "")
- [x] `pnpm tsc --noEmit` 통과
- [ ] 개발 서버에서 KR/US 종목 등록 및 상세 렌더 확인

## 우려사항 / 리스크

- `portfolio.ts`의 `if (lot.exchange) pos.exchange = lot.exchange` 계열 가드는 빈 문자열을 자연스럽게 무시하므로 유지 (행동 변화 없음 확인 필요)
- 기존 거래 중 `exchange=""`(빈 문자열) 데이터가 포함되었을 경우 상세 화면의 `ExchangeBadge`가 숨겨지는 것이 정상 동작
- Supabase 마이그레이션 적용 경로(로컬/원격)는 기존 절차 그대로
