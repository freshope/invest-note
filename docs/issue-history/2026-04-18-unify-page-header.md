> 완료: 2026-04-18

# 탭 타이틀 영역 통일 (Page Header Unification)

## 배경 / 목적

4개 탭(홈/기록/분석/설정)의 상단 타이틀/헤더 구현이 제각각이다.
기록 탭만 올바른 sticky 헤더를 갖고 있으며, 다른 탭들은 타이틀이 없거나 sticky 처리가 안 되어 있다.
공용 `PageHeader` 컴포넌트를 도입해 4개 탭의 타이틀 영역을 통일한다.

## 범위

| 탭 | 변경 내용 |
|---|---|
| 홈 | 총자산+주식/예수금 subline을 PageHeader children으로 sticky 고정. 손익 3-grid는 스크롤 본문 |
| 기록 | 인라인 sticky div → PageHeader (시각 동일, iOS safe-area 대응 추가) |
| 분석 | "분석" 타이틀 추가 + PeriodFilterTabs compact를 actions에 배치 |
| 설정 | h1 sticky 아님 + 24px → PageHeader sticky + 20px 통일 |

## 공용 컴포넌트 API

`src/components/layout/PageHeader.tsx`

```tsx
interface PageHeaderProps {
  title?: ReactNode;    // 기록/설정/분석 — 텍스트 타이틀
  actions?: ReactNode;  // 오른쪽 액션 영역 (버튼, 토글)
  children?: ReactNode; // 홈 — 내부 레이아웃 완전 대체
  sticky?: boolean;     // 기본 true
  className?: string;
}
```

- sticky + bg-background + `paddingTop: calc(1.5rem + env(safe-area-inset-top))`
- z-index: z-10 (BottomNav z-50, FAB z-20보다 낮음)
- 서버 컴포넌트에서도 사용 가능

## 구현 체크리스트

- [x] `src/components/layout/PageHeader.tsx` 신규
- [x] `src/components/records/TradeList.tsx` — PageHeader 교체
- [x] `src/app/(app)/settings/page.tsx` — PageHeader 교체
- [x] `src/components/analysis/PeriodFilterTabs.tsx` — compact prop 추가
- [x] `src/components/analysis/AnalysisDashboard.tsx` — PageHeader 적용
- [x] `src/components/home/DashboardSummary.tsx` — DashboardTitle/DashboardBody 분리
- [x] `src/components/home/HomeDashboard.tsx` — PageHeader 재조립

## 결정 사항

- 분석 탭 기간 토글: compact 세그먼트 (1M/3M/6M/YTD/전체, h-7 text-[11px])
- iOS safe-area-inset-top: 이번 PR에 포함 (PageHeader 단일 진입점)
- 설정 탭 폰트: 24px → 20px 통일

## QA 체크리스트

- [x] 4개 탭 sticky 헤더 동작 확인
- [x] 홈 탭: 총자산 고정, 손익 3-grid 스크롤
- [x] 분석 탭: compact 세그먼트 5개 한 줄 수용 (375px 포함)
- [x] iOS Safari safe-area-inset-top 반영 확인
- [x] BottomNav/FAB z-index 충돌 없음
