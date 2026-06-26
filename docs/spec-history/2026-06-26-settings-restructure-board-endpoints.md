# 설정 화면 재구성 + 사용자 게시판 엔드포인트 사양서

> 완료: 2026-06-26

> 출처: 승인된 플랜 `~/.claude/plans/parsed-wiggling-brooks.md` (사용자 승인 완료). 본 문서는 그 플랜을 사양서로 정리한 것이며 재설계가 아니다.

## 배경 / 목적

현재 설정 화면(`app/src/app/(app)/settings/page.tsx`)은 4개 섹션(계좌 관리 / 내 정보 / 고객 지원 / 계정)이 단일 `page.tsx`에 **인라인 세로 나열**돼 있다. 항목이 늘수록 스크롤만 길어지고 위계가 무너지며, 게시판(공지/의견/오류신고) 도입을 인라인으로 감당할 수 없다.

토스·카카오뱅크·당근의 표준 패턴인 **"리스트 메뉴(행+chevron) + 슬라이드 패널 진입"** 으로 재구성하고, 사용자용 게시판(공지 읽기 / 의견·오류신고 쓰기)을 신설한다. 게시판 인프라(`board_posts` 테이블, `board_repo`)는 존재하나 앱용 엔드포인트는 거래내역서 제보뿐이라 신규 엔드포인트가 필요하다.

**목표:** 친숙하고 확장 가능한 설정 IA + 앱 내 공지/의견/오류신고 채널.

## 확정 IA

```
[프로필 헤더] 이메일
자산 관리:   계좌 관리              → 패널
소식:        공지사항              → 패널(목록) → 패널(상세)
고객 지원:   의견 보내기            → 작성 패널 (텍스트 전용)
             오류 신고             → 작성 패널 (텍스트 + 스크린샷 첨부)
             거래내역서 제보        → 기존 패널
약관·정책:   서비스 이용약관 / 개인정보 처리방침   → 외부 링크
계정:        로그아웃
             회원 탈퇴             → 작은 텍스트 → 경고 패널(2depth)
[푸터] 투자노트 v{version}
```

## 확정 결정

- 전 항목 **슬라이드 패널 통일**(기존 `FullScreenPanel` compound 재사용).
- 의견 / 오류신고 **각각 별도 메뉴**.
- 회원 탈퇴는 **계정 섹션 하단 작은 텍스트 → 경고 패널 2depth**.
- **오류신고만 스크린샷 첨부 허용**, 의견은 텍스트 전용.
- 오픈소스 라이선스 메뉴 **이번 제외(defer)** — 약관·정책은 이용약관/개인정보 처리방침 2개만.
- 공지 상세 응답은 **화이트리스트 필드만**(id/title/body/created_at/is_pinned/metadata). admin user_id·comments·attachments 미노출.
- board 도메인 wire 포맷은 기존 관례대로 **snake_case raw passthrough**(CamelModel 미사용).

## 전제 (조사로 확정 — 마이그레이션/auth 변경 없음)

- `status` 컬럼은 publish 게이트가 아님(`DEFAULT 'open'`, broker_statement 티켓 상태용). 공지는 `board_type='notice'`만으로 거른다(발행 필터는 phantom).
- `board_repo.list_posts`는 board_type/page/q 지원, `order by created_at desc` 고정(admin 공유). 상단고정 필요 시 `pinned_first: bool=False`(default-off)만 추가해 admin 동작 보존.
- `count_recent_submissions`는 `board_type='broker_statement'` 하드코딩 → `board_type` 파라미터화(default 유지)로 feedback/bug_report 스팸가드 재사용.
- R2 헬퍼(`storage/r2.py`): `build_temp_key`/`promote_key`(temp→정식 prefix)/`generate_put_url`, copy/delete 동기→threadpool. broker_statement 첨부 흐름을 bug_report로 일반화(목적지 prefix 추가).
- `FullScreenPanel`(`app/src/components/base/FullScreenPanel.tsx`)은 compound + `useStaggeredPanel` + 중첩 scroll-lock 카운터 → 공지 목록→상세 2단계 중첩 가능.
- **테이블·repo 이미 존재, 컬럼 추가·마이그레이션·auth 변경 없음.** DB 변경 필요 판단 시 임의 진행 금지·리더 보고.

## 작업 단위 (1요청=1파일, BE→FE 의존 순서)

### Phase A — BE (응답 shape가 FE 타입의 source of truth)

**A1. `api/src/invest_note_api/db_ops/board_repo.py`** — 담당: be-engineer
- `count_recent_submissions(...)`에 `board_type: str = "broker_statement"` 인자 추가(기본값으로 기존 동작 보존).
- (공지 상단고정 필요 시) `list_posts`에 `pinned_first: bool=False` 추가 → `order by is_pinned desc, created_at desc`. 기본 off.
- verify: `cd api && poetry run pytest tests/test_board_submit.py tests/test_admin_board.py -q` green.
- 의존: 없음.

**A2. `api/src/invest_note_api/storage/r2.py`** — 담당: be-engineer
- `promote_key`를 목적지 prefix 인자화(또는 `BUG_REPORT_PREFIX="bug_report"` 추가)해 temp→bug_report 승격 지원. 기존 broker_statement 경로 불변.
- verify: import + A5 테스트.
- 의존: 없음.

**A3. `api/src/invest_note_api/schemas/board.py`** — 담당: be-engineer
- `FeedbackCreate`: `extra="forbid"`, `body: str`, `title: str | None = None`. consent 없음, board_type 없음(서버 하드코딩).
- `BugReportCreate`: `body: str`, `title: str | None = None`, `attachment: AttachmentRef | None = None`(broker_statement의 `AttachmentRef` 재사용/공유). 첨부는 **이미지 MIME 화이트리스트**.
- title NOT NULL → 미전송 시 라우터가 고정 prefix(`[의견]`/`[오류신고]`)로 합성(broker_statement 미러).
- verify: import 성공.
- 의존: A1·A2.

**A4. `api/src/invest_note_api/routers/board.py`** (엔드포인트 추가, `get_current_user` 게이트) — 담당: be-engineer
- `GET /board/notices` — `list_posts(board_type='notice', page, page_size)`. 응답 `{"items": rows, "total": total, "page": page}`.
- `GET /board/notices/{post_id}` — `get_post` 후 **화이트리스트 필드만** 반환(user_id/comments/attachments 제거). `board_type != 'notice'`면 404(우회 조회 차단).
- `POST /board/feedback` (201) — board_type `'feedback'` 하드코딩, user_id 토큰, title 합성, `create_post(metadata={"source":"app"})`. 스팸가드 `count_recent_submissions(..., board_type='feedback')` ≥ `_SPAM_MAX` → 429. 응답 `{"post_id": ...}`.
- `POST /board/bug-report/presign` — 이미지 presign(broker_statement presign 패턴 일반화). temp key 발급.
- `POST /board/bug-report` (201) — board_type `'bug_report'`, 선택적 attachment. attachment 있으면 temp-prefix(`temp/{user_id}/`) 검증(403) + MIME/size 재검증(415/413) + `promote_key`(temp→bug_report, threadpool) + `create_attachment`. 트랜잭션 실패 시 R2 보상 삭제. 스팸가드 `board_type='bug_report'`.
- verify: `cd api && poetry run pytest tests/test_board_submit.py -q` 회귀 없음 + A5.
- 의존: A3.

**A5. `api/tests/test_board.py` (신규)** — 담당: be-engineer
- FakePool/FakeConnection 패턴(`test_board_submit.py` 미러), `get_current_user` override.
- notice 목록(fetchval count → fetch rows), 상세(fetchrow post → fetch comments → fetch attachments, **user_id/comments 미노출 검증**, board_type 불일치 404), feedback POST(201 / board_type 주입 422 / 스팸 429), bug-report POST(첨부 없음 201 / 첨부 있음 promote 경로 / temp-prefix 위반 403).
- verify: `cd api && poetry run pytest tests/test_board.py tests/test_board_submit.py tests/test_admin_board.py -q` 전부 green.
- 의존: A4.

### Phase B — FE 기반 유틸/타입 (서로 독립, B4만 A4 shape 의존)

**B1. `app/src/lib/external-link.ts` (신규)** — 담당: fe-engineer
- `FileStep.tsx:19-26`의 로컬 `openExternal` 공용 승격(native=`@capacitor/browser`, web=`window.open`). `FileStep.tsx`는 import 교체.
- verify: `pnpm -C app exec tsc --noEmit`.
- 의존: 없음.

**B2. `app/src/lib/legal-links.ts` (신규)** — 담당: fe-engineer
- `LEGAL_LINKS = { terms, privacy }`(licenses 제외). `login/page.tsx:162,171` 하드코딩 교체.
- verify: tsc.
- 의존: 없음.

**B3. `app/src/components/settings/SettingsMenuRow.tsx` (신규)** — 담당: fe-engineer
- 행 컴포넌트. props `label`/`onClick`/`variant?: "default"|"external"|"destructive"`/`description?`. 우측 아이콘 lucide `ChevronRightIcon`(default)·`ExternalLinkIcon`(external). 그룹 컨테이너는 기존 `rounded-2xl bg-muted/60 overflow-hidden` 재사용.
- verify: tsc.
- 의존: 없음.

**B4. `app/src/lib/api-client.ts`** — 담당: fe-engineer
- `ROUTES.board` 확장(notices/noticeById/feedback/bugReport/bugReportPresign). 타입(**snake_case 정합**): `NoticeListItem{id,title,created_at,is_pinned}`, `NoticeListResponse{items,total,page}`, `NoticeDetail{id,title,body,created_at,is_pinned,metadata}`(화이트리스트와 1:1), `FeedbackInput{body}`, `BugReportInput{body, attachment?}`. `boardApi`: `listNotices`/`getNotice`/`submitFeedback`/`submitBugReport`(+presign·uploadToR2 재사용).
- verify: tsc.
- 의존: A4(BE shape 확정).

**B5. `app/src/lib/query-keys.ts`** — 담당: fe-engineer
- `notices`, `notice(id)` 키 추가.
- verify: tsc.
- 의존: 없음.

### Phase C — FE 패널 (B 의존)

**C1. `app/src/components/settings/NoticePanel.tsx` (신규)** — 담당: fe-engineer
- `FullScreenPanel` + `useStaggeredPanel`로 목록→상세 2단계 중첩. `useQuery(queryKeys.notices)` / `useQuery(queryKeys.notice(id))`.
- verify: tsc + 수동(목록→상세→뒤로).
- 의존: B4·B5.

**C2. `app/src/components/settings/FeedbackPanel.tsx` (신규)** — 담당: fe-engineer
- textarea + 제출. `useMutation(boardApi.submitFeedback)`, 성공 toast+닫기, 429 안내.
- verify: tsc + 수동.
- 의존: B4·B5.

**C3. `app/src/components/settings/BugReportPanel.tsx` (신규)** — 담당: fe-engineer
- textarea + **스크린샷 첨부(이미지 파일피커, presign→R2 PUT→submit)**. broker_statement 업로드 흐름(`BrokerStatementPanel`) 참조. 첨부 선택.
- verify: tsc + 수동.
- 의존: B4·B5·A4(presign).

**C4. `app/src/components/settings/DeleteAccountSection.tsx` 수정** — 담당: fe-engineer
- `ConfirmDeleteDialog` → 경고 `FullScreenPanel`(2depth). `meApi.deleteAccount` + `signOut` + `queryClient.clear` + `router.replace("/login")` 로직 이전. 진입은 destructive variant `SettingsMenuRow`.
- verify: tsc + 수동(stage에서만 실제 삭제).
- 의존: B3.

### Phase D — 통합 (마지막, 전부 의존)

**D1. `app/src/app/(app)/settings/page.tsx` 재구성** ⚠️ SettingsMenuRow·전 패널·api-client 훅 존재 후 조립(shape drift 위험 지점) — 담당: fe-engineer
- IA 순서대로 섹션 재배치. `<h2 text-[13px]>` 라벨 유지, 푸터 버전(`useAppVersion`) 유지.
- 계좌 관리/공지/의견/오류신고/거래내역서 제보/탈퇴 = 각 `SettingsMenuRow` → 해당 패널. 약관·정책 = `openExternal(LEGAL_LINKS.x)` external row.
- **`UserInfoSection.tsx` 분해**: email → 프로필 헤더, 로그아웃 → 계정 섹션. 패널 open 상태는 각 섹션/page useState 소유(기존 패턴).
- verify: `pnpm -C app exec tsc --noEmit`, `pnpm -C app build`, 디바이스/웹 수동 전 메뉴 플로우.
- 의존: B1~B5, C1~C4.

## Shape drift 체크리스트 (QA 강제)

1. notice 상세 응답(화이트리스트) ↔ FE `NoticeDetail` 키 1:1. comments/attachments/user_id를 FE 타입에 넣지 말 것.
2. board 요청/응답 전부 **snake_case**(`created_at`, `is_pinned`, `post_id`). camel → 422(extra forbid).
3. feedback/bug-report 바디에 **board_type 미포함**(서버 하드코딩, 보내면 422).
4. `count_recent_submissions` 기본값 변경이 broker_statement 스팸 테스트(count→10→429, →9→201) 회귀 없는지 A1 직후 확인.

## Out of scope (백로그)

- 데이터 내보내기 CSV / 알림 설정 / 앱 평가하기 / 수동 업데이트 확인 / 다크모드.
- 의견(feedback) 첨부(텍스트 전용 유지).
- 오픈소스 라이선스 메뉴(licenses.html 발행 후 별도 추가).

## 검증 (end-to-end)

- BE: `cd api && poetry run pytest tests/test_board.py tests/test_board_submit.py tests/test_admin_board.py -q`
- FE: `pnpm -C app exec tsc --noEmit` + `pnpm -C app build`
- 수동: 설정 진입 → 각 메뉴(계좌/공지 목록·상세/의견 제출/오류신고+스크린샷/약관 외부링크/로그아웃/탈퇴 경고 패널) 플로우. 실제 탈퇴·실제 R2 업로드는 stage 환경.

## 완료 조건

- [x] A1~A5, B1~B5, C1~C4, D1 전 단위 verify 통과.
- [x] QA-BE / QA-FE-panels / QA-integration 통과.
- [x] 기술 결정(트레이드오프) 없음 → `docs/decisions.md` 갱신 불필요.
- [x] spec → `docs/spec-history/2026-06-26-settings-restructure-board-endpoints.md` 이동 준비.

## 완료 후 추가 변경 (커밋 7dfec5d 이후 코드리뷰 반영)

- 오류신고 첨부를 **단일 → 다중(최대 5장)** 으로 확장: 썸네일 미리보기, presign→PUT 병렬 업로드, 부분 실패 시 승격분만 보상 삭제, 중복 storage_key 400.
- 코드리뷰 수정: 회원탈퇴 중복 발사 가드(deletingRef), 공지 핀 상단고정(pinned_first), 공지 상세 불필요 쿼리 제거(get_post with_relations), `_check_spam` 공용화, 토스트 억제 수정, 415 문구 HEIC 추가.
- 후속(backlog): 공지사항 페이지네이션.
