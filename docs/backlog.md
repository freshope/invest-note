# 백로그

MVP 이후 구현할 작업 후보 목록.

---

## 해외주식(US) 지원 — Phase C + 후속 (Phase A·B 완료)

로드맵 v2 "해외 주식 지원". **Phase A(기반 plumbing)·B(정합성 슬라이스) 모두 2026-06-08 완료.**

- Phase A: US 시세(`_fetch_yahoo_us`), USD/KRW 환율(`external/fx.py`+`GET /stocks/fx`), 검색
  KR+US 병합(`search_multi`), US seed(`seed_us`), FE 통화 포맷 유틸.
- Phase B: 해외 BUY 차단 해제, `domain/trade_types.to_krw`/`currency_for_country`,
  KRW 환산 합산(`build_totals`/`build_account_snapshots`/`build_pnl_map_krw`/`concentration`,
  라우터 `fetch_usdkrw` 주입), FE live overlay(`applyQuotesToTotals`/`applyQuotesToSnapshots` +
  `useFxRate`), `StockSearchInput` 필터 해제, HoldingCard native 통화 표시. 표시 전략: **KRW 환산 단일 총액**.

- [ ] **Phase C — import + 엣지.** Samsung/Toss 브로커 파서의 USD 거래 skip 해제
      (`broker_import/samsung_xlsx.py`·`toss_pdf.py`), 해외 거래세/수수료 규칙, 엣지케이스.
- [ ] **해외 SELL latent 경로 정리** — 해외 BUY 가 이제 허용되므로 정상 경로(BUY→SELL)가 열렸다.
      선행 BUY 없는 해외 SELL 단독 입력의 처리 규칙은 KR 과 동일(walker `running_qty>0` 가드)이라
      포지션은 안 생기나, 수동 입력 시 사용자 안내 UX 검토.

## 분석 탭 성능 / 유지보수

- [ ] 분석 대시보드 시세 분리 (옵션 B 동일 패턴) — `/analysis/dashboard` 도 요청 안에서 시세를 동기 fetch(concentration 계산용, `fetch_quotes_by_keys`)한다. 2026-05-27 `/portfolio/summary` 분리(`docs/decisions.md` 참고)와 동일하게 `withQuotes` opt-in + FE overlay 적용 검토. 단 concentration(HHI/top3/비중)은 시세 없으면 `cost_basis` fallback 이라 FE 로 옮기려면 concentration 계산까지 FE 중복이 필요 → 표면적이 summary 보다 큼. 트리거: summary 분리 효과 확인 후, 또는 분석 탭 응답 지연 체감 시.
- [ ] 분석 API 쿼리 `.limit(1000)` 가드 — 거래 수 급증 시 메모리/응답 보호
- [ ] 수수료 현황 별도 패널 — BUY commission·세금 합계, 순실현손익 vs 총비용 비교
- [ ] `_rule_high_winrate` 신뢰도 게이트 재검토 — 2026-05-20 `result_input_rate` 게이트 제거 후 현재 `sell_trades >= MIN_HIGH_WINRATE_SELL` + `win_rate >= WIN_THRESHOLD` 만으로 트리거. 실 데이터에서 인사이트가 과도하게 트리거되면 별도 신뢰도 메트릭(SELL 매칭률 등) 도입 검토. 트리거: 사용자 피드백 또는 인사이트 노출 빈도 모니터링에서 노이즈 체감.

## 운영 / 어드민 도구

- [ ] **KIS 앱키 만료·로테이션 가시화 (어드민 페이지에서 확인)** — 2026-06-08 조사. **문제:** KIS 앱키는 발급 1년 후 만료, 만료 30일 전부터 갱신 가능하고 **갱신=APP Key/APP Secret 재발급**(기존 값 연장이 아니라 새 값, KIS 공식 이용안내·wikidocs 확인). 즉 1년마다 시크릿 로테이션이 강제된다. 현재는 `KIS_APP_KEY`/`KIS_APP_SECRET` **env 단일 전역 키**(`kis_tokens.scope='app'` 고정)이고 **만료 감지/알림 코드 전무** → 만료 누락 시 `_issue_token()` 전면 실패 → 시세·일별종가 전체 장애(SPOF). 또 단일 키라 로테이션 시 env 교체+Coolify 재시작 사이 시세 공백 불가피(무중단 불가). **확인된 사실:** ① 유량 제한 단위 = 앱키(=계좌), 공식 기본 18건/초 — 다중 앱키 발급이 유량 확장 + 로테이션 무중단(키 A 교체 중 키 B 유지)의 공식 우회로(line 58 참조), ② 갱신은 재발급이라 만료일을 코드가 알 수 없음 → 운영자가 만료일을 명시 등록해야 D-day 산출 가능. **미확인(도입 전 KIS 확인 필요):** ① 갱신 직후 기존 키가 만료일까지 유효한지(유효하면 사전 갱신→교체로 무중단 가능, 무효화되면 점검창 필수), ② 유량 회피 목적 다중 앱키가 약관 허용인지. **방향(2026-06-08 결정):** 별도 어드민 페이지를 신규 구축해 거기서 만료 D-day·토큰 상태·최근 발급실패를 **확인**. 키 등록/교체(hot-swap)·멀티키까지 "관리"로 확장할지는 별도 결정 — 그 경우 키·만료일을 DB 저장(시크릿 암호화+서비스롤만 접근) 전제. 아래 "미사용 admin 라우터" 정리와 함께 엔드포인트 재설계.
- [ ] **미사용 admin 라우터 + ADMIN_TOKEN 인프라 제거** — 현재 모든 seed 스케줄은 Coolify 에서 CLI(`python -m invest_note_api.services.{stock_seed,nps_seed}`)로 돌고, `POST /admin/seed/{stocks,nps,daily-prices}`·`/admin/reconcile/nps` HTTP 트리거는 실제로 호출되지 않는다(`daily-prices` 는 스케줄 미등록·비활성 옵션). 작업: `routers/admin.py` 삭제 + `main.py` 의 `include_router(admin.router)` 제거 + `auth/admin.py`(`require_admin_token`) 제거 + `config.py` `admin_token`·env `ADMIN_TOKEN` 정리 + 관련 테스트 폐기. **단 `services/daily_price_seed.py` 의 `seed_daily_prices`(pre-warm) 함수는 보존** — 자산 추이 콜드스타트 첫-오픈 지연을 더 줄이고 싶을 때 살릴 여지(현재 비활성, `docs/decisions.md` 2026-06-04 cron 우선순위 하향 참고). 트리거: 별도 관리자 페이지를 만들 때 그에 맞는 엔드포인트로 재설계하며 함께 정리.
- [ ] PnL 저장값 검증 엔드포인트 (이슈 E) — `/admin/verify-pnl` 신설. SELL의 저장된 `profit_loss`/`avg_buy_price`/`holding_days`/`strategy_type`/`reasoning_tags`/`emotion`을 `compute_group_pnl()`로 재계산해 차이 검출. 사용자 단위 batch + 차이 리포트 + (옵션) 자동 보정. 권한은 admin scope. DB 직접 수정·마이그레이션 누락·mutation 경로 우회 시 분석 탭과 거래 기록 합계 불일치를 잡기 위함.

## PostHog 제품 분석 — 출시 전 후속 (도입은 2026-06-12 완료)

2026-06-12 PostHog(FE 전용, Cloud) 도입(`docs/decisions.md` 참고). 코드·tsc·build·정적 export 청크 로드까지 검증. 아래는 코드 외/실환경 잔여.

- [ ] **실환경 검증** — ① 웹 dev 로그인 후 PostHog Activity 에서 `$pageview`·`$identify`·커스텀 이벤트(`trade_recorded`/`trades_imported`/`account_added`) 도착 + 이벤트 프로퍼티에 종목/금액 등 민감값 없는지 직접 점검, ② `environment` 필터로 dev/prod 분리 동작 확인, ③ Capacitor 실기기(iOS/Android) — 탭 이동 시 pageview 도착·앱 재시작 후 distinct_id 유지·로그인/로그아웃 identify/reset·웹뷰 네트워크 차단 회귀 없음.
- [ ] **출시 전 개인정보 고지 (코드 외, 필수)** — 스토어 게시 금융 앱에 UUID 식별 서드파티 분석 도입에 따른 고지 의무. ① 개인정보처리방침 갱신(`invest-note.pixelwave.app`, 통합 저장소 freshope/pixelwave-web — PostHog 수집 항목·국외 이전 명시), ② Play Data Safety / App Store 개인정보 라벨("사용 데이터/식별자" 신고), ③ PIPA 동의·국외이전 검토. **불필요(확인됨):** posthog-js 는 1st-party JS — iOS ATT 프롬프트·`PrivacyInfo.xcprivacy` 번들 SDK 요건 미트리거.
- [ ] **운영 키 주입 확인** — `app/.env.production` 의 `NEXT_PUBLIC_POSTHOG_KEY` 는 빌드타임 주입(Coolify env 아님). 출시 빌드에 키가 실제 박혔는지 1회 확인(빈값이면 운영에서도 조용히 no-op).

## 배포 / 인프라

- [ ] user-scoped 테이블 신규 추가 시 `on delete cascade` 가드 — `auth.users` 삭제 시 cascade 누락된 FK가 있으면 탈퇴가 FK 위반으로 실패. 향후 새 user_id 컬럼을 가진 테이블을 추가하는 마이그레이션은 PR 리뷰 시 cascade 옵션 확인을 체크리스트로 명시. 또는 통합 테스트로 데모 사용자 삭제→재시드 시나리오를 자동화 검토.
- [ ] **OTA post-store 검증** — 2026-06-08 OTA v1(`docs/spec-history/2026-06-08-capacitor-ota-live-update.md`) 도입 후, 스토어 빌드 라이브 시점에 수행할 실검증. ① 실 R2 발행 1회(`node scripts/publish-ota.mjs`) 후 manifest/zip URL 200 + BE `POST /live-update/manifest` 분기 확인, ② 실기기 스큐 매트릭스 — 구네이티브+신웹(`required_native_version > version_build`) → OTA 차단되고 force-update 폴백 / 신네이티브+구웹 → OTA 적용 / 신규설치(`version_name="builtin"`) 중복 다운로드 없음, ③ 부팅 실패 번들 → `notifyAppReady()` 미달 시 자동 롤백, ④ capgo CLI checksum ↔ 플러그인 무결성 실디바이스 확인. v1 은 코드/pytest 까지라 실기기 항목이 미검증으로 남음.
- [ ] **OTA v2 확장** — v1 에서 의도적으로 제외한 항목. ① 서명/E2E 암호화(v1 은 checksum 무결성 + TLS 만 — 출처 위변조 방지용 서명 키 도입), ② 단계 롤아웃(%)(v1 은 100% 일괄 + 자동롤백 + 빠른 재푸시 — 사용자 증가 후 매니페스트 결정 API 에 `device_id` 해시 % 게이팅 추가), ③ 델타(차등) 업데이트(현재 매 발행 풀 zip 다운로드 — `out/` 크기 커지면 검토), ④ 채택률/실패율 통계 대시보드(R2 JSON SSOT 는 이력·통계 없음 — 도입 시 Postgres SSOT 재검토, `decisions.md` 2026-06-08 OTA 결정 참고). 부수: `ota-publish` Makefile 타깃 위치 정리(현재 스크립트 직접 호출, thin wrapper 관례).

## API 라우터 prefix 마이그레이션

- [ ] BE legacy `/api/*` alias 제거 (sunset) — 2026-05-21 `docs/spec-history/2026-05-21-be-dual-api-prefix.md` 에서 신/구 prefix 동시 지원 등록 (legacy 는 `include_in_schema=False`). FE/웹은 이미 새 경로 전환. 강제 업데이트 메커니즘은 2026-05-26 머지(`docs/spec-history/2026-05-26-force-update.md`). **남은 선행 조건**: 양 스토어 승인 + 옛 번들 사용자가 새 번들로 모두 이동 + 운영 로그에서 `/api/*` 트래픽이 충분히 줄어든 시점. 작업: `api/src/invest_note_api/main.py` 의 legacy `include_router` 루프 제거 + `tests/test_legacy_api_prefix.py` 폐기.
- [ ] `api/README.md` curl 예시 새 경로 갱신 — README 의 `http://localhost:8000/api/{accounts,trades,portfolio,stocks,analysis}` curl 예시 약 20곳을 신 경로로 일괄 갱신. 코스메틱.

## 거래내역서 임포트 — 후속 과제

- [ ] **종목 검색 provider db 복귀 + import/NPS stale 추적** (2026-06-03 Naver 임시 복귀, `docs/decisions.md` 참고) — data.go.kr 게이트웨이(~50% 성공률) 안정성 모니터링 후 `STOCK_SEARCH_PROVIDER=db` 로 복귀(코드 변경 없이 env 한 줄). **잔여 리스크:** 검색만 토글했으므로 seed 를 장기 중단하면 거래 import 매칭(`ticker_resolver.lookup_by_names`)·NPS(`stocks_repo.search`)·marcap 이 stale 로컬 stocks 에 의존해 조용히 낡음. 트리거: ① seed 게이트웨이 성공률 안정화 확인 시 db 복귀, 또는 ② import 매칭률 저하/NPS·시총 stale 체감 시 seed 재개 우선순위 상향.
- [ ] 공급자 env 토글 제외 잔존 — data.go.kr 고정 의존 (2026-06-07 env registry 도입, `docs/decisions.md` 참고) — 교차검증은 2026-06-07 KIS 트랙 1 에서 `CROSSVALIDATE_PROVIDER`(naver|kis) 토글로 **해소**. `update_marcap`(data.go.kr)만 고정 단계로 잔존 — KIS 는 bulk 시총 API 가 없어 종목별 호출 필요. 기본 유량 18건/초 기준 전종목 4,300콜≈4분 심야 cron 으로 **가능은 해짐**(2026-06-07 재평가)이나, data.go.kr 는 bulk 2콜로 같은 일을 하고 시총은 하루 stale 무해(실패 시 기존값 보존)라 평시 전환은 비권장 — **data.go.kr 장애 장기화 시 대체선**으로만(신규 fetcher 구현 필요). ⚠️ `CROSSVALIDATE_PROVIDER=kis` 전환 시 KONEX 종목이 대조 없이 "검증됨"으로 박제됨(마스터 파일에 KONEX 없음, `naver_checked_at` 공유 컬럼) — 전환 전 인지 필요. 트리거: data.go.kr 시총 경로 장애 장기화 시 marcap 대체 재검토.
- [ ] 미해결 종목 수동 매칭 UI — Naver 자동매칭 실패 또는 부분일치 오매칭 케이스에 대비, PreviewStep에서 사용자가 직접 종목 검색하여 매칭하는 UI 추가 검토
- [ ] Preview staging 멀티 워커 대응 — 현재 `TTLCache` (단일 워커 메모리). 멀티 워커 배포 전 DB 임시 테이블 또는 Redis로 교체 필요
- [ ] 임포트 통합 테스트 — `/import/preview`, `/import/commit` HTTP 엔드포인트 단위 테스트 (DB mock 또는 테스트 DB)
- [ ] import preview 그룹 검증 중복 제거 (2026-05-26 API 성능 분석 #5) — `import_preview` 가 `account_id` 를 받으면 `_validate_import_groups` 가 commit 과 동일한 그룹별 `list_trades_in_group` + oversell 검증을 한 번 더 수행한다(`routers/trades.py` 의 preview 경로). 그룹 수가 많은 파일일수록 preview 에서 N회 추가 쿼리. 작업: preview 의 dedup 용 date-range fetch 결과를 재활용하거나, 정합성(oversell) 검증을 commit 단계로 일원화하고 preview 는 참고용 카운트만 노출. 주의: preview 단계에서 사용자에게 위반을 미리 보여주는 UX 가치가 있으므로 제거 전 FE 노출 동작 확인 필요.
- [ ] `BROKERS`(`lib/brokers.ts`) ↔ `BROKER_OPTIONS`(`ImportTradesPanel/brokers.ts`) 라벨 동기화 단위 테스트 — `findBrokerKeyByAccountBroker`가 라벨 정확 일치에 의존(예: "삼성증권"). 한쪽 표기가 변하면 매칭이 조용히 깨짐. 두 테이블 라벨 교집합을 단위 테스트로 강제
- [ ] 일괄 등록 — 모든 계좌가 미지원 증권사일 때 별도 안내 — 계좌가 0개일 때(빈 상태)와 다른 메시지(예: "등록된 계좌의 증권사가 아직 일괄 등록을 지원하지 않습니다") 노출. 현재는 비활성 카드에 "일괄 등록 미지원" 라벨만 표시되고 전체 안내 메시지는 없음(`AccountStep.tsx`)
- [ ] 머지 갱신 범위 확장 재검토 — 현재 머지는 `commission`/`tax`/`traded_at` 만 update, `market_type`/`country_code`/`exchange` 는 사용자 분류를 우선해 **보존**(`docs/decisions.md` 2026-05-18 참고). 다음 트리거 발생 시 재검토: ① 사용자가 거래내역서로 분류 자동 보정을 명시적으로 원함, ② 증권사 파서가 사용자 수동 분류보다 더 정확한 케이스가 다수 보고됨. 재검토 시 `update_trade_from_import` 화이트리스트와 `build_merge_patch` 비교 필드를 함께 확장
- [ ] 다운로드 가이드 콘텐츠 검수 — `app/src/components/records/ImportTradesPanel/brokers.ts` 의 `downloadGuide` 는 AI 1차 초안(`TODO` 주석 표시). 삼성증권 mPOP/토스 앱과 실제 화면 대조 후 단계 텍스트·`helpUrl` 수정. 증권사 앱 UI 개편 시 깨질 수 있어 분기별 점검 또는 사용자 신고 트리거 시 갱신. 캡처 이미지 단계 안내가 더 효과적이라 판단되면 별도 spec 으로 보강

## 거래내역서 일괄등록 고도화 — 해외주식(US/USD)

2026-06-12 토스 해외포함 거래내역서 샘플(`sample/거래내역서_토스_해외포함_20250613_20260612_1.pdf`) 검토 결과 정리. 본체(US 직접입력·KRW 통합표시·거래시점 환율 저장)는 이미 출시됨 — 위 "해외주식(US) 지원" 섹션 **Phase C** 및 "거래내역서 임포트 — 후속 과제"의 "해외 주식 임포트 지원" 항목을 이 섹션으로 통합·상세화한다.

**확인된 토스 해외 행 구조(한 거래 = 2줄):**

```
거래일자 거래구분 종목명(종목코드) 환율 거래수량 거래대금 정산금액 단가 수수료 제세금 변제/연체합 잔고 잔액
2026.06.10 구매 게임하우스 홀딩스(KYG3731B1086) 1,518.40 1 3,006 3,006 3,006 0 0 0 1 3,036   ← KRW 환산값 + 환율
              ($ 1.98)  ($ 1.98) ($ 1.98) ($ 0.00) ($ 0.00) ($ 0.00) ($ 2.00)                  ← USD 원값
```

일자·구분·종목명·**환율(1,518.40)**·수량·KRW단가·USD단가($1.98)가 모두 존재. USD 섹션 헤더는 KRW 섹션과 달리 `거래세` 컬럼이 없다(동적 `_build_column_map` 이 흡수).

> 해외 거래 누락 silent-loss 상시 안내 배너(`PreviewStep.tsx`)는 2026-06-12 구현됨. 실제 해외 **등록**은 아래 본구현 전까지 미지원(국내만 등록).

### 본구현 — 해외 일괄등록 (US/USD)

- [ ] **파서 USD 섹션 파싱** — ① 종목코드 정규식 6자리→ISIN(12자리 영숫자) 허용, ② 한 거래=2줄(KRW행 + `($…)` USD행) 연결 파싱, ③ 환율·USD 단가 추출, ④ `ParsedTrade` 에 `exchange_rate` 필드 추가(`base.py`). ⚠️ **샘플엔 구매(BUY) 행만 존재 — 판매(SELL) 행 포맷은 미관측**, SELL 포함 실샘플 확보 후 검증 필요.
- [ ] **종목 식별 (핵심 병목)** — 파일은 ISIN(`KYG3731B1086`)만 제공하나 시스템은 해외 종목을 **Yahoo 티커 + country_code** 로 식별·시세조회한다(`external/quotes.py` US 경로). ISIN→(티커·거래소·국가) 매핑 부재 시 전건 미해결. ISIN 접두는 설립지(KY=케이맨)라 상장국가도 도출 불가. `resolve_tickers→lookup_by_names` 는 `country_code=KR` 기본값으로만 검색하고 파일은 한글명이라 영문 US 마스터와도 불일치. 선택지: ① stocks 마스터에 ISIN 매핑 자료원 확보(예탁원/KRX), ② 종목명 매칭, ③ 미해결 종목 수동 매칭 UI(아래 후속 과제 항목)로 사용자가 직접 검색·매칭. **현실적 1차안: ③(+②).**
- [ ] **커밋 환율 가드 충족** — `import_commit` 이 비-KRW 거래에 `exchange_rate` 강제(`trades.py:866` 방어 가드). 파서가 추출한 환율을 staging→`insert_row` 까지 배선하고, `country_code` 하드코딩(KR, `trades.py:730`)을 해외 실국가로 해소.
- [ ] **삼성증권 USD** — `samsung_xlsx.py:96` 동일 skip 존재. 동일 silent-loss 여부 검증 후 같은 안내 가드·본구현 적용. (삼성 USD 샘플 확보 후)
- [ ] 업로드 파일 형식 ↔ 선택 증권사 일치 검증 — 파일명 자동감지(`detect_broker`/`match`)는 2026-06-12 제거(사용자가 계좌=증권사 직접 선택). 향후 필요 시 "토스 계좌인데 삼성 xlsx 업로드" 같은 불일치를 경고하는 검증으로 재설계.

## 자산 추이 페이지 — 운영 잔여 (페이지 자체는 2026-06-04 출시)

- [ ] **일별 종가 자동 적재 + 2년 prune 운영** — 현재 종가 백필은 페이지 진입 시 동기 실행(종목별 watermark 증분), 전체 사전적재는 `POST /admin/seed/daily-prices`(수동/cron). 콜드스타트 지연 완화·stale 방지를 위해 Coolify scheduled task 로 주기 실행 + `prune_older_than`(2년 윈도우) 운영 연결 검토. (`seed_daily_prices` 가 prune 까지 수행하므로 cron 만 걸면 됨.)
  - **2026-06-04 갱신:** 진입 backfill 에 `daily_price_sync_state` 마커 + 종목 병렬화 적용(`docs/decisions.md` 참고). 휴장/발행지연 무한 재질의 제거·data.go.kr 호출수 상한 고정·신규 종목 자동 처리로 **cron 우선순위 하향**. cron 은 콜드스타트 첫-오픈 지연을 더 줄이고 싶을 때의 옵션으로 남음.
- [ ] **오늘 점 시세 소스 정합 (자산추이 ↔ 대시보드)** — 2026-06-11 자산추이 KRW 환산 BE 이관 후 잔여. 자산추이 오늘 점 총액은 BE `fetch_quotes_by_keys` 로, 대시보드 합계는 `/portfolio/summary` + FE overlay 시세로 계산돼 **오늘 점 총액이 미세하게 어긋날 수 있다**(포함범위·usdkrw 소스는 일치, finding A 해소됨). 같은 시세 소스로 통일하거나 허용 오차를 명시. 트리거: 사용자가 두 화면 오늘 값 차이를 체감하거나 시세 변동성 큰 종목에서 괴리 보고 시.

- [ ] 푸시 알림, 생체인증(Face ID/지문), Android 백버튼/키보드 처리
- [ ] iOS 상태바 색 동기화 — @capacitor/status-bar 도입 후 다크/라이트 전환 시 status bar style 동기화

## 사용자 요청 및 추가 기능

- [ ] 목표가(%), 손절 및 익절 계획을 입력하고 그것을 지켰는지 여부를 분석
- [ ] 관심 종목 추가 (보유하지 않은 종목도 볼 수 있게)

## v2 — KIS API 연동 (2026-06-07 사전 조사 완료, 2-트랙 분리)

2026-06-07 deep-research 사전 조사 결과를 바탕으로 2개 트랙으로 분리. **트랙 1 먼저 진행.**

- [ ] **KIS 트랙 1: 활성화(env 전환)** — 구현은 2026-06-07 완료(`docs/spec-history/2026-06-07-kis-data-providers.md`): 시세(`QUOTE_PROVIDERS` 에 kis)·일별 종가(`DAILY_PRICE_PROVIDER`/`DAILY_PRICE_GAP_PROVIDER`)·종목마스터(`STOCK_SEED_SOURCES` 에 kis)·교차검증(`CROSSVALIDATE_PROVIDER`) 전부 registry 등록 + 실호출 검증 완료. **활성화 진행 상태(2026-06-14): 종목마스터 seed·일별종가 primary·시세 보조 fallback 까지 운영 적용·검증 완료. 시세 primary=kis 전환은 보조 유지로 보류(B 휴장일 API 선행 필요, 급하지 않음) — 활성화 트랙 사실상 마무리.**
  - **활성화 선행 조건:** ① 시세 화면 노출의 약관/KRX 라이선스 리스크 — KIS 공식 확인 권장(2026-06-07 사용자 인지 후 구현 포함 결정), ② **레이트리밋 — 공식 기본 유량 18건/초(실전, 계좌=앱키 단위, 2026-04-20 공지 기준)**. 실측 2건/초(2026-06-07, EGW00201)는 **신규 고객 3일 제한(2026-04-03 시행, 신규 신청 후 3일간 초당 3건)** 기간 측정이었음이 **2026-06-14 재실측으로 확정**(발급 7일 경과, 국내 현재가 동시 20건 버스트 ×2 → 20/20 성공·EGW00201 0건 → 기본 유량 ≥20/초 복귀). `kis.py` 페이싱 상수 `_RATE_MAX_CALLS` **2→18 상향 완료**(`docs/decisions.md` 2026-06-07 ① 재실측 메모 참고). ✅ **레이트리밋 선행조건 해소.** 잔여: 페이싱은 per-process — **Coolify replica=1 확인됨(2026-06-14)**, replica 증설 시 공유 리미터(Redis 등) 재검토("Preview staging 멀티 워커 대응"과 같은 계열). 추가 유량은 다른 계좌 앱키 발급이 공식 우회로(유량 확대/과금 계획 없음), ③ 운영 env 에 `KIS_APP_KEY`/`KIS_APP_SECRET` 주입 — **완료**(실유효 키 확인: 2026-06-14 토큰 발급+시세 호출 성공), ④ **토큰 1일 1회 발급 원칙 — 해소됨(2026-06-07 `kis_tokens` DB 영속화 구현, `docs/decisions.md` 참고)**. 잔여: ~~운영 배포 후 토큰 영속 동작 1회 확인~~ **확인됨(2026-06-14: 일별종가 kis 전환 후 운영 BE 에서 신규 종목 백필이 토큰 발급·영속 성공)**, cron 배치(`seed_daily_prices` 등 별도 프로세스)가 KIS 를 쓰게 되면 해당 진입점에도 `configure_kis(settings, pool=...)` 배선 필요(현재 lifespan 만). 종목마스터·교차검증은 키 불필요 경로라 무관. ⑤ 멀티워커/멀티 replica 전환 시 토큰 거부 응답 → DB 재조회(타 워커 신규 토큰 픽업) 로직 추가 필요 — 현재 replica=1 전제.
  - 권장 활성화 순서(위험 낮은 것부터): ✅ `STOCK_SEED_SOURCES` 에 kis 추가(키 불필요, data.go.kr 대체선) — **env 적용됨**(`STOCK_SEED_SOURCES=data_go_kr,stock_prices,securities,kis`) → ✅ 일별 종가 `DAILY_PRICE_PROVIDER=kis` + `DAILY_PRICE_GAP_PROVIDER=none` — **운영 적용·검증 완료(2026-06-14: 부팅 OK, 신규 종목 KIS 백필+토큰 발급 확인)** → ✅ 시세는 우선 **보조 공급자**(`QUOTE_PROVIDERS=naver,kis,yahoo`)로 **적용됨(2026-06-14 확인, kis=naver 실패 시 fallback)**. 레이트리밋 재실측·페이싱 상향이 끝나(위 ② 해소) 1차 전환도 기술적으로 가능해졌으나, KIS 시세는 traded_on=None 휴장판정 degrade(아래 휴장일 API 항목) 때문에 우선 보조 포지셔닝 권장.
  - **자산 추이 단순화(2026-06-07 검토): primary=kis 전환 시 gap 단계 자체가 제거된다** — gap 은 data.go.kr T+1 발행 지연이 만든 인공물인데 KIS 일봉은 어제 종가가 즉시(T+0) 반영되어 primary 가 어제까지 한 번에 채움. 구성요소 3개(primary+gap+현재가)→2개. 부수 이득: naver 비공식·data.go.kr 간헐 404 의존 동시 해소, ETN 커버(시장코드 J), cold-start 도 data.go.kr(14~18s)보다 빨라질 수 있음(18건/초 기준 2년×20종목≈100콜≈6s). **오늘 점 현재가까지 KIS 일봉으로 대체하는 것은 비권장** — ① 일봉 경로엔 시세의 TTLCache 45s+single-flight 완충이 없어 매 요청 종목 수만큼 호출(계좌 단위 한도 소모), ② 당일 행은 watermark 오염 방지 가드가 일부러 잘라냄(분리 취급은 코드 재설계), ③ 시세 인프라는 포트폴리오 요약 등이 어차피 사용해 절감 없음, ④ 휴장일 판정(`market_open_today`의 traded_on) 대체 변경 수반.
- [ ] KIS 휴장일 조회 API(CTCA0903R) 도입 검토 — 현재 휴장일 판정이 휴리스틱 2곳: ① `market_open_today`(시세 `traded_on` 신호 — KIS 시세는 항상 None), ② marcap `basDt` lookback("빈 응답이면 하루 더"). 공식 캘린더(일 1콜 수준)로 대체/보강 가능. 단독으론 작은 개선이지만 **시세 1차 공급자 kis 전환의 선행 문제(traded_on=None 휴장 판정 degrade)를 해소하는 연계 가치** — 시세 1차 전환 검토 시 함께 진행. 신규 구현 필요(실전 전용 TR, 모의 미지원 유의). **2026-06-14: 시세 primary=kis 전환을 보류(보조 유지)하기로 결정 → B 도 함께 보류. 독립적인 휴장일 판정 개선이 필요해지면 단독 진행.**
- [ ] KIS 트랙 2: 사용자 개인 데이터 자동화 — 사용자 본인 appkey 입력(BYOK)으로 매매내역·예수금·잔고 자동 동기화. 파일 업로드 임포트의 "대체"가 아닌 "KIS 사용자용 자동 동기화 옵션"으로 병행. 트랙 1 과 독립된 대형 feature.
  - 조회 API(2026-06-07 조사, 국내 실전 기준): 체결내역 `inquire-daily-ccld`(TTTC8001R, **최근 3개월**, 초과분 CTSC9215R) / 보유잔고 `inquire-balance`(TTTC8434R, 예수금 포함) / 매수가능현금 `inquire-psbl-order`(TTTC8908R) / 해외잔고 `inquire-present-balance`(CTRP6504R). 해외 체결내역 TR ID·기간 제한은 미확정.
  - 과거 이력 초기 적재는 3개월 제한 때문에 구체결 API 페이징 또는 기존 파일 업로드 병행 필요.
  - **선행 리스크(도입 전 KIS 공식 확인 필수):** ① 제3자 서비스가 사용자 키로 대신 호출(BYOK)하는 구조가 개인 약관 범위인지 — 가장 큰 리스크, ② appkey 에 주문 권한 포함(읽기 전용 스코프 불가로 보임) → 키 유출 시 주문 실행 가능, 키 보관 위치(서버 암호화 vs 디바이스 Keychain/Keystore + 디바이스 직접 호출) 설계 결정 필요, ③ 사용자별 KIS Developers 가입·앱키 발급 UX 마찰.

## v2 — UX

- [ ] 홈 위젯 커스터마이징

## v2 — 성능 / 스케일

- [ ] trades 페이지네이션 (BE+FE 동반) — `GET /trades` 에 cursor/limit 도입 + records 화면 `useInfiniteQuery` 무한스크롤. records 가 현재 전량 fetch 후 메모리 group-by-date / account filter 구조라, 페이지네이션 시 그룹핑·`allTrades` (상세 패널) ·`accounts` 응답 분리까지 함께 재설계 필요. 트리거: 거래 수 분포 측정에서 첫 페인트/메모리 영향이 체감되면 도입. ticker SQL push (2026-05-03 `docs/spec-history/2026-05-03-be-simplify-trades-ticker-sql-push.md`) 로 HoldingsList 측은 이미 행 수만 fetch 중.
- [ ] 포트폴리오/분석 읽기 경로 전량 로드 최적화 (2026-05-26 API 성능 분석 #4) — `GET /portfolio/summary`·`GET /analysis/dashboard` 가 매 호출마다 사용자 전체 거래를 `SELECT *` 로 로드하고 row 마다 `Trade(**dict(row))` Pydantic 검증을 돈다. 거래 누적 시 O(전체 거래수)로 선형 악화. 작업: ① 계산에 안 쓰는 텍스트 컬럼(`reflection_note`/`buy_reason`/`sell_reason`/`improvement_note` 등)을 `SELECT` 목록에서 제외, ② 읽기 전용 경로는 `Trade.model_construct(**dict(row))` 로 검증 스킵(DB 데이터 신뢰), ③ 위 trades 페이지네이션과 연계해 분석/요약 계산을 증분화 가능한지 검토. 트리거: 헤비 유저(대량 시드/실데이터)에서 응답시간·메모리 체감 또는 `pg_stat_statements` 의 rows/평균시간 상승. 측정 없이 선제 적용 시 micro-opt 수준.

## v3 — AI 분석

- [ ] 매매 패턴 분석 고도화 (감정-결과 상관관계 등)
- [ ] AI 기반 복기 제안
- [ ] 모바일 네이티브 앱 (React Native / Expo) 검토
