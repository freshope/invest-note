# 백로그

MVP 이후 구현할 작업 후보 목록.

---

## 분석 탭 성능 / 유지보수 개선

- [ ] InsightSection useMemo 적용 — AnalysisDashboard.tsx의 InsightSection 내 evaluateRules() 호출을 useMemo로 메모이제이션 (176줄 룰 배열 순회+정렬이 매 렌더마다 실행됨) (출처: /custom:review)

- [ ] 분석 API 3개(`/summary`, `/behavior`, `/suggestions`) Supabase 쿼리에 `.limit(1000)` 추가 — 거래 수 급증 시 메모리/응답 보호
- [ ] `aggregate.ts` `byTag` 계산 O(n²) 개선 — `sellTime` 기준 binary search 또는 누적 Map으로 전환
- [ ] 수수료 현황 별도 패널 노출 — BUY commission 합계, 세금 합계, 순실현손익 vs 총비용 비교 (WAC 순수가격 결정의 후속 작업)
- [ ] 테스트 보강: `period.ts` 직접 테스트 (1m/6m 구간, 월말 overflow), `computeRealizedPnL` 멀티 종목 시나리오, `byTag` FIFO 귀속 케이스

## 보안

- [ ] `/api/stocks/quote` 엔드포인트 인증 추가 — 현재 인증 없이 공개됨. `requireUser()` 추가 또는 라우트 필요성 재검토 (Naver/Yahoo Finance 프록시로 서버 IP 통한 rate-limit 우회 악용 가능) (출처: /custom:review)

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
