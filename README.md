# 투자노트 (Invest Note)

개인 투자자를 위한 **매매일지 · 포트폴리오 분석 앱**입니다. 거래를 매매 이유·감정과 함께 기록하면, 종목·태그·키워드 단위로 승률·실현손익·보유기간·집중도 같은 통계를 자동으로 산출합니다.

**기획부터 설계 · 개발 · 배포 · 운영까지 1인으로** 진행했으며, App Store와 Google Play에 출시해 실제로 운영 중입니다.

[![App Store](https://img.shields.io/badge/App_Store-출시-0D96F6?logo=apple&logoColor=white)](https://apps.apple.com/kr/app/id6769310576)
[![Google Play](https://img.shields.io/badge/Google_Play-출시-414141?logo=googleplay&logoColor=white)](https://play.google.com/store/apps/details?id=app.pixelwave.investnote)

| | |
|---|---|
| **상태** | 양대 스토어 출시 · 운영 중 (BE v1.3.10 / App v1.3.4) |
| **범위** | 1인 풀스택 — 프로덕트 · 백엔드 · 모바일 · 인프라 · 운영 |
| **규모** | 모노레포 3개 워크스페이스 · 자동화 테스트 백엔드 950+ / 프론트 260+ |

---

## 기술 스택

| 영역 | 스택 |
|------|------|
| 프론트엔드 | Next.js 16 (App Router · 정적 export) · React 19 · TypeScript · Tailwind CSS 4 |
| 모바일 | Capacitor 8 (iOS / Android) · 자체 호스팅 OTA |
| 데이터/폼 | TanStack Query · React Hook Form · Zod · Recharts |
| 백엔드 | FastAPI 0.115 · Python 3.12 · asyncpg · Pydantic |
| DB / 마이그레이션 | self-hosted PostgreSQL · Alembic |
| 인증 | OIDC issuer registry verifier · 자체 토큰 브로커 (ES256 / JWKS) · Authlib OAuth |
| 제품 분석 | PostHog (FE 전용 · Cloud) |
| 인프라 | Coolify (self-hosted) · Cloudflare R2 (OTA · 파일) · GitHub Actions |

**아키텍처 개요**

```
모바일 앱 (Capacitor + Next.js)  ──►  FastAPI  ──►  PostgreSQL
                                        │
                                        └──►  외부 공급자 (네이버 · Yahoo · KIS · data.go.kr · OpenFIGI)
```

하나의 Next.js 코드베이스를 웹으로 빌드해 Capacitor로 iOS·Android 네이티브로 패키징합니다. 백엔드는 단일 FastAPI 서비스로, 시세·환율·종목마스터·거래내역서 파싱 등 외부 의존을 모두 어댑터 뒤로 격리합니다.

## 모노레포 구성

| 디렉터리 | 설명 |
|---|---|
| `api/` | FastAPI 백엔드 — 라우터 15 · 도메인 로직 · 외부 공급자 어댑터 · 증권사 파서 · Alembic 마이그레이션 12 |
| `app/` | 크로스플랫폼 모바일 앱 — Capacitor + Next.js (홈 · 기록 · 분석 · 설정 탭) |
| `admin/` | 운영 어드민 패널 — Next.js SPA (공지/게시판 · 회원·탈퇴 통계 등) |
| `docs/` | 로드맵 · 백로그 · **기술 결정 로그(`decisions.md`)** · 스펙 히스토리 |
| `supabase/` | *(legacy)* 초기 Supabase 스키마 아카이브 — 현재 마이그레이션은 Alembic이 단일 소유 |

## 설계 하이라이트

기술 결정은 `docs/decisions.md`에 **"문제 → 결정 → 트레이드오프"** 형태로 시간순 기록해 둡니다. 대표적인 것들:

### 1. 외부 시세 데이터 — 공급자 추상화 + 체인 폴백
**문제:** 네이버·Yahoo·KIS·공공데이터(data.go.kr) 등 출처가 제각각이고 비공식·간헐 실패가 잦습니다.
**결정:** 도메인별 `dict[name, fn]` registry + 환경변수 체인으로 공급자를 조합하고(`external/provider_registry.py`), 한 소스가 실패하면 다음 소스로 자동 폴백합니다. 반복 호출은 **TTLCache**(시세 45초·환율 10분)로 줄이고, 시세는 동시 요청이 첫 호출만 실제로 나가도록 **single-flight**로 묶었습니다.
**트레이드오프:** KIS는 토큰 발급 한도가 빡빡해 **레이트리밋 페이싱**(슬라이딩 윈도우 + 슬롯 대기 예산)과 토큰의 PostgreSQL 영속화(advisory lock)로 호출을 한도 안에 가뒀습니다.

### 2. 증권사 거래내역서 파싱
신한·미래에셋·삼성·토스의 거래내역서(PDF·Excel)를 파싱해 거래로 일괄 등록합니다(`broker_import/`). 증권사마다 다른 양식을 공통 인터페이스(`base.py`)로 추상화했고, 토스 해외 거래는 종목명 매칭의 오류를 없애기 위해 **OpenFIGI로 ISIN → 티커를 정확 매칭**합니다. 추정 구현 대신 실제 거래내역서 샘플 기반 회귀 테스트로 양식 변형을 가드합니다.

### 3. 무중단 인증 마이그레이션 (탈-Supabase)
**문제:** 초기에 Supabase Auth로 시작했으나, 운영 중인 사용자를 깨뜨리지 않고 자체 토큰 브로커(ES256 / JWKS)로 이전해야 했습니다.
**결정:** **expand/contract + 서버 플래그 cutover**. OIDC issuer registry로 두 발급자를 공존시키고, identity→profile 백필 완료를 *전제 조건*으로 두어 플래그를 뒤집는 방식입니다.
**결과:** 운영 cutover를 무중단으로 완료(`docs/decisions.md`의 "탈-Supabase Auth Phase 1~2c").

### 4. 크로스플랫폼 + 자체 OTA
하나의 Next.js 빌드를 Capacitor로 양 플랫폼 네이티브로 패키징하고, 라이브 업데이트는 상용 서비스 대신 **Cloudflare R2(JSON SSOT) 기반 OTA를 자체 호스팅**했습니다. 네이티브 버전 스큐를 매니페스트에서 판정해 강제 업데이트로 안전하게 폴백하고, 부팅 실패 번들은 자동 롤백합니다.

### 5. 매매 분석 엔진
거래를 종목·태그·키워드 단위로 집계해 승률·실현손익·보유기간·집중도(HHI) 등을 산출합니다(`domain/`). 손익 계산은 매수-매도 매칭 walker로 일관 처리하고, 사용자 정의 분석 태그는 레지스트리 테이블로 분리해 거래 레코드와 디커플링했습니다. 해외 주식은 거래 시점 환율을 박제해 KRW 환산 총액으로 통합 표시합니다.

## 엔지니어링 · 품질

- **테스트:** 백엔드 950+ (pytest / asyncpg 실DB 픽스처) · 프론트 260+ (Vitest). 사용자 격리·손익 계산·증권사 파서 회귀를 자동 가드.
- **결정 로그 습관:** `docs/decisions.md`에 설계 선택의 *왜와 트레이드오프*를 보존 — "왜 이렇게 했지?"를 다시 묻지 않기 위함.
- **마이그레이션 규율:** Alembic 단일 소유. RLS 제거 후 사용자 격리는 앱 레이어 `WHERE user_id`로 단일화하고 회귀 테스트로 가드.
- **스펙 우선 워크플로:** `docs/spec-current.md` → 작은 단위 구현 → `docs/spec-history/` 보관.

## 로컬 실행

각 워크스페이스가 독립적으로 실행됩니다.

```bash
# 백엔드 (api/) — 자세한 내용은 api/README.md
cd api && poetry install && make dev

# 모바일 앱 웹 미리보기 (app/)
cd app && pnpm install && pnpm dev
```

## 더 보기

- 설계 결정 배경 — [`docs/decisions.md`](docs/decisions.md)
- 제품 로드맵 — [`docs/roadmap.md`](docs/roadmap.md)
- 백엔드 상세 — [`api/README.md`](api/README.md)
