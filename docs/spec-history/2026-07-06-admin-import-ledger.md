# 현재 작업 사양 — 어드민 거래내역서 원장(import ledger) 조회

> 완료: 2026-07-06 (BE test_admin_crud 33 passed·admin tsc/eslint 클린·실 로컬 DB 롤백 트랜잭션으로 조인·카운트·raw 디코드 검증)

## 목표

어드민 패널에서 거래내역서 원장(import_batches / import_ledger_entries)을 확인한다.
원장은 2026-07-02 도입된 불변 캡처 레이어(파일 1건=배치 1행, 행 append-only + raw 원문).
운영자가 "누가 어떤 파일을 업로드/등록했는지"와 "파싱 원본(raw)"까지 감사할 수 있게 한다.

**스코프:** 배치 목록 + 행 드릴다운(권장안 채택). 읽기 전용. admin/ 패널 + BE(require_admin).
쓰기/삭제/다운로드는 이번 스코프 밖(원장은 append-only, 파일 삭제는 R2 lifecycle 소유).

## BE (api)

- **B1. `admin_repo.py`** — `_LIST_TABLES` 에 `import_batches` 추가(제네릭 목록 재사용).
  - `from`: user_profiles(email)·accounts(account_name) LEFT JOIN.
  - `select`: 배치 메타 + `entry_count`(전체 행)·`trade_row_count`(trade_type IS NOT NULL 서브쿼리).
  - `search`: filename·broker_key·email. `order`: created_at desc.
  - 신규 함수 2개: `get_import_batch(conn, batch_id)`(상세 메타, 없으면 None) +
    `list_ledger_entries(conn, batch_id)`(행 전량, **raw jsonb str→dict json.loads**, source_row_no 순).
  - 검증: `poetry run pytest tests/test_admin_crud.py -q`.
- **B2. `schemas/admin.py`** — `ImportBatchDetail(BaseModel)` = `batch: dict` + `entries: list[dict]`.
- **B3. `routers/admin.py`** — `_TABLE_PATH["import-batches"]="import_batches"` +
  `GET /admin/import-batches/{batch_id}` 상세 엔드포인트(`/{table}` 앞 등록, 404 시 ERR_NOT_FOUND).
  - 검증: 신규 테스트(목록 shape·상세 shape·404) FakePool 로 추가.

## FE (admin)

- **F1. `lib/api.ts`** — `ImportBatchRow`·`ImportLedgerEntry`·`ImportBatchDetail` 타입 +
  `adminApi.importBatches = { list, get }`. snake_case passthrough 유지.
- **F2. `lib/nav.ts`** — NAV_ITEMS 에 `{ href:"/import-ledger", label:"일괄등록 원장", icon: ScrollText }`.
- **F3. `app/(dash)/import-ledger/page.tsx`** — `DataTablePage` 목록(증권사·파일명·사용자·업로드·
  등록여부·행수) + rowActions Link → 상세. searchPlaceholder="파일명·증권사·이메일".
- **F4. `app/(dash)/import-ledger/[id]/page.tsx`** — useQuery 상세: 배치 메타 카드 + 원장 행 테이블
  (source_row_no·유형·종목·수량·단가·country + raw 펼침 `<details>`). 미등록 배치는 "미리보기" 표기.
  - 검증: `pnpm -C admin exec tsc --noEmit`.

## 하위 호환 / 배포 주의

- 원장 테이블(0014/0015)은 **운영 미적용** — 이 어드민 기능은 마이그레이션 적용 후에만 실동작.
  로컬은 적용됨(검증 가능). 배포는 기존 원장 배포 절차(마이그레이션 선적용)에 편승.
- 순수 조회 추가라 app/모바일·기존 어드민 계약에 영향 없음.
