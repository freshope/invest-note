# Spec: 홈탭 자산 차트 개편 (예수금 포함 · 총합 일치 · 콤마)

## 배경 / 문제

홈탭의 자산 분포 차트(`AllocationTabs`)는 두 탭(종목별/계좌별)이 있지만 총합이 일치하지 않음. 종목별 차트는 주식평가금액만 포함하고 예수금을 빠뜨리며, 도넛 중앙 총액이 "3.4억"처럼 압축 표기되어 천단위 콤마가 없음. 계좌별 차트는 (주식+현금) 합계를 사용하도록 설계되었지만 시세 누락 시 예수금만 표시되는 것처럼 보이는 케이스가 발생.

## 목표

- 종목별 차트가 보유 종목 평가금액 + 예수금(단일 슬라이스 1개)을 합한 도넛으로 동작한다.
- 계좌별 차트가 계좌마다 (주식+현금) 합산 단일 슬라이스로 동작한다.
- 종목별 차트 총합 = 계좌별 차트 총합 = `totals.totalAssets`로 일치한다.
- 도넛 중앙 총액이 컴팩트 형식을 유지하면서 천단위 콤마로 표기된다 (예: `2,000만원`, `3.4억원`).
- 종목별 라벨 "주식 평가" → "총자산"으로 정리.

## 설계

### 접근 방식

단일 파일 수정 (`app/src/components/home/AllocationTabs.tsx`). 데이터는 이미 props로 흘러오므로 추가 fetch/백엔드 수정 불필요.

- 종목별 차트: 기존 종목 top7 + "기타" 빌드 후 `cashTotal > 0`이면 "예수금" 슬라이스를 끝에 push
- 계좌별 차트: `s.totalValue` 사용 유지 (현재 설계 그대로)
- 중앙 텍스트: `fmtCompact` 유지하되 만 범위에 천단위 콤마 추가 (`format.ts` 수정)
- 라벨: "주식 평가" → "총자산"
- 계좌별 차트 주식금액 미포함 버그 수정 (asyncpg UUID 타입 불일치)

### 주요 변경 파일

- `app/src/components/home/AllocationTabs.tsx` — `posData` 빌더에 예수금 슬라이스 추가, 종목별 라벨 변경
- `app/src/lib/format.ts` — `fmtCompact` 만 범위 천단위 콤마 추가
- `api/src/invest_note_api/routers/portfolio.py` — `_account_from_row` UUID→str 변환 추가
- `api/src/invest_note_api/domain/portfolio.py` — `build_account_snapshots` `str(account.id)` 방어 처리

## 구현 체크리스트

- [x] `posData` useMemo: 종목 top7 + "기타" 후 cashTotal>0이면 "예수금" 슬라이스 push. 종속성 `[positions, snapshots]`로 갱신
- [x] 예수금 슬라이스 색상 고정: `color: "#9CA3AF"` (회색)
- [x] 종목별 도넛 `label`을 "주식 평가" → "총자산"으로 변경
- [x] `format.ts` `fmtCompact`: 만 범위에 `.toLocaleString("ko-KR")` 적용
- [x] `_account_from_row`: `id`, `user_id` UUID→str 변환
- [x] `build_account_snapshots`: `str(account.id)` 방어 처리
- [x] 회귀 테스트 추가 (`test_snapshot_uuid_account_id`)
- [ ] 타입 체크 통과 (`pnpm tsc --noEmit`)

## 우려사항 / 리스크

- 시세 누락 시 두 차트 총합이 동일하게 작아짐 (일관성 유지, 원장가와 차이는 별도 이슈)
- 예수금 슬라이스 색상은 "기타" 유무에 따라 변동 — 고정 색상은 후속 작업
