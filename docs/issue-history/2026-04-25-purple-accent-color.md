> 완료: 2026-04-25

# Spec: 포인트 컬러 퍼플 전환

## 배경 / 문제

투자 기록 앱 아이콘 시안에서 퍼플 그라데이션 안이 최종 채택되었다.
앱 UI의 포인트 컬러(현재 토스 블루 `#3182F6`)를 시안의 퍼플 톤과 통일하기 위해 디자인 토큰을 일괄 변경한다.

## 목표

- 앱 전반(버튼, 포커스 링, 칩, FAB, 차트1, 사이드바)의 포인트 컬러가 violet-600 퍼플 `#7C3AED`로 표시된다
- 다크 모드에서도 동일하게 표시된다
- 모바일 브라우저 주소창 / PWA 설치 시 테마 컬러도 새 퍼플로 바뀐다
- 차트의 5번째 색이 새 primary와 시각적으로 구분된다 (현재 `#6C5CE7` 보라 → pink `#EC4899`로 교체)

## 설계

### 접근 방식

`globals.css` 의 CSS 변수 토큰만 변경하면 base 컴포넌트와 shadcn 컴포넌트 전반이 자동 반영된다.

### 주요 변경 파일

- `app/src/app/globals.css` — 라이트/다크 모드 포인트 컬러 토큰 변경
- `app/public/manifest.webmanifest` — `theme_color`, `background_color` 추가
- `app/src/app/layout.tsx` — `viewport` export에 `themeColor` 추가

## 구현 체크리스트

- [x] `app/src/app/globals.css` 라이트 모드(`:root`) 토큰 6개 퍼플로 교체 + `--chart-5` pink로 교체
- [x] `app/src/app/globals.css` 다크 모드(`.dark`) 토큰 5개 퍼플로 교체 + `--chart-5` pink로 교체
- [x] `app/public/manifest.webmanifest` 에 `theme_color`, `background_color` 추가
- [x] `app/src/app/layout.tsx` 에 `viewport` export로 `themeColor` 추가 (light/dark 배열)
- [x] `pnpm --filter app tsc --noEmit` 타입 체크 통과
- [x] `pnpm --filter app build` 빌드 성공 확인
- [x] 로컬 dev 서버에서 라이트/다크 모드 모두 시각 확인

## 우려사항 / 리스크

- 다크 모드 가독성: violet-600이 어두운 배경에서 약간 진해 보일 수 있음 → 후속 PR에서 분리 가능
- 네이티브 앱 아이콘 PNG/스플래시 재생성은 이번 범위 밖 (별도 spec)
- 증권사 브랜드 컬러(케이프 bg-purple-600, 신영 bg-violet-600) — 의미가 다른 영역이라 이번엔 손대지 않음
