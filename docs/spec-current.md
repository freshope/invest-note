# Spec: 분석 탭 "투자 방향성 제안" 섹션 박스/타이틀 제거

## 배경 / 문제

분석 탭의 "투자 방향성 제안" 섹션은 다른 섹션들과 동일한 `SectionCard`(`rounded-2xl bg-muted/60 p-4`) 박스로 감싸져 있고 "투자 방향성 제안" 타이틀이 표시된다.

이 섹션의 `SuggestionList`는 각 제안 항목 자체가 이미 색상이 들어간 박스(`rounded-xl border`, severity별 배경색)로 시각적 강조가 충분하다. 추가로 회색 배경의 SectionCard로 한 번 더 감싸면 박스 안에 박스가 중첩되어 시선 분산이 발생하고, 섹션 타이틀 없이도 제안 항목들의 의미가 자명하다.

상단으로 통합된 직후 사용자 피드백에 따라 래퍼와 타이틀을 제거해 더 직접적인 강조 형태로 노출하려 한다.

## 목표

- 분석 탭에서 "투자 방향성 제안" 텍스트(섹션 타이틀)가 더 이상 렌더링되지 않는다.
- "투자 방향성 제안" 섹션을 둘러싸던 회색 라운드 박스(SectionCard)가 사라지고, `SuggestionList`의 제안 카드들이 분석 탭 컨테이너에 직접 배치된다.
- 다른 섹션들(투자 성향 프로필, 감정별 성과 등)은 영향을 받지 않고 기존 SectionCard 형태를 유지한다.
- 섹션 간 세로 간격(`space-y-4`)이 유지되어 제안 카드 묶음이 위/아래 섹션과 자연스럽게 구분된다.
- 타입 체크가 통과한다.

## 설계

### 접근 방식

`AnalysisDashboard.tsx`의 78–83행에서 `SectionCard` 래퍼만 제거하고 `SuggestionList`를 조건부 렌더링 그대로 둔다. `SectionCard` 컴포넌트 정의(21–28행) 자체는 다른 섹션들이 사용 중이므로 유지한다.

`SuggestionList`는 자체적으로 `space-y-2`로 항목 간 간격을 가지며, 각 제안 카드가 자체 색/테두리를 가져 박스 없이 노출돼도 시각적으로 자연스럽다. 외부 컨테이너의 `space-y-4`가 위/아래 다른 SectionCard들과의 간격을 처리한다.

빈 상태(`suggestions.length === 0`)는 `SuggestionList` 내부에서 안내 문구를 가운데 정렬로 보여준다. 박스 제거 시 이 안내 문구가 단독으로 떠 보일 수 있으나, 현 데이터 흐름상 제안이 0건이면 섹션 자체가 비교적 짧게 노출돼 큰 문제는 없다고 판단한다.

### 주요 변경 파일

- `app/src/components/analysis/AnalysisDashboard.tsx` — "투자 방향성 제안" 블록(78–83행)에서 `SectionCard` 래퍼를 벗기고 `<SuggestionList />`만 직접 렌더하도록 수정. 주변 주석은 그대로 유지하거나 짧게 갱신.

## 구현 체크리스트

- [ ] `app/src/components/analysis/AnalysisDashboard.tsx` 78–83행: `SectionCard title="투자 방향성 제안"` 래퍼 제거, `suggestionsData &&` 조건부로 `<SuggestionList suggestions={suggestionsData.suggestions} />`만 렌더
- [ ] 분석 탭 화면을 직접 확인해 타이틀과 회색 박스가 사라지고 제안 카드들이 노출되는지, 위아래 섹션과의 간격이 자연스러운지 검증
- [ ] 타입 체크 통과 (`pnpm tsc`)

## 우려사항 / 리스크

- 제안이 0건일 때 `SuggestionList`의 빈 상태 텍스트("아직 특이 패턴이 감지되지 않았어요")가 컨텍스트(타이틀)를 잃고 단독으로 뜬다. 다만 0건 케이스는 신규 사용자에게만 짧게 보이고, 컨테이너의 `space-y-4`로 분리되어 큰 위화감은 없을 것으로 예상.
- SectionCard 컴포넌트는 다른 섹션들이 계속 사용하므로 정의는 유지한다.

## 검증 방법

1. `pnpm -C app dev`로 개발 서버 기동 → 분석 탭 진입 → 제안이 1건 이상인 계정으로 확인
2. 회색 라운드 박스 및 "투자 방향성 제안" 타이틀이 보이지 않는지 확인
3. 제안 카드들이 SummaryCards와 "투자 성향 프로필" 사이에 적절한 간격으로 배치되는지 확인
4. `pnpm -C app exec tsc --noEmit` 통과 확인
