# 게시판 알림 → 푸시 전환 + 알림 이력 페이지 — 사양서

> 승인된 계획: `~/.claude/plans/structured-sprouting-feather.md` 를 구현 단위로 구체화한 것.
> 작업 원장(체크리스트·의존성 그래프·담당): `_workspace/01_planner_summary.md`.

## 배경 / 목적

현재 앱의 모든 사용자 알림은 인앱 dot 배지 + 폴링뿐이라 사용자가 앱을 열어야만 게시판 처리
결과(관리자 답변·상태변경)를 인지한다. 또한 개별 알림 레코드가 저장되지 않고 board 상태에서
매번 계산되므로 "무엇을 언제 통지받았는지" 이력이 남지 않는다.

- (1) 게시판 처리 통지를 **푸시 알림**으로 전환(Phase 2, 게이트)
- (2) **알림 이력 페이지** 신설(Phase 1)
- (3) 트리거를 하나의 알림 피드로 정리(Phase 1)

roadmap/backlog 연결: 게시판(project_board_structure)·푸시 인프라 선통과(project_native_prereview_batch)
위에 얹는 활성화 작업.

### 확정 트리거 스코프

| 트리거 | 이력/푸시 | 성격 | 저장 |
|--------|:---:|------|------|
| ① 게시판 답변(관리자 댓글) | ✅ | per-user | notifications row |
| ② 거래내역서 제보 resolved(status 변경) | ✅ | per-user | notifications row(①의 status 경로) |
| ③ 새 공지사항 | ✅ | broadcast | **row 미생성 — union 조회** |
| ④ 강제 업데이트 | ❌ 제외 | 차단 게이트 | - |

## 범위 (Scope)

- 포함(Phase 1): notifications 테이블·repo·조회/쓰기 라우터·producer 배선, 홈 헤더 벨 +
  설정 '알림' 행, 알림 이력 패널, api-client/query-keys.
- 포함(Phase 2, 코드만·활성화 게이트): device_tokens 테이블·토큰 등록 엔드포인트·push_sender
  서비스(FCM v1 + APNs), FE 토큰 등록. **시크릿 없으면 sender no-op**.
- 제외: iOS `aps-environment` production 승격(네이티브 재배포·재심사 — Phase 2 배포 스텝에서
  사용자가 수행), 기존 unread-summary 와의 완전 일원화(후속), ④ 강제 업데이트 피드화.

## 핵심 제약 (구현 시 반드시 준수)

1. **공지(③)를 notifications 에 per-user row 로 넣지 않는다.** `0012_board_reads` 의
   high-water mark 결정을 보존(신규가입자 backfill 버그 회피). 이력 조회 시 **SQL UNION ALL**
   로 합친다. 두 producer 는 `board_type='notice'` 를 **무시**한다.
2. 벨 아이콘은 **홈 헤더에만**(Records/Analysis actions 는 점유됨). 설정 '소식' 섹션에 '알림'
   행 추가. unread 표시는 기존 관례 `size-1.5 rounded-full bg-primary` (boolean dot).
3. 마이그레이션: 리비전 ID ≤32자, OWNER `invest_note_app`, 현재 head = **`0018_drop_import_staging`**
   → 신규 `0019_notifications`. 컨테이너 자동미적용(수동 upgrade), 로컬 up/down 검증 필수.
4. Phase 2 push sender 는 FCM/APNs 시크릿 없으면 조용히 skip(PostHog no-op 계약 사상). Phase 1
   무영향.
5. 기존 unread-summary(설정 per-board-type 점)는 **유지**. notifications 피드는 상위 통합 레이어로
   추가(surgical, 공존).

---

## BE API Shape 명세 (be/fe 병렬 계약 — 확정)

모든 경로는 `/v1` prefix 하위(main.py app_routers 로 등록). 인증 `get_current_user`(토큰 user_id).

### 피드 아이템 shape (공통)

두 이종 소스(notifications row + notice)를 union 하므로 discriminator 와 계산된 read 상태를
포함한다. 응답 필드(snake_case, admin 관례 passthrough):

```jsonc
{
  "id": "uuid",                       // notification.id 또는 notice(board_post).id
  "source": "notification" | "notice",// FE 라우팅 discriminator (필수)
  "type": "board_reply" | "board_status" | "notice",
  "title": "string",
  "body": "string | null",
  "board_type": "string | null",      // 딥링크용: 'feedback'|'bug_report'|'broker_statement' (notice 는 'notice')
  "ref_id": "uuid | null",            // board_posts.id (딥링크 대상)
  "created_at": "iso8601",
  "read": true                        // notification: read_at IS NOT NULL / notice: created_at <= COALESCE(notices_seen_at, users.created_at)
}
```

- `board_type` 은 notifications 행에 **컬럼으로 저장**(producer 가 set)해 조회 시 join 없이 project.
- `read` 는 서버 계산값(row 의 read_at, notice 의 high-water 비교). FE 는 계산하지 않는다.
- **⚠️ notice `read` 는 반드시 `COALESCE(notices_seen_at, users.created_at)` fallback 사용**
  (state row 없는 신규가입자에게 `bare notices_seen_at IS NULL` → 옛 공지 전부 unread = 0012
  backfill 버그 재발). `board_repo.has_unread_notice` 가 쓰는 동일 fallback 식을 재사용(단일 출처).

### 엔드포인트

| # | method | path | request | response |
|---|--------|------|---------|----------|
| A | GET | `/v1/notifications` | query: `page`(기본1), `page_size`(기본20) | `{ "items": FeedItem[], "total": int, "page": int }` |
| B | GET | `/v1/notifications/unread-count` | - | `{ "count": int }` (notifications read_at IS NULL 수 + 안읽은 notice 수) |
| C | POST | `/v1/notifications/{id}/read` | - | `204` (source=notification 만 유효. 없는/타인 row → 404) |
| D | POST | `/v1/notifications/read-all` | - | `204` (notifications 전체 read_at=now() **AND** `set_notices_seen_at(now())`) |

**Union/페이지네이션 규칙(A):** notifications 와 board_posts(board_type='notice')를 각각 피드
컬럼으로 project 한 뒤 **단일 SQL `UNION ALL` … `ORDER BY created_at DESC LIMIT/OFFSET`**.
in-memory merge 금지(offset 페이징 깨짐). `total` 은 두 소스 count 합. 소유권: notifications 는
`user_id = $me`, notice 는 전체 공개(union subquery 에서 스코프 분기). 이 쿼리는
`notifications_repo` 가 소유하되 notice projection 서브쿼리를 포함한다(board_repo 의 notice 컬럼
관례 참조).

**read-all(D) 이중 소스:** notifications 행 read 처리 + notices_seen_at high-water upsert 를
반드시 함께 수행. 하나만 하면 벨 점이 남는다. 이것이 '패널 진입 시 미읽음 해소' 메커니즘.

**unread-count(B):** `count(notifications where read_at is null) + count(notices where
created_at > COALESCE(notices_seen_at, users.created_at))`. fallback 을 count 내부에 포함(신규
가입자 옛 공지 미포함). FE 벨은 boolean dot(`count > 0`)으로만 사용(제약 #2).

---

## 작업 단위 — Phase 1 (지금 출시 가능)

### 1. [BE] 마이그레이션 `api/alembic/versions/0019_notifications.py`
- `notifications` 테이블 생성. 컬럼: `id uuid PK default gen_random_uuid()`, `user_id uuid NOT
  NULL REFERENCES users(id) ON DELETE CASCADE`, `type text NOT NULL`, `title text NOT NULL`,
  `body text`, `board_type text`, `ref_type text`, `ref_id uuid`, `created_at timestamptz NOT
  NULL default now()`, `read_at timestamptz`.
- 인덱스 `notifications_user_created_idx (user_id, created_at DESC)`.
- OWNER `invest_note_app`(0001/0012 관습). down_revision=`0018_drop_import_staging`. 리비전 ID
  `0019_notifications`(≤32자 OK).
- verify: `cd api && make migration up local` 후 `make migration down local` 왕복 성공
  (또는 `poetry run alembic upgrade head` / `downgrade -1`).
- 의존: 없음.

### 2. [BE] repo `api/src/invest_note_api/db_ops/notifications_repo.py` (신규)
- `insert(conn, *, user_id, type, title, body, board_type, ref_type, ref_id) -> dict`
- `list_feed(conn, user_id, *, page, page_size) -> (items, total)` — 제약 #1 UNION ALL 쿼리
  (notifications ∪ notice, 피드 컬럼 project, created_at DESC, offset). notice `read` =
  `created_at <= COALESCE(notices_seen_at, users.created_at)` (**`has_unread_notice` 와 동일
  fallback 재사용** — bare notices_seen_at 금지, 신규가입자 backfill 버그 회피).
- `mark_read(conn, notification_id, user_id) -> bool`(소유·존재 게이트, 멱등)
- `mark_all_read(conn, user_id) -> None`(notifications read_at=now(); notices_seen 는 라우터가
  `board_repo.set_notices_seen_at` 로 별도 호출 — repo 경계 유지)
- `unread_count(conn, user_id) -> int`(notifications 미읽음 + notice 미읽음 합)
- 패턴: `board_repo` row→dict(UUID→str, jsonb→dict), `_to_dt` 관례 따름.
- verify: `cd api && poetry run pytest tests/test_notifications_repo.py -q` (단위 4에서 작성)
- 의존: 단계 1.

### 3. [BE] 스키마 `api/src/invest_note_api/schemas/notification.py` (신규)
- `NotificationItem`(위 FeedItem shape), `NotificationListResponse{items,total,page}`,
  `UnreadCountResponse{count}`.
- verify: `cd api && poetry run pytest tests/test_notifications_router.py -q` (단위 5)
- 의존: 없음(shape 확정 — 병렬 가능).

### 4. [BE] 라우터 `api/src/invest_note_api/routers/notifications.py` (신규) + `main.py` 등록
- 엔드포인트 A/B/C/D 구현(위 shape). `router = APIRouter(prefix="/notifications",
  tags=["notifications"])`.
- **main.py L75 `app_routers` 튜플에 `notifications.router` 추가**(이 단위에서 두 번째 파일
  터치 — 누락 금지). import 도 추가.
- C: mark_read 실패(없음/타인) → 404. D: `mark_all_read` + `board_repo.set_notices_seen_at`.
- verify: `cd api && poetry run pytest tests/test_notifications_router.py -q`
- 의존: 단계 2, 3.

### 5. [QA-BE] `api/tests/test_notifications_repo.py` + `tests/test_notifications_router.py`
- repo: insert→list_feed 순서(created_at DESC), notice union 합류, mark_read 멱등·타인 격리,
  unread_count 이중소스, read-all 후 notice 미읽음까지 0.
- router: A 페이지네이션 shape, B count, C 404(타인/없음)·204, D 후 unread-count=0.
- fake_pool 관례(board repo 테스트 참조).
- verify: 위 두 pytest 파일 통과.
- 의존: 단계 2·4 (각 완료 직후 unblock — incremental).

### 6. [BE] Producer 배선 `api/src/invest_note_api/routers/admin_board.py`
- `create_board_comment`(관리자 댓글): `create_comment` 는 **댓글 행만** 반환하므로 post 를
  조회해 **글 소유자 user_id + board_type** 획득 → 소유자에게 `notifications_repo.insert`
  (type=`board_reply`, title=board_type 라벨, body=댓글 발췌, board_type, ref_type=`board_post`,
  ref_id=post_id). **소유자에게 통지(admin 본인 아님)**. `board_type='notice'` 는 skip.
- `update_board`(status 변경): `update_post` 는 `*` 반환(user_id·board_type 有). **`"status" in
  fields` 일 때만** insert(type=`board_status`). title/body/is_pinned 편집엔 발화 금지.
  `board_type='notice'` skip. ②(broker_statement resolved)가 여기로 자연 포함.
- 실패 격리: 알림 insert 실패가 댓글/상태변경 본 작업을 깨지 않도록 배선(best-effort, 예외
  삼킴 또는 동일 트랜잭션 여부는 be-engineer 판단 — spec 권장: 본 작업 성공 우선).
- verify: `cd api && poetry run pytest tests/test_admin_board.py -q` (단위 7에서 producer 케이스 추가)
- 의존: 단계 2.

### 7. [QA-BE] `api/tests/test_admin_board.py` producer 케이스 추가
- 관리자 댓글 → 소유자 notifications row 1건(admin 아님). status 변경 → board_status row.
  title-only PATCH → row 미생성. notice 댓글/변경 → row 미생성.
- verify: `cd api && poetry run pytest tests/test_admin_board.py -q`
- 의존: 단계 6.

### 8. [FE] `app/src/lib/query-keys.ts`
- `notifications: ["notifications"] as const`, `notificationsList: ["notifications","list"] as
  const`, `notificationsUnread: ["notifications","unread"] as const`. (notices 패턴 참조 — prefix
  공유로 한 번의 invalidate.)
- verify: `pnpm -C app exec tsc --noEmit`
- 의존: 없음.

### 9. [FE] `app/src/lib/api-client.ts` `notificationApi`
- `list(page=1)` → GET `/notifications?page=`, `unreadCount()` → GET
  `/notifications/unread-count`, `markRead(id)` → POST `/notifications/{id}/read`,
  `markAllRead()` → POST `/notifications/read-all`. 응답 타입은 BE shape 그대로(FeedItem[]).
  ROUTES.notifications 블록 추가.
- verify: `pnpm -C app exec tsc --noEmit`
- 의존: 단계 8(타입 참조), BE shape(문서 확정 — 병렬 가능).

### 10. [FE] 알림 이력 패널 `app/src/components/notifications/NotificationHistoryPanel.tsx` (신규)
- `FullScreenPanel`(라우트 아님) + `useInfiniteQuery(queryKeys.notificationsList)` +
  `LoadMoreButton` + `EmptyCard`/`ErrorState`(공유 재사용). 행: 제목·본문발췌·상대시각·미읽음 점.
- 진입 시 `markAllRead()` 호출 → `notifications` invalidate(미읽음 자연 해소). 개별 행 탭 시
  `markRead(id)`(source=notification) 후 딥링크. **렌더 순서 주의**: 초기 fetch 의 unread 상태를
  화면 표시용으로 먼저 캡처하고 `markAllRead()` 는 **first paint 이후** 발화(안 그러면 계획이
  원하는 미읽음 점이 이미 stale). 미읽음 점 표시는 초기 응답의 `read` 값 기준.
- 딥링크: `source='notice'` → NoticePanel 오픈(**목록 레벨** — 특정 공지 딥링크 아님, MVP 허용.
  NoticePanel 에 prop 추가 기대 안 함), `source='notification'` → 해당 board_type 의
  `MyPostsListPanel` 을 `initialOpenPostId=ref_id` 로 오픈(단계 11 prop, 특정 글까지 딥링크).
  딥링크 깊이가 비대칭임을 명시. 새 detail fetcher 만들지 말 것.
- verify: `pnpm -C app exec tsc --noEmit` + `pnpm -C app test`
- 의존: 단계 9, 11.

### 11. [FE] `app/src/components/settings/MyPostsListPanel.tsx` — `initialOpenPostId` prop 추가
- optional prop `initialOpenPostId?: string`. 목록 로드 후 해당 id 글을 자동으로
  `MyPostDetailPanel` 오픈(딥링크 진입점). 기존 사용처(무전달)는 무영향.
- verify: `pnpm -C app exec tsc --noEmit`
- 의존: 없음(단계 10과 계약만 맞추면 병렬).

### 12. [FE] 홈 헤더 벨 `app/src/components/home/HomeDashboard.tsx`
- L162~182 children 헤더: 기존 '자산 추이' 버튼(`right-0`) **좌측**에 아이콘 전용 벨 버튼 추가
  (`useQuery(queryKeys.notificationsUnread, notificationApi.unreadCount)`). unread>0 시
  `size-1.5 rounded-full bg-primary` 점 오버레이(아이콘 우상단). 탭 → NotificationHistoryPanel
  오픈. content `pr-24`→`pr-32` 조정. Records/Analysis 헤더 무변경.
- verify: `pnpm -C app exec tsc --noEmit` + 동작(벨 노출·점등)
- 의존: 단계 9, 10.

### 13. [FE] 설정 '알림' 행 `app/src/app/(app)/settings/page.tsx`
- '소식' 섹션(L127~150) 공지사항 위/아래에 `SettingsMenuRow label="알림"
  dot={notifUnread}` 추가. 탭 → NotificationHistoryPanel 오픈(로컬 useState + 패널 렌더).
  `notifUnread` 는 unread-count useQuery.
- verify: `pnpm -C app exec tsc --noEmit`
- 의존: 단계 9, 10.

### 14. [QA-FE] `app/src/components/notifications/__tests__/NotificationHistoryPanel.test.tsx`
- 목록 렌더·미읽음 점·빈/에러 상태·행 탭 markRead 호출·딥링크 라우팅(source 분기) mock 검증.
- verify: `pnpm -C app test`
- 의존: 단계 10.

### 15. [DOC] `docs/decisions.md` 갱신
- 트레이드오프 3건 기록: (a) 전용 notifications 테이블 vs board 상태 파생 → 전용 테이블 채택
  (이력·읽음상태 필요), (b) 공지 union 조회 vs per-user row → union(0012 high-water 보존,
  backfill 버그 회피), (c) push sender 시크릿 없으면 no-op 게이트(PostHog 계약 사상).
- verify: 문서 diff 리뷰.
- 의존: 없음(단계 1 결정 확정 후 병렬).

### 16. [QA] Phase 1 정합성 검증 (E2E headless preview)
- BE 응답 shape ↔ FE FeedItem 타입 일치(source/board_type/read 필드). 어드민에서 답변 작성 →
  앱 벨 점등 → 이력 패널 진입 → 행 탭 딥링크(MyPostsListPanel/NoticePanel) → 배지 해소.
- headless preview 포트 3100 JWT 주입(project_preview_headless_auth_bypass), 데이터는 로컬 BE 3108.
- 메모리 함정 체크: project_be_buy_meta_cascades_to_sell(무관), high-water 보존, union 정렬.
- verify: 시나리오 통과 + `poetry run pytest -q` + `pnpm -C app exec tsc --noEmit` + `pnpm -C app test`.
- 의존: 단계 5·7·12·13·14.

---

## 작업 단위 — Phase 2 (코드 작성, 활성화 게이트)

> 활성화 전제(사용자/외부): FCM 서비스계정 JSON, APNs .p8(key id·team id), iOS
> `aps-environment`→`production`(네이티브 재배포·재심사), 실기기 검증. 시크릿 없으면 sender no-op.

### 17. [BE] 마이그레이션 `api/alembic/versions/0020_device_tokens.py`
- `device_tokens`(user_id uuid FK CASCADE, token text, platform text 'ios'|'android',
  created_at, last_seen_at; UNIQUE(user_id, token)). OWNER invest_note_app.
  down_revision=`0019_notifications`.
- verify: `make migration up local` / `down local` 왕복.
- 의존: 단계 1.

### 18. [BE] 토큰 등록 `api/src/invest_note_api/routers/me.py` + repo
- `POST /v1/me/push-token` req `{ token, platform }` → upsert(user_id, token) last_seen_at 갱신,
  204. 로그아웃/탈퇴 정리 훅(기존 삭제 경로에 device_tokens 정리).
- verify: `cd api && poetry run pytest tests/test_me_push_token.py -q`
- 의존: 단계 17.

### 19. [BE] `api/src/invest_note_api/services/push_sender.py` (신규)
- FCM HTTP v1(Android, 서비스계정) + APNs token-based(.p8, iOS). notifications insert 훅에서
  사용자 토큰으로 전송. 공지(③)는 broadcast(토큰 순회). env: `FCM_SERVICE_ACCOUNT_JSON`,
  `APNS_KEY_P8`/`APNS_KEY_ID`/`APNS_TEAM_ID`. **없으면 no-op(로그만) — Phase 1 무영향**.
- 단계 6 producer 에 sender 호출 훅 배선(insert 직후, best-effort).
- verify: `cd api && poetry run pytest tests/test_push_sender.py -q` (no-op 경로·payload 조립 단위)
- 의존: 단계 6, 18.

### 20. [FE] `app/src/lib/push/registerPush.ts` (신규) + `layout.tsx` 마운트
- 로그인 후 `PushNotifications.requestPermissions()`→`register()`, `registration` 리스너
  토큰 → `POST /me/push-token`, `pushNotificationActionPerformed` → 알림 이력/딥링크. Android
  13+ POST_NOTIFICATIONS 런타임 권한. 루트 `layout.tsx` 마운트.
- verify: `pnpm -C app exec tsc --noEmit` (실전송은 실기기 게이트)
- 의존: 단계 18.

### 21. [NATIVE·게이트] iOS `app/ios/App/App/App.entitlements`
- `aps-environment` `development`→`production`(실배포 직전, 재빌드·재심사, **OTA 불가**). 릴리즈
  scope web-only **오판 금지**(feedback_release_scope_native_plugin_gap). 실기기 검증
  (feedback_device_smoke_auth_bugs).
- verify: device 빌드 실기기 — 권한 허용→토큰 등록(BE 로그)→어드민 답변→실제 푸시 수신→탭 딥링크.
- 의존: 단계 19, 20(+ 사용자 시크릿 제공).

---

## 완료 조건

Phase 1:
- [ ] 단계 1~16 모든 verify 통과 (`poetry run pytest -q`, `pnpm -C app exec tsc --noEmit`,
      `pnpm -C app test`, E2E 시나리오)
- [ ] `docs/decisions.md` 갱신(단계 15)
- [ ] spec → `docs/spec-history/2026-07-22-board-notifications.md` 이동 준비

Phase 2(게이트):
- [ ] 단계 17~20 코드 작성 + verify(no-op 경로)
- [ ] 단계 21 은 사용자 시크릿·iOS production 승격·실기기 검증 후 활성화

## 가정 (Assumptions)

- 알림 insert 는 본 작업(댓글/상태변경) 성공을 우선하는 best-effort(실패해도 본 작업 미롤백).
  트랜잭션 포함 여부는 be-engineer 재량, 단 본 작업 깨짐 금지.
- 딥링크는 `initialOpenPostId` prop 1개 추가로 해결(새 detail fetcher 미생성).
- 벨 unread 는 boolean dot(count 노출 안 함) — 제약 #2.
