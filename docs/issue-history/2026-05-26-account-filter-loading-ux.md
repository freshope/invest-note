# Spec: 계좌 필터 변경 시 스켈레톤 + 헤더 숫자 count-up

> 완료: 2026-05-26

## 배경 / 문제

메인 대시보드는 `usePortfolioSummary`에 `placeholderData: keepPreviousData`를 걸어두어, 계좌 필터(칩)를 바꾸면 **스켈레톤이 전혀 뜨지 않고** 이전 계좌의 데이터가 그대로 보이다가 새 데이터로 순간 교체된다. 로딩 피드백이 없고, 다른 계좌 숫자가 잠깐 남아 혼동을 준다.

원하는 동작:
- **본문(body)**: 계좌 필터 변경으로 데이터를 다시 로드하는 동안 **스켈레톤**을 보여준다.
- **헤더 숫자 3개(총자산 / 주식 / 예수금)**: 스켈레톤 대신 **이전 값 → 새 값으로 count-up 애니메이션**. 초기 진입 시에도 0 → 값으로 count-up.

`keepPreviousData`는 유지 — 이전 계좌의 totals가 헤더 count-up의 "시작 값" 역할을 하므로 이 옵션이 헤더 count-up의 from 값을 제공하는 용도로 재활용된다.

## 목표 (완료 기준)

- 계좌 2개 이상일 때 필터 칩을 바꾸면 새 데이터 도착 전까지 **본문에 BodySkeleton**이 보인다.
- 같은 구간 동안 **헤더 3개 숫자는 스켈레톤이 아니라** 이전 값을 유지하다 새 데이터 도착 시 **count-up**.
- 앱 최초 진입 시 헤더 숫자가 0 → 실제 값으로 count-up.
- 풀투리프레시(같은 계좌 재조회)에서는 **본문 스켈레톤이 뜨지 않는다**(기존 깜박임 방지 유지).
- 타입 체크 통과 (`pnpm -C fe exec tsc --noEmit`).

## 설계

### 접근 방식

1. **로딩 신호 분리** — react-query의 `isPlaceholderData` 활용.
   - 초기 로드: `isPending=true`, `isPlaceholderData=false` → 헤더·본문 모두 스켈레톤.
   - 필터 변경: `isPending=false`, `isPlaceholderData=true` → **본문만 스켈레톤**, 헤더는 placeholder 숫자 유지하다 count-up.
   - 풀투리프레시(같은 키): `isPlaceholderData=false` → 본문 스켈레톤 안 뜸.

2. **count-up 라이브러리** — `react-countup`(`countup.js` 기반) 도입.
   - `preserveValue`로 `end` 변경 시 직전 값 → 새 값 애니메이션.
   - 초기 마운트 `start`(0) → `end`.
   - `formattingFn`에 기존 `fmt()` 연결.

3. **의도된 비대칭** — 필터 변경 직후 본문이 스켈레톤인 동안 헤더는 이전 계좌 숫자를 보여주고, 새 데이터 도착 시 count-up + 본문 채워짐이 동시에 일어난다. count-up의 from 값을 만들기 위한 의도된 동작.

### 주요 변경 파일

- `fe/package.json` — `react-countup` 추가.
- `fe/src/hooks/usePortfolioSummary.ts` — `isPlaceholderData` 꺼내 `reloading`으로 반환(추가만, non-breaking).
- `fe/src/components/shared/CountUpNumber.tsx` — 신규. react-countup 래퍼(`duration` 0.6s, `preserveValue`, `formattingFn={fmt}`, reduced-motion 시 즉시 표시).
- `fe/src/components/home/DashboardSummary.tsx` — `DashboardTitle` 3개 숫자를 `CountUpNumber`로 교체.
- `fe/src/components/home/HomeDashboard.tsx` — `reloading` 구조분해, body 가드 `loading || reloading`. 헤더 가드는 변경 없음.

## 구현 체크리스트

- [x] `pnpm -C fe add react-countup` (6.5.3)
- [x] `usePortfolioSummary.ts` — `reloading: isPlaceholderData` 반환
- [x] `CountUpNumber.tsx` 신규 (react-countup 래퍼 + reduced-motion)
- [x] `DashboardSummary.tsx` — `DashboardTitle` 3개 숫자 `CountUpNumber`로 교체
- [x] `HomeDashboard.tsx` — body 가드 `loading || reloading`
- [x] 타입 체크 통과 (`pnpm -C fe exec tsc --noEmit`) — lint 0 error, build 성공, vitest 144 passed
- [x] 수동 검증: 칩 전환 시 본문 스켈레톤 + 헤더 count-up / 풀투리프레시 시 본문 스켈레톤 안 뜸 (사용자 직접 확인)

## 우려사항 / 리스크

- react-countup React 19 호환 — 설치 후 타입체크/렌더 확인.
- 빠른 연속 칩 전환 시 `preserveValue` 동작 — `key` 재마운트 금지(from 값 손실).
- 본문 스켈레톤 정책 변경 — 풀투리프레시 경로는 `isPlaceholderData` 기반이라 영향 없음.
