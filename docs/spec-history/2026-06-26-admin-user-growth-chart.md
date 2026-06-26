# 현재 작업 사양 — 어드민 대시보드 신규 가입자 일별 막대 차트

> 완료: 2026-06-26
> 최종 결과: 후속 요청으로 별도 막대 차트(`NewSignupsChart`)를 만들지 않고, `UserGrowthChart` 하나에 누적(선, 우축)·신규(막대, 좌축)를 이중 Y축 `ComposedChart`로 통합. 선행으로 `get_user_growth` 빈 날짜 누락(generate_series) 수정 포함.

## 목표
어드민 대시보드에 "일별 신규 가입자 수" 막대 차트를 추가한다. 기존 누적 사용자수 라인 차트(`UserGrowthChart`)는 그대로 유지하고, 그 아래에 막대 차트를 새로 추가한다.

## 배경
직전 작업에서 `get_user_growth` 집계 SQL을 `generate_series` 기반으로 변경하여, 첫 가입일~오늘(KST) 연속 날짜에 대해 일별 신규 수(`coalesce(d.cnt,0)`)와 누적합(`cumulative`)을 이미 계산한다. 일별 신규 수는 현재 응답에 노출되지 않으므로 이를 노출만 하면 된다.

## Shape 계약 (리더 확정 — 협상 불필요)
`/admin/user-growth` 응답 항목에 필드 1개 추가:
- 필드명: `new_users` (snake_case passthrough, 어드민 패널 컨벤션)
- 의미: 해당 날짜의 신규 가입자 수 (0 포함)
- 타입: BE `int` / FE `number`
- 기존 `date`, `cumulative` 유지

응답 예: `[{"date":"2026-06-01","cumulative":1,"new_users":1}, {"date":"2026-06-02","cumulative":1,"new_users":0}, ...]`

## BE 작업 (be-engineer)
1. `api/src/invest_note_api/db_ops/admin_repo.py` `get_user_growth`: SELECT 절에 `coalesce(d.cnt, 0) as new_users` 추가, 반환 dict에 `"new_users": int(r["new_users"])` 추가.
2. `api/src/invest_note_api/schemas/admin.py` `UserGrowthPoint`: `new_users: int` 필드 추가.
3. `api/tests/test_admin_crud.py` `test_user_growth_returns_series`: fixture series에 `new_users` 키 추가하여 shape 정합 유지.
- 검증: `cd api && poetry run pytest tests/test_admin_crud.py -q`

## FE 작업 (fe-engineer)
1. `admin/src/lib/api.ts` `UserGrowthPoint` 인터페이스: `new_users: number` 추가.
2. `admin/src/components/NewSignupsChart.tsx` 신규 — `UserGrowthChart`를 템플릿으로 recharts `BarChart` 사용, `dataKey="new_users"`, X축 `date`(동일 `fmtTick`), 제목 "일별 신규 가입자". 같은 `adminApi.userGrowth()` 쿼리 재사용(queryKey 동일 → 캐시 공유).
3. `admin/src/app/(dash)/page.tsx`: 기존 `<UserGrowthChart />` 아래에 `<NewSignupsChart />` 마운트.
- shadcn 규칙: 차트는 `@/components/base/Chart` 래퍼 사용(기존 컴포넌트와 동일).
- 검증: `pnpm -C admin exec tsc --noEmit`

## QA (integration-qa)
- BE 응답 `new_users` 필드 ↔ FE `UserGrowthPoint.new_users` 타입 정합
- 막대 차트가 0인 날도 연속 표시되는지 (generate_series 연속성 유지)
- 기존 라인 차트 회귀 없음
