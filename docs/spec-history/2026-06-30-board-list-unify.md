# 게시판 목록 조회 통합 + 페이지네이션 사양서

## 배경 / 목적

게시판 4종(notice / feedback / bug_report / broker_statement) 중 `my-posts` 계열만
**무페이지네이션 전량 반환**이라 글이 쌓이면 응답 비용(첨부 presigned URL 재서명 포함)이
선형 증가한다. notices 는 이미 페이지네이션(`list_notices` + `useInfiniteQuery`)으로
전환됐으므로, my-posts 도 동일 패턴(board_type 필터 + page/page_size/total)으로 통일한다.

단, my-posts 응답을 페이지네이션하면 현재 **목록 전량 순회로 파생되던 미확인(unread) 신호**가
page1 만 보고 판정해 깨진다:
- `settings/page.tsx`: board_type별 unread dot 을 `myPostsQuery.data.items` 순회로 계산.
- `MySubmissionsPopupGate`: resolved broker_statement 중 `popup_acked===false` 1건을 전량에서 탐색.

따라서 unread/popup 신호를 목록과 분리한 **전용 경량 엔드포인트(`GET /v1/board/unread-summary`)**로
빼낸다. 이 엔드포인트는 page 와 무관하게 **본인 글 전체를 스캔**해 board_type별 unread bool 과
진입 팝업 1건을 단일 출처로 제공한다.

연결: docs/backlog.md(게시판 운영 후속), 메모리 [[project_board_structure]],
[[project_broker_statement_submission]], [[project_import_staging_durable]].

## 범위 (Scope)

포함:
- BE: `board_repo.list_my_posts` 에 board_type 필터 + page/page_size/total 추가(레거시 무인자 호출은 전량 보존).
- BE: `board_repo` 에 unread 집계 함수 추가 + `GET /v1/board/unread-summary` 신설.
- BE: `routers/board.py` `list_my_posts` 응답을 additive `{items, total, page}` 로 확장.
- FE: api-client/query-keys 에 unread-summary + 페이지네이션 my-posts 추가.
- FE: `MyPostsListPanel` 무한스크롤 전환, `settings`·`MySubmissionsPopupGate` 를 unread-summary 소비로 전환.
- FE(선택): `NoticePanel`/`MyPostsListPanel` 공통 무한목록 스캐폴드 추출.
- docs/decisions.md 갱신.

제외:
- **DB 스키마 변경 없음**(페이지네이션=LIMIT/OFFSET, board_type 필터=WHERE, 기존 컬럼 사용). Alembic 마이그레이션 불필요.
- notices(공지) 경로는 **건드리지 않는다**. `has_unread_notice` 는 서버 EXISTS 라 page 무관 → pagination 으로 깨지지 않음. notice unread 를 unread-summary 로 통합하지 않는다(blast radius 대비 정합 이득 없음).
- comment 첨부 뷰어, 검색(q) UI 등 기존 미구현 항목.

## 가정 (Assumptions)

- my-posts 무한스크롤 page_size 기본 20(notices 와 동일 관용). 첨부 presigned URL 은 page 단위로만 동봉.
- unread-summary 응답 popup 은 정확히 1건(created_at desc 첫 매칭) 또는 null.

## 핵심 설계 결정 (불변식)

1. **권한 경계 혼합 금지.** my-posts/unread-summary 는 `user_id` 토큰 스코프(본인 글만), notice 는 전체 공개. 한 핸들러로 합치지 않는다(repo 페이지네이션 로직만 공유, 엔드포인트 분리 유지).
2. **unread 단일 출처.** FE 는 목록에서 unread 를 파생하지 않는다. 행(row)별 점은 각 `MyPost.unread`(page 내), board_type별 메뉴 점·진입 팝업은 `unread-summary` 가 단일 출처.
3. **레거시 하위호환(가장 빡빡한 제약).** 라이브 네이티브 v1.3.4 는 `/board/my-posts` 를 **무인자**로 호출하고 `.items` 만 읽는다. `board_type` 파라미터는 **반드시 Optional** — 생략 시 전 board_type 전량 반환(레거시 동작), 응답은 additive(`{items, total, page}`, 구 클라이언트는 `.items` 만 읽어 무해). board_type 필수화 금지(422 로 라이브 앱 파손).
4. **unread-summary 는 page 비의존.** 새 페이지네이션 `list_my_posts` 위에 얹지 말 것 — 제거하려는 page1-only 버그가 재발한다. 본인 글 **전체**를 스캔해 집계한다.
5. **unread 규칙 단일 정의.** unread-summary 는 BE `_compute_unread`(FE `isMyPostUnread` 미러)를 **그대로 재사용**한다(Python 에서 글+어드민 댓글+read JOIN 으로 계산, 첨부/R2 서명 생략 = "경량"). SQL EXISTS 집계로 규칙을 3번째 복제하지 않는다.
6. **invalidation prefix 보존.** query-keys 에서 `["my-posts"]` 를 **무효화 루트 prefix 로 유지**한다. 신규 reader 키는 그 하위(`["my-posts","list",boardType]`, `["my-posts","unread-summary"]`)로 둔다. → 기존 invalidator(FeedbackPanel/BugReportPanel/BrokerStatementPanel/MyPostDetailPanel/MySubmissionsPopupGate)가 `queryKeys.myPosts` 루트를 무효화하면 list·summary 가 함께 갱신되어 **invalidator 측 수정 불필요**.
7. **롤아웃 순서.** `unread-summary` 는 신규 엔드포인트 → **BE 가 FE OTA 보다 먼저 배포**돼야 한다(BE/FE 독립 배포). FE 는 BE-lag 대비 응답 부재 시 안전 degrade(점 미표시).

## 작업 단위

### 1. [BE] board_repo.list_my_posts — board_type 필터 + 페이지네이션
- `api/src/invest_note_api/db_ops/board_repo.py`
- `list_my_posts(conn, user_id, *, board_type=None, page=1, page_size=DEFAULT_PAGE_SIZE)` → `(rows, total)`.
  - `board_type` None → 기존 3종 전량(레거시), total=len, LIMIT 미적용.
  - `board_type` 지정 → 해당 타입만 + count(total) + LIMIT/OFFSET. 첨부/댓글 합본은 page 행에 한정.
- verify: `cd api && poetry run pytest tests/test_board_repo.py -q`
- 의존: 없음

### 2. [BE] board_repo.unread_summary — 전량 스캔 집계
- `api/src/invest_note_api/db_ops/board_repo.py`
- 신규 함수: 본인 글 **전체**(3종) + 어드민 댓글 + `board_post_reads` JOIN 만 fetch(첨부/R2 서명 없음). 글마다 `_compute_unread` 재사용해 board_type별 unread bool 집계 + resolved broker_statement 중 `popup_acked_at IS NULL` created_at desc 첫 건을 popup 후보(post_id, broker)로 반환.
- verify: `cd api && poetry run pytest tests/test_board_repo.py -q`
- 의존: 없음

### 3. [BE] routers/board.py — my-posts 페이지네이션
- `api/src/invest_note_api/routers/board.py` `list_my_posts`
- query param `board_type: str | None = None`, `page: int = 1`, `page_size: int = 20` 추가. repo 호출에 전달, 응답 `{items, total, page}` (MyPostsResponse 에 total/page 추가). 첨부 presign 은 page 행만.
- 불변식 3 준수: 무인자 호출 시 전량 반환.
- verify: `cd api && poetry run pytest tests/test_board.py -q`
- 의존: 단계 1

### 4. [BE] routers/board.py — GET /board/unread-summary
- `api/src/invest_note_api/routers/board.py`
- `GET /board/unread-summary`(get_current_user). 응답 shape(BE/FE 합의):
  ```json
  {
    "unread": {"feedback": false, "bug_report": true, "broker_statement": false},
    "popup": {"post_id": "uuid", "broker": "삼성증권"}
  }
  ```
  popup 없으면 `"popup": null`. schemas/board.py 에 응답 모델 추가.
- verify: `cd api && poetry run pytest tests/test_board.py -q`
- 의존: 단계 2

### 5. [FE] api-client + query-keys
- `app/src/lib/api-client.ts`, `app/src/lib/query-keys.ts`
- api-client: `boardApi.myPosts(boardType?, page?)` → `?board_type=&page=` 쿼리; `MyPostsResponse` 에 `total`/`page` 추가; `boardApi.unreadSummary()` + `UnreadSummary` 타입(unread map + popup `{post_id, broker} | null`).
- query-keys: `myPostsList: (boardType) => ["my-posts","list",boardType]`, `unreadSummary: ["my-posts","unread-summary"]`. **`myPosts: ["my-posts"]` 루트는 invalidation prefix 로 유지**(불변식 6).
- verify: `pnpm -C app exec tsc --noEmit`
- 의존: 단계 3, 4

### 6. [FE] MyPostsListPanel 무한스크롤 전환
- `app/src/components/settings/MyPostsListPanel.tsx`
- `useQuery(myPosts)` → `useInfiniteQuery(myPostsList(boardType))`, `queryFn` 에 board_type+pageParam, `getNextPageParam`(누적<total), "더 보기" 버튼(NoticePanel 패턴). 클라이언트 board_type 필터 제거(서버 필터). 행별 unread 점은 각 item.unread 유지.
- detail: `items.find` 가 로드된 page 들에서 조회되도록 유지. markPostRead invalidate 는 `queryKeys.myPosts` 루트로 두면 list·summary 동시 갱신(MyPostDetailPanel 무변경 가능).
- verify: `pnpm -C app exec tsc --noEmit` + 동작: 행 20개 초과 시 "더 보기" 로 다음 page 로드, 상세 진입 시 점 해제.
- 의존: 단계 5

### 7. [FE] settings/page.tsx — 3-dot 을 unread-summary 로
- `app/src/app/(app)/settings/page.tsx`
- `myPostsQuery`(전량) 제거 → `unreadSummary` 쿼리. `myPostsUnread` 파생을 `summary.unread` 직접 사용으로 교체. **notices 경로(noticeUnread / markNoticesSeen / noticesQuery)는 무변경.**
- verify: `pnpm -C app exec tsc --noEmit` + 동작: 어드민 답변 달린 board_type 메뉴에 점 표시.
- 의존: 단계 5

### 8. [FE] MySubmissionsPopupGate — unread-summary popup
- `app/src/components/providers/MySubmissionsPopupGate.tsx`
- `myPosts`(전량) 쿼리 → `unreadSummary`. target 을 `summary.popup`(post_id+broker)에서 직접. ack 는 `ackPopup(post_id)` 후 `queryKeys.myPosts` 루트 invalidate(summary 갱신, 무변경).
- verify: `pnpm -C app exec tsc --noEmit` + 동작: resolved broker_statement 1건 시 진입 팝업 1회.
- 의존: 단계 5

### 9. [FE·선택] 공통 무한목록 스캐폴드 추출
- NoticePanel/MyPostsListPanel 공통(FullScreenPanel + loading/error/empty + 행 컨테이너 + "더 보기")을 generic `InfiniteListPanel`(renderRow/detail host 주입)로 추출. 행/상세 타입별 렌더는 각자 유지.
- **추상화가 누수되면 통합하지 말 것**(CLAUDE.md 단순성 우선). 비차단·후순위.
- verify: `pnpm -C app exec tsc --noEmit`
- 의존: 단계 6

### 10. [docs] decisions.md
- unread-summary 가 `_compute_unread` 를 재사용(규칙 단일 정의, SQL 집계 미채택) + query-key prefix 보존 전략(invalidator 무수정) 트레이드오프 기록.
- 의존: 없음

### QA-A. [QA] BE my-posts 페이지네이션 shape
- `{items, total, page}` additive · board_type 필터 동작 · **무인자 호출 전량 반환(레거시)** · 첨부는 page 행만.
- 의존(blockedBy): 단계 3

### QA-B. [QA] BE unread-summary shape + page 비의존
- unread map 3키 · popup `{post_id, broker}|null` · **본인 글 전체 스캔(page 무관)** · `_compute_unread` 패리티 · 타인/notice 비포함.
- 의존(blockedBy): 단계 4

### QA-C. [QA] FE-BE shape 정합 + reader 마이그레이션
- api-client 타입 ↔ BE 응답 1:1 · 모든 reader(settings·MyPostsListPanel·MySubmissionsPopupGate) 전환 완료 · invalidation prefix(`["my-posts"]`) 보존으로 invalidator 무파손 · 롤아웃 순서(BE 선배포) 명시 · BE-lag degrade(점 미표시).
- 의존(blockedBy): 단계 6, 7, 8

## 완료 조건
- [ ] 모든 단위 verify 통과(pytest test_board*.py / tsc)
- [ ] `docs/decisions.md` 갱신
- [ ] QA-A/B/C 통과
- [ ] spec → spec-history 이동 준비(YYYY-MM-DD-board-pagination.md)
