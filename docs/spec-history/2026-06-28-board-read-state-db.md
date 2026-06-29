# Spec: 게시판 읽음/알림 상태 DB 이전

> 완료: 2026-06-28

## 배경 / 문제

게시판의 읽음·알림 상태가 전부 기기 `localStorage`(`app/src/lib/board-seen.ts`)에만 저장되어 두 가지 문제가 있다:

1. **기기 변경 시 유실** — 재설치/기기 변경 시 모든 글이 안읽음으로 부활.
2. **신규 가입자 옛 공지** — 신규 기기는 `last-seen-notice`가 `null`이라 가입 전 옛 공지까지 전부 안읽음으로 떠서 공지 메뉴에 점이 뜸.

BE에는 읽음 추적이 전무하다(`board_posts`/`board_comments`/`board_attachments` 3개 테이블뿐). 판정 기준을 전부 DB로 옮겨 기기 무관하게 유지하고, 신규 가입자 기준 시각을 가입 시점으로 잡아 해결한다. **운영 미적용 상태라 데이터 마이그레이션/backfill은 불필요.**

## 목표 (완료 기준)

- 공지 메뉴 점이 DB의 `notices_seen_at` 기준으로 동작하고, 기기를 바꿔도 유지된다.
- 신규 가입자에게 가입 전 공지는 점이 뜨지 않는다(가입 시각 fallback).
- 내 글(의견/오류신고/거래내역서) 안읽음 점이 DB `read_at` 기준으로 동작하고 기기 무관하게 유지된다.
- 거래내역서 resolved 바텀시트 팝업이 사용자 단위 1회만 노출되고 기기를 바꿔도 다시 뜨지 않는다.
- `board-seen.ts`의 localStorage 읽음/알림 로직이 완전히 제거된다.
- BE `pytest`, FE `tsc --noEmit` 통과.

## 설계

세 가지 상태를 모두 DB로 이전. 메커니즘은 둘로 유지(공지=high-water mark, 내 글/팝업=per-post). 통합하지 않는 이유: 공지를 per-post로 만들면 신규가입자 backfill 문제가 생기는데, high-water mark가 이를 구조적으로 회피.

### 1) 공지 — per-user high-water mark

신규 테이블:
```sql
user_notice_state(
  user_id uuid PRIMARY KEY REFERENCES users(id) ON DELETE CASCADE,
  notices_seen_at timestamptz NOT NULL
)
```
- row는 lazy 생성(사용자가 공지 메뉴를 처음 열어 "읽음 처리"할 때). hot path인 `acquire_for_user`는 건드리지 않음.
- 안읽음(서버 EXISTS, 전역):
  `EXISTS(notice.created_at > COALESCE(state.notices_seen_at, users.created_at))`
  → row 없으면 `users.created_at`(가입 시각) fallback = problem 2 구조적 해결.
- `pinned_first` 정렬로 인한 client-side 오판(items[0]이 고정 옛 공지)도 서버 EXISTS가 해소.

### 2) 내 글 — per-post reads (+ 팝업 ack 동일 테이블)

신규 테이블:
```sql
board_post_reads(
  user_id uuid REFERENCES users(id) ON DELETE CASCADE,
  post_id uuid REFERENCES board_posts(id) ON DELETE CASCADE,
  read_at         timestamptz NULL,   -- 상세 열람(읽음 점 해제)
  popup_acked_at  timestamptz NULL,   -- 진입 바텀시트 안내 확인
  PRIMARY KEY (user_id, post_id)
)
```
- 읽음과 팝업 ack는 독립 이벤트라 한 테이블의 두 nullable 컬럼으로 보관(별도 테이블 X). 한쪽만 upsert.
- **서버 unread 계산은 현행 `isMyPostUnread`(`app/src/lib/board-post.ts:45-65`) 규칙을 정확히 복제:**
  - 어드민 댓글 0 + `status='open'` → `false`
  - 활동시각 = `max(어드민 댓글 created_at, status≠'open'일 때만 updated_at)`
    (※ `updated_at`은 status≠open일 때만 활동신호. 본문 편집 잡음 배제 — 현행과 동일하게 유지)
  - `read_at` 없으면 `true`, 있으면 `활동시각 > read_at`
  - 댓글이 이미 글마다 로드되므로 Python(repo/service) 계산이 단순. SQL 복제 불필요.

### 3) 바텀시트 팝업 dedup

- 위 `board_post_reads.popup_acked_at` 사용.
- `MySubmissionsPopupGate` 노출 조건: `status==='resolved' && board_type==='broker_statement' && !popup_acked`.

### 엔드포인트 델타 (`routers/board.py`)
- `POST /board/notices/seen` → `notices_seen_at = now()` upsert (공지 메뉴 열 때)
- `POST /board/posts/{id}/read` → `read_at = now()` upsert (내 글 상세 열 때)
- `POST /board/posts/{id}/ack-popup` → `popup_acked_at = now()` upsert (팝업 닫기/이동)
- `GET /board/notices` 응답 += `has_unread: bool`
- `GET /board/my-posts` 각 item += `unread: bool`, `popup_acked: bool`

### 주요 변경 파일

**BE**
- `api/alembic/versions/0011_board_reads.py` (신규) — `user_notice_state` + `board_post_reads` 두 테이블. revises `0010_import_staging`(현재 head).
- `api/src/invest_note_api/db_ops/board_repo.py` — `get_notices_seen_at`/`set_notices_seen_at`, `has_unread_notice`, `upsert_post_read`, `upsert_popup_ack`; `list_my_posts`에 reads LEFT JOIN + `unread`/`popup_acked` 계산.
- `api/src/invest_note_api/routers/board.py` — 신규 3개 엔드포인트, `list_notices`/`list_my_posts` 응답 확장.
- `api/src/invest_note_api/schemas/board.py` — `MyPostItem` += `unread`, `popup_acked`; notices 응답 모델 += `has_unread`.
- `api/tests/test_board*.py` — 회귀 테스트 추가.

**FE**
- `app/src/lib/api-client.ts` — `boardApi` += `markNoticesSeen`, `markPostRead`, `ackPopup`; `MyPost` 타입 += `unread`/`popup_acked`; notices 응답 += `has_unread`; `ROUTES.board` 확장.
- `app/src/lib/board-seen.ts` — localStorage 읽음/seen/ack 로직 제거(파일 제거 또는 잔여 정리).
- `app/src/lib/board-post.ts` — `isMyPostUnread` 제거, 서버 `unread` 사용.
- `app/src/app/(app)/settings/page.tsx` — dot 계산을 서버 `has_unread`/`unread`로 교체, 공지 메뉴 클릭 시 `markNoticesSeen` 호출 + invalidate(`recomputeTick` 제거).
- `app/src/components/settings/MyPostsListPanel.tsx` — `unreadIds`를 서버 `unread`로.
- `app/src/components/settings/MyPostDetailPanel.tsx` — 진입 시 `markPostRead(post.id)` 호출 + invalidate.
- `app/src/components/providers/MySubmissionsPopupGate.tsx` — `!popup_acked` 조건, `ack()`/`goImport()`에서 `ackPopup` 호출 + invalidate.
- `app/src/lib/constants/storage.ts` — 미사용 키 제거.

## 구현 체크리스트

- [x] `0011_board_reads.py` 마이그레이션 작성 (두 테이블 + FK CASCADE + 필요 인덱스)
- [x] `board_repo.py` — notice seen get/set + `has_unread_notice` (COALESCE fallback)
- [x] `board_repo.py` — `list_my_posts` reads JOIN + `unread`/`popup_acked` 계산(isMyPostUnread 복제)
- [x] `board_repo.py` — `upsert_post_read`, `upsert_popup_ack`
- [x] `routers/board.py` — `POST /board/notices/seen`, `/posts/{id}/read`, `/posts/{id}/ack-popup`
- [x] `routers/board.py` + `schemas/board.py` — `list_notices`(has_unread) / `list_my_posts`(unread, popup_acked) 응답 확장
- [x] BE 테스트: unread 판정·has_unread fallback·세 upsert 멱등 (`poetry run pytest -q`)
- [x] FE `api-client.ts` — 타입/엔드포인트/ROUTES 반영
- [x] FE 컴포넌트 6종 — 서버 플래그로 교체 + read/seen/ack 호출 + invalidate
- [x] `board-seen.ts`/`board-post.ts`/`storage.ts` 정리(미사용 제거)
- [x] FE 타입 체크 (`pnpm -C app exec tsc --noEmit`)

## 우려사항 / 리스크

- `isMyPostUnread` 활동시각 규칙(특히 status≠open일 때만 `updated_at` 사용)을 BE가 정확히 복제하지 않으면 점 동작이 드리프트. 테스트로 고정.
- `board_post_reads`는 (user, post) 단위라 데이터량 적음(내 글 소수). 인덱스는 PK로 충분.
- 운영 데이터 없음 → 기존 사용자 부활/backfill 이슈 없음.
