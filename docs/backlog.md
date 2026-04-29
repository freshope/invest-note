# 백로그

MVP 이후 구현할 작업 후보 목록.

---

## 분석 탭 성능 / 유지보수

- [ ] 분석 API 3개(`/summary`, `/behavior`, `/suggestions`) 단일 엔드포인트 통합 또는 캐싱 — 동일 거래 데이터를 3번 조회
- [ ] 분석 API 쿼리 `.limit(1000)` 가드 — 거래 수 급증 시 메모리/응답 보호
- [ ] 수수료 현황 별도 패널 — BUY commission·세금 합계, 순실현손익 vs 총비용 비교
- [ ] 테스트 보강 — `period.ts` 경계값, `computeRealizedPnL` 멀티 종목, `byTag` FIFO 귀속
- [ ] 행동 프로파일 tempo 식 단순화 (이슈 B) — BE `profile.py:58-59`의 `(avg_holding_days / 60) * 100 - scalping_ratio * 10`은 보유기간과 스캘핑 페널티가 한 축에 혼합. 단순 평균 보유기간 점수만 사용하도록 변경 + 테스트 갱신. 같이 FE `app/src/lib/analysis/profile.ts`의 `computeProfile`은 production 미사용(테스트 전용 dead code)이라 함수·테스트를 함께 삭제하고 `BehaviorProfile`/`ProfileInputRates` 타입 정의만 보존(2026-04-28 SOT 통합 잔재 정리). 런타임 BE/FE 정합성 이슈는 이미 해소되어 추가 동기화 작업은 불필요.
- [ ] `recalc_group_pnl` 변경 row만 UPDATE 최적화 — `PNL_AFFECTING_FIELDS`에 `reasoning_tags`/`emotion` 추가로 BUY 메타 단독 변경에서도 그룹 advisory lock + `executemany`가 발동. `pnl_map` 결과를 기존 SELL row와 비교해 실제 변경된 row에만 UPDATE 발행. DB write 부하 절감.

## 프론트엔드 표시 / UI 정합성

- [ ] `TradeDetail` inline PnL → `formatPnL` 통합 — `app/src/components/records/TradeDetail.tsx`의 `{summary.pnl >= 0 ? "+" : ""}{summary.pnl.toLocaleString("ko-KR")}원` 인라인 표현이 분석 탭의 `formatPnL` 헬퍼와 동일 로직. 점진 통합으로 부호/포맷 단일 SOT화. 부수로 `Math.round(-0)` → "-0원" 잠재 버그도 동시 해소.
- [ ] PnL 색상 클래스 토큰화 — `text-[var(--rise)]` / `text-[var(--fall)]` raw string이 26+ 위치에 반복. `app/src/lib/constants/colors.ts`로 토큰화하여 색 변경 시 단일 지점 수정. 기존 `:root` CSS 변수 정의는 그대로 두고 클래스 문자열만 상수화.
- [ ] `FullScreenPanelFooter` 컴포넌트 추출 — `<div className="sticky bottom-0 bg-background px-5 pt-3 pb-4" style={{ paddingBottom: "calc(1rem + env(safe-area-inset-bottom))" }}>` 패턴이 코드베이스 9곳 중복 (`TradeBasicForm` / `TradeMetaBuyForm` / `TradeMetaSellForm` / `TradeEditPanel` / `AccountFormPanel` / `ImportTradesPanel`의 4 step). `TradeDetail`은 `flex-none` 변형으로 같은 safe-area 인라인 스타일 사용. magic 인라인 `calc(1rem + env(safe-area-inset-bottom))`가 9곳에 동일 복붙되어 한 곳만 바꾸면 어긋날 위험. `@/components/base/FullScreenPanel`에 `FullScreenPanelFooter`(optional `sticky` prop, `className` 합성) 추가 후 9곳 일괄 마이그레이션.

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
