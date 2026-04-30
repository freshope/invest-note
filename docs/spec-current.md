# Spec: 분석 탭 "투자 방향성 제안" 중복 제거

## 배경 / 문제

분석 탭(`/analysis`)에서 동일한 `suggestionsData.suggestions` 데이터를 두 곳에서 다른 형태로 노출하고 있어 사용자가 "투자 방향성 제안이 중복으로 보인다"고 인식한다.

**현재 두 위치의 차이:**

| 항목 | 상단 (섹션 2, "투자 성향 프로필" 바로 위) | 하단 (섹션 10, 마지막) |
|------|--------|--------|
| 컴포넌트 | `InsightHighlights` | `SuggestionList` (in `SectionCard`) |
| 섹션 제목 | 없음 | "투자 방향성 제안" 명시 |
| 표시 개수 | 상위 3개 (`slice(0, 3)`) | 전체 |
| metric 값 | 표시 안 함 | 우상단에 표시 (수치) |
| 컨테이너 | 카드 직접 노출 (제목 X) | `SectionCard` (`bg-muted/60`) |
| 빈 상태 | 0개면 렌더링 안 함 | "아직 특이 패턴이 감지되지 않았어요" |

데이터 소스가 같으면서 표현만 다르게 두 번 노출되어 정보가 중복되고 페이지가 불필요하게 길어진다.

## 목표

- 분석 탭에 "투자 방향성 제안" 섹션이 **상단(투자 성향 프로필 바로 위) 한 곳에만** 노출된다.
- 상단 섹션은 "투자 방향성 제안" 제목을 갖고, 전체 suggestions를 metric 포함하여 표시한다 (= 기존 하단 섹션의 정보량을 상단 위치로 이동).
- 하단의 동일 섹션은 제거된다.
- 사용되지 않게 된 `InsightHighlights` 컴포넌트와 `InsightSection` 헬퍼는 정리된다.
- 타입 체크가 통과한다.

## 설계

### 접근 방식

`AnalysisDashboard.tsx`의 섹션 2 위치(`InsightSection`)에 하단 섹션 10과 동일한 `SectionCard title="투자 방향성 제안"` + `SuggestionList`를 배치하고, 하단 섹션 10은 제거한다. 정보 손실 없이 노출 위치만 상단으로 이동하는 방식.

- 상단 노출 조건: `suggestionsData`가 있을 때 (= 하단의 기존 조건과 동일).
- `SuggestionList`는 빈 배열일 때 자체적으로 "아직 특이 패턴이 감지되지 않았어요"를 표시하므로, 데이터가 비어 있어도 일관된 빈 상태 UX 제공.
- `InsightHighlights.tsx`와 `InsightSection` 인라인 함수, 관련 import는 모두 제거.

### 주요 변경 파일

- `app/src/components/analysis/AnalysisDashboard.tsx`
  - 섹션 2: `<InsightSection ... />` → `<SectionCard title="투자 방향성 제안"><SuggestionList ... /></SectionCard>`로 교체 (조건: `suggestionsData &&`)
  - 섹션 10: 동일 SectionCard 블록 제거
  - `InsightHighlights` import 제거, `InsightSection` 인라인 함수 제거, `SuggestionsData` 타입 import도 더 이상 사용되지 않으면 제거
- `app/src/components/analysis/InsightHighlights.tsx`
  - 파일 삭제 (다른 곳에서 사용되지 않음 — `grep`으로 확인됨)

### 재사용하는 기존 자산

- `SectionCard` (in `AnalysisDashboard.tsx`) — 다른 모든 분석 섹션과 동일한 스타일링 일관성 유지.
- `SuggestionList` (`app/src/components/analysis/SuggestionList.tsx`) — 그대로 사용. 변경 없음.
- `severity-styles.ts` — 그대로 사용.

## 구현 체크리스트

- [ ] `AnalysisDashboard.tsx` 섹션 2를 `SectionCard` + `SuggestionList`로 교체하고 `suggestionsData &&` 가드 추가
- [ ] `AnalysisDashboard.tsx` 섹션 10 (기존 "투자 방향성 제안" SectionCard) 제거
- [ ] `AnalysisDashboard.tsx`에서 `InsightHighlights` import 및 `InsightSection` 인라인 함수, 미사용된 `SuggestionsData` 타입 import 제거
- [ ] `app/src/components/analysis/InsightHighlights.tsx` 파일 삭제
- [ ] 타입 체크 통과 (`pnpm -C app exec tsc --noEmit`)

## 검증 방법

1. **타입 체크**: `pnpm -C app exec tsc --noEmit` — 에러 없이 통과
2. **수동 확인** (`pnpm -C app dev` 후 `/analysis`):
   - 분석 탭에 "투자 방향성 제안" 섹션이 **딱 한 번**, "투자 성향 프로필" 섹션 바로 **위**에 노출된다
   - 다른 분석 섹션(`SectionCard`)과 동일한 회색 배경 컨테이너 + 제목 스타일을 따른다
   - 제안이 4개 이상이어도 모두 표시되고, metric이 있는 항목은 우상단에 수치가 보인다
   - 제안이 0개일 때 "아직 특이 패턴이 감지되지 않았어요" 문구가 보인다
   - 페이지 하단(거래 패턴 상세 다음)에는 더 이상 "투자 방향성 제안" 섹션이 없다

## 우려사항 / 리스크

- 상단에서 `InsightHighlights`(상위 3개, 컴팩트)를 본 사용자에게 정보량이 늘어나는 변화가 발생함. 다만 사용자가 명시적으로 "상단에만 유지(통합)"을 선택했으므로 의도된 변경.
- `InsightHighlights.tsx`를 삭제하는데, `grep`상 다른 사용처는 없음 — 안전.
