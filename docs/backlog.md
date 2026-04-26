# 백로그

MVP 이후 구현할 작업 후보 목록.

---

## 분석 탭 성능 / 유지보수

- [ ] InsightSection `useMemo` 적용 — `evaluateRules()` 호출 메모이제이션 (176줄 룰 배열이 매 렌더마다 실행)
- [ ] InsightSection 룰 일관성 — `suggestionsData` null 시 빈 배열 fallback으로 서버/클라이언트 룰 불일치 제거
- [ ] 분석 API 3개(`/summary`, `/behavior`, `/suggestions`) 단일 엔드포인트 통합 또는 캐싱 — 동일 거래 데이터를 3번 조회
- [ ] 분석 API 쿼리 `.limit(1000)` 가드 — 거래 수 급증 시 메모리/응답 보호
- [ ] `aggregate.ts` `byTag` O(n²) → binary search / 누적 Map 개선
- [ ] 수수료 현황 별도 패널 — BUY commission·세금 합계, 순실현손익 vs 총비용 비교
- [ ] 테스트 보강 — `period.ts` 경계값, `computeRealizedPnL` 멀티 종목, `byTag` FIFO 귀속

## 거래 손익 정합성

- [x] TOCTOU race → pg_advisory_xact_lock 원자화 완료 (feature/toctou-advisory-lock, 2026-04-24)
- [x] advisory lock timeout — `acquire_trade_group_lock` 내부에 `SET LOCAL lock_timeout = '2s'` 추가, 운영 hang 방어 (feature/advisory-lock-timeout, 2026-04-25)
- [ ] 동시성 통합 테스트 — testcontainers-python + asyncpg + asyncio.gather 기반 실 Postgres race 재현 (현재 FakeConnection만으로는 실제 race 미검증)

## 데이터 정확성

- [ ] USD/KRW 혼합 합산 — `portfolio.ts` US 종목 평가액을 환율 적용 없이 KRW와 합산해 총평가액·미실현손익 왜곡. USD→KRW 환율 적용 필요
- [ ] HHI 크로스-통화 왜곡 — `concentration.py` 가 USD 포지션 평가액을 환율 변환 없이 합산. USD→KRW 변환 후 비중 계산
- [x] 자동완성 후 종목명 수정 시 stale ticker 저장 — `TradeBasicForm.tsx` 자동완성 후 asset_name 수동 수정하면 이전 ticker_symbol/country_code 유지. 수동 수정 감지 시 ticker 필드 초기화
- [x] 미래 거래 묵시 필터링 명시화 — 신규 등록은 미래 거래를 차단하지만, 기존/외부 유입 데이터 기준으로 `period.py filter_by_period` 가 "all" 기간에도 `to_ts = now`로 미래 거래를 제외하는 정책 문서화 완료 (`docs/decisions.md`, 2026-04-26)

## 코드 품질

- [x] fmtCompact 억 범위 콤마 — 1,000억 이상에서 `(n / 100_000_000).toFixed(1)` 결과에 콤마 없음 ("1000.0억"). 만 범위와 동일하게 `toLocaleString` 적용 필요
- [x] TradeEditPanel 스키마 일관성 — `price_display: z.string()` → `z.number().positive()` 기반으로 `TradeBasicForm`과 통일 (feature/trade-edit-schema-alignment, 2026-04-25)
- [x] StrategyEmotionFields Controller 중첩 — strategy/emotion 이중 Controller → sibling Controller 배치 완료 (feature/fix-strategy-emotion-controller-nesting, 2026-04-26)
- [ ] 자유 텍스트 필드 길이 제한 — buy_reason, sell_reason, reflection_note, improvement_note 5000자 제한 (FastAPI validation + DB CHECK)

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

## v2 — UX

- [x] 다크 모드 (feature/theme-toggle, 2026-04-25)
- [ ] 홈 위젯 커스터마이징

## v3 — AI 분석

- [ ] 매매 패턴 분석 고도화 (감정-결과 상관관계 등)
- [ ] AI 기반 복기 제안
- [ ] 모바일 네이티브 앱 (React Native / Expo) 검토
