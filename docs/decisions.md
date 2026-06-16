# 기술 결정 로그

중요한 설계/기술 선택 기록. "왜 이렇게 했지?"를 다시 묻지 않기 위해.

---

## 2026-06-16 | Supabase DB 종속성 제거 — RLS를 표준 PostgreSQL 객체로 치환 (무중단 expand/contract)

- **맥락:** DB를 다른 PostgreSQL로 바로 교체하면 Supabase 고유 객체(`auth.uid()`, `auth.users`, `authenticated` 역할, `request.jwt.claims` GUC)가 딸려와 지저분해진다. Supabase를 유지한 채 DB 레이어가 이들에 의존하지 않도록 자체 `public` 객체로 옮겨, 이후 DB만 lift-and-shift 하면 깨끗이 이관되게 한다. **DB 종속성 축만** 대상이고 Supabase **Auth(JWT/OAuth)는 유지** — FE `@supabase`·BE JWKS 검증·계정삭제 Admin API 무변경. `2026-04-22 RLS GUC 주입` 결정을 대체.
- **결정:**
  - ① **치환 매핑(1:1).** `auth.uid()`→`public.current_user_id()`(= `nullif(current_setting('app.current_user_id',true),'')::uuid`, 미설정 시 NULL→fail-closed) / `request.jwt.claims`·`role` GUC→`app.current_user_id` 단일 GUC / Supabase `authenticated` 역할→자체 `app_authenticated`(nologin, `grant ... to postgres`로 SET ROLE) / `auth.users(id)` FK→`public.users(id)`(id+created_at, 신원은 Auth 소유, `acquire_for_user`가 첫 요청 시 owner로 프로비저닝).
  - ② **owner-only 테이블 패턴 유지.** `public.users`·`kis_tokens` 는 RLS enable+정책 없음 → `app_authenticated` 전면 차단, owner(postgres)만 통과. 프로비저닝·계정삭제·재백필은 owner 컨텍스트.
  - ③ **무중단 expand/contract 2단계.** 하드 컷오버 시 마이그레이션~신 BE 배포 사이 구간에서 구 BE가 `app.current_user_id`를 몰라 새 정책에서 fail-closed(읽기 0건·쓰기 500)로 깨진다. expand(`033`, BE와 함께 배포): 역할/함수/`public.users` 추가 + 정책을 `auth.uid() OR current_user_id()` 양쪽 허용 + FK는 `auth.users` 유지 → 구·신 BE 동시 동작·롤백 안전. contract(`migrations_pending/034`, 신 BE 라이브 확인 후 `migrations/`로 이동해 push): FK 재지정 + `auth.uid()` 분기 제거로 디커플 완료.
- **이유:** 앱은 `WHERE user_id` 없이 RLS로 격리(2026-04-22 설계)하므로 RLS 제거는 ~30 호출부 전 쿼리 감사·데이터 유출 위험. 대신 enforcement 메커니즘만 Supabase 제공→자체 객체로 바꾸면 보안 모델·쿼리 변경 최소. 정책 내 `auth.uid()`는 정책 생성 시점(postgres)에 파싱돼 런타임엔 EXECUTE(public)만 확인 → `auth` 스키마 USAGE 없는 `app_authenticated`도 OR 정책 평가 정상(로컬 실증). expand/contract로 무중단·롤백안전 확보.
- **트레이드오프:** ① 마이그레이션 2단계·임시 이중 정책(OR)·`migrations_pending/` 수동 이동 절차. contract 적용 후 구 BE 롤백 불가(신 BE 안정이 전제). ② 마이그레이션 도구는 여전히 supabase CLI — DB 실이관·도구 교체는 Phase 2. ③ 운영 적용 시 클라우드에서 `create role`/`grant` 권한 통과 확인 필요(postgres CREATEROLE 보유). ④ `kis_token_store.py` 주석의 "authenticated role" 표현은 이제 `app_authenticated`이나 의미 유효(미수정).

---

## 2026-06-14 | 사용자 정의 분석 태그 — 레지스트리 테이블 + 거래엔 라벨 저장(디커플링), reasoning_tags 미러링

- **맥락:** 분석 태그가 고정 ENUM `reasoning_tags` 4종(TECHNICAL/FUNDAMENTAL/NEWS/FEELING)뿐이라 사용자가 자기 분류(배당·테마주 등)를 못 남겼다. 자유 텍스트 사용자 태그를 추가하되, ENUM 구조·SELL 자동상속·분석 집계와 정합을 유지해야 했다.
- **결정:**
  - ① **프리셋 ENUM 유지 + 자유텍스트 평행.** 기존 `reasoning_tags reasoning_tag[]` 는 그대로 두고 `trades.custom_tags text[]` 컬럼을 평행 추가(비파괴적). 프리셋은 타입드 집계(`by_tag`/UNTAGGED 버킷)를 보존, 커스텀은 문자열 버킷(`by_custom_tag`, UNTAGGED 없음)으로 분리.
  - ② **레지스트리 테이블(`custom_tags`) = 선택 카탈로그, 거래엔 라벨(text) 저장.** 사용자가 만든 태그는 별도 테이블(id/user_id/label, RLS)에 영속(거래 부착 없이도). 거래는 id FK 가 아니라 **라벨 문자열**을 저장 → 레지스트리에서 태그를 삭제해도 과거 거래 라벨·분석은 불변. 등록/수정 폼은 프리셋 4종 + 레지스트리 태그를 한 그리드에 노출하고 `+` 바텀시트로 생성/삭제.
  - ③ **reasoning_tags 파이프라인 전체 미러링.** BUY 입력 → SELL 자동상속(`_meta_from_consumed_latest`·`FifoLot`·`GroupPnLEntry`·`pnl_sync`·`TRADE_FIELD_META.sell_auto_derived`) → 분석 집계(`by_custom_tag`)를 동일 패턴으로 복제. 분석이 SELL 기준 집계라 커스텀 태그도 SELL 에 실려야 하므로 auto-derive 가 필수.
  - ④ **생성 멱등 + 자동 선택.** `POST /trades/custom-tags` 는 `ON CONFLICT(user_id,label) DO UPDATE…RETURNING` 으로 1쿼리 멱등. 바텀시트에서 새 태그 저장 시 현재 편집 거래에 자동 선택.
- **이유:** ENUM 은 런타임 확장 불가라 자유 텍스트는 별도 컬럼 필수. 거래에 id 대신 라벨을 저장하면 레지스트리 라이프사이클(삭제/정리)과 과거 데이터·분석을 디커플 — "삭제했더니 과거 거래 분석이 깨졌다"를 원천 차단. 미러링은 검증된 기존 파이프라인 재사용이라 새 join 발명보다 저위험.
- **트레이드오프:** 컬럼·집계·폼 필드가 reasoning/custom 2벌로 늘어 표면적 증가(3종째 태그가 생기면 3배). 라벨 저장이라 레지스트리 rename 이 과거 거래에 소급 안 됨(의도 — 분석 안정성 우선). 태그 rename/사용건수/미사용 정리 UX 는 이번 범위에서 제외.

---

## 2026-06-12 | PostHog 제품 분석 도입 — FE 전용·Cloud·정적 export instrumentation-client·민감값 보호

- **맥락:** 사용자가 어떤 화면을 쓰고 어떤 기능에 도달하는지 알 수 있는 analytics 가 전무했다. 제품 의사결정 근거를 위해 PostHog 도입. 핵심 제약은 앱이 순수 웹이 아니라 `next.config output:"export"` 정적 빌드를 Capacitor 웹뷰(iOS `capacitor://localhost`, Android `https://localhost`)로 패키징한 모바일이라는 점.
- **결정:**
  - ① **PostHog Cloud + FE 클라이언트 전용**(BE 서버사이드 추적 없음). 정적 export 라 Next.js rewrite reverse-proxy 불가 → 클라이언트가 PostHog host 로 직접 전송. `api_host` 는 `NEXT_PUBLIC_POSTHOG_HOST`(기본 us).
  - ② **init 진입점 = `app/src/instrumentation-client.ts`**(Next 15.3+ 클라이언트 전용 파일, 자동 로드). 정적 export 빌드에서 모든 페이지 HTML 이 이 청크를 참조함을 빌드로 검증(단일 의존점 — 안 실리면 조용히 no-op 인데 tsc/build 는 통과하므로 사전 확인 필수). 폴백은 useEffect provider.
  - ③ **키 없으면 전체 no-op** — `NEXT_PUBLIC_POSTHOG_KEY` 빈값이면 init·모든 헬퍼가 건너뜀. 로컬/CI 키 없이 빌드·동작(`POSTHOG_ENABLED` 단일 판정, app-config.ts 빈 env 패턴 차용).
  - ④ **금융 민감값 보호**: autocapture·session recording off, identify 는 UUID 만(email 등 person property 금지), 커스텀 이벤트는 명시 필드만(종목/티커/금액/수량/가격/수수료/세금/환율/계좌명 전송 금지). 2중 방어 `property_denylist`(키 차단) + `before_send`(런타임 scrub). persistence "localStorage"(웹뷰 쿠키 불안정), person_profiles "identified_only"(익명 프로필·MAU·PII 축소).
  - ⑤ **수동 페이지뷰** `usePathname`(`useSearchParams` 는 정적 export Suspense 경계 강제 → 금지). 유저 식별은 `PostHogIdentifyBridge`(AuthProvider 미수정, 관심사 분리).
  - ⑥ **environment·project super property** — 모든 이벤트에 `environment`(`NEXT_PUBLIC_POSTHOG_ENV` 우선, 없으면 NODE_ENV)·`project`("invest-note") 부착해 PostHog 필터로 dev/prod·앱 구분. dev local 에도 키가 있어 로컬 검증 이벤트는 development 로 분리.
  - 커스텀 이벤트 3종: `trade_recorded`·`trades_imported`·`account_added`.
- **트레이드오프:** FE 전용이라 서버사이드 이벤트(import 실패 원인 등)는 미수집 — 필요 시 BE 확장. capture_pageleave 는 켜두되 모바일 웹뷰는 unload 불안정(백그라운드 전환)이라 세션 시간 신뢰도 낮음. 출시 전 개인정보 고지(처리방침·스토어 라벨·PIPA)는 코드 외 별도 작업으로 분리(backlog).

---

## 2026-06-12 | US S&P500 편입 뱃지 — us_index 메타 + /stocks/meta 무국가 단일 쿼리(format-inference)

- **맥락:** US 종목에 'S&P 500' 편입 뱃지(KR "시총 N위" 대칭)를 추가하려면 `stocks.us_index`('SP500')를 `/stocks/meta` 로 노출해야 한다. 기존 `fetch_meta` 는 `where country_code=$1 and ticker=any($2)` 로 KR 고정이라, US 코드도 조회되게 country 를 다뤄야 했다. 선택지: ① `country` 쿼리 파라미터 추가, ② 코드 포맷으로 국가 추론(무분기 단일 쿼리).
- **결정:** ② **format-inference.** `fetch_meta(conn, codes)` 에서 country 인자 제거, `where ticker = any($1)` 단일 쿼리. KR 티커(정확히 6자리 숫자)와 US 티커(선두 알파벳 + `.`/`$`)가 **disjoint** 라 한 쿼리로 KR/US 를 함께 매칭한다. FE 게이트도 `isKrStockCode` → `isMetaCode`(`/^\d{6}$/` 또는 `/^[A-Z][A-Z.$]*$/`)로 일반화 — 이 게이트가 4개 호출처에서 US 를 차단하던 게 숨은 작업량이었다. 뱃지 라벨은 `{SP500:'S&P 500'}` 매핑 + `?? usIndex` 폴백(미지 인덱스도 안 깨짐).
- **이유:** codes 는 bare ticker(국가 접두 없음) 라 country 파라미터를 추가하면 FE 가 코드별 국가를 따로 실어 보내야 한다. 포맷이 이미 disjoint 라 추론이 더 단순하고 호출부 변경이 적다.
- **트레이드오프:** "KR=6자리 숫자 / US=비숫자" disjoint 가정에 의존한다. 6자리 숫자 US 티커나 비숫자 KR 티커가 생기면 깨지므로 그때는 country 분기로 전환해야 한다(현 거래소 심볼 체계상 충돌 없음). 부수효과: US 메타를 처음 fetch 하게 되어, exchange 미기록 수기 US 거래도 `meta.market` 으로 상장시장 뱃지가 노출된다(정보상 정확, 의도 수용).

---

## 2026-06-11 | 안내문구 노출 — 중립=Info 아이콘+바텀시트, 경고/에러=인라인 유지 (공유 InfoHintSheet)

- **맥락:** 자산추이 헤더가 금액/날짜 아래에 중립 설명(예수금 제외·환율 환산 기준)을 항상 인라인으로 깔아 시각적 잡음. 아이콘+바텀시트로 정리하면서 "안내문구를 전부 숨길지"가 쟁점 — 자산추이 문구는 성격이 둘로 갈린다.
- **결정:**
  - ① **중립 설명만 아이콘 뒤로, 경고/에러는 인라인 유지.** 중립(예수금 제외·환율 환산 기준 — 숫자는 정상, "이런 의미예요")은 금액/날짜 우측 lucide `Info` 아이콘 → `base/Drawer` 바텀시트로 이동. 경고/에러(환율 미상=환산 불가, incomplete=시세 보정값 포함 — 화면 숫자가 빠졌거나 보정됐다는 신호, fall 색)는 인라인 유지.
  - ② **공유 컴포넌트 `InfoHintSheet`(`components/shared/`) 신설.** `StockMetaBadges` 의 Drawer 패턴을 일반화(`items: {title?, description}[]`). 단 `StockMetaBadges` 의 `stop()`/`display:contents`/오버레이 직접 dismiss 는 *클릭 가능한 카드 안 중첩* 때문에 필요한 것이라, 단독 트리거인 자산추이/홈 헤더엔 복사하지 않음(평범한 Drawer 트리거).
  - ③ **홈 fxBasis 동일 적용.** 홈의 중립 "환율 … 기준 · 시각"(투명성 표시)도 아이콘+시트로 통일. `HomeDashboard` 가 fxBasis 를 `fxNote`(중립)/`fxWarning`(환율 미상) 으로 분리해 `DashboardBody` 에 전달 — 중립은 시트, 경고는 인라인.
- **이유:** 경고를 아이콘 뒤로 숨기면 사용자가 "환율 확인 중"이나 이상한 숫자만 보고 이유를 모른다. 요청문("예수금 제외나 환율등")도 액면상 중립 설명만 가리킨다.
- **트레이드오프:** "다른 곳 동일 적용" 범위를 자산추이 + 홈 중립 fxBasis 로 한정. 홈/분석의 경고류 배지(fxMissing·MissingQuoteBadge=평가액 제외)는 *경고 인라인 유지* 원칙상 시트 대상이 아니라 미적용 — "동일성" 타깃이 생각보다 적음. 홈 fxBasis 는 헤더 금액 우측이 아닌 기존 footer 슬롯 자리에 아이콘을 둠(최소 침습, 총자산 옆 이동 안 함).

---

## 2026-06-11 | 자산추이 해외(US) KRW 환산을 BE 로 일원화 + spot 일괄

- **맥락:** `/assets/history` 가 `country` 기본값 `'KR'` 로 single-country 스코프라 전체/계좌뷰(ticker=None)가 US 보유를 통째로 제외 — 같은 화면 대시보드 합계(`merge_quotes(usdkrw)` + FE overlay)는 US 포함이라 **두 수치가 어긋남**(code-review finding A). 종목뷰만 FE(`asset-history-convert.ts`+`useFxRate`)가 현재 환율로 부분 환산하던 비대칭 구조.
- **결정:**
  - ① **환산 책임을 FE → BE 로 이관.** `compute_asset_history` 가 `usdkrw` 인자를 받아 종목별 `to_krw` 로 KRW 합산(직접 곱 금지 — USD+usdkrw=None 은 None 전파로 기여 제외+incomplete, silent USD-as-KRW 합산 구조적 차단). 종목 식별 키를 `position_key(ticker, country)` 로 일관화(steps/closes/live_quotes 3축 동기, US/KR ticker 충돌 방지). `assets.py` 는 전체/계좌뷰에서 country 필터를 제거하고 country 별 파이프라인(backfill/get_closes/quotes)을 분리·합산, `usdkrw` 는 해외 보유 시 1회 조회. 응답에 `usdkrw`/`has_foreign` 노출. FE 는 `asset-history-convert.ts` 삭제하고 BE KRW 값을 그대로 사용.
  - ② **환율 정책: 현재 환율(spot) 일괄 적용**(일자별 historical FX 아님). 모든 과거 일자 US 평가액에 '오늘 usdkrw' 하나를 곱한다. FE 에 '현재 환율 기준(일자별 아님)' 고지 유지.
- **트레이드오프:** spot 일괄이라 과거 곡선 모양이 오늘 환율로 왜곡됨(USD 가격 변동만 반영) — 정확한 일자별 환산은 USD/KRW 일별 시계열 적재라는 별도 대형 작업이 필요해 **보류**. 오늘 점 총액은 자산추이(BE `fetch_quotes_by_keys`)와 대시보드(FE overlay)의 시세 소스가 갈려 미세 불일치 가능(포함범위·usdkrw 소스는 일치 — backlog 후속).

---

## 2026-06-11 | 해외 공급처 env 구조 통일 + 환율(FX) 폴백 추가 (open.er-api.com)

- **맥락:** 해외(US)는 시세·일별종가·종목마스터·환율을 모두 단일 공급처(Yahoo / nasdaqtrader)에 의존. 국내(KR)는 시세 naver→yahoo→kis, 종가 data.go.kr+naver/kis, 마스터 data.go.kr+kis 처럼 registry/env 로 공급처를 토글·폴백할 수 있는데 US 는 코드에 하드코딩(`backfill_closes` 가 country=US 시 env 우회·Yahoo 강제, `_entry_fetch_fn` US 가 `_fetch_yahoo_us` 직접 호출)돼 있어 비대칭. 또한 환율은 Yahoo `USDKRW=X` 단일점 — 죽으면 전 해외 평가액의 KRW 환산이 통째로 "환율미상".
- **결정:**
  - ① **US 도 KR 과 동일한 registry + `resolve_chain` + env 구조로 통일.** 시세 `US_QUOTE_PROVIDERS`(`_US_QUOTE_REGISTRY`), 일별종가 `US_DAILY_PRICE_PROVIDER`(`_US_PRIMARY_REGISTRY`), 종목마스터 `US_STOCK_SEED_SOURCES`(`_US_STOCK_SEED_REGISTRY`). 기본값은 현행과 동일한 단일 출처(`yahoo`/`nasdaqtrader`) — **구조만 통일**(공급처 추가/교체 시 함수+registry 등록+env 변경으로 끝). lifespan `validate_*` 가 KR/US 양쪽 오타·빈 체인을 부팅 시점 fail-fast.
  - ② **환율 공급자 체인화 + 폴백 1개 추가.** `FX_PROVIDERS`(기본 `yahoo,er_api`). `get_fx_rate` 가 체인을 앞에서부터 시도해 첫 성공값 캐시·반환. 폴백은 **open.er-api.com**(무인증·무료, `/v6/latest/USD`→`rates.KRW`) — 기존 Yahoo/Naver/nasdaqtrader 전부 무인증인 컨벤션과 일관, 키 관리 부담 없음. 한국은행 ECOS(권위 높으나 키 필요)·frankfurter(ECB, 영업일 1회 갱신·지연) 대비 무인증+일 1회 갱신 균형으로 선택.
- **트레이드오프:** US 단일 출처 자체는 유지(MVP 비중 작음)하되 *스왑 가능성*만 확보. 환율 폴백은 단일 통화쌍이라 추가 비용이 가장 작고 영향 반경(전역 "환율미상")이 가장 커 우선 보강. er-api 는 일 1회 갱신이라 Yahoo 대비 실시간성 낮음 — 어디까지나 2순위 폴백(Yahoo 정상 시 미사용). stale-유지(D2)는 **전체 체인 실패 후**에만 적용해 Yahoo 한 번 실패에 폴백을 건너뛰지 않게 함. cache key 는 통화쌍(`base/quote`)만 — Yahoo 실패→er_api 성공분을 같은 키에 공유.

---

## 2026-06-09 | 해외(미국) 주식 — 원화기준 통합표시 + 달러 보조 + 거래등록 달러·원화 직접입력 (2026-06-08 "분리+토글" 대체)

- **맥락:** 2026-06-08 "분리 섹션 + ₩/$ 토글" 방향으로 Phase A/B 구현을 진행하던 중 기본 정책을 재변경. 분리/토글 UI 대신 **단일 통화 기준(원화)으로 통일**하되 해외는 달러를 보조로 노출하는 쪽이 인지 부하가 더 낮다고 판단.
- **결정(확정):**
  - ① **모든 통화 원화 기준 표시.** 대시보드 총액·보유 리스트·손익 전부 KRW 단일 합산(국내·US 한 리스트). 분리 섹션·₩/$ 토글은 폐기.
  - ② **해외는 달러 보조 표시.** `MoneyText` 가 원화 primary + 달러 괄호 병기("1,095,500원 ($716.07)"). 거래 입력 폼·상세도 동일.
  - ③ **거래 등록 시 달러·원화 모두 직접 입력.** 해외 거래는 **가격(USD) + 체결 원화(KRW)** 를 사용자가 직접 입력하고, `exchange_rate = 체결원화 / (price×quantity)` 로 **역산 저장**(증권사 정산서 = USD 체결액 + KRW 정산액과 동형). 체결 원화는 **원금(가격×수량)만** — 수수료·제세금은 USD 로 입력하고 역산 환율로 KRW 환산. 체결 원화 기본값은 현재 시세 환율 기준 제안값(수정 가능). DB 는 기존대로 native 금액 + `trades.exchange_rate`(`029_add_exchange_rate.sql`) 저장, KRW = native × rate.
- **유지(2026-06-08 에서 계승):** 거래별 체결환율 박제(취득원가=매입환율, 평가=현재환율 → 환차손익 반영), US 시세 Yahoo primary·KIS 보조, Nasdaq Trader 심볼 seed, FX 시계열 Yahoo `USDKRW=X` 별도 레일, import(토스·삼성 USD)는 v2.x 후속.
- **트레이드오프:** ₩/$ 혼재 화면을 피하는 대신 통합 합산이라 환율 변동이 전체 평가액에 섞인다(거래별 박제 환율로 취득원가는 고정돼 손익 정확도는 유지). 입력 모델을 "환율 직접입력"이 아닌 "원화 직접입력→환율 역산"으로 한 것은 사용자가 정산서의 KRW 금액을 그대로 옮길 수 있게 하기 위함.
- **Phase D 구현 결정(2026-06-09, 잔여 정합/기능/UX — Phase C 임포트 제외):**
  - **D1 US 일별종가:** Yahoo chart v8 range 엔드포인트(`YAHOO_CHART_RANGE_URL`, 기존 시세용 URL 은 `range=1d` 고정이라 부적합)로 US daily closes backfill → 자산추이/종목 미니차트 US 활성화. **실패/빈 범위 구분(2026-06-10 코드리뷰로 정정):** 전송 실패·비200·malformed 만 raise(sync_state 미advance → 재시도 보장)하고, 정상 200 의 빈 범위(주말/휴장)는 synced 처리 — 초기 "빈 응답=실패 승격" 정책은 주말마다 US 종목 수만큼 매 요청 Yahoo 재질의 + incomplete 배너 상시 노출을 유발해 폐기(KR data.go.kr 의 빈 응답 synced 처리와 대칭). **장중 캔들 가드:** Yahoo 일봉 마지막 캔들은 진행 중 세션(close=현재가)이라, 캔들 날짜 D 는 `now_kst >= D+1일 07:00 KST`(미장 마감 05/06:00 + 버퍼) 일 때만 확정으로 보고 그 전엔 제외·sync_state 도 cutoff 로 클램프 — 새벽(미장 진행 중) 조회 시 장중가가 D 종가로 영구 박제되는 것 방지. KR 경로 무변경.
  - **D2 시세/FX graceful:** 시세·환율 fetch 실패(None)를 캐시에 박지 않고 **직전 성공값을 stale 로 유지** → 단일 공급자(Yahoo) 일시 장애가 해외 평가액을 통째로 가리는 것 방지. "원래 시세 없는 종목"은 직전값도 None 이라 영향 없음(실패/데이터없음을 캐시 존재 여부로 구분). KR 도 공통 함수라 동반 개선.
  - **D3 거래 수정 통화 인지:** 등록폼과 동일하게 해외 거래 수정도 체결원화→환율 역산. 단 재제안 anchor 는 현재 시세가 아닌 **거래 시점 환율(`trade.exchange_rate`)** — 단순 오타 정정 시 기록 환율이 silent 하게 오염되는 것을 막기 위함(현재 시세는 정보성 표시 전용).
  - **D4 환율 검증 대칭:** 해외(비-KRW) 거래에 `exchange_rate=1.0`(기본/누락) 거부를 create(POST 422)·update(PATCH 400) 양쪽에 적용, 메시지 공유. PATCH 는 country_code 가 body 에 없어 **existing 거래 기준** 라우터 가드로 검증.
  - **D5 분석 정밀도/투명성:** size 분포(매수 원금 버킷)는 **거래 시점 환율로 KRW 환산**(현재환율 아님 — 원금 분포라 고정환율이 원가 모델과 일관). 평가액 환산에 쓰인 환율·기준시각(`FxRate.as_of`)을 해외 보유 시 대시보드에 노출.
- **코드리뷰 보류건 처리(2026-06-11):** 1차 리뷰 후 보류했던 항목들을 사용자 판단으로 진행. 트레이드오프 있는 선택만 기록:
  - **자산추이 원화 통일(US):** US 종목 자산추이도 원화 primary + 달러 보조로 통일. **일자별 환율이 아닌 현재 환율로 전체 시계열 환산** + "현재 환율 적용" 안내 문구 — historical FX 인프라 없이 통화 일관성 확보(정밀도 대신 단순성·일관성 택함). 환율 미상 시 차트/헤더 비표시로 조용한 USD-as-KRW 차단. BE `/assets/history` 무변경, FE overlay(Phase B 철학 일관).
  - **`missing_quote_tickers` 기준 통일:** analysis 가 `current_price is None` → `evaluation is None`(portfolio·FE 와 일치). **사용자 가시 동작 변경** — US 종목이 시세는 받았으나 환율 미수신 시 analysis 대시보드에도 "시세 없음" 노출(기존엔 누락). 두 화면 배지 일관성 확보.
  - **클래스주·우선주 seed 허용 + Yahoo 심볼 변환:** nasdaqtrader 필터를 `isalpha or [A-Z]+\.[ABC](클래스주) or [A-Z]+\$[A-Z](우선주)` 로 확대 — BRK.B·BF.B(클래스주), BAC$B(우선주, 한국 우선주와 가장 유사) 포함. 워런트(`.W`/`.WS`)·유닛(`.U`)·rights(`.R`)는 계속 제외(사용자가 클래스주+우선주만 선택). **핵심: nasdaqtrader↔Yahoo 표기 불일치로 시세가 안 나오던 버그 동반 수정** — seed 는 `BRK.B`/`BAC$B`(nasdaqtrader) 형식인데 Yahoo 는 `BRK-B`/`BAC-PB` 를 요구(실측: 점 형식·`BAC-B`·`BACpB` 모두 Not Found). `_to_yahoo_us_symbol`(`$`→`-P`, `.`→`-`)을 시세·일별종가 fetch 양쪽에 적용. 변환 없이는 검색·등록만 되고 평가액 영구 missing. 보통주(AAPL)·KR 경로는 no-op. 클래스 경계 `[ABC]`·우선주 단일 시리즈 문자로 좁힌 트레이드오프: 드문 클래스(`.K` 등)·복수문자 시리즈는 누락하나 실사용 대다수 커버.
  - **`exchange_rate` DB CHECK 제약:** 029 에 `CHECK (exchange_rate > 0)` 추가(029 미적용 상태라 동일 파일). API `_comma_positive` 양수 강제에 더해 DB 레벨 방어 + `exchange_rate or 1.0` 의 0→1.0 silent 치환 차단.

---

## 2026-06-08 | Capacitor OTA 라이브 업데이트 v1 — 자체 호스팅(`@capgo/capacitor-updater` + R2 JSON SSOT), Capgo Cloud 미사용

- **맥락:** FE 는 `next.config output:"export"` 정적 SPA 를 `capacitor webDir:"out"` 로 동봉 → 웹 자산(JS/HTML/CSS) 한 줄 수정에도 스토어 재심사가 필요했다. 웹 수정 빈도가 네이티브보다 압도적으로 높아 OTA 로 재심사를 우회한다. Apple §2.5.2/§3.3.2 는 WebKit 해석 코드(웹뷰 자산)만 교체하는 OTA 를 허용(핵심 목적 불변·네이티브 코드 미변경 한정).
- **결정(확정):**
  - ① **플러그인 `@capgo/capacitor-updater`(오픈소스)** 채택 — 다운로드/checksum 검증/원자적 교체/부팅 실패 시 자동 롤백을 플러그인이 처리(직접 구현 대비 핵심 안전장치). **Capgo Cloud(SaaS $12+/mo) 미사용 — 자체 호스팅.**
  - ② **매니페스트 발행상태 SSOT = R2 단일 JSON**(`manifest/latest.json`, 플랫폼 공통), 대안 Postgres 기각. 릴리즈 스크립트가 이미 가진 R2 자격증명으로 원자적 PUT flip, BE 는 자격증명 없이 HTTPS GET → **Supabase 마이그레이션/RLS 변경 회피**. 번들 zip 도 R2(CDN 전면, 무료 egress)에 두고 결정 API(작은 JSON)만 FastAPI/Coolify.
  - ③ **결정 API** `POST /live-update/manifest`(public, force-update `/app-config` 패턴). 로직: `effective_installed = version_build if version_name=="builtin" else version_name`; `required_native_version > version_build`(스큐)면 차단; `published.version > effective_installed`면 `{version,url,checksum}`; 그 외/조회실패는 **fail-open**(앱 부팅 차단 금지).
  - ④ **`required_native_version` 과 force-update `min_supported_version` 은 직교**(절대 합치지 않음) — 전자는 "이 웹 번들을 안전히 돌릴 최소 네이티브", 후자는 "스토어 강제 하드 플로어". 스큐 시 OTA 는 조용히 차단하고 force-update 가 독립 폴백.
  - ⑤ **번들 버전 = `fe/package.json` 마케팅 버전(semver)**. 웹 전용 OTA 발행 = `bump-patch fe` without `bump-build`. 비교 기준은 `version_build`(=`App.getInfo().version` 마케팅 버전, ForceUpdateGate 비교값과 동일), `version_code`(정수 빌드번호) 아님.
  - ⑥ **R2 자격증명은 릴리즈 스크립트 전용** — 루트 gitignored `.env`(또는 CI secret). fe public env(`NEXT_PUBLIC_*`/`.env.development.local`)·번들에 절대 미주입. BE 는 manifest 절대 URL(`live_update_manifest_url`)만.
- **실측 정정(2026-06-08, 플러그인 네이티브 소스 직접 판독 — Android `CapacitorUpdaterPlugin.java`, iOS `CapacitorUpdaterPlugin.swift`):**
  - **no-update 응답 = `200 {"kind":"up_to_date"}`** (초안의 "url 키 없는 빈 200"은 **오류**). 빈 200/`{}`/204/empty-body 는 모두 플러그인이 `failed` 로 정규화 → 매 부팅 다운로드 실패 통지. 스큐 차단도 non-failure kind(`up_to_date`/`blocked`) 필수. ← 머지블로킹 실측이 사양 추정을 뒤집은 사례(브로커 파서 fixture·KIS 레이트리밋 교훈과 동일: 추정 금지·실측 우선).
  - 호환 zip+checksum 은 표준 `zip`/`sha256sum` 이 아니라 **`@capgo/cli bundle zip --json`** 으로만 생성(로그인 불필요·오프라인 동작 확인, 메이저 8 = 플러그인 8.49 호환). checksum 은 CLI 출력에서 파싱(직접 계산 금지).
- **페이징:** 플러그인은 네이티브 추가라 **스토어 1회 제출이 OTA 동작 전제.** v1 = "제출 가능한 상태"(코드 완성 + `pytest`/`tsc`/`cap sync`/dry-run green, 전체 회귀 529 passed). 라이브 OTA·실기기 스큐 매트릭스·실 R2 발행은 스토어 빌드 라이브 이후 후속.
- **트레이드오프:** R2 JSON SSOT 는 발행 이력 쿼리/트랜잭션·채택률 통계가 없다(v1 미포함, 롤백은 클라이언트 자동이라 무방) — v2 통계 도입 시 Postgres 재검토. 서명/E2E 암호화·단계 롤아웃(%)·델타 업데이트는 v2(현재는 checksum 무결성 + TLS + 100% 일괄 + 자동롤백 + 빠른 재푸시). full remote(`server.url`) 대신 OTA 를 택해 오프라인 회복력·`capacitor://localhost` 오리진(인증 영향 최소)·심사 가용성을 보존.

---

## 2026-06-08 | 해외(미국) 주식 v2 방향 — 분리 + ₩/$ 토글(거래별 체결환율), 기존 "KRW 합산" 계획 대체

> ⚠️ **2026-06-09 대체됨** — 위 항목 참조. 분리 섹션·₩/$ 토글은 폐기, 원화기준 통합표시로 재전환.


- **맥락:** 2026-04-27 "MVP 해외 제외" 이후 v2 재개 사전조사. 기존 backlog/roadmap 의 v2 해외 계획은 "USD/KRW 환율로 해외 평가액을 **KRW 총자산·미실현손익에 합산** + 크로스-통화 HHI"였다. 그러나 ① 실시간 환율 환산이 부정확(특히 **당일 직접입력은 거래일 종가 환율 미확정**), ② 한 화면에 ₩/$ 혼재 시 인지 부하 → "분리 + USD-native + 사용자 토글"로 방향 전환. 증권사(미래에셋·KB·키움) 조사로 토글 원화 = **일별 매매기준율 환산(실시간 피드 불필요)**, 당일 거래는 **잠정→익일 재정산**(KB 10:45 재정산·미래에셋 가환전→실환전)이 업계 표준임을 확인 — 우리 backfill 설계와 동일.
- **결정(확정):**
  - ① **미국만.** 모델은 다시장 가능하게 두되 seed·UI 는 US 만(다른 시장은 추가작업 없이 확장 가능, 이번 미포함).
  - ② **MVP = 직접 입력.** import(토스 `달러 거래내역`·삼성 USD)는 **v2.x 후속**(미국 거래 샘플 확보 후 — 없는 입력에 맞춘 파서는 speculative). 해제 지점: `trade.py:132 _mvp_foreign_buy_blocked`, `samsung_xlsx.py:96`, `toss_pdf.py` USD 섹션.
  - ③ **국내와 분리 섹션.** 통합 뷰는 **제품 선택으로 보류**(거래별 KRW 가 생기므로 기술적 불가는 아님 — "어느 환율·시점" 컨벤션 확정 시 추가).
  - ④ **미국 섹션 내 ₩/$ 토글(MVP 포함).** KRW = **거래별 체결환율** — 취득원가=매입 시점 환율, 평가=현재 환율 → **환차손익 반영**(증권사 평가 방식). 토글 KRW 는 "참고 평가값"(증권사도 평가환율 ≠ 결제환율).
  - ⑤ **거래 4필드 통화중립 저장**(국내/해외 통일): `amount_native`(체결통화 금액=price×qty), `fx_rate`(native→KRW, **국내=1.0**), `amount_krw`(=round(native×fx)), `fx_provisional`(당일 잠정 여부). **write 시점 단일 경로 계산**(생성/수정 시 갱신), read 는 저장값. 그 이상 파생(비용 KRW·순액·손익)은 `fx_rate` 로 유도 — **과한 비정규화 회피**(박제 늘릴수록 stale 위험↑, BUY→SELL cascade 교훈).
  - ⑥ **BE 손익:** `trade_walker` 에 환율 차원 추가 → 매수 로트별 `fx_rate` 를 끌고 가 KRW 실현/미실현손익 계산. 실제 계산은 BE `/portfolio/summary`(FE walker 는 dead code).
- **선행검증(2026-06-08 실호출 완료):**
  - **US 시세: primary=Yahoo, 보조=KIS 해외.** 실측 — Yahoo(AAPL $307.34, 무인증·근실시간·레이트리밋 무이슈) vs KIS 해외(`/uapi/overseas-price/v1/quotations/price`, TR `HHDFS00000300`, `EXCD`=NAS/NYS/AMS·`SYMB` — AAPL 309.06·KO 79.33 정상이나 **2건/초 앱키 예산이 국내와 공유**, NVDA 에서 EGW00201 재현). `decisions.md:25` "KIS 시세=보조" 결론이 해외에도 전이 확인 → **Yahoo primary, KIS 는 공식 교차검증/fallback**. US 엔 Naver fallback 없음. `_fetch_yahoo` 는 현재 `.KS/.KQ` suffix 만 붙이므로 US 는 suffix 없는 분기 추가 필요.
  - **US 심볼 seed: Nasdaq Trader 1순위(SEC 보강).** 실측 — `nasdaqlisted.txt`(5,494) + `otherlisted.txt`(7,301, **ETF 플래그 Y 4,107·거래소코드 포함**) → 기존 seed shape(`{ticker, asset_name, market}`) 매핑 가능. SEC `company_tickers.json`(10,400사·정식회사명·CIK)은 보강용.
  - **FX 시계열: Yahoo `USDKRW=X` 로 시작(추후 smbs 고려).** 실측 — 일별 close 무인증 정상. 시장환율이라 매매기준율과 ~0.1% 차이나나 토글 KRW='참고 평가값'이라 충분. 정밀 필요 시 서울외국환중개 매매기준율(jsp 스크래핑) 업그레이드. **적재·backfill job 은 신규 레일**(주가 `daily_price_sync_state` 와 별도 테이블·job).
- **트레이드오프:** 거래별 환율 박제로 KRW 손익은 정확하나 walker 에 환율 차원 + FX 시계열 적재가 신규 비용. 직접입력 당일 거래는 잠정 환율→backfill 수렴(USD-only 가 아니라 토글이라 잠정값이 일시 노출될 수 있음 — `fx_provisional` 로 표시 처리). import 는 샘플 부재로 후속 분리.

---

## 2026-06-07 | KIS 토큰 영속화 — Redis 대신 PostgreSQL (kis_tokens + advisory xact lock)

- **맥락:** KIS 토큰 1일 1회 발급 원칙(잦은 발급 시 이용 제한 제재) 대응. 기존 토큰 캐시는 per-process 메모리라 재배포·롤링 배포 중 신구 컨테이너·cron 배치마다 각자 발급. 저장소로 Redis vs DB 조사.
- **결정:** ① 기존 PostgreSQL(Supabase)에 `kis_tokens` 테이블(`scope` pk — 'app', 추후 `user:{id}` 확장)로 영속화. Redis 미도입. ② 발급 직렬화는 `pg_advisory_xact_lock`(trades_repo 와 동일 패턴 — session lock 은 Supavisor 에서 leak) + 같은 트랜잭션에서 upsert. ③ 보안은 RLS enable + 정책 없음 — anon/authenticated(PostgREST) 차단, BE 는 owner(postgres) 접속이라 통과(전역 테이블의 "RLS 미적용" 패턴과 의도적으로 다름). 접근은 `acquire_for_user` 가 아닌 plain `pool.acquire()`. ④ 조회는 메모리 캐시 → DB → 락+발급 3단, `pool=None`(테스트/DB 미연결)이면 종전 메모리 전용.
- **이유:** 토큰 저장은 고빈도 캐시가 아니라 저빈도(하루 1~4회 쓰기)·고내구성·프로세스 간 공유 문제 — Redis 강점(저지연)은 쓸 곳이 없고 약점(휘발성)이 급소(토큰 유실 = 재발급 = 레이트리밋 대상). DB 는 운영 비용 0(기존 인프라)·기본 영속·RLS/암호화로 사용자 토큰(트랙 2 BYOK) 확장에도 유리. 실 DB 라운드트립으로 SQL·락·owner RLS 통과 검증 완료.
- **트레이드오프:** ① owner 가정 — 운영에서 마이그레이션 role ≠ 앱 접속 role 이 되면 `load()` 가 조용히 None → 매번 재발급 → EGW00133. 운영 배포 후 영속 동작 1회 확인 필요. ② DB 장애 시 KIS fail-closed(발급 우회 없음) — KIS 는 fallback 공급자고 DB 다운이면 앱 전체 불능이라 수용. ③ 멀티워커에서 토큰 거부 응답 시 DB 재조회(타 워커 토큰 픽업) 로직은 미구현 — replica=1 전제, backlog 기록.

---

## 2026-06-07 | KIS 공급자 구현 — 레이트리밋 실측 페이싱·마스터 파일 일괄 교차검증·실측 보정

- **맥락:** KIS 트랙 1(기존 데이터 공급처 확대)로 시세/일별 종가/종목마스터/교차검증에 kis 공급자를 추가. 사전 조사(deep-research) 수치 일부가 "재검증 필요"였고, 실호출 검증에서 실제와 다른 것이 다수 확인됐다.
- **결정/실측:**
  - ① **레이트리밋 실측 2건/초**(개인 실전 계정, 3번째 연속 호출부터 EGW00201) — 사전 조사의 ~20req/s 는 법인/과거 수치. 대응: `external/kis.py` 에 슬라이딩 윈도우 페이싱(2건/1.05s, 토큰 발급 포함) + EGW00201 1회 재시도. **시세 경로만 슬롯 대기 예산 1.0s** — 초과 시 즉시 None 반환해 다음 공급자(naver)로 fallback(체인 전체가 `QUOTE_FETCH_DEADLINE` 5s 에 걸려 죽는 것 방지). 배치(일별 종가)는 무제한 대기.
    - **2026-06-14 재실측·정정:** 2건/초는 **신규 고객 3일 제한**(신청 후 3일간 3건/초, 2026-04-03 시행) 구간 측정이었다. 발급 7일 경과 후 재측정(국내 현재가 동시 20건 버스트 × 2회) → **20/20 성공·EGW00201 0건**으로 기본 유량(공식 18건/초) 복귀 확인. 페이싱 상수 `_RATE_MAX_CALLS` 를 **2 → 18** 상향. per-process 한계는 그대로(아래 트레이드오프) — replica=1 전제 유지.
  - ② **교차검증 kis 는 종목별 REST 가 아니라 종목마스터 파일 1회 다운로드 일괄 대조** — 미검증 수천 종목 × 종목별 호출은 2건/초 한도에서 비현실적, 파일은 키 불필요·1회 다운로드로 전체 스냅샷.
  - ③ **마스터 파일 실측 보정**: tail 고정폭 227/221(공식 예제 주석 228/222 와 1 차이 — 228 로 자르면 그룹코드가 한 칸 밀려 ETF/ETN 분류 전멸), ETN 단축코드는 'Q' 접두 7자(Q500061→500061), 신형 ETF 는 영숫자 코드(0000D0) — isdigit 필터 금지. 실파일 검증 4,295건(KOSPI 950·ETF 1,137·ETN 385·KOSDAQ 1,823).
  - ④ **marcap(시총)은 보류** — data.go.kr 는 bulk 응답, KIS 는 종목별 호출(전종목 수천 콜)이라 비용 비대칭. `update_marcap` 은 data.go.kr 유지.
- **이유:** synthetic 테스트만으로는 ①③을 못 잡았다(브로커 파서 fixture 회귀 테스트 교훈과 동일) — 실호출 검증을 구현 단계에 포함한 것이 결정적.
- **트레이드오프:** 페이싱·토큰 캐시는 **per-process** — 2건/초는 appkey 당 서버 제한이라 멀티 replica 면 합산 초과(EGW00201 은 fallback 으로 흡수되나 KIS 활용률 저하). kis 공급자 활성화 선행조건: replica=1 확인 또는 공유 리미터(backlog 기록). 시세는 한도 특성상 1차 공급자로 부적합 — 보조 공급자 포지셔닝. `crossvalidate=kis` 는 KONEX 를 대조 없이 검증완료로 박제(마스터에 KONEX 없음, `naver_checked_at` 공유 컬럼).

---

## 2026-06-07 | 외부 데이터 공급자 — 도메인별 dict registry + env 토글 (entry-point threading)

- **맥락:** KIS Open API 도입(시세)과 향후 공급처 추가에 대비해 모든 외부 데이터(시세/종목마스터/일별종가/NPS)의 공급처를 env 로 전환 가능하게 요구. 시세 fallback 체인·seed 파이프라인·tail-gap 보충이 코드에 하드코딩돼 있었고, 검색만 `STOCK_SEARCH_PROVIDER` 토글 전례가 있었다.
- **결정:** ① 각 도메인 모듈 내 `dict[str, fn]` registry + 공통 `provider_registry.resolve_chain`(unknown 이름 ValueError). ② env 는 `QUOTE_PROVIDERS`(콤마 체인)·`STOCK_SEED_SOURCES`(첫 항목=authority)·`DAILY_PRICE_PROVIDER`/`DAILY_PRICE_GAP_PROVIDER`("none"=비활성)·`NPS_PROVIDER`(registry-of-one). ③ 함수 내부에서 `get_settings()` 를 읽지 않고 entry point(라우터 `Depends`/배치 `main()`)에서 인자로 threading — 체인 함수는 현재 동작과 동일한 리터럴 기본값. ④ quotes 만 lifespan startup 에서 `validate_quote_providers` 검증.
- **이유:** ① config.py 가 도메인을 import 하면 순환 위험 — 이름 문자열만 방출하고 해석은 도메인이 담당. ③ `Settings()` 는 `supabase_url` 필수라 내부 호출 시 단위 테스트가 깨지고 암묵 의존이 생김 — 리터럴 기본값 덕에 기존 테스트가 무수정 통과해 동작 보존이 증명됨. ④ 시세 요청 경로는 `gather(return_exceptions=True)` 가 ValueError 를 삼켜 env 오타 시 전 종목이 조용히 null — 부팅 fail-fast 필요(타 도메인은 호출 시점 ValueError 로 충분: seed=CLI crash/배치 로깅, daily_price=라우터 500).
- **트레이드오프:** 공급자 "추가"는 여전히 코드(함수+registry 등록) — env 는 선택/순서만 담당(플러그인/동적 import 같은 과추상화 배제). `update_marcap`·`crossvalidate_stocks_with_naver` 는 seed 의 고정 단계로 토글 제외 — Naver·data.go.kr 고정 의존이 알려진 예외로 남음(backlog 기록). NPS 는 대체 공급처가 없어 registry-of-one(구조 일관성 우선, 사용자 결정).

---

## 2026-06-06 | 일별 손익 차트 — "손익" = 전일대비(자산 평가액 일간 변화), BE items.change 재사용

- **맥락:** 자산 추이 페이지에 일별 손익 막대 차트 탭을 추가하며 "일별 손익"의 정의가 쟁점. ① 전일대비(자산 평가액 일간 변화 — 추가 매수/매도로 인한 증감도 포함, 기존 '일별 내역' 표와 동일), ② 매수/매도 현금흐름을 제외한 순수 평가손익(보유 수량 × 가격 변화) 두 해석이 가능했다.
- **결정:** ① 전일대비 채택. BE `/assets/history` 응답의 `items[].change`(직전 거래일 대비 value 차)를 FE 에서 역순 변환해 막대 차트에 그대로 사용 — 재계산 없음, BE 무변경.
- **이유:** 같은 화면의 '일별 내역' 표가 이미 전일대비 정의를 쓰므로 차트와 표의 숫자가 항상 일치(정합 보장). ②는 BE 에 일별 손익 walker(보유 수량 × 가격 변화) 추가가 필요하고, 같은 화면에서 표와 차트의 숫자가 달라져 혼란.
- **트레이드오프:** 큰 추가 매수일에 손익이 아닌 +막대(빨강)가 표시됨 — 알려진 특성으로 수용(사용자 확인 완료). 순수 평가손익 요구가 생기면 BE 확장으로 재검토.

---

## 2026-06-06 | 자산 추이 차트 매수 금액 기준선 — BE 응답 포함 + baseValue 분할 그라데이션

- **맥락:** 차트에 매수 원금 가이드와 손익 구간 색(위 빨강/아래 파랑)을 넣는데, ① 원금 값을 어디서 가져올지(FE 가 `/portfolio/summary` 재조합 vs BE 가 `/assets/history` 에 포함), ② recharts 에서 기준선 분할 색을 어떻게 그릴지(그라데이션 offset 이 objectBoundingBox 기준이라 stroke/fill 의 bbox 가 다르면 어긋남)가 쟁점.
- **결정:** ① BE 가 이미 로드한 scoped trades 에 `build_positions()` 를 재사용해 `investedAmount`(보유분 cost_basis 합)를 응답에 포함. ② 원금이 가시 데이터 범위 안일 때만 `Area baseValue=원금` 으로 분할 렌더(이때 stroke/fill bbox 가 [dataMin,dataMax] 로 일치해 단일 offset 공유), 범위 밖이면 단색(수익 빨강=아래로 fade / 손실 파랑=곡선 위로 fade) 3-케이스 분기. 가이드 라인·라벨도 범위 안일 때만 표시해 Y 도메인 불변.
- **이유:** ① FE 재조합은 scope(accountId/ticker/country) 매칭을 FE 가 중복 구현해야 해 shape drift 위험 — 대시보드 평가손익과 동일 계산 경로(`cost_basis`)를 쓰면 숫자가 항상 일치. ② baseValue 를 쓰지 않으면 fill path bbox(곡선~바닥)와 stroke path bbox(곡선만)가 달라 offset 이 안 맞는다 — 범위 밖 케이스를 분기로 빼면 offset 수학이 항상 정확.
- **트레이드오프:** 분할 fill 이 곡선~원금 라인 사이만 칠해져 단색 모드와 채움 범위가 다름(시각적으로는 의도된 표현). 그라데이션 SVG id 는 `useId()` 로 인스턴스별 분리(고정 id 는 다중 마운트 시 첫 defs 로 오염).

---

## 2026-06-05 | 자산 추이 계좌뷰 — country 로 일관 필터 (혼합 국가 보유 부분 누락 대신)

- **맥락:** code-review 에서 발견 — 계좌뷰가 trades 는 전 국가 로드하면서 종가 backfill·라이브 시세는 `country="KR"` 고정이라, 비-KR 보유분이 시리즈 값에서 조용히 빠지고 `incomplete` 플래그만 섰다. 비-KR 티커가 data.go.kr(KR 전용)로 전달돼 쿼터도 낭비.
- **결정:** 계좌뷰도 `list_trades_with_account` 에 `country` 필터(기본 KR)를 항상 적용해 적재·시세·계산 스코프를 country 로 일관시킨다. NULL/'' country_code 는 SQL `COALESCE(NULLIF(...,''),'KR')` 정규화로 KR 매칭 유지.
- **이유:** data.go.kr 는 KR 전용이라 비-KR 과거 종가는 어차피 적재 불가 — "전 국가 로드 후 일부 누락 + incomplete 노이즈"보다 "country 단위 일관 스코프"가 정직하다. 수치는 동일(비-KR 은 이전에도 값 미포함), 불필요 외부 호출·플래그 노이즈 제거.
- **트레이드오프:** 비-KR 전용 계좌는 자산 추이가 빈 시리즈(거래 없음 경로)로 표시. 해외 종가 소스를 붙이면 country 파라미터 분기로 확장.

---

## 2026-06-04 | 자산 추이 backfill — sync_state 마커로 빈-범위 재질의 차단(cron 대신 B)

- **맥락:** 종가가 적재돼 있어도 `/assets/history` 가 매 요청 12초까지 걸렸다. backfill skip 조건이 "마지막 거래일"이 아닌 **달력상 어제**와 비교(`begin > yesterday`)해, 어제가 비거래일(예: 6/3 지방선거 휴장)이면 watermark(6/2)<어제라 종가가 있어도 fetch 가 발사됐다. 휴장 응답은 거래일이 없어 `if rows:` 로 upsert 가 안 돼 watermark 가 영구 정체 → 매 요청 전 종목을 순차로 data.go.kr 에 재질의(쿼터 소진 위험). 실측: backfill 이 응답시간의 93%, compute/quotes/DB 는 무관.
- **결정:** cron(사전적재)으로 우회하지 않고, backfill 진행상태를 "종가 존재"와 분리해 `daily_price_sync_state(checked_through_date, checked_at)` 마커에 기록한다(**빈 응답도 기록**). 어제까지 최근 확인했으면 쿨다운(6h) 내 재질의 skip. 종목 fetch 는 `Semaphore` 로 병렬화.
- **이유:** 버그의 뿌리는 실행 위치(cron)가 아니라 "확인했지만 비었음"을 기록 못 하는 상태 모델. 마커는 ① 신규 종목도 첫 요청 1회 적재 후 skip(cron 불필요), ② 호출수를 트래픽 비례 → "종목수 × 쿨다운당 1회" 상한으로 고정(쿼터 안전), ③ 휴장/발행지연 무한 재질의 제거를 한 번에 해결. 기존 stocks `naver_checked_at`(빈 응답도 확인 기록) 과 동일 패턴.
- **트레이드오프:** 쿨다운 6h — 짧으면 늦은 발행(T+1 ~14:00) 반영 빠르나 호출↑, 길면 반영 지연↑·쿼터↓. 오늘 점은 라이브 시세라 과거 점의 일시 carry-forward(incomplete)만 영향. asyncpg 단일 커넥션 동시쿼리 불가로 **fetch 만 병렬, upsert 는 순차**. cron(사전적재)은 범위 제외 — 마커로 콜드스타트 완화, 첫-오픈 지연이 남으면 후속 옵션.
- **검증:** 로컬 휴장일 재현 1.37s → 2회차 0.01s. `be/tests/test_daily_price_seed.py` 신규 5케이스. 마이그레이션 `027_daily_price_sync_state.sql`(운영 적용 필요).

---

## 2026-06-04 | data.go.kr "성공률 50%" 재진단 — 상시 장애 아님, 무한페이징 버그 자가유발

- **맥락:** "data.go.kr 불안정으로 데이터가 적재되지 않는다"는 인식으로 게이트웨이(`apis.data.go.kr` 금융위 1160100) 안정성을 실측 진단했다. 2026-06-03 결정문이 "성공률 ~50%"를 게이트웨이 상시 불안정으로 기술해 검색 provider를 Naver로 임시 복귀시킨 바 있다.
- **실측(2026-06-04 08:32 KST):** 3개 엔드포인트(`getItemInfo`/`getStockPriceInfo`/`getETFPriceInfo`)를 **재시도 없이** 각 20회 raw 호출 → **60/60 성공, 응답 전부 0.3초 이하**. 게이트웨이가 현재 완전히 안정적임을 확인.
- **결론(가설 확정):** "성공률 50%"는 게이트웨이 상시 장애가 아니라 **`getItemInfo` basDt 누락 무한페이징 버그(~400만 행)가 dev 키 일일 1만콜 쿼터를 소진해 throttle/404 를 유발한 자가유발 증상**이 유력하다. 근거 ① "50%" 관측과 basDt 버그 수정이 동일 커밋(`617eff3`, 06-02 15:38) — 버그가 살아있던 동안의 측정. ② 06-04 raw 실측 60/60. ③ 사용자가 06-04 수동 seed 실행으로 정상 적재를 확인. 즉 핵심 원인은 06-02에 이미 수정 완료.
- **판단:** 게이트웨이가 간헐적으로 느린 것은 사실이나(정상 응답도 0.7~20초) `_get_with_retry`(6회 backoff) + timeout 60초로 이미 흡수된다. **대체 데이터소스 도입 등 추가 대규모 작업 불필요.** 검색 provider 의 db 복귀는 자동 cron 안정 가동 확인 후 별도 판단(2026-06-03 항목 후속).
- **미해소 변수:** 06-04 적재는 *수동* 실행이었다. Coolify scheduled task 의 매일 14:00 KST 자동 가동 여부는 본 진단 범위 밖(사용자 판단으로 추적 보류).
- **검증 도구:** `be/scripts/diagnose_data_go_kr.py`(재시도 없는 raw 성공률/지연 측정, read-only, DB 미접근). 재발 시 재실행으로 게이트웨이 vs 코드 문제 즉시 분리 가능.

---

## 2026-06-03 | 종목 검색 provider env 토글 — Naver 임시 복귀(data.go.kr 모니터링)

- **맥락:** stocks 검색은 `bffc39d`(2026-05-30)에서 Naver 라이브 호출 → 로컬 stocks 마스터 조회로 전환됐다. 그러나 그 마스터를 채우는 data.go.kr 게이트웨이(`apis.data.go.kr` 금융위 1160100)가 간헐 404/30초 ReadTimeout으로 **성공률 ~50%**(2026-06-02 기록). seed가 불안정한 동안 로컬 검색 데이터가 stale/불완전해질 수 있어, 사용자 대면 검색만 안정적인 이전 Naver 방식으로 되돌리되 코드 폐기 없이 env로 즉시 복귀 가능하게 한다.
- **결정:** `Settings.stock_search_provider`(env `STOCK_SEARCH_PROVIDER`, `"naver"`|`"db"`, **기본 naver**) 추가. `routers/stocks.py:search_stocks`에서 분기 — `db`면 `stocks_repo.search`(로컬), 그 외 `external/naver_search.search_kr`(라이브). Naver 구현은 `bffc39d`에서 보존돼 있어 재연결만. 두 provider 응답 shape 동일(`{code,name,market,exchange}`) → **FE 무변경**.
- **이유:** seed 안정성 모니터링과 사용자 검색 품질을 분리. 코드 양쪽 보존으로 모니터링 종료 후 `STOCK_SEARCH_PROVIDER=db` 한 줄로 복귀(롤백 비용 0).
- **트레이드오프:** ① Naver는 외부 라이브 호출이라 지연/실패 재노출(실패는 빈 리스트로 흡수 — 500 아님, 빈 결과 가능). ② **검색만** 토글 — 거래 import 매칭(`ticker_resolver.lookup_by_names`)·NPS seed(`stocks_repo.search`)·marcap은 여전히 로컬 stocks(stale 가능) 의존. seed를 장기 중단하면 이들이 stale해짐(범위 외, backlog 추적).
- **검증:** `tests/test_stocks.py` 두 경로(db override + naver 기본값) 추가, 12 passed / 전체 372 passed.
- **후속:** 모니터링 종료 후 db 복귀 + import/NPS stale 추적(`docs/backlog.md`).

---

## 2026-06-03 | 안드로이드 safe-area — 네이티브 WindowInsets 주입 (플러그인 미사용)

- **맥락:** 구형 안드로이드(<15) 기기에서 edge-to-edge 가 자동 강제되지 않아 상단 상태바/카메라 영역이 앱 배경으로 안 채워짐(빈 `MainActivity` stub). today-alive 는 `capacitor-plugin-safe-area` 로 해결했으나 invest-note 는 **AGP 9.2.0 / Gradle 9.4.1**(today-alive 는 AGP 8.13)이라, 그 플러그인(및 `@capacitor-community/safe-area`)의 구식 `getDefaultProguardFile('proguard-android.txt')` 가 빌드를 깨뜨려 **설치 불가**. `@capawesome/...edge-to-edge-support` 는 AGP-9 호환이나 철학이 반대(웹뷰 인셋 + 단색 바, full-bleed 아님). `@capacitor/status-bar` 는 styling 전용이라 <140 폴리필 미제공.
- **결정:** 외부 플러그인 없이 **`MainActivity` 에서 네이티브 WindowInsets 를 직접 읽어 `--safe-area-inset-*` CSS 변수로 주입**.
  - `EdgeToEdge.enable(this)` — 모든 버전에서 full-bleed.
  - `capacitor.config` `SystemBars.insetsHandling: "disable"` — 코어 인셋 패딩 방지(full-bleed 유지).
  - `getRootWindowInsets`(상위 뷰 소비 전 루트)로 `systemBars|displayCutout` 조회 → dp 변환 후 `evaluateJavascript` 로 주입.
  - `BridgeWebViewClient.onPageFinished` 마다 재주입 — 콜드 런치 시 인셋 패스가 SPA 로드 전 실행돼 `about:blank` documentElement 에 주입·소실되는 레이스 방지.
  - FE 는 `env(safe-area-inset-*)` → `var(--safe-area-inset-*, env(...))` 마이그레이션(주입 변수 우선, iOS/web 은 env 폴백).
- **이유:** AGP 9 에선 플러그인 proguard 줄 패치가 per-plugin·생태계 공통 비호환이라 취약하고 fe 분리 시 이전 부담. 네이티브 주입은 외부 의존성·패치·버전충돌 0.
- **트레이드오프:** ① `MainActivity` 에 ~50줄 Java(today-alive 와 코드 분기). ② Android 에서 env() 를 항상 덮어쓰므로 네이티브 읽기 실패 시 0 주입 위험 → null 가드로 완화(못 읽으면 env 폴백 유지).
- **검증:** Galaxy S20 / **WebView 111 (<140 버그 기기)** 에서 adb + CDP 직접 확인 — `--safe-area-inset-top: 28px`, bottom 48px 주입(깨진 env()=0 덮어씀). `assembleDebug` SUCCESS.

---

## 2026-06-02 | NPS 우선주 보강(getStockPriceInfo) + 미매칭 reconcile(과거사명 alias)

- **맥락:** NPS 적재 후 `nps_unmatched` 160건 잔류. 원인 검증 → (a) **우선주가 stocks 에 0건** — authority `getItemInfo` 응답에 우선주 미포함(삼성전자만, 삼성전자우 005935 없음), (b) major 발행기관명 접두 `(주)`, (c) 시점 사명 드리프트(스냅샷=과거명, 마스터=현재명). "Naver 로 해소 가능한가" 재검증 → Naver 자동완성은 **현재 등록명 prefix 만 인덱스**해 과거명에 무력(160 중 4건·잔여 69 중 4건만 매칭).
- **결정:**
  - **우선주 보강:** `getStockPriceInfo`(이미 시총용으로 같은 키 호출, 우선주 114건·영문코드 21 포함)를 종목 파이프라인 **preserve 소스(`stock_prices`)** 로 추가. pykrx·Naver 등 새 의존성 불필요. `fetch_stock_prices` 에 asset_name/market 파싱 추가.
  - **(주) 전처리:** `nps_seed.clean_name` 에 접두 `(주)`/`㈜` 제거(접미는 기존 `_ANNOTATION_RE`).
  - **미매칭 reconcile:** `resolved_ticker`(관리자 수동 매핑) 기반 **자기완결** reconcile(`reconcile_nps_unmatched` + `POST /admin/reconcile/nps`). NPS fingerprint-skip 이라 다음 적재 위임 불가 → 즉시 `set_nps_holding` + 행 삭제. `stock_aliases` 등록은 강제 재적재 `reset_nps_holding` 후 재매칭 보험. **`nps_as_of` 는 seed 와 통일**(stocks `max(nps_as_of)` 조회 = held 기준일) — major 행의 major 기준일을 그대로 쓰면 seed-매칭분과 날짜 분기.
  - **상폐 가드:** `resolved_ticker` 가 stocks 부재면 skip + 행 보존. 억지 매칭 금지(데이터 오염).
- **이유:** 우선주·`(주)` 는 자동 해소 가능하나, 사명 드리프트는 ticker 확정이 큐레이터 판단(유사도로 못 잡음) → 수동 매핑 + 자동 반영이 안전. Naver 는 동일 한계라 해법 아님.
- **트레이드오프:** ① `getStockPriceInfo` 가 종목소스+marcap 양쪽 호출(중복 — 기존 `securities` 패턴과 동일). ② `marcap_rank` 에 우선주 포함(현재 소비처 없어 무해, 회사단위 순위 원하면 우선주 ticker 제외 필요). ③ reconcile 큐레이션은 운영 수작업(`resolved_ticker` SQL UPDATE).
- **실측:** 미매칭 160→69(우선주 47 + `(주)` 44 해소) → reconcile 4건 추가 해소 → 65. major `nps_as_of` 단일(2024-12-31) 통일 확인. 테스트 370 passed.
- **후속:** 잔여 상폐 종목은 영구 미매칭(정상). FE 종목 메타 아이콘(`docs/backlog.md`).

## 2026-06-02 | 국민연금 적재 "자동 fetch 불가" 판정 철회 — odcloud OpenAPI 자동화 가능

- **맥락:** 2026-06-01 결정에서 국민연금 적재를 "odcloud 자동 fetch 부적합(연도별 uddi 상이·최신 지칭 엔드포인트 없음·목록 조회 공개 API 없음)" 이유로 보류했다. 재조사 결과 **그 4개 근거 중 "목록 조회 공개 API 없음" 하나가 오류**였다. 이전 조사는 data.go.kr `fileData`(JS 셸) 페이지만 보고 **`infuser.odcloud.kr/oas/docs?namespace=<id>/v1`** 라는 인증 불필요·기계판독 OpenAPI 목록 엔드포인트를 놓쳤다. 나머지(연도별 uddi 상이 등)는 여전히 사실이나 OAS 목록+날짜 정렬로 우회된다.
- **실호출 검증(2026-06-02, 활성 키):**
  - **Discovery:** `GET infuser.odcloud.kr/oas/docs?namespace=3070507/v1`(key 불필요, 200) → `paths` 각 summary 의 날짜를 `max(20\d{6})` 로 정렬 → 최신 uddi 자동 선택. (3070507 최신=20241231, 15106890 최신=20251231)
  - **Fetch:** `GET api.odcloud.kr/api/{uddi-path}?serviceKey=&page=&perPage=&returnType=JSON` 정상. 3070507(전체보유)=1,200건, 15106890(5%+)=111건. perPage=1200 한 번에 수신(페이지네이션 부담 없음).
  - **활용신청:** 두 데이터셋(국내주식 투자정보 3070507 / 대량보유주식 15106890) 모두 승인 완료(같은 serviceKey).
- **확정된 제약(자동화로도 안 사라짐):** 응답에 **종목코드 없음**(3070507=`종목명`만, 15106890=`발행기관명`만). 안정 키가 없어 종목명→ticker 매칭이 필요하고, 실측 매칭률은 정확 93.6%→주석 정제 후 94.8%(로컬 stale DB 기준). 미매칭 잔여 원인: ① 부기 주석 `(배당)(무상)(전환)`[정제 가능] ② 약칭 vs 정식명(금호석유↔금호석유화학) ③ **시점 사명 드리프트**(NPS 스냅샷은 기준일 시점의 과거 이름, stocks 마스터는 현재 이름 → 사명 변경 종목은 미스) ④ 폐지/합병. ②③④는 자동 완전 해소 불가 → **미매칭 reconcile 경로 필수**.
- **권고:** CSV 업로드 대신 **API fetch 자동화 채택**(인코딩/컬럼 추측 제거). 단 3070507은 연 1회 데이터라 **타이트한 cron 불필요**(수동 트리거 또는 저빈도 OAS 신규 uddi 체크로 충분). infuser OAS 는 Swagger 문서 백엔드지 보증 데이터 API 가 아니므로 discovery 는 **soft dependency**(깨지면 uddi 수동 설정 폴백).
- **후속:** 구현은 `docs/spec-current.md`. CSV 업로드 방식은 폐기가 아니라 **백로그 보류**(`docs/backlog.md`).

## 2026-06-02 | stocks seed 라이브 검증 — getItemInfo basDt 버그 + data.go.kr 게이트웨이 재시도

- **맥락:** NPS 적재 시연을 위해 로컬 DB를 비우고 stocks→NPS 재적재를 시도하니 stocks seed가 data.go.kr 전 소스에서 실패(404/422/ReadTimeout). 2026-06-01 "실서버 확인 필요"로 남긴 미해소 스파이크의 실체였다.
- **버그 ① getItemInfo basDt 누락:** `fetch_data_go_kr`가 basDt를 안 넘겨 getItemInfo가 **전체 과거 이력(~4,026,153행)** 을 반환 → 사실상 무한 페이징. basDt(직전 영업일, `_recent_basdt_candidates` fallback) 지정 시 ~2,763행으로 정상화. 시세 3종(getStockPriceInfo/getETF·ETNPriceInfo)은 이미 basDt 사용.
- **문제 ② 게이트웨이 불안정:** `apis.data.go.kr`(금융위 1160100)는 200은 0.7초(캐시)지만 간헐 404 HTML 오류페이지가 ~20초 만에 오고 종종 30초 초과 ReadTimeout(성공률 ~50%). → `_get_with_retry`(404/408/429/5xx·TransportError backoff 재시도 6회) + data.go.kr 클라이언트 timeout 60초(`_DATA_GO_KR_TIMEOUT`). 비재시도 4xx(파라미터 오류)는 즉시 raise.
- **결과:** stocks 4,276 + marcap 4,390 적재 성공. NPS 실 적재: held 1085/major 50 matched, 미매칭 160(우선주·사명 드리프트·폐지) → `nps_unmatched`. 동일 스냅샷 재호출은 fingerprint(`nps_held`/`nps_major`) skip. 테스트 364 passed.
- **참고:** NPS의 `api.odcloud.kr`는 안정적 — 불안정은 `apis.data.go.kr` 게이트웨이에 국한.

## 2026-06-01 | 종목 적재 data.go.kr 단일화(FDR 폐기) + 시가총액 + 국민연금 + 웹 라우터 실행

- **맥락:** stocks 마스터 적재가 data.go.kr(authority) + FDR(fallback) 2소스였고 CLI로만 실행, 스케줄 미설정. 사용자 결정: **FDR 폐기**하고 data.go.kr 공식 OpenAPI로 단일화, 시가총액·시총순위 보강, 적재를 **웹 라우터(+스케줄)로 트리거**. UI는 미변경(아이콘 노출은 후속 FE). **국민연금 적재는 조사 후 보류 → backlog**.
- **결정:**
  - **FDR 제거**: `fetch_finance_data_reader`·`finance-datareader`(seed poetry 그룹) 삭제. 키 없는 fallback이 사라져 **data.go.kr 키가 hard 의존성으로 격상**.
  - **소스 = data.go.kr 3개 서비스(상호보완)**: KRX상장종목정보(`getItemInfo`, 주식 name authority) + 증권상품시세(`getETF/ETNPriceInfo`, **ETF/ETN coverage = FDR 대체** + 시총) + 주식시세(`getStockPriceInfo`, 주식 시총). 증권상품시세는 coverage 파이프라인(preserve 소스)과 marcap 단계 양쪽에 사용. 기존 authority/preserve/fingerprint/Naver 프레임워크 유지.
  - **시총(`024_stocks_marcap.sql`)**: `marcap`(bigint), `marcap_rank`(int, 주식 KOSPI+KOSDAQ 시총 내림차순 window 순위; ETF/ETN·미적재 NULL), `marcap_as_of`(basDt). marcap은 매일 변동 → **fingerprint skip 우회 always-run**. 시세 API는 **basDt(직전 영업일) 날짜키** + T+1 발행이라 빈 응답 시 최대 7일 거슬러 fallback. basDt(YYYYMMDD str)는 date 컬럼이라 `_basdt_to_date`로 변환(실DB 검증으로 잡은 버그).
  - **웹 라우터**: `POST /admin/seed/stocks` — `X-Admin-Token` 헤더(env `ADMIN_TOKEN`, constant-time 비교) guard → `BackgroundTasks`로 즉시 202. **백그라운드 seed는 `Depends(get_pool)` 미사용** — CLI처럼 자체 `asyncpg.connect()`(session advisory lock 수 분 보유 → 풀 차용 시 고갈·lock leak 방지).
  - **모듈 이동**: seed 본체 `scripts/seed_stocks.py` → `src/invest_note_api/services/stock_seed.py`(라우터·CLI 공유). scripts는 thin shim(sys.path 보존).
  - **국민연금 적재 보류**: 단일 컬럼/수동 업로드 설계까지 마쳤으나, odcloud 자동 fetch가 **연도별 uddi 상이·최신 지칭 엔드포인트 없음**으로 자동화 부적합 + 연 1회 데이터라 가치 대비 비용 큼 → 이번 범위에서 제외하고 backlog 이관(조사 결과 `docs/backlog.md` 보존). **(⚠️ 2026-06-02 이 "자동 fetch 부적합" 판정은 철회됨 — 상단 항목 참고. infuser OAS 엔드포인트를 놓친 오판.)**
- **스케줄:** 외부 cron / Coolify scheduled task가 매일 ~14:00 KST(FSC T+1 발행 이후) 호출. 중복=advisory lock, 무변경=fingerprint-skip 가드.
  ```
  curl -fsS -X POST -H "X-Admin-Token: $ADMIN_TOKEN" https://<api>/admin/seed/stocks
  ```
- **트레이드오프/리스크:** ① 증권상품시세·주식시세는 **서비스별 활용신청 별도 필요**(같은 serviceKey) — 누락 시 `SERVICE_KEY_IS_NOT_REGISTERED`(403). ② 신규 fetcher 응답 키(`srtnCd`/`itmsNm`/`mrktTotAmt`)는 **스파이크 미해소**(실서버 확인 필요, 코드에 ⚠️ 주석). ③ marcap_rank는 verbatim SQL이라 이전에 순위 있던 종목이 marcap fetch에서 빠지면 stale rank 잔존(엣지).
- **재평가 트리거:** getItemInfo의 ETF/ETN 포함 여부 실측 → 포함 시 증권상품시세는 marcap 전용으로 축소 가능.

## 2026-05-30 | 종목 검색/매칭을 자체 stocks 마스터로 전환 (2026-04-28 Naver 단일화 역전)

- **맥락:** 2026-04-28 에 종목 검색·일괄 import 매칭을 Naver 자동완성 단일 경로로 단순화하고 `stocks` 마스터를 폐기(`016_drop_stocks.sql`)했었다. 폐기 사유는 ① coverage(KIND 시드가 ETF/ETN/우선주 누락), ② matchability(정확 일치만 → 약칭 불가). 이번에 backlog 재도입 트리거 ①(ETF/약칭 커버 소스 확보)을 동기로, 자체 데이터 운영으로 재추진. 사용자 결정: **런타임 Naver 완전 대체** + 검색·import 양쪽 적용 + 해외 포함 설계 + **주기 갱신** + **다중 소스** + **Naver 도 적재 소스로 사용**.
- **결정:**
  - `stocks` 마스터 재도입(`020_recreate_stocks.sql`): (country_code, ticker) PK, `market` CHECK 제거(ETF/ETN 수용), `pg_trgm` + `name_chosung`(초성) + `stock_aliases`(alias_chosung 포함).
  - **런타임은 로컬 DB 만 조회**(외부 호출 0): `routers/stocks.py:/search` → `stocks_repo.search`, `broker_import/ticker_resolver.py` → `stocks_repo.lookup_by_names`. 검색 우선순위 ticker/명 prefix/별칭/초성(명+별칭)/부분일치(trgm).
  - **Naver 는 런타임 fallback 이 아니라 적재(batch) enrichment 소스**: `scripts/seed_stocks.py` 가 다중 소스(공공데이터포털 금융위 coverage + Naver 약칭 + 교차 소스 명칭 변형)를 멱등 UPSERT 하고, 상폐는 `is_active` soft-delete. `external/naver_search.py` 는 런타임에서 빠지고 seed enrichment 용으로만 유지.
  - 약칭(공식 소스에 없음)은 **수동 시드 + 종목별 Naver 교차검증(이름 변형) + 교차 소스 변형명**으로 자체 소유.
- **이유:** ① "런타임 완전 대체 + Naver 적재" 를 분리하면 검색/import 가 외부 의존·지연 0 이면서도 Naver 의 약칭 해소력을 offline 으로 흡수 → 폐기 사유(matchability)를 정면 해소. ② trades 가 stocks 를 FK 참조 안 함(`001_initial_schema.sql`) → 거래 데이터 무영향. stocks/aliases 는 public read-only 라 RLS 미적용. ③ 응답 shape(`code/name/market/exchange`) 를 Naver 검색과 동일하게 유지 → FE 무변경(`exchange`=보드 KOSPI/ETF 는 `stocks.market` 에서 매핑, `stocks.exchange`='KRX' 아님).
- **트레이드오프:**
  - **데이터 미적재 시 검색/import 가 degraded**(빈 결과). 마이그레이션+코드 배포 후 seed 가 1회 돌기 전까지 비어 있다. **배포 순서: 마이그레이션 → seed 1회 실행 → 기능 정상.**
  - **coverage = 다중 소스 순차 병합(`021_seed_source_state.sql`).** fallback(택1) 아님 — 우선순위 순으로 모든 소스를 병합: 첫 번째로 데이터를 반환한 소스가 canonical(이름 authority, overwrite), 이후 소스는 신규 ticker 추가 + 같은 ticker 인데 이름 다르면 그 이름을 `stock_aliases(source=소스명)` 로 등록. soft-delete 는 어떤 소스에도 없는 ticker 기준(`updated_at` 아님 — skip 과 양립). 소스 우선순위: data.go.kr(공식, 키 필요) → FDR(`finance-datareader`, 키 불필요, `seed` poetry 그룹). data.go.kr 다운이면 FDR 가 authority.
  - **효율화(변경 드문 데이터):** 소스별 내용 fingerprint(sha256) 를 `seed_source_state` 에 저장 → 무변경 소스는 UPSERT/별칭 skip, 아무 소스도 안 바뀌면 soft-delete 도 skip. 무변경 run = fetch + 해시비교만. 가드: `stocks` 가 비어있으면(db reset/out-of-band wipe) stale fingerprint 를 무효화해 전체 재적재.
  - **종목별 출처 기록(`023`, `stocks.source`):** canonical(이름·시장)을 소유한 authority 소스를 종목마다 기록(`fdr`|`data_go_kr`|...). authority 가 overwrite 시 갱신, 하위 소스 preserve 시 보존. 어느 소스 분류를 신뢰 중인지 추적 → market 불일치 판정·소스 전환 추적에 활용.
  - **종목별 Naver 교차검증(`022`, `stocks.naver_checked_at`):** 미검증 종목을 코드로 Naver 조회해 ① 이름 변형→별칭, ② 시장(typeCode) 교차검증. `naver_checked_at` 으로 종목당 1회만(신규만 추가 질의), 병렬(동시 8) + run 당 batch(1500)로 rate-limit·전수호출 비용 가드. 실측: 이름은 거의 일치(별칭 ~0), 시장 불일치 다수(FDR 가 ETF/KR 에 포함한 알파벳코드 종목을 Naver 는 KOSPI 로 분류 — ELW/파생 오분류 의심). 현재는 불일치 **집계·보고만**(자동 수정 안 함).
  - 실측: FDR 로 주식 2878 + ETF 1130 = **ETF 포함 확인**(스파이크 해소). **ETN 은 FDR 미지원 → 미커버(후속, 별도 소스).** data.go.kr 은 2026-05-30 키 체계 변경(base64→64hex)·신규 키 활성화 지연(401→403)으로 당일 사용 불가 → FDR 만으로 운영 가능. KRX 공식 OpenAPI 는 "비상업적" 제약이라 상업 앱엔 부적합(제외).
  - 약칭 초기 커버리지 < Naver(수동 시드 수준) → 수동 시드 확충으로 보완(자동 약칭 수집/검색-miss 환류는 미도입).
  - 주기 batch(cron 1일 1회) 유지 비용 = 이전 폐기의 "마스터 유지 비용". 멱등 스크립트로 최소화.
- **재평가 트리거:** ① data.go.kr 가 ETF/ETN 미포함으로 확인되면 ETF/ETN 별도 소스 wiring. ② Naver 적재 차단/포맷 변경 시 enrichment 만 graceful skip(런타임 검색은 무중단). ③ 해외 종목 적재 착수 시 currency/거래소/환율 설계.

## 2026-05-27 | 포트폴리오 요약 시세 조회를 요청 경로에서 분리 (옵션 B) — withQuotes opt-in + holdings additive

- **맥락:** "API 성능 개선" 요청. `/portfolio/summary`(홈 대시보드 단일 데이터 소스)가 요청 처리 중 네이버/야후 시세를 동기 fetch(개별 2s/전체 5s deadline)한 뒤 평가금액·평가손익·총계를 계산 → 외부 API 지연·캐시 미스 시 홈 응답이 통째로 지연. "현재 시세 로직을 BE→FE 이전"과 "API 속도 개선"은 동치가 아님을 확인하고(전자는 옵션 A=FE 네이버 직접 호출, CapacitorHttp/CORS·도메인 중복 부담), 목표가 후자임을 받아 결정.
- **결정 (옵션 B):**
  - **`/portfolio/summary` 에 `withQuotes` opt-in 파라미터(default True)** 추가. 신규 FE 만 `withQuotes=false` 전송 → `fetch_quotes_by_keys` skip(시세 의존 필드 null/0, 빠른 응답). 파라미터 미전송 구버전 앱은 기존 시세 포함 응답 그대로 = 하위호환.
  - **FE 가 기존 BE `/stocks/quote` 를 병렬 호출** → `mergeQuotes`/`applyQuotesToTotals`/`applyQuotesToSnapshots` 로 **시세 의존 필드만** 클라이언트 overlay. 시세 비의존 값(수량/원가/실현손익/현금/월거래수)은 BE 값 그대로.
  - **`AccountSnapshotResponse.holdings: [{key, quantity}]` additive 필드** 신설 — 계좌별 `totalValue`(계좌 allocation 탭) overlay 에 계좌별 종목 수량이 필요(positions 의 `account_ids` 만으론 다계좌 종목 분배 불가). 2026-05-23 결정문이 "계좌별 수량 미직렬화 → 클라 집계 불가" 를 이유로 BE 필터링을 택했는데, 이번엔 **snapshots 한정**으로 계좌별 수량을 직렬화(`Position` 은 그대로 `account_ids` 만 유지).
  - **옵션 A(FE 네이버 직접 호출) 기각** — CapacitorHttp/CORS·도메인 중복·웹 dev 분기 부담이 목표 대비 과함.
- **이유:** ① 두 엔드포인트 모두 BE라 신규 CORS/CapacitorHttp 표면 0, FE trade walker 부활 불필요(`buildPositions` 는 BE 가 제공) → `sort_for_calc` 패리티 리스크 없음. ② additive `holdings` + `withQuotes` default True 로 구버전 앱 무영향(강제 업데이트 불필요). ③ 시세 의존 필드만 overlay → BE `merge_quotes`/`build_totals` 와 공식 동일, shape drift 최소. `buildTotals`/`buildAccountSnapshots`(trades 재순회) 는 BE 불일치 위험으로 재사용 금지.
- **트레이드오프:**
  - **버전 skew 크래시(실제 발생·수정 완료):** 신규 FE 가 `.env.production` 으로 빌드돼 **미배포 구 BE** 를 치면 응답에 `holdings` 부재 → `applyQuotesToSnapshots` 가 `undefined` 순회로 `TypeError` → 홈 렌더 크래시(Next.js global-error "This page couldn't load"). `snapshot.holdings ?? []` 가드로 graceful degrade(stockEvaluation 0/현금) 처리. **배포 순서: BE 먼저 → FE.**
  - 시세 캐시 주체가 summary → `/stocks/quote` 로 이동(여전히 BE 45s single-flight 공유, 외부 호출량 증가 없음).
  - 계좌별 탭 `stockEvaluation` 은 BE 배포 전까지 0(graceful). **측정(Step 0)은 사용자 결정으로 생략** — 배포 후 효과 미확인 시 진짜 병목 재조사 필요.
- **재평가 트리거:** ① 분석 대시보드 `/analysis/dashboard` 도 동일 동기 fetch → 같은 패턴 적용 검토(backlog, concentration cost_basis fallback 차이로 별도). ② 배포 후 summary 응답시간 개선이 체감 안 되면 진짜 병목(DB 전량 로드/콜드부트/네트워크 RTT) 재조사 — backlog "포트폴리오/분석 읽기 경로 전량 로드 최적화" 와 연계.

---

## 2026-05-26 | 앱 강제 업데이트 메커니즘 — BE env 계약 + plain div 오버레이 + 2중 fail-open

- **맥락:** Capacitor 단일 배포 앱은 JS 번들이 빌드 시 박혀 설치되므로, 호환성 깨는 변경(예: BE legacy `/api/*` alias 제거, 2026-05-20 결정문)을 안전하게 진행하려면 옛 번들 사용자를 강제로 새 번들로 이동시키는 수단이 필요했다. 기존엔 그 수단이 없었음.
- **결정:**
  - **저장소·계약:** BE env `MIN_SUPPORTED_VERSION`(단일, 양 플랫폼 공통) + `STORE_URL_IOS`/`STORE_URL_ANDROID`. 인증 없는 `GET /app-config` 가 `{minSupportedVersion, storeUrl:{ios,android}}`(CamelModel) 로 응답. legacy `/api/*` alias 등록 루프에서는 제외.
  - **비교 단위:** `versionName`(semver "1.1.13") — `App.getInfo().version`(iOS `CFBundleShortVersionString` / Android `versionName`). build/`versionCode` 는 플랫폼별로 갈리고 재심사 시 변동되어 미사용.
  - **단일 min 버전:** 플랫폼별 분리 대신 공통 단일값. lockout 방지는 "양 스토어 모두 신버전 승인 후에만 min 인상" 운영 규칙으로 처리.
  - **오버레이:** Radix Dialog 가 아닌 plain fixed `inset-0` div — ESC·외부 클릭이 본래 동작하지 않아 자동 차단. Android 하드웨어 백버튼만 명시적으로 swallow.
  - **하드 업데이트만:** 해제 불가 강제만 구현. "최신 버전" 안내·소프트(권장) 업데이트는 제외.
- **이유:** ① `versionName` 은 양 스토어가 공유하는 유일한 안정 식별자 — `versionCode`/build 는 플랫폼·재심사마다 어긋남. ② plain div 오버레이는 Dialog 의 dismiss 경로(ESC/backdrop)를 원천적으로 갖지 않아 가장 단순하게 해제 불가를 보장 — Dialog 를 쓰면 오히려 dismiss 를 막는 코드를 추가해야 함. ③ 단일 min + 운영 규칙이 플랫폼별 min 관리보다 단순하고 lockout 표면적이 작음. ④ public `/app-config` 는 인증 의존이 없어 로그인 전에도 게이트가 동작.
- **트레이드오프:**
  - **baseline 한계:** 체크 로직이 포함된 이번 릴리즈 이후 번들부터만 강제 가능. 이미 배포된 옛 번들은 `/app-config` 를 호출하지 않으므로 강제 불가 — 설계상 불가피하며 이번 릴리즈가 향후 강제 업데이트의 baseline.
  - **fail-open 2중 방어:** env 미설정(빈 문자열) → 강제 안 함, 네트워크 실패 → 강제 안 함. lockout 위험을 낮추는 대신 BE 장애 시 강제 업데이트가 일시 무력화됨.
  - 단일 min 버전이라 한 플랫폼만 먼저 승인된 상황에서 min 을 올리면 미승인 플랫폼 사용자가 lockout — "양 스토어 승인 후 인상" 운영 규칙 준수에 의존. Apple App ID 미발급 상태라 `STORE_URL_IOS` 주입은 첫 출시 후로 미뤄짐(빈 URL 모달 방지 위해 URL 먼저 설정 후 min 인상).
- **재평가 트리거:** ① 플랫폼별 출시 주기가 크게 어긋나 단일 min 운영이 부담되면 플랫폼별 min 분리. ② 소프트(권장) 업데이트 UX 요구가 생기면 강제/권장 2단계로 확장. ③ 강제 업데이트 게이트가 모든 사용자를 새 번들로 옮긴 시점 → legacy `/api/*` alias 제거(2026-05-20 결정문 3단계) 진행.

---

## 2026-05-23 | 홈 계좌 필터 — BE `/portfolio/summary` 에 accountId 도입 + invalidate scope 확대

- **맥락:** 메인(`HomeDashboard`)에 계좌 필터 칩을 추가. 2026-05-03 결정문은 AccountFilter 를 "클라 메모리 필터링(BE 영향 0)" 으로 정의했으나, 이는 기록 페이지(`TradeList`)의 단순 리스트 필터에만 한정된 결정이었음. 메인의 집계는 BE 도메인 로직(`build_positions`/`build_account_snapshots`/`build_totals`)을 거쳐 다단계로 계산되므로 클라이언트만으로는 정확히 좁힐 수 없음.
- **결정:**
  - **BE 필터링 채택**: `GET /portfolio/summary?accountId=...` 옵션 쿼리 파라미터 추가. 지정 시 trades 와 accounts 를 그 계좌로 좁힌 뒤 기존 도메인 함수 재사용. 미지정 시 기존 합산 동작 유지. `has_accounts` 는 글로벌 기준(EmptyState "계좌 만드세요" 가 잘못 뜨지 않도록), `has_trades` 는 필터된 결과 기준.
  - **`queryKeys.portfolioSummary` 함수화**: `(accountId: string | null) => ["portfolio", "summary", accountId]` 로 변경해 calc 별 캐시 분리. invalidate 호출처는 모두 prefix `queryKeys.portfolio` (`["portfolio"]`) 로 전환 → 모든 accountId 캐시를 한 번에 무효화.
  - **`keepPreviousData` 적용**: 칩 전환 시 이전 응답을 유지해 스켈레톤 깜박임 차단.
  - **sticky 패턴 통일**: records 와 동일하게 `<div className="sticky top-0 z-10 bg-background">` 안에 `<PageHeader sticky={false}>` + `<AccountFilter>` 를 묶어 칩이 스크롤 시 함께 고정.
- **이유:**
  - `Position` 응답에 `account_ids: list[str]` 만 있고 **계좌별 holding_quantity / cost_basis 가 분리되어 있지 않음** — 한 종목을 여러 계좌에서 보유 중일 때 클라에서 정확한 집계 불가능. BE 가 lot 단위 정보를 추가로 내려보내는 것보다 기존 도메인 로직을 입력 trades 만 좁혀 재사용하는 쪽이 변경 표면적이 작음.
  - 2026-05-03 결정은 "사용자가 클라에서 즉시 토글" 패턴에 한정된 것으로 재확인됨(본 결정문이 그 범위를 명시).
- **트레이드오프:**
  - **invalidate scope 확대**: `queryKeys.portfolioSummary` 단일 키 → `queryKeys.portfolio` prefix 로 바꾸면서, 같은 prefix 의 `queryKeys.accounts`(`["portfolio","accounts"]`)도 함께 무효화됨. 의도된 동작 — `Account.trade_count` 가 trade mutation 에 의존하므로 함께 갱신되는 게 자연스러움. trades CUD 빈도가 낮아 성능 부담 미미.
  - 칩 전환 시 BE 라운드트립이 발생(클라 즉시 토글 불가). `keepPreviousData` 로 UX 회귀 완화.
- **재평가 트리거:**
  - `Position` 에 계좌별 수량/원가가 추가로 직렬화되면 클라 필터링 회귀 가능.
  - 모바일 Capacitor resume 시 staleTime 만료로 모든 accountId 캐시가 동시에 refetch 되어 부하 이슈 보고가 들어오면 per-accountId staleTime 차등화 검토.

---

## 2026-05-22 | 거래 일괄 등록 부분 성공 정책 — 그룹 단위 제외 + ResultStep 성공 판정 완화

- **맥락:** 일괄 등록(`/trades/import/preview` → `/trades/import/commit`) 은 BE 내부적으로 이미 그룹(=계좌·종목·국가) 단위 부분 성공을 지원했음. 그러나 FE `PreviewStep` 의 `hasValidationError` disabled 가드가 정합성 위반(보유부족 SELL 등) 발생 시 commit 자체를 막아 BE 의 부분 성공 경로에 도달하지 못했음 — 한 종목에서 매도 보유부족이 1건이라도 발견되면 모든 거래(정상 다른 종목 포함)가 등록되지 않는 사용자 불만 발생. 또한 ResultStep 은 `error_count === 0` 만으로 성공을 판정해, 부분 등록이 정상 진행된 경우에도 빨간 X 아이콘 + "일부 오류 발생" 으로 표시되어 사용자가 실패로 오해했음.
- **결정:**
  - **제외 단위**: row 단위가 아닌 **그룹(종목) 단위** 로 제외. 문제 SELL 이 포함된 종목 그룹은 그 그룹의 BUY 까지 함께 commit 에서 skip, 다른 종목 그룹은 정상 등록.
  - **FE 흐름**: PreviewStep 의 정합성 위반 배너를 red → yellow 톤으로 바꾸고("일부 거래가 제외됩니다"), 등록 버튼 disabled 조건에서 `hasValidationError` 제거. 라벨에 "제외하고 N건 등록" 으로 사용자 의사 표현. 카운트 카드의 "신규 등록" 은 `excluded_count` 만큼 차감, "제외 예정" 카드에 합산.
  - **BE 메시지·메타**: `_find_import_oversell` 사용자 안내를 "거래내역서 기간을 더 길게 받아 다시 시도해주세요" → "이 종목 거래는 제외되고 나머지 거래만 등록됩니다" 로 정정. `ImportPreviewResponse.excluded_count: int` 신설해 FE 카운트 카드 정확도 확보.
  - **ResultStep 성공 판정**: `error_count === 0` → `inserted_count > 0 || merged_count > 0 || error_count === 0`. 등록·갱신이 1건이라도 발생했으면 성공(CheckCircle + "등록 완료"), errors 는 "제외된 종목" 안내로 노출. 진짜 실패(등록 0건)인 경우에만 XCircle + "등록 실패".
- **이유:**
  - ① row 단위 제외(같은 그룹에서 SELL 만 빼고 BUY 는 등록)는 사용자 발화("문제 없는 거래는 등록")와 가장 부합하지만, **BUY 만 들어가고 SELL 이 누락된 상태**가 보유 수량·PnL 을 일시적으로 왜곡함. 그룹 단위 제외는 부정합 없는 일관 상태를 보장하고, 누락 SELL 보완은 재업로드 + signature dedup 으로 자연스럽게 해결됨.
  - ② BE 는 이미 그룹 단위 부분 성공 구조였으므로 FE 차단만 풀고 메시지·메타데이터만 다듬는 최소 변경으로 사용자 요구를 충족.
  - ③ ResultStep 성공 판정은 사용자가 PreviewStep 에서 제외 항목을 **인지하고 의도적으로** "제외하고 등록" 을 클릭한 결과 — error 가 있어도 그것은 사용자가 수락한 제외이며 시스템적 실패가 아님. 빨간 X 아이콘은 이 의미를 왜곡함.
- **트레이드오프:**
  - ① 같은 그룹의 정상 BUY 도 함께 제외되므로 사용자가 매도 누락분을 보완하려면 거래내역서를 한 번 더 받아 재업로드해야 함. dedup 이 중복 등록을 막아 안전하지만, "BUY 만 정상이고 SELL 만 문제" 인 사용자는 2-step 작업을 거침.
  - ② `excluded_count` 가 그룹 row 합계라 dup 으로 분류된 row 가 포함된 경우 카운트 카드의 "신규 등록" 이 약간 낮게 표시될 수 있음 — 실제 commit 결과는 정확하므로 ResultStep 에서 보정됨.
  - ③ ResultStep 성공 판정 완화로 1건이라도 등록되면 success 표시 — 사용자가 결과 화면에서 errors 리스트를 안 읽고 지나칠 위험이 있음. errors 리스트 자체는 여전히 노출되며 헤더("제외된 종목") 로 맥락을 강조해 완화.
- **재평가 트리거:**
  - ① 사용자 피드백으로 row 단위 제외(같은 그룹의 BUY 는 살리고 SELL 만 빼기) 요구가 누적되면 재검토. 그 경우 BE `_find_import_oversell` 이 (msg, skip 인덱스) 를 반환하도록 확장하고 preview/commit 양쪽에서 row 단위로 제거.
  - ② "기존 DB 거래만으로도 oversell" (사용자가 import 하지 않은 기존 데이터 문제) 케이스가 다수 보고되면, 해당 시그널을 별도로 분리해 사용자가 데이터 정합성을 직접 손볼 수 있는 UI(수동 매칭/삭제) 추가.

---

## 2026-05-21 | shadcn 컴포넌트 primitive — base-ui → radix-ui 전환

- **맥락:** `fe/components.json` 의 `style: "base-nova"` 로 도입된 shadcn 컴포넌트들이 `@base-ui/react` 프리미티브에 의존하고 있었음. shadcn 의 표준 라인은 `@radix-ui/react-*` 이며, 향후 registry 업데이트·예제 코드·새 컴포넌트 추가 시 base-nova 변종은 호환을 잃는다. 또 `Backdrop`/`Popup`/`Positioner`·`alignItemWithTrigger`·`render` prop 등 base-ui 고유 API 가 `ui/` 9개 컴포넌트와 컨슈머 클래스명(`data-active:`, `group-data-horizontal/tabs:`)까지 새어 나가 있어 유지보수 부담이 컸음.
- **결정:**
  - `@base-ui/react` 의존을 제거하고 `@radix-ui/react-{dialog,popover,select,tabs,toggle,toggle-group,slot}` 7개 패키지로 교체. `components.json` 의 `style` 을 `"new-york"` 으로 변경.
  - `ui/` 9개(button/input/toggle/toggle-group/tabs/popover/dialog/select) 를 shadcn registry 의 표준 radix 버전을 그대로 `pnpm dlx shadcn add` 로 재설치하지 않고 **수동으로 한 파일씩 포팅**. `base/` 래퍼들이 의존하는 export 이름(`tabsListVariants`, `showCloseButton` 옵션 등)과 커스텀 className 을 보존하기 위함.
  - Button 의 `render={<X/>}` → `<Slot asChild>` 패턴. Dialog/Popover/Select 의 `Positioner`+`Popup` → `Content` 한 단계 구조. Tabs 의 `Tab`/`Panel` → `Trigger`/`Content`. data 속성 `data-open`/`data-closed`/`data-active`/`data-horizontal` → radix 의 `data-[state=*]`/`data-[orientation=*]` 로 컨슈머 코드(`TradeBasicForm.tsx`, `pnl-colors.ts`)도 함께 치환.
  - Select 의 `alignItemWithTrigger=true` (선택 아이템을 트리거 위치에 정렬) 동작은 radix 에 1:1 대응 없음 → `position="popper"` + `align="center"` 기본값으로 시각 근사 매칭.
  - 컨슈머가 한 곳도 직접 `@/components/ui/*` 를 import 하지 않는다는 AGENTS.md 규칙이 이미 지켜져 있어, ui/ 내부 재작성만으로 컨슈머는 영향 없음.
- **이유:** ① 표준 radix 정합으로 향후 shadcn 업데이트·신규 컴포넌트 추가가 마찰 없음. ② shadcn registry 재설치 대신 수동 포팅을 택한 이유는 (a) 기존 `base/` 래퍼·variant·옵션을 보존하기 위함, (b) 컴포넌트 간 미세한 className 충돌(`new-york` 표준 스타일과 우리 토큰 차이)을 점진적으로 흡수할 수 있기 때문. ③ Select `position="popper"` 채택은 모바일 우선 UX 에서 더 자연스럽고(드롭다운이 트리거 아래로 펼침), `alignItemWithTrigger` 의 "선택된 아이템 정렬" 은 다항목 리스트에서만 가치가 있는데 invest-note 의 Select 사용처(계좌 선택, 일반적으로 1~3개)에서 효용이 낮음.
- **트레이드오프:** ① Select 의 시각 동작이 base-ui 와 미세하게 달라짐 — "선택된 아이템이 트리거 위에 겹쳐 나타나는" 동작이 사라지고 트리거 아래로 펼침. 실기기 회귀 가능성 있어 후속 모바일 QA 권장. ② `base-nova` → `new-york` 스타일 토큰 차이(그림자/radius/색)가 잠재적으로 존재하나 우리는 ui/ 컴포넌트의 className 을 그대로 옮겼으므로 즉각 차이는 없음. ③ React Hook Form Controller 의 `onValueChange` 가 radix 에서는 `(value: string) => void` 시그니처로 좁아져 `TradeBasicForm.tsx` 에 `v as TradeType` 캐스팅 1건 추가. ④ Tabs trigger 의 `fireEvent.click` 이 라dix-tabs controlled mode 에서 testing-library `fireEvent` 만으로 active 상태 갱신이 즉시 반영되지 않아, `TradeBasicForm.test.tsx` 의 매도 탭 클릭을 `userEvent.click` 으로 교체. ⑤ radix Select 가 form 통합을 위해 hidden native `<select>` (BubbleSelect) 를 함께 렌더 → 동일 옵션 라벨 텍스트가 DOM 에 2회 존재. 테스트에서 `getByText` 가 중복 매칭되어 `getByRole("combobox")` 의 textContent 검증으로 보정.
- **재평가 트리거:** ① Select 의 popper 동작이 사용자 피드백/QA 에서 문제 보고되면 radix Select 의 `item-aligned` mode 로 전환 검토. ② shadcn 이 new-york → new-york-v5 같은 신규 style 을 표준화하면 그때 `style` 마이그레이션. ③ 다른 컨슈머가 ui/ 의 새 prop(예: Dialog `forceMount`) 을 필요로 하면 그때 표준 radix 시그니처에 맞춰 점진 확장.

---

## 2026-05-20 | BE 라우터 prefix 단축 — `/api/*` legacy alias 동시 지원 (1단계)

- **맥락:** 운영 도메인이 `api.invest-note.pixelwave.app` 서브도메인으로 분리되면서 라우터 path 의 `/api/` prefix 가 의미상 중복이 되었다. 단축이 자연스럽지만 ① Capacitor Android 앱은 JS 번들이 빌드 시 박혀 설치되므로 기존 설치 사용자는 강제 업데이트 전까지 옛 경로로 호출하고, ② BE/FE 가 별도 배포라 동시 전환 보장이 어렵다. 한쪽만 바꾸면 전체 기능이 즉시 마비.
- **결정:**
  - 1단계(본 결정): 각 라우터의 `prefix` 를 `/api/<resource>` → `/<resource>` 로 단축하고, `main.py` 에서 동일 라우터를 `include_router(router, prefix="/api", include_in_schema=False)` 로 한 번 더 register 해 legacy alias 를 유지. OpenAPI/Swagger 에는 새 경로만 노출.
  - 테스트는 새 SOT 경로로 일괄 치환하고, legacy 동등성은 `tests/test_legacy_api_prefix.py` 한 곳에서 status + body 비교로 검증.
  - 2단계(후속 spec): FE `api-client.ts` ROUTES 의 `/api/` 제거 + 모바일 앱 강제 업데이트 게이트 + 새 번들 배포.
  - 3단계(후속 spec): legacy alias 등록 제거(sunset). 시점은 강제 업데이트 게이트 이후 + 모니터링에서 `/api/*` 트래픽이 사라지면.
- **이유:** ① 같은 라우터 객체를 두 번 include 하는 패턴은 FastAPI 표준 — 새 코드 작성 없이 무중단 prefix 전환 가능. ② `include_in_schema=False` 로 docs 중복 노출이 차단되어 신규 사용자/외부 consumer 에게는 새 경로만 보임. ③ 테스트가 새 경로 SOT 를 따라야 한다 — legacy 는 alias 이며 "동일 응답" 만 한 곳에서 보장하면 충분. ④ 단일 PR revert 로 원복 가능 — 본 spec 은 BE 내부 변경만이라 FE/앱 호환성 회귀 위험은 BE 내부에 한정.
- **트레이드오프:** ① 같은 라우터를 두 번 include 하면 FastAPI 가 operation_id 중복 경고를 낼 수 있음 (`include_in_schema=False` 로 스키마 영향은 없으나 기동 로그에 잔재). ② legacy alias 가 살아 있는 동안에는 두 경로 응답 동등성을 새 엔드포인트 추가 때마다 의식해야 함 — 단일 라우터 객체를 그대로 등록하므로 자동 동등하지만 라우터 분기/middleware 가 path-prefix 기반이면 깨질 수 있음. ③ legacy 가 OpenAPI 에서 빠지므로 옛 경로로 호출하는 외부 도구는 docs 만으로 발견 불가 — 본 spec 의 범위가 invest-note 자체 클라이언트에 한정됨이 전제.
- **재평가 트리거:** ① 옛 앱 버전 점유율이 충분히 줄어 강제 업데이트 게이트가 모든 사용자를 새 번들로 옮긴 시점 → 3단계(alias 제거) 진행. ② OpenAPI operation_id 중복 경고가 도구 체인에 실제 문제를 일으키면 `generate_unique_id_function` 으로 legacy 쪽만 다른 prefix 적용.

---

## 2026-05-20 | 계정 탈퇴 & 로그아웃 강건화 — Supabase Admin REST 직호출 + 클라이언트 finally redirect

- **맥락:** App Store Review (1.0_15) 에서 두 건 reject — ① Guideline 5.1.1(v): 계정 생성이 있으면 탈퇴도 필요, ② Guideline 2.1(a): 리뷰어 환경(iPhone 17 Pro Max / iOS 26.5)에서 "Unable to sign out". 로그아웃은 개발자 환경에서 재현 불가지만 코드 분석 결과 catch 후 `setPending(false)` 만 실행하고 `queryClient.clear()` / `router.replace` 가 누락된 채 `AuthGuard.onAuthStateChange` 에 의존하는 구조였음.
- **결정:**
  - **탈퇴**: `BE DELETE /api/me` 신설. Supabase Auth 사용자 삭제는 `${SUPABASE_URL}/auth/v1/admin/users/{user_id}` 로의 **httpx 직접 호출** (supabase-py 미도입). `auth.users` 삭제 시 `accounts`/`trades` 는 FK `on delete cascade` 로 자동 정리. 키 누락 시 503, 외부 호출 실패/4xx/5xx 응답은 502 매핑.
  - **키 명칭**: `SUPABASE_SECRET_KEY` (FE 와 통일). Supabase 신규 키 형식 `sb_secret_*` 사용 — 구 명칭 `service_role` 은 `supabase status` 출력에서 제거됨.
  - **라우터 prefix**: me 라우터를 `APIRouter(prefix="/api/me")` 로 변경하고 path 는 `""` 로 정의. accounts/trades 등과 컨벤션 통일 + 기존 GET `/me` 의 잠재 404 동시 해결.
  - **FE 로그아웃**: `supabase.auth.signOut({ scope: "local" })` + `try/catch` + `finally` 에서 `queryClient.clear()` + `router.replace("/login")` 강제. 에러는 `console.error` + sonner toast 로 가시화. AuthGuard 의존 제거.
  - **FE 탈퇴 UX**: 설정 → "계정" 섹션에 `DeleteAccountSection`. destructive 버튼 → `ConfirmDeleteDialog` 경고 ("탈퇴 시 모든 데이터 영구 삭제, 복구 불가") → 확정 시 `meApi.deleteAccount()` → 로컬 signOut + redirect.
- **이유:** ① supabase-py 도입은 BE 의존성/이미지 사이즈 증가에 비해 호출 1건. 기존 패턴(`httpx.AsyncClient` + lifespan 공유)으로 충분. ② Supabase 신규 키 형식이 표준이고 FE 가 이미 `SUPABASE_SECRET_KEY` 로 통일되어 BE 만 다른 명명을 두면 혼선. ③ 로그아웃 실패의 본질은 "서버 호출 결과와 무관하게 클라이언트가 로그아웃되었다고 인지하는가" — `scope: "local"` 은 서버 콜을 생략해 네트워크/스토리지 오류와 무관하게 로컬 토큰만 무효화, `finally` 는 try 경로와 catch 경로 모두에서 동일한 정리·이동을 보장. ④ Admin REST 호출 path 는 안정적이고 RLS 와 무관하게 service-role 권한으로 동작 — `acquire_for_user` 컨텍스트가 불필요.
- **트레이드오프:** ① `SUPABASE_SECRET_KEY` 가 BE 시크릿에 별도 필요 — 운영 환경 누락 시 탈퇴 503 (이슈는 `docs/backlog.md` 에 등록). ② `auth.users` cascade 에 의존하므로 향후 `user_id` 컬럼을 가진 새 테이블이 cascade 없이 추가되면 탈퇴가 FK 위반으로 실패 (가드는 backlog 항목). ③ 로그아웃 강건화는 추정 기반 fix — 리뷰어 환경에서 실제 원인이 무엇이었든 사용자 입장에서 항상 `/login` 으로 이동하므로 증상이 사라짐.
- **재평가 트리거:** ① BE 에서 Supabase 측 호출이 2~3건 이상 누적되면 supabase-py 도입 재검토. ② `auth.users` cascade 정책으로 부족한 부수 정리(예: 외부 S3 객체) 가 생기면 hard delete + soft delete 혼합 또는 별도 `delete_user_data()` SQL function 추가 검토.

---

## 2026-05-19 | 법적 문서·랜딩 호스팅 — pixelwave-web 모노레포 + `api.<project>.pixelwave.app` 분리

- **맥락:** 프로덕션 배포 준비 중. 그동안 개인정보처리방침은 `freshope.github.io/invest-note-legal` (단일 HTML, GitHub Pages) 에 두고, 서비스 이용약관은 미작성. API 는 `invest-note.pixelwave.app` 단일 서브도메인이 점유. 신규 `pixelwave.app` 도메인을 구입했고 향후 다른 Pixelwave 프로젝트(`b2c`, `claimon`, `today-alive` 등 워크스페이스에 이미 존재) 도 같은 패턴으로 운영 예정. 지원 이메일은 개인 `freshope@gmail.com` 상태였음.
- **결정:**
  - **저장소**: 프로젝트별 분리(`<project>-site`) 대신 통합 모노레포 `freshope/pixelwave-web`. `sites/<project>/` 폴더당 Cloudflare Pages 프로젝트 1개 (Root directory 옵션 사용). `shared/` 에 디자인 토큰·푸터 템플릿을 두어 다음 프로젝트의 시드로 사용.
  - **도메인 패턴**: `<project>.pixelwave.app` = 랜딩 + 법적 문서(CF Pages), `api.<project>.pixelwave.app` = API. 기존 `invest-note.pixelwave.app` (API) 를 `api.invest-note.pixelwave.app` 으로 이전. `pixelwave.app` 루트는 당분간 invest-note 로 301 리다이렉트(`sites/hub/_redirects`).
  - **법적 문서 위치**: FastAPI BE 에 두지 않고 별도 정적 사이트로 분리. 약관은 이번에 신규 작성, 개인정보처리방침은 기존 콘텐츠 이관 + Apple/Cloudflare 위탁 추가 + 시행일 갱신.
  - **이메일**: 프로젝트별(`support@<project>.pixelwave.app`) 대신 단일 `support@pixelwave.app`. Cloudflare Email Routing → `freshope@gmail.com` 포워딩. `be/pyproject.toml` authors 와 모든 정적 사이트 푸터를 새 주소로 일괄 갱신.
  - **레거시**: `freshope/invest-note-legal` 저장소는 archive 대상.
- **이유:** ① 약관/개인정보는 프로젝트 간 80% 동일 보일러플레이트 → 통합 저장소가 재사용·일관성 유리. ② BE 에 정적 페이지를 추가하면 인증 미들웨어·CORS·RLS 경로에서 공개 페이지 분기 분기점이 늘어 RLS 회피 사고 위험. ③ 단일 도메인이 랜딩+API 를 동시 호스팅하면 CDN 캐시·OAuth redirect_uri·CORS 가 충돌. `api.*` 패턴은 의미가 명확하고 충돌 없음. ④ 서브도메인 메일은 별도 MX 필요해 프로젝트 추가마다 반복 비용 발생 — root 도메인 단일 인박스 + Gmail 라벨 분리가 운영 부담 가장 낮음. ⑤ Cloudflare 가 DNS/Pages/Email 을 한 콘솔에서 통합 관리 — 같은 vendor 안에서 끝남.
- **트레이드오프:** ① 모노레포 → 한 PR 이 여러 사이트에 영향 가능. CF Pages 의 root directory 빌드 트리거가 이를 완화하지만 큰 변경은 사이트별 PR 권장. ② `shared/styles/base.css` 와 `sites/<name>/styles.css` 가 물리적으로 분리되어 sync 부담 — 사이트 3 개 이내는 수동 OK, 늘어나면 빌드 단계에서 자동 복사. ③ API 도메인 이전으로 OAuth redirect URI (Google/Apple/Kakao/Supabase) · BE 운영 설정 · FE `NEXT_PUBLIC_API_BASE_URL` · 모바일 빌드까지 모두 갱신 필요했음 (이번 작업에서 완료). ④ 단일 `support@` 이메일이라 프로젝트별 인박스 분리는 Gmail 필터에 의존. ⑤ 발신은 무료 구성에서 개인 Gmail 로 보내져 발신자 표기는 개인 메일임 — 도메인 발신이 필요해지면 별도 비용.
- **재평가 트리거:** ① 사이트가 5 개 이상으로 늘어 `shared/styles` ↔ `sites/*/styles.css` 수동 sync 가 부담스러워지면 빌드 스크립트 도입. ② 시스템 발신 메일(인증·알림) 요구가 생기면 Google Workspace 또는 Resend/Mailgun 도입. ③ 프로젝트 간 디자인 시스템이 크게 분기되어 공통 자산 가치가 사라지면 모노레포 → 프로젝트별 저장소 분리 검토. ④ `pixelwave.app` 루트가 invest-note 단독 리다이렉트로 충분치 않아지면 (다른 프로젝트가 출시되면) 진짜 허브 페이지로 전환.

---

## 2026-05-19 | Apple Sign In — Supabase OAuth web flow 통일 (Native SDK 미사용)

- **맥락:** App Store Review Guideline 4.8 충족을 위해 Apple Sign In 추가가 필요. 구현 선택지는 ① iOS Native(`@capacitor-community/apple-sign-in` + `signInWithIdToken`), ② Supabase OAuth web flow(Google/Kakao와 동일), ③ 둘 다(iOS만 native) 였음.
- **결정:** ②번 — Google/Kakao와 동일하게 Supabase `signInWithOAuth({provider:"apple"})` + Capacitor InAppBrowser deep-link 패턴을 그대로 재사용. iOS 네이티브 Sign in with Apple SDK 는 도입하지 않음. `fe/src/app/login/page.tsx` 의 `handleSocialLogin(provider)` 시그니처를 `"google" | "kakao" | "apple"` 로 확장하기만 함.
- **이유:** ① 기존 OAuth 흐름이 PKCE + 딥링크 핸들러(`CapacitorDeepLinkHandler.tsx`)로 provider 무관하게 동작하도록 일반화되어 있어, Apple 만 별도 코드 경로를 두면 분기가 늘어남. ② Apple Developer 자격증명 발급/Supabase secret JWT 생성 등 사전 설정 비용이 큰데 그 위에 native plugin 까지 추가하면 도입 부담이 가중. ③ 첫 통합은 동작 확보가 우선 — 심사·UX 피드백을 본 뒤 native 도입을 결정하는 게 합리적.
- **트레이드오프:** ① iOS Human Interface Guidelines 의 system Sign in with Apple 버튼(`ASAuthorizationAppleIDButton`) UX 를 제공하지 못함 — 검정 배경 + 흰 사과 로고의 일반 OAuth 버튼으로 대체. ② 로컬 dev 환경(`http://127.0.0.1:64321`) 에서 동작 검증이 불가 — Apple 은 `https://` + 공개 도메인 redirect_uri 만 허용. cloud/staging 환경에서만 실제 흐름 테스트 가능. ③ Apple 의 `privaterelay.appleid.com` relay 이메일 때문에 기존 Google/Kakao 사용자가 Apple 로 로그인 시 별도 `auth.users` row 가 생성됨 — Supabase 자동 identity linking 은 verified email 일치 시에만 동작하므로 우회 불가. Manual Identity Linking 은 후속 spec(`docs/backlog.md`) 으로 분리.
- **재평가 트리거:** ① App Store 심사에서 native Sign in with Apple 버튼 요구로 거절되거나 사용자 피드백이 누적되면 native plugin 도입. ② 사용자 중복 계정(같은 사람이 Google + Apple 둘 다 사용) 문의가 누적되면 Manual Identity Linking 도입.

---

## 2026-05-18 | 거래내역서 머지 정책 — update_trade_from_import 분리 + 필드 화이트리스트

- **맥락:** 거래 일괄 등록(`/import/commit`) 은 기존 동일 시그니처 거래를 **단순 skip** 만 했음. 사용자는 거래내역서를 여러 번 받아 update 가 필요하지만, 거래마다 수동으로 기록한 메모(`buy_reason`/`sell_reason`)·전략(`strategy_type`)·감정(`emotion`)·근거(`reasoning_tags`) 는 보존되어야 함. 또한 거래내역서에 정확한 체결 시각이 있으면 09:00 고정 대신 그 시각으로 정밀도를 높이고 싶음.
- **결정:**
  - **머지 키**: `(account_id, traded_date, ticker_or_asset_name, trade_type, quantity, price)` (`be/src/invest_note_api/domain/trade_import.py` `TradeSignature` — 기존 dedup 키 유지). 사용자 명시 키에는 `trade_type` 이 빠져 있었지만 BUY/SELL 머지는 회계 부정합(PnL 망가짐)을 만들어 안전상 포함.
  - **머지 갱신 필드 = `commission`/`tax`/`traded_at`** 만 (`be/src/invest_note_api/domain/trade_import.py::build_merge_patch`). `market_type`/`country_code`/`exchange` 는 거래내역서가 사용자 수동 분류를 덮어쓸 위험이 있어 **보존**.
  - **머지 전용 update 경로 분리**: `db_ops/trades_repo.py::update_trade_from_import()` 신규. 허용 필드 = `{commission, tax, traded_at}` 화이트리스트. 기존 `patch_trade()` 의 `TRADE_FIELD_META` 에는 `traded_at` 없음 — PATCH 엔드포인트에서 사용자가 거래 시각을 직접 바꿀 수 없게 한 의도된 보안 모델을 머지에서만 우회.
  - **SELL 자동 산출 필드**(`profit_loss`/`avg_buy_price`/`holding_days`/`result`/SELL의 `emotion`/`reasoning_tags`/`strategy_type`)는 머지 후 `recalc_group_pnl()` 이 자동 재계산.
  - **응답 분리**: `ImportCommitResponse` 에 `merged_count` 필드 추가. `skipped_count` 의미는 "완전히 동일하여 noop" 으로 좁아짐.
- **이유:** ① 사용자 메타 보존이 머지의 핵심 가치 — 화이트리스트로 명시하지 않으면 `commission` 추가하다 실수로 `buy_reason` 까지 덮어쓸 위험. ② PATCH 엔드포인트의 보안 모델(traded_at 불변)을 깨면 다른 경로에서도 시각 변경 가능해져 분석 결과 일관성 위협. ③ `market_type`/`exchange` 자동 갱신은 사용자가 명시적으로 원할 때만 — 거래내역서 파서가 한쪽으로 일괄 분류해 사용자 분류를 일거에 무효화하는 사고 회피.
- **트레이드오프:** ① 머지 패치 함수가 `patch_trade` 와 별도라 두 곳을 동기화 유지해야 함 — `commission`/`tax` 가 양쪽 모두 patchable. ② 완전 동일 거래는 `skipped_count` 로 분류되어 preview 의 `duplicate_count` 는 commit 후 `merged_count + skipped_count` 합으로 분해됨. ③ 시각 정보가 거래내역서마다 있을 수도 없을 수도 있어, 같은 거래가 재import 될 때 시각 정밀도가 들쭉날쭉 갱신될 수 있음 (현재는 시각이 있을 때만 갱신).
- **재평가 트리거:** ① `market_type`/`exchange` 의 사용자 수동 분류와 거래내역서 분류가 다른 사례가 다수 보고됨 → 머지 갱신 범위 확장 검토(`docs/backlog.md`). ② 사용자가 SELL 자동 산출 결과를 수동 override 하고 싶다는 요구가 생기면 `result` 등 SELL 자동 필드의 머지 보존 로직 추가 검토.

---

## 2026-05-14 | FE 모바일 빌드 API URL — 인라인 env 제거 (v1.1.7 hotfix)

- **사건:** TestFlight v1.1.6 빌드에서 모든 데이터 화면이 `"데이터를 불러오지 못했어요"` 로 실패. `https://invest-note.pixelwave.app/healthz` 는 200 정상이지만, 모바일 번들이 옛 Render 주소 `https://invest-note-api.onrender.com` 을 호출하고 있었음 (해당 도메인은 현재 Render 기본 404 응답).
- **원인:** `fe/package.json` 의 `build:mobile` 스크립트가 `NEXT_PUBLIC_API_BASE_URL=https://invest-note-api.onrender.com next build` 로 옛 Render URL 을 인라인 env 로 강제 주입. 인라인 env 가 `.env.production` (`NEXT_PUBLIC_API_BASE_URL=https://invest-note.pixelwave.app`) 보다 우선 적용되어, BE 가 79808b6 에서 Coolify 의 `invest-note.pixelwave.app` 으로 이전된 뒤에도 모바일 번들은 죽은 Render 주소를 박은 채 출시됨.
- **결정:** `build:mobile` 의 인라인 `NEXT_PUBLIC_API_BASE_URL` 제거. API URL 은 `.env.production` 단일 출처에서만 관리. `fe/package.json` 1.1.6 → 1.1.7, iOS/Android build number 6 → 7.
- **이유:** 모바일 빌드만 별도 URL 을 갖는 정당한 이유가 없음 — production build 는 어차피 `.env.production` 을 로드한다. 인라인 env 는 BE 도메인이 바뀌었을 때 추적이 어려운 hidden override 였음. 단일 출처 (`.env.production`) 로 통일해야 다음 BE 이전 시 재발 안 함.
- **사용자 후속:** `pnpm -C fe device:ios` (또는 `build:mobile && cap sync ios`) 재빌드 → Xcode 에서 Archive → TestFlight 업로드.

---

## 2026-05-14 | FE 로컬 env 파일 — `.env.local` → `.env.development.local` (v1.1.6 hotfix)

- **사건:** v1.1.4 배포 후 SNS 로그인이 운영 환경에서 `http://127.0.0.1:64321` 을 호출하며 실패. 정적 export 산출물(`fe/out/_next/static/chunks/*.js`)에 로컬 Supabase URL 이 박혀 있었음 (grep 으로 운영 URL `phynizbvzzsvprawxkvd.supabase.co` 부재 확인).
- **원인:** `feature/local-supabase-dev` 에서 `fe/.env.local` 을 로컬 Supabase 로 변경. Next.js 의 env 우선순위는 **test 모드를 제외하면 `.env.local` 이 `.env.production` 보다 우선**(공식 문서)이라 `next build` 시 로컬 URL 이 그대로 번들 + Capacitor iOS/Android assets 에 박힘.
- **결정:** FE 로컬 개발 env 파일을 `.env.development.local` 로 사용. `.env.development.local` 은 Next.js 가 dev 모드에서만 로드하므로 production build 가 격리됨. `.env.local` 은 사용 금지.
- **이유:** Next.js 공식 컨벤션. 빌드 환경별 분리가 파일명 자체로 명시되어 사고 재발 가능성 차단. BE 는 별개(컨테이너 런타임 주입) 이므로 이번 변경 범위 밖.
- **사용자 후속:** 운영 재배포 — `pnpm -C fe build && npx cap sync` 로 모바일 번들 포함 재빌드.

---

## 2026-05-14 | 앱 번들ID — `com.investnote.app` → `app.pixelwave.investnote`

- **결정:** Capacitor `appId`, iOS `PRODUCT_BUNDLE_IDENTIFIER`, Android `applicationId/namespace`, OAuth 딥링크 스킴(`NATIVE_URL_SCHEME`, `AndroidManifest`, `Info.plist`, `strings.xml`) 모두 `app.pixelwave.investnote`로 통일. Android `MainActivity.java` 패키지 경로도 `app/pixelwave/investnote/`로 이동.
- **이유:** 기존 `com.investnote.app`은 미보유 도메인 기반 역도메인. 보유 도메인(`pixelwave.app`) 기반으로 통일해 스토어 등록 전 충돌·소유권 분쟁 가능성을 제거.
- **후속 작업(사용자):** Supabase 대시보드 Authentication → URL Configuration → Redirect URLs에 `app.pixelwave.investnote://auth/callback` 추가. 스토어 등록 전 상태이므로 기존 ID 마이그레이션 이슈는 없음.

---

## 2026-05-14 | 로컬 개발 — Supabase CLI 로컬 스택 + ES256 비대칭 서명

- **맥락:** BE/FE 의 `.env.local` 이 클라우드 Supabase (`phynizbvzzsvprawxkvd.supabase.co`) 를 가리켜 로컬 개발이 운영 DB·Auth 와 직접 연결됨. 마이그레이션 검증을 운영에서 수행해야 하는 위험 + 테스트 데이터가 운영과 섞이는 문제.
- **결정:** 개발(로컬)에서 `supabase start` 로 띄우는 로컬 스택을 사용. 다른 Supabase 프로젝트 (`today`) 가 기본 포트를 점유 중이라 invest-note 는 64321 대역으로 변경 (API 64321 / DB 64322 / Studio 64323 / Inbucket 64324 / Analytics 64327 / Pooler 64329 / shadow 64320). JWT 는 ES256 비대칭 서명 활성화 — `supabase gen signing-key --algorithm ES256` 로 생성한 `supabase/signing_keys.json` (gitignore) + `config.toml` 의 `signing_keys_path` 등록. BE `auth/jwt.py` 무수정으로 운영과 동일한 JWKS 검증 경로.
- **이유:** ① 클라우드 의존 제거로 오프라인/속도/안전성 확보. ② 마이그레이션은 `supabase db reset` 으로 로컬 검증 후 클라우드에 반영. ③ 운영도 비대칭 (`sb_publishable_*`/`sb_secret_*`) 사용 중이라 로컬 ES256 채택 시 인증 검증 경로가 환경 간 동일.
- **트레이드오프:** ① 다른 Supabase 프로젝트와 동시 실행 시 포트 변경 필요 (이미 적용). ② 로컬 Auth 사용자는 비어있어 회원가입 다시 (의도된 격리). ③ 클라우드 일시 전환 필요 시 `cp be/.env.production be/.env.local && cp fe/.env.production fe/.env.local`. ④ `signing_keys.json` 분실 시 재생성하면 기존 발급 토큰 모두 무효 (로컬 한정 영향).
- **운영 절차:**
  - 시작: `supabase start` (루트 또는 `supabase/` 안에서)
  - 중지: `supabase stop`
  - 마이그레이션 재적용: `supabase db reset`
  - 키/URL 확인: `supabase status` (Studio: http://127.0.0.1:64323, Inbucket: http://127.0.0.1:64324)
- **OAuth 보강 (2026-05-14):** 클라우드는 Dashboard 에서 Google/Kakao 를 활성화했지만 로컬은 `config.toml` 로 별도 선언이 필요. `[auth.external.google]`, `[auth.external.kakao]` 섹션 추가, `client_id`/`secret` 은 `env(...)` 로 `supabase/.env` 참조, `redirect_uri = "http://127.0.0.1:64321/auth/v1/callback"` 명시 (생략 시 GoTrue 가 "missing redirect URI" 반환). 사용자는 `supabase/.env` 에 실제 OAuth credentials 입력 + Google Cloud Console / Kakao Developers 의 redirect URI 화이트리스트에 동일 callback URL 추가 + `supabase stop && supabase start` 로 반영.

---

## 2026-05-03 | FE simplify Round 6 — AccountFilter / StockSearchInput

- **백로그:** "FE simplify · 타입/구조" 2 항목.
- **결정:**
  - `AccountFilter`: `selectedAccountId: string` + `ACCOUNT_FILTER_ALL = "all"` → `string | null` (`null` = 전체). 상수 제거, 5 파일 수정 (`AccountFilterProvider` / `AccountFilter` / `TradeList` / `StockDetail` / `DetailPanelProvider`).
  - `StockSearchInput prevQuery`: 렌더 중 prev state 비교 패턴 (`StockSearchInput.tsx:51-57`) 그대로 유지.
- **이유:**
  - sentinel: API 계층은 sentinel 미사용(클라 메모리 필터링) → BE 영향 0. `useEffectiveAccountId` 가 정규화 캡슐화. `string | null` 이 마법문자열보다 type-safe.
  - prevQuery: React 공식 ["Adjusting some state when a prop changes"](https://react.dev/learn/you-might-not-need-an-effect#adjusting-some-state-when-a-prop-changes) 권장 패턴. 렌더 중 `setState` 비교는 React 가 commit 전 즉시 재렌더로 동기화 → stale `activeIndex` commit 방지. `useEffect` 대안은 commit→effect→setState→재렌더 4 단계 사이클로 한 프레임 stale 노출 (회귀). 기존 코드 주석의 "참조 비교 무한루프" 표현은 부정확 (`debouncedValue` 는 string primitive) — 본 결정문이 사이클 효율성 / stale frame 회피 프레이밍으로 정정.
- **재평가 트리거:** sentinel 종류가 3+ 가지로 늘면 discriminated union 재평가. React 19+ `use` 훅 / transition 채택 시 prevQuery 재평가.

---

## 2026-05-03 | FE simplify Round 5 — refetchOnWindowFocus 글로벌 default 유지

- **백로그:** "FE simplify · 성능" 의 `refetchOnWindowFocus false 검토`.
- **결정:** 글로벌 default (`true`) 유지. per-query staleTime 만 명시 (`useAnalysisData` 5min / `usePortfolioSummary` 2min / `TradeBasicForm` holding 10s). backlog 메모는 본 결정으로 종결.
- **이유:**
  - 글로벌 변경 blast radius — 모든 useQuery (accounts/trades/portfolio/analysis 등) 영향. 모바일 Capacitor resume / tab visibility 회귀 위험.
  - focus refetch 가 살아 있으면 staleTime 5 분도 다른 앱에서 돌아오면 자동 refetch — stale 노출 시간 사실상 짧음. 탭 안 머무는 동안은 명시적 invalidate 가 보장 (`queryKeys.portfolio` 5 곳, `queryKeys.trades` invalidate 등).
  - "분석 5 분 stale 허용" 같은 도메인 시맨틱은 query 옆 `staleTime` 으로 표현해야 의도 보존.
- **재평가 트리거:** 모바일 백그라운드→포그라운드 복귀 시 동시 refetch 부하가 실측 확인되면 mobile 전용 false 분기 / lightweight summary 쿼리 대체 / `focusManager` 커스터마이즈 검토.

---

## 2026-05-03 | BE simplify Round 5 — `external/quotes._parse_*` 통합 미진행

- **백로그:** "BE simplify · 재사용 / 잔여" 마지막 항목 (`_parse_realtime_price` / `_parse_basic_price` 통합).
- **결정:** 진행 안 함. backlog 에서 제거.
- **이유:** Naver realtime/basic endpoint 응답 구조 비대칭 — realtime 은 `data["datas"][0]` unwrap 후 `closePriceRaw` / shim `now` / `closePrice` fallback, basic 은 unwrap 없이 `closePriceRaw` / `stockEndPrice` / `closePrice` fallback. realtime 의 `datas[0]` 래핑·`now` 필드는 basic 응답에 없고, basic 의 `stockEndPrice` 는 realtime 응답에 없음. 단일 함수화 시 `is_realtime: bool` 분기 파라미터 필요 → LOC 절감 0. 공통 추출 가치도 `float(raw) if raw else 0.0` 1 줄 + 최상위 `closePriceRaw` fallback 정도라 가독성 오히려 손해.
- **재평가 트리거:** Naver 가 두 endpoint 응답 형식 통일, 또는 시세 provider 가 3+ 개로 증가 (`Strategy` 패턴 도입 가치 발생).

---

## 2026-05-03 | BE simplify Round 3 — analysis period SQL push 미진행

- **백로그:** "BE simplify · 효율 / 핫패스" 5 번째 (`routers/analysis` period 파라미터 SQL push).
- **결정:** 진행 안 함. backlog 에서 제거.
- **이유:**
  - `routers/analysis.py:89, 98, 101` 가 `build_positions(all_trades)` / `compute_concentration(positions, all_trades)` / `build_strategy_evaluations(all_trades, holding_days_map)` 에 의도적으로 unfiltered `all_trades` 전달 — line 100 인라인 주석이 비대칭 의도 명시 (compute_profile 누적 일관성 평가용). period filter 는 `pnl_map` / `holding_days_map` / `summary` 에서만 사용.
  - SQL push = 1 round-trip → 2 round-trip — `all_trades` 어차피 필요하므로 period ≠ 'all' 시 별도 fetch 필수. 개인 투자자 데이터 (수십~수백 거래) 에서 round-trip (~10ms) > 메모리 필터 (<1ms). **net negative.**
  - 분기 workaround (`period == "all"` 만 1 회 fetch) 도 marginal benefit 대비 복잡도 증가로 거부.
- **재평가 트리거:** 거래 데이터 천 단위 이상 증가 (페이지네이션 도입 시 자연 감소), 또는 `all_trades` invariant 변경 (예: `compute_profile` 도 period-filtered 결정). `domain/analysis/period.py:filter_by_period` 유지.

---

## 2026-05-03 | FE simplify Round 3 — HoldingCard pressing state (data attribute 채택)

- **맥락:** Round 1 에서 `pressing` `useState` + 4 개 pointer 핸들러를 CSS `:active:scale-[0.98]` 로 단순화 시도했으나, inner note 영역의 `onPointerDown` `stopPropagation()` 이 outer `:active` 를 차단하지 못해 원본 UX (멀티라인 note 탭 시 outer 카드 scale 미발동) 가 깨져 복원 (커밋 `9e494ce`). 사용자 확인 결과 원본 UX 는 의도된 동작.
- **결정:** `useState`/4 핸들러는 유지하되, className 조건부 (`pressing && "scale-[0.98]"`) 만 `data-pressing={pressing ? "true" : undefined}` + Tailwind v4 `data-[pressing=true]:scale-[0.98]` variant 로 교체. nested clickable 없는 카드 (TradeCard 등) 는 CSS `:active` 그대로 유지 (본 결정은 HoldingCard 한정).
- **이유:** CSS `:active` 는 React synthetic event 의 stopPropagation 을 우회 발동 → 의도된 UX 보존 불가. native `<button>` 변환은 nested clickable 충돌 (HTML spec). data attribute 방식은 JS 가 상태만 표현하고 시각 변화는 CSS 가 선언적으로 책임 → 추후 시각 변화 추가 시 className 분기 미증가.
- **트레이드오프 / 재평가:** LOC 중립 (Round 1 단순화 동기였던 "JS state 제거" 미달성). nested clickable note 가 제거되면 CSS `:active` 로 전환 가치, nested stop layer 패턴이 다른 카드에서도 필요하면 별도 stop layer wrapper 재평가.

---

## 2026-05-03 | FE simplify — Card primitive 추출 미진행

- **백로그:** "FE simplify · 컴포넌트 추출" 의 `Card` primitive 30+ 곳 (`rounded-2xl bg-muted/60`).
- **결정:** `<Card>` 컴포넌트도 CSS 유틸 (`.card-shell`) 도 도입 안 함. 인라인 클래스 그대로 유지. 백로그 항목 종결.
- **이유:** 사용처 32 곳 / 18 파일이지만 ① 셸 마크업이 단 2 개 유틸 클래스 — `<Card className="...">` 가 인라인 대비 토큰 절감 가치 미미. ② padding 변종 7 가지 (`p-3.5×6`, `p-4×10`, `p-5×2`, `p-8×1`, `px-4 py-1×1`, `px-4 py-3×1`, 스켈레톤 padding 없음 ×5) + interaction (`active:scale-[0.99]`, `cursor-pointer`) / overflow / div·button 혼합으로 다양 — prop API 흡수 시 escape-hatch `className` 만연 (추상화 → passthrough 전락). ③ Round 2~7 추출은 시맨틱 콘텐츠 (EmptyCard 의 title/description, BreakdownList 의 items 등) 가 prop API 를 자연스럽게 만들었으나 순수 시각 셸은 동일 패턴 부적용.
- **재평가 트리거:** ① 셸 클래스 변경 PR 6 개월 내 2 회 이상, ② 인터랙티브 카드 5 곳 이상으로 증가, ③ 시맨틱 props (`as`, `interactive`) 가 절반 이상 사용처에서 요구.

---

## 2026-05-03 | BE simplify Round 2 — TradeWithAccountResponse 스키마화 미진행

- **백로그:** Round 2 "응답 매핑" 5 번째 (`_trade_with_account_dict` 의 `pop` 기반 dict reshape → `TradeWithAccountResponse` + `response_model`).
- **결정:** 진행 안 함. backlog 에서 제거.
- **이유:**
  - LOC 중립~증가 — 7 줄 helper 제거하려면 `TradeWithAccountResponse` + nested `AccountInfo` + `model_validator` 변환 ~30 줄 필요.
  - FE 계약 보존 비용 — FE Trade interface (`fe/src/types/database.ts:27`) 가 snake_case (`account_name`, `ticker_symbol`, `country_code`, `created_at` 등) 사용. `_trade_with_account_dict` 가 통과하는 `model_dump(mode="json")` 은 snake_case. `CamelModel` (`schemas/_base.py`) 적용 시 wire format 이 camelCase 로 바뀌어 FE 가 깨짐. snake_case 보존하려면 `BaseModel` 직접 상속 → `CamelModel` 일원화 컨벤션과 충돌.
  - OpenAPI 정확도 가치 < 비용 — internal-only API.
- **재평가 트리거:** trades 응답 wire format 을 camelCase 일원화 결정 (FE 동시 마이그레이션) 시. 본 결정은 2026-04-30 Tier 3 / 본 라운드의 다른 미진행 결정과 동일한 "다르게 보이지만 단순화 비용이 더 큰 사례" 패턴.

---

## 2026-04-30 | BE simplify Tier 3 — aggregate.py 3-bucket loop / build_strategy_evaluations 호출 통합 미진행

- **백로그:** Tier 3 항목 E (`aggregate.py` 3 버킷 루프 → `_bucketize` 헬퍼) / F (`build_strategy_evaluations` 의 router (`all_trades`) / `compute_summary` 내부 (period-filtered) 두 호출 통합).
- **결정:** 두 항목 모두 통합 안 함. 두 호출 지점에 의도 차이 docstring 추가 (F1) 까지만 진행.
- **이유:**
  - E: 3 버킷이 도메인 의미 (계획된 전략 / 전략 준수도 / 감정) 다름. `strat_map` 만 보유일 (`days`) 추적, key 추출 fallback 정책 비대칭 (evaluation fallback / `ADHERENCE_UNKNOWN` / `EMOTION_UNTAGGED`). 단일 헬퍼화 시 옵션 매개변수 (보유일 추적 여부, key fallback 정책) 확산 → 가독성 손해.
  - F: router 호출은 `compute_profile` 장기 일관성 평가용 (전체 거래), `compute_summary` 내부 호출은 기간별 `strat_map` / `adherence_map` 스냅샷용 (period-filtered). 어느 입력으로 통일해도 시맨틱 손실.
- **재평가 트리거:** 표면적 유사성으로 재제기되더라도 본 결정 + docstring 으로 차단. 두 항목 모두 "다르게 보이지만 사실 다른 것" 패턴.

---

## 2026-04-30 | trade group 매칭 — `ticker_symbol` 항상 존재 invariant 명시 의존

- **맥락:** `domain/holdings.py` 의 `_is_flexible_match` 와 `domain/realized_pnl.py` 의 `_is_same_group` 이 같은 의도 (같은 종목·계좌·국가 trade 그룹화) 였으나 매칭 정책이 미묘하게 달랐음. 전자는 `trade_id == target_ticker OR trade.asset_name == target_asset` (OR 너그러움), 후자는 `trade_id == (key.ticker or key.asset_name)` (단일 비교, strict). `routers/portfolio.py` 의 `/holding` SQL 도 `ticker_symbol = $4 OR asset_name = $5` 분기 보유. 두 정책의 결과 차이는 `Trade.ticker_symbol` 이 빈 문자열인 경우에만 발생.
- **결정:** `Trade.ticker_symbol` 은 항상 채워진다는 invariant 를 명시적으로 신뢰. 이 가정 하에 `_is_flexible_match` 의 OR 분기와 `/holding` SQL 의 `OR asset_name = $5` 분기를 dead branch 로 간주해 모두 제거. `LotKey` 폐기, `TradeGroupKey` 단일 키 + `is_same_group` 단일 매칭 함수로 통합. 후속으로 `routers/trades.py` 의 `GET /api/trades?ticker=...` 메모리 필터도 `t.ticker_symbol == ticker` strict 비교로 정리.
- **이유:** 두 함수의 정책 차이를 유지하면 "왜 다른가" 추적 비용이 영구화. invariant 가 깨진 데이터가 실재하지 않는 한 strict 통일해도 동작 회귀 없음. 백엔드 도메인 코드와 SQL 양쪽에서 invariant 위배 시 동일하게 매칭 실패하므로 정합성 일관됨.
- **트레이드오프:** invariant 가 깨진 레거시 row 가 DB 에 존재한다면 holding 이 0 으로 잘못 계산. 향후 데이터 임포트 경로 (broker_import 등) 에서 `ticker_symbol` 빈 문자열 진입 차단 검증 강화 필요. 검증 쿼리: `SELECT count(*) FROM trades WHERE ticker_symbol = '' OR ticker_symbol IS NULL`.

---

## 2026-04-28 | 일괄 등록 종목명 매칭을 Naver API 단일화 + stocks 마스터 제거

- **맥락:** 거래명세서 일괄 등록의 종목명→ticker 매칭이 `stocks` 마스터 exact match 에 묶여 ① 약칭 미일치 ("현대차" vs "현대자동차"), ② 마스터 누락 (KIND 시드는 일반 상장사만 — ETF/ETN/우선주/리츠 제외, "TIGER 미국S&P500" 등 미존재), ③ 변형/공백/대소문자 차이 일체 미허용으로 실패. 보강 시도 (KRX OTP / pykrx / FinanceDataReader / KIS) 모두 약칭 매핑 미제공. 한편 `routers/stocks.py` 의 `/api/stocks/search` 는 이미 Naver 자동완성 API 를 사용 중이며 약칭/부분일치/ETF 자연스럽게 처리.
- **결정:** ① 일괄 등록 ticker 매칭을 `ticker_hints → Naver 검색 API → None` 단일 경로로 단순화. `external/naver_search.py` 로 `_search_kr` 추출 + `find_first_kr_match(q)` helper 추가 (우선순위: 정확일치 > 자동완성 1 순위, 가드: 입력 길이 ≥ 2). `broker_import/ticker_resolver.py` 에서 stocks_repo 의존 제거, 미해결 이름들은 `asyncio.gather` 로 병렬 조회. ② `public.stocks` 테이블, `db_ops/stocks_repo.py`, `scripts/seed_stocks.py` 모두 제거 (마이그레이션 016_drop_stocks.sql 추가). 014/015 는 역사 보존. ③ `routers/trades.py:420` 미해결 사유 메시지와 `PreviewStep.tsx` 안내 문구 갱신.
- **이유:** 마스터 자체 시드 유지 비용 (KIND 의존, ETF 별도 소스 필요, 약칭은 어떤 공식 소스도 미제공) 이 매칭 품질 대비 과도. Naver 자동완성 API 는 검색 자동완성에서 이미 도입된 의존성이라 추가 외부 위험 없이 약칭/ETF/변형 표기를 일거 해결. trades 테이블이 stocks 를 FK 로 참조하지 않아 (`001_initial_schema.sql:30`) 거래 데이터 무영향, 시세 조회/검색은 외부 API 라 마스터와 무관.
- **트레이드오프:** Naver API 단일 의존 (다운/응답 변경 시 일괄 등록 전체 영향) — 5 초 timeout + try/except 로 hang 방지, 검색 라우터와 동일 의존이라 추가 위험 없음. 부분 일치 오매칭 가능 ("삼성" → "삼성전자") — 입력 길이 ≥ 2 가드 + 정확일치 우선 정책으로 1 차 완화, 보수적 운영 후 필요 시 사용자 수동 매칭 UI 도입. 미매칭 N 건당 N 회 외부 호출 — `asyncio.gather` 병렬화로 완화. 마스터 재도입은 향후 ETF/약칭 데이터 소스 확보 시 재검토 (`docs/backlog.md` 기록).

---

## 2026-04-28 | 분석 임계값 단일 SOT (BE thresholds.py 통합 + FE constants/analysis.ts 동기화)

- **맥락:** 임계값 (`SCALPING_MAX_DAYS=1`, `SWING_MAX_DAYS=30`, `HHI_HIGH=0.5`, `HHI_MID=0.25`, `TOP1_WEIGHT_HIGH=0.4`) 이 BE 내부에서도 분산 (`strategy_adherence.py` 매직 넘버 / `concentration.py` 모듈 상수) 되고 FE/BE 양쪽 이중화. `rules.py` 9 개 규칙 함수에 도메인 판정 임계값 (`feeling_rate < 40`, `reflection_rate >= 30`, `win_rate < 30`, `missing_tag_rate < 30`, `result_input_rate >= 50`, `avg_holding_days <= 7`) 과 최소 샘플 가드 (`count < 5/3`, `total_trades < 5`, `sell_trades < 3/5`) 가 매직 넘버로 박혀 있어 SOT 외부에서 침묵 변경 가능. FE `SummaryCards.tsx` 가 `60`/`40` 하드코드해 BE `WIN_THRESHOLD` 60→65 변경 미추종. FE `aggregate.ts:computeSummary` / `rules.ts:evaluateRules` / `strategy-adherence.ts` 함수들은 production 미호출 (테스트만) 상태로 임계값 import 의존성 생성.
- **결정:**
  1. BE `domain/analysis/thresholds.py` 단일 모듈로 추출. `strategy_adherence.py` (전략 임계값) / `rules.py` (HHI 임계값) / `concentration.py` 가 모두 import. `concentration.py` 자체 상수 정의 제거.
  2. `rules.py` 의 모든 비교 매직 넘버를 `thresholds.py` 상수로 흡수 — 도메인 판정 6 개 (`FEELING_RATE_HIGH`, `REFLECTION_RATE_LOW`, `LOSING_STRATEGY_RATE`, `MISSING_TAG_RATE_HIGH`, `RESULT_INPUT_RATE_LOW`, `SCALPING_HOLDING_LIMIT_DAYS`) + 최소 샘플 가드 8 개 (`MIN_EMOTION_TRADES/RESULTS`, `MIN_TOTAL_TRADES`, `MIN_SELL_TRADES`, `MIN_HIGH_WINRATE_SELL`, `MIN_SCALPING_TRADES`, `MIN_STRATEGY_TRADES/RESULTS`). 명명은 "어디서 쓰이는가" 가 아닌 "무엇을 의미하는가" 기준 (같은 5 라도 의미 다르면 별도 상수).
  3. FE `SummaryCards.tsx` 가 `WIN_THRESHOLD`/`LOSS_THRESHOLD` import — 하드코드 제거.
  4. FE dead 분석 로직 삭제 — `aggregate.ts:computeSummary`, `rules.ts:evaluateRules`, `strategy-adherence.ts:inferActualStrategy/evaluateStrategyAdherence`, `AnalysisDashboard.tsx` fallback 호출, 관련 테스트 (BE `tests/test_analysis_logic.py` 가 동일 검증 담당). 응답 타입 정의 (`AnalysisSummary`, `Suggestion`, `StrategyEvaluation`) 만 보존.
  5. FE 정적 export 구조상 BE 직접 참조 불가 — `fe/src/lib/constants/analysis.ts` 위치 유지. **임계값 변경 시 BE/FE 두 파일을 함께 수정한다.**
- **이유:** "임계값은 한 곳에서 변경" 정신을 깨고 있던 분산을 모두 흡수. BE 는 `thresholds.py` 만 보면 모든 도메인 임계값 파악. FE 자체 평가 로직은 BE 응답이 모든 판정 결과를 담고 있어 dead code, 임계값 동기화 책임 분산만 유발.
- **트레이드오프:** ① BE suggestions 응답 빈 배열/실패 시 인사이트 섹션 공란 (fallback 사라진 비용) — `useAnalysisData` 별도 에러 핸들링 경로 담당. ② BE/FE 동기화는 여전히 수동 — PR review 시 양쪽 diff 확인 필요. 자동 sync (JSON export → FE 빌드 import) 는 정적 export 구조 + 별도 빌드 단계 비용으로 미적용. ③ `analysis.py:_HOLDING_BUCKETS` / `_size_bucket` 은 표시용 버킷팅이라 SOT 흡수 제외. UI 색상/라벨용 임계값 (`WinRateBar`, `DiversificationPanel`) 은 FE constants 그대로 — BE→rating 필드 응답화는 비용 대비 가치 낮아 미적용.

---

## 2026-04-28 | SELL 거래 reasoning_tags · emotion 자동 산출 정책

- **맥락:** 분석 탭의 byTag/byEmotion 이 SELL 시점에 직전 BUY 를 매번 FIFO 매칭해 태그/감정 귀속 — 프론트엔드 키에서 `account_id` 누락으로 다계좌 사용자에게 잘못된 귀속 가능. EmotionStats 는 BUY+SELL 합산 `count` 와 SELL 한정 `sellCount` 를 분리해 UI 표기 혼동 유발.
- **결정:** `strategy_type` 패턴 (`compute_group_pnl` → `recalc_group_pnl` → SELL row UPDATE) 을 그대로 `reasoning_tags`/`emotion` 에 확장. 두 필드를 SELL row 에 저장, 분석 라우터/aggregate 는 SELL 저장값만 카운트. 통합 정책은 FIFO 소비 BUY lot 중 **가장 최근 (`traded_at` 최대, 동률 시 BUY order 최대) lot 의 값**을 그대로 복사 (`_meta_from_consumed_latest`). SELL UI 는 두 필드를 read-only chip 으로 표시, PATCH 입력은 라우터 `strip_sell_auto_derived` 헬퍼에서 명시적으로 제거. 기존 데이터는 011 패턴의 PL/SQL FIFO 마이그레이션 (013) 으로 백필.
- **이유:** byTag FIFO 매칭의 hot-path 비용을 mutation 시점으로 이동. frontend 키 누락과 EmotionStats 의미 혼동을 동시 해소. `strategy_type` 과 동일 패턴이라 향후 SELL 자동 산출 필드 (예: `result`) 추가 용이. `strategy_type` (수량 가중 최다) 과 `reasoning_tags`/`emotion` (가장 최근 BUY) 의 두 정책 공존은 전자가 SELL 의 "주된 전략", 후자는 "직전 진입의 근거/감정" 으로 의미가 다르기 때문.
- **트레이드오프:** `PNL_AFFECTING_FIELDS` 에 두 필드 추가로 BUY 메타 단독 변경에서도 그룹 advisory lock + recalc 발동 — DB write 부하 약간 증가, 정합성과 교환. 사용자가 SELL 에 직접 입력했던 기존 emotion/reasoning_tags 값은 마이그레이션 시 무조건 덮어써짐 (의도된 결정). 자동 산출 정책 책임은 `SELL_AUTO_DERIVED_FIELDS` 상수와 `strip_sell_auto_derived` 헬퍼로 단일 등록 지점화.

---

## 2026-04-28 | 라이트 모드 전용 — 다크 모드 제거

- **결정:** 테마 토글 UI (`AppearanceSection`), `next-themes` 의존성, `ThemeProvider` 래퍼, `globals.css` 의 `.dark { ... }` CSS 변수 블록 및 `@custom-variant dark` 선언, 11 개 컴포넌트의 `dark:` Tailwind 프리픽스 26 곳 모두 제거. `ThemedToaster` → `AppToaster` 리네임, sonner 기본값 (light) 활용해 prop 단순화.
- **이유:** 디자인 토큰을 `:root` 단일 소스로 관리. 컴포넌트마다 dark variant 색을 별도 결정·QA할 필요 없음. `next-themes` 제거로 번들/hydration 비용 소폭 감소. `<html suppressHydrationWarning>` 회피 코드 제거.
- **트레이드오프:** 다크 모드 재도입 시 `dark:` 프리픽스 재추가 + `.dark` CSS 변수 블록 복원 필요. 기존 사용자의 `localStorage["theme"]` 은 next-themes 가 사라져 무시 (별도 마이그레이션 코드 미배치). shadcn 컴포넌트 동기화 시 원본 `dark:` 클래스와 diff 발생 가능하나 본 프로젝트는 `src/components/base/` 래퍼 경유라 영향 제한적.

---

## 2026-04-27 | MVP 해외 주식 제외 — 신규 진입 차단, 기존 데이터 호환 유지

- **맥락:** MVP 는 국내 주식 매매 기록·분석에 집중. 기존 코드의 US/Yahoo 검색·시세와 USD 합산 전제는 환율 미적용 총자산·분석 왜곡 발생 가능.
- **결정:** MVP 에서는 신규 해외 주식 검색/시세 조회/신규 매수 등록 차단. `country_code` 타입과 기존 US/OTHER 데이터 렌더링은 유지 — 과거 데이터 조회와 보유분 매도 흐름 보존.
- **트레이드오프:** 기존 해외 보유분은 v2 전까지 신규 시세 `null` 일 수 있음. v2 재도입 시 Yahoo 등 provider, USD/KRW 환율, 크로스 통화 분석 정합성 함께 설계.

---

## 2026-04-26 | 미래 거래 등록 차단 — 입력 경계에서 거절, 분석 필터 상한 유지

- **맥락:** 분석 기간 필터는 "all" 에서도 `now` 이후 거래를 제외 — 사용자가 미래 거래를 등록하면 기록에는 보이지만 분석에는 빠지는 혼란 발생 가능.
- **결정:** 신규 거래 등록에서 미래 `traded_at` 차단. 프론트는 캘린더와 zod 검증으로 사전 차단, FastAPI `TradeCreate` 스키마는 문자열/`datetime` 입력을 UTC 정규화한 뒤 서버 현재 시각보다 미래면 400 거절. 분석 필터의 `now` 상한은 기존/외부 유입 데이터 방어용으로 유지.
- **트레이드오프:** 미래 예약/계획 거래는 MVP 미지원. 향후 CSV 임포트나 계획 거래 기능 추가 시 별도 데이터 타입 또는 명시적 import 정책 필요.

---

## 2026-04-25 | asyncpg UUID→str 타입 경계 — 라우터 입력 경계에서 변환

- **맥락:** asyncpg 는 PostgreSQL UUID 컬럼을 `uuid.UUID` 객체로 반환. Pydantic 모델 (`Trade`) 은 `_uuid_to_str` validator 로 자동 str 변환되지만, 일반 dataclass (`Account`) 는 type hint 강제 부재로 `account.id` 가 UUID 객체로 남음. `build_account_snapshots` 에서 `by_account.get(account.id)` 가 str 키와 타입 불일치 → 항상 빈 배열 → `stock_evaluation = 0`.
- **결정:** 라우터 입력 경계 `_account_from_row` 에서 UUID 필드를 str 변환. 도메인 함수 `build_account_snapshots` 에도 `str(account.id)` 방어 처리 유지.
- **이유:** 타입 강제 없는 dataclass 는 입력 경계에서 정규화해야 런타임 타입 불일치 차단. 도메인의 `str()` 호출은 라우터 외 경로 (테스트, 직접 호출) 에서 UUID 가 들어올 경우의 안전망.
- **트레이드오프:** asyncpg 를 사용하는 다른 dataclass 변환 함수에도 동일 패턴 적용 필요. Pydantic 전환 시 validator 로 중앙화 가능하나 현재는 도메인 모델을 경량 dataclass 로 유지.

---

## 2026-04-25 | advisory lock timeout — SET LOCAL 2s + 전역 handler

- **맥락:** `feature/toctou-advisory-lock` 에서 `pg_advisory_xact_lock` 도입 시 lock_timeout 미설정으로, 운영에서 동일 그룹 동시 mutation 이 몰리면 뒤 요청이 무한 대기하며 워커 점유 위험.
- **결정:** `acquire_trade_group_lock` 내부에 advisory lock 직전 `SET LOCAL lock_timeout = '2s'`. `LockNotAvailableError` (sqlstate 55P03) 발생 시 `main.py` 전역 exception handler 에서 `409 Conflict` + 한국어 안내 메시지 변환.
- **이유:** `SET LOCAL` 은 트랜잭션 종료 시 자동 reset. 2s 는 운영 hang 방어용 보수적 값 (일반 INSERT/UPDATE 는 훨씬 빠름). 전역 handler 선택으로 `db_ops` 가 `errors.APIError` 를 import 하지 않아 의존 방향 유지.
- **트레이드오프:** 같은 트랜잭션 내 INSERT/UPDATE row-lock 대기에도 2s 상한 적용 (현 코드베이스에서 무해). 2s 는 휴리스틱 — 운영 모니터링 후 조정 필요. 클라이언트 재시도 정책은 별도 처리.

---

## 2026-04-24 | TOCTOU race — pg_advisory_xact_lock 선택

- **맥락:** trades 라우터의 `list_trades → validate → write` 흐름에서 동시 SELL 요청이 같은 보유량 스냅샷을 읽고 둘 다 validate 통과해 음수 보유량 발생 가능. `FOR UPDATE` 를 걸 행이 없고 (보유량은 trades 집계로 유도), `SERIALIZABLE` 격리는 retry loop 가 필요해 라우터 구조 변경 비용이 큼.
- **결정:** transaction-scoped advisory lock (`pg_advisory_xact_lock`) 사용. 키는 `TradeGroupKey(ticker, asset_name, country, account_id)` + `user_id` 를 `hashtextextended` 로 bigint 해시. create/update/delete 세 mutation 경로에 `list_trades` 이전 삽입.
- **이유:** xact 변종은 트랜잭션 종료 시 자동 해제 → Supavisor transaction mode pooler 에서 session-level 변종 (`pg_advisory_lock`) 대비 leak 없음. 마이그레이션 불필요 (Postgres 11+ 내장). 기존 `TradeGroupKey` 도메인 타입 재사용으로 그룹 경계 일관성 유지.
- **트레이드오프:** 해시 충돌 시 불필요한 직렬화 발생 (정합성 영향 없음, 64-bit 충돌 확률 무시 가능). lock_timeout 후속 필요 → 2026-04-25 결정으로 보완.

---

## 2026-04-24 | FE constants — 레이어 분리 + 중앙화 (BE co-location 미적용)

- **결정:** FE 상수는 BE 처럼 도메인 폴더 내 co-location 이 아닌 `fe/src/lib/constants/` 중앙 폴더로 관리. 단일 파일에서만 쓰이는 UI 로컬 상수 (색상, 애니메이션 ms, 탭 정의 등) 는 컴포넌트 파일 내 유지.
- **이유:** FE UI 는 여러 도메인 데이터를 혼합해서 보여주는 것이 본업이라 도메인 경계가 BE 처럼 강하지 않음. co-location 하면 어디에 둘지 애매한 상수 발생. 현재 구조 (레이어 분리 + 도메인 서브폴더) 가 FE 특성에 맞는 절충안.
- **트레이드오프:** 상수가 늘어날수록 constants 파일 관리 필요. 여러 곳에서 쓰이는 상수만 선별 이관, 단일 파일 전용은 로컬 유지 원칙.

---

## 2026-04-24 | BE 상수 co-location — 모놀리식 constants.py 배제

- **결정:** API 백엔드 상수를 단일 `constants.py` 가 아닌 각 도메인 모듈에 인접 배치. `domain/trade_types.py` (enum 단일 소스), `domain/trade_utils.py` (KST·MS_PER_DAY), `external/constants.py` (URL·User-Agent·timeout), `auth/constants.py` (JWT·GUC 상수), `errors.py` (에러 메시지) 구조.
- **이유:** 모놀리식 파일은 응집도 없이 크기만 커져 수정 범위 파악 어려움. 도메인 경계 내 co-location 이 변경 이유가 같은 상수를 함께 관리.
- **트레이드오프:** `schemas/` → `domain/` 단방향 import 규칙 필수. 순환 import 발생 시 추적 어려울 수 있음.

---

## 2026-04-24 | 거래·종목 상세 패널 — 2-슬롯 + open/payload 분리 구조 (mode 제거)

- **결정:** `mode` 단일 상태 제거. `tradePayload`/`stockPayload` (콘텐츠) + `tradeOpen`/`stockOpen` (애니메이션) 분리. 동일 타입 재오픈 시 `key` 증가로 portal remount → z-order 재정렬.
- **이유:** `mode` SSOT 는 두 타입이 동시에 열릴 수 없어 Stock → Trade 이동 시 Stock 이 닫혀 뒤로가기가 1 단계. 2-슬롯 구조에서는 각 타입이 독립적으로 open/close 되어 최대 2 번 뒤로가기로 원래 페이지 복귀 가능.
- **트레이드오프:** `createPortal` 의 DOM 추가 순서가 z-order 를 결정하므로 동일 타입 재오픈 시 key remount 필수. `open=false` 후 `PANEL_ANIMATION_MS+50ms` 타이머로 payload null 처리해 슬라이드 아웃 중 콘텐츠 유지.

---

## 2026-04-23 | FastAPI CORS — Capacitor WebView origin 허용

- **결정:** `Settings.cors_origins` 기본값과 `.env.example` 에 `capacitor://localhost` (iOS), `https://localhost` (Android, 포트 없음) 추가. `allow_credentials=True`, 고정 리스트 유지.
- **이유:** Capacitor WKWebView 가 이 두 origin 으로 페이지를 서빙해 기존 웹 origin 만으로는 preflight 거부. 고정 2 개라 regex 불필요.
- **트레이드오프:** production `CORS_ORIGINS` 환경변수에도 반드시 반영 필요.

---

## 2026-04-23 | OAuth Deep Link — `com.investnote.app://auth/callback`

- **결정:** reverse-DNS 형식 고정. 짧은 형식 (`investnote://`) 배제.
- **이유:** Bundle ID 와 일치, App Store 유니크성으로 하이재킹 위험 최소.
- **후속:** Universal Links 전환은 도메인·심사 확정 후 재검토.

---

## 2026-04-23 | Supabase 클라이언트 — `@supabase/supabase-js` + PKCE + implicit fallback

- **결정:** `@supabase/ssr` → `@supabase/supabase-js` 의 `createClient`. `auth.flowType: 'pkce'` 명시. `CapacitorDeepLinkHandler` 가 `?code=` (PKCE) 와 `#access_token=` (implicit) 모두 수용.
- **이유:** `@supabase/ssr` 은 쿠키 기반 storage 인데 Capacitor iOS `capacitor://localhost` 에서 WebKit 이 쿠키를 저장하지 않아 PKCE verifier 분실. `supabase-js` 는 localStorage 기본이라 안정 persist. provider/버전 이슈로 implicit 응답 가능성 배제 불가라 fragment fallback 유지.
- **후속:** 서버측 세션 공유가 필요해지면 `@supabase/ssr` 재도입 검토 (현재 FastAPI Bearer 로 불필요).

---

## 2026-04-23 | OAuth Deep Link 리스너 — 루트 레이아웃 상주

- **결정:** `CapacitorDeepLinkHandler` 단일 컴포넌트로 분리해 루트 `layout.tsx` 내 상주 마운트. `@capacitor/app`·`@capacitor/browser` dynamic import.
- **이유:** Cold start 시 `App.getLaunchUrl()` 을 리스너 등록 전에 호출해야 이벤트 손실 방지. 루트 상주로 페이지 이탈/재진입 경쟁 상태 제거. dynamic import 로 웹 번들에 플러그인 chunk 미포함.

---

## 2026-04-23 | Capacitor 셋업 — 설치 `fe/`, appId `com.investnote.app`

- **결정:** Capacitor 8.x 를 `fe/` 워크스페이스 내부 설치. `webDir=out`. `ios/`, `android/` 네이티브 프로젝트 커밋.
- **이유:** Next.js export 결과물 경로 일치. 네이티브 커밋은 Capacitor 공식 권장 (재현성).
- **트레이드오프:** appId 는 스토어 등록 후 변경 불가. 레포 크기 수 MB 증가.

---

## 2026-04-22 | 정적 export + Next.js API Routes 제거 (Chunk D)

- **결정:** `output: 'export'` 정적 모드 전환. Server Component + Route Handler 전부 제거. FastAPI 가 모든 API 커버.
- **이유:** Capacitor 가 정적 번들을 WebView 에서 직접 로드 — SSR/쿠키 기반 서버 기능 사용 불가.
- **트레이드오프:** 동적 라우트 (`records/[id]`, `stocks/[country]/[ticker]`) 삭제 (패널 진입 대체, 딥링크 소실). 인증은 localStorage 기반. `NEXT_PUBLIC_API_BASE_URL` 미설정 시 모든 API 호출 실패.

---

## 2026-04-22 | 모노레포 — pnpm workspace (`fe/` + `be/`)

- **결정:** 루트 pnpm workspace 로 `fe/` (Next.js) 과 `be/` (FastAPI) 분리. 루트 `package.json` 은 위임 스크립트만.
- **이유:** 단일 레포에서 코드·히스토리·이슈 공동 관리가 1 인 팀에 적합. `fe/` 는 독립 레포 분리 여지 확보.
- **트레이드오프:** Vercel 배포 시 Root Directory 를 `fe` 로 수동 설정. `scripts/backfill-pnl.ts` 는 `fe/` 에서 실행.

---

## 2026-04-22 | FastAPI 인증 — Supabase JWKS (ES256)

- **결정:** `PyJWKClient` 로 `/auth/v1/.well-known/jwks.json` 공개키 조회해 ES256 검증. `@lru_cache` 로 프로세스당 클라이언트 1 개.
- **이유:** Supabase 권장. 시크릿 서버 저장 불필요, 키 로테이션 자동 반영.
- **트레이드오프:** cold start 시 JWKS 동기 HTTP 호출 (~100ms), 이후 메모리 캐시.

---

## 2026-04-22 | FastAPI DB — asyncpg + RLS GUC 주입

- **결정:** asyncpg 풀. `acquire_for_user()` 가 transaction 안에서 GUC 2 개 (`role`, `request.jwt.claims`) 를 `set_config` 로 주입해 기존 RLS policy 재사용.
- **이유:** supabase-py 는 트랜잭션 미지원 + SQL 표현력 제한. GUC 주입으로 `auth.uid()` 자동 동작 → SQL 에 `WHERE user_id` 명시 불필요.
- **트레이드오프:** 요청마다 `set_config` 1 회 추가 (단일 SELECT 로 통합).

---

## 2026-04-22 | Supabase Pooler — Session mode (port 5432)

- **결정:** Supavisor Session Pooler (5432). `statement_cache_size=0`.
- **이유:** Direct Connection 은 IPv6-only 로 로컬/Render 접속 불가. Transaction Pooler (6543) 는 `SET LOCAL` 이 connection 반환 후 다른 요청에 영향 가능. Session Pooler 는 connection 당 1 세션 보장.
- **트레이드오프:** 동시 접속 증가 시 풀 소진 가능. MVP 수준에선 문제없음.

---

## 2026-04-20 | SELL avg_buy_price DB 저장

- **결정:** SELL 등록·재계산 시 `profit_loss` 와 `avg_buy_price` 를 함께 계산·저장 (migration 007: `avg_buy_price numeric NULL` 추가).
- **이유:** 조회 시점 WAC 재계산 제거. `recalcGroupPnL` 같은 흐름에서 처리되어 추가 비용 없음.
- **트레이드오프:** 백필 스크립트 1 회 실행.

---

## 2026-04-20 | 수정 불가 필드 확장 — 삭제 후 재등록 정책

- **결정:** account_id, ticker_symbol, asset_name, country_code 를 수정 불가로 확장. 잘못 입력한 거래는 삭제 후 재등록.
- **이유:** cross-group 재계산 (이전 그룹 + 새 그룹 양쪽 검증) 로직이 복잡하고 edge case 많음. 단순 정책이 서버 로직·정합성 모두 유리. 계좌·종목 변경 빈도는 극히 낮음.
- **보완:** TradeEditPanel 에 읽기 전용 표시 + 안내.

---

## 2026-04-20 | WAC fallback 완전 제거

- **결정:** `buildPnlMap`, `buildPositions`, `computeFlexibleBreakdown` 에서 WAC fallback 제거하고 저장값 (`profit_loss`, `avg_buy_price`) 직접 사용. `computeRealizedPnL` 은 테스트용으로 export 유지.
- **이유:** `recalcGroupPnL` 이 CUD 때마다 갱신해 정합성 보장됨. 중복 연산 제거, `computeFlexibleBreakdown` 이 O(n) → O(1).
- **트레이드오프:** `recalcGroupPnL` 실패로 null 남은 행은 손익 0 표시. legacy oversell matched_qty 불일치 케이스는 spec 수용.

---

## 2026-04-19 | 거래·종목 상세 패널 상태 — Context SSOT (2026-04-24 에 2-슬롯으로 대체)

초기 도입 시 `DetailPanelProvider` 의 단일 `mode: "trade" | "stock" | null` SSOT 로 mutual-exclusive 보장 — 무한 중첩 해결. Stock → Trade 이동 시 Stock 이 닫히는 1-단계 뒤로가기 문제로 2026-04-24 에 2-슬롯 + open/payload 분리 구조로 교체.

---

## 2026-04-17 | 시세 API — 비공식 API

- **결정:** 네이버 금융 (KR). Yahoo Finance (US) 는 2026-04-27 결정에 따라 MVP 에서 제외하고 v2 로 이동. KIS Open API 는 v2.
- **트레이드오프:** 응답 포맷 깨질 수 있음.

---

## 2026-04-17 | 평균단가 — WAC (가중평균단가)

- **결정:** 보유 종목 평균단가를 WAC 로 계산.
- **이유:** 한국 증권사 대부분이 WAC — 사용자 익숙도 높음.
- **트레이드오프:** FIFO 대비 세금 계산 정확도 낮음 (세금은 MVP 외).

---

## 2026-04-17 | 분석 탭 WAC — 순수 가격 기준 (수수료 제외)

- **결정:** `portfolio.ts` 와 `realized-pnl.ts` 모두 BUY commission 을 WAC 에서 제외. 수수료는 매도 시점에 `- commission - tax` 로 별도 차감.
- **이유:** 포트폴리오 `avgBuyPrice` 표시와 실현손익 계산 기준 통일.
- **트레이드오프:** BUY 수수료가 큰 계좌에서 실현손익 약간 과대계상 가능.

---

## 2026-04-17 | 자산 탭 제거 → 홈 통합

- **결정:** 별도 자산 탭 없이 홈 (`/`) 에 보유 종목 현황 통합.
- **이유:** 탐색 depth 감소 — 모바일 UX 적합.
- **트레이드오프:** 보유 종목이 많아지면 홈이 길어짐.

---

## 2026-04-17 | 탭 구조 — 홈/기록/분석/설정 (자산 대신 분석)

- **결정:** 4 개 탭, "자산" 대신 "분석".
- **이유:** 매매 패턴 분석이 핵심 목표. 자산 현황은 홈으로 커버.
