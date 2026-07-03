# 백로그

MVP 이후 구현할 작업 후보 목록.

> 정리 이력: 2026-07-03 완료항목 제거(다크 테마·iOS 상태바·eslint 잔여 warnings — 모두 완료) + 우선순위 스냅샷 추가 + 영역 재정렬.

## 우선순위 스냅샷 (다음 착수 후보)

- 🟡 **사용자 요청 기능** — 목표가/손절·익절 추적, 관심종목, 자산추이 기간선택, 벤치마크 비교, 푸시/생체인증/백버튼.
- 🟡 **임포트 후속** — 다계좌 이중 preview 최적화(BE `re-validate` 엔드포인트 도입 시 카운트 갭까지 동시 해소), provider db 복귀 모니터링.
- 🟢 **운영/어드민** — KIS 앱키 만료 가시화(SPOF), PnL 저장값 검증 엔드포인트.
- 🟢 **성능/스케일(측정 후 착수)** — trades 페이지네이션, 포트폴리오/분석 읽기 경로 최적화, 분석 대시보드 시세 분리.

---

## 사용자 요청 및 추가 기능

- [ ] 목표가(%), 손절 및 익절 계획을 입력하고 그것을 지켰는지 여부를 분석 — **(2026-07-02 감사) 부분:** 전략(strategy_type) 준수 분석은 이미 구현됨(`analysis/StrategyAdherencePanel.tsx` — 실보유기간 자동추론 vs 입력 전략 비교). **미구현이 이 항목의 핵심:** 거래/종목에 목표가·손절가·익절가 필드·입력 폼·달성/이탈 추적이 전무(스키마·폼에 target_price/stop_loss/take_profit 없음).
- [ ] 관심 종목 추가 (보유하지 않은 종목도 볼 수 있게) — (2026-07-02 감사) 미구현 확인(watchlist 테이블·API·컴포넌트 전무).
- [ ] 자산추이에 일, 주, 월, 6개월, 올해 1년, 5년, all 선택 표시 — **(2026-07-02 감사) 부분:** 분석 탭엔 기간 선택 존재(`lib/constants/analysis.ts` Period 1m/3m/6m/ytd/all — 재사용 가능 패턴). **자산추이 뷰(`assets/AssetHistoryView.tsx`)엔 기간 선택 없음**(전체 역사만) → 이 항목 대상.
- [ ] 자산추이에 차트 기준점 s&p500, 코스피 지수등과 비교 — (2026-07-02 감사) 미구현 확인(benchmark/지수 오버레이 코드 전무, 차트는 단일 asset 곡선만).
- [ ] 푸시 알림, 생체인증(Face ID/지문), Android 백버튼/키보드 처리 — **(2026-07-02 감사) 부분:** 푸시(`@capacitor/push-notifications`)·생체인증 플러그인 미설치. 키보드는 `@capacitor/keyboard` `resize:Native`만 설정(show/hide 이벤트 처리 없음), 백버튼은 `ForceUpdateGate.tsx`에서 강제업데이트 오버레이용 swallow만 존재 → **일반 네비게이션 백버튼 핸들러 없음**.

## 거래내역서 임포트 — 후속 과제

- [ ] **다계좌 자동매칭 시 이중 preview 최적화 (2026-07-01, 활성화 feature 후속)** — 계좌가 2개 이상이고 파일 계좌번호가 기존 계좌와 매칭되면, import 흐름이 `preview(account 없이)`(account_hint 확보·매칭용) → `preview(account_id)`(oversell/카운트 scoped) 로 **파일을 2회 파싱**(해외는 OpenFIGI 재실행 포함)하고 staging 행도 2개 생성(첫 행 orphan, TTL 정리). 단일계좌 경로는 이미 1회로 최적화됨. 근본 해소는 BE 에 `re-validate(staging_id, account_id)`(재파싱 없이 기존 staging 을 계좌 기준 재검증) 엔드포인트가 필요 → FE 만으로는 불가라 이번 스코프 밖. 참조: `docs/decisions.md` 2026-07-01. (기존 "import preview 그룹 검증 중복 제거" 항목과 함께 재설계 검토)
- [ ] **다계좌 재수입 preview↔result 카운트 갭 (2026-07-01, 알려진 한계)** — `new_count`/`duplicate_count` 는 account 무관 BE 근사 dedup 이라, 보유가 있는 **기존 계좌에 재수입**할 때 preview 의 "신규 등록" 카운트(버튼 라벨)와 실제 commit `inserted_count` 가 어긋날 수 있음(commit 데이터 자체는 정확). 활성화 타깃(0계좌 신규·dup 0)에선 정확. oversell 은 계좌 확정 후 scoped 재-preview 로 이미 반영됨. 정확한 preview 카운트는 위 `re-validate` 엔드포인트 도입 시 함께 해소 가능.
- [ ] **종목 검색 provider db 복귀 + import/NPS stale 추적** (2026-06-03 Naver 임시 복귀, `docs/decisions.md` 참고) — data.go.kr 게이트웨이(~50% 성공률) 안정성 모니터링 후 `STOCK_SEARCH_PROVIDER=db` 로 복귀(코드 변경 없이 env 한 줄). **잔여 리스크:** 검색만 토글했으므로 seed 를 장기 중단하면 거래 import 매칭(`ticker_resolver.lookup_by_names`)·NPS(`stocks_repo.search`)·marcap 이 stale 로컬 stocks 에 의존해 조용히 낡음. 트리거: ① seed 게이트웨이 성공률 안정화 확인 시 db 복귀, 또는 ② import 매칭률 저하/NPS·시총 stale 체감 시 seed 재개 우선순위 상향.
- [ ] 공급자 env 토글 제외 잔존 — data.go.kr 고정 의존 (2026-06-07 env registry 도입, `docs/decisions.md` 참고) — 교차검증은 2026-06-07 KIS 트랙 1 에서 `CROSSVALIDATE_PROVIDER`(naver|kis) 토글로 **해소**. `update_marcap`(data.go.kr)만 고정 단계로 잔존 — KIS 는 bulk 시총 API 가 없어 종목별 호출 필요. 기본 유량 18건/초 기준 전종목 4,300콜≈4분 심야 cron 으로 **가능은 해짐**(2026-06-07 재평가)이나, data.go.kr 는 bulk 2콜로 같은 일을 하고 시총은 하루 stale 무해(실패 시 기존값 보존)라 평시 전환은 비권장 — **data.go.kr 장애 장기화 시 대체선**으로만(신규 fetcher 구현 필요). ⚠️ `CROSSVALIDATE_PROVIDER=kis` 전환 시 KONEX 종목이 대조 없이 "검증됨"으로 박제됨(마스터 파일에 KONEX 없음, `naver_checked_at` 공유 컬럼) — 전환 전 인지 필요. 트리거: data.go.kr 시총 경로 장애 장기화 시 marcap 대체 재검토.
- [ ] 미해결 종목 수동 매칭 UI — Naver 자동매칭 실패 또는 부분일치 오매칭 케이스에 대비, PreviewStep에서 사용자가 직접 종목 검색하여 매칭하는 UI 추가 검토
- [ ] import preview 그룹 검증 중복 제거 (2026-05-26 API 성능 분석 #5) — `import_preview` 가 `account_id` 를 받으면 `_validate_import_groups` 가 commit 과 동일한 그룹별 `list_trades_in_group` + oversell 검증을 한 번 더 수행한다(`routers/trades.py` 의 preview 경로). 그룹 수가 많은 파일일수록 preview 에서 N회 추가 쿼리. 작업: preview 의 dedup 용 date-range fetch 결과를 재활용하거나, 정합성(oversell) 검증을 commit 단계로 일원화하고 preview 는 참고용 카운트만 노출. 주의: preview 단계에서 사용자에게 위반을 미리 보여주는 UX 가치가 있으므로 제거 전 FE 노출 동작 확인 필요.
- [ ] 머지 갱신 범위 확장 재검토 — 현재 머지는 `commission`/`tax`/`traded_at` 만 update, `market_type`/`country_code`/`exchange` 는 사용자 분류를 우선해 **보존**(`docs/decisions.md` 2026-05-18 참고). 다음 트리거 발생 시 재검토: ① 사용자가 거래내역서로 분류 자동 보정을 명시적으로 원함, ② 증권사 파서가 사용자 수동 분류보다 더 정확한 케이스가 다수 보고됨. 재검토 시 `update_trade_from_import` 화이트리스트와 `build_merge_patch` 비교 필드를 함께 확장
- [ ] **KB증권 파서 — 매도 포함 샘플 확보 후 구현 (2026-06-25 보류)** — 신한·미래에셋과 함께 추가하려 했으나 제공된 KB 샘플(`거래내역서_KB증권_1.xlsx`)에 **매수 행만** 있어 매도(`주식장내매도`/`KOSDAQ매도`, 금액=`입금/입고/매도` 컬럼) 포맷을 회귀 검증할 수 없음. 추정 구현 금지 — 매도 거래 포함 KB 거래내역서가 들어오면 매수+매도 함께 구현(`broker_import/kb_xlsx.py` 신규 + PARSERS + FE `BROKER_OPTIONS` 에 `kb_xlsx`/"KB증권"). 시트 `Sheet0`, 헤더 `거래일|내용|종목명|수량|단가|입금/입고/매도|출금/출고/매수|예수금잔액(원)`, 종목코드 없음(종목명 매칭). `lib/brokers.ts` "KB증권"(계좌 마스터)은 이미 존재.
- [ ] 다운로드 가이드 콘텐츠 검수 — `app/src/components/records/ImportTradesPanel/brokers.ts` 의 `downloadGuide`. **2026-07-02 검수:** ① description(문서명)·accept(형식)는 파서 docstring·`sample/` 실제 export 파일명과 대조 완료 — 삼성 "기간별 매매내역서"→**"거래내역서"**, 미래에셋 "거래내역서"→**"거래내역증명서"** 수정. ② 삼성 steps 는 **PC 웹(samsungpop.com) 엑셀 다운로드**로 정정(모바일 mPOP 엔 xlsx 내보내기 없음, 파서도 xlsx 전용). ③ 토스 steps 는 공식 FAQ(support.toss.im/faq/3331)의 **앱 경로**(홈→우측상단 삼단바→설정→계좌관리→증명서 발급하기→'거래 내역서')로 정정 — PC 웹으로도 받을 수 있으나 모바일 앱 흐름이 우리 앱에 적합. **남은 것:** **신한·미래에셋 steps(앱 메뉴 경로) 미검수** — 계정 없어 캡처 대기. 증권사 UI 개편 시 깨질 수 있어 분기별 점검 또는 사용자 신고 트리거 시 갱신. 캡처 이미지 단계 안내가 더 효과적이라 판단되면 별도 spec 으로 보강

### 거래내역서 원장(ledger) — 배포 및 후속 (2026-07-03)

원장 기능(캡처/물질화 2-스테이지·append-only·등록 마커·날짜 파일거절) 구현 완료(`docs/decisions.md` 2026-07-02·07-03, `docs/spec-current.md`, 마이그레이션 `0014`, 유닛 959 + 격리 realdb 8 통과). 아래는 **배포 시/배포 후** 진행 항목 — feature 동작엔 영향 없음.

- [ ] **`0014` 마이그레이션 운영 적용 (배포 시)** — `import_batches` / `import_ledger_entries` / `trades.source_ledger_entry_id`. 현재 "작성만"·미적용. 적용은 일상 경로(invest_note_app, superuser 불요). 참조: [[project_alembic_migrations]].
- [ ] **R2 lifecycle 규칙 설정 (배포 시, 수동 Ops)** — Cloudflare R2 콘솔에서 **prefix `import_source/` 90일 만료** 규칙 추가. ⚠️ 버킷 전체 아님(OTA 매니페스트·`broker_statement/` 제보 첨부와 공유) — prefix 스코프 필수. 현재 storage_key 를 읽는 코드는 없음(다운로드 엔드포인트 부재).
- [ ] **`import_staging`(0010) drop (배포 후)** — 원장이 대체해 dead 상태(라우터 참조 이미 제거). 별도 리비전 `0015` 로 DROP + `db_ops/import_staging_repo.py`·`tests/test_import_staging_repo.py`·잔존 import 정리. 운영 적용 테이블이라 위험 분리해 배포 후 진행.
- [ ] **개인정보처리방침에 내역서 원본/파싱본 수집·보유기간(90일) 명시** — 위 "PIPA 개인정보처리방침 갱신" 항목과 함께 진행. 내역서 **원본 파일(R2, 90일)** + **파싱 원장 rows** 수집을 처리방침(`freshope.github.io/invest-note-legal`)·Play Data Safety·App Store privacy 라벨에 반영.

### 일괄등록 고도화 — 해외주식(US/USD)

해외 주식 지원 본체(US 직접입력·KRW 통합표시·거래시점 환율 저장·US 시세/환율/검색/seed·KRW 환산 합산·FE overlay)는 모두 출시 완료(2026-06-08 Phase A·B, decisions·spec-history 기록). 이 섹션은 **일괄등록(import) 경로의 해외 잔여 작업**만 추적한다.

**해외 일괄등록(토스 USD)은 2026-06-27 구현 완료** (`docs/spec-history/2026-06-27-toss-overseas-import.md`·`2026-06-27-toss-isin-matching.md`, `docs/decisions.md` 2026-06-27). 토스 달러 섹션을 USD 네이티브(`country_code=US`·`exchange_rate=행환율`·price/commission/tax÷환율)로 import + 종목 식별을 ISIN 코드 매칭(OpenFIGI)으로 전환해 종목명 매칭 시절 미해결 101→0 근본 해소.

- [ ] **토스 USD SELL 행 회귀 보강** — 파서는 구매(BUY) 행만 실샘플 검증됨(SELL 행 포맷 미관측). SELL 포함 토스 해외 거래내역서 확보 후 파싱·회귀 테스트 보강.
- [ ] **삼성증권 USD** — `samsung_xlsx.py` 동일 skip 존재. 동일 silent-loss 여부 검증 후 같은 안내 가드·본구현 적용. (삼성 USD 샘플 확보 후)
- **타 증권사 해외(USD) 준비도:** **신한**(`단가/환율`·`수량/외화`)·**미래에셋**(`환율`·`통화코드`·`외화거래금액`)·**삼성**(`외화*` 컬럼)은 포맷에 환율 컬럼은 있으나 **실제 해외 행 샘플 없음** → 해외 거래 포함 샘플 확보 후 구현·fixture. 데이터/계산 토대(per-trade `exchange_rate`·`to_krw`·`currency_for_country`·walker FX·포트폴리오 KRW 합산)는 토스 구현으로 검증 완료.

## 운영 / 어드민 도구

- [ ] **PIPA 개인정보처리방침 갱신 (탈-Supabase Auth 후속, 사용자 별도 진행)** — `user_profiles` PII 수집 확대(email·이름·아바타·provider·email_verified·가입일·최근로그인)에 맞춰 개인정보처리방침(`freshope.github.io/invest-note-legal`) / Play Data Safety(Android) / App Store privacy 라벨 갱신. 기존 PostHog 고지 항목과 연동. (PII 수집 코드는 완료, 공개 정책 문구만 미갱신)
- [ ] **KIS 앱키 만료·로테이션 가시화 (어드민 페이지에서 확인)** — 2026-06-08 조사. **문제:** KIS 앱키는 발급 1년 후 만료, 만료 30일 전부터 갱신 가능하고 **갱신=APP Key/APP Secret 재발급**(기존 값 연장이 아니라 새 값, KIS 공식 이용안내·wikidocs 확인). 즉 1년마다 시크릿 로테이션이 강제된다. 현재는 `KIS_APP_KEY`/`KIS_APP_SECRET` **env 단일 전역 키**(`kis_tokens.scope='app'` 고정)이고 **만료 감지/알림 코드 전무** → 만료 누락 시 `_issue_token()` 전면 실패 → 시세·일별종가 전체 장애(SPOF). 또 단일 키라 로테이션 시 env 교체+Coolify 재시작 사이 시세 공백 불가피(무중단 불가). **확인된 사실:** ① 유량 제한 단위 = 앱키(=계좌), 공식 기본 18건/초 — 다중 앱키 발급이 유량 확장 + 로테이션 무중단(키 A 교체 중 키 B 유지)의 공식 우회로, ② 갱신은 재발급이라 만료일을 코드가 알 수 없음 → 운영자가 만료일을 명시 등록해야 D-day 산출 가능. **미확인(도입 전 KIS 확인 필요):** ① 갱신 직후 기존 키가 만료일까지 유효한지(유효하면 사전 갱신→교체로 무중단 가능, 무효화되면 점검창 필수), ② 유량 회피 목적 다중 앱키가 약관 허용인지. **방향(2026-06-08 결정):** 별도 어드민 페이지를 신규 구축해 거기서 만료 D-day·토큰 상태·최근 발급실패를 **확인**. 키 등록/교체(hot-swap)·멀티키까지 "관리"로 확장할지는 별도 결정 — 그 경우 키·만료일을 DB 저장(시크릿 암호화+서비스롤만 접근) 전제. 미사용 X-Admin-Token 트리거 인프라는 2026-07-01 제거됨(어드민 패널 CRUD `routers/admin.py` 는 유지) — 어드민 페이지 신설 시 `require_admin`(JWT+allowlist) 게이트 위에 엔드포인트 추가.
- [ ] PnL 저장값 검증 엔드포인트 (이슈 E) — `/admin/verify-pnl` 신설. SELL의 저장된 `profit_loss`/`avg_buy_price`/`holding_days`/`strategy_type`/`reasoning_tags`/`emotion`을 `compute_group_pnl()`로 재계산해 차이 검출. 사용자 단위 batch + 차이 리포트 + (옵션) 자동 보정. 권한은 admin scope. DB 직접 수정·마이그레이션 누락·mutation 경로 우회 시 분석 탭과 거래 기록 합계 불일치를 잡기 위함.

## 분석 탭 성능 / 유지보수

- [ ] 분석 대시보드 시세 분리 (옵션 B 동일 패턴) — `/analysis/dashboard` 도 요청 안에서 시세를 동기 fetch(concentration 계산용, `fetch_quotes_by_keys`)한다. 2026-05-27 `/portfolio/summary` 분리(`docs/decisions.md` 참고)와 동일하게 `withQuotes` opt-in + FE overlay 적용 검토. 단 concentration(HHI/top3/비중)은 시세 없으면 `cost_basis` fallback 이라 FE 로 옮기려면 concentration 계산까지 FE 중복이 필요 → 표면적이 summary 보다 큼. 트리거: summary 분리 효과 확인 후, 또는 분석 탭 응답 지연 체감 시.
- [ ] 분석 API 쿼리 `.limit(1000)` 가드 — 거래 수 급증 시 메모리/응답 보호
- [ ] 수수료 현황 별도 패널 — BUY commission·세금 합계, 순실현손익 vs 총비용 비교
- [ ] `_rule_high_winrate` 신뢰도 게이트 재검토 — 2026-05-20 `result_input_rate` 게이트 제거 후 현재 `sell_trades >= MIN_HIGH_WINRATE_SELL` + `win_rate >= WIN_THRESHOLD` 만으로 트리거. 실 데이터에서 인사이트가 과도하게 트리거되면 별도 신뢰도 메트릭(SELL 매칭률 등) 도입 검토. 트리거: 사용자 피드백 또는 인사이트 노출 빈도 모니터링에서 노이즈 체감.

## v2 — UX

- [ ] 홈 위젯 커스터마이징

## v2 — 성능 / 스케일

- [ ] trades 페이지네이션 (BE+FE 동반) — `GET /trades` 에 cursor/limit 도입 + records 화면 `useInfiniteQuery` 무한스크롤. records 가 현재 전량 fetch 후 메모리 group-by-date / account filter 구조라, 페이지네이션 시 그룹핑·`allTrades` (상세 패널) ·`accounts` 응답 분리까지 함께 재설계 필요. 트리거: 거래 수 분포 측정에서 첫 페인트/메모리 영향이 체감되면 도입. ticker SQL push (2026-05-03 `docs/spec-history/2026-05-03-be-simplify-trades-ticker-sql-push.md`) 로 HoldingsList 측은 이미 행 수만 fetch 중.
- [ ] 포트폴리오/분석 읽기 경로 전량 로드 최적화 (2026-05-26 API 성능 분석 #4) — `GET /portfolio/summary`·`GET /analysis/dashboard` 가 매 호출마다 사용자 전체 거래를 `SELECT *` 로 로드하고 row 마다 `Trade(**dict(row))` Pydantic 검증을 돈다. 거래 누적 시 O(전체 거래수)로 선형 악화. 작업: ① 계산에 안 쓰는 텍스트 컬럼(`reflection_note`/`buy_reason`/`sell_reason`/`improvement_note` 등)을 `SELECT` 목록에서 제외, ② 읽기 전용 경로는 `Trade.model_construct(**dict(row))` 로 검증 스킵(DB 데이터 신뢰), ③ 위 trades 페이지네이션과 연계해 분석/요약 계산을 증분화 가능한지 검토. 트리거: 헤비 유저(대량 시드/실데이터)에서 응답시간·메모리 체감 또는 `pg_stat_statements` 의 rows/평균시간 상승. 측정 없이 선제 적용 시 micro-opt 수준.

## v3 — AI 분석

- [ ] 매매 패턴 분석 고도화 (감정-결과 상관관계 등)
- [ ] AI 기반 복기 제안
- [ ] 모바일 네이티브 앱 (React Native / Expo) 검토
