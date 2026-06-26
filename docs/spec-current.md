# 현재 작업 사양 — 어드민 게시판 작성자/회원 아바타+이름 표시

## 목표
어드민 패널 게시판(boards) 화면에서 작성자·댓글 작성자 회원을 `user_id`(uuid) 원문 대신
**아바타 + 이름(display_name)** 으로 표시한다. 이름이 없으면 이니셜 fallback, 작성자 미상(`user_id` null,
관리자 공지 등)도 안전하게 처리한다.

## 배경 (사전 조사 결과)
- 현재 board 목록/상세 API는 `select * from board_posts` 만 수행 → 응답에 작성자 이름/아바타 없음 → FE만으론 불가, **BE 변경 필수**.
- 회원 이름/아바타는 `public.user_profiles`(`display_name`, `avatar_url`) 에 저장. board_posts.user_id ↔ user_profiles.user_id (1:1).
- 기존 어드민 회원 목록(`admin/src/app/(dash)/users/page.tsx`)이 이미 아바타+이름 셀을 그리고, `admin_repo.py` users 쿼리가 `LEFT JOIN user_profiles` 패턴 → **그대로 참고 모델**.

## BE↔FE 계약 (고정 — 양측 동일 필드명 사용)
board 게시글 row, 댓글 row 각각에 작성자 프로필 필드를 LEFT JOIN 으로 추가한다:

| 필드명 | 타입 | 의미 |
|---|---|---|
| `author_display_name` | `string \| null` | user_profiles.display_name (없으면 null) |
| `author_avatar_url` | `string \| null` | user_profiles.avatar_url (없으면 null) |

- 기존 `user_id` 필드는 유지(제거 금지). 신규 필드만 추가.
- snake_case raw passthrough 관례 유지 — 별도 직렬화 매핑 없이 컬럼 그대로 노출.
- BE가 부득이 필드명을 바꿔야 하면 fe-engineer 에게 DM 후 변경.

## 작업 분해
- **[BE]** `board_repo.list_posts` / `get_post` 의 게시글 쿼리와 `get_post` 의 댓글(`board_comments`) 쿼리에
  `LEFT JOIN user_profiles p ON p.user_id = <테이블>.user_id` 추가, select 에 위 계약 두 필드 alias 노출.
  기존 pytest 영향 확인 + 가능하면 join 노출 회귀 테스트 추가.
- **[FE]** `BoardRow`/`BoardComment` 타입에 계약 필드 추가. `users/page.tsx` 의 아바타+이름 셀을
  **공용 컴포넌트로 추출**(`admin/src/components/board/` 또는 공용 위치)하여
  `authorCol`(board-config.tsx), `TriageDetail.tsx`, `StatementDetail.tsx`, `BoardCommentThread.tsx` 4곳에서 재사용.
  user_id null / display_name null fallback 처리. `pnpm -C admin exec tsc --noEmit` 통과.
- **[QA]** BE 응답 shape ↔ FE 타입 정합, null fallback, 4곳 모두 교체됐는지, 기존 컬럼/기능 회귀 없음 검증.

## 검증 기준
- 어드민 게시판 목록/상세/댓글에서 작성자가 아바타+이름으로 표시(이름 없으면 이니셜, 작성자 미상은 fallback).
- BE pytest green, FE tsc green.
