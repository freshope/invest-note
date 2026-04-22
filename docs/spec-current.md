# Spec: 모노레포 폴더 구조 정리 (Monorepo Restructure)

## 배경 / 문제

소셜 로그인 마이그레이션(1단계) 완료 후, 2단계 **FastAPI 백엔드 분리** 진입 직전.
백엔드를 별도 언어(Python)로 분리하기 전에 현재 단일 Next.js 프로젝트를
**`app/` (Frontend) + `api/` (Backend)** 모노레포 구조로 재배치하여
이후 백엔드 코드가 들어갈 자리를 확보한다.

본 작업은 **순수 파일 이동 + 설정 경로 보정**이며 코드 동작 변경은 없다.

## 목표

- Next.js 자산이 모두 `app/` 하위로 이동되고 `pnpm dev/build/lint/test/tsc` 가 루트에서 정상 동작
- `api/` 폴더 placeholder 생성 (FastAPI 코드가 들어갈 자리)
- `pnpm-workspace.yaml` 에 `app` 등록, 루트 `package.json` 은 공용 스크립트만 보유
- `git mv` 사용으로 모든 파일 히스토리 보존
- 브라우저 동작/타입 체크/린트/테스트 회귀 없음

## 설계

### 접근 방식

- **이동**: `git mv` 로 src, public, scripts, next.config.ts, tsconfig.json, components.json, eslint.config.mjs, postcss.config.mjs, vitest.config.ts, package.json → `app/` 하위
- **gitignored 이동**: `.env.local`, `.env.local.example`, `next-env.d.ts` 는 `mv` (수동), `.next/`·`tsconfig.tsbuildinfo` 는 삭제 후 재생성
- **루트 잔존**: docs, supabase, sample, certificates, .claude, .git, .gitignore, AGENTS.md, CLAUDE.md, README.md, pnpm-workspace.yaml, pnpm-lock.yaml
- **루트 신규**: 최소 `package.json` (`pnpm -C app <cmd>` 위임 스크립트)
- **api/**: 빈 폴더 + 안내용 README.md
- **경로 alias**: `@/*` → `./src/*` (tsconfig 가 함께 이동하므로 그대로), `vitest.config.ts` `__dirname` 기반이라 자동 호환
- **Vercel**: Root Directory 설정을 `app` 으로 변경 (수동, 머지 직전)

### 주요 변경 파일

- `app/` 신규 디렉터리 — Next.js 자산 전체 이동 위치
- `api/` 신규 디렉터리 — FastAPI placeholder
- `api/README.md` — 다음 작업 안내
- `pnpm-workspace.yaml` — `packages: ["app"]` 추가
- `package.json` (루트, 신규) — 위임 스크립트만
- `.gitignore` — Next.js 항목 `/app/.next/`, `/app/out/`, `/app/next-env.d.ts` 로 보정
- `README.md` — 디렉터리 구조 섹션 추가

## 구현 체크리스트

- [ ] `app/` 디렉터리 생성 + `git mv` 로 Next.js 자산 일괄 이동 (src, public, scripts, next.config.ts, tsconfig.json, components.json, eslint.config.mjs, postcss.config.mjs, vitest.config.ts, package.json)
- [ ] gitignored 파일 수동 이동: `.env.local`, `.env.local.example`, `next-env.d.ts` → `app/`
- [ ] `.next/`, `tsconfig.tsbuildinfo` 삭제
- [ ] `api/` 디렉터리 생성 + `api/README.md` 작성
- [ ] `pnpm-workspace.yaml` 수정 (`packages: ["app"]` 추가)
- [ ] 루트 `package.json` 신규 생성 (위임 스크립트만)
- [ ] `.gitignore` 경로 보정 (`/app/.next/`, `/app/out/`, `/app/next-env.d.ts`)
- [ ] `README.md` 디렉터리 구조 섹션 추가
- [ ] `pnpm install` (루트) 정상 동작 확인
- [ ] `pnpm dev` (루트) — Next.js 개발 서버 정상 기동 확인
- [ ] `pnpm build` (루트) — 빌드 통과
- [ ] `pnpm tsc` (루트) — 타입 체크 통과
- [ ] `pnpm lint` (루트) — 린트 통과
- [ ] `pnpm test` (루트) — vitest 통과
- [ ] `git log --follow app/src/app/login/page.tsx` — 이전 히스토리 보존 확인

## 우려사항 / 리스크

- **Vercel 빌드**: Root Directory 변경 전 develop merge 시 빌드 실패 가능. 머지 직전 Vercel 설정을 먼저 변경.
- **certificates/**: 현재 `next.config.ts` 가 비어 있어 영향 없음. 추후 dev HTTPS 옵션 추가 시 `../certificates` 로 참조.
- **scripts/backfill-pnl.ts**: `dotenv.config({ path: process.cwd() + ".env.local" })` — 호출 시 cwd 가 `app/` 이어야 함. 루트에서 호출하면 깨짐.
- **.next/ 캐시**: 루트에 잔존하면 혼란 → 반드시 삭제.
