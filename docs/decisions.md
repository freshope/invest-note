# 기술 결정 로그

중요한 설계/기술 선택 기록. "왜 이렇게 했지?"를 다시 묻지 않기 위해.

---

## 2026-05-03 | FE simplify Round 6 — AccountFilter / StockSearchInput

- **백로그:** "FE simplify · 타입/구조" 2 항목.
- **결정:**
  - `AccountFilter`: `selectedAccountId: string` + `ACCOUNT_FILTER_ALL = "all"` → `string | null` (`null` = 전체). 상수 제거, 5 파일 수정 (`AccountFilterProvider` / `AccountFilter` / `TradeList` / `StockDetail` / `DetailPanelProvider`).
  - `StockSearchInput prevQuery`: 렌더 중 prev state 비교 패턴 (`StockSearchInput.tsx:51-57`) 그대로 유지.
- **이유:**
  - sentinel: API 계층은 sentinel 미사용(클라 메모리 필터링) → BE 영향 0. `useEffectiveAccountId` 가 정규화 캡슐화. `string | null` 이 마법문자열보다 type-safe.
  - prevQuery: React 공식 ["Adjusting some state when a prop changes"](https://react.dev/learn/you-might-not-need-an-effect#adjusting-some-state-when-a-prop-changes) 권장 패턴. 렌더 중 `setState` 비교는 React 가 commit 전 즉시 재렌더로 동기화 → stale `activeIndex` commit 방지. `useEffect` 대안은 commit→effect→setState→재렌더 4 단계 사이클로 한 프레임 stale 노출 (회귀). 기존 코드 주석의 "참조 비교 무한루프" 표현은 부정확 (`debouncedValue` 는 string primitive) — 본 결정문이 사이클 효율성 / stale frame 회피 프레이밍으로 정정.
- **재평가 트리거:** sentinel 종류가 3+ 가지로 늘면 discriminated union 재평가. React 19+ `use` 훅 / transition 채택 시 prevQuery 재평가.

---

## 2026-05-03 | FE simplify Round 5 — refetchOnWindowFocus 글로벌 default 유지

- **백로그:** "FE simplify · 성능" 의 `refetchOnWindowFocus false 검토`.
- **결정:** 글로벌 default (`true`) 유지. per-query staleTime 만 명시 (`useAnalysisData` 5min / `usePortfolioSummary` 2min / `TradeBasicForm` holding 10s). backlog 메모는 본 결정으로 종결.
- **이유:**
  - 글로벌 변경 blast radius — 모든 useQuery (accounts/trades/portfolio/analysis 등) 영향. 모바일 Capacitor resume / tab visibility 회귀 위험.
  - focus refetch 가 살아 있으면 staleTime 5 분도 다른 앱에서 돌아오면 자동 refetch — stale 노출 시간 사실상 짧음. 탭 안 머무는 동안은 명시적 invalidate 가 보장 (`queryKeys.portfolio` 5 곳, `queryKeys.trades` invalidate 등).
  - "분석 5 분 stale 허용" 같은 도메인 시맨틱은 query 옆 `staleTime` 으로 표현해야 의도 보존.
- **재평가 트리거:** 모바일 백그라운드→포그라운드 복귀 시 동시 refetch 부하가 실측 확인되면 mobile 전용 false 분기 / lightweight summary 쿼리 대체 / `focusManager` 커스터마이즈 검토.

---

## 2026-05-03 | BE simplify Round 5 — `external/quotes._parse_*` 통합 미진행

- **백로그:** "BE simplify · 재사용 / 잔여" 마지막 항목 (`_parse_realtime_price` / `_parse_basic_price` 통합).
- **결정:** 진행 안 함. backlog 에서 제거.
- **이유:** Naver realtime/basic endpoint 응답 구조 비대칭 — realtime 은 `data["datas"][0]` unwrap 후 `closePriceRaw` / shim `now` / `closePrice` fallback, basic 은 unwrap 없이 `closePriceRaw` / `stockEndPrice` / `closePrice` fallback. realtime 의 `datas[0]` 래핑·`now` 필드는 basic 응답에 없고, basic 의 `stockEndPrice` 는 realtime 응답에 없음. 단일 함수화 시 `is_realtime: bool` 분기 파라미터 필요 → LOC 절감 0. 공통 추출 가치도 `float(raw) if raw else 0.0` 1 줄 + 최상위 `closePriceRaw` fallback 정도라 가독성 오히려 손해.
- **재평가 트리거:** Naver 가 두 endpoint 응답 형식 통일, 또는 시세 provider 가 3+ 개로 증가 (`Strategy` 패턴 도입 가치 발생).

---

## 2026-05-03 | BE simplify Round 3 — analysis period SQL push 미진행

- **백로그:** "BE simplify · 효율 / 핫패스" 5 번째 (`routers/analysis` period 파라미터 SQL push).
- **결정:** 진행 안 함. backlog 에서 제거.
- **이유:**
  - `routers/analysis.py:89, 98, 101` 가 `build_positions(all_trades)` / `compute_concentration(positions, all_trades)` / `build_strategy_evaluations(all_trades, holding_days_map)` 에 의도적으로 unfiltered `all_trades` 전달 — line 100 인라인 주석이 비대칭 의도 명시 (compute_profile 누적 일관성 평가용). period filter 는 `pnl_map` / `holding_days_map` / `summary` 에서만 사용.
  - SQL push = 1 round-trip → 2 round-trip — `all_trades` 어차피 필요하므로 period ≠ 'all' 시 별도 fetch 필수. 개인 투자자 데이터 (수십~수백 거래) 에서 round-trip (~10ms) > 메모리 필터 (<1ms). **net negative.**
  - 분기 workaround (`period == "all"` 만 1 회 fetch) 도 marginal benefit 대비 복잡도 증가로 거부.
- **재평가 트리거:** 거래 데이터 천 단위 이상 증가 (페이지네이션 도입 시 자연 감소), 또는 `all_trades` invariant 변경 (예: `compute_profile` 도 period-filtered 결정). `domain/analysis/period.py:filter_by_period` 유지.

---

## 2026-05-03 | FE simplify Round 3 — HoldingCard pressing state (data attribute 채택)

- **맥락:** Round 1 에서 `pressing` `useState` + 4 개 pointer 핸들러를 CSS `:active:scale-[0.98]` 로 단순화 시도했으나, inner note 영역의 `onPointerDown` `stopPropagation()` 이 outer `:active` 를 차단하지 못해 원본 UX (멀티라인 note 탭 시 outer 카드 scale 미발동) 가 깨져 복원 (커밋 `9e494ce`). 사용자 확인 결과 원본 UX 는 의도된 동작.
- **결정:** `useState`/4 핸들러는 유지하되, className 조건부 (`pressing && "scale-[0.98]"`) 만 `data-pressing={pressing ? "true" : undefined}` + Tailwind v4 `data-[pressing=true]:scale-[0.98]` variant 로 교체. nested clickable 없는 카드 (TradeCard 등) 는 CSS `:active` 그대로 유지 (본 결정은 HoldingCard 한정).
- **이유:** CSS `:active` 는 React synthetic event 의 stopPropagation 을 우회 발동 → 의도된 UX 보존 불가. native `<button>` 변환은 nested clickable 충돌 (HTML spec). data attribute 방식은 JS 가 상태만 표현하고 시각 변화는 CSS 가 선언적으로 책임 → 추후 시각 변화 추가 시 className 분기 미증가.
- **트레이드오프 / 재평가:** LOC 중립 (Round 1 단순화 동기였던 "JS state 제거" 미달성). nested clickable note 가 제거되면 CSS `:active` 로 전환 가치, nested stop layer 패턴이 다른 카드에서도 필요하면 별도 stop layer wrapper 재평가.

---

## 2026-05-03 | FE simplify — Card primitive 추출 미진행

- **백로그:** "FE simplify · 컴포넌트 추출" 의 `Card` primitive 30+ 곳 (`rounded-2xl bg-muted/60`).
- **결정:** `<Card>` 컴포넌트도 CSS 유틸 (`.card-shell`) 도 도입 안 함. 인라인 클래스 그대로 유지. 백로그 항목 종결.
- **이유:** 사용처 32 곳 / 18 파일이지만 ① 셸 마크업이 단 2 개 유틸 클래스 — `<Card className="...">` 가 인라인 대비 토큰 절감 가치 미미. ② padding 변종 7 가지 (`p-3.5×6`, `p-4×10`, `p-5×2`, `p-8×1`, `px-4 py-1×1`, `px-4 py-3×1`, 스켈레톤 padding 없음 ×5) + interaction (`active:scale-[0.99]`, `cursor-pointer`) / overflow / div·button 혼합으로 다양 — prop API 흡수 시 escape-hatch `className` 만연 (추상화 → passthrough 전락). ③ Round 2~7 추출은 시맨틱 콘텐츠 (EmptyCard 의 title/description, BreakdownList 의 items 등) 가 prop API 를 자연스럽게 만들었으나 순수 시각 셸은 동일 패턴 부적용.
- **재평가 트리거:** ① 셸 클래스 변경 PR 6 개월 내 2 회 이상, ② 인터랙티브 카드 5 곳 이상으로 증가, ③ 시맨틱 props (`as`, `interactive`) 가 절반 이상 사용처에서 요구.

---

## 2026-05-03 | BE simplify Round 2 — TradeWithAccountResponse 스키마화 미진행

- **백로그:** Round 2 "응답 매핑" 5 번째 (`_trade_with_account_dict` 의 `pop` 기반 dict reshape → `TradeWithAccountResponse` + `response_model`).
- **결정:** 진행 안 함. backlog 에서 제거.
- **이유:**
  - LOC 중립~증가 — 7 줄 helper 제거하려면 `TradeWithAccountResponse` + nested `AccountInfo` + `model_validator` 변환 ~30 줄 필요.
  - FE 계약 보존 비용 — FE Trade interface (`fe/src/types/database.ts:27`) 가 snake_case (`account_name`, `ticker_symbol`, `country_code`, `created_at` 등) 사용. `_trade_with_account_dict` 가 통과하는 `model_dump(mode="json")` 은 snake_case. `CamelModel` (`schemas/_base.py`) 적용 시 wire format 이 camelCase 로 바뀌어 FE 가 깨짐. snake_case 보존하려면 `BaseModel` 직접 상속 → `CamelModel` 일원화 컨벤션과 충돌.
  - OpenAPI 정확도 가치 < 비용 — internal-only API.
- **재평가 트리거:** trades 응답 wire format 을 camelCase 일원화 결정 (FE 동시 마이그레이션) 시. 본 결정은 2026-04-30 Tier 3 / 본 라운드의 다른 미진행 결정과 동일한 "다르게 보이지만 단순화 비용이 더 큰 사례" 패턴.

---

## 2026-04-30 | BE simplify Tier 3 — aggregate.py 3-bucket loop / build_strategy_evaluations 호출 통합 미진행

- **백로그:** Tier 3 항목 E (`aggregate.py` 3 버킷 루프 → `_bucketize` 헬퍼) / F (`build_strategy_evaluations` 의 router (`all_trades`) / `compute_summary` 내부 (period-filtered) 두 호출 통합).
- **결정:** 두 항목 모두 통합 안 함. 두 호출 지점에 의도 차이 docstring 추가 (F1) 까지만 진행.
- **이유:**
  - E: 3 버킷이 도메인 의미 (계획된 전략 / 전략 준수도 / 감정) 다름. `strat_map` 만 보유일 (`days`) 추적, key 추출 fallback 정책 비대칭 (evaluation fallback / `ADHERENCE_UNKNOWN` / `EMOTION_UNTAGGED`). 단일 헬퍼화 시 옵션 매개변수 (보유일 추적 여부, key fallback 정책) 확산 → 가독성 손해.
  - F: router 호출은 `compute_profile` 장기 일관성 평가용 (전체 거래), `compute_summary` 내부 호출은 기간별 `strat_map` / `adherence_map` 스냅샷용 (period-filtered). 어느 입력으로 통일해도 시맨틱 손실.
- **재평가 트리거:** 표면적 유사성으로 재제기되더라도 본 결정 + docstring 으로 차단. 두 항목 모두 "다르게 보이지만 사실 다른 것" 패턴.

---

## 2026-04-30 | trade group 매칭 — `ticker_symbol` 항상 존재 invariant 명시 의존

- **맥락:** `domain/holdings.py` 의 `_is_flexible_match` 와 `domain/realized_pnl.py` 의 `_is_same_group` 이 같은 의도 (같은 종목·계좌·국가 trade 그룹화) 였으나 매칭 정책이 미묘하게 달랐음. 전자는 `trade_id == target_ticker OR trade.asset_name == target_asset` (OR 너그러움), 후자는 `trade_id == (key.ticker or key.asset_name)` (단일 비교, strict). `routers/portfolio.py` 의 `/holding` SQL 도 `ticker_symbol = $4 OR asset_name = $5` 분기 보유. 두 정책의 결과 차이는 `Trade.ticker_symbol` 이 빈 문자열인 경우에만 발생.
- **결정:** `Trade.ticker_symbol` 은 항상 채워진다는 invariant 를 명시적으로 신뢰. 이 가정 하에 `_is_flexible_match` 의 OR 분기와 `/holding` SQL 의 `OR asset_name = $5` 분기를 dead branch 로 간주해 모두 제거. `LotKey` 폐기, `TradeGroupKey` 단일 키 + `is_same_group` 단일 매칭 함수로 통합. 후속으로 `routers/trades.py` 의 `GET /api/trades?ticker=...` 메모리 필터도 `t.ticker_symbol == ticker` strict 비교로 정리.
- **이유:** 두 함수의 정책 차이를 유지하면 "왜 다른가" 추적 비용이 영구화. invariant 가 깨진 데이터가 실재하지 않는 한 strict 통일해도 동작 회귀 없음. 백엔드 도메인 코드와 SQL 양쪽에서 invariant 위배 시 동일하게 매칭 실패하므로 정합성 일관됨.
- **트레이드오프:** invariant 가 깨진 레거시 row 가 DB 에 존재한다면 holding 이 0 으로 잘못 계산. 향후 데이터 임포트 경로 (broker_import 등) 에서 `ticker_symbol` 빈 문자열 진입 차단 검증 강화 필요. 검증 쿼리: `SELECT count(*) FROM trades WHERE ticker_symbol = '' OR ticker_symbol IS NULL`.

---

## 2026-04-28 | 일괄 등록 종목명 매칭을 Naver API 단일화 + stocks 마스터 제거

- **맥락:** 거래명세서 일괄 등록의 종목명→ticker 매칭이 `stocks` 마스터 exact match 에 묶여 ① 약칭 미일치 ("현대차" vs "현대자동차"), ② 마스터 누락 (KIND 시드는 일반 상장사만 — ETF/ETN/우선주/리츠 제외, "TIGER 미국S&P500" 등 미존재), ③ 변형/공백/대소문자 차이 일체 미허용으로 실패. 보강 시도 (KRX OTP / pykrx / FinanceDataReader / KIS) 모두 약칭 매핑 미제공. 한편 `routers/stocks.py` 의 `/api/stocks/search` 는 이미 Naver 자동완성 API 를 사용 중이며 약칭/부분일치/ETF 자연스럽게 처리.
- **결정:** ① 일괄 등록 ticker 매칭을 `ticker_hints → Naver 검색 API → None` 단일 경로로 단순화. `external/naver_search.py` 로 `_search_kr` 추출 + `find_first_kr_match(q)` helper 추가 (우선순위: 정확일치 > 자동완성 1 순위, 가드: 입력 길이 ≥ 2). `broker_import/ticker_resolver.py` 에서 stocks_repo 의존 제거, 미해결 이름들은 `asyncio.gather` 로 병렬 조회. ② `public.stocks` 테이블, `db_ops/stocks_repo.py`, `scripts/seed_stocks.py` 모두 제거 (마이그레이션 016_drop_stocks.sql 추가). 014/015 는 역사 보존. ③ `routers/trades.py:420` 미해결 사유 메시지와 `PreviewStep.tsx` 안내 문구 갱신.
- **이유:** 마스터 자체 시드 유지 비용 (KIND 의존, ETF 별도 소스 필요, 약칭은 어떤 공식 소스도 미제공) 이 매칭 품질 대비 과도. Naver 자동완성 API 는 검색 자동완성에서 이미 도입된 의존성이라 추가 외부 위험 없이 약칭/ETF/변형 표기를 일거 해결. trades 테이블이 stocks 를 FK 로 참조하지 않아 (`001_initial_schema.sql:30`) 거래 데이터 무영향, 시세 조회/검색은 외부 API 라 마스터와 무관.
- **트레이드오프:** Naver API 단일 의존 (다운/응답 변경 시 일괄 등록 전체 영향) — 5 초 timeout + try/except 로 hang 방지, 검색 라우터와 동일 의존이라 추가 위험 없음. 부분 일치 오매칭 가능 ("삼성" → "삼성전자") — 입력 길이 ≥ 2 가드 + 정확일치 우선 정책으로 1 차 완화, 보수적 운영 후 필요 시 사용자 수동 매칭 UI 도입. 미매칭 N 건당 N 회 외부 호출 — `asyncio.gather` 병렬화로 완화. 마스터 재도입은 향후 ETF/약칭 데이터 소스 확보 시 재검토 (`docs/backlog.md` 기록).

---

## 2026-04-28 | 분석 임계값 단일 SOT (BE thresholds.py 통합 + FE constants/analysis.ts 동기화)

- **맥락:** 임계값 (`SCALPING_MAX_DAYS=1`, `SWING_MAX_DAYS=30`, `HHI_HIGH=0.5`, `HHI_MID=0.25`, `TOP1_WEIGHT_HIGH=0.4`) 이 BE 내부에서도 분산 (`strategy_adherence.py` 매직 넘버 / `concentration.py` 모듈 상수) 되고 FE/BE 양쪽 이중화. `rules.py` 9 개 규칙 함수에 도메인 판정 임계값 (`feeling_rate < 40`, `reflection_rate >= 30`, `win_rate < 30`, `missing_tag_rate < 30`, `result_input_rate >= 50`, `avg_holding_days <= 7`) 과 최소 샘플 가드 (`count < 5/3`, `total_trades < 5`, `sell_trades < 3/5`) 가 매직 넘버로 박혀 있어 SOT 외부에서 침묵 변경 가능. FE `SummaryCards.tsx` 가 `60`/`40` 하드코드해 BE `WIN_THRESHOLD` 60→65 변경 미추종. FE `aggregate.ts:computeSummary` / `rules.ts:evaluateRules` / `strategy-adherence.ts` 함수들은 production 미호출 (테스트만) 상태로 임계값 import 의존성 생성.
- **결정:**
  1. BE `domain/analysis/thresholds.py` 단일 모듈로 추출. `strategy_adherence.py` (전략 임계값) / `rules.py` (HHI 임계값) / `concentration.py` 가 모두 import. `concentration.py` 자체 상수 정의 제거.
  2. `rules.py` 의 모든 비교 매직 넘버를 `thresholds.py` 상수로 흡수 — 도메인 판정 6 개 (`FEELING_RATE_HIGH`, `REFLECTION_RATE_LOW`, `LOSING_STRATEGY_RATE`, `MISSING_TAG_RATE_HIGH`, `RESULT_INPUT_RATE_LOW`, `SCALPING_HOLDING_LIMIT_DAYS`) + 최소 샘플 가드 8 개 (`MIN_EMOTION_TRADES/RESULTS`, `MIN_TOTAL_TRADES`, `MIN_SELL_TRADES`, `MIN_HIGH_WINRATE_SELL`, `MIN_SCALPING_TRADES`, `MIN_STRATEGY_TRADES/RESULTS`). 명명은 "어디서 쓰이는가" 가 아닌 "무엇을 의미하는가" 기준 (같은 5 라도 의미 다르면 별도 상수).
  3. FE `SummaryCards.tsx` 가 `WIN_THRESHOLD`/`LOSS_THRESHOLD` import — 하드코드 제거.
  4. FE dead 분석 로직 삭제 — `aggregate.ts:computeSummary`, `rules.ts:evaluateRules`, `strategy-adherence.ts:inferActualStrategy/evaluateStrategyAdherence`, `AnalysisDashboard.tsx` fallback 호출, 관련 테스트 (BE `tests/test_analysis_logic.py` 가 동일 검증 담당). 응답 타입 정의 (`AnalysisSummary`, `Suggestion`, `StrategyEvaluation`) 만 보존.
  5. FE 정적 export 구조상 BE 직접 참조 불가 — `fe/src/lib/constants/analysis.ts` 위치 유지. **임계값 변경 시 BE/FE 두 파일을 함께 수정한다.**
- **이유:** "임계값은 한 곳에서 변경" 정신을 깨고 있던 분산을 모두 흡수. BE 는 `thresholds.py` 만 보면 모든 도메인 임계값 파악. FE 자체 평가 로직은 BE 응답이 모든 판정 결과를 담고 있어 dead code, 임계값 동기화 책임 분산만 유발.
- **트레이드오프:** ① BE suggestions 응답 빈 배열/실패 시 인사이트 섹션 공란 (fallback 사라진 비용) — `useAnalysisData` 별도 에러 핸들링 경로 담당. ② BE/FE 동기화는 여전히 수동 — PR review 시 양쪽 diff 확인 필요. 자동 sync (JSON export → FE 빌드 import) 는 정적 export 구조 + 별도 빌드 단계 비용으로 미적용. ③ `analysis.py:_HOLDING_BUCKETS` / `_size_bucket` 은 표시용 버킷팅이라 SOT 흡수 제외. UI 색상/라벨용 임계값 (`WinRateBar`, `DiversificationPanel`) 은 FE constants 그대로 — BE→rating 필드 응답화는 비용 대비 가치 낮아 미적용.

---

## 2026-04-28 | SELL 거래 reasoning_tags · emotion 자동 산출 정책

- **맥락:** 분석 탭의 byTag/byEmotion 이 SELL 시점에 직전 BUY 를 매번 FIFO 매칭해 태그/감정 귀속 — 프론트엔드 키에서 `account_id` 누락으로 다계좌 사용자에게 잘못된 귀속 가능. EmotionStats 는 BUY+SELL 합산 `count` 와 SELL 한정 `sellCount` 를 분리해 UI 표기 혼동 유발.
- **결정:** `strategy_type` 패턴 (`compute_group_pnl` → `recalc_group_pnl` → SELL row UPDATE) 을 그대로 `reasoning_tags`/`emotion` 에 확장. 두 필드를 SELL row 에 저장, 분석 라우터/aggregate 는 SELL 저장값만 카운트. 통합 정책은 FIFO 소비 BUY lot 중 **가장 최근 (`traded_at` 최대, 동률 시 BUY order 최대) lot 의 값**을 그대로 복사 (`_meta_from_consumed_latest`). SELL UI 는 두 필드를 read-only chip 으로 표시, PATCH 입력은 라우터 `strip_sell_auto_derived` 헬퍼에서 명시적으로 제거. 기존 데이터는 011 패턴의 PL/SQL FIFO 마이그레이션 (013) 으로 백필.
- **이유:** byTag FIFO 매칭의 hot-path 비용을 mutation 시점으로 이동. frontend 키 누락과 EmotionStats 의미 혼동을 동시 해소. `strategy_type` 과 동일 패턴이라 향후 SELL 자동 산출 필드 (예: `result`) 추가 용이. `strategy_type` (수량 가중 최다) 과 `reasoning_tags`/`emotion` (가장 최근 BUY) 의 두 정책 공존은 전자가 SELL 의 "주된 전략", 후자는 "직전 진입의 근거/감정" 으로 의미가 다르기 때문.
- **트레이드오프:** `PNL_AFFECTING_FIELDS` 에 두 필드 추가로 BUY 메타 단독 변경에서도 그룹 advisory lock + recalc 발동 — DB write 부하 약간 증가, 정합성과 교환. 사용자가 SELL 에 직접 입력했던 기존 emotion/reasoning_tags 값은 마이그레이션 시 무조건 덮어써짐 (의도된 결정). 자동 산출 정책 책임은 `SELL_AUTO_DERIVED_FIELDS` 상수와 `strip_sell_auto_derived` 헬퍼로 단일 등록 지점화.

---

## 2026-04-28 | 라이트 모드 전용 — 다크 모드 제거

- **결정:** 테마 토글 UI (`AppearanceSection`), `next-themes` 의존성, `ThemeProvider` 래퍼, `globals.css` 의 `.dark { ... }` CSS 변수 블록 및 `@custom-variant dark` 선언, 11 개 컴포넌트의 `dark:` Tailwind 프리픽스 26 곳 모두 제거. `ThemedToaster` → `AppToaster` 리네임, sonner 기본값 (light) 활용해 prop 단순화.
- **이유:** 디자인 토큰을 `:root` 단일 소스로 관리. 컴포넌트마다 dark variant 색을 별도 결정·QA할 필요 없음. `next-themes` 제거로 번들/hydration 비용 소폭 감소. `<html suppressHydrationWarning>` 회피 코드 제거.
- **트레이드오프:** 다크 모드 재도입 시 `dark:` 프리픽스 재추가 + `.dark` CSS 변수 블록 복원 필요. 기존 사용자의 `localStorage["theme"]` 은 next-themes 가 사라져 무시 (별도 마이그레이션 코드 미배치). shadcn 컴포넌트 동기화 시 원본 `dark:` 클래스와 diff 발생 가능하나 본 프로젝트는 `src/components/base/` 래퍼 경유라 영향 제한적.

---

## 2026-04-27 | MVP 해외 주식 제외 — 신규 진입 차단, 기존 데이터 호환 유지

- **맥락:** MVP 는 국내 주식 매매 기록·분석에 집중. 기존 코드의 US/Yahoo 검색·시세와 USD 합산 전제는 환율 미적용 총자산·분석 왜곡 발생 가능.
- **결정:** MVP 에서는 신규 해외 주식 검색/시세 조회/신규 매수 등록 차단. `country_code` 타입과 기존 US/OTHER 데이터 렌더링은 유지 — 과거 데이터 조회와 보유분 매도 흐름 보존.
- **트레이드오프:** 기존 해외 보유분은 v2 전까지 신규 시세 `null` 일 수 있음. v2 재도입 시 Yahoo 등 provider, USD/KRW 환율, 크로스 통화 분석 정합성 함께 설계.

---

## 2026-04-26 | 미래 거래 등록 차단 — 입력 경계에서 거절, 분석 필터 상한 유지

- **맥락:** 분석 기간 필터는 "all" 에서도 `now` 이후 거래를 제외 — 사용자가 미래 거래를 등록하면 기록에는 보이지만 분석에는 빠지는 혼란 발생 가능.
- **결정:** 신규 거래 등록에서 미래 `traded_at` 차단. 프론트는 캘린더와 zod 검증으로 사전 차단, FastAPI `TradeCreate` 스키마는 문자열/`datetime` 입력을 UTC 정규화한 뒤 서버 현재 시각보다 미래면 400 거절. 분석 필터의 `now` 상한은 기존/외부 유입 데이터 방어용으로 유지.
- **트레이드오프:** 미래 예약/계획 거래는 MVP 미지원. 향후 CSV 임포트나 계획 거래 기능 추가 시 별도 데이터 타입 또는 명시적 import 정책 필요.

---

## 2026-04-25 | asyncpg UUID→str 타입 경계 — 라우터 입력 경계에서 변환

- **맥락:** asyncpg 는 PostgreSQL UUID 컬럼을 `uuid.UUID` 객체로 반환. Pydantic 모델 (`Trade`) 은 `_uuid_to_str` validator 로 자동 str 변환되지만, 일반 dataclass (`Account`) 는 type hint 강제 부재로 `account.id` 가 UUID 객체로 남음. `build_account_snapshots` 에서 `by_account.get(account.id)` 가 str 키와 타입 불일치 → 항상 빈 배열 → `stock_evaluation = 0`.
- **결정:** 라우터 입력 경계 `_account_from_row` 에서 UUID 필드를 str 변환. 도메인 함수 `build_account_snapshots` 에도 `str(account.id)` 방어 처리 유지.
- **이유:** 타입 강제 없는 dataclass 는 입력 경계에서 정규화해야 런타임 타입 불일치 차단. 도메인의 `str()` 호출은 라우터 외 경로 (테스트, 직접 호출) 에서 UUID 가 들어올 경우의 안전망.
- **트레이드오프:** asyncpg 를 사용하는 다른 dataclass 변환 함수에도 동일 패턴 적용 필요. Pydantic 전환 시 validator 로 중앙화 가능하나 현재는 도메인 모델을 경량 dataclass 로 유지.

---

## 2026-04-25 | advisory lock timeout — SET LOCAL 2s + 전역 handler

- **맥락:** `feature/toctou-advisory-lock` 에서 `pg_advisory_xact_lock` 도입 시 lock_timeout 미설정으로, 운영에서 동일 그룹 동시 mutation 이 몰리면 뒤 요청이 무한 대기하며 워커 점유 위험.
- **결정:** `acquire_trade_group_lock` 내부에 advisory lock 직전 `SET LOCAL lock_timeout = '2s'`. `LockNotAvailableError` (sqlstate 55P03) 발생 시 `main.py` 전역 exception handler 에서 `409 Conflict` + 한국어 안내 메시지 변환.
- **이유:** `SET LOCAL` 은 트랜잭션 종료 시 자동 reset. 2s 는 운영 hang 방어용 보수적 값 (일반 INSERT/UPDATE 는 훨씬 빠름). 전역 handler 선택으로 `db_ops` 가 `errors.APIError` 를 import 하지 않아 의존 방향 유지.
- **트레이드오프:** 같은 트랜잭션 내 INSERT/UPDATE row-lock 대기에도 2s 상한 적용 (현 코드베이스에서 무해). 2s 는 휴리스틱 — 운영 모니터링 후 조정 필요. 클라이언트 재시도 정책은 별도 처리.

---

## 2026-04-24 | TOCTOU race — pg_advisory_xact_lock 선택

- **맥락:** trades 라우터의 `list_trades → validate → write` 흐름에서 동시 SELL 요청이 같은 보유량 스냅샷을 읽고 둘 다 validate 통과해 음수 보유량 발생 가능. `FOR UPDATE` 를 걸 행이 없고 (보유량은 trades 집계로 유도), `SERIALIZABLE` 격리는 retry loop 가 필요해 라우터 구조 변경 비용이 큼.
- **결정:** transaction-scoped advisory lock (`pg_advisory_xact_lock`) 사용. 키는 `TradeGroupKey(ticker, asset_name, country, account_id)` + `user_id` 를 `hashtextextended` 로 bigint 해시. create/update/delete 세 mutation 경로에 `list_trades` 이전 삽입.
- **이유:** xact 변종은 트랜잭션 종료 시 자동 해제 → Supavisor transaction mode pooler 에서 session-level 변종 (`pg_advisory_lock`) 대비 leak 없음. 마이그레이션 불필요 (Postgres 11+ 내장). 기존 `TradeGroupKey` 도메인 타입 재사용으로 그룹 경계 일관성 유지.
- **트레이드오프:** 해시 충돌 시 불필요한 직렬화 발생 (정합성 영향 없음, 64-bit 충돌 확률 무시 가능). lock_timeout 후속 필요 → 2026-04-25 결정으로 보완.

---

## 2026-04-24 | FE constants — 레이어 분리 + 중앙화 (BE co-location 미적용)

- **결정:** FE 상수는 BE 처럼 도메인 폴더 내 co-location 이 아닌 `fe/src/lib/constants/` 중앙 폴더로 관리. 단일 파일에서만 쓰이는 UI 로컬 상수 (색상, 애니메이션 ms, 탭 정의 등) 는 컴포넌트 파일 내 유지.
- **이유:** FE UI 는 여러 도메인 데이터를 혼합해서 보여주는 것이 본업이라 도메인 경계가 BE 처럼 강하지 않음. co-location 하면 어디에 둘지 애매한 상수 발생. 현재 구조 (레이어 분리 + 도메인 서브폴더) 가 FE 특성에 맞는 절충안.
- **트레이드오프:** 상수가 늘어날수록 constants 파일 관리 필요. 여러 곳에서 쓰이는 상수만 선별 이관, 단일 파일 전용은 로컬 유지 원칙.

---

## 2026-04-24 | BE 상수 co-location — 모놀리식 constants.py 배제

- **결정:** API 백엔드 상수를 단일 `constants.py` 가 아닌 각 도메인 모듈에 인접 배치. `domain/trade_types.py` (enum 단일 소스), `domain/trade_utils.py` (KST·MS_PER_DAY), `external/constants.py` (URL·User-Agent·timeout), `auth/constants.py` (JWT·GUC 상수), `errors.py` (에러 메시지) 구조.
- **이유:** 모놀리식 파일은 응집도 없이 크기만 커져 수정 범위 파악 어려움. 도메인 경계 내 co-location 이 변경 이유가 같은 상수를 함께 관리.
- **트레이드오프:** `schemas/` → `domain/` 단방향 import 규칙 필수. 순환 import 발생 시 추적 어려울 수 있음.

---

## 2026-04-24 | 거래·종목 상세 패널 — 2-슬롯 + open/payload 분리 구조 (mode 제거)

- **결정:** `mode` 단일 상태 제거. `tradePayload`/`stockPayload` (콘텐츠) + `tradeOpen`/`stockOpen` (애니메이션) 분리. 동일 타입 재오픈 시 `key` 증가로 portal remount → z-order 재정렬.
- **이유:** `mode` SSOT 는 두 타입이 동시에 열릴 수 없어 Stock → Trade 이동 시 Stock 이 닫혀 뒤로가기가 1 단계. 2-슬롯 구조에서는 각 타입이 독립적으로 open/close 되어 최대 2 번 뒤로가기로 원래 페이지 복귀 가능.
- **트레이드오프:** `createPortal` 의 DOM 추가 순서가 z-order 를 결정하므로 동일 타입 재오픈 시 key remount 필수. `open=false` 후 `PANEL_ANIMATION_MS+50ms` 타이머로 payload null 처리해 슬라이드 아웃 중 콘텐츠 유지.

---

## 2026-04-23 | FastAPI CORS — Capacitor WebView origin 허용

- **결정:** `Settings.cors_origins` 기본값과 `.env.example` 에 `capacitor://localhost` (iOS), `https://localhost` (Android, 포트 없음) 추가. `allow_credentials=True`, 고정 리스트 유지.
- **이유:** Capacitor WKWebView 가 이 두 origin 으로 페이지를 서빙해 기존 웹 origin 만으로는 preflight 거부. 고정 2 개라 regex 불필요.
- **트레이드오프:** production `CORS_ORIGINS` 환경변수에도 반드시 반영 필요.

---

## 2026-04-23 | OAuth Deep Link — `com.investnote.app://auth/callback`

- **결정:** reverse-DNS 형식 고정. 짧은 형식 (`investnote://`) 배제.
- **이유:** Bundle ID 와 일치, App Store 유니크성으로 하이재킹 위험 최소.
- **후속:** Universal Links 전환은 도메인·심사 확정 후 재검토.

---

## 2026-04-23 | Supabase 클라이언트 — `@supabase/supabase-js` + PKCE + implicit fallback

- **결정:** `@supabase/ssr` → `@supabase/supabase-js` 의 `createClient`. `auth.flowType: 'pkce'` 명시. `CapacitorDeepLinkHandler` 가 `?code=` (PKCE) 와 `#access_token=` (implicit) 모두 수용.
- **이유:** `@supabase/ssr` 은 쿠키 기반 storage 인데 Capacitor iOS `capacitor://localhost` 에서 WebKit 이 쿠키를 저장하지 않아 PKCE verifier 분실. `supabase-js` 는 localStorage 기본이라 안정 persist. provider/버전 이슈로 implicit 응답 가능성 배제 불가라 fragment fallback 유지.
- **후속:** 서버측 세션 공유가 필요해지면 `@supabase/ssr` 재도입 검토 (현재 FastAPI Bearer 로 불필요).

---

## 2026-04-23 | OAuth Deep Link 리스너 — 루트 레이아웃 상주

- **결정:** `CapacitorDeepLinkHandler` 단일 컴포넌트로 분리해 루트 `layout.tsx` 내 상주 마운트. `@capacitor/app`·`@capacitor/browser` dynamic import.
- **이유:** Cold start 시 `App.getLaunchUrl()` 을 리스너 등록 전에 호출해야 이벤트 손실 방지. 루트 상주로 페이지 이탈/재진입 경쟁 상태 제거. dynamic import 로 웹 번들에 플러그인 chunk 미포함.

---

## 2026-04-23 | Capacitor 셋업 — 설치 `fe/`, appId `com.investnote.app`

- **결정:** Capacitor 8.x 를 `fe/` 워크스페이스 내부 설치. `webDir=out`. `ios/`, `android/` 네이티브 프로젝트 커밋.
- **이유:** Next.js export 결과물 경로 일치. 네이티브 커밋은 Capacitor 공식 권장 (재현성).
- **트레이드오프:** appId 는 스토어 등록 후 변경 불가. 레포 크기 수 MB 증가.

---

## 2026-04-22 | 정적 export + Next.js API Routes 제거 (Chunk D)

- **결정:** `output: 'export'` 정적 모드 전환. Server Component + Route Handler 전부 제거. FastAPI 가 모든 API 커버.
- **이유:** Capacitor 가 정적 번들을 WebView 에서 직접 로드 — SSR/쿠키 기반 서버 기능 사용 불가.
- **트레이드오프:** 동적 라우트 (`records/[id]`, `stocks/[country]/[ticker]`) 삭제 (패널 진입 대체, 딥링크 소실). 인증은 localStorage 기반. `NEXT_PUBLIC_API_BASE_URL` 미설정 시 모든 API 호출 실패.

---

## 2026-04-22 | 모노레포 — pnpm workspace (`fe/` + `be/`)

- **결정:** 루트 pnpm workspace 로 `fe/` (Next.js) 과 `be/` (FastAPI) 분리. 루트 `package.json` 은 위임 스크립트만.
- **이유:** 단일 레포에서 코드·히스토리·이슈 공동 관리가 1 인 팀에 적합. `fe/` 는 독립 레포 분리 여지 확보.
- **트레이드오프:** Vercel 배포 시 Root Directory 를 `fe` 로 수동 설정. `scripts/backfill-pnl.ts` 는 `fe/` 에서 실행.

---

## 2026-04-22 | FastAPI 인증 — Supabase JWKS (ES256)

- **결정:** `PyJWKClient` 로 `/auth/v1/.well-known/jwks.json` 공개키 조회해 ES256 검증. `@lru_cache` 로 프로세스당 클라이언트 1 개.
- **이유:** Supabase 권장. 시크릿 서버 저장 불필요, 키 로테이션 자동 반영.
- **트레이드오프:** cold start 시 JWKS 동기 HTTP 호출 (~100ms), 이후 메모리 캐시.

---

## 2026-04-22 | FastAPI DB — asyncpg + RLS GUC 주입

- **결정:** asyncpg 풀. `acquire_for_user()` 가 transaction 안에서 GUC 2 개 (`role`, `request.jwt.claims`) 를 `set_config` 로 주입해 기존 RLS policy 재사용.
- **이유:** supabase-py 는 트랜잭션 미지원 + SQL 표현력 제한. GUC 주입으로 `auth.uid()` 자동 동작 → SQL 에 `WHERE user_id` 명시 불필요.
- **트레이드오프:** 요청마다 `set_config` 1 회 추가 (단일 SELECT 로 통합).

---

## 2026-04-22 | Supabase Pooler — Session mode (port 5432)

- **결정:** Supavisor Session Pooler (5432). `statement_cache_size=0`.
- **이유:** Direct Connection 은 IPv6-only 로 로컬/Render 접속 불가. Transaction Pooler (6543) 는 `SET LOCAL` 이 connection 반환 후 다른 요청에 영향 가능. Session Pooler 는 connection 당 1 세션 보장.
- **트레이드오프:** 동시 접속 증가 시 풀 소진 가능. MVP 수준에선 문제없음.

---

## 2026-04-20 | SELL avg_buy_price DB 저장

- **결정:** SELL 등록·재계산 시 `profit_loss` 와 `avg_buy_price` 를 함께 계산·저장 (migration 007: `avg_buy_price numeric NULL` 추가).
- **이유:** 조회 시점 WAC 재계산 제거. `recalcGroupPnL` 같은 흐름에서 처리되어 추가 비용 없음.
- **트레이드오프:** 백필 스크립트 1 회 실행.

---

## 2026-04-20 | 수정 불가 필드 확장 — 삭제 후 재등록 정책

- **결정:** account_id, ticker_symbol, asset_name, country_code 를 수정 불가로 확장. 잘못 입력한 거래는 삭제 후 재등록.
- **이유:** cross-group 재계산 (이전 그룹 + 새 그룹 양쪽 검증) 로직이 복잡하고 edge case 많음. 단순 정책이 서버 로직·정합성 모두 유리. 계좌·종목 변경 빈도는 극히 낮음.
- **보완:** TradeEditPanel 에 읽기 전용 표시 + 안내.

---

## 2026-04-20 | WAC fallback 완전 제거

- **결정:** `buildPnlMap`, `buildPositions`, `computeFlexibleBreakdown` 에서 WAC fallback 제거하고 저장값 (`profit_loss`, `avg_buy_price`) 직접 사용. `computeRealizedPnL` 은 테스트용으로 export 유지.
- **이유:** `recalcGroupPnL` 이 CUD 때마다 갱신해 정합성 보장됨. 중복 연산 제거, `computeFlexibleBreakdown` 이 O(n) → O(1).
- **트레이드오프:** `recalcGroupPnL` 실패로 null 남은 행은 손익 0 표시. legacy oversell matched_qty 불일치 케이스는 spec 수용.

---

## 2026-04-19 | 거래·종목 상세 패널 상태 — Context SSOT (2026-04-24 에 2-슬롯으로 대체)

초기 도입 시 `DetailPanelProvider` 의 단일 `mode: "trade" | "stock" | null` SSOT 로 mutual-exclusive 보장 — 무한 중첩 해결. Stock → Trade 이동 시 Stock 이 닫히는 1-단계 뒤로가기 문제로 2026-04-24 에 2-슬롯 + open/payload 분리 구조로 교체.

---

## 2026-04-17 | 시세 API — 비공식 API

- **결정:** 네이버 금융 (KR). Yahoo Finance (US) 는 2026-04-27 결정에 따라 MVP 에서 제외하고 v2 로 이동. KIS Open API 는 v2.
- **트레이드오프:** 응답 포맷 깨질 수 있음.

---

## 2026-04-17 | 평균단가 — WAC (가중평균단가)

- **결정:** 보유 종목 평균단가를 WAC 로 계산.
- **이유:** 한국 증권사 대부분이 WAC — 사용자 익숙도 높음.
- **트레이드오프:** FIFO 대비 세금 계산 정확도 낮음 (세금은 MVP 외).

---

## 2026-04-17 | 분석 탭 WAC — 순수 가격 기준 (수수료 제외)

- **결정:** `portfolio.ts` 와 `realized-pnl.ts` 모두 BUY commission 을 WAC 에서 제외. 수수료는 매도 시점에 `- commission - tax` 로 별도 차감.
- **이유:** 포트폴리오 `avgBuyPrice` 표시와 실현손익 계산 기준 통일.
- **트레이드오프:** BUY 수수료가 큰 계좌에서 실현손익 약간 과대계상 가능.

---

## 2026-04-17 | 자산 탭 제거 → 홈 통합

- **결정:** 별도 자산 탭 없이 홈 (`/`) 에 보유 종목 현황 통합.
- **이유:** 탐색 depth 감소 — 모바일 UX 적합.
- **트레이드오프:** 보유 종목이 많아지면 홈이 길어짐.

---

## 2026-04-17 | 탭 구조 — 홈/기록/분석/설정 (자산 대신 분석)

- **결정:** 4 개 탭, "자산" 대신 "분석".
- **이유:** 매매 패턴 분석이 핵심 목표. 자산 현황은 홈으로 커버.
