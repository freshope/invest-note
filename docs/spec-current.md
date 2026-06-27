# 일괄등록 거래 출처 배지 + 금액 수정 잠금 사양서

> 승인된 계획: `~/.claude/plans/federated-spinning-unicorn.md` 를 작업 단위로 분해. 새 설계 없음.

## 배경 / 목적

PostHog 분석상 거래 등록은 개별등록이 압도적(2주 사용자 76명/1,484건)이고 일괄등록(거래내역서 가져오기)은 4명/57건으로 소수지만, **두 경로의 거래가 데이터·UI상 전혀 구분되지 않는다**. `trades` 테이블에 출처 컬럼이 없어 증권사 내역서에서 자동 등록된 "사실에 가까운" 거래와 손입력 거래가 똑같이 보이고 똑같이 수정된다.

목표:
1. 일괄등록 거래를 거래 카드·상세에서 **인증/도장 배지**로 구분 표시.
2. 일괄등록 거래의 **금액 5필드(가격/수량/환율/수수료/세금)는 수정 불가**로 잠금. 분석 메타(전략/감정/태그/메모)는 계속 수정 가능.

## 범위 (Scope)

- 포함:
  - BE: `trades.origin` 컬럼(text, NOT NULL, default `'MANUAL'`) 추가 — 마이그레이션 + baseline DDL + 도메인 모델 + INSERT 경로 분기 + PATCH 가드.
  - FE: `Trade` 타입 `origin` 추가 + 출처 배지 컴포넌트(카드/상세) + TradeEditPanel 금액 5필드 read-only + 안내문 + onSubmit 잠금필드 omit.
- 제외 (수용 사항, 만들지 않음):
  - 운영 기존 일괄등록 57건 backfill 불가 → 전부 `MANUAL`로 남고 배지 없음. **전방향만 적용**.
  - 재import 머지가 MANUAL 거래 commission/tax 갱신해도 `origin`은 INSERT 시에만 설정되어 불변. 수용.
  - 증권사명(broker) 미표시 — 배지는 일반 표시만, 출처 식별 컬럼 1개로 충분.

## 핵심 불변식 (각 작업 단위에서 반드시 지킬 것)

- **컬럼명은 `origin`** (`source` 아님). 코드 전반의 `source`는 전부 analytics용 → 혼동 방지.
- 값: `'MANUAL'`(개별등록·기본) / `'IMPORT'`(일괄등록).
- **잠금 필드 집합 = 정확히 `{price, quantity, exchange_rate, commission, tax}` 5개.** `market_type`/`trade_type`은 **절대 포함 금지** — FE가 항상 변경 없이 전송하므로 거부 집합에 끼면 메타 수정까지 false-reject 된다.
- **`origin`은 불변** — PATCH 화이트리스트 `TRADE_FIELD_META`에 추가하지 않는다.
- BE 서버단에서도 잠금 강제(가드). FE만 막으면 불변식이 아니다.
- **의존**: BE `origin` 컬럼·응답 노출이 FE 배지·잠금의 선행 의존 → BE 먼저.

## 작업 단위

### 1. [BE] origin 컬럼 — 마이그레이션 + baseline DDL + 도메인 모델 + INSERT 경로
- 마이그레이션: 신규 리비전 `api/alembic/versions/0007_trade_origin.py`, `down_revision = "0006_auth_token_store"`.
  `op.add_column("trades", sa.Column("origin", sa.Text(), nullable=False, server_default="MANUAL"))`.
- baseline: `api/alembic/baseline_schema.sql:354-386` trades DDL에도 동일 컬럼 추가(신규 DB 부트스트랩 일관성).
- 도메인 모델: `api/src/invest_note_api/domain/trade_types.py:114` `Trade`에 `origin: str = "MANUAL"` 추가 → dict 직렬화 경로라 응답 자동 노출.
- INSERT 경로(공용 SQL, 값만 분기): `api/src/invest_note_api/db_ops/trades_repo.py:204-246` — `_TRADE_INSERT_SQL` 컬럼/플레이스홀더에 `origin` 추가, `_trade_insert_params`에 origin 추가, `_TRADE_INSERT_PARAM_COUNT` 21→22. 헬퍼에 `origin: str = "MANUAL"` 파라미터 추가.
  - 개별등록: `create_trade`(`routers/trades.py:330`) → 기본값 `MANUAL`.
  - 일괄등록: `insert_row`/`insert_trades_bulk`(`routers/trades.py:912`, `trades_repo.py:368`) → `IMPORT` 전달.
- **함정/주의**: 마이그레이션은 사용자 confirm 필요한 변경. 파일은 작성하되 **운영 DB 직접 적용 금지** — 로컬 적용·검증만(`alembic upgrade head` 로컬). `_TRADE_INSERT_PARAM_COUNT` 갱신 누락 시 placeholder mismatch.
- verify: `cd api && poetry run pytest tests/ -q` (해당 trades 테스트) + 로컬 `alembic upgrade head` 로 컬럼 추가 확인.
- 의존: 없음.
- 산출물 로그: `_workspace/02_be_changes.md`

### 2. [BE] PATCH 가드 — IMPORT 거래 잠금 5필드 patch 시 422
- `update_trade`(`routers/trades.py:452`) 또는 `trades_repo.py` update 경로: 대상 거래 `origin == "IMPORT"` 이고 patch body에 `{price, quantity, exchange_rate, commission, tax}` 중 하나라도 있으면 **HTTP 422**.
- `market_type`/`trade_type`은 검사 대상 아님. 메타 필드 patch는 그대로 허용 → 기존 BUY→SELL 캐스케이드(`db_ops/pnl_sync.py:recalc_group_pnl`)는 잠금 5필드를 안 건드리므로 충돌 없음.
- **함정**: 잠금 집합에 `market_type`/`trade_type`을 절대 넣지 말 것(메타 수정 false-reject). `origin`은 불변 — 화이트리스트 추가 금지.
- verify: `cd api && poetry run pytest tests/ -q`
- 의존: 단계 1.
- 산출물 로그: `_workspace/02_be_changes.md`

### 3. [QA-BE] BE pytest 정합성 검증
- import commit → 해당 trades `origin == "IMPORT"`, 개별 create → `MANUAL`.
- imported 거래에 `{price|quantity|exchange_rate|commission|tax}` PATCH → 422 거부.
- imported 거래에 메타(`reasoning_tags`/`emotion`/`buy_reason`) PATCH → 허용 + BUY 메타 변경 시 매칭 SELL 캐스케이드 정상.
- MANUAL 거래 금액 PATCH는 기존대로 허용(회귀 없음).
- verify: `cd api && poetry run pytest -q` (전체 그린)
- 의존: 단계 1, 2.

### 4. [FE] Trade 타입 origin + 출처 배지 컴포넌트 + 카드/상세 삽입
- 타입: `app/src/types/database.ts:27-76` `Trade`에 `origin?: "MANUAL" | "IMPORT"` 추가 (**optional**). 근거: 다수 테스트 `makeTrade` 팩토리(`period.test.ts:7`, `analysis.test.ts:10`, `TradeEditPanel.test.tsx:35`)가 full `Trade` 리터럴을 만들어 required면 tsc 깨짐 → `exchange_rate?:` fixture 호환 컨벤션 동일 적용. `undefined !== "IMPORT"` 라 배지 미노출·미잠금(MANUAL 보수 경로)으로 자동 안전, 런타임은 BE NOT NULL default라 프로덕션 응답에 항상 존재.
- 배지(신규): `app/src/components/shared/ImportSourceBadge.tsx` — `TradeTypeBadge.tsx` 패턴 차용. lucide 인증/도장 아이콘(`BadgeCheckIcon`/`StampIcon`/`FileCheckIcon`) + 라벨 "거래내역서". **중립색**(`bg-background border text-muted-foreground`, `StockMetaBadges` 표준 — 손익 빨강/파랑 금지). `origin === "IMPORT"` 일 때만 렌더.
- 삽입: `app/src/components/records/TradeCard.tsx:220-235`(종목명/메타 배지 줄), `app/src/components/records/TradeHeaderCard.tsx:82-94`(상세 헤더 배지 행).
- **함정**: BE 응답 shape(`origin` 노출) 확정 후 진행 — 단계 1 blockedBy. shadcn 신규 컴포넌트 아님(공유 컴포넌트 패턴 차용)이므로 base 래퍼 불필요, 단 내부에서 Badge 등 shadcn을 쓰면 `components/base/` 래퍼 경유.
- verify: `pnpm -C app exec tsc --noEmit` + 동작(imported 거래 카드/상세 배지 노출, MANUAL 미노출).
- 의존: 단계 1.
- 산출물 로그: `_workspace/03_fe_changes.md`

### 5. [FE] TradeEditPanel 금액 5필드 read-only + 안내문 + onSubmit omit
- `app/src/components/records/TradeEditPanel.tsx`: `const isImported = trade.origin === "IMPORT";`
- 금액 입력 5개 `NumericInput` imported면 읽기전용: 가격(:257), 수량(:274), 체결 원화/환율(:292), 수수료(:313), 제세금(:331). `NumericInput`(`app/src/components/records/NumericInput.tsx`)이 `disabled`/`readOnly` 지원 여부 먼저 확인, 미지원이면 prop 추가(surgical).
- `onSubmit`(:167-199): imported면 patch payload에서 `price, quantity, exchange_rate, commission, tax` **omit**(BE 가드와 정합). 현재 price/quantity/commission/tax를 항상 전송 → 분기 필수. 메타(strategy/emotion/tags/result/reason)는 그대로 전송.
- 패널 상단 안내 한 줄: "거래내역서에서 가져온 거래는 금액 정보를 수정할 수 없어요."
- **함정**: `market_type`/`trade_type`은 잠그지 말 것(메타 수정 경로). omit 집합 = BE 잠금 5필드와 정확히 일치.
- verify: `pnpm -C app exec tsc --noEmit` + 동작(5필드 read-only·메타 편집 가능·저장 시 잠금필드 미전송).
- 의존: 단계 4.
- 산출물 로그: `_workspace/03_fe_changes.md`

### 6. [QA-FE] FE 정합성 검증
- `pnpm -C app exec tsc --noEmit` 그린.
- imported 거래 카드/상세 배지 노출, 편집 패널 금액 5필드 read-only·메타 편집 가능, 저장 시 잠금 필드 미전송(payload omit) 확인.
- BE 잠금 5필드 ↔ FE omit 5필드 정확 일치 검증.
- (`pnpm -C app test` 해당 컴포넌트 테스트 추가 시 그린.)
- verify: `pnpm -C app exec tsc --noEmit` + 동작 시나리오
- 의존: 단계 4, 5.

## 완료 조건

- [ ] 모든 단위 verify 통과 (BE pytest 그린 / FE tsc 그린 / 동작 시나리오)
- [ ] 마이그레이션 로컬 적용·검증 (운영 DB 미적용 — confirm 대기)
- [ ] BE 잠금 5필드 ↔ FE omit 5필드 정확 일치 (QA 교차 확인)
- [ ] `docs/decisions.md` 갱신 — 불필요(계획에 트레이드오프 결정 이미 명시, 신규 기술선택 없음). 필요 시 origin vs source 네이밍 결정 1줄 추가 검토.
- [ ] spec → `docs/spec-history/2026-06-27-trade-origin-badge-lock.md` 이동 준비
