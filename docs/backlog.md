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

> Round 4 후속 (2026-05-03): `ImportTradesPanel/AccountStep` 자동 단일 계좌 선택 effect 처리 완료 — 부모(`ImportTradesPanel`) 의 `useState` lazy initializer 로 마운트 시점에 한 번만 결정하는 헬퍼 (`getInitialSelectedAccountId`) 추출.

### 성능

> Round 5 (2026-05-03) 에서 6 개 항목 처리 완료 — `docs/spec-history/2026-05-03-fe-simplify-round5-performance.md` 참고. recharts dynamic import / `TradeBasicForm` `useWatch` / `TradeCard`·`HoldingCard` `React.memo` + 부모 콜백 안정화 / 무거운 쿼리 staleTime 명시 (analysis 5min, portfolio 2min) / `holding` staleTime 10초 / `groupByDate` 정렬 명시. backlog 메모의 `refetchOnWindowFocus false 검토` 는 [decisions.md 2026-05-03](decisions.md) 으로 **글로벌 default 유지 확정** (per-query staleTime 만 조정).

> 2026-05-03 cleanup-trio: `accountsApi.list` ↔ `portfolioApi.summary` 캐시 키 통일은 `queryKeys.accounts = ["portfolio", "accounts"]` 로 트리 흡수하는 방식으로 처리 — `queryKeys.portfolio` invalidate 한 번이 prefix 매칭으로 accounts/summary 모두 무효화. selector 대체(snapshots[].account 재사용) 는 `trade_count` enrich 누락 때문에 BE 변경 없이는 불가, 따로 spec 필요 시 BE 협조.

> 2026-05-03 ticker SQL push 처리됨: BE `list_trades_with_account` 가 ticker/country WHERE 를 SQL 로 push → HoldingsList(`tradesApi.list({ ticker, country })`) 가 더 이상 사용자 전체 trades 를 가져오지 않음. records 화면 무한스크롤은 별개 — 거래 수 분포 검증 후 결정.

> 2026-05-03 `tradesApi.list()` 페이지네이션 항목은 **v2 — 성능 / 스케일** 로 이관 (BE 페이지네이션 항목과 동반).

### 타입/구조 (선택적)

> Round 6 (2026-05-03) 에서 2 개 항목 모두 처리 완료 — `docs/spec-history/2026-05-03-fe-simplify-round6-types.md` 참고. `AccountFilter` 는 `string | null` 채택 (`ACCOUNT_FILTER_ALL` 상수 제거), `StockSearchInput prevQuery` 는 [decisions.md 2026-05-03](decisions.md) 으로 **변경 미진행 확정** (React 공식 권장 패턴 + 사이클 효율성 우위).

## BE simplify (Round 1 이후 deferred — 2026-05-01 `/simplify` 결과)

Round 1 (`docs/spec-history/2026-05-01-be-simplify-round1-quick-wins.md`) 에서 처리된 3 개 (`model_copy(update=)` / `dataclasses.replace` / `sort_by_traded_at` 통합) + Round 2 (`docs/spec-history/2026-05-03-be-simplify-round2-response-mapping.md`) 에서 처리된 4 개 + Round 3 (`docs/spec-history/2026-05-03-be-simplify-round3-hot-path.md`) 에서 처리된 4 개 + Round 4 (`docs/spec-history/2026-05-03-be-simplify-round4-domain-cleanup.md`) 에서 처리된 2 개 + Round 5 (`docs/spec-history/2026-05-03-be-simplify-round5-reuse.md`) 에서 처리된 5 개 외에 도출된 후속 항목.

> Round 2 (2026-05-03) 에서 응답 매핑 카테고리 4 개 처리 완료 (`asdict` spread / `account_row_to_dict` UUID 흡수 / `patch_account` 추출 / `create_trade` `model_dump` spread). `_trade_with_account_dict` 스키마화는 [decisions.md 2026-05-03](decisions.md) 으로 **미진행 확정**.

> Round 3 (2026-05-03) 에서 효율/핫패스 4 개 처리 완료 (`httpx.AsyncClient` lifespan 공유 / broker parser `run_in_threadpool` / `import_preview` date 범위 좁히기 / `delete_account` round-trip 통합). `routers/analysis` period SQL push 는 [decisions.md 2026-05-03](decisions.md) 으로 **미진행 확정** (`all_trades` 가 의도적 unfiltered 입력, SQL push 가 1→2 round-trip net negative).

> Round 4 (2026-05-03) 에서 도메인 정리 2 개 처리 완료 (`compute_holding_summary` 를 `walk_trades` terminal state 기반으로 재구성 / `build_positions` 119 줄을 `_build_lot_map` + `_lot_to_positions` 헬퍼로 분리).

> Round 5 (2026-05-03) 에서 재사용/잔여 5 개 처리 완료 (`accounts_repo.list_accounts` 헬퍼 + 라우터 3곳 SELECT 통합 / `trade_import` signature 4함수 본문 헬퍼화 + `parse_kst_date` 로 trades.py KST 파싱 흡수 / `_first_bucket_label` 일반 헬퍼 + `Counter` dist 빌드 / `_decimal_to_*` 3 validator 공통 헬퍼 추출 / `EMOTION_UNTAGGED`·`TAG_UNTAGGED` Literal 타입 명시 + 응답 스키마 좁힘). `external/quotes._parse_*` 통합은 [decisions.md 2026-05-03](decisions.md) 으로 **미진행 확정** (Naver realtime/basic endpoint 응답 구조 비대칭).

### 효율 / 핫패스

> 2026-05-03 ticker SQL push: `list_trades_with_account` 에 `ticker`/`country` keyword-only 인자 추가, 라우터 Python 후처리 제거. HoldingsList 호출이 종목 행만 fetch.

> 2026-05-03 `GET /api/trades` 페이지네이션 항목은 **v2 — 성능 / 스케일** 로 이관 (FE 페이지네이션 항목과 동반).

### 재사용 / 잔여

> 2026-05-03 cleanup-trio: `SellBreakdown.is_manual_input` 폐기 처리 완료 — BE dataclass/응답 스키마/FE 타입/UI 분기/단위 테스트 동기 제거. "진짜 manual input 케이스" 명세 안 됨이 확인되어 재도입 트리거 없으면 다시 추가하지 않음.

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

## v2 — 성능 / 스케일

- [ ] trades 페이지네이션 (BE+FE 동반) — `GET /api/trades` 에 cursor/limit 도입 + records 화면 `useInfiniteQuery` 무한스크롤. records 가 현재 전량 fetch 후 메모리 group-by-date / account filter 구조라, 페이지네이션 시 그룹핑·`allTrades` (상세 패널) ·`accounts` 응답 분리까지 함께 재설계 필요. 트리거: 거래 수 분포 측정에서 첫 페인트/메모리 영향이 체감되면 도입. ticker SQL push (2026-05-03 `docs/spec-history/2026-05-03-be-simplify-trades-ticker-sql-push.md`) 로 HoldingsList 측은 이미 행 수만 fetch 중.

## v3 — AI 분석

- [ ] 매매 패턴 분석 고도화 (감정-결과 상관관계 등)
- [ ] AI 기반 복기 제안
- [ ] 모바일 네이티브 앱 (React Native / Expo) 검토
