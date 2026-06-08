# Spec: GitHub Actions CI baseline

## 배경 / 문제

`.github/workflows/` 디렉토리가 존재하지 않아 PR/푸시 단계에서 자동 검증 가드가 전혀 없다. 현재 모든 검증(`pnpm tsc`, `pnpm test`, `pnpm build`, `poetry run pytest`)이 로컬 수동 실행에 의존하므로:

- develop 브랜치에 타입 에러/테스트 실패가 회귀해도 머지 시점에 잡히지 않는다.
- 이후 진행할 quote_status 플래그(#3), 접근성(#4), 순환 import 가드(#5) 같은 변경의 안전망이 없다.
- `app/` (Next.js + Capacitor) 와 `api/` (FastAPI) 모노레포 구조에서 한쪽 변경이 다른 쪽 빌드/테스트를 깨도 보이지 않는다.

이 spec은 **PR 트리거**로 FE/BE 양쪽의 최소 가드(타입체크 + 린트 + 테스트 + 빌드 / pytest + ruff)를 자동 실행하는 단일 워크플로를 추가한다. 배포 자동화는 범위 밖.

## 목표

- `main`/`develop`을 향한 PR과 두 브랜치 push에서 다음이 자동 실행되고 실패 시 머지 차단:
  - **frontend job**: `pnpm install` → `pnpm tsc` → `pnpm test` → `pnpm build`
  - **backend job**: `poetry install` → `ruff check` → `pytest -q`
- 두 잡은 병렬 실행
- 환경변수는 더미값으로 주입 (실제 Supabase 연결 없이 동작 가능 — BE는 `fake_pool`, FE 빌드는 NEXT_PUBLIC_* 더미)
- pnpm·poetry 캐시로 재실행 속도 확보

> **lint 가드 제외 결정**: 사전 dry-run에서 `pnpm lint`가 329 errors / 25,348 warnings 로 실패. `react-hooks/refs` (useClickOutside.ts:8), `react-hooks/incompatible-library` (AccountFormPanel.tsx:78 등 useForm.watch 사용처) 등 React 19 신규 룰 위반과 unused-vars warning 누적이 큼. 본 spec의 baseline 범위에선 제외하고 별도 spec(`feature/eslint-cleanup`)으로 분리. ruff 6 errors는 모두 unused imports 라 본 spec에서 `ruff check --fix`로 함께 정리.

## 설계

### 트리거 정책

```yaml
on:
  pull_request:
    branches: [main, develop]
  push:
    branches: [main, develop]
```

PR 푸시·머지·develop 직접 푸시까지 커버. feature 브랜치 push에는 트리거되지 않으므로 비용 절감.

### Frontend job

- `actions/checkout@v4`
- `pnpm/action-setup@v4` (루트 `pnpm-lock.yaml` 사용)
- `actions/setup-node@v4` with `cache: pnpm`, `node-version: 20`
- `pnpm install --frozen-lockfile`
- 단계: `pnpm tsc` → `pnpm test` → `pnpm build` (lint 제외)
- env (더미): `NEXT_PUBLIC_SUPABASE_URL`, `NEXT_PUBLIC_SUPABASE_PUBLISHABLE_KEY`, `NEXT_PUBLIC_API_BASE_URL`, `NEXT_PUBLIC_SITE_URL`

### Backend job

- `actions/checkout@v4`
- `actions/setup-python@v5` with `python-version-file: api/.python-version` (3.12)
- `snok/install-poetry@v1`
- 캐시: `actions/cache@v4` 로 `~/.cache/pypoetry` + `api/.venv`
- `poetry install --no-interaction --no-root` (working-directory: api)
- 단계: `poetry run ruff check` → `poetry run pytest -q`
- env (더미): `SUPABASE_URL=https://example.supabase.co`

### 주요 변경 파일

- `.github/workflows/ci.yml` (신규)

### 비범위

- 배포 자동화 (Render/Vercel/앱스토어)
- 매트릭스(여러 OS/Python 버전) — 단일 ubuntu-latest + Node 20 + Python 3.12
- 캐시 무효화 정책 튜닝 — 기본값 사용
- Codecov / 테스트 리포트 업로드
- Concurrency 그룹 (PR 중복 실행 취소) — 추후 비용 이슈 발생 시 추가

## 구현 체크리스트

- [x] 사전 검증 FE: `pnpm tsc` ✅, `pnpm test` (124 passed) ✅, `pnpm build` (NEXT_PUBLIC_* 더미값) ✅
- [x] 사전 검증 BE: `poetry run pytest -q` (251 passed, SUPABASE_URL 더미) ✅
- [x] ruff 6 errors (unused imports) `--fix` 자동 정리
- [x] `.github/workflows/ci.yml` 작성 (lint 제외, ruff 포함)
- [x] spec에 lint 제외 결정 명시
- [ ] feature/ci-baseline → develop PR 생성 + Actions 실행 결과 green 확인
- [ ] `docs/backlog.md` 에 후속 spec `feature/eslint-cleanup` 항목 추가 (react-hooks 위반, unused vars 정리)

## 검증

1. **로컬 dry-run** (모두 통과 확인됨):
   - FE: `pnpm tsc` ✅, `pnpm test` (124 passed) ✅, `pnpm build` (NEXT_PUBLIC_* 더미) ✅
   - BE: `cd api && poetry run ruff check` ✅ (--fix 후), `SUPABASE_URL=https://example.supabase.co poetry run pytest -q` (251 passed) ✅
2. **CI 실제 실행**: feature/ci-baseline → develop PR 생성 → Actions 탭에서 두 잡 모두 green 확인
3. **회귀 가드**: 의도적으로 타입 에러를 도입한 dummy 커밋을 push 해 frontend job 이 실패하는지 확인 (이후 revert) — optional

## 우려사항 / 리스크

- **환경변수 더미값으로 빌드 실패**: 사전 dry-run에서 통과 확인 (Next.js 16.2.3 turbopack, 11 routes 정적 생성). URL 형식 validation 없음.
- **`pnpm test` 가 인터랙티브 watch로 진입**: `app/package.json:10` 의 `"test": "vitest run"` 으로 이미 단발 실행 모드 → 안전.
- **Poetry 캐시 키 mis-match**: `poetry.lock` 변경 빈도가 낮으니 `hashFiles('api/poetry.lock')` 키로 충분.
- **lint 제외**: 위 "lint 가드 제외 결정" 참고. 별도 spec(`feature/eslint-cleanup`)으로 분리, backlog 등록.
- **CI 비용**: GitHub Actions 무료 분(public repo는 무제한, private는 월 2,000분). 두 잡 합쳐 PR 1회당 약 3-5분 예상.
