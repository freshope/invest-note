# Spec: ProgressTrack 추출 (FE simplify Round 5)

> 완료: 2026-05-01

## 배경 / 문제

`docs/backlog.md` 의 "FE simplify · 컴포넌트 추출" 섹션에서 도출된 후속 항목. Round 4 (TradeTypeBadge) 까지 처리 완료. Round 5 첫 작업으로 `ProgressTrack` 추출을 진행.

`WinRateBar` / `WeightBar` (DiversificationPanel 내부) / `QualityBar` (ReviewQualityPanel 내부) 세 컴포넌트가 동일한 진행률 바 마크업을 중복 사용하고 있음:

```tsx
<div className="h-1.5 rounded-full bg-muted overflow-hidden">
  <div className={cn("h-full rounded-full", color)} style={{ width: `${pct}%` }} />
</div>
```

3 곳 동일 마크업 + 색상 임계치 분기가 WinRateBar(65/40)·QualityBar(70/40) 두 곳에 중복.

## 목표

- 진행률 트랙 마크업이 단일 컴포넌트(`ProgressTrack`)로 추출되어 3 곳에서 재사용된다.
- 색상 임계치 분기가 헬퍼 함수(`pickRateColor`)로 추출되어 WinRateBar·QualityBar 가 공유한다.
- 기존 컴포넌트(`WinRateBar`/`WeightBar`/`QualityBar`)의 외부 API(props·사용처)는 변경 없음.
- 시각적 출력(렌더링 결과) 동일.
- 타입 체크 통과(`pnpm tsc --noEmit`).

## 설계

### 접근 방식

- **트랙 마크업만 추출**, 각 Bar 컴포넌트 자체는 통합하지 않음 — Bar 별로 라벨 레이아웃과 외부 props 가 달라 통합 시 추상화 비용이 가치보다 큼.
- `ProgressTrack` 은 `pct: number` + `colorClass: string` 만 받는 단일 책임 컴포넌트. Tailwind 클래스 문자열을 그대로 받아 트랙 안쪽 div 의 배경으로 적용.
- 색상 임계치는 `pickRateColor(rate, { win, loss })` 헬퍼로 추출. WinRateBar(65/40)·QualityBar(70/40) 임계치를 인자로 받아 공유. 반환값은 `{ bg, text }` 페어.
- WeightBar 는 단색 (`bg-[var(--chart-1)]`) 이라 헬퍼 사용 안 함, ProgressTrack 만 사용.

### 주요 변경 파일

- `app/src/components/shared/ProgressTrack.tsx` — **신규**. 트랙 컴포넌트.
- `app/src/lib/analysis/rate-color.ts` — **신규**. `pickRateColor` 헬퍼.
- `app/src/components/analysis/WinRateBar.tsx` — 트랙 마크업 → `<ProgressTrack/>`, 색상 분기 → `pickRateColor` 호출.
- `app/src/components/analysis/DiversificationPanel.tsx` — 내부 `WeightBar` 의 트랙 마크업 → `<ProgressTrack/>`.
- `app/src/components/analysis/ReviewQualityPanel.tsx` — 내부 `QualityBar` 의 트랙 마크업 → `<ProgressTrack/>`, 색상 분기 → `pickRateColor` 호출.

### 재사용 검토

- 기존 헬퍼 위치 검색 결과 색상 임계치 헬퍼 부재. `WIN_THRESHOLD`/`LOSS_THRESHOLD` 상수는 `app/src/lib/constants/analysis.ts` 에 이미 존재 — `pickRateColor` 의 기본 인자로 활용.
- `PNL_COLORS` (`app/src/lib/constants/colors.ts`) 그대로 재사용.

## 구현 체크리스트

- [x] `app/src/components/shared/ProgressTrack.tsx` 신규 작성 (pct + colorClass props, h-1.5 트랙 마크업)
- [x] `app/src/lib/analysis/rate-color.ts` 신규 작성 (`pickRateColor` 헬퍼, 임계치 인자)
- [x] `WinRateBar.tsx` 를 `ProgressTrack` + `pickRateColor` 사용하도록 리팩터
- [x] `DiversificationPanel.tsx` 의 `WeightBar` 가 `ProgressTrack` 사용하도록 리팩터
- [x] `ReviewQualityPanel.tsx` 의 `QualityBar` 가 `ProgressTrack` + `pickRateColor` 사용하도록 리팩터
- [x] 타입 체크 통과 (`pnpm tsc --noEmit`)
- [x] 분석 탭 시각 회귀 확인 (분석 페이지에서 승률 바 / 분산 바 / 품질 바 정상 표시)
- [x] `docs/backlog.md` Round 5 진행 표시 + `docs/issue-current.md` → `docs/issue-history/` 이동

## 우려사항 / 리스크

- **시각 회귀 가능성 낮음** — 마크업/클래스 문자열을 동일하게 유지하고 단순 추출이라 출력 차이가 발생하기 어려움.
- **임계치 분기 통합** — WinRateBar(65/40, "결과 없음" 처리·flex 외곽 포함)와 QualityBar(70/40)는 색상 분기 로직이 동일 형태이지만 임계치 값이 달라 헬퍼 인자로 받도록 함. 무리한 통합 회피.
- **WeightBar 단색** — `bg-[var(--chart-1)]` 단색이라 색상 헬퍼 사용 안 하고 ProgressTrack 만 사용. 향후 다색 요구 시 colorClass 만 바꾸면 됨.

## 검증

1. `pnpm -C app exec tsc --noEmit` 통과.
2. `pnpm -C app dev` 실행 후 분석 탭 진입 — 승률 분포 / 분산 / 품질 패널의 진행률 바가 변경 전과 동일하게 표시되는지 시각 확인.
3. 공통 검토: `WinRateBar` 의 `hasData=false` 분기, `QualityBar` 의 임계치 70/40 분기, `WeightBar` 의 단색 분기가 모두 정상 렌더되는지 분석 페이지에서 데이터별로 확인.
