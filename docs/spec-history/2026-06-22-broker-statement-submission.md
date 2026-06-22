# Spec: 거래내역서 제보 (broker statement submission)

> 완료: 2026-06-22

## 배경 / 문제

일괄등록(거래내역서 업로드)이 삼성·토스만 지원하고, 새 증권사 파서를 만들려면 실제 거래내역서 샘플이 필요하다. 지원 증권사도 해외(USD) 거래는 파서가 스킵한다. 사용자에게서 거래내역서 샘플을 수집해 (1) 미지원 증권사 파서 추가, (2) 해외 거래 파싱 추가의 재료로 쓰고, 수집 파일은 어드민 게시판(`board_posts`, `board_type='broker_statement'`)에 저장해 어드민이 다운로드·검토한다.

이 작업은 `decisions.md`가 의도적으로 연기했던 두 결정을 연다: ① 앱 유저의 board write 경로(현재 board 전부 `require_admin`), ② 첨부 스토리지(미결정 + Supabase Storage 금지 → Cloudflare R2).

## 목표

- 앱 사용자가 미지원 증권사 거래내역서 / 해외 거래 포함 내역서를 동의 후 업로드하면, R2에 저장되고 어드민 게시판에 `broker_statement` 글로 등록된다.
- 어드민이 게시판 상세에서 첨부 파일을 다운로드할 수 있다.
- 미설정(R2 자격증명 없음) 환경에서는 기능이 dormant(503)이고 기존 동작은 무회귀.

## 설계

### 확정 결정 (사용자 합의)
- 저장 = Cloudflare R2 (S3 호환, presigned PUT 직접 업로드, BE 무연결 SigV4).
- 진입 = dual-entry: ① 일괄등록 wizard 맥락 분기(AccountStep 미지원 계좌 + Preview/Result 해외거래 배너) + ② 설정 독립 "거래내역서 제보"(증권사 free-text).
- PII = 동의 체크박스만(강한 마스킹/redaction 없음).
- `metadata.type`(`unsupported_broker`|`overseas_trade`)로 구분.

### 핵심 보안 불변식 (서버 강제)
1. `board_type='broker_statement'` 서버 하드코딩(body 미수신, 전용 스키마).
2. `storage_key`/`bucket` 서버 생성(`broker_statement/{user_id}/{uuid}.{ext}`), 서버 생성 key로만 presign.
3. `user_id`는 토큰에서, body 무시.
4. content_type/size는 register 시점 재검증.

### 주요 변경 파일
- `api/src/invest_note_api/config.py` — R2 설정(`r2_*`) + `r2_enabled` property
- `api/pyproject.toml` — boto3 추가
- `api/src/invest_note_api/storage/r2.py` (신규) — presign PUT/GET, build_storage_key, 미설정 503
- `api/src/invest_note_api/db_ops/board_repo.py` — `create_attachment`/`get_attachment` + 스팸 count 헬퍼
- `api/src/invest_note_api/schemas/broker_statement.py` (신규) — PresignRequest/SubmitRequest/AttachmentRef
- `api/src/invest_note_api/routers/board.py` (신규) — `/v1/board/broker-statement/presign` + submit (get_current_user)
- `api/src/invest_note_api/main.py` — board.router 등록
- `api/src/invest_note_api/routers/admin_board.py` — 첨부 다운로드 endpoint(require_admin, presigned GET URL JSON)
- `app/src/lib/api-client.ts` — board ROUTES + presign/submit + `uploadToR2`(raw fetch PUT)
- `app/src/components/broker-statement/BrokerStatementPanel.tsx` (신규) — 단일 제보 패널(dual-entry 공유)
- `app/src/components/records/ImportTradesPanel/{brokers.ts,AccountStep.tsx,index.tsx,PreviewStep.tsx,ResultStep.tsx}` — 진입 트리거
- 설정 화면 — 독립 진입점(구현 시 위치 확정)
- `admin/src/lib/api.ts` + `admin/src/app/(dash)/boards/[id]/page.tsx` — 다운로드 버튼
- `docs/decisions.md` — 연기 두 건 여는 기록

## 구현 체크리스트

### Phase 0 — 설계 기록
- [x] `docs/decisions.md` append (R2 첨부 스토리지 + app-side board write only, 트레이드오프)

### Phase 1 — BE walking skeleton (presign → PUT → register)
- [x] 1a `config.py` R2 설정 + `r2_enabled` (dormant 검증)
- [x] 1b `pyproject.toml` boto3 + `poetry lock`
- [x] 1c (신규) `storage/r2.py` presign 헬퍼 + `test_r2_storage.py`(네트워크 無)
- [x] 1d `db_ops/board_repo.py` create_attachment/get_attachment/count
- [x] 1e (신규) `schemas/broker_statement.py` (board_type 필드 없음)
- [x] 1f (신규) `routers/board.py` presign + submit (consent/key-prefix/size/spam 가드) + `test_board_submit.py`
- [x] 1g `main.py` board.router 등록 (/v1/board/* openapi 노출)
- [x] 1h `admin_board.py` 첨부 다운로드 endpoint + `test_admin_board.py` 확장

### Phase 2 — FE 앱
- [x] 2b `api-client.ts` ROUTES.board + presign/submit + uploadToR2(raw fetch)
- [x] 2c (신규) `BrokerStatementPanel.tsx` 단일 제보 패널 + 테스트
- [x] 2a `brokers.ts` free-text 보조 증권사 후보
- [x] 2d AccountStep/index 미지원 계좌 제보 트리거
- [x] 2e PreviewStep/ResultStep 해외거래 제보 트리거
- [x] 2f 설정 독립 진입점

### Phase 3 — Admin FE 다운로드
- [x] `admin/src/lib/api.ts` attachmentDownloadUrl
- [x] `boards/[id]/page.tsx` 다운로드 버튼(window.open)

### Phase 4 — 검증
- [x] BE 전체 `cd api && poetry run pytest -q` green
- [x] 타입 체크: `pnpm -C app exec tsc --noEmit`, `pnpm -C admin exec tsc --noEmit`
- [x] FE 테스트 `pnpm -C app test`
- [x] 수동 presign→PUT→register→admin 다운로드 라운드트립 1회

## 확정한 구현 디테일 (기본값)
- presign = PUT + register 재검증 / admin 다운로드 = presigned GET URL JSON / 스팸 = 10건/시간/user / orphan = R2 lifecycle 7일 / 독립 진입점 = 설정 화면.

## 우려사항 / 리스크
- R2 버킷 CORS 미설정 시 prod PUT 실패(`AllowedOrigins`: capacitor://localhost, https://localhost, http://localhost:3000 / `AllowedMethods`: PUT,OPTIONS / `AllowedHeaders`: content-type). **repo 밖 Ops 필수.**
- presign content_type ≠ PUT Content-Type → 서명 실패. 양쪽 동일 강제.
- Coolify env(SSOT) 주입 필요: `R2_ENDPOINT_URL/R2_BUCKET/R2_ACCESS_KEY_ID/R2_SECRET_ACCESS_KEY`.
