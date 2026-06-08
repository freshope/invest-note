> 완료: 2026-05-18

# Spec: 파일 업로드 일괄 등록 고도화

## 배경 / 문제

거래 일괄 등록 기능은 2026-04 시점에 풀스택으로 구현되었으나(`docs/issue-history/2026-04-28-trade-statement-import.md` 외 2개 후속 spec), 2026-05-06 커밋 `77abcec` 에서 "스토어 등록 전까지" 라는 메모와 함께 프론트 버튼 핸들러가 toast 안내로 임시 차단됨(`fe/src/components/records/TradeList.tsx:39-42`). 백엔드 라우터·파서·테스트, 프론트 4단계 패널은 모두 살아 있는 상태.

이번 작업은 차단 해제와 동시에 사용자가 명시한 7단계 시나리오에 맞춰 미흡한 두 지점을 보강한다.

1. **머지 로직 (시나리오 5)** — 현재는 같은 시그니처 거래를 단순 skip 함. 사용자 요구는 "신규는 INSERT, 기존 거래가 있으면 거래내역서 필드(`commission`, `tax`, `traded_at` 시각)를 갱신 + 사용자 메타(`strategy_type`/`reasoning_tags`/`emotion`/`buy_reason`/`sell_reason`)는 보존". SELL 자동 산출 필드는 머지 후 `recalc_group_pnl()` 이 자동 재계산. 머지 키에 `trade_type` 포함(BUY/SELL 분리).
2. **다운로드 가이드 (시나리오 3)** — 현재 `FileStep` 은 드래그앤드롭만 있어 사용자가 "어디서 어떻게 거래내역서를 받는지" 모름. 증권사별 단계 안내 + 도움말 외부 링크 추가.
3. **버튼 차단 해제 (시나리오 1)** — `openImport` 핸들러를 `setImportOpen(true)` 로 원복.

나머지 시나리오 2/4/6/7 은 이미 구현됨(`AccountStep`, `BrokerStatementParser` ABC 정규형, 동기 commit 트랜잭션, `ResultStep`).

## 목표

- 거래 → "기록" 화면 우측 상단 "파일 업로드" 버튼 클릭 시 `ImportTradesPanel` 이 다시 열린다.
- 파일 업로드 단계에서 선택한 증권사의 거래내역서 다운로드 절차(단계 텍스트 + 도움말 링크)가 노출된다.
- preview 단계에서 신규/머지/오류/USD skip 4개 카운트가 표시되고, "머지" 카운트는 "기존 거래 갱신 + 메모 보존" 임이 안내된다.
- commit 단계에서 시그니처가 일치하는 기존 거래는 `commission`, `tax`, `traded_at`(시각 정보 있을 때) 가 갱신되고, 사용자 메타는 보존되며, 영향받는 SELL 거래의 `profit_loss`/`avg_buy_price`/`holding_days` 가 자동 재계산된다.
- 결과 화면에서 `inserted_count` / `merged_count` / `skipped_count` / `error_count` 가 분리되어 표시된다.
- 단위 테스트: 머지 시 사용자 메타 보존, `commission`/`tax`/`traded_at` 갱신, SELL PnL 재계산, BUY/SELL 시그니처 분리 케이스 검증.

## 설계

### 접근 방식

#### A. 백엔드 머지 로직

**시그니처 키 (변경 없음)**: `TradeSignature(account_id, trade_date, identifier, trade_type, quantity, price)`. price 소수점 2자리 정규화, trade_type 포함(`be/src/invest_note_api/domain/trade_import.py:14-23`).

**머지 대상 필드**: `commission`, `tax`, `traded_at`(시각). `market_type`/`country_code`/`exchange` 는 사용자 수동 분류 보존(백로그).

**traded_at 시각 갱신**:
- 현재 commit 흐름은 staging row 에 날짜만 보관(`be/src/invest_note_api/routers/trades.py:397, 422`). 시각 정보 보관 추가 필요.
- `ParsedTrade.traded_at_kst` 가 "YYYY-MM-DD HH:MM:SS" 형식인 경우만 머지 시 `traded_at` UPDATE. 날짜만 있는 경우 기존 시각 보존.
- 기존 `patch_trade()` 는 `traded_at` 미허용(사용자 PATCH 보안 모델 유지). 머지 전용 신규 함수 `update_trade_from_import()` 추가 — 허용 필드 = `{commission, tax, traded_at}`.

**`import_commit` 머지 분기 의사코드**:
```
FOR EACH GROUP:
  group_existing = list_trades_in_group(...)
  existing_by_sig = {trade_to_signature(t, account_id): t for t in group_existing}

  to_insert = []
  to_merge = []  # (existing_trade, patch)
  FOR row in group_rows:
    sig = make_signature(...)
    IF sig in existing_by_sig:
      patch = build_merge_patch(existing_by_sig[sig], row)
      IF patch: to_merge.append(...)
      ELSE: skipped_count += 1  # 완전 동일 noop
    ELSE:
      to_insert.append(row)

  async with conn.transaction():
    acquire_trade_group_lock(...)
    inserted = insert_trades_bulk(...)
    merged = []
    FOR (existing, patch) in to_merge:
      await update_trade_from_import(conn, user_id, existing.id, patch)
      merged.append(existing.model_copy(update=patch))
    fresh = merged + [t for t in group_existing if t.id not in {m.id for m in merged}] + inserted
    recalc_group_pnl(conn, fresh, key)
```

**재사용**: `recalc_group_pnl()`, `acquire_trade_group_lock()`, `insert_trades_bulk()`.

#### B. 프론트 다운로드 가이드

`brokers.ts` 에 `downloadGuide: { description, steps[], helpUrl? }` 추가. AI 1차 초안 + TODO 주석으로 사용자 검수 표시.

`FileStep` 에 토글 섹션 추가 — `PreviewStep.tsx:91-112` 패턴 재사용, `ChevronDown/Up`. helpUrl 클릭 시 `isNativePlatform()` 분기로 Capacitor `Browser` / `window.open` (`fe/src/app/login/page.tsx:48-76`).

#### C. UI 결과 표시

- `PreviewStep`: "중복(근사)" → "기존 거래에 머지(근사)" + 정책 한 줄 안내.
- `ResultStep`: 4분할 (신규/머지/skip/오류).
- `index.tsx`: 토스트에 머지 건수 반영.

#### D. 차단 해제

마지막 단계에서 `TradeList.tsx:39-42` `openImport` 핸들러 원복 + 주석 제거.

### 주요 변경 파일

**백엔드**
- `be/src/invest_note_api/routers/trades.py` — `import_preview` (staging 에 시각 보관), `import_commit` (머지 분기)
- `be/src/invest_note_api/db_ops/trades_repo.py` — `update_trade_from_import()` 신규
- `be/src/invest_note_api/domain/trade_import.py` — `build_merge_patch()` 순수 함수
- `be/src/invest_note_api/schemas/trade_import.py` — `ImportCommitResponse.merged_count` 필드
- `be/tests/test_trades.py` — 머지 케이스 5건
- `be/tests/test_trade_import_domain.py` — `build_merge_patch` 단위 테스트

**프론트엔드**
- `fe/src/components/records/TradeList.tsx` — `openImport` 원복
- `fe/src/components/records/ImportTradesPanel/brokers.ts` — `downloadGuide`
- `fe/src/components/records/ImportTradesPanel/FileStep.tsx` — 가이드 토글 섹션
- `fe/src/components/records/ImportTradesPanel/PreviewStep.tsx` — 라벨/안내
- `fe/src/components/records/ImportTradesPanel/ResultStep.tsx` — `merged_count` 분리
- `fe/src/components/records/ImportTradesPanel/index.tsx` — 토스트 머지 반영
- `fe/src/lib/api-client.ts` — `ImportCommitResponse.merged_count` 타입

## 구현 체크리스트

### 백엔드
- [x] `domain/trade_import.py` — `build_merge_patch(existing, row) -> dict` 순수 함수
- [x] `db_ops/trades_repo.py` — `update_trade_from_import()` 신규 (commission/tax/traded_at 화이트리스트)
- [x] `schemas/trade_import.py` — `ImportCommitResponse.merged_count` 필드 추가
- [x] `routers/trades.py` `import_preview` — staging row 에 traded_at 시각 정보 보관
- [x] `routers/trades.py` `import_commit` — 머지 분기 구현
- [x] `tests/test_trade_import_domain.py` — `build_merge_patch` 단위 테스트
- [x] `tests/test_trades.py` — 머지 케이스 5건:
  - 사용자 메타 보존
  - commission/tax 갱신
  - traded_at 시각 갱신
  - SELL PnL 재계산
  - BUY/SELL 시그니처 분리
- [x] `cd be && poetry run pytest -q` 전체 통과

### 프론트엔드
- [x] `api-client.ts` — `ImportCommitResponse.merged_count` 타입 추가
- [x] `brokers.ts` — `downloadGuide` 필드 정의 + 초안
- [x] `FileStep.tsx` — 가이드 토글 섹션
- [x] `PreviewStep.tsx` — 라벨 + 정책 안내
- [x] `ResultStep.tsx` — `merged_count` 분리 표시
- [x] `index.tsx` — 결과 토스트 머지 반영
- [x] `TradeList.tsx` — `openImport` 원복
- [x] `pnpm -C fe exec tsc --noEmit` 통과
- [x] `pnpm -C fe test` 통과

### 검증
- [x] 로컬 supabase + 샘플 파일 dogfood: 같은 파일 재import → 신규 0, 머지 0~N, skip N
- [x] commission/tax 만 다른 파일 재import → 머지로 잡히고 기존 메모 보존
- [x] BUY 머지 후 매칭 SELL 의 profit_loss 재계산되어 분석 탭 합계 일치

## 우려사항 / 리스크

- **SELL 자동 산출 변경**: 머지로 BUY 가 바뀌면 SELL 의 `emotion`/`reasoning_tags`/`strategy_type` 이 자동 재계산되어 변할 수 있음. 의도된 동작(기존 PATCH 흐름과 동일).
- **preview vs commit 카운트 차이**: preview 의 `duplicate_count` 는 commit 후 `merged_count + skipped_count` 로 분해. "근사값" 주석 보강.
- **`market_type`/`country_code`/`exchange` 보존**: 거래내역서 vs 사용자 분류 충돌 시 사용자 우선. 백로그.
- **다운로드 가이드 정확성**: 증권사 UI 변경 시 단계 깨짐. AI 1차 초안 후 사용자 검수.
- **차단 해제 vs 스토어 일정**: 차단 사유가 "스토어 등록 전까지" 였음. 작업 완료 후 머지 시점에 사용자와 일정 확인.
