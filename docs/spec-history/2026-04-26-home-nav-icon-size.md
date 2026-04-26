# 홈 네비게이션 아이콘 크기 조정

## 목표

하단 네비게이션의 홈 아이콘이 다른 아이콘보다 커 보이지 않도록 조금 더 작게 조정한다.

## 범위

- `NavHomeIcon` 내부 스케일만 변경한다.
- 다른 네비게이션 아이콘과 레이아웃은 유지한다.

## 검증

- 홈 아이콘 렌더링 코드가 기존 `currentColor` 동작을 유지한다.
- `npx eslint src/components/base/NavIcons.tsx` 통과.
