# Spec: 분석 탭 BehaviorRadar 인터랙션 효과 제거

> 완료: 2026-04-30

## 배경 / 문제

분석 탭의 "투자 성향 프로필" 차트(`BehaviorRadar`)는 탭/호버 시 데이터 점·라벨 강조 효과가 떠오르고, SVG 포커스 시 브라우저 기본 outline 테두리가 보인다. 홈 탭의 도넛 차트(`AllocationDonut`)는 같은 recharts 기반이지만 이미 두 효과 모두 제거되어 있다. 두 화면의 차트 동작을 일치시켜 시각적 일관성을 확보한다.

## 목표

- 분석 탭 "투자 성향 프로필" 차트에서 탭/호버 시 점·라벨 등 강조 효과가 더 이상 나타나지 않는다.
- 차트의 SVG 요소가 포커스(클릭/탭/키보드)되어도 outline 테두리가 그려지지 않는다.
- 홈 탭의 도넛 차트와 동일한 인터랙션 동작을 갖는다.

## 설계

### 접근 방식

홈 탭 [AllocationTabs.tsx](../app/src/components/home/AllocationTabs.tsx) (라인 43, 54)의 패턴을 그대로 적용한다.

1. **포커스 테두리 제거** — 차트 컨테이너 div에 `[&_*:focus]:outline-none` Tailwind 임의 변형 클래스를 적용해, 자식 SVG 요소의 `:focus` 상태에서 브라우저 기본 outline을 제거한다. 홈 탭과 동일한 방식.
2. **호버/탭 강조 효과 제거** — recharts `<Radar>`는 `<Tooltip>`이 없어도 hover 시 `activeDot`이 그려진다. `activeDot={false}` prop으로 비활성화한다. (기본 `dot`은 이미 false)

`<Tooltip>` 컴포넌트는 현재 코드에 import/사용이 없으므로 추가 조치 불필요.

### 주요 변경 파일

- [app/src/components/analysis/BehaviorRadar.tsx](../app/src/components/analysis/BehaviorRadar.tsx) — `ResponsiveContainer`를 감싸는 컨테이너에 `[&_*:focus]:outline-none` 추가, `<Radar>`에 `activeDot={false}` 추가

`outline-none` CSS는 차트 영역만 감싸는 새 div에 적용한다 (외곽 `space-y-4` div에 직접 붙이면 하단 `ProfileBadge` 등 다른 자식 focus 동작에 영향 가능).

## 구현 체크리스트

- [x] `BehaviorRadar.tsx` — `ResponsiveContainer`를 `<div className="[&_*:focus]:outline-none">`로 감싸기
- [x] `BehaviorRadar.tsx` — `<Radar>`에 `activeDot={false}` 추가
- [x] 타입 체크 통과 (`pnpm tsc`)
- [x] 분석 탭에서 Radar 차트 탭/호버 시 점·라벨 강조 효과가 없는지 수동 확인
- [x] 분석 탭에서 차트 클릭/탭 후 포커스 outline이 보이지 않는지 수동 확인

## 우려사항 / 리스크

- **활성 효과 제거의 UX 영향**: `activeDot={false}`는 데이터 가독성에 영향 없음. Radar polygon과 grid는 그대로.
- **outline 제거의 접근성 영향**: 차트 자체가 키보드 포커스 시 outline을 잃으나, 차트는 비대화형 시각화이며 데이터는 하단 `ProfileBadge` 텍스트로 동등하게 제공된다. 홈 탭이 이미 동일 접근을 하고 있으므로 일관성 확보.
