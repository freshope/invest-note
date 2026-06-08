# Spec: 폴더명 변경 — `api` → `be`, `app` → `fe`

> 완료: 2026-05-14

## 배경 / 문제

현재 백엔드/프론트엔드 디렉터리명(`api`, `app`)이 일반적·중의적이라 코드/스크립트/문서에서 식별성이 떨어진다(특히 `app` 은 Capacitor 의 `android/app/`, `ios/App/` 등 내부 관례와 겹쳐 혼동을 유발). 명시적인 `be` / `fe` 로 통일해 가독성과 도구 출력의 모호함을 줄인다.

## 목표

- 루트 폴더 `api/` 가 `be/` 로, `app/` 가 `fe/` 로 git 히스토리를 보존한 채 이동되어 있다.
- `pnpm install`, `pnpm tsc`, `pnpm build`, `pnpm test` 가 새 경로 기준으로 통과한다.
- `cd be && poetry install --no-root && poetry run pytest -q` 가 통과한다.
- `make dev be` / `make dev fe` 가 정상 기동한다.
- `node scripts/version.mjs check` 가 새 경로에서 통과한다.
- CI workflow(`.github/workflows/ci.yml`) 가 동일한 두 잡을 새 경로 기준으로 수행한다.

## 설계

### 접근 방식

1. **폴더 이동은 `git mv` 로 한 번에**: `git mv api be`, `git mv app fe` — 히스토리/리네임 추적 보존.
2. **참조 갱신은 그 다음 별도 편집**: 루트 설정/스크립트/문서/CI 파일에서 `api` → `be`, `app` → `fe` 치환. 폴더 내부 코드는 자체 상대경로만 사용하므로 추가 수정 불필요(탐색에서 확인됨).
3. **lockfile**: `pnpm-workspace.yaml` 변경으로 `pnpm-lock.yaml` 의 importer 키가 바뀐다. `pnpm install` 을 한 번 돌려 lockfile 의 importer 경로(`importers: app:` → `importers: fe:`)를 자연 갱신. 의존성 버전은 변하지 않는다.
4. **Poetry/Capacitor 내부 패키지명은 미변경**: `pyproject.toml` 의 `name = "invest-note-api"`, `app/package.json` 의 `"name": "invest-note"`, Android `app/android/app/` 같은 Capacitor 내부 디렉터리는 폴더명 리네이밍과 무관하므로 건드리지 않는다(요청 범위 = 루트 폴더 2개만).
5. **순서 주의**: 작업 전 `make dev` 로 띄운 백그라운드 프로세스가 있으면 `.dev/pids/` 의 PID 들로 먼저 종료한다(파일 잠금/캐시 충돌 방지).

### 주요 변경 파일

폴더 이동:
- `api/` → `be/` (전체)
- `app/` → `fe/` (전체)

루트 참조 갱신(총 10개 파일):
- `package.json` — `pnpm -C app …`/`cd api …`/`sh app/scripts/…` 6개 스크립트 → `pnpm -C fe …`/`cd be …`/`sh fe/scripts/…`
- `pnpm-workspace.yaml` — `- "app"` → `- "fe"`
- `Makefile` — `API_DIR := api` → `BE_DIR := be`, `APP_DIR := app` → `FE_DIR := fe` (그리고 내부 참조 변수도 동일하게 정리)
- `scripts/version.mjs` — `app/package.json`, `api/pyproject.toml`, `app/android/app/build.gradle`, `app/ios/App/App.xcodeproj/project.pbxproj` 4개 경로
- `.github/workflows/ci.yml` — `working-directory: api`, `python-version-file: api/.python-version`, `path: api/.venv`, `hashFiles('api/poetry.lock')` 4개
- `.gitignore` — `api/.env.local`, `app/.env.local`, `app/.env.production` 3줄
- `README.md` — 디렉터리 설명 2줄
- `CLAUDE.md` — 프로젝트 구조 설명 2줄
- `AGENTS.md` — 프로젝트 구조 + 명령어 규칙(`pnpm -C app …`, `cd api …` 등) 다수
- `docs/decisions.md` — 본문 내 경로 참조 7개(`app/src/...`, `api/...`)
- `docs/backlog.md` — 본문 내 경로 참조 3개

`pnpm-lock.yaml` — `pnpm install` 실행 후 자동 갱신(수동 편집 X).

## 구현 체크리스트

- [x] 작업 전 `make dev` 백그라운드 프로세스 확인 후 정리 (`.dev/pids/*.pid` 의 PID 종료)
- [x] `git mv api be`
- [x] `git mv app fe`
- [x] `pnpm-workspace.yaml` 수정 (`app` → `fe`)
- [x] `package.json` 스크립트 6개 수정
- [x] `Makefile` 디렉터리 변수와 사용처 갱신
- [x] `scripts/version.mjs` 경로 4개 수정
- [x] `.github/workflows/ci.yml` 의 `api` 참조 4개 수정
- [x] `.gitignore` 의 `api/.env.local`, `app/.env.local`, `app/.env.production` 갱신
- [x] `README.md` 디렉터리 설명 갱신
- [x] `CLAUDE.md` 프로젝트 구조 설명 갱신
- [x] `AGENTS.md` 프로젝트 구조 + 명령어 규칙 갱신
- [x] `docs/decisions.md` 경로 참조 일괄 갱신
- [x] `docs/backlog.md` 경로 참조 일괄 갱신
- [x] `pnpm install` 실행 → `pnpm-lock.yaml` 의 importer 키 갱신 확인
- [x] `pnpm tsc` 통과
- [x] `pnpm test` 통과
- [x] `pnpm build` 통과
- [x] `cd be && poetry install --no-root && poetry run pytest -q` 통과
- [x] `node scripts/version.mjs check` 통과
- [x] `make dev be` / `make dev fe` 각각 기동 후 정상 종료 확인

## 검증

End-to-end 확인 순서:
1. `pnpm install` (lockfile importer 키 갱신)
2. `pnpm tsc && pnpm test && pnpm build`
3. `cd be && poetry install --no-root && poetry run pytest -q && cd ..`
4. `node scripts/version.mjs check`
5. `make dev be`, `make dev fe` 각각 백그라운드 기동 후 헬스체크(`curl 127.0.0.1:8000`, `curl 127.0.0.1:3000`)
6. CI 는 PR 올린 뒤 GitHub Actions 결과로 최종 확인

## 우려사항 / 리스크

- **`pnpm-lock.yaml` 자동 변경**: `pnpm install` 실행 시 importer 키 외에 의도치 않은 변경이 더 발생할 수 있다 → diff 검토 후 의존성 버전 변경이 있으면 별도 커밋으로 분리.
- **로컬 미커밋 파일 분실**: 사용자의 `api/.env.local`, `app/.env.local`, `app/.env.production` 등 ignore 된 파일은 `git mv` 가 옮겨주지 않을 수 있다 → 작업자가 직접 `mv api/.env.local be/.env.local` 식으로 옮길 것을 안내(스펙 실행 시 추가 확인).
- **Worktree 환경**: 다른 worktree 가 동일 폴더를 점유 중이면 충돌. 현재 메인 repo `develop` 브랜치에서 작업이므로 문제 없음.
- **외부 배포/IDE 설정**: VS Code 워크스페이스 파일, 에디터 북마크 등 레포 외부 설정은 사용자가 직접 수정. 본 spec 범위 외.
