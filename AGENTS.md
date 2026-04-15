<!-- BEGIN:nextjs-agent-rules -->
# This is NOT the Next.js you know

This version has breaking changes — APIs, conventions, and file structure may all differ from your training data. Read the relevant guide in `node_modules/next/dist/docs/` before writing any code. Heed deprecation notices.
<!-- END:nextjs-agent-rules -->

# shadcn/ui 규칙

- 설치한 shadcn 컴포넌트를 직접 사용하지 않는다.
- 설치된 컴포넌트와 동일한 이름의 래퍼를 `src/components/base/` 에 만들고 항상 해당 래퍼를 사용한다.
- 컴포넌트 업데이트 시 래퍼를 수정하여 반영한다.

# Git 규칙

## Git Flow 사용
- 브랜치 전략으로 Git Flow를 사용한다
- 기본 브랜치: `main` (프로덕션), `develop` (개발 통합)

## 브랜치 네이밍
- 기능 추가 또는 이슈 수정: `feature/<설명>` 브랜치 사용
  - 예: `feature/add-stock-chart`, `feature/fix-login-bug`
- 릴리즈: `release/<버전>` 브랜치 사용
- 긴급 수정: `hotfix/<설명>` 브랜치 사용

## 작업 흐름
1. `develop` 브랜치에서 `feature` 브랜치 생성
2. 작업 완료 후 `develop`으로 병합
3. 릴리즈 준비 시 `release` 브랜치 생성 후 `main`과 `develop`에 병합
