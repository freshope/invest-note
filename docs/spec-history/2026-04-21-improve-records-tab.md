> 완료: 2026-04-21

# Spec: 거래 기록 탭 UX 개선

## 배경 / 문제

`/records` 탭(UI 제목 "기록")의 세 가지 UX 문제 해결:

1. 거래가 쌓이면 특정 계좌만 확인하기 어려움 — 계좌 필터 부재.
2. "CSV 업로드" 버튼은 실제로 `.csv/.xlsx/.xls` 모두 받지만 명칭이 CSV로 한정되어 오해 유발.
3. 업로드 기능은 미구현인데 파일 다이얼로그를 먼저 띄우고 `window.alert`로 안내 — 사용자 혼란.

## 목표

- 거래 목록 헤더에서 계좌를 선택해 해당 계좌의 거래만 볼 수 있다.
- 업로드 버튼 라벨이 **"파일 업로드"** 로 표시된다.
- 업로드 버튼 클릭 시 파일 다이얼로그가 뜨지 않고, **토스트로 "파일 업로드는 준비중"** 안내가 뜬다.

## 설계

### 접근 방식

- **계좌 필터**: `base/Select` 드롭다운 (`"전체 계좌"` + 계좌 목록). 로컬 `useState`로 관리.
- **토스트**: `sonner` 도입. 루트 `src/app/layout.tsx`에 `<Toaster />` 마운트.
- **업로드 버튼**: 숨겨진 `<input type="file">` + `useRef` 제거. 클릭 즉시 `toast.info`.
- **데이터**: `/records` 서버 페이지가 이미 `accounts`를 props로 내려주므로 추가 쿼리 불필요.
- **상세 패널 회귀 방지**: `openTrade({ allTrades })`는 필터와 무관하게 원본 `trades` 전달.

### 주요 변경 파일

- `package.json` / lockfile — `sonner` 의존성 추가
- `src/app/layout.tsx` — `<Toaster />` 마운트
- `src/components/records/CsvUploadButton.tsx` — 라벨 "파일 업로드"로 변경, 숨은 input 제거, sonner 호출
- `src/components/records/TradeList.tsx` — 계좌 필터 state, 필터링, `PageHeader` actions에 필터+버튼 병치, 빈 상태 분기 개선
- `src/components/records/AccountFilter.tsx` — 신규, `base/Select` 래퍼

## 구현 체크리스트

- [x] `pnpm add sonner` 설치
- [x] `src/app/layout.tsx`에 `<Toaster position="top-center" richColors />` 마운트
- [x] `src/components/records/CsvUploadButton.tsx` — 라벨/동작 교체, 숨은 input 제거
- [x] `src/components/records/AccountFilter.tsx` 신규 작성 (`base/Select` 기반)
- [x] `src/components/records/TradeList.tsx` — 필터 state·필터링·헤더 actions·빈 상태 분기 수정
- [x] 타입 체크 통과 (`pnpm tsc --noEmit`)
- [x] dev 서버 확인: 전체/계좌 필터 전환, 업로드 토스트, FAB/상세 패널 회귀 없음

## 우려사항 / 리스크

- `sonner` 최신 버전의 React 19 / Next 15 호환성: 이슈 발생 시 `react-hot-toast`로 대체.
- 필터 결과 0건일 때 빈 상태 문구: "선택한 계좌의 기록이 없어요"로 구분.
- 필터 상태가 URL에 남지 않음 (새로고침 시 초기화 — 현 프로젝트 패턴과 일치).
