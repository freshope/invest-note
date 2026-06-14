# Spec: 분석태그에 사용자 정의 태그 추가

## 배경 / 문제

현재 거래의 **분석태그(reasoning_tags)**는 PostgreSQL ENUM으로 고정된 4종(`TECHNICAL`/`FUNDAMENTAL`/`NEWS`/`FEELING`)뿐이라, 사용자가 자신만의 판단 근거 분류(예: "배당", "테마주", "스윙복기")를 기록할 수 없다. 매수(BUY)에 자유 텍스트 **사용자 정의 태그(custom_tags)**를 추가하고, 매도(SELL)에 자동 상속시켜 분석 탭에서 태그별 승률/손익까지 집계한다.

**사용자 결정 (이번 작업 범위 확정):**
1. **프리셋 4종 유지 + 커스텀 추가** — 기존 reasoning_tags ENUM은 그대로 두고, 별도 `custom_tags text[]` 컬럼을 평행 추가 (비파괴적).
2. **분석 집계 포함** — 커스텀 태그도 분석 탭의 태그별 승률/손익 통계에 반영.

**UX 재설계 (v2 — 영속 레지스트리 + 통합 그리드):**
3. **영속 저장**: 사용자 태그는 1회성이 아니라 **레지스트리 테이블(`custom_tags`)에 저장** → 다음부터 프리셋과 같은 칩 그리드에 노출·선택. (거래에 쓰인 태그를 distinct로 모으는 방식 ❌ → 명시적 레지스트리 ✅)
4. **통합 표시**: 등록/수정 시 **별도 섹션 없이** "분석 태그" 그리드에 프리셋 + 사용자 태그를 함께 표시(둘 다 멀티 선택).
5. **+ 버튼 + 바텀시트**: 분석 태그 칩 마지막에 `+` 버튼 → 클릭 시 바텀시트로 새 태그 입력·저장(+ 기존 태그 삭제) → 저장 직후 **현재 거래에 자동 선택**되고 이후 그리드에 노출.
6. **삭제 지원**: 바텀시트에서 저장된 태그 삭제 가능. 삭제해도 과거 거래의 `custom_tags` 라벨은 유지(분석 안전) — 레지스트리는 선택 카탈로그일 뿐.

## 목표

- 매수 거래 메타 폼/편집에서 자유 텍스트 커스텀 태그를 추가·선택할 수 있다.
- 매도 거래는 매칭된 최신 매수의 커스텀 태그를 자동 상속해 읽기 전용으로 표시한다 (reasoning_tags와 동일).
- 거래 상세에서 커스텀 태그가 표시된다.
- 분석 탭에 "사용자 정의 태그" 섹션이 생겨 태그별 거래 수/승률/손익이 집계된다.
- BE `pytest`, FE `tsc --noEmit` 통과.

## 설계 (v2)

### 데이터 모델

- `trades.custom_tags text[]` (마이그레이션 031) — 거래에 **선택된 사용자 태그 라벨** 저장. SELL 자동 상속(reasoning_tags 미러). **유지.**
- `custom_tags` 레지스트리 테이블 (마이그레이션 032 신규) — 사용자별 **선택 가능한 태그 카탈로그**. `id uuid pk / user_id uuid / label text / created_at`, `unique(user_id, label)`, RLS(본인만 select/insert/delete — trades 정책 미러). 거래 부착 없이도 영속.
- 거래는 라벨(text)을 저장하고 레지스트리는 id+label 을 제공 → 레지스트리 태그 삭제해도 과거 거래 라벨 불변(분석 안전).

### 엔드포인트 (`/trades` 라우터, `/{trade_id}` 보다 먼저 선언)

- `GET /trades/custom-tags` → `{ tags: [{ id, label }] }` (레지스트리, 가나다순)
- `POST /trades/custom-tags` body `{ label }` → `{ id, label }` (trim/1~20자, `on conflict (user_id,label) do nothing` 후 기존 반환 — 멱등)
- `DELETE /trades/custom-tags/{tag_id}` → 204 (레지스트리에서만 제거, 거래 라벨 불변)

### FE 통합 선택기 + 바텀시트

- 기존 별도 `CustomTagEditor` 섹션 **제거**. "분석 태그" 한 그리드에 프리셋 칩(→reasoning_tags) + 레지스트리 커스텀 칩(→custom_tags) + 끝에 `+` 버튼.
- `+` → `Drawer`(바텀시트): 새 태그 입력(저장=POST→invalidate→**자동 선택**) + 기존 커스텀 태그 목록 삭제(=DELETE→invalidate, 폼에서 선택돼 있으면 해제).
- 프리셋/커스텀은 저장 컬럼이 다르므로(enum[] vs text[]) 선택 토글을 각 폼 필드로 라우팅하되 시각적으로 한 그리드.

### 접근 방식: `reasoning_tags`를 그대로 미러링 (저장/집계 파이프라인)

`reasoning_tags`는 BUY 입력 → SELL 자동 산출(pnl_sync) → 분석 집계(by_tag)까지 검증된 파이프라인이 있다. 새 join/집계 로직을 발명하지 않고 **동일 패턴을 평행 복제**하는 것이 최소·최저위험 구현이다. 차이점은 ENUM이 아니라 **자유 텍스트(`text[]`)**라는 점뿐.

- 저장: `trades.custom_tags text[]` (ENUM 아님, 사용자 자유 입력). 신규 컬럼이라 backfill 불필요 (빈 배열로 시작).
- 입력 경로: reasoning_tags와 동일하게 **생성(TradeCreate)이 아닌 PATCH(TradeUpdate/메타)** 로만 설정.
- SELL 자동 산출: 분석이 SELL 기준으로 집계되므로(`aggregate.py`가 `sells` 순회), 커스텀 태그가 SELL에 실려야 한다 → auto-derive 파이프라인 전체 미러링 필수.
- 재사용 지원: 자유 텍스트는 오타로 파편화되어 집계가 노이즈가 되므로, 사용자의 기존 커스텀 태그 distinct 목록을 제공하는 가벼운 read-only 엔드포인트로 재선택을 돕는다. *(분리 가능 — 아래 [재사용] 표기)*

### 검증 규칙 (BE/FE 동일)

- 각 태그 `trim`, 빈 문자열 제거, 중복 제거.
- 태그당 최대 길이 20자(`CUSTOM_TAG_MAX_LEN`), 거래당 최대 10개(`MAX_CUSTOM_TAGS`).

### 주요 변경 파일

**DB**
- `supabase/migrations/031_add_custom_tags_column.sql` (신규) — `alter table trades add column custom_tags text[] not null default '{}';`

**BE — 모델/스키마/저장**
- `api/src/.../domain/trade_types.py` — `Trade.custom_tags: list[str] = []` (L125 인접) + `CUSTOM_TAG_MAX_LEN`/`MAX_CUSTOM_TAGS` 상수.
- `api/src/.../schemas/trade.py` — `TradeUpdate.custom_tags: list[str] | None = None` + 정규화 `field_validator`(trim/dedupe/cap).
- `api/src/.../db_ops/trades_repo.py` — `_TRADE_INSERT_SQL`/params에 `custom_tags` 추가; `TRADE_FIELD_META`에 `"custom_tags": TradeFieldMeta(patchable=True, pnl_affecting=True, sell_auto_derived=True)` 등록. **[재사용]** `list_custom_tags(conn, user_id)` distinct 쿼리.

**BE — SELL 자동 산출 (reasoning_tags 함정 그대로 적용)**
- `api/src/.../domain/realized_pnl.py` — `GroupPnLEntry`(L79)에 `custom_tags: list[str]`; `_meta_from_consumed_latest`(L115)를 3-tuple로 확장하고 호출부(L154 unpack, L156 생성자) 동기 수정.
- `api/src/.../db_ops/pnl_sync.py` — `_is_changed` 비교 튜플(L36)에 `("custom_tags", operator.eq)` 추가(없으면 SELL 갱신 미트리거); UPDATE SQL(L83-84)에 `custom_tags = $N` 추가하고 **`WHERE id` 위치 파라미터 번호 재배치**, `entry.custom_tags` 파라미터 추가(L69 인접).

**BE — 분석 집계/응답**
- `api/src/.../domain/analysis/aggregate.py` — `CustomTagStats` dataclass + `AnalysisSummary.by_custom_tag`; `compute_summary`에서 `sells`를 `custom_tags`로 집계(by_tag 패턴, UNTAGGED 버킷 없음 — 존재하는 태그만; 다중 태그 PnL 중복 합산 주석 동일).
- `api/src/.../schemas/analysis_response.py` — `CustomTagStatsResponse`(CamelModel) + `AnalysisSummaryResponse.by_custom_tag`(L48 인접).
- `api/src/.../routers/analysis.py` — by_custom_tag가 응답에 흐르는지 확인(필드 매핑 방식이면 매핑 추가).
- **[재사용]** `api/src/.../routers/trades.py` — `GET /trades/custom-tags` → `{tags: string[]}`.

**FE — 타입/클라이언트**
- `app/src/types/database.ts` — `Trade.custom_tags: string[]` (L44 인접).
- `app/src/lib/api-client.ts` — `TradeMetaInput.custom_tags?: string[]`. **[재사용]** custom-tags GET 함수.
- `app/src/lib/analysis/aggregate.ts` — `CustomTagStats` 인터페이스 + `AnalysisSummary.byCustomTag` (**타입만**; `computeSummary`는 dead code이므로 로직 미수정).
- **[재사용]** `app/src/lib/query-keys.ts` + `app/src/hooks/useCustomTags.ts` — 기존 커스텀 태그 목록 조회.

**FE — 입력/표시 컴포넌트**
- `app/src/components/records/CustomTagEditor.tsx` (신규, 공유) — 기존 태그 토글 칩 + 자유 텍스트 추가 입력(인라인 생성). MetaForm/EditPanel 중복 방지용.
- `app/src/components/records/TradeMetaBuyForm.tsx` — "사용자 정의 태그" 섹션 추가(zod 스키마 + submit payload에 `custom_tags`).
- `app/src/components/records/TradeEditPanel.tsx` — BUY: CustomTagEditor; SELL: 읽기전용 자동 표시.
- `app/src/components/records/AutoMetaField.tsx` — `AutoCustomTagsField`(읽기전용, `AutoReasoningTagsField` 미러).
- `app/src/components/records/TradeDetail.tsx` — `custom_tags` InfoRow 표시(L142-162 미러).

**FE — 분석 탭**
- `app/src/components/analysis/CustomTagBreakdown.tsx` (신규) — `summary.byCustomTag` 렌더(비어있으면 미표시).
- 분석 페이지(ReasoningBreakdown 상위 조립부) — CustomTagBreakdown 추가.

## 구현 체크리스트 (전부 완료 — BE 638 pytest / FE 187 test / tsc / 양 마이그레이션 실DB 검증)

저장·집계 파이프라인 (v1, reasoning_tags 미러):
- [x] DB 마이그레이션 031 — `trades.custom_tags text[]`
- [x] BE Trade 모델 + 상수 / TradeUpdate validator
- [x] BE trades_repo INSERT + TRADE_FIELD_META(sell_auto_derived)
- [x] BE realized_pnl(GroupPnLEntry·3-tuple) + trade_walker(FifoLot) + pnl_sync(UPDATE $9·_is_changed)
- [x] BE aggregate by_custom_tag + analysis_response + 라우터 연결
- [x] FE database.ts / aggregate.ts 타입 / CustomTagBreakdown + 분석 페이지

영속 레지스트리 + 통합 UX (v2):
- [x] DB 마이그레이션 032 — `custom_tags` 레지스트리 테이블(RLS)
- [x] BE custom_tags_repo(list/create/delete) + 스키마 CustomTagCreate
- [x] BE 라우터 GET/POST/DELETE `/trades/custom-tags`
- [x] FE api-client(CustomTag·create·delete) + useCustomTags/useCreate/useDelete
- [x] FE AnalysisTagsField(통합 그리드 + `+` 버튼 + 바텀시트), CustomTagEditor 제거
- [x] FE TradeMetaBuyForm / TradeEditPanel 통합 / AutoCustomTagsField / TradeDetail

검증:
- [x] BE pytest 638 통과(SELL ignore / BUY recalc / by_custom_tag / validator / 레지스트리 CRUD)
- [x] FE tsc + 187 test 통과
- [x] 마이그레이션 031·032 + 쿼리 로컬 DB tx/rollback 검증

## 우려사항 / 리스크

- **레지스트리 삭제 ≠ 거래 라벨 삭제** — 의도된 동작. 거래는 라벨(text)을 저장, 레지스트리는 카탈로그. 삭제 시 그리드에서만 사라지고 과거 거래·분석은 라벨 유지(분석 안전).
- **pnl_sync UPDATE 위치 파라미터 재배치** — `custom_tags=$6` 추가로 `WHERE id=$9` 밀림. 회귀 테스트로 가드.
- **다중 태그 PnL 중복 합산** — 한 SELL이 여러 커스텀 태그를 가지면 각 버킷에 손익 중복 합산(by_tag와 동일). FE 안내 문구 노출.
- **수동 앱 E2E 미실행** — Capacitor 앱 실기기 플로우(매수→`+`로 태그 생성→자동선택→매도 자동상속→분석탭)는 미실행. 자동 테스트로 대체.
