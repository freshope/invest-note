# Spec: BreakdownList<T> 통합 (FE simplify Round 6)

## 배경 / 문제

`docs/backlog.md` 의 "FE simplify · 컴포넌트 추출 (중복 제거)" 섹션에서 Round 5(`ProgressTrack`)까지 처리 완료. Round 6 첫 작업으로 `BreakdownList<T>` 통합을 진행한다.

분석 탭의 3개 Breakdown 컴포넌트(`EmotionBreakdown` / `StrategyBreakdown` / `ReasoningBreakdown`)가 동일한 구조를 가진다 — `others + untagged` 분리, `space-y-3` 리스트, 각 항목의 `라벨 + count + PnLLine + WinRateBar` 마크업. 이 구조 중복(약 30~40줄)을 제네릭 콜백 기반 단일 컴포넌트로 통합하여, 향후 새로운 Breakdown 추가 시 마크업 재작성을 피하고 시각적 일관성을 유지한다.

차이점:
- **key 필드**: `type` (Emotion/Strategy) vs `tag` (Reasoning)
- **untagged 상수**: `UNTAGGED_KEY` (Emotion/Reasoning) vs `STRATEGY_UNKNOWN_KEY` (Strategy)
- **라벨 맵**: `EMOTION_LABELS` / `STRATEGY_LABELS` / `REASONING_TAG_LABELS`
- **Strategy 한정**: `avgHoldingDays > 0` 인라인 span 추가
- **Reasoning 한정**: 외곽에 헤더 텍스트 + 경고 박스 (feelingRate/missingTagRate)
- **hasData 계산**: Emotion/Strategy = `resultCount > 0`, Reasoning = `count > 0`
- **WinRateBar emptyLabel**: Emotion = `"결과 미입력"`, 나머지 = 기본값 `"결과 없음"`
- **빈 상태 메시지**: 각 컴포넌트별 다름

## 목표

- 3개 Breakdown 컴포넌트의 리스트 마크업이 단일 `BreakdownList<T>` 제네릭 컴포넌트로 추출되어 재사용된다.
- 각 Wrapper(`EmotionBreakdown` / `StrategyBreakdown` / `ReasoningBreakdown`)는 `BreakdownList`에 콜백을 주입하는 얇은 어댑터 역할만 한다.
- 외부 API(props·사용처)는 변경 없음 — `AnalysisDashboard`에서 동일하게 사용.
- 시각적 출력(렌더링 결과) 동일 — 데이터별 빈 상태/경고/메타가 모두 보존됨.
- 타입 체크 통과 (`pnpm tsc --noEmit`).

## 설계

### 접근 방식

- **리스트 렌더링만 추출**, Wrapper 컴포넌트는 유지 — Reasoning의 헤더/경고 같은 도메인 특화 chrome은 Wrapper에 남기고, `BreakdownList`는 `data → sorted list of rows`만 책임.
- 제네릭 `BreakdownList<T>`는 콜백 props로 type 차이를 흡수 — `getKey`, `isUntagged`, `getLabel`, `getStats`, `renderMeta`(선택), `emptyMessage`, `emptyRateLabel`(선택).
- `getStats`는 `{ count, sumPnL, winRate, hasData }` 단일 객체 반환 — `hasData` 계산 차이(Emotion/Strategy의 `resultCount > 0` vs Reasoning의 `count > 0`)를 callback 내부에서 결정.
- 빈 상태(`data.length === 0`)도 `BreakdownList` 내부에서 처리 — `emptyMessage` prop으로 텍스트만 다르게.
- `PnLLine` / `WinRateBar`는 그대로 사용 (수정 없음).

### Props 시그니처

```tsx
interface BreakdownListProps<T> {
  data: T[];
  emptyMessage: string;
  getKey: (item: T) => string;
  isUntagged: (item: T) => boolean;
  getLabel: (item: T) => string;
  getStats: (item: T) => {
    count: number;
    sumPnL: number;
    winRate: number;
    hasData: boolean;
  };
  renderMeta?: (item: T) => ReactNode;
  emptyRateLabel?: string;
}
```

### 주요 변경 파일

- `app/src/components/analysis/BreakdownList.tsx` — **신규**. 제네릭 리스트 컴포넌트.
- `app/src/components/analysis/EmotionBreakdown.tsx` — `BreakdownList<EmotionStats>` 호출로 본문 교체.
- `app/src/components/analysis/StrategyBreakdown.tsx` — `BreakdownList<StrategyStats>` + `renderMeta` (avgHoldingDays inline span) 주입.
- `app/src/components/analysis/ReasoningBreakdown.tsx` — 외곽 헤더 + 경고 박스 유지, 가운데에 `BreakdownList<TagStats>` 끼움.

### 재사용 검토

- `PnLLine` (`analysis/PnLLine.tsx`) — 그대로 사용.
- `WinRateBar` (`analysis/WinRateBar.tsx`) — 그대로 사용. 이미 Round 5에서 `ProgressTrack` 기반으로 정리됨.
- 라벨/상수(`EMOTION_LABELS`, `STRATEGY_LABELS`, `REASONING_TAG_LABELS`, `UNTAGGED_KEY`, `STRATEGY_UNKNOWN_KEY`) — Wrapper에서 콜백으로 주입.
- 위치는 `analysis/` 폴더(도메인 특화) — `PnLLine`/`WinRateBar`와 같은 위치. Round 2~5의 `shared/` 패턴과 다른 이유: `BreakdownList`가 `PnLLine`/`WinRateBar`라는 analysis 한정 컴포넌트에 의존.

## 구현 체크리스트

- [x] `app/src/components/analysis/BreakdownList.tsx` 신규 작성 (제네릭 props, 빈 상태/정렬/리스트 렌더)
- [x] `EmotionBreakdown.tsx` 를 `BreakdownList<EmotionStats>` 사용하도록 리팩터
- [x] `StrategyBreakdown.tsx` 를 `BreakdownList<StrategyStats>` + `renderMeta` 사용하도록 리팩터
- [x] `ReasoningBreakdown.tsx` 를 외곽 헤더+경고 유지, `BreakdownList<TagStats>` 사용하도록 리팩터
- [x] 타입 체크 통과 (`pnpm -C app exec tsc --noEmit`)
- [ ] 분석 탭 시각 회귀 확인 (감정/전략/근거 패널의 리스트·빈 상태·경고 박스 정상)
- [ ] `docs/backlog.md` Round 6 진행 표시 + `docs/spec-current.md` → `docs/spec-history/` 이동

## 우려사항 / 리스크

- **시각 회귀 가능성 낮음** — 각 항목 마크업·className 문자열을 동일하게 유지. 빈 상태 텍스트는 `emptyMessage` prop으로 정확히 보존.
- **Reasoning 외곽 chrome 보존** — 헤더 안내 문구(`한 거래가 여러 태그...`)와 경고 박스(`AlertTriangle`)는 Wrapper에 남기고 `BreakdownList`를 가운데에만 끼우므로 `space-y-3` 간격 유지됨.
- **빈 상태 패딩 미세 차이** — Reasoning 빈 상태는 현재 `py-4`, Emotion/Strategy는 `py-6`. `BreakdownList`는 통일해서 `py-6` 채택(주 사용처 패턴) — Reasoning 빈 상태가 약간 커지지만 Wrapper에서 외곽 헤더가 있어 시각 균형은 오히려 개선됨. 위험도 낮음.
- **avgHoldingDays inline 위치** — Strategy의 메타 span은 라벨 옆 `<div>` 컨테이너 안에 있는 sibling. `renderMeta`는 라벨과 같은 컨테이너에 배치되도록 `BreakdownList` 내부에서 라벨 옆에 렌더 — wrapping 구조를 명확히 일치시켜 회귀 방지.

## 검증

1. `pnpm -C app exec tsc --noEmit` 통과.
2. `pnpm -C app dev` 실행 후 분석 탭 진입:
   - 감정 분포 패널: 라벨/카운트/손익/승률 바 정상, 데이터 없을 때 "감정 데이터가 없습니다" 표시
   - 전략 분포 패널: 평균 N일 보유 메타가 라벨 옆 정상 표시, 데이터 없을 때 "전략 데이터가 없습니다"
   - 근거 분포 패널: 외곽 안내문 + 경고 박스(feelingRate≥40 또는 missingTagRate≥30 시) 정상 표시, 빈 데이터 시 "매칭된 태그 데이터가 없습니다"
3. untagged 항목이 항상 마지막에 표시되는지 확인 (3패널 모두).
