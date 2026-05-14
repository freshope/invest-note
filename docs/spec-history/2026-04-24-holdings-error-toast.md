> 완료: 2026-04-24

# Spec: HoldingsList fetch 에러 시 토스트 연동

## 배경 / 문제

`HoldingsList` 카드 탭 시 `tradesApi.list()` 실패하면 빈 `catch` 후 빈 배열로 `openStock`을 호출해 빈 Stock 패널이 열린다. 사용자는 "데이터 없음"과 "에러"를 구별할 수 없다.

## 목표

- fetch 실패 시 Stock 패널이 열리지 않는다.
- 에러 유형별 토스트가 표시된다: 401 → 재로그인 안내 / 5xx → 서버 오류 / 네트워크 실패 → 연결 확인.
- 기존 `apiFetch` 호출처 회귀 없음.

## 설계

### 접근 방식

- `ApiError extends Error { status: number }` 클래스를 `api-client.ts`에 도입. non-OK 응답 시 기존 `Error` 대신 `ApiError` throw.
- `HoldingsList.handleCardPress` catch에서 `instanceof ApiError`로 분기, `toast.error`로 안내 후 함수 종료 (패널 미오픈).

### 주요 변경 파일

- `app/src/lib/api-client.ts` — `ApiError` 클래스 추가, `apiFetch` throw 교체
- `app/src/components/home/HoldingsList.tsx` — catch 블록 교체 (토스트 + 미오픈)

## 구현 체크리스트

- [x] `src/lib/api-client.ts` — `ApiError` 클래스 추가 및 `apiFetch` throw 변경
- [x] `src/components/home/HoldingsList.tsx` — catch 블록 교체 (토스트 + 미오픈)
- [x] 타입 체크 — 기존 pre-existing 오류 2건 외 신규 오류 없음

## 우려사항 / 리스크

- `ApiError extends Error` 이므로 기존 `err.message` 사용 코드와 호환 유지.
