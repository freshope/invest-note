# Spec: 분석 모듈 테스트 보강 (period · computeRealizedPnL · byTag FIFO 귀속)

> 완료: 2026-04-30

## 배경 / 문제

`docs/backlog.md`의 "분석 탭 성능 / 유지보수" 섹션 항목:

> 테스트 보강 — `period.ts` 경계값, `computeRealizedPnL` 멀티 종목, `byTag` FIFO 귀속

분석 모듈은 회귀가 잦은 영역인데, 기존 단위 테스트가 단일 그룹·단순 시나리오 위주라 멀티 종목/계좌/국가 분리, FIFO 메타데이터 귀속 tie-break, 기간 필터 경계값 같은 운영에서 자주 마주치는 엣지 케이스가 비어 있다.

## 목표

- `period.ts`의 `parsePeriod` / `filterByPeriod`가 5개 모드(`1m`/`3m`/`6m`/`ytd`/`all`)와 from/to 경계, 빈 배열, 미래 거래에서 정확히 동작함이 단위 테스트로 검증된다.
- `computeRealizedPnL`이 동일 배열 내 멀티 종목·멀티 계좌·서로 다른 `country_code` 거래를 그룹별로 독립 계산함이 검증된다.
- `computeGroupPnL`의 reasoning_tags FIFO 귀속이 (a) 부분 소비 시 가장 최신 BUY tags 선택, (b) 동일 timeMs tie-break(order 큰 쪽), (c) 모든 BUY tags가 빈 배열인 경우에서 명세대로 동작함이 검증된다.
- `pnpm -C app test` 그린, `pnpm -C app exec tsc --noEmit` 그린.

## 설계

### 접근 방식

- **프로덕션 코드 변경 없음.** 테스트 코드만 추가.
- `period.ts` 전용 테스트는 `period.test.ts` 신규 파일로 분리. `analysis.test.ts`의 parsePeriod/filterByPeriod 섹션은 신규 파일로 이동(중복 제거).
- 시간 의존 테스트는 `vi.useFakeTimers()` + `vi.setSystemTime()`으로 결정론적 now 고정.
- 픽스처는 기존 `makeTrade` 헬퍼 재사용.

### 주요 변경 파일

- `app/src/lib/analysis/__tests__/period.test.ts` — 신규. parsePeriod 5개 모드 + invalid + null/empty, filterByPeriod의 1m/3m/6m/ytd/all 경계, 빈 배열, from/to 경계 포함, 미래 거래 제외.
- `app/src/lib/analysis/__tests__/analysis.test.ts` — parsePeriod/filterByPeriod 섹션 제거, `computeRealizedPnL` 멀티 그룹 케이스 추가, `computeGroupPnL` FIFO 귀속 추가 케이스.

## 구현 체크리스트

- [x] `app/src/lib/analysis/__tests__/period.test.ts` 신규 작성 (parsePeriod·filterByPeriod 경계값)
- [x] `analysis.test.ts`에서 parsePeriod/filterByPeriod describe 블록 제거
- [x] `analysis.test.ts`의 `computeRealizedPnL`에 멀티 종목·멀티 계좌·country 분리·타 그룹 BUY 비소비 케이스 추가
- [x] `analysis.test.ts`의 `computeGroupPnL`에 부분 소비 latest 선택·tie-break·빈 tags 케이스 추가
- [x] `pnpm -C app test` 통과 확인
- [x] `pnpm -C app exec tsc --noEmit` 통과 확인

## 우려사항 / 리스크

- 기존 `filterByPeriod` 3m 테스트는 `new Date()` 실시간 의존 → fake timer 도입으로 결정론적 검증으로 전환.
- `metaFromConsumedLatest` tie-break는 `consumed` push 순서(=`sortForCalc` 결과)에 의존하므로 픽스처에서 `created_at`을 명시적으로 다르게 설정.
- 백로그의 "byTag FIFO 귀속"은 백엔드 `aggregate.py.compute_summary().byTag`까지 포함할 수 있으나, 해당 집계는 SELL.reasoning_tags(FIFO 귀속의 결과물)만 읽으므로 프론트 `computeGroupPnL` 단위 테스트로 커버되며, 백엔드 byTag 자체 테스트는 `api/tests/test_analysis_logic.py`에 이미 존재.
