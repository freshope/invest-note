# Spec: 멀티 게시판 구조 (어드민 우선)

> 완료: 2026-06-19

## 배경 / 문제

공지사항·사용자의견·오류신고·거래내역서 제공(미지원 증권사 거래내역 사용자 제출) 등 여러 "게시판"
기능이 예정돼 있다. 각 기능을 개별 테이블로 만들면 중복이 커지므로, **하나의 게시글 테이블 +
`board_type` discriminator + `metadata jsonb`** 로 멀티 게시판을 흡수한다. 이번 스펙은 개별 기능을
다 만드는 게 아니라 **이 구조를 정의하고, 어드민에서 동작하는 얇은 vertical slice**까지 구현한다.
실제 사용자(app) 화면과 파일 업로드 스토리지는 후속 개별 스펙으로 진행한다.

## 목표 (완료 기준)

- `board_posts` / `board_comments` / `board_attachments` 3개 테이블이 마이그레이션으로 생성된다.
- 어드민에서 게시판 글 목록을 `board_type`으로 필터해 조회할 수 있다.
- 어드민에서 글 상세(본문 + 댓글 스레드 + 첨부 메타)를 볼 수 있다.
- 어드민이 글에 **관리자 댓글**을 달고, 글 **상태/상단고정/공지 작성**을 할 수 있다.
- `pnpm -C admin exec tsc --noEmit` 통과, `cd api && poetry run pytest -q` 통과.

## 설계

### 접근 방식

- **전용 board 모듈** (기존 `_LIST_TABLES` catch-all 비틀지 않음). 게시판은 board_type 필터,
  상세 조인(post+comments+attachments), 관리자 댓글 mutation, 상태 변경을 요구 → 평면 CRUD로 불가.
  단, **목록 엔벨로프는 `AdminListResponse` 재사용**, **FE 목록은 `DataTablePage` 재사용**.
- **board_type = text + CHECK** (PG enum 금지). 후속 스펙마다 새 type이 추가되므로 enum의
  `ALTER TYPE ADD VALUE` owner/superuser 마찰을 피한다. CHECK는 초기 4종(`notice`/`feedback`/
  `bug_report`/`broker_statement`)을 나열하고, 새 type은 CHECK 교체(drop/add constraint)로 확장.
  값 검증은 BE pydantic `Literal`로 이중.
- **첨부 스토리지 백엔드는 이번 스펙에서 결정하지 않는다** (TODO). 사용자 업로드가 app-side(후속)라
  이번 스펙엔 첨부될 파일이 0건. attachments 테이블은 백엔드-무관 shape(`storage_key`/`bucket`/
  `content_type`/`size_bytes`/`original_name`)만 정의. Supabase Storage로 반사적으로 기울지 말 것
  (팀은 탈-Supabase 방향) — 업로드 스펙에서 객체 스토리지와 함께 의식적으로 결정.
- **RLS 절대 추가 금지** (2026-06-18 전역 제거됨). 격리는 앱 레이어 `WHERE`로 단일화.
- uuid PK + `gen_random_uuid()`, `created_at`/`updated_at timestamptz`, `updated_at`은 기존 공유
  트리거 함수 `public.set_updated_at()`(baseline 존재) BEFORE UPDATE 부착. 소유자 `invest_note_app`.
- soft-delete 미도입(기존 컨벤션=hard delete). 모더레이션 이력 요구 없음.
- 작성자 표시는 `user_id`만 (어드민 `users`엔 email 컬럼 없음 — 신원은 Supabase Auth 소유, 기존 한계).

### 테이블 (마이그레이션 `0003_board_tables.py`, down_revision=`0002_drop_rls`)

`board_posts`
- `id uuid PK default gen_random_uuid()`
- `board_type text NOT NULL` + `CHECK (board_type in ('notice','feedback','bug_report','broker_statement'))`
- `user_id uuid NULL` FK→`users(id)` `ON DELETE SET NULL` (작성자 떠나도 글 보존; 공지는 NULL 가능)
- `title text NOT NULL`
- `body text NOT NULL DEFAULT ''`
- `status text NOT NULL DEFAULT 'open'` (board_type별 의미는 앱 레이어 관리: open/closed/resolved 등)
- `is_pinned boolean NOT NULL DEFAULT false` (공지 상단 고정)
- `metadata jsonb NOT NULL DEFAULT '{}'` (board별 가변 필드: 증권사명·앱버전 등 흡수)
- `created_at` / `updated_at timestamptz NOT NULL DEFAULT now()`
- index: `(board_type, created_at desc)`, `(user_id)`; trigger: `board_posts_updated_at`

`board_comments`
- `id uuid PK`, `post_id uuid NOT NULL` FK→`board_posts(id)` `ON DELETE CASCADE`
- `user_id uuid NULL` FK→`users(id)` `ON DELETE SET NULL`
- `is_admin boolean NOT NULL DEFAULT false` (관리자 댓글 구분)
- `body text NOT NULL`, `created_at`/`updated_at`
- index: `(post_id, created_at)`; trigger: `board_comments_updated_at`

`board_attachments`
- `id uuid PK`
- `post_id uuid NULL` FK→`board_posts(id)` `ON DELETE CASCADE`
- `comment_id uuid NULL` FK→`board_comments(id)` `ON DELETE CASCADE`
- `CHECK (post_id IS NOT NULL OR comment_id IS NOT NULL)` (둘 중 하나엔 귀속)
- `user_id uuid NULL` FK→`users(id)` `ON DELETE SET NULL`
- `original_name text NOT NULL`, `content_type text`, `size_bytes bigint`
- `storage_key text`, `bucket text` (스토리지 백엔드 미정 — 후속 업로드 스펙에서 채움)
- `created_at timestamptz NOT NULL DEFAULT now()` (immutable → updated_at 생략)
- index: `(post_id)`, `(comment_id)`

### BE 엔드포인트 (`/admin/boards*`, 게이트 = `require_admin` = JWT + allowlist)

신규 `routers/admin_board.py` (`APIRouter`) — `main.py`에서 **`admin.router`보다 먼저 include**.
(⚠️ `admin.py`의 catch-all `GET /admin/{table}`이 `/admin/boards`를 table="boards"로 흡수하므로
등록 순서가 핵심 — `/stats`·`/me`를 `/{table}`보다 먼저 둔 것과 동일 함정.)

- `GET /admin/boards?board_type=&page=&q=` → `AdminListResponse`(snake_case passthrough)
- `GET /admin/boards/{post_id}` → 상세 dict `{...post, comments:[...], attachments:[...]}`
- `POST /admin/boards` → 글 작성(관리자 공지 등): board_type/title/body/metadata/is_pinned
- `PATCH /admin/boards/{post_id}` → status/is_pinned/title/body 부분수정
- `DELETE /admin/boards/{post_id}` → 삭제(cascade)
- `POST /admin/boards/{post_id}/comments` → 관리자 댓글(`is_admin=true`, user_id=현재 어드민)
- `DELETE /admin/boards/comments/{comment_id}` → 댓글 삭제

응답은 어드민 컨벤션대로 **snake_case raw passthrough**(CamelModel 미사용). 쓰기 입력 스키마는
`ConfigDict(extra="forbid")` + board_type `Literal` 검증.

### 주요 변경 파일

- `api/alembic/versions/0003_board_tables.py` — 3테이블 생성(`op.execute` raw SQL)
- `api/src/invest_note_api/db_ops/board_repo.py` — list/get(상세 조인)/create_post/update_post/
  delete_post/create_comment/delete_comment asyncpg 쿼리 (`accounts_repo` 패턴: 화이트리스트 컬럼·
  row→dict 정규화 UUID/Decimal/datetime)
- `api/src/invest_note_api/schemas/board.py` — `BoardPostCreate`/`BoardPostUpdate`/`BoardCommentCreate`
  (extra=forbid, board_type Literal)
- `api/src/invest_note_api/routers/admin_board.py` — 위 엔드포인트
- `api/src/invest_note_api/main.py` — `admin_board.router`를 `admin.router`보다 먼저 include
- `api/tests/test_admin_board.py` — CRUD + 댓글 + board_type 필터 회귀 (FakePool 패턴, `test_admin_crud.py` 참고)
- `admin/src/lib/api.ts` — `BoardRow` 타입 + `adminApi.boards={list,get,create,update,remove,addComment,removeComment}`
- `admin/src/lib/nav.ts` — "게시판" nav 항목 추가
- `admin/src/app/(dash)/boards/page.tsx` — `DataTablePage` + board_type 필터 toolbar + columns
- `admin/src/app/(dash)/boards/[id]/page.tsx` — 상세(본문+댓글 스레드+첨부 메타+관리자 댓글 폼+상태/고정 컨트롤)
- `admin/src/components/board/` — 상세용 컴포넌트(관리자 댓글 폼·상태 select), `base/` 프리미티브 재사용

## 구현 체크리스트

- [x] `0003_board_tables.py` 작성 → 일회용 postgres:18 로 baseline→0002→0003 전체 체인 검증(로컬 64340 DB 미기동)
- [x] `schemas/board.py` (입력 스키마 + Literal/forbid)
- [x] `db_ops/board_repo.py` (목록·상세 조인·create/update/delete·댓글)
- [x] `routers/admin_board.py` + `main.py` include (순서 = catch-all보다 먼저)
- [x] `tests/test_admin_board.py` → `poetry run pytest tests/test_admin_board.py -q` (19 passed)
- [x] `admin/src/lib/api.ts` BoardRow + adminApi.boards
- [x] `admin/src/lib/nav.ts` 게시판 메뉴
- [x] `admin/src/app/(dash)/boards/page.tsx` 목록 + board_type 필터
- [x] `admin/src/app/(dash)/boards/[id]/page.tsx` 상세 + 관리자 댓글 + 상태 컨트롤
- [x] 타입 체크 통과 (`pnpm -C admin exec tsc --noEmit`)
- [x] 백엔드 테스트 통과 (`cd api && poetry run pytest -q` → 685 passed)

## 검증 (end-to-end)

1. `cd api && make migrate` → 3테이블 생성 확인 (`\d board_posts` 등).
2. `cd api && poetry run pytest tests/test_admin_board.py -q` → CRUD/댓글/필터 회귀.
3. admin 로컬 dev (`pnpm -C admin dev`, 포트 3001) + 어드민 계정 로그인 →
   게시판 메뉴 → 공지 글 작성 → board_type 필터 → 상세 진입 → 관리자 댓글 작성 → 상태 변경 확인.
4. `pnpm -C admin exec tsc --noEmit`.

## 우려사항 / 리스크

- **라우트 등록 순서**: `/admin/boards`가 `GET /admin/{table}` catch-all에 흡수되지 않도록
  `admin_board.router`를 `admin.router`보다 먼저 include (테스트로 가드).
- **어드민 동적 라우트 `[id]`**: 어드민이 standalone Node 서버면 동작(메모리 `project_admin_panel`).
  만약 `next.config` output이 `export`로 확인되면 동적 prerender 불가 → `?id=` 쿼리 상세로 폴백.
  구현 시작 시 `admin/next.config.*` output 모드 먼저 확인.
- **스토리지 미결정**: attachments는 shape만 — 이번 스펙에 업로드 엔드포인트/뷰어 없음. 어드민 상세는
  첨부 메타데이터(파일명·크기)만 표시. 다운로드/업로드는 후속 스펙 명시.
- **board_type CHECK 확장**: 새 게시판 type 추가 시 CHECK constraint 교체 마이그레이션 필요(설계 의도).
