# 네비게이션 active brand 컬러 적용

## 목표

하단 네비게이션의 active 상태 텍스트와 아이콘 색상을 brand 컬러로 표시한다.

## 범위

- `BottomNav`의 active 색상만 변경한다.
- 기존 라우팅 판별, 폰트 굵기, inactive 색상은 유지한다.

## 검증

- active 링크에 `text-brand` 클래스가 적용된다.
- `npx eslint src/components/layout/BottomNav.tsx` 통과.
