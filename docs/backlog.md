# 백로그

MVP 이후 구현할 작업 후보 목록.

---

## 분석 탭 성능 / 유지보수

- [ ] 분석 API 쿼리 `.limit(1000)` 가드 — 거래 수 급증 시 메모리/응답 보호
- [ ] 수수료 현황 별도 패널 — BUY commission·세금 합계, 순실현손익 vs 총비용 비교

## FE simplify (Round 1 이후 deferred — 2026-04-30 `/simplify` 결과)

Round 1 (`docs/spec-history/...`) 에서 처리된 6 개 외에 도출된 후속 항목. 위험도/가치 평가 후 Round 2+ 에서 분할 처리.

### 컴포넌트 추출 (중복 제거)

- [ ] `ConfirmDeleteDialog` 통합 — `DeleteTradeDialog` ↔ `DeleteAccountDialog` 거의 동일 패턴(Dialog 셸 + pending state + 삭제 버튼 + 에러). title/description/onConfirm props 로 합치고 호출부에서 mutation/invalidate 주입
- [ ] `TradeHeaderCard` 추출 — `TradeDetail` ↔ `TradeEditPanel` 종목 헤더 카드 마크업 ~80 줄 중복(파스텔 액센트 + 종목명 + BUY/SELL 배지 + 마켓 배지 + 총액)
- [ ] `ToggleChipGrid` 추출 — `StrategyEmotionFields`, `TradeEditPanel` 의 `STRATEGIES`/`EMOTIONS`/`REASONING_TAGS` 토글 그리드 6 곳 중복. options/value/onChange/columns/multi props
- [ ] `AccountChip` 추출 — `BrokerLogo + 계좌명` inline-flex 7 곳 (TradeDetail / TradeEditPanel / TradeBasicForm Select / TradeCard / AccountCard / AccountFilter)
- [ ] `TradeTypeBadge` 추출 — 매수/매도 라벨 + PNL_COLORS 인라인 분기 3 곳 (TradeDetail / TradeCard / TradeEditPanel). `TRADE_TYPE_LABELS: Record<TradeType, string>` 상수 + bgSoft/text 통합
- [ ] `BreakdownList<T>` 통합 — `EmotionBreakdown` / `StrategyBreakdown` / `ReasoningBreakdown` 동일 구조 (정렬·라벨·count + PnLLine·WinRateBar). getKey/getLabel/getStats/isUntagged 콜백 받는 일반 컴포넌트
- [ ] `ProgressTrack` 추출 — `WinRateBar` / `WeightBar` / `QualityBar` 의 `h-1.5 rounded-full bg-muted overflow-hidden` 트랙 동일 마크업. `pickRateColor(rate)` 임계치 헬퍼 함께 추출
- [ ] `EmptyCard` 일반화 — `home/EmptyState` 를 일반화하거나 `shared/EmptyCard` 신규. `TradeList` / `AccountList` / `StockDetail` 의 "데이터 없음" 카드 패턴 통합
- [ ] `Card` primitive 30+ 곳 — `rounded-2xl bg-muted/60` 카드 셸. padding sm/md/lg 변종 흡수. 대규모 변경이라 디자인 토큰화 가치 검증 필요

### 상태/구조 리팩터

- [ ] `DetailPanelProvider` 5 중 상태 단순화 — open/payload/key/payloadRef/closeTimer 를 trade·stock 각 5 개씩 관리. 슬라이드 lifecycle 을 `FullScreenPanel` 내부 `useStaggeredPanel(payload)` 훅으로 추출, Provider 는 setPayload 만
- [ ] `StrategyEmotionFields` 강제 분리 사용 정리 — `TradeMetaBuyForm` 에서 같은 컴포넌트를 `hideEmotion`/`hideStrategy` 로 두 번 렌더하고 빈 콜백 채움. `StrategyField` / `EmotionField` 분리 또는 `ToggleChipGrid` 로 일원화
- [ ] `HoldingCard` pressing state CSS 화 (재시도) — Round 1 에서 시도했으나 inner note 의 `onPointerDown` `stopPropagation` 으로 outer pressing 을 차단하는 원본 UX (note 탭 시 outer 카드 scale 안 함) 가 CSS `:active` 로는 보존 불가능 (`:active` 는 stopPropagation 미준수). 해결안: ① `data-pressing` 속성 + JS 토글 + CSS attr selector 로 selective 적용, ② note 영역만 별도 stop layer 두기, ③ TradeCard 처럼 button 으로 변경하고 nested 클릭 영역을 별도 button 으로 분리, ④ 원본 UX 가 의도적이지 않다면 그냥 CSS active 채택. 디자인 검증 필요해 backlog 로

### useEffect 안티패턴

- [ ] `TradeBasicForm` commission/tax effect 동기화 제거 — input onChange 에서 한꺼번에 setValue, 사용자 수동 수정 보호 플래그 검토
- [ ] `TradeBasicForm` localStorage 복원 effect → `defaultValues` 함수 — 마운트 직전 동기 초기화, eslint-disable 제거
- [ ] `TradeFormPanel` 이중 reset effect — `<TradeFormPanel key={open ? "open" : "closed"} />` 로 부모에서 key 교체 또는 `open` 일 때만 마운트
- [ ] `ImportTradesPanel` setTimeout reset — 부모 key 교체 패턴으로 치환
- [ ] `useEnsureValidAccount` effect-setState — render 중 직접 호출(공식 store rule 패턴) 또는 `effectiveAccountId` derive

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
