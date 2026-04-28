# 백로그

MVP 이후 구현할 작업 후보 목록.

---

## 분석 탭 성능 / 유지보수

- [ ] InsightSection `useMemo` 적용 — `evaluateRules()` 호출 메모이제이션 (176줄 룰 배열이 매 렌더마다 실행)
- [ ] InsightSection 룰 일관성 — `suggestionsData` null 시 빈 배열 fallback으로 서버/클라이언트 룰 불일치 제거
- [ ] 분석 API 3개(`/summary`, `/behavior`, `/suggestions`) 단일 엔드포인트 통합 또는 캐싱 — 동일 거래 데이터를 3번 조회
- [ ] 분석 API 쿼리 `.limit(1000)` 가드 — 거래 수 급증 시 메모리/응답 보호
- [ ] `compute_holding_days_map` 정리 — `trades.holding_days` 저장값 전환 후 분석 라우터/프로필/집계 인터페이스를 저장값 직접 사용으로 단순화하고 legacy FIFO fallback 제거 여부 결정
- [ ] `aggregate.ts` `byTag` O(n²) → binary search / 누적 Map 개선
- [ ] 수수료 현황 별도 패널 — BUY commission·세금 합계, 순실현손익 vs 총비용 비교
- [ ] 테스트 보강 — `period.ts` 경계값, `computeRealizedPnL` 멀티 종목, `byTag` FIFO 귀속
- [ ] PnL 표시 패턴 통합 — `EmotionBreakdown`/`StrategyBreakdown`/`ReasoningBreakdown`의 인라인 양수/음수 색상+부호+`fmt` 패턴을 `PnLLine` 공용 컴포넌트로 추출하고 `format.ts`에 `formatPnL` 헬퍼 추가
- [ ] 행동 프로파일 tempo 식 단순화 (이슈 B) — 현 식은 `(avg_holding_days / 60) * 100 - scalping_ratio * 10`로 보유기간과 스캘핑 페널티가 한 축에 혼합. 단순 평균 보유기간 점수만 사용하도록 변경 (`profile.py` / `profile.ts` 동시 수정, 테스트 갱신). 백엔드는 actual 기준, 프론트엔드는 planned 기준이라 결과도 어긋나는 정합성 문제도 함께 해소.
- [ ] `recalc_group_pnl` 변경 row만 UPDATE 최적화 — `PNL_AFFECTING_FIELDS`에 `reasoning_tags`/`emotion` 추가로 BUY 메타 단독 변경에서도 그룹 advisory lock + `executemany`가 발동. `pnl_map` 결과를 기존 SELL row와 비교해 실제 변경된 row에만 UPDATE 발행. DB write 부하 절감.
- [ ] SELL의 `result` 자동 산출 일관 처리 — 현재 `result`는 PnL 부호로 자동 결정되어 `summary.result`로 UI에 채워지나 SELL row에는 저장되지 않음. `strategy_type`/`reasoning_tags`/`emotion`과 동일하게 mutation 시점에 SELL row에 저장 + `PNL_AFFECTING_FIELDS` 확장 + UI 입력 차단으로 일관 처리. 분석 라우터의 `_derive_result` 의존도 함께 정리.
- [ ] 분석 임계값 단일 SOT (이슈 C) — `STRATEGY_THRESHOLDS`(SCALPING_MAX_DAYS=1, SWING_MAX_DAYS=30), `HHI_HIGH=0.5`, `HHI_MID=0.25`, `TOP1_WEIGHT_HIGH=0.4`가 frontend 상수와 backend 하드코딩(`strategy_adherence.py`, `concentration.py`)으로 이중화. 백엔드는 `analysis/thresholds.py` 모듈로 추출하고 두 파일이 import하도록, frontend 상수 위치는 그대로 두되 `docs/decisions.md`에 "임계값 변경 시 양쪽 함께 수정" 명시.
- [ ] 라우터 단위 테스트 사전 실패 2건 — `tests/test_analysis.py::TestAnalysisSummary::test_buy_and_sell`(`strategyAdherenceRate`가 100 기대인데 SELL `holding_days` 미지정으로 0), `TestAnalysisBehavior::test_holding_period_dist`(`holdingPeriodDist`가 비어 있음). develop 기준에서도 실패하므로 본 작업과 무관. 테스트 fixture에 `holding_days`를 채워주거나 라우터가 fallback 계산하도록 결정 필요.

## 운영 / 어드민 도구

- [ ] PnL 저장값 검증 엔드포인트 (이슈 E) — `/api/admin/verify-pnl` 신설. SELL의 저장된 `profit_loss`/`avg_buy_price`/`holding_days`/`strategy_type`/`reasoning_tags`/`emotion`을 `compute_group_pnl()`로 재계산해 차이 검출. 사용자 단위 batch + 차이 리포트 + (옵션) 자동 보정. 권한은 admin scope. DB 직접 수정·마이그레이션 누락·mutation 경로 우회 시 분석 탭과 거래 기록 합계 불일치를 잡기 위함.

## 거래내역서 임포트 — 후속 과제

- [ ] kr_stocks 갱신 자동화 — seed 스크립트를 주기적으로 실행하는 cron 또는 KIS API 연동 시 통합 (현재 수동 실행)
- [ ] Preview staging 멀티 워커 대응 — 현재 `TTLCache` (단일 워커 메모리). 멀티 워커 배포 전 DB 임시 테이블 또는 Redis로 교체 필요
- [ ] 임포트 통합 테스트 — `/import/preview`, `/import/commit` HTTP 엔드포인트 단위 테스트 (DB mock 또는 테스트 DB)
- [ ] 해외 주식 임포트 지원 — 토스 PDF `달러 거래내역` 섹션 처리 (현재 MVP skip)

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
