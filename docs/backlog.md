# 백로그

MVP 이후 구현할 작업 후보 목록.

---

## UI 코드 정리

- [ ] `BreakdownRow` 컴포넌트 추출 — `TradeMetaSellForm.tsx`와 `TradeEditPanel.tsx`에 동일 컴포넌트가 중복 정의됨. `trade-display.tsx` 또는 별도 파일로 이동.

## 분석 탭 성능 / 유지보수

- [ ] InsightSection `useMemo` 적용 — `evaluateRules()` 호출 메모이제이션 (176줄 룰 배열이 매 렌더마다 실행)
- [ ] InsightSection 룰 일관성 — `suggestionsData` null 시 빈 배열 fallback으로 서버/클라이언트 룰 불일치 제거
- [ ] 분석 API 3개(`/summary`, `/behavior`, `/suggestions`) 단일 엔드포인트 통합 또는 캐싱 — 동일 거래 데이터를 3번 조회
- [ ] 분석 API 쿼리 `.limit(1000)` 가드 — 거래 수 급증 시 메모리/응답 보호
- [ ] `compute_holding_days_map` 정리 — `trades.holding_days` 저장값 전환 후 분석 라우터/프로필/집계 인터페이스를 저장값 직접 사용으로 단순화하고 legacy FIFO fallback 제거 여부 결정
- [ ] `aggregate.ts` `byTag` O(n²) → binary search / 누적 Map 개선
- [ ] 수수료 현황 별도 패널 — BUY commission·세금 합계, 순실현손익 vs 총비용 비교
- [ ] 테스트 보강 — `period.ts` 경계값, `computeRealizedPnL` 멀티 종목, `byTag` FIFO 귀속

## MVP 잔여 — CSV 임포트

- [ ] 임포트 포맷 정의 (컬럼 매핑)
- [ ] CSV 파일 파싱 로직 (현재 `CsvUploadButton` UI만)
- [ ] 파싱 결과 → DB insert

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
