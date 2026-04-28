> 완료: 2026-04-28

# Spec: SELL 거래 근거태그·감정 자동 산출 (이슈 A+D)

## 배경 / 문제

분석 탭 지표 정합성 조사에서 두 가지 이슈 발견 (이슈 A+D 통합 처리):
- byTag 분석이 SELL 시점에 직전 BUY를 매번 FIFO 매칭. frontend 키는 `account_id` 누락으로 다계좌 사용자에게 잘못된 태그 귀속 가능.
- `EmotionStats`의 `count`(BUY+SELL 빈도)와 `sellCount`(승률 분모) 의미 차이가 UI 표기 혼동 유발.

해결: `strategy_type`이 이미 따르는 패턴과 동일하게 `reasoning_tags`/`emotion`도 SELL 거래 mutation 시점에 직전 BUY로부터 자동 산출하여 SELL row에 저장. 분석은 SELL 저장값만 사용.

## 목표

- SELL 거래 INSERT/UPDATE/DELETE 시 그룹 재계산이 SELL의 `reasoning_tags`/`emotion`도 함께 갱신한다.
- BUY 거래의 `reasoning_tags`/`emotion` 변경 시 같은 그룹 SELL들이 자동 재계산된다.
- 분석 탭 byTag/byEmotion이 SELL의 저장값만 사용한다 (FIFO 매칭 불필요).
- SELL 작성/수정 폼에서 emotion·reasoning_tags 입력이 read-only가 된다.
- 기존 SELL 거래의 두 필드가 일괄 백필되어 직전 BUY와 일치한다.

## 설계

### 통합 정책

`reasoning_tags`/`emotion` 모두: FIFO 소비된 BUY lot 중 **가장 최근(`traded_at` 최대, 동률 시 BUY order 최대) lot의 값**을 그대로 복사. 소비 BUY 없으면 `[]`/`NULL`.

`strategy_type`은 기존 정책(수량 가중 최다) 유지 — 두 정책 공존.

### 주요 변경 파일

**백엔드**
- `api/src/invest_note_api/domain/realized_pnl.py` — `GroupPnLEntry`/`compute_group_pnl` 확장, 신규 헬퍼
- `api/src/invest_note_api/db_ops/pnl_sync.py` — UPDATE 쿼리에 두 컬럼 추가
- `api/src/invest_note_api/db_ops/trades_repo.py` — `PNL_AFFECTING_FIELDS`에 두 필드 추가, `SELL_AUTO_DERIVED_FIELDS` + `strip_sell_auto_derived` 헬퍼 추가
- `api/src/invest_note_api/routers/trades.py` — SELL patch에서 자동 산출 필드 제거
- `api/src/invest_note_api/domain/analysis/aggregate.py` — byTag/byEmotion 단순화, `EmotionStats.sell_count` 제거, 미사용 `all_trades` 파라미터 제거
- `api/src/invest_note_api/domain/analysis/rules.py` — `sell_count` → `count`
- `api/src/invest_note_api/routers/analysis.py` — 응답 직렬화 갱신
- `supabase/migrations/013_backfill_sell_meta_from_buy.sql` — 백필 마이그레이션 (PL/SQL FIFO)

**프론트엔드**
- `app/src/lib/analysis/realized-pnl.ts` — `GroupPnLEntry`/`computeGroupPnL` 동기화
- `app/src/lib/analysis/aggregate.ts` — byTag/byEmotion 단순화, `EmotionStats.sellCount` 제거
- `app/src/lib/analysis/rules.ts` — `sellCount` → `count`
- `app/src/lib/analysis/__tests__/analysis.test.ts` — 다계좌/다 BUY 케이스 추가
- `app/src/components/records/AutoMetaField.tsx` (신규) — read-only chip 공용 컴포넌트
- `app/src/components/records/TradeMetaSellForm.tsx` — emotion read-only
- `app/src/components/records/TradeEditPanel.tsx` — SELL일 때 emotion/reasoning_tags 비활성화 + patch payload에서 제외
- `app/src/components/records/TradeDetail.tsx` — SELL 라벨에 "(자동)"
- `app/src/components/analysis/EmotionBreakdown.tsx` — `sellCount` → `resultCount` 기반 hasData

## 구현 체크리스트

- [x] `realized_pnl.py` — `GroupPnLEntry`에 `reasoning_tags`/`emotion` 추가, FIFO lot 확장, `_meta_from_consumed_latest()` 헬퍼 추가
- [x] `pnl_sync.py` — UPDATE 쿼리에 두 컬럼 추가
- [x] `trades_repo.py` — `PNL_AFFECTING_FIELDS` 확장 + `SELL_AUTO_DERIVED_FIELDS`/`strip_sell_auto_derived` 헬퍼
- [x] `routers/trades.py` — `update_trade`에서 SELL patch 자동 산출 필드 제거
- [x] `aggregate.py` — byTag/byEmotion 단순화, `EmotionStats.sell_count` 제거, 미사용 `all_trades` 정리
- [x] `routers/analysis.py` — 응답 직렬화에서 `sellCount` 제거 + `compute_summary` 호출 시그니처 업데이트
- [x] `supabase/migrations/013_backfill_sell_meta_from_buy.sql` — 신규 마이그레이션 작성
- [x] 백엔드 테스트 갱신·추가 (`test_realized_pnl`, `test_analysis_logic`, `test_trades` PATCH 무시 검증 3건), `poetry run pytest -q` 통과 (사전 실패 2건은 본 spec 무관)
- [x] `realized-pnl.ts` — 백엔드와 동일 패턴으로 동기화
- [x] `aggregate.ts` — byTag/byEmotion 단순화, `EmotionStats.sellCount` 제거, 미사용 `allTrades` 파라미터 제거
- [x] `__tests__/analysis.test.ts` — 갱신, 다계좌·다 BUY 케이스 추가
- [x] `AutoMetaField.tsx` 신규 + 사용처 적용
- [x] `TradeMetaSellForm.tsx` — emotion read-only
- [x] `TradeEditPanel.tsx` — SELL일 때 emotion/reasoning_tags 비활성화 + patch payload에서 제외
- [x] `TradeDetail.tsx` — SELL 라벨에 "(자동)"
- [x] `EmotionBreakdown.tsx` — `resultCount > 0` 기준 hasData
- [x] `pnpm -C app exec tsc --noEmit` 통과
- [x] `pnpm -C app test` 통과 (127 passed)
- [ ] 로컬 `supabase db reset` 후 마이그레이션 적용 검증 — 사용자 환경에서 별도 실행

## 우려사항 / 리스크

- API 응답 breaking change: `EmotionStats.sellCount` 제거. frontend·backend 단일 PR로 동시 변경 필요.
- 마이그레이션이 모든 SELL을 덮어쓰므로 사용자가 의도적으로 입력한 값이 사라짐 — 사용자 결정사항이지만 변경 사실을 changelog/UI 안내에 명시 고려.
- `PNL_AFFECTING_FIELDS`에 `reasoning_tags`/`emotion` 추가 → BUY의 두 필드 단독 변경에서도 그룹 lock + 재계산 발생. 정합성을 위한 의도된 트레이드오프.

## 후속 작업 (backlog 등록 완료)

- 이슈 B (tempo 식 단순화), 이슈 C (분석 임계값 단일 SOT), 이슈 E (어드민 PnL 검증 엔드포인트)
- `recalc_group_pnl` 변경 row만 UPDATE 최적화
- SELL `result` 자동 산출 일관 처리
- 라우터 단위 테스트 사전 실패 2건 정리
