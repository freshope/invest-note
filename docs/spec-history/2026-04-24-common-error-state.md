> 완료: 2026-04-24

# Spec: 데이터 로드 오류 화면 통일 및 공통 ErrorState 컴포넌트 도입

## 배경 / 문제

네 개의 주요 탭(홈/기록/분석/설정)에서 데이터 로드 실패 시 보여주는 오류 UI가 제각각이다.

- 홈/기록/설정: 중앙 정렬된 "데이터를 불러오지 못했어요." + "다시 시도" 버튼(홈은 `underline`, 기록·설정은 `text-primary`로 버튼 스타일도 미세하게 다름).
- 분석: 빨간 경고 박스(`bg-red-50 border-red-200 text-red-600`)에 `"분석 데이터를 불러오는 중 오류가 발생했습니다"` 문자열만 표시. **재시도 버튼 없음** — `useAnalysisData`(`app/src/hooks/useAnalysisData.ts:10`)가 `refetch`를 반환하지 않기 때문.

현재 `src/components/shared/`에는 `AccountFilter.tsx` 하나만 있어 공통 오류 컴포넌트가 없다. 각 페이지가 `isError` 분기를 인라인으로 복사해 쓰고 있다.

## 목표

- 네 개 탭 모두 동일한 레이아웃/문구/재시도 동작을 보여준다(분석 탭 포함).
- `src/components/shared/ErrorState.tsx` 공통 컴포넌트를 추가하고, 홈·기록·분석·설정이 모두 이 컴포넌트를 사용한다.
- 분석 탭에서 "다시 시도" 버튼이 동작한다.

## 설계

### 접근 방식

1. **공통 `ErrorState` 컴포넌트 신설**
   - 경로: `app/src/components/shared/ErrorState.tsx`
   - Props: `message?: string`(기본 `"데이터를 불러오지 못했어요."`), `onRetry?: () => void`
   - 레이아웃: 기록/설정 패턴을 베이스로 함 — `className="px-5 pt-6 text-center space-y-3"`, 메시지는 `text-[13px] text-muted-foreground`, 버튼은 `text-primary text-[13px] font-medium` (다수파 스타일로 통일).
   - `PageHeader`는 포함하지 않음 — 각 페이지에서 `<PageHeader title="..." />`와 함께 렌더.

2. **각 탭을 `ErrorState`로 교체**
   - 홈(`components/home/HomeDashboard.tsx:43-59`): 인라인 오류 UI를 `<ErrorState onRetry={refetch} />`로 교체.
   - 기록(`app/(app)/records/page.tsx:30-46`): 인라인 → `<ErrorState onRetry={() => refetch()} />`.
   - 설정(`app/(app)/settings/page.tsx:32-48`): 인라인 → `<ErrorState onRetry={() => refetch()} />`.

3. **분석 탭 오류 처리 통일**
   - `useAnalysisData`에 `refetch` 추가 반환, `error: string | null` → `isError: boolean`으로 변경.
   - `AnalysisDashboard`: `isError` early return으로 `<PageHeader title="분석" />` + `<ErrorState onRetry={refetch} />` 렌더. 빨간 경고 박스 제거. 오류 상태에서 PeriodFilterTabs 숨김.

### 주요 변경 파일

- `app/src/components/shared/ErrorState.tsx` — 신규 생성
- `app/src/components/home/HomeDashboard.tsx` — 인라인 오류 UI → `ErrorState`
- `app/src/app/(app)/records/page.tsx` — 동일
- `app/src/app/(app)/settings/page.tsx` — 동일
- `app/src/hooks/useAnalysisData.ts` — `refetch` 추가, `isError` 반환
- `app/src/components/analysis/AnalysisDashboard.tsx` — `ErrorState` early return, 빨간 경고 박스 제거

## 구현 체크리스트

- [x] `app/src/components/shared/ErrorState.tsx` 생성 (message, onRetry props)
- [x] `HomeDashboard` 오류 분기를 `ErrorState`로 교체
- [x] `records/page.tsx` 오류 분기를 `ErrorState`로 교체
- [x] `settings/page.tsx` 오류 분기를 `ErrorState`로 교체
- [x] `useAnalysisData`에 `refetch` 추가, 반환 필드를 `isError`로 변경
- [x] `AnalysisDashboard` 오류 분기를 `ErrorState` early return 패턴으로 교체, 빨간 경고 박스 제거
- [x] 타입 체크 통과 (`pnpm tsc --noEmit`)
- [x] 수동 검증: 각 탭에서 네트워크 차단 후 오류 화면/재시도 동작 확인

## 우려사항 / 리스크

- **홈 탭 버튼 스타일 변경**: 기존 `underline`에서 `text-primary`로 바뀐다. 디자인 통일이 목적이므로 의도된 변경.
- **분석 탭 오류 메시지 변경**: `"분석 데이터를 불러오는 중 오류가 발생했습니다"` → `"데이터를 불러오지 못했어요."`. 일관성 우선.
- **분석 탭 헤더의 PeriodFilterTabs 숨김**: 오류 상태에서는 `<PageHeader title="분석" />`만 표시하고 기간 필터는 숨김(사용자 확정).
