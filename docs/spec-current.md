# Spec: 매도 손익 저장 및 연쇄 재계산

**브랜치**: `feature/persist-realized-pnl` (develop 기반)

## 배경 / 문제

매도(SELL) 거래의 실현손익은 현재 조회 시마다 `src/lib/analysis/realized-pnl.ts:13` `computeRealizedPnL`이 사용자의 모든 거래를 시간순 순회하여 계산한다. 거래량이 늘수록 불필요한 반복 계산이고, 홈/분석/종목상세 화면이 각자 동일 계산을 반복한다. 최근 서버측 계산 포함 시도(커밋 9537877)가 롤백(736ab8e)된 이력도 있어 "한 번 계산해 저장, 영향 범위만 재계산" 방향으로 정리한다.

## 목표

- SELL 등록 시 `profit_loss`가 DB에 저장되고, 조회 시 재계산 없이 저장값을 바로 반환한다.
- BUY/SELL 수정·삭제·삽입 시 같은 (종목+계좌+국가) 그룹 내 이후 SELL들의 `profit_loss`가 자동 갱신된다.
- 수정/삭제로 이후 SELL이 보유수량 부족(oversell)이 되는 경우 400 오류로 차단된다.
- `traded_at`과 `profit_loss`는 사용자가 수정할 수 없다(계산 필드·시점 불변).
- 기존 데이터의 SELL 중 `profit_loss`가 비어 있는 항목은 백필 스크립트로 채워진다.

## 설계

### 접근 방식

**A안: 저장 + 연쇄 재계산 (이동평균 WAC)**

1. 이동평균 계산 결과(`profit_loss`)를 기존 컬럼에 그대로 저장.
2. `computeGroupPnL`을 재사용 가능한 그룹 단위 계산 함수로 분리해 서버·클라이언트 양쪽에서 사용.
3. 수정/삭제 전 `validateMutation`으로 가상 적용 시뮬레이션 → runningQty 음수가 되는 첫 SELL 발견 시 400 차단.
4. 통과 시 DB 변경 후 같은 그룹의 이후 SELL들 profit_loss 일괄 갱신.
5. 계산용 정렬 규칙: `traded_at` asc → 같은 날이면 BUY 우선 → `created_at` asc.
6. 수동 입력 UI/스키마 제거 (profit_loss, traded_at).
7. 트랜잭션은 옵션 B(검증 통과 후 재계산 실패 시 로깅 + 재시도)로 시작.

### 주요 변경 파일

- `src/lib/analysis/realized-pnl.ts` — `sortForCalc`/`computeGroupPnL`/`validateMutation` 추가, `sellPnL`의 `profit_loss` 우선분기 제거
- `src/lib/api-server/validators.ts` — `TradeUpdateSchema`에서 `traded_at`, `profit_loss` 필드 제거
- `src/app/api/trades/route.ts` (POST) — SELL 삽입 시 profit_loss 저장, 과거 시점 삽입 시 oversell 검증 + 후행 그룹 재계산
- `src/app/api/trades/[id]/route.ts` — PATCH/DELETE에 oversell 검증 + 재계산 로직 추가
- `src/components/records/TradeEditPanel.tsx` — `profit_loss_display` 입력/스키마 제거, 읽기전용 표시로 전환
- `src/lib/portfolio.ts` — SELL의 `profit_loss` 저장값 우선 사용, null인 경우만 계산 fallback
- `src/app/(app)/stocks/[country]/[ticker]/page.tsx` — 저장값 우선 사용
- `src/app/api/analysis/summary/route.ts` — 저장값 우선 사용
- `src/app/api/analysis/suggestions/route.ts` — 저장값 우선 사용
- `src/components/panels/DetailPanelProvider.tsx` — 저장값 우선 사용
- `scripts/backfill-pnl.ts` (신규) — 기존 SELL profit_loss 백필

## 구현 체크리스트

- [x] `src/lib/analysis/realized-pnl.ts`: `sortForCalc` 추가 + `computeRealizedPnL`이 이를 사용하도록 수정
- [x] `src/lib/analysis/realized-pnl.ts`: `computeGroupPnL(trades, key)` 추가
- [x] `src/lib/analysis/realized-pnl.ts`: `validateMutation(trades, mutation)` 추가
- [x] `src/lib/analysis/realized-pnl.ts`: `sellPnL`에서 `profit_loss != null` 분기 제거
- [x] `src/lib/analysis/__tests__/analysis.test.ts`: 새 함수 테스트 + 같은 날 BUY/SELL 정렬 케이스 추가
- [x] `src/lib/api-server/validators.ts`: `TradeUpdateSchema`에서 `traded_at`, `profit_loss` 제거
- [x] `src/app/api/trades/route.ts` POST: SELL 삽입 시 profit_loss 계산·저장
- [x] `src/app/api/trades/route.ts` POST: 과거 시점 삽입 시 oversell 검증 + 후행 SELL 재계산
- [x] `src/app/api/trades/[id]/route.ts` PATCH: oversell 검증 + 영향 그룹 재계산 (account/ticker 변경 시 양쪽 그룹)
- [x] `src/app/api/trades/[id]/route.ts` DELETE: oversell 검증 + 그룹 재계산
- [x] `src/components/records/TradeEditPanel.tsx`: `profit_loss_display` 필드·스키마·payload 제거
- [x] `src/lib/portfolio.ts`: 저장값 우선 사용
- [x] `src/app/(app)/stocks/[country]/[ticker]/page.tsx`: 저장값 우선 사용
- [x] `src/app/api/analysis/summary/route.ts`: 저장값 우선 사용
- [x] `src/app/api/analysis/suggestions/route.ts`: 저장값 우선 사용
- [x] `src/components/panels/DetailPanelProvider.tsx`: 저장값 우선 사용
- [x] `scripts/backfill-pnl.ts`: 기존 SELL profit_loss 백필 스크립트 작성 (1회 실행 대기 중)
- [x] 타입 체크 통과 (`pnpm tsc --noEmit`)
- [x] 유닛 테스트 통과 (`pnpm test`)
- [ ] 수동 검증: 새 SELL 등록 / BUY 수정으로 이후 SELL 갱신 / oversell 차단 / traded_at·profit_loss PATCH 무시 / 같은 날 BUY+SELL 혼재 / 홈·분석·종목상세 표시

## 우려사항 / 리스크

- **트랜잭션 부재**: Supabase 클라이언트는 트랜잭션 미지원. DB 변경과 재계산 배치 사이에 실패하면 데이터 드리프트 가능. 옵션 B(재시도 + 로깅)로 시작하고, 실제 이슈 발생 시 Postgres RPC로 전환.
- **기존 oversell 데이터**: 이미 저장된 이상 데이터는 유지. 수정 시점부터만 검증 적용 → 사용자가 이상 데이터 위에서 수정하려 할 때 예상치 못한 차단 가능(요구사항대로 수용).
- **백필 타이밍**: 배포 전 1회 실행. 실행 전에는 클라이언트 fallback 경로로 기존 SELL은 계산값 표시. 백필 후 fallback 제거 가능하지만 이번 스펙에선 fallback 유지(후속 작업).
- **account_id/ticker 변경 PATCH**: 두 그룹(이전/새)을 모두 재계산해야 하며, 두 그룹 모두 oversell 검증 대상. 로직 복잡도 주의.
