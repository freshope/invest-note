# 백로그

MVP 이후 구현할 작업 후보 목록.

---

## 분석 탭 성능 / 유지보수

- [ ] 분석 대시보드 시세 분리 (옵션 B 동일 패턴) — `/analysis/dashboard` 도 요청 안에서 시세를 동기 fetch(concentration 계산용, `fetch_quotes_by_keys`)한다. 2026-05-27 `/portfolio/summary` 분리(`docs/decisions.md` 참고)와 동일하게 `withQuotes` opt-in + FE overlay 적용 검토. 단 concentration(HHI/top3/비중)은 시세 없으면 `cost_basis` fallback 이라 FE 로 옮기려면 concentration 계산까지 FE 중복이 필요 → 표면적이 summary 보다 큼. 트리거: summary 분리 효과 확인 후, 또는 분석 탭 응답 지연 체감 시.
- [ ] 분석 API 쿼리 `.limit(1000)` 가드 — 거래 수 급증 시 메모리/응답 보호
- [ ] 수수료 현황 별도 패널 — BUY commission·세금 합계, 순실현손익 vs 총비용 비교
- [ ] `_rule_high_winrate` 신뢰도 게이트 재검토 — 2026-05-20 `result_input_rate` 게이트 제거 후 현재 `sell_trades >= MIN_HIGH_WINRATE_SELL` + `win_rate >= WIN_THRESHOLD` 만으로 트리거. 실 데이터에서 인사이트가 과도하게 트리거되면 별도 신뢰도 메트릭(SELL 매칭률 등) 도입 검토. 트리거: 사용자 피드백 또는 인사이트 노출 빈도 모니터링에서 노이즈 체감.

## 운영 / 어드민 도구

- [ ] **미사용 admin 라우터 + ADMIN_TOKEN 인프라 제거** — 현재 모든 seed 스케줄은 Coolify 에서 CLI(`python -m invest_note_api.services.{stock_seed,nps_seed}`)로 돌고, `POST /admin/seed/{stocks,nps,daily-prices}`·`/admin/reconcile/nps` HTTP 트리거는 실제로 호출되지 않는다(`daily-prices` 는 스케줄 미등록·비활성 옵션). 작업: `routers/admin.py` 삭제 + `main.py` 의 `include_router(admin.router)` 제거 + `auth/admin.py`(`require_admin_token`) 제거 + `config.py` `admin_token`·env `ADMIN_TOKEN` 정리 + 관련 테스트 폐기. **단 `services/daily_price_seed.py` 의 `seed_daily_prices`(pre-warm) 함수는 보존** — 자산 추이 콜드스타트 첫-오픈 지연을 더 줄이고 싶을 때 살릴 여지(현재 비활성, `docs/decisions.md` 2026-06-04 cron 우선순위 하향 참고). 트리거: 별도 관리자 페이지를 만들 때 그에 맞는 엔드포인트로 재설계하며 함께 정리.
- [ ] PnL 저장값 검증 엔드포인트 (이슈 E) — `/admin/verify-pnl` 신설. SELL의 저장된 `profit_loss`/`avg_buy_price`/`holding_days`/`strategy_type`/`reasoning_tags`/`emotion`을 `compute_group_pnl()`로 재계산해 차이 검출. 사용자 단위 batch + 차이 리포트 + (옵션) 자동 보정. 권한은 admin scope. DB 직접 수정·마이그레이션 누락·mutation 경로 우회 시 분석 탭과 거래 기록 합계 불일치를 잡기 위함.

## 배포 / 인프라

- [ ] internal 패키지명 일관화 검토 — `fe/package.json` `"name": "invest-note"` 과 `be/pyproject.toml` `name = "invest-note-api"` 의 BE/FE 명시화 (`invest-note-fe`, `invest-note-be` 등) 검토. 폴더명과 일관성 vs 변경 비용(import 경로, 빌드 설정, 외부 참조) 비교 후 결정.
- [ ] user-scoped 테이블 신규 추가 시 `on delete cascade` 가드 — `auth.users` 삭제 시 cascade 누락된 FK가 있으면 탈퇴가 FK 위반으로 실패. 향후 새 user_id 컬럼을 가진 테이블을 추가하는 마이그레이션은 PR 리뷰 시 cascade 옵션 확인을 체크리스트로 명시. 또는 통합 테스트로 데모 사용자 삭제→재시드 시나리오를 자동화 검토.

## API 라우터 prefix 마이그레이션

- [ ] BE legacy `/api/*` alias 제거 (sunset) — 2026-05-21 `docs/issue-history/2026-05-21-be-dual-api-prefix.md` 에서 신/구 prefix 동시 지원 등록 (legacy 는 `include_in_schema=False`). FE/웹은 이미 새 경로 전환. 강제 업데이트 메커니즘은 2026-05-26 머지(`docs/issue-history/2026-05-26-force-update.md`). **남은 선행 조건**: 양 스토어 승인 + 옛 번들 사용자가 새 번들로 모두 이동 + 운영 로그에서 `/api/*` 트래픽이 충분히 줄어든 시점. 작업: `be/src/invest_note_api/main.py` 의 legacy `include_router` 루프 제거 + `tests/test_legacy_api_prefix.py` 폐기.
- [ ] `be/README.md` curl 예시 새 경로 갱신 — README 의 `http://localhost:8000/api/{accounts,trades,portfolio,stocks,analysis}` curl 예시 약 20곳을 신 경로로 일괄 갱신. 코스메틱.

## 거래내역서 임포트 — 후속 과제

- [ ] **종목 검색 provider db 복귀 + import/NPS stale 추적** (2026-06-03 Naver 임시 복귀, `docs/decisions.md` 참고) — data.go.kr 게이트웨이(~50% 성공률) 안정성 모니터링 후 `STOCK_SEARCH_PROVIDER=db` 로 복귀(코드 변경 없이 env 한 줄). **잔여 리스크:** 검색만 토글했으므로 seed 를 장기 중단하면 거래 import 매칭(`ticker_resolver.lookup_by_names`)·NPS(`stocks_repo.search`)·marcap 이 stale 로컬 stocks 에 의존해 조용히 낡음. 트리거: ① seed 게이트웨이 성공률 안정화 확인 시 db 복귀, 또는 ② import 매칭률 저하/NPS·시총 stale 체감 시 seed 재개 우선순위 상향.
- [ ] 공급자 env 토글 제외 잔존 — data.go.kr 고정 의존 (2026-06-07 env registry 도입, `docs/decisions.md` 참고) — 교차검증은 2026-06-07 KIS 트랙 1 에서 `CROSSVALIDATE_PROVIDER`(naver|kis) 토글로 **해소**. `update_marcap`(data.go.kr)만 고정 단계로 잔존 — KIS 는 bulk 시총 API 가 없어 종목별 호출 필요. 기본 유량 18건/초 기준 전종목 4,300콜≈4분 심야 cron 으로 **가능은 해짐**(2026-06-07 재평가)이나, data.go.kr 는 bulk 2콜로 같은 일을 하고 시총은 하루 stale 무해(실패 시 기존값 보존)라 평시 전환은 비권장 — **data.go.kr 장애 장기화 시 대체선**으로만(신규 fetcher 구현 필요). ⚠️ `CROSSVALIDATE_PROVIDER=kis` 전환 시 KONEX 종목이 대조 없이 "검증됨"으로 박제됨(마스터 파일에 KONEX 없음, `naver_checked_at` 공유 컬럼) — 전환 전 인지 필요. 트리거: data.go.kr 시총 경로 장애 장기화 시 marcap 대체 재검토.
- [ ] 미해결 종목 수동 매칭 UI — Naver 자동매칭 실패 또는 부분일치 오매칭 케이스에 대비, PreviewStep에서 사용자가 직접 종목 검색하여 매칭하는 UI 추가 검토
- [ ] Preview staging 멀티 워커 대응 — 현재 `TTLCache` (단일 워커 메모리). 멀티 워커 배포 전 DB 임시 테이블 또는 Redis로 교체 필요
- [ ] 임포트 통합 테스트 — `/import/preview`, `/import/commit` HTTP 엔드포인트 단위 테스트 (DB mock 또는 테스트 DB)
- [ ] import preview 그룹 검증 중복 제거 (2026-05-26 API 성능 분석 #5) — `import_preview` 가 `account_id` 를 받으면 `_validate_import_groups` 가 commit 과 동일한 그룹별 `list_trades_in_group` + oversell 검증을 한 번 더 수행한다(`routers/trades.py` 의 preview 경로). 그룹 수가 많은 파일일수록 preview 에서 N회 추가 쿼리. 작업: preview 의 dedup 용 date-range fetch 결과를 재활용하거나, 정합성(oversell) 검증을 commit 단계로 일원화하고 preview 는 참고용 카운트만 노출. 주의: preview 단계에서 사용자에게 위반을 미리 보여주는 UX 가치가 있으므로 제거 전 FE 노출 동작 확인 필요.
- [ ] 해외 주식 임포트 지원 — 토스 PDF `달러 거래내역` 섹션 처리 (현재 MVP skip)
- [ ] `BROKERS`(`lib/brokers.ts`) ↔ `BROKER_OPTIONS`(`ImportTradesPanel/brokers.ts`) 라벨 동기화 단위 테스트 — `findBrokerKeyByAccountBroker`가 라벨 정확 일치에 의존(예: "삼성증권"). 한쪽 표기가 변하면 매칭이 조용히 깨짐. 두 테이블 라벨 교집합을 단위 테스트로 강제
- [ ] 일괄 등록 — 모든 계좌가 미지원 증권사일 때 별도 안내 — 계좌가 0개일 때(빈 상태)와 다른 메시지(예: "등록된 계좌의 증권사가 아직 일괄 등록을 지원하지 않습니다") 노출. 현재는 비활성 카드에 "일괄 등록 미지원" 라벨만 표시되고 전체 안내 메시지는 없음(`AccountStep.tsx`)
- [ ] 머지 갱신 범위 확장 재검토 — 현재 머지는 `commission`/`tax`/`traded_at` 만 update, `market_type`/`country_code`/`exchange` 는 사용자 분류를 우선해 **보존**(`docs/decisions.md` 2026-05-18 참고). 다음 트리거 발생 시 재검토: ① 사용자가 거래내역서로 분류 자동 보정을 명시적으로 원함, ② 증권사 파서가 사용자 수동 분류보다 더 정확한 케이스가 다수 보고됨. 재검토 시 `update_trade_from_import` 화이트리스트와 `build_merge_patch` 비교 필드를 함께 확장
- [ ] 다운로드 가이드 콘텐츠 검수 — `fe/src/components/records/ImportTradesPanel/brokers.ts` 의 `downloadGuide` 는 AI 1차 초안(`TODO` 주석 표시). 삼성증권 mPOP/토스 앱과 실제 화면 대조 후 단계 텍스트·`helpUrl` 수정. 증권사 앱 UI 개편 시 깨질 수 있어 분기별 점검 또는 사용자 신고 트리거 시 갱신. 캡처 이미지 단계 안내가 더 효과적이라 판단되면 별도 spec 으로 보강

## 자산 추이 페이지 — 운영 잔여 (페이지 자체는 2026-06-04 출시)

- [ ] **일별 종가 자동 적재 + 2년 prune 운영** — 현재 종가 백필은 페이지 진입 시 동기 실행(종목별 watermark 증분), 전체 사전적재는 `POST /admin/seed/daily-prices`(수동/cron). 콜드스타트 지연 완화·stale 방지를 위해 Coolify scheduled task 로 주기 실행 + `prune_older_than`(2년 윈도우) 운영 연결 검토. (`seed_daily_prices` 가 prune 까지 수행하므로 cron 만 걸면 됨.)
  - **2026-06-04 갱신:** 진입 backfill 에 `daily_price_sync_state` 마커 + 종목 병렬화 적용(`docs/decisions.md` 참고). 휴장/발행지연 무한 재질의 제거·data.go.kr 호출수 상한 고정·신규 종목 자동 처리로 **cron 우선순위 하향**. cron 은 콜드스타트 첫-오픈 지연을 더 줄이고 싶을 때의 옵션으로 남음.

## 모바일앱 (v2.5) 잔여

- [ ] 푸시 알림, 생체인증(Face ID/지문), Android 백버튼/키보드 처리
- [ ] iOS 상태바 색 동기화 — @capacitor/status-bar 도입 후 다크/라이트 전환 시 status bar style 동기화

## v2 — KIS API 연동 (2026-06-07 사전 조사 완료, 2-트랙 분리)

2026-06-07 deep-research 사전 조사 결과를 바탕으로 2개 트랙으로 분리. **트랙 1 먼저 진행.**

- [ ] **KIS 트랙 1: 활성화(env 전환)** — 구현은 2026-06-07 완료(`docs/issue-history/2026-06-07-kis-data-providers.md`): 시세(`QUOTE_PROVIDERS` 에 kis)·일별 종가(`DAILY_PRICE_PROVIDER`/`DAILY_PRICE_GAP_PROVIDER`)·종목마스터(`STOCK_SEED_SOURCES` 에 kis)·교차검증(`CROSSVALIDATE_PROVIDER`) 전부 registry 등록 + 실호출 검증 완료. **현재 env 는 전부 기존 공급자 유지(무변경) — 활성화는 별도 운영 결정.**
  - **활성화 선행 조건:** ① 시세 화면 노출의 약관/KRX 라이선스 리스크 — KIS 공식 확인 권장(2026-06-07 사용자 인지 후 구현 포함 결정), ② **레이트리밋 — 공식 기본 유량 18건/초(실전, 계좌=앱키 단위, 2026-04-20 공지 기준)**. 실측 2건/초(2026-06-07, EGW00201)는 **신규 고객 3일 제한(2026-04-03 시행, 신규 신청 후 3일간 초당 3건)** 기간 측정으로 보임 — 기존 "법인/과거 수치" 추정은 정정. 발급 3일 경과 후 재실측하고 `kis.py` 페이싱 상수(`_RATE_MAX_CALLS=2`) 상향. 페이싱은 per-process 라 Coolify replica=1 확인 또는 공유 리미터(Redis 등) 필요("Preview staging 멀티 워커 대응"과 같은 계열). 추가 유량은 다른 계좌 앱키 발급이 공식 우회로(유량 확대/과금 계획 없음), ③ 운영 env 에 `KIS_APP_KEY`/`KIS_APP_SECRET` 주입, ④ **토큰 1일 1회 발급 원칙(2026-06-07 KIS 공식 안내 문자)** — "유효기간(24h) 내 잦은 토큰 발급 시 이용 제한" 정책 제재 명시. 토큰 캐시가 per-process 라 재배포·cron 배치(`seed_daily_prices` 등 별도 프로세스)·replica 마다 각자 발급 → 키 사용 경로(gap/일별종가/시세) 활성화 전 토큰 공유 저장소(DB/Redis) 영속화 필요(②와 같은 계열). 종목마스터·교차검증은 키 불필요 경로라 무관.
  - 권장 활성화 순서(위험 낮은 것부터): `STOCK_SEED_SOURCES` 에 kis 추가(키 불필요, data.go.kr 대체선) → **일별 종가는 `DAILY_PRICE_PROVIDER=kis` + `DAILY_PRICE_GAP_PROVIDER=none` 으로 직행**(아래 단순화 참조 — gap=kis 중간 단계 불필요) → 시세는 우선 **보조 공급자**(`QUOTE_PROVIDERS=naver,kis,yahoo` 등)로 — 1차 전환은 기본 유량(18건/초) 재실측 확인 후 재검토(신규 3일 제한 해제 여부 확인 선행).
  - **자산 추이 단순화(2026-06-07 검토): primary=kis 전환 시 gap 단계 자체가 제거된다** — gap 은 data.go.kr T+1 발행 지연이 만든 인공물인데 KIS 일봉은 어제 종가가 즉시(T+0) 반영되어 primary 가 어제까지 한 번에 채움. 구성요소 3개(primary+gap+현재가)→2개. 부수 이득: naver 비공식·data.go.kr 간헐 404 의존 동시 해소, ETN 커버(시장코드 J), cold-start 도 data.go.kr(14~18s)보다 빨라질 수 있음(18건/초 기준 2년×20종목≈100콜≈6s). **오늘 점 현재가까지 KIS 일봉으로 대체하는 것은 비권장** — ① 일봉 경로엔 시세의 TTLCache 45s+single-flight 완충이 없어 매 요청 종목 수만큼 호출(계좌 단위 한도 소모), ② 당일 행은 watermark 오염 방지 가드가 일부러 잘라냄(분리 취급은 코드 재설계), ③ 시세 인프라는 포트폴리오 요약 등이 어차피 사용해 절감 없음, ④ 휴장일 판정(`market_open_today`의 traded_on) 대체 변경 수반.
- [ ] KIS 휴장일 조회 API(CTCA0903R) 도입 검토 — 현재 휴장일 판정이 휴리스틱 2곳: ① `market_open_today`(시세 `traded_on` 신호 — KIS 시세는 항상 None), ② marcap `basDt` lookback("빈 응답이면 하루 더"). 공식 캘린더(일 1콜 수준)로 대체/보강 가능. 단독으론 작은 개선이지만 **시세 1차 공급자 kis 전환의 선행 문제(traded_on=None 휴장 판정 degrade)를 해소하는 연계 가치** — 시세 1차 전환 검토 시 함께 진행. 신규 구현 필요(실전 전용 TR, 모의 미지원 유의).
- [ ] KIS 트랙 2: 사용자 개인 데이터 자동화 — 사용자 본인 appkey 입력(BYOK)으로 매매내역·예수금·잔고 자동 동기화. 파일 업로드 임포트의 "대체"가 아닌 "KIS 사용자용 자동 동기화 옵션"으로 병행. 트랙 1 과 독립된 대형 feature.
  - 조회 API(2026-06-07 조사, 국내 실전 기준): 체결내역 `inquire-daily-ccld`(TTTC8001R, **최근 3개월**, 초과분 CTSC9215R) / 보유잔고 `inquire-balance`(TTTC8434R, 예수금 포함) / 매수가능현금 `inquire-psbl-order`(TTTC8908R) / 해외잔고 `inquire-present-balance`(CTRP6504R). 해외 체결내역 TR ID·기간 제한은 미확정.
  - 과거 이력 초기 적재는 3개월 제한 때문에 구체결 API 페이징 또는 기존 파일 업로드 병행 필요.
  - **선행 리스크(도입 전 KIS 공식 확인 필수):** ① 제3자 서비스가 사용자 키로 대신 호출(BYOK)하는 구조가 개인 약관 범위인지 — 가장 큰 리스크, ② appkey 에 주문 권한 포함(읽기 전용 스코프 불가로 보임) → 키 유출 시 주문 실행 가능, 키 보관 위치(서버 암호화 vs 디바이스 Keychain/Keystore + 디바이스 직접 호출) 설계 결정 필요, ③ 사용자별 KIS Developers 가입·앱키 발급 UX 마찰.

## v2 — 해외 주식

- [ ] 해외 주식 검색/시세 재도입 — Yahoo Finance 등 해외 종목 provider 선정 및 장애 fallback 정의
- [ ] USD/KRW 환율 적용 — 해외 종목 평가액을 KRW 기준 총자산·미실현손익에 합산
- [ ] HHI 크로스-통화 정합성 — 해외 포지션 평가액을 KRW로 변환 후 비중 계산

## v2 — UX

- [ ] 홈 위젯 커스터마이징

## v2 — 성능 / 스케일

- [ ] trades 페이지네이션 (BE+FE 동반) — `GET /trades` 에 cursor/limit 도입 + records 화면 `useInfiniteQuery` 무한스크롤. records 가 현재 전량 fetch 후 메모리 group-by-date / account filter 구조라, 페이지네이션 시 그룹핑·`allTrades` (상세 패널) ·`accounts` 응답 분리까지 함께 재설계 필요. 트리거: 거래 수 분포 측정에서 첫 페인트/메모리 영향이 체감되면 도입. ticker SQL push (2026-05-03 `docs/issue-history/2026-05-03-be-simplify-trades-ticker-sql-push.md`) 로 HoldingsList 측은 이미 행 수만 fetch 중.
- [ ] 포트폴리오/분석 읽기 경로 전량 로드 최적화 (2026-05-26 API 성능 분석 #4) — `GET /portfolio/summary`·`GET /analysis/dashboard` 가 매 호출마다 사용자 전체 거래를 `SELECT *` 로 로드하고 row 마다 `Trade(**dict(row))` Pydantic 검증을 돈다. 거래 누적 시 O(전체 거래수)로 선형 악화. 작업: ① 계산에 안 쓰는 텍스트 컬럼(`reflection_note`/`buy_reason`/`sell_reason`/`improvement_note` 등)을 `SELECT` 목록에서 제외, ② 읽기 전용 경로는 `Trade.model_construct(**dict(row))` 로 검증 스킵(DB 데이터 신뢰), ③ 위 trades 페이지네이션과 연계해 분석/요약 계산을 증분화 가능한지 검토. 트리거: 헤비 유저(대량 시드/실데이터)에서 응답시간·메모리 체감 또는 `pg_stat_statements` 의 rows/평균시간 상승. 측정 없이 선제 적용 시 micro-opt 수준.

## v3 — AI 분석

- [ ] 매매 패턴 분석 고도화 (감정-결과 상관관계 등)
- [ ] AI 기반 복기 제안
- [ ] 모바일 네이티브 앱 (React Native / Expo) 검토
