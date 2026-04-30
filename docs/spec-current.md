# Spec: 분석 탭 — YTD 라벨 명확화

## 배경 / 문제

분석 탭(`/analysis`)의 기간 옵션 중 'YTD'가 [PERIODS_FULL](app/src/lib/constants/analysis.ts:6)에서 `"올해"` 라벨로만 표시되고 있어, 사용자가 이를 "1년"으로 오인하는 사례가 발생했다. 사용자 보고: **"1년(YTD)의 총거래가 6개월의 총거래보다 적게 표시된다"**.

코드 정의와 실제 동작은 정상이다:
- [periodToRange](app/src/lib/analysis/period.ts:24-26): `ytd` = `startOfYear(now) ~ now` → 오늘(2026-04-30) 기준 ≈ 4개월치
- 6개월 옵션은 ≈ 6개월치
- 따라서 `6개월 ≥ YTD`는 수학적으로 정상이며 버그가 아니다.

문제의 본질은 라벨이 의미를 충분히 전달하지 못해 사용자가 "1년치"로 기대했다는 점이다. 라벨을 명확화하여 동일한 오해가 재발하지 않도록 한다.

## 목표

[PERIODS_FULL](app/src/lib/constants/analysis.ts:6-12)의 `ytd` 항목 라벨이 `"올해(YTD)"`로 표시되어, "1년치 데이터"가 아닌 "연초~현재"임을 즉시 인지할 수 있다. PERIODS_COMPACT는 이미 `"YTD"`이므로 변경 없음.

## 설계

### 접근 방식

`PERIODS_FULL`의 `ytd` 라벨 한 줄만 변경한다. 라벨 소비처([PeriodFilterTabs.tsx:25](app/src/components/analysis/PeriodFilterTabs.tsx:25))는 `p.label`을 그대로 렌더링하므로 추가 컴포넌트 수정은 불필요하다. 다른 화면에서 `"올해"` 문자열을 하드코딩으로 의존하는 곳은 없음 (grep 확인됨).

`Period` 타입(`"ytd"`)과 `parsePeriod`/`filterByPeriod`는 일절 변경하지 않는다 — URL 파라미터 호환성과 백엔드 API 키 호환성을 유지한다.

### 주요 변경 파일

- [app/src/lib/constants/analysis.ts:10](app/src/lib/constants/analysis.ts:10) — `PERIODS_FULL` 의 `ytd` 라벨 `"올해"` → `"올해(YTD)"`

## 구현 체크리스트

- [x] `PERIODS_FULL`의 `ytd` 라벨 `"올해"` → `"올해(YTD)"` 변경
- [x] 타입 체크 통과 (`pnpm -C app exec tsc --noEmit`)
- [x] 분석 관련 단위 테스트 통과 (`pnpm -C app test` — 96/96 pass)
- [ ] 분석 탭 UI에서 `grid-cols-5` 레이아웃에 라벨이 깨지지 않는지 수동 확인 (데스크톱 + 모바일 폭)

## 우려사항 / 리스크

- `PERIODS_FULL`은 `grid-cols-5`로 균등 배분되므로 좁은 모바일 폭에서는 `"올해(YTD)"` 5자가 다른 옵션(`"3개월"` 3자, `"전체"` 2자)보다 길어 줄바꿈 또는 자간 압축이 발생할 수 있다. PeriodFilterTabs는 `compact` prop이 `true`면 PERIODS_COMPACT를 쓰므로, 좁은 화면에서 호출자가 `compact`를 사용하고 있다면 영향 없음. 수동 확인 필수.

## 검증

1. `pnpm -C app exec tsc --noEmit` 통과
2. `pnpm -C app test` 통과 (analysis 관련 테스트)
3. 분석 탭(`/analysis`)을 열어:
   - 기간 탭에 `"올해(YTD)"`가 표시되는지 확인
   - 데스크톱 폭과 모바일 폭(≤ 480px)에서 라벨 잘림/줄바꿈 없는지 확인
   - 탭 클릭 시 URL의 `period=ytd` 동작이 종전과 동일한지 확인
