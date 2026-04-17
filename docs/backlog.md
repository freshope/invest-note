# 백로그

MVP 이후 구현할 작업 후보 목록.

---

## 분석 탭 성능 / 유지보수 개선

- [ ] 분석 API 3개(`/summary`, `/behavior`, `/suggestions`) Supabase 쿼리에 `.limit(1000)` 추가 — 거래 수 급증 시 메모리/응답 보호
- [ ] `aggregate.ts` `byTag` 계산 O(n²) 개선 — `sellTime` 기준 binary search 또는 누적 Map으로 전환
- [ ] 수수료 현황 별도 패널 노출 — BUY commission 합계, 세금 합계, 순실현손익 vs 총비용 비교 (WAC 순수가격 결정의 후속 작업)
- [ ] 테스트 보강: `period.ts` 직접 테스트 (1m/6m 구간, 월말 overflow), `computeRealizedPnL` 멀티 종목 시나리오, `byTag` FIFO 귀속 케이스

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

## v3 — AI 분석

- [ ] 매매 패턴 분석 고도화 (감정-결과 상관관계 등)
- [ ] AI 기반 복기 제안
- [ ] 모바일 네이티브 앱 (React Native / Expo)
