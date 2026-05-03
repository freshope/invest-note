# 백로그

MVP 이후 구현할 작업 후보 목록.

---

## 분석 탭 성능 / 유지보수

- [ ] 분석 API 쿼리 `.limit(1000)` 가드 — 거래 수 급증 시 메모리/응답 보호
- [ ] 수수료 현황 별도 패널 — BUY commission·세금 합계, 순실현손익 vs 총비용 비교

## FE simplify (Round 1 이후 deferred — 2026-04-30 `/simplify` 결과)

Round 1 (`docs/spec-history/...`) 에서 처리된 6 개 외에 도출된 후속 항목. 위험도/가치 평가 후 Round 2+ 에서 분할 처리.

### useEffect 안티패턴

> Round 4 (2026-05-03) 에서 5 개 항목 모두 처리 완료 — `docs/spec-history/2026-05-03-fe-simplify-round4-useeffect-antipatterns.md` 참고. 백로그 가이드의 `key={open?...}` 제안은 `FullScreenPanel` 의 mounted/visible 2 단계 lifecycle 과 충돌하여 "단조증가 key bump" 패턴으로 교정 적용.

- [ ] `ImportTradesPanel/AccountStep` 자동 단일 계좌 선택 effect — `eligibleAccounts.length === 1` 일 때 `onSelect(...)` 를 호출하는 effect-setState (`AccountStep.tsx:25-28`). derive (예: 부모에서 `defaultSelected` 결정) 또는 render-mount 시점 한 번만 실행하는 패턴 검토. Round 4 범위 외로 deferred.

### 성능

- [ ] recharts dynamic import — `AllocationTabs`, `BehaviorRadar` 의 `import { PieChart, ... }` 정적 → `next/dynamic` lazy. 모바일 콜드스타트 TTI 직접적
- [ ] `tradesApi.list()` 페이지네이션 — 현재 전량 fetch (records/HoldingsList). 무한스크롤/limit + cursor 도입 (BE 협조 필요)
- [ ] `TradeBasicForm` `watch()` 7 회 → `useWatch` 일괄 구독 — 입력 시 전체 폼 리렌더 폭증 (Calendar/StockSearch 포함). 모바일 입력 지연 직접
- [ ] `TradeCard` / `HoldingCard` `React.memo` — 큰 리스트(거래/보유) 부모 리렌더 시 N 개 카드 재렌더. 부모 onPress 콜백 안정화 동반
- [ ] `accountsApi.list` ↔ `portfolioApi.summary` 캐시 키 통일 — settings 페이지 별도 fetch, 공유 안 됨. queryKey 통합 또는 `setQueryData` 미러
- [ ] 무거운 쿼리 staleTime 상향 — 분석/포트폴리오 5 분+, refetchOnWindowFocus false 검토
- [ ] `holding` 쿼리 staleTime 0 → 짧은 staleTime — 매도 폼 종목 입력 변경마다 항상 fetch
- [ ] `groupByDate` 정렬 명시 — Map insertion order 의존, 백엔드 정렬 깨질 시 화면 순서 깨짐
- [ ] `HoldingCard` / `TradeCard` 부모 콜백 안정화 — `useCallback` deps 에 `fetching` 같은 변동값으로 매번 새 함수 생성 → memo 무력화

### 타입/구조 (선택적)

- [ ] `AccountFilter` `"all"` sentinel 검토 — `selectedAccountId: string` + `ACCOUNT_FILTER_ALL = "all"` 패턴이 곳곳에 분기. discriminated union (`{kind: "all"} | {kind: "one"; id}`) 또는 `string | null` 로 type-safe 화 검토. 유지/변경 결정 필요
- [ ] `StockSearchInput` `prevQuery` derived state → `useEffect(() => setActiveIndex(-1), [debouncedValue])` 검토 — 단순화 가치 vs 공식 권장 패턴 간 결정

## BE simplify (Round 1 이후 deferred — 2026-05-01 `/simplify` 결과)

Round 1 (`docs/spec-history/2026-05-01-be-simplify-round1-quick-wins.md`) 에서 처리된 3 개 (`model_copy(update=)` / `dataclasses.replace` / `sort_by_traded_at` 통합) + Round 2 (`docs/spec-history/2026-05-03-be-simplify-round2-response-mapping.md`) 에서 처리된 4 개 + Round 3 (`docs/spec-history/2026-05-03-be-simplify-round3-hot-path.md`) 에서 처리된 4 개 + Round 4 (`docs/spec-history/2026-05-03-be-simplify-round4-domain-cleanup.md`) 에서 처리된 2 개 외에 도출된 후속 항목. 위험도/가치 평가 후 Round 5+ 에서 분할 처리.

> Round 2 (2026-05-03) 에서 응답 매핑 카테고리 4 개 처리 완료 (`asdict` spread / `account_row_to_dict` UUID 흡수 / `patch_account` 추출 / `create_trade` `model_dump` spread). `_trade_with_account_dict` 스키마화는 [decisions.md 2026-05-03](decisions.md) 으로 **미진행 확정**.

> Round 3 (2026-05-03) 에서 효율/핫패스 4 개 처리 완료 (`httpx.AsyncClient` lifespan 공유 / broker parser `run_in_threadpool` / `import_preview` date 범위 좁히기 / `delete_account` round-trip 통합). `routers/analysis` period SQL push 는 [decisions.md 2026-05-03](decisions.md) 으로 **미진행 확정** (`all_trades` 가 의도적 unfiltered 입력, SQL push 가 1→2 round-trip net negative).

> Round 4 (2026-05-03) 에서 도메인 정리 2 개 처리 완료 (`compute_holding_summary` 를 `walk_trades` terminal state 기반으로 재구성 / `build_positions` 119 줄을 `_build_lot_map` + `_lot_to_positions` 헬퍼로 분리).

### 효율 / 핫패스

- [ ] `GET /api/trades` 페이지네이션 + `ticker` 필터 SQL push — 현재 전량 fetch 후 Python 필터 (FE backlog `tradesApi.list()` 와 동반)

### 재사용 / 잔여

- [ ] `accounts_repo.list_accounts` 헬퍼 추출 — 라우터 3곳 (`accounts`/`portfolio`/`trades`) 인라인 SQL 흡수 + `_ACCOUNT_RETURNING_COLS` SOT 화
- [ ] `make_signature` ↔ `make_preview_signature` 4함수 통합 — `account_id: str | None` 단일화 + KST 일자 파싱 헬퍼 (`routers/trades.py:387, 498` 인라인 try/except 흡수)
- [ ] `_holding_bucket` / `_size_bucket` 통합 + `Counter` 로 dist 빌드
- [ ] `_decimal_to_float*` 3 validator 공통 헬퍼 추출 (cosmetic)
- [ ] `EMOTION_UNTAGGED` / `TAG_UNTAGGED` Literal 타입 누락 — `EmotionBucket = EmotionType | Literal["UNTAGGED"]` 정의
- [ ] `SellBreakdown.is_manual_input` 필드 폐기 또는 명세화 — BE/FE 모두 항상 `false` 만 송수신, FE `TradeDetail.tsx:177` 가 분기 사용. 진짜 manual input 케이스 명세 후 제거 결정 (BE+FE 동기 변경)
- [ ] `external/quotes._parse_realtime_price` / `_parse_basic_price` 통합 (cosmetic, realtime shim 차이로 완전 통합 어려움)

> 참고: `aggregate.py` 4 누산 패턴 (`strat_map`/`adherence_map`/`emotion_map`/`tag_map`) 헬퍼화는 [Tier 3 결정 (2026-04-30)](decisions.md) 으로 **미진행 확정**. 향후 재제기 시 `decisions.md` 의 도메인 시맨틱 비대칭 근거 참조.

## 운영 / 어드민 도구

- [ ] PnL 저장값 검증 엔드포인트 (이슈 E) — `/api/admin/verify-pnl` 신설. SELL의 저장된 `profit_loss`/`avg_buy_price`/`holding_days`/`strategy_type`/`reasoning_tags`/`emotion`을 `compute_group_pnl()`로 재계산해 차이 검출. 사용자 단위 batch + 차이 리포트 + (옵션) 자동 보정. 권한은 admin scope. DB 직접 수정·마이그레이션 누락·mutation 경로 우회 시 분석 탭과 거래 기록 합계 불일치를 잡기 위함.

## 거래내역서 임포트 — 후속 과제

- [ ] stocks 마스터 재도입 검토 (트리거 발생 시에만) — 현재는 Naver 검색 API 단일 매칭(`docs/decisions.md` 2026-04-28 참고). 다음 트리거 중 하나가 실제로 발생하면 재검토: ① ETF/ETN/약칭을 모두 커버하는 공식 데이터 소스(공공데이터포털·KRX OpenAPI 등) 신규 확보, ② Naver 자동완성 API의 응답 포맷 변경/율 제한/장기 다운으로 일괄 등록 매칭이 사실상 불가, ③ 오프라인/내부망 배포 요구사항 발생. 트리거 미발생 상태에서 선제 재도입은 비용 대비 가치 낮음. 재도입 시 014/015 마이그레이션 이력과 이전 `seed_stocks.py` 구조 참고
- [ ] 미해결 종목 수동 매칭 UI — Naver 자동매칭 실패 또는 부분일치 오매칭 케이스에 대비, PreviewStep에서 사용자가 직접 종목 검색하여 매칭하는 UI 추가 검토
- [ ] Preview staging 멀티 워커 대응 — 현재 `TTLCache` (단일 워커 메모리). 멀티 워커 배포 전 DB 임시 테이블 또는 Redis로 교체 필요
- [ ] 임포트 통합 테스트 — `/import/preview`, `/import/commit` HTTP 엔드포인트 단위 테스트 (DB mock 또는 테스트 DB)
- [ ] 해외 주식 임포트 지원 — 토스 PDF `달러 거래내역` 섹션 처리 (현재 MVP skip)
- [ ] `BROKERS`(`lib/brokers.ts`) ↔ `BROKER_OPTIONS`(`ImportTradesPanel/brokers.ts`) 라벨 동기화 단위 테스트 — `findBrokerKeyByAccountBroker`가 라벨 정확 일치에 의존(예: "삼성증권"). 한쪽 표기가 변하면 매칭이 조용히 깨짐. 두 테이블 라벨 교집합을 단위 테스트로 강제
- [ ] 일괄 등록 — 모든 계좌가 미지원 증권사일 때 별도 안내 — 계좌가 0개일 때(빈 상태)와 다른 메시지(예: "등록된 계좌의 증권사가 아직 일괄 등록을 지원하지 않습니다") 노출. 현재는 비활성 카드만 보이고 별도 안내 없음

## 모바일앱 (v2.5) 잔여

- [ ] Apple Sign-in (Apple Developer Program $99/년, App Store 4.8 심사 필수)
- [ ] 푸시 알림, 생체인증(Face ID/지문), safe area/Android 백버튼/외부 링크/키보드, 강제 업데이트 메커니즘
- [ ] 앱 아이콘·스플래시·스토어 메타데이터·개인정보처리방침
- [ ] iOS 상태바 색 동기화 — @capacitor/status-bar 도입 후 다크/라이트 전환 시 status bar style 동기화

## v2 — KIS API 연동

- [ ] 한국투자증권 Open API 연동 — 거래 내역 자동 임포트, 공식 실시간 시세

## v2 — 해외 주식

- [ ] 해외 주식 검색/시세 재도입 — Yahoo Finance 등 해외 종목 provider 선정 및 장애 fallback 정의
- [ ] USD/KRW 환율 적용 — 해외 종목 평가액을 KRW 기준 총자산·미실현손익에 합산
- [ ] HHI 크로스-통화 정합성 — 해외 포지션 평가액을 KRW로 변환 후 비중 계산

## v2 — UX

- [ ] 홈 위젯 커스터마이징

## v3 — AI 분석

- [ ] 매매 패턴 분석 고도화 (감정-결과 상관관계 등)
- [ ] AI 기반 복기 제안
- [ ] 모바일 네이티브 앱 (React Native / Expo) 검토
