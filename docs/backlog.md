# 백로그

MVP 이후 구현할 작업 후보 목록.

---

## 분석 탭 성능 / 유지보수

- [ ] 분석 API 쿼리 `.limit(1000)` 가드 — 거래 수 급증 시 메모리/응답 보호
- [ ] 수수료 현황 별도 패널 — BUY commission·세금 합계, 순실현손익 vs 총비용 비교

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

## v2 — 성능 / 스케일

- [ ] trades 페이지네이션 (BE+FE 동반) — `GET /api/trades` 에 cursor/limit 도입 + records 화면 `useInfiniteQuery` 무한스크롤. records 가 현재 전량 fetch 후 메모리 group-by-date / account filter 구조라, 페이지네이션 시 그룹핑·`allTrades` (상세 패널) ·`accounts` 응답 분리까지 함께 재설계 필요. 트리거: 거래 수 분포 측정에서 첫 페인트/메모리 영향이 체감되면 도입. ticker SQL push (2026-05-03 `docs/spec-history/2026-05-03-be-simplify-trades-ticker-sql-push.md`) 로 HoldingsList 측은 이미 행 수만 fetch 중.

## v3 — AI 분석

- [ ] 매매 패턴 분석 고도화 (감정-결과 상관관계 등)
- [ ] AI 기반 복기 제안
- [ ] 모바일 네이티브 앱 (React Native / Expo) 검토
