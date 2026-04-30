# Spec: 분석탭 섹션 레이아웃 일관성 — 설명은 타이틀 밑, 알림은 섹션 하단

> 완료: 2026-04-30

## 배경 / 문제

분석탭의 "근거 태그별 성과"(ReasoningBreakdown) 섹션은 알림(amber Alert)이 섹션 상단에, 보조 설명 문구는 섹션 하단에 위치해, "전략 준수 분석"(StrategyAdherencePanel) 등 다른 섹션의 표준 패턴과 어긋난다.

표준 패턴(StrategyAdherencePanel 기준):
- 섹션 타이틀 → 보조 설명 문구
- 메인 콘텐츠
- 알림(Alert)은 가장 아래

이 작업은 `ReasoningBreakdown`을 표준 패턴으로 정렬하고, 동일 패턴이 어긋난 다른 섹션(`BehaviorRadar`)도 함께 정리해 분석탭 전반의 시각적 일관성을 회복한다.

## 목표

- "근거 태그별 성과" 섹션이 다음 순서로 렌더링된다: **(SectionCard 타이틀) → 설명 문구 → 태그 행 목록 → 알림**.
- "투자 성향 프로필" 섹션이 다음 순서로 렌더링된다: **(SectionCard 타이틀) → 설명(분산도 각주) → 레이더 차트 → 5개 dimension 배지**.
- 그 외 분석탭 섹션의 시각/구조는 변하지 않는다.
- 타입 체크가 통과한다.

## 설계

### 접근 방식

- `ReasoningBreakdown.tsx`의 JSX 순서를 재배치한다. 알림 블록은 컴포넌트 마지막으로 옮기고, 하단 footer `<p>`는 컴포넌트 최상단(SectionCard `h2` 바로 아래)으로 옮긴다.
- 데이터가 없는 빈 상태(empty state)에서도 설명 문구는 항상 보이도록 한다 — `StrategyAdherencePanel`의 sub-title/description이 항상 노출되는 패턴과 일치시킨다.
- 알림은 데이터 유무와 무관하게 조건이 충족되면 표시되므로, empty state 분기 바깥의 컴포넌트 끝부분에 둔다.
- `BehaviorRadar.tsx`의 footer `<p>`("* 분산도는 …")도 컴포넌트 최상단으로 이동한다. asterisk는 차원 라벨 "분산도\*"의 각주이므로, 위로 옮겨도 의미가 통한다.
- `StrategyAdherencePanel`, `DiversificationPanel`, `EmotionBreakdown`, `StrategyBreakdown`, `ReviewQualityPanel`, `DrilldownHistograms`, `SuggestionList`은 이미 패턴에 부합하거나 해당 요소(설명/알림)가 없으므로 변경하지 않는다.
- 텍스트 내용·스타일(색·크기·간격) 자체는 그대로 유지하며, 위치만 이동한다.

### 주요 변경 파일

- `app/src/components/analysis/ReasoningBreakdown.tsx` — 설명 `<p>`를 상단으로 이동, Alert 블록을 컴포넌트 최하단으로 이동.
- `app/src/components/analysis/BehaviorRadar.tsx` — 하단 각주 `<p>`("\* 분산도는 …")를 컴포넌트 상단으로 이동.

### 참고 패턴 (이미 표준에 부합 — 변경 없음)

- `app/src/components/analysis/StrategyAdherencePanel.tsx` — 타이틀 행(sub-title + description) → 콘텐츠 → 알림 순서.
- `app/src/components/analysis/DiversificationPanel.tsx` — 타이틀 행(sub-title + description + KPI) → 콘텐츠 순서.

## 구현 체크리스트

- [x] `ReasoningBreakdown.tsx` — JSX 재배치: 설명 `<p>` 상단, Alert 하단, empty state에서도 설명 항상 노출
- [x] `BehaviorRadar.tsx` — 하단 footnote `<p>`를 상단으로 이동
- [x] 타입 체크 통과 (`pnpm -C app exec tsc --noEmit`)

## 우려사항 / 리스크

- `ReasoningBreakdown`의 설명 문구는 "한 거래가 여러 태그에 포함되어 합계가 총 실현손익과 다를 수 있습니다."로, 데이터가 없는 빈 상태에서 보이는 게 어색할 수 있다. → 표준 패턴과 일관성을 우선해 항상 노출하기로 결정.
- `BehaviorRadar`의 각주를 위로 옮기면 "분산도\*" → "\* 분산도는 …" 시각 동선이 길어질 수 있다. 다만 5개 dimension 배지 영역 위에 위치해 사용자가 차원 정보를 보기 전에 컨텍스트를 얻는 효과가 있어 허용 가능 범위로 판단.
