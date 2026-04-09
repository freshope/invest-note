# 투자노트 (Invest Note) — 제품 계획

<!-- /autoplan restore point: /Users/jwlee/.gstack/projects/invest-note/develop-autoplan-restore-20260409-143731.md -->

## 제품 개요

**제품명:** 투자노트  
**카테고리:** 개인 투자 관리 웹앱 (모바일 우선)  
**목표:** 주식 매매일지 작성과 투자 내역을 개인 투자자에 최적화해 한눈에 볼 수 있도록 지원

---

## 핵심 아이디어

1. **주식 매매일지 작성/확인** — 매매 기록을 일지 형태로 작성하고 이력 조회
2. **매매 데이터 자동/수동 입력** — API 연동 가능하면 자동, 불가하면 수동 입력 지원
3. **투자 내역 자동/수동 입력** — API 연동 가능하면 자동, 불가하면 수동 입력 지원
4. **투자 내역 한눈에 보기** — 개인 투자자 최적화 대시보드 (수익률, 평가손익, 포트폴리오 비중 등)
5. **다중 계좌 통합** — 여러 증권사 계좌를 등록하고 합산해서 조회
6. **웹앱 우선, 추후 모바일 포팅** — React 기반 PWA 또는 Next.js 웹앱

---

## 플랫폼 & 기술 스택 (초안)

- **프론트엔드:** Next.js 14 (App Router) + TypeScript + Tailwind CSS
- **백엔드:** Next.js API Routes 또는 별도 FastAPI
- **DB:** PostgreSQL (Supabase 또는 PlanetScale)
- **인증:** NextAuth.js (소셜 로그인)
- **증권사 API:** 한국투자증권 KIS API, 키움 OpenAPI (데스크톱 앱 한계로 웹 한계 존재)
- **배포:** Vercel (프론트엔드) + Supabase (DB)

---

## 디자인 방향

- **모바일 우선** — 320px ~ 430px 기준 설계, 데스크톱은 선택
- **첫 화면 thesis:** "오늘의 투자 상태와 취해야 할 행동을 3초 안에 보여준다"
- **디자인 레퍼런스:** 토스(정보 신뢰감·액션 명확성), 카카오페이(친근한 금융 톤), Minical(밀도 규율)
- **톤:** 간결, 신뢰감, 숫자 중심

### 색상 시스템 (한국 주식 관행 — 미국과 반대)
- 상승 = 빨강 `#F04452`
- 하락 = 파랑 `#1B6AC9`
- 보합 = 회색 `#8B95A1`
- 배경 = 흰색 `#FFFFFF`
- 기본 텍스트 = `#1A1A1A`
- 브랜드 = `#3366FF`

### 타이포그래피
- 폰트: Pretendard (무료, 한글 최적화, tabular-nums)
- 금액: ₩1,234,567 (₩ 기호 + 콤마 구분)
- 수익률: +1.23% / -0.45% (색상 + 기호 모두 표시)
- 주가 소수점: 2자리 허용
- 수량: 정수

### 핵심 UX 패턴
- 바텀시트 (상세 보기, 일지 작성)
- 레이아웃 우선, 카드는 필요한 곳만 (거래 목록, 계좌 모듈)
- 스와이프 액션 (삭제, 일지 이동)
- 탭 네비게이션 3개 (하단): 홈 / 기록 / 자산

### 접근성
- 터치 타깃 최소 44×44px
- 색상 대비 4.5:1 이상 (WCAG AA)
- +/- 기호와 색상 병행 (색맹 고려)
- 최소 폰트 14sp

---

## 핵심 화면 (MVP) — 정보 계층 포함

### 홈 화면
```
1순위 (36px bold): 총 평가금액 (₩23,456,789)
2순위 (24px, 색상+기호): 오늘 손익 (+₩234,000 / +1.23%)
3순위: 계좌별 스냅샷 카드 (2-3개)
4순위: 보유 종목 상위 3개 (간략)
고정 하단 CTA: "오늘 거래 기록하기"
```

### 탭 구조 (3탭, 이전 5탭에서 축소)
1. **홈** — 대시보드 + 오늘 손익 (설정: 우상단 아이콘)
2. **기록** — 매매 입력 + 매매일지 목록/작성
3. **자산** — 포트폴리오 (보유 종목, 비중, 계좌별 보기)

### 매매일지 2단계 플로우
- 1단계 (매수 시점): 이유, 목표가, 손절가
- 2단계 (매도 후): 결과, 교훈
- 매수 기록 저장 시 → "일지 작성" 바텀시트 자동 노출

### 종목 코드 처리
- 국내: 6자리 숫자 (005930 → 삼성전자)
- 해외: 알파벳 티커 (AAPL, TSLA)
- 검색: 코드 or 이름 모두 허용

### 숫자 입력 (모바일)
- 금액: `inputmode="decimal"` + 커스텀 콤마 포맷터
- 수량: `inputmode="numeric"` (정수)

### 상태 테이블
```
FEATURE       | LOADING      | EMPTY              | ERROR          | SUCCESS
──────────────────────────────────────────────────────────────────────────────
홈 대시보드   | 스켈레톤 UI  | 온보딩 가이드+CTA  | 에러 배너      | 정상 표시
매매 입력     | 제출 중 표시 | N/A                | 필드 에러 인라인| 완료 토스트
일지 작성     | 저장 중      | "첫 일지를 쓰세요" | 실패 재시도    | 저장 완료
현재가 조회   | 점 깜빡임    | "-"                | 캐시+"N분 전"  | 금액 표시
CSV 임포트    | 진행 바      | N/A                | 에러 행 목록   | N개 완료
다중 계좌     | 탭별 스켈레톤| 계좌 추가 안내     | 계좌 오류 표시 | 합산 표시
```

### 다중 계좌 전환
- 홈 상단 드롭다운 or 탭: "전체 / 계좌1 / 계좌2"
- 동일 종목 다계좌 보유 시 → 자산 탭에서 계좌별 분리 표시 (기본) + 합산 옵션

---

## 기술 스택 (확정)

### 인증
- **Supabase Auth** (단독 사용 — NextAuth 제거, JWT → RLS 직결)

### DB 전략
- **Supabase PostgreSQL** (PlanetScale 제외)
- **migrations:** `supabase/migrations/` 파일 기반
- **holdings:** materialized view (DB 트리거 자동 갱신)
- **trades:** immutable ledger (삭제 대신 soft cancel)
- **RLS:** 모든 테이블 적용

### 평균단가 정책
- **가중평균(WAC)** — 계좌별 독립 계산
- 수수료 포함: `(매수금액 + 수수료) / 수량`
- 다계좌 합산: `(A_qty * A_avg + B_qty * B_avg) / (A_qty + B_qty)`
- 수량 음수 방지: DB `CHECK (qty >= 0)` + API 검증

### 현재가 API
- **국내:** KRX Open API (15분 지연, 무료, 공식)
- **해외:** Yahoo Finance v8 API
- **캐시 정책:** 15분 이내 = 정상, 15분-2시간 = 경고, 2시간+ = "-"

### 오프라인 전략 (PWA)
- **읽기 전용 오프라인** (쓰기 미지원 — 동기화 복잡도 회피)
- Service Worker: 최근 포트폴리오 캐시

### 환경변수 명세
```
NEXT_PUBLIC_SUPABASE_URL=
NEXT_PUBLIC_SUPABASE_ANON_KEY=
SUPABASE_SERVICE_ROLE_KEY=
KRX_API_KEY=
YAHOO_FINANCE_FALLBACK=true
```

### CSV 임포트 — 지원 증권사 (MVP)
1. 키움증권 (HTS 거래내역)
2. 삼성증권 (mPOP 거래내역)
3. NH투자증권 (나무 거래내역)
- 인터페이스: `BrokerParser` (lib/importers/types.ts)
- 미지원 증권사: 수동 입력 안내

### TTHW 목표 (로컬 개발 셋업)
```
1. pnpm install       (~2분)
2. supabase db push   (~3분)
3. .env.local 설정    (~3분, .env.example 제공)
4. pnpm dev           (~1분)
= 총 ~9분
```

---

## MVP 범위

### 포함
- 수동 매매 기록 입력 (종목, 매수/매도, 수량, 가격, 날짜)
- 매매일지 작성 (2단계: 투자이유 + 매도 후 회고, 텍스트 + 태그)
- 보유 종목 자동 계산 (WAC 기반, DB 트리거)
- 평가손익 계산 (KRX API + 15분 지연 정책)
- 다중 계좌 등록 (수동)
- ~~CSV 임포트~~ → v2로 이동 (사용자 결정: 수동 입력 UX 품질 우선)
- KOSPI/KOSDAQ 벤치마크 비교
- 일지에 주가 차트 자동 삽입 (매수/매도 시점 표시)
- 오늘 손익 공유 카드
- ~~한국투자증권 KIS API 연동~~ → v2로 이동 (사용자 결정: 수동 우선)

### 제외 (v2+)
- 키움 OpenAPI (데스크톱 전용, 웹 불가)
- 자동 세금 계산
- 실시간 알림 (푸시)
- 소셜 기능 (공유, 팔로우)
- 모바일 네이티브 앱

---

## 성공 지표

- 사용자가 매일 매매 기록을 입력하고 확인하는 습관 형성
- 포트폴리오 현황을 30초 이내에 파악 가능
- 매매일지 작성이 3분 이내 완료

---

## 리스크 & 가정

- **증권사 API 접근:** KIS API는 공개 REST API지만 계좌별 인증 필요. 일부 증권사는 웹 API 미제공
- **현재가 API:** 한국 주식 실시간 데이터는 유료 or 15분 지연. Yahoo Finance KR 지원 제한적
- **데이터 정확성:** 수동 입력 의존 시 오기입 리스크
- **개인정보:** 금융 데이터 처리 — 최소한의 서버 저장, 가능하면 클라이언트 암호화

## Decision Audit Trail

| # | Phase | Decision | Classification | Principle | Rationale | Rejected |
|---|-------|----------|----------------|-----------|-----------|---------|
| 1 | CEO | Approach C 선택 (Next.js + Supabase + PWA) | Mechanical | P1+P5 | KIS API CORS로 서버 필요, 모바일 우선 = PWA | A,B |
| 2 | CEO | CSV 임포트 범위에 추가 | Mechanical | P1+P2 | 모든 증권사 지원 현실적 방법 | — |
| 3 | CEO | 벤치마크 비교 추가 | Mechanical | P1+P2 | 차트 3줄 추가, 임팩트 큼 | — |
| 4 | CEO | 일지에 주가 차트 삽입 추가 | Mechanical | P1+P2 | 핵심 UX, 없으면 밋밋 | — |
| 5 | CEO | 공유 카드 추가 | Mechanical | P1+P2 | 바이럴+동기부여 | — |
| 6-8 | CEO | AI 분석/알림/세금/리포트 DEFER | Mechanical | P3 | MVP 이후, 핵심 기능 우선 | — |
| 9 | CEO | MVP에서 KIS API 제외 (User direction) | User direction | P5+P3 | 사용자: 수동 우선 → API는 v2 | — |
| 10 | CEO | SELECTIVE EXPANSION 모드 | Mechanical | P3 | 사용자가 MVP 범위 명확히 정의 | — |
| 11 | CEO | holdings 캐시 저장 방식 | Mechanical | P5 | 성능상 유리, 동기화 관리 | 재계산 |
| 12 | CEO | iconv-lite EUC-KR→UTF-8 변환 추가 | Mechanical | P1 | 한국 증권사 CSV는 대부분 EUC-KR | — |
| 18 | Design | 홈 화면 정보 계층 명시 | Mechanical | P1+P5 | 크기/순서/강조도 없으면 구현자가 임의 결정 | — |
| 19 | Design | 상태 테이블 추가 | Mechanical | P1 | 빈 상태 등 미정의 = Critical 갭 | — |
| 20 | Design | 2단계 일지 플로우 | Mechanical | P1+P5 | 투자이유 vs 회고가 다른 UX | — |
| 21 | Design | 탭 5→3개로 축소 + 첫화면 thesis | Mechanical | P5 | 5탭은 과도, 3탭이 명확 | — |
| 22 | Design | Pretendard 폰트 + 금액 포맷 | Mechanical | P5 | 미정의시 구현자가 임의 선택 | — |
| 23 | Design | 접근성 기본 기준 | Mechanical | P1 | 색맹 투자자 배려 | — |
| 24 | Design | 종목 타입 구분 + 색상 명시 | Mechanical | P5 | 한국=빨강상승, 미지정시 미국관행 적용 위험 | — |
| 25 | Eng | Supabase Auth 단독 (NextAuth 제거) | Mechanical | P5 | JWT 클레임 중복 복잡도 제거 | NextAuth |
| 26 | Eng | holdings materialized view | Mechanical | P5 | 캐시 드리프트 방지 | 캐시 저장 |
| 27 | Eng | trades immutable ledger | Mechanical | P1 | 금융 데이터 무결성 | 직접 수정 |
| 28 | Eng | 오프라인 읽기만 (쓰기 미지원 MVP) | Mechanical | P3+P5 | 동기화 충돌 복잡도 회피 | 오프라인 쓰기 |
| 29 | Eng | WAC 방식 평균단가 확정 | Mechanical | P5 | 한국 MTS 관행 일치, 명시적 정책 | FIFO |
| 30 | Eng | 클라이언트 암호화 제거 | Mechanical | P5 | 서버사이드 CSV 처리와 충돌 | 클라이언트 암호화 |
| 31 | Eng | CSV MVP 증권사 3개 확정 | Mechanical | P3+P5 | 실용적 범위, 나머지 수동 안내 | 전체 지원 |
| 32 | Eng | 15분 지연 표시 정책 확정 | Mechanical | P5 | 사용자가 실시간으로 오인하지 않도록 | 무표시 |
| 33 | DX | .env.example + 환경변수 명세 | Mechanical | P1+P5 | 미제공시 개발자 60-90분 낭비 | — |
| 34 | DX | Supabase migrations 파일 전략 | Mechanical | P5 | supabase db push 한 번으로 셋업 | 대시보드 직접 설정 |
| 35 | DX | BrokerParser 인터페이스 정의 | Mechanical | P5 | 새 증권사 추가 방법 명확화 | — |
| 36 | DX | 현재가 API 확정 (KRX + Yahoo) | Mechanical | P3 | 미확정시 개발자가 직접 조사해야 함 | — |
| 37 | Final | CSV 임포트 v2로 이동 | User direction | P5 | 사용자 결정: 수동 입력 UX 품질 먼저 | MVP 포함 |
| 13 | CEO | Supabase RLS 모든 테이블 적용 | Mechanical | P1 | 보안 기본 | — |
| 14 | CEO | 파일 업로드 5MB + 10,000행 제한 | Mechanical | P5 | 명시적 제한 | — |
| 15 | CEO | 더블 제출 방지 (debounce + disable) | Mechanical | P1 | 완성도 | — |
| 16 | CEO | 계좌 삭제 soft delete | Mechanical | P5 | 데이터 보전 | CASCADE |
| 17 | CEO | 주가 Batch 조회 | Mechanical | P5 | N+1 방지 | 개별 조회 |

## GSTACK REVIEW REPORT

| Review | Trigger | Why | Runs | Status | Findings |
|--------|---------|-----|------|--------|----------|
| CEO Review | `/gstack-autoplan` | 전략 & 범위 | 1 | issues_open (2 User Challenges) | JTBD 혼재, 수동 리텐션 |
| Design Review | `/gstack-autoplan` | UI/UX 갭 | 1 | clean | 색상/계층/상태 모두 반영 |
| Eng Review | `/gstack-autoplan` | 아키텍처 & 테스트 | 1 | clean | Critical 3건 해결 |
| DX Review | `/gstack-autoplan` | 개발자 경험 | 1 | issues_open | TTHW 9분 목표 |

**VERDICT:** APPROVED — 37개 결정, 4개 페이즈 완료. 사용자 결정: CSV 임포트 v2, 수동 입력 U선.
