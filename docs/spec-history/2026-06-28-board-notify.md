# Spec: 거래내역서 제보 알림 — "내 제보/문의" 인앱 알림

> 완료: 2026-06-28

## 배경 / 문제

사용자가 거래내역서를 제보하면(`board_posts`, `board_type='broker_statement'`) 그 증권사의 일괄등록(import) 파서가 실제로 추가됐을 때 제보자에게 알릴 방법이 현재 전혀 없다. 푸시·이메일 인프라가 전무하고, 사용자가 쓴 게시판 글(`feedback`/`bug_report`/`broker_statement`)에 어드민이 단 답변을 앱에서 되읽을 경로조차 없다(답변은 어드민 콘솔에서만 보임). 서버가 사용자에게 능동적으로 알리는 채널은 강제 업데이트 게이트 하나뿐이다.

따라서 푸시 없이 **앱 진입 시점**에 동작하는 인앱 알림을 만든다. 제보자 개인에게 "당신 제보가 반영됐다"를, 전체에 공지로 "OO증권 지원 시작"을 알리고, feedback/bug_report 답변 사각지대까지 해소한다. (로드맵상 푸시 알림은 v2+ 제외 항목 → 본 작업은 푸시가 아닌 인앱 경량 알림으로 그 공백을 메움.)

## 목표

- 설정 탭의 "내 제보/문의" 화면에서 **본인이 쓴 글만**(feedback/bug_report/broker_statement) 상태·어드민 답변과 함께 본다. (타인 글 노출 0, `notice` 제외)
- 제보가 `resolved`이면 완료 칩 + 축하 문구 + "가져오기" 화면 딥링크가 표시된다.
- 앱 진입 시 **미확인 resolved 제보**가 있으면 바텀시트 팝업이 **정확히 1회** 뜬다(닫으면 재노출 없음). 강제 업데이트 오버레이가 떠 있으면 팝업은 뜨지 않는다.
- 설정의 "내 제보/문의" 진입점에 새 어드민 답변이 있으면 unread 점, "공지사항" 진입점에 새 공지가 있으면 뱃지가 표시되고, 해당 화면을 열면 사라진다.
- 읽음 상태는 **기기 localStorage**에만 기록한다(BE 읽음 테이블/컬럼 신설 없음).

## 설계

### 접근 방식

**트리거(자동 매칭 금지):** 어드민이 ① `board_posts.status → 'resolved'` 변경, ② 답변 댓글(`board_comments`, `is_admin=true`) 작성, ③ `notice` 글 작성. `metadata.broker`는 자유 텍스트라 증권사명 문자열 자동 매칭은 오매칭 위험 → 사람이 status flip으로 판정.

**읽음/dedup (클라이언트 로컬, localStorage):**
- `ackedResolvedPostIds`: 진입 팝업을 이미 본 resolved post-id 집합 → 팝업 1회 dedup. **시각이 아니라 id 집합**으로 처리해 `updated_at`이 status 외 수정에도 갱신되는 부정확성을 우회.
- `lastSeenMyPosts`: **board_type→ISO 맵**. 의견/오류/거래내역서 제보 각 메뉴를 연 시각을 그 type 만 기록 → 메뉴별 unread 점 독립 해제. 어드민 답변 댓글의 불변 `created_at`과 비교.
- `lastSeenNotice`: 공지 마지막 확인 시각. 최신 notice `created_at`과 비교해 뱃지.

**팝업 게이트 순서:** ForceUpdateGate(차단 시 우선·팝업 미표시) → 인증 토큰 준비(AuthProvider 안에서 마운트) → `my-posts` 조회 → 미확인 resolved 1건만 바텀시트(개인 우선). 기존 `ForceUpdateGate`가 "마운트 시 조건 판정 후 오버레이" 참고 구현.

### 주요 변경 파일

**BE**
- `api/src/invest_note_api/routers/board.py` — `GET /board/my-posts` 신설(`get_current_user` 인증). 응답 필드 화이트리스트는 기존 `_NOTICE_DETAIL_FIELDS`/`_NOTICE_LIST_FIELDS`(board.py:66-70) 패턴 따라 `_MY_POST_FIELDS` 추가. 어드민 답변 댓글 포함.
- `api/src/invest_note_api/db_ops/board_repo.py` — `list_my_posts(user_id, ...)` 추가. `user_id = :me AND board_type IN ('feedback','bug_report','broker_statement')`, 각 글의 `board_comments`(is_admin=true) 합본. 기존 `get_post(with_relations=True)`의 comments 합본 로직(board_repo.py:126-138) 재사용.
- `api/src/invest_note_api/schemas/broker_statement.py`(또는 board 스키마) — my-posts 응답 모델(post + status + metadata + comments + created_at/updated_at).
- `api/tests/` — my-posts 엔드포인트 테스트(본인 글만·타인 0·notice 제외·댓글 포함).

**FE** (UX 확정: 메뉴 클릭 → "내가 보낸 내역" **목록 메인 패널**, 헤더 "작성" → **별도 작성 폼 패널**)
- `app/src/lib/board-seen.ts` — 신설. localStorage 헬퍼(`ackedResolvedPostIds`, `lastSeenMyPosts`는 **board_type→ISO 맵**, `lastSeenNotice`). 기존 컨벤션(`STORAGE_KEYS`, TradeBasicForm.tsx:83) 참고.
- `app/src/lib/api-client.ts` — `boardApi.myPosts()` + `MyPost*` 타입.
- `app/src/components/settings/MyPostCard.tsx` — 신설. 단일 글 카드(유형 라벨/증권사/상태 칩 검토중·완료·반려/어드민 답변, broker_statement resolved 시 가져오기 CTA). `onImport?` prop.
- `app/src/components/settings/MyPostsListPanel.tsx` — 신설. 제네릭 목록 메인 패널(props `open/onOpenChange/boardType/title/onCompose`). 본문 = 해당 board_type 본인 글(`MyPostCard`), 비면 `EmptyCard`. 헤더 우측 "작성" → `onCompose`. broker_statement resolved 가져오기 CTA(딥링크)는 카드에 유지.
- `app/src/components/base/FullScreenPanel.tsx` — `FullScreenPanelHeader` 에 옵셔널 `action` 슬롯(헤더 우측 버튼) 추가.
- `app/src/components/settings/FeedbackPanel.tsx` / `BugReportPanel.tsx` / `broker-statement/BrokerStatementPanel.tsx` — **write 폼 전용으로 유지/원복**(목록 미포함). 제출 성공 시 `queryKeys.myPosts` invalidate → 목록 패널 자동 갱신. import 흐름의 BrokerStatementPanel 도 폼만(변화 없음).
- `app/src/app/(app)/settings/page.tsx` — 의견/오류/거래내역서 제보 메뉴 클릭 → 각 **목록 패널** 오픈(+ 그 type lastSeen 기록·그 점만 해제). 목록 패널 `onCompose` → 해당 write 폼 패널 오픈(목록 위 스택). "공지사항"엔 새 공지 뱃지.
- `app/src/components/providers/MySubmissionsPopupGate.tsx` — 신설. `base/Drawer` 바텀시트. 미확인 resolved 제보 1건 + [지금 가져오기]. (개정 영향 없음)
- `app/src/app/layout.tsx` — `MySubmissionsPopupGate`를 `AuthProvider`+`QueryProvider` **안**에 마운트.

## 구현 체크리스트

- [x] BE: `board_repo.list_my_posts` + 응답 스키마 (user_id 스코프, 3개 board_type, is_admin 댓글 합본, notice 제외)
- [x] BE: `GET /board/my-posts` 라우트(`get_current_user`) + `_MY_POST_FIELDS` 화이트리스트
- [x] BE: pytest — 본인 글만/타인 0/notice 제외/댓글 포함 검증 (`cd api && poetry run pytest`)
- [x] FE: `lib/board-seen.ts` localStorage 헬퍼 (acked ids + board_type별 lastSeen 맵 + notice last-seen)
- [x] FE: `api-client.ts` myPosts 클라이언트 + 타입(BE 응답 shape 정합)
- [x] FE: `MyPostCard.tsx` + `MyPostsListPanel.tsx` (목록 메인 패널: 상태 칩·답변·resolved 딥링크·EmptyCard·헤더 "작성"). 작성 폼 패널은 write 전용 유지, 제출 시 myPosts invalidate
- [x] FE: `settings/page.tsx` 의견/오류/거래내역서 제보 메뉴 → 목록 패널, 목록 헤더 "작성" → 폼 패널. board_type별 unread 점 + 공지 뱃지
- [x] FE: `MySubmissionsPopupGate.tsx` 바텀시트 팝업(미확인 resolved 1회, 강제업데이트 우선)
- [x] FE: `layout.tsx`에 팝업 게이트 마운트(AuthProvider+QueryProvider 안)
- [x] 타입 체크 통과 (`pnpm -C app exec tsc --noEmit`)

## 2차 확장 (목록→상세 + 첨부 + 어드민 댓글 + 타입 prefix 숨김)

사용자 요구로 read-back UX를 공지사항 스타일(목록→상세)로 고도화하고 첨부·어드민 댓글·타입 노출을 보완한다.

### 목표
- 목록은 **공지사항 스타일 행**: 본문 일부(미리보기) + 상태 칩 + **글별 읽기 점**. 행 클릭 → **상세 화면**.
- **읽기 점(글별)**: 어드민 답변(새 댓글) **또는** 상태 변경(완료/반려) 중 하나라도 마지막 상세 열람 이후 발생하면 점. 상세를 열면 그 글 해제. 메뉴 점 = 그 type에 안 읽은 글이 하나라도 있으면 표시(글별 점에서 파생).
- **상세 화면**: 본문 전체 + 상태 + **첨부파일** + 어드민 댓글(사용자는 보기 전용).
  - 이미지 첨부: 클릭 시 미리보기(크게 보기/라이트박스).
  - PDF·엑셀 첨부: 다운로드.
- **어드민(admin/)**: 거래내역서 제보 상세에서 **댓글 작성 가능**(반려 시 사유 등록). 기존 `POST /admin/boards/{post_id}/comments` 재사용, broker_statement 상세에 댓글 작성 UI 노출.
- **`[unsupported_broker]`/`[overseas_trade]` 사용자 노출 금지**: 제목이 `[type] 증권사`로 합성되어 새므로 FE 표시에서 prefix 제거(또는 broker_statement는 broker만 표시).

### 설계 결정
- **읽기 점 추적(클라이언트 로컬)**: `lastSeenMyPosts`(board_type→ISO 맵)를 **글별 맵 `lastReadMyPost`(postId→ISO)** 로 대체/보강. 글의 최신 활동 = `max(updated_at, 최신 is_admin 댓글 created_at)`. 이 값 > `lastReadMyPost[postId]` 면 안 읽음. 상세 열 때 `lastReadMyPost[postId]=now`. (updated_at은 status 변경 시 트리거로 갱신되므로 상태변경 신호로 사용 — 본문 편집 잡음은 무해.)
- **첨부(BE)**: 현재 my-posts가 제외한 `attachments`를 응답에 추가. 각 첨부 `{ id, original_name, content_type, size_bytes, url }` — `url`은 **소유자 스코프 presigned GET**(my-posts가 이미 user_id 스코프라 본인 글 첨부만). 첨부 없으면 `[]`. 기존 어드민 `GET /admin/boards/attachments/{id}/download` 의 presigned GET 발급 로직 참고.

### 주요 변경 파일 (2차)
- **BE** `routers/board.py`/`schemas/board.py`/`db_ops/board_repo.py` — my-posts 응답에 attachments(+presigned GET) 추가. `_MY_POST_FIELDS` 갱신. 첨부 합본·소유자 스코프 테스트.
- **FE** `app/` — `MyPostsListPanel`을 공지 스타일 목록행(미리보기+상태+글별 점)으로 개편, **상세 패널 신설**(`MyPostDetailPanel`), 이미지 라이트박스(base/Dialog 등), PDF/엑셀 다운로드(presigned URL → `openExternal`), `board-seen.ts`에 `lastReadMyPost` 글별 맵, 제목 prefix 제거 유틸.
- **Admin** `admin/` — `StatementDetail.tsx`(broker_statement 상세)에 댓글 작성 UI 추가(다른 board_type 상세의 댓글 컴포저 재사용). 반려(상태 closed) 시 사유 댓글 흐름.

### 구현 체크리스트 (2차 FE)

- [x] FE: `api-client.ts` `MyPostAttachment` + `MyPost.attachments`(snake_case 1:1)
- [x] FE: `lib/board-post.ts` 신설 — `stripTypePrefix`/`getPostDisplayTitle`(prefix 숨김)·`getPostLatestActivity`·`isMyPostUnread`·`STATUS_META`/`TYPE_LABEL`·`formatPostDate`/`formatFileSize`
- [x] FE: `board-seen.ts` `lastSeenMyPosts`(type맵) → `lastReadMyPost`(postId맵) 교체(new STORAGE_KEY)
- [x] FE: `MyPostsListPanel` 공지 스타일 행(미리보기+상태 칩+글별 읽기 점), 행 클릭 → 상세
- [x] FE: `MyPostDetailPanel` 신설 — 본문 전체+상태+첨부(이미지 라이트박스 base/Dialog z-200 / PDF·엑셀 `openExternal` 다운로드)+어드민 댓글+resolved 가져오기 CTA, 열람 시 `setLastReadMyPost`
- [x] FE: `settings/page.tsx` 메뉴 점 = 그 type 안읽은 글 1개+ 파생(글별 read map). 목록 열 때 type별 lastSeen 기록 제거
- [x] FE: `[unsupported_broker]`/`[overseas_trade]` prefix 사용자 노출 0(모든 제목 `getPostDisplayTitle` 경유)
- [x] FE: 타입 체크 통과(`pnpm -C app exec tsc --noEmit`)
- [x] BE: my-posts 응답 attachments(소유자 스코프 presigned GET) — 랜딩 완료, FE shape 정합
- [x] Admin: broker_statement 상세 댓글 작성 UI (기존 BoardCommentThread/Form 재사용)

## 우려사항 / 리스크

- **`updated_at` 부정확**: status 외 수정에도 갱신 → 팝업은 resolved post-id 집합 dedup으로, 답변 뱃지는 댓글 불변 `created_at`으로 우회(설계 반영).
- **읽음=기기 로컬**: 재설치/타 기기에서 unread·팝업 재노출 가능. 의도된 트레이드오프(서버 읽음 상태는 범위 외). 어드민이 개별 읽음 여부 확인 불가.
- **팝업 타이밍**: 인증 토큰 준비 전 호출 금지(AuthProvider 안 마운트), ForceUpdateGate 차단 시 미표시 — 순서 보장 필요.
- **보안**: my-posts는 토큰 user_id로만 스코프(body의 user_id 무시), 타인 글·notice 절대 노출 금지 — 테스트로 가드.
