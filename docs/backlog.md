# 백로그

MVP 이후 구현할 작업 후보 목록.

---

## 분석 탭 성능 / 유지보수 개선

- [ ] InsightSection useMemo 적용 — AnalysisDashboard.tsx의 InsightSection 내 evaluateRules() 호출을 useMemo로 메모이제이션 (176줄 룰 배열 순회+정렬이 매 렌더마다 실행됨) (출처: /custom:review)
- [ ] InsightSection 룰 일관성 — suggestionsData null 시 빈 배열 fallback으로 서버 룰과 클라이언트 룰 불일치 제거 (출처: /custom:review)
- [ ] PeriodFilterTabs compact 모드 터치 타겟 — min-h-[44px] 적용해 44px 미달 개선 (출처: /custom:review)

- [ ] 분석 API 3개(`/summary`, `/behavior`, `/suggestions`) 단일 엔드포인트 통합 또는 캐싱 레이어 추가 — 현재 동일 거래 데이터를 3번 독립 조회 (출처: /custom:review)
- [ ] 분석 API 3개(`/summary`, `/behavior`, `/suggestions`) Supabase 쿼리에 `.limit(1000)` 추가 — 거래 수 급증 시 메모리/응답 보호
- [ ] `aggregate.ts` `byTag` 계산 O(n²) 개선 — `sellTime` 기준 binary search 또는 누적 Map으로 전환
- [ ] 수수료 현황 별도 패널 노출 — BUY commission 합계, 세금 합계, 순실현손익 vs 총비용 비교 (WAC 순수가격 결정의 후속 작업)
- [ ] 테스트 보강: `period.ts` 직접 테스트 (1m/6m 구간, 월말 overflow), `computeRealizedPnL` 멀티 종목 시나리오, `byTag` FIFO 귀속 케이스

## 패널 UX 개선

- [ ] HoldingsList fetch 에러 시 토스트 연동 — 네트워크 실패/401/500 시 빈 패널 오픈 대신 토스트 에러 표시 후 패널 미오픈 (출처: /custom:review)

## 기록 탭

- [ ] 거래 카드 computed_pnl 미표시 — `records/page.tsx`가 Supabase 직접 조회로 WAC 계산 누락. `TradeList` 클라이언트 fetch 전환(`useQuery` + `tradesApi.list()`) 또는 page.tsx에서 `computeFlexibleBreakdown` 직접 호출로 해결 필요 (출처: feature/sell-registration-improve)

## 거래 손익 (persist-realized-pnl 후속)

- [ ] TOCTOU race → Postgres RPC atomic 전환 — 동시 SELL 요청이 같은 보유량 스냅샷을 보고 둘 다 통과 가능. validateMutation+write를 single RPC로 원자화 (출처: /custom:review)
- [ ] recalcGroupPnL 실패 플래그 — UPDATE 실패 시 console.error만 하고 204 반환. partial failure 시 응답 헤더 또는 로그 강화 (출처: /custom:review)
- [ ] portfolio.ts buildPositions avg_buy_price 우선 사용 — 현재 runningCost/runningQty WAC 재계산 중. trade.avg_buy_price 저장값 우선 사용으로 전환 (출처: /custom:review)
- [ ] computeFlexibleBreakdown avg_buy_price 반영 — `holdings.ts`의 종목상세 breakdown 카드가 저장된 `trade.avg_buy_price`를 사용하도록 전환. 현재는 런타임 WAC 재계산에 의존 (출처: feature/persist-realized-pnl)

## 데이터 정확성

- [ ] USD/KRW 혼합 합산 버그 — `portfolio.ts:174` US 종목 평가액을 환율 적용 없이 KRW와 직접 합산해 총평가액·미실현손익 왜곡. USD → KRW 환율 적용 필요 (출처: /custom:review)
- [ ] 자동완성 후 종목명 수정 시 stale ticker 저장 — `TradeBasicForm.tsx:249` 자동완성 선택 후 asset_name을 수동 수정하면 이전 ticker_symbol/country_code가 남아 저장됨. 수동 수정 감지 시 ticker 관련 필드 초기화 필요 (출처: /custom:review)

## 코드 품질 — 라이브러리 도입 후속

- [ ] TradeEditPanel 스키마 일관성 — `price_display: z.string()` 방식을 `TradeBasicForm`처럼 `z.number().positive()` 기반으로 통일 (출처: /custom:review)
- [ ] zod enum 중복 추출 — `strategy_type`, `emotion` enum이 TradeMetaBuyForm, TradeMetaSellForm, TradeEditPanel, validators.ts에 4중 복사. validators.ts에서 export 후 import 통일 (출처: /custom:review)
- [ ] 테스트 커버리지 추가 — validators.ts zod 스키마 (parseTradedAt, commaPositive 경계값), API 라우트 400/404 케이스, groupByDate KST 날짜 경계 (출처: /custom:review)
- [ ] StockSearchInput open 조건 — value 대신 debouncedValue 기준으로 드롭다운 열고 닫기 (캐시 반환 시 잠깐 열리는 경합 제거) (출처: /custom:review)
- [ ] StrategyEmotionFields Controller 중첩 개선 — strategy/emotion 각각을 별도 Controller로 감싸고 StrategyEmotionFields에 props 전달하는 이중 중첩 구조를 sibling Controller 배치로 교체 (출처: /custom:review)
- [ ] parseTradedAt zod transform throw 방식 검토 — transform 내 `throw new Error()`가 zod v4에서 `.issues`가 아닌 unhandled exception으로 전파될 수 있음. `ctx.addIssue()` 패턴으로 교체 검토 (출처: /custom:review)

## 보안

- [x] `/api/stocks/quote` + `/api/stocks/search` 인증 추가 완료 — requireUser() 적용 (2026-04-18)
- [ ] 자유 텍스트 필드 길이 제한 — buy_reason, sell_reason, reflection_note, improvement_note 5000자 제한 추가. API route + DB CHECK constraint (출처: /custom:review)

## MVP 잔여 — CSV 임포트

- [ ] CSV 파일 파싱 로직 구현 (현재 버튼 UI만 존재, 실제 처리 없음)
- [ ] 파싱 결과 → Supabase insert
- [ ] 임포트 포맷 정의 (컬럼 매핑)

## v2 — KIS API 연동

- [ ] 한국투자증권 Open API 연동
- [ ] 거래 내역 자동 임포트
- [ ] 공식 실시간 시세 연동 (현재: 네이버/Yahoo Finance 지연 시세)

## v2 — UX 개선

- [ ] 다크 모드
- [ ] 홈 위젯 커스터마이징
- [ ] 종목/거래 상세 패널 스택 어색함 해소 — `StockDetailPanel`과 `TradeDetailPanel`이 서로를 dynamic import로 호출하며 React 트리에 중첩 마운트되어 같은 종목/거래가 반복 누적될 수 있음 (예: A종목 → A의 거래 → 거래의 A종목 링크 → 또 A종목...). 헤더 뒤로가기는 자기 패널만 닫으므로 깊어진 만큼 N번 눌러야 원래 자리로 복귀. 1순위: 새로 열려는 대상이 부모 스택에 이미 있으면 새로 푸시하지 않고 그 단계까지 pop. 2순위: 헤더에 깊이 인디케이터 + "모두 닫기" 액션. 3순위: URL/history 연동(시스템 뒤로가기·새로고침 복원·딥링크). 관련 파일: `src/components/stocks/StockDetailPanel.tsx`, `src/components/records/TradeDetailPanel.tsx`, `src/components/common/full-screen-panel.tsx`.

## v3 — AI 분석

- [ ] 매매 패턴 분석 고도화 (감정-결과 상관관계 등)
- [ ] AI 기반 복기 제안
- [ ] 모바일 네이티브 앱 (React Native / Expo)
