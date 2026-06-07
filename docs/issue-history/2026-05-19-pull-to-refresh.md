# Spec: Pull-to-Refresh (당겨서 새로고침)

> 완료: 2026-05-19

## 배경 / 문제

모바일 사용자가 메인/거래내역/분석 페이지에서 최신 데이터를 보고 싶을 때 새로고침할 수단이 없다. React Query staleTime(2~5분)이 지나기 전까지 캐시된 데이터가 노출되어, 거래를 다른 디바이스에서 등록하거나 시세가 갱신된 직후 즉시 반영하기 어렵다. 네이티브 앱(Capacitor) UX에 익숙한 사용자는 화면을 위에서 아래로 당겨 새로고침하는 제스처를 기대한다.

## 목표

- 메인(`/`), 거래내역(`/records`), 분석(`/analysis`) 세 페이지에서 화면 최상단에서 아래로 당기면 해당 페이지의 주요 React Query 캐시가 invalidate되고 최신 데이터로 다시 그려진다.
- iOS Safari/Android Chrome WebView의 기본 pull-to-refresh 동작과 충돌하지 않는다 (브라우저 기본 동작 차단).
- 새로고침 중에는 시각적 인디케이터(스피너)가 노출되며, 완료되면 자연스럽게 사라진다.
- 다른 페이지(설정, 종목 상세 패널 등)에는 적용하지 않는다.

## 설계

### 접근 방식

- `react-simple-pull-to-refresh` 라이브러리를 fe에 추가한다 (커스텀 구현 대비 검증된 touch 핸들링/스크롤 감지 사용).
- 라이브러리를 직접 페이지에서 import하지 않고 `fe/src/components/shared/PullToRefresh.tsx` 공통 래퍼를 만들어 모든 페이지가 동일한 인디케이터/임계값/스타일을 공유하도록 한다 (기존 shared 디렉터리에 위치).
- 각 페이지는 본인의 데이터 훅이 반환하는 `refetch()`(또는 `queryClient.invalidateQueries` + `await`)를 onRefresh 콜백으로 전달한다.
- 브라우저 기본 새로고침 제스처는 `overscroll-behavior-y: contain` 으로 차단한다 (스크롤 컨테이너 = `body`).
- BottomNav가 fixed bottom에 있으므로 PullToRefresh wrapper는 `main` 내부 페이지 콘텐츠 영역만 감싼다.

### 페이지별 refetch 매핑

| 페이지 | 적용 위치 | invalidate / refetch 대상 |
|--------|----------|--------------------------|
| 메인 `/` | `fe/src/components/home/HomeDashboard.tsx` | `usePortfolioSummary().refetch()` |
| 거래내역 `/records` | `fe/src/app/(app)/records/page.tsx` | `queryKeys.trades` refetch (기존 `refetch()` 활용) |
| 분석 `/analysis` | `fe/src/components/analysis/AnalysisDashboard.tsx` | `useAnalysisData(period).refetch()` |

### 주요 변경 파일

- `fe/package.json` — `react-simple-pull-to-refresh` 의존성 추가
- `fe/src/components/shared/PullToRefresh.tsx` — 공통 래퍼 컴포넌트 신규 작성 (children + onRefresh prop, 일관된 스피너/임계값)
- `fe/src/components/home/HomeDashboard.tsx` — 콘텐츠 최외곽을 PullToRefresh로 감싸고 portfolioSummary refetch 연결
- `fe/src/app/(app)/records/page.tsx` — useQuery refetch 활용해 PullToRefresh 적용
- `fe/src/components/analysis/AnalysisDashboard.tsx` — useAnalysisData refetch 연결
- `fe/src/app/globals.css` — `html, body { overscroll-behavior-y: contain; }` 추가해 브라우저 기본 pull 차단

## 구현 체크리스트

- [x] `pnpm -C fe add react-simple-pull-to-refresh` 의존성 설치 (v1.3.4)
- [x] `fe/src/components/shared/PullToRefresh.tsx` 공통 래퍼 작성
- [x] `fe/src/app/globals.css` 에 `overscroll-behavior-y: contain` 추가
- [x] 메인 페이지(`fe/src/components/home/HomeDashboard.tsx`)에 PullToRefresh 적용
- [x] 거래내역(`fe/src/app/(app)/records/page.tsx`)에 PullToRefresh 적용
- [x] 분석(`fe/src/components/analysis/AnalysisDashboard.tsx`)에 PullToRefresh 적용
- [x] 타입 체크 통과 (`pnpm -C fe exec tsc --noEmit` exit 0)
- [x] Production 빌드 통과 (모든 라우트 정적 prerender)
- [ ] 실기기/Chrome DevTools 모바일 에뮬레이션에서 3개 페이지 풀-다운 제스처 검증 (사용자 확인)

## 우려사항 / 리스크

- 라이브러리의 `.ptr / .ptr__children { height:100%; overflow:hidden }`이 PageHeader의 `sticky top-0`의 가까운 스크롤 컨테이너를 `ptr__children`으로 바꿔 sticky가 깨지는 문제 발견 → `globals.css`에서 `.ptr, .ptr__children { height: auto !important; overflow: visible !important; }` override로 해결. 라이브러리는 boundingRect.top 기반으로 pull 여부를 판단하므로 동작에 영향 없음.
- 드래그 중 라이브러리가 `ptr__children`에 `transform: translate(0, Y)`를 적용 → transform된 element는 sticky descendants의 새 containing block이 되어 sticky 헤더가 콘텐츠와 함께 잠깐 내려옴(의도와 일치).
- iOS Safari의 시스템 overscroll bounce가 라이브러리 transform 처리와 충돌하면 `body`의 `overscroll-behavior-y` 외에 추가 조정이 필요할 수 있다.
- 빌드는 통과했지만 모바일 터치 제스처는 자동 검증이 어려워 사용자 실기기 확인이 필수.
