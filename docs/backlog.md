# 백로그

MVP 이후 구현할 작업 후보 목록.

---

- [ ] **탈-Supabase Auth Phase 2 — BE token-broker 코드 완료, 출시/활성화·2c 대기 (2026-06-19, 2b-3/2b-4 추가 2026-06-20)** — **코드 구현 완료**(2a expand 토대 dormant / 2b-1 BE OAuth 중개·토큰 발급·refresh·profile / 2b-2 FE 네이티브 BE flow 전환 / **2b-3 신규 가입 경로**(callback miss→런타임 user+매핑 생성, race-safe) / **2b-4 BE flow 서버 플래그**(app-config `beAuthEnabled`, B안 cutover flip 메커니즘)). 사양: `decisions.md` 2026-06-19(2a/2b-1/2b-2)·2026-06-20(2b-3/2b-4), `spec-history` 2b-3/2b-4, 설계 `_workspace/auth-phase2-design.md`. 머지는 **dormant-safe**(BE env 미주입 시 발급 off + 플래그 default OFF→Supabase 무회귀). **남은 것:**
  - **① 🔴 출시 전 디바이스 스모크(코드 불가)**: iOS+Android 실기기로 `crypto.subtle.digest`(S256 PKCE) custom-scheme WebView 동작 + secure storage(Keychain/Keystore) round-trip. (안전 신호: 현 supabase-js PKCE 가 동일 WebView S256 성공 중)
  - **② B안 cutover(심사-cutover 디커플)**: **(선행)** secure-storage 포함 shell 바이너리를 **BE flow OFF**(플래그)로 일반 출시·점진 보급(신규 네이티브 델타는 secure-storage 하나뿐, 딥링크 scheme 기존 재사용). **(cutover, 전부 서버·심사 무관)** 마이그레이션 **0004+0005+0006** 적용 → **Supabase 신규가입 동결**(클라우드 대시보드, SSOT) → **최종 백필**(identity→profile, dry-run 선행) → **BE 활성화 env**(provider secret·Apple `.p8`·ES256 서명키·`be_token_audience`·`be_oauth_redirect_base`) + IdP redirect_uri 에 BE callback 추가 → **`BE_AUTH_ENABLED=true` flip**(Coolify env). ⚠️ flip 은 **백필 완료 후**(hard precond, 미완 시 기존자 중복). ⚠️ flip 시 신 바이너리 기존자 **1회 재로그인**(토큰 체계 상이, 데이터 보존). + A1 운영 토큰 iss 실측(prod 핀 활성화 시 — Supabase fallback 이라 핀은 선택).
  - **③ 배포**: BE Coolify(dormant 먼저 가능) / FE secure-storage shell 스토어 빌드(네이티브 플러그인 → **OTA 불가**). 단 **cutover flip 자체는 Coolify env 토글**(OTA·스토어·심사 무관 서버 전환).
  - **④ 2c (contract, force-update 양 스토어 승인 후 [[project_force_update]])**: issuer registry 의 Supabase default fallback 제거(BE 토큰만 검증) + FE 웹 분기 supabase-js 제거(또는 웹 폐기) + `@supabase/supabase-js`·`SUPABASE_*` env·`supabase/` 디렉토리·클라우드 프로젝트 정리. ⚠️ 비가역(신 앱 안정 전제). `auth_identities` 매핑 테이블은 유지.
  - **⑤ DEFER(코드리뷰 후속)**: AuthStrategy 인터페이스로 isNativePlatform 이중화 일반화(2c 가 웹 분기 삭제하므로 그때) / ✅ BE `/auth/logout` refresh-revoke 엔드포인트 **완료(2026-06-26, `feature/admin-be-auth`)** — app+admin signOut 이 best-effort 서버 revoke 호출, `token_store.revoke_refresh` 멱등(access 는 단명 stateless 라 자연 만료) / 딥링크 scheme 상수↔BE `BE_DEEPLINK_SCHEME` 정합 주석 / `getAccessToken` cold-start 캐시 미스 race(저severity, 최대 1h stale·30d 부활은 가드됨).
  - **⑥ PIPA**: `user_profiles` PII(email·이름·아바타·provider·email_verified·가입일·최근로그인) 확대 → 개인정보처리방침/Play Data Safety/App Store 라벨 갱신(기존 PostHog 고지 항목과 연동).
  - 트리거: 출시 결정 시 ①②③ → 베이크 → ④.
- [ ] **app/admin auth 3계층 공유 패키지화 (2026-06-19, 코드리뷰 후속)** — Phase 1 에서 `app/src/lib/auth/`(types/supabase-client/index)를 `admin/src/lib/auth/` 패턴을 미러링해 신규 작성 → 두 워크스페이스에 거의 동일한 SDK 격리 seam 이 중복. `pnpm-workspace.yaml` 이 app+admin 을 한 모노레포로 묶으므로 공유 패키지(`@invest-note/auth` 류)로 공통부(supabase-client·neutral 타입·`toAuthUser`/`getAccessToken`/`getUser`/`subscribe`/`signOut`) 추출 가능. 발산부(`signInWithOAuth` 멀티프로바이더+네이티브 url vs admin `signInWithGoogle` 웹전용, signOut scope)만 각자 유지. 효과: 탈-Supabase 시 격리 경계를 한 곳만 교체. 트리거: 양쪽 auth 동시 변경이 잦아지거나 Phase 2 착수 시.
- [ ] **어드민 BE-auth 코드리뷰 후속 (2026-06-26, 배포 완료)** — 어드민 패널 BE 토큰-브로커 전환(`feature/admin-be-auth` → develop)·운영 배포·라이브 완료(v1.3.2). **남은 스킵된 코드리뷰 후속(저severity, 내부 콘솔)**: #3 `_handle_callback` 실패 레그가 web 어드민에 raw JSON 노출(만료 state 는 client 식별 불가라 근본 수정 한계) / #4 `signInWithGoogle` full-page 이동이라 dormant-503 catch 불가(env 미설정 시에만, 배포 체크리스트가 커버). 트리거: 코드 품질 라운드.
- [ ] **RLS 제거 후속 — 라우터 인라인 user_id 필터 e2e 회귀 가드 확대 (2026-06-18)** — RLS 제거(`0002_drop_rls`)로 DB 백스톱이 사라져 사용자 격리는 앱 레이어 `WHERE user_id` 가 유일 수단. 현재 회귀 가드 `tests/test_user_isolation_db.py` 는 **repo 함수(accounts/trades/custom_tags repo + pnl_sync)만** 커버하고, 라우터에 인라인된 user_id 필터(`routers/accounts.py` 의 `get_trade_count` 2쿼리·`list_accounts` 의 trades count·`create_account` INSERT)는 미커버. 후속: HTTP 레이어 + 실DB 픽스처로 두 사용자 시드 후 해당 엔드포인트의 cross-user 격리를 검증(인라인 쿼리에서 `AND user_id` 누락 시 실패하도록). 트리거: 라우터 인라인 SQL 추가/수정 시 또는 보안 강화 라운드.

## 분석 탭 성능 / 유지보수

- [ ] 분석 대시보드 시세 분리 (옵션 B 동일 패턴) — `/analysis/dashboard` 도 요청 안에서 시세를 동기 fetch(concentration 계산용, `fetch_quotes_by_keys`)한다. 2026-05-27 `/portfolio/summary` 분리(`docs/decisions.md` 참고)와 동일하게 `withQuotes` opt-in + FE overlay 적용 검토. 단 concentration(HHI/top3/비중)은 시세 없으면 `cost_basis` fallback 이라 FE 로 옮기려면 concentration 계산까지 FE 중복이 필요 → 표면적이 summary 보다 큼. 트리거: summary 분리 효과 확인 후, 또는 분석 탭 응답 지연 체감 시.
- [ ] 분석 API 쿼리 `.limit(1000)` 가드 — 거래 수 급증 시 메모리/응답 보호
- [ ] 수수료 현황 별도 패널 — BUY commission·세금 합계, 순실현손익 vs 총비용 비교
- [ ] `_rule_high_winrate` 신뢰도 게이트 재검토 — 2026-05-20 `result_input_rate` 게이트 제거 후 현재 `sell_trades >= MIN_HIGH_WINRATE_SELL` + `win_rate >= WIN_THRESHOLD` 만으로 트리거. 실 데이터에서 인사이트가 과도하게 트리거되면 별도 신뢰도 메트릭(SELL 매칭률 등) 도입 검토. 트리거: 사용자 피드백 또는 인사이트 노출 빈도 모니터링에서 노이즈 체감.

## 운영 / 어드민 도구

- [ ] **eslint lint warnings 잔여 (2026-06-30, set-state-in-effect 라운드 후속)** — admin eslint config 부재(전역 lint 실패)는 2026-06-30 해소(`admin/eslint.config.mjs` 추가 + app/admin `react-hooks/set-state-in-effect` 에러 5+1건 정식 수정: 대부분 렌더 중 상태조정 패턴 전환, object-URL previews·딥링크 consume 2건만 사유주석 disable). `_`-prefix 미사용 var 경고는 2026-06-30 `argsIgnorePattern:^_`(app+admin config) 로 해소(7→4). **남은 advisory warnings 4건:** ① `<img>`→`next/image`(`BrokerLogo.tsx`·`trade-display.tsx`, 시각/레이아웃 영향 검토 필요), ② `compilation-skipped`(React Compiler "incompatible library" — `TradeEditPanel.tsx`·`AccountFormPanel.tsx`). 에러 아님(exit 0). 트리거: 코드 품질 라운드 또는 CI lint 게이트 `--max-warnings 0` 도입 시.
- [ ] **KIS 앱키 만료·로테이션 가시화 (어드민 페이지에서 확인)** — 2026-06-08 조사. **문제:** KIS 앱키는 발급 1년 후 만료, 만료 30일 전부터 갱신 가능하고 **갱신=APP Key/APP Secret 재발급**(기존 값 연장이 아니라 새 값, KIS 공식 이용안내·wikidocs 확인). 즉 1년마다 시크릿 로테이션이 강제된다. 현재는 `KIS_APP_KEY`/`KIS_APP_SECRET` **env 단일 전역 키**(`kis_tokens.scope='app'` 고정)이고 **만료 감지/알림 코드 전무** → 만료 누락 시 `_issue_token()` 전면 실패 → 시세·일별종가 전체 장애(SPOF). 또 단일 키라 로테이션 시 env 교체+Coolify 재시작 사이 시세 공백 불가피(무중단 불가). **확인된 사실:** ① 유량 제한 단위 = 앱키(=계좌), 공식 기본 18건/초 — 다중 앱키 발급이 유량 확장 + 로테이션 무중단(키 A 교체 중 키 B 유지)의 공식 우회로(line 58 참조), ② 갱신은 재발급이라 만료일을 코드가 알 수 없음 → 운영자가 만료일을 명시 등록해야 D-day 산출 가능. **미확인(도입 전 KIS 확인 필요):** ① 갱신 직후 기존 키가 만료일까지 유효한지(유효하면 사전 갱신→교체로 무중단 가능, 무효화되면 점검창 필수), ② 유량 회피 목적 다중 앱키가 약관 허용인지. **방향(2026-06-08 결정):** 별도 어드민 페이지를 신규 구축해 거기서 만료 D-day·토큰 상태·최근 발급실패를 **확인**. 키 등록/교체(hot-swap)·멀티키까지 "관리"로 확장할지는 별도 결정 — 그 경우 키·만료일을 DB 저장(시크릿 암호화+서비스롤만 접근) 전제. 아래 "미사용 admin 라우터" 정리와 함께 엔드포인트 재설계.
- [ ] **미사용 admin 라우터 + ADMIN_TOKEN 인프라 제거** — 현재 모든 seed 스케줄은 Coolify 에서 CLI(`python -m invest_note_api.services.{stock_seed,nps_seed}`)로 돌고, `POST /admin/seed/{stocks,nps,daily-prices}`·`/admin/reconcile/nps` HTTP 트리거는 실제로 호출되지 않는다(`daily-prices` 는 스케줄 미등록·비활성 옵션). 작업: `routers/admin.py` 삭제 + `main.py` 의 `include_router(admin.router)` 제거 + `auth/admin.py`(`require_admin_token`) 제거 + `config.py` `admin_token`·env `ADMIN_TOKEN` 정리 + 관련 테스트 폐기. **단 `services/daily_price_seed.py` 의 `seed_daily_prices`(pre-warm) 함수는 보존** — 자산 추이 콜드스타트 첫-오픈 지연을 더 줄이고 싶을 때 살릴 여지(현재 비활성, `docs/decisions.md` 2026-06-04 cron 우선순위 하향 참고). 트리거: 별도 관리자 페이지를 만들 때 그에 맞는 엔드포인트로 재설계하며 함께 정리.
- [ ] PnL 저장값 검증 엔드포인트 (이슈 E) — `/admin/verify-pnl` 신설. SELL의 저장된 `profit_loss`/`avg_buy_price`/`holding_days`/`strategy_type`/`reasoning_tags`/`emotion`을 `compute_group_pnl()`로 재계산해 차이 검출. 사용자 단위 batch + 차이 리포트 + (옵션) 자동 보정. 권한은 admin scope. DB 직접 수정·마이그레이션 누락·mutation 경로 우회 시 분석 탭과 거래 기록 합계 불일치를 잡기 위함.

## 거래내역서 임포트 — 후속 과제

- [ ] **종목 검색 provider db 복귀 + import/NPS stale 추적** (2026-06-03 Naver 임시 복귀, `docs/decisions.md` 참고) — data.go.kr 게이트웨이(~50% 성공률) 안정성 모니터링 후 `STOCK_SEARCH_PROVIDER=db` 로 복귀(코드 변경 없이 env 한 줄). **잔여 리스크:** 검색만 토글했으므로 seed 를 장기 중단하면 거래 import 매칭(`ticker_resolver.lookup_by_names`)·NPS(`stocks_repo.search`)·marcap 이 stale 로컬 stocks 에 의존해 조용히 낡음. 트리거: ① seed 게이트웨이 성공률 안정화 확인 시 db 복귀, 또는 ② import 매칭률 저하/NPS·시총 stale 체감 시 seed 재개 우선순위 상향.
- [ ] 공급자 env 토글 제외 잔존 — data.go.kr 고정 의존 (2026-06-07 env registry 도입, `docs/decisions.md` 참고) — 교차검증은 2026-06-07 KIS 트랙 1 에서 `CROSSVALIDATE_PROVIDER`(naver|kis) 토글로 **해소**. `update_marcap`(data.go.kr)만 고정 단계로 잔존 — KIS 는 bulk 시총 API 가 없어 종목별 호출 필요. 기본 유량 18건/초 기준 전종목 4,300콜≈4분 심야 cron 으로 **가능은 해짐**(2026-06-07 재평가)이나, data.go.kr 는 bulk 2콜로 같은 일을 하고 시총은 하루 stale 무해(실패 시 기존값 보존)라 평시 전환은 비권장 — **data.go.kr 장애 장기화 시 대체선**으로만(신규 fetcher 구현 필요). ⚠️ `CROSSVALIDATE_PROVIDER=kis` 전환 시 KONEX 종목이 대조 없이 "검증됨"으로 박제됨(마스터 파일에 KONEX 없음, `naver_checked_at` 공유 컬럼) — 전환 전 인지 필요. 트리거: data.go.kr 시총 경로 장애 장기화 시 marcap 대체 재검토.
- [ ] 미해결 종목 수동 매칭 UI — Naver 자동매칭 실패 또는 부분일치 오매칭 케이스에 대비, PreviewStep에서 사용자가 직접 종목 검색하여 매칭하는 UI 추가 검토
- [ ] 임포트 통합 테스트 — **부분 완료(2026-06-30, `tests/test_trade_import_http.py`)**: preview 가드(415 확장자/400 broker)+happy-path(파싱→ticker 해결→staging, new/unresolved/error 카운트·staging 영속), commit 가드(만료 400·타user 403)를 Fake harness(FakePool/FakeConnection/staging dict)로 커버. **잔여:** commit happy-path 전체 INSERT/merge/skip·`recalc_group_pnl` 경로(group·pnl mock 표면이 커 fragile → 테스트 DB 픽스처 또는 추가 mock 필요), preview의 account_id 지정 시 `_validate_import_groups`(oversell) 경로.
- [ ] import preview 그룹 검증 중복 제거 (2026-05-26 API 성능 분석 #5) — `import_preview` 가 `account_id` 를 받으면 `_validate_import_groups` 가 commit 과 동일한 그룹별 `list_trades_in_group` + oversell 검증을 한 번 더 수행한다(`routers/trades.py` 의 preview 경로). 그룹 수가 많은 파일일수록 preview 에서 N회 추가 쿼리. 작업: preview 의 dedup 용 date-range fetch 결과를 재활용하거나, 정합성(oversell) 검증을 commit 단계로 일원화하고 preview 는 참고용 카운트만 노출. 주의: preview 단계에서 사용자에게 위반을 미리 보여주는 UX 가치가 있으므로 제거 전 FE 노출 동작 확인 필요.
- [ ] 머지 갱신 범위 확장 재검토 — 현재 머지는 `commission`/`tax`/`traded_at` 만 update, `market_type`/`country_code`/`exchange` 는 사용자 분류를 우선해 **보존**(`docs/decisions.md` 2026-05-18 참고). 다음 트리거 발생 시 재검토: ① 사용자가 거래내역서로 분류 자동 보정을 명시적으로 원함, ② 증권사 파서가 사용자 수동 분류보다 더 정확한 케이스가 다수 보고됨. 재검토 시 `update_trade_from_import` 화이트리스트와 `build_merge_patch` 비교 필드를 함께 확장
- [ ] **KB증권 파서 — 매도 포함 샘플 확보 후 구현 (2026-06-25 보류)** — 신한·미래에셋과 함께 추가하려 했으나 제공된 KB 샘플(`거래내역서_KB증권_1.xlsx`)에 **매수 행만** 있어 매도(`주식장내매도`/`KOSDAQ매도`, 금액=`입금/입고/매도` 컬럼) 포맷을 회귀 검증할 수 없음. 추정 구현 금지 — 매도 거래 포함 KB 거래내역서가 들어오면 매수+매도 함께 구현(`broker_import/kb_xlsx.py` 신규 + PARSERS + FE `BROKER_OPTIONS` 에 `kb_xlsx`/"KB증권"). 시트 `Sheet0`, 헤더 `거래일|내용|종목명|수량|단가|입금/입고/매도|출금/출고/매수|예수금잔액(원)`, 종목코드 없음(종목명 매칭). `lib/brokers.ts` "KB증권"(계좌 마스터)은 이미 존재.
- [ ] 다운로드 가이드 콘텐츠 검수 — `app/src/components/records/ImportTradesPanel/brokers.ts` 의 `downloadGuide` 는 AI 1차 초안(`TODO` 주석 표시). 삼성증권 mPOP/토스/신한 SOL증권/미래에셋 m.Stock 앱과 실제 화면 대조 후 단계 텍스트·`helpUrl` 수정. 증권사 앱 UI 개편 시 깨질 수 있어 분기별 점검 또는 사용자 신고 트리거 시 갱신. 캡처 이미지 단계 안내가 더 효과적이라 판단되면 별도 spec 으로 보강

## 거래내역서 일괄등록 고도화 — 해외주식(US/USD)

해외 주식 지원 본체(US 직접입력·KRW 통합표시·거래시점 환율 저장·US 시세/환율/검색/seed·KRW 환산 합산·FE overlay)는 모두 출시 완료(2026-06-08 Phase A·B, decisions·spec-history 기록). 이 섹션은 **일괄등록(import) 경로의 해외 잔여 작업**만 추적한다.

**확인된 토스 해외 행 구조(한 거래 = 2줄):**

```
거래일자 거래구분 종목명(종목코드) 환율 거래수량 거래대금 정산금액 단가 수수료 제세금 변제/연체합 잔고 잔액
2026.06.10 구매 게임하우스 홀딩스(KYG3731B1086) 1,518.40 1 3,006 3,006 3,006 0 0 0 1 3,036   ← KRW 환산값 + 환율
              ($ 1.98)  ($ 1.98) ($ 1.98) ($ 0.00) ($ 0.00) ($ 0.00) ($ 2.00)                  ← USD 원값
```

일자·구분·종목명·**환율(1,518.40)**·수량·KRW단가·USD단가($1.98)가 모두 존재. USD 섹션 헤더는 KRW 섹션과 달리 `거래세` 컬럼이 없다(동적 `_build_column_map` 이 흡수).

> 해외 거래 누락 silent-loss 상시 안내 배너(`PreviewStep.tsx`)는 2026-06-12 구현됨. 해외(토스 USD) 실제 등록은 2026-06-27 본구현으로 지원됨(아래).

### 본구현 — 해외 일괄등록 (US/USD)

**해외 일괄등록(토스 USD)은 2026-06-27 구현 완료** (`docs/spec-history/2026-06-27-toss-overseas-import.md`·`2026-06-27-toss-isin-matching.md`, `docs/decisions.md` 2026-06-27). 토스 달러 섹션을 USD 네이티브(`country_code=US`·`exchange_rate=행환율`·price/commission/tax÷환율)로 import + 종목 식별을 ISIN 코드 매칭(OpenFIGI)으로 전환해 종목명 매칭 시절 미해결 101→0 근본 해소.

- [ ] **토스 USD SELL 행 회귀 보강** — 파서는 구매(BUY) 행만 실샘플 검증됨(SELL 행 포맷 미관측). SELL 포함 토스 해외 거래내역서 확보 후 파싱·회귀 테스트 보강.
- [ ] **삼성증권 USD** — `samsung_xlsx.py` 동일 skip 존재. 동일 silent-loss 여부 검증 후 같은 안내 가드·본구현 적용. (삼성 USD 샘플 확보 후)

- **타 증권사 해외(USD) 준비도:** **신한**(`단가/환율`·`수량/외화`)·**미래에셋**(`환율`·`통화코드`·`외화거래금액`)·**삼성**(`외화*` 컬럼)은 포맷에 환율 컬럼은 있으나 **실제 해외 행 샘플 없음** → 해외 거래 포함 샘플 확보 후 구현·fixture. 데이터/계산 토대(per-trade `exchange_rate`·`to_krw`·`currency_for_country`·walker FX·포트폴리오 KRW 합산)는 토스 구현으로 검증 완료.

## 사용자 요청 및 추가 기능

- [ ] 목표가(%), 손절 및 익절 계획을 입력하고 그것을 지켰는지 여부를 분석
- [ ] 관심 종목 추가 (보유하지 않은 종목도 볼 수 있게)
- [ ] 보유종목 카드에 오늘 등락 표시
- [ ] 자산추이에 일, 주, 월, 6개월, 올해 1년, 5년, all 선택 표시
- [ ] 자산추이에 차트 기준점 s&p500, 코스피 지수등과 비교
- [ ] 다크 테마 추가
- [ ] 푸시 알림, 생체인증(Face ID/지문), Android 백버튼/키보드 처리
- [ ] iOS 상태바 색 동기화 — @capacitor/status-bar 도입 후 다크/라이트 전환 시 status bar style 동기화

## v2 — UX

- [ ] 홈 위젯 커스터마이징

## v2 — 성능 / 스케일

- [ ] trades 페이지네이션 (BE+FE 동반) — `GET /trades` 에 cursor/limit 도입 + records 화면 `useInfiniteQuery` 무한스크롤. records 가 현재 전량 fetch 후 메모리 group-by-date / account filter 구조라, 페이지네이션 시 그룹핑·`allTrades` (상세 패널) ·`accounts` 응답 분리까지 함께 재설계 필요. 트리거: 거래 수 분포 측정에서 첫 페인트/메모리 영향이 체감되면 도입. ticker SQL push (2026-05-03 `docs/spec-history/2026-05-03-be-simplify-trades-ticker-sql-push.md`) 로 HoldingsList 측은 이미 행 수만 fetch 중.
- [ ] 포트폴리오/분석 읽기 경로 전량 로드 최적화 (2026-05-26 API 성능 분석 #4) — `GET /portfolio/summary`·`GET /analysis/dashboard` 가 매 호출마다 사용자 전체 거래를 `SELECT *` 로 로드하고 row 마다 `Trade(**dict(row))` Pydantic 검증을 돈다. 거래 누적 시 O(전체 거래수)로 선형 악화. 작업: ① 계산에 안 쓰는 텍스트 컬럼(`reflection_note`/`buy_reason`/`sell_reason`/`improvement_note` 등)을 `SELECT` 목록에서 제외, ② 읽기 전용 경로는 `Trade.model_construct(**dict(row))` 로 검증 스킵(DB 데이터 신뢰), ③ 위 trades 페이지네이션과 연계해 분석/요약 계산을 증분화 가능한지 검토. 트리거: 헤비 유저(대량 시드/실데이터)에서 응답시간·메모리 체감 또는 `pg_stat_statements` 의 rows/평균시간 상승. 측정 없이 선제 적용 시 micro-opt 수준.

## v3 — AI 분석

- [ ] 매매 패턴 분석 고도화 (감정-결과 상관관계 등)
- [ ] AI 기반 복기 제안
- [ ] 모바일 네이티브 앱 (React Native / Expo) 검토
