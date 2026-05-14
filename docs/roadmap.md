# 투자노트 (Invest Note) — 로드맵

## 제품 개요

개인 투자자를 위한 매매일지 & 포트폴리오 관리 앱.
매매 기록을 빠르게 입력하고, 이유·감정과 함께 저장해 이후 패턴 분석이 가능하도록 설계.

## 핵심 목표

- 매매 기록을 **3~5초 이내** 입력
- 단순 데이터가 아닌 **매매 이유 + 감정** 기록
- **승률·행동 패턴 분석** 가능한 구조

## 기술 스택

| 영역 | 선택 |
|------|------|
| 프론트엔드 | Next.js (App Router, 정적 export) + TypeScript |
| 스타일링 | Tailwind CSS |
| 백엔드 | FastAPI (Python) — Supabase JWKS(ES256) 인증 + asyncpg + RLS |
| DB/Auth | Supabase (PostgreSQL + Auth + RLS) |
| 시세 | 네이버 금융(KR) — 비공식 지연 시세 |
| 배포 | Vercel (웹), Render → Railway (API, 예정) |
| 모바일 | Capacitor (iOS/Android), 향후 React Native 검토 |

## 디자인 원칙

- **모바일 우선** (320px~430px)
- **버튼 기반 선택** — 타이핑 최소화
- 색상: 상승=빨강 `#F04452` / 하락=파랑 `#1B6AC9` (한국 주식 관행)
- 폰트: Pretendard, 금액 tabular-nums

## 릴리즈 계획

| 버전 | 내용 | 상태 |
|------|------|------|
| MVP | 국내 주식 수동 매매 기록, 포트폴리오 조회, 홈 대시보드, 분석 탭 | ✅ 완료 |
| v2.5 | FastAPI 백엔드 분리 + Capacitor 모바일앱 (iOS/Android) | 🚧 FastAPI 배포·Apple Sign-in·스토어 심사 대기 |
| v2 | 해외 주식 지원, KIS API 자동 연동, 공식 실시간 시세 | 예정 |
| v3 | AI 패턴 분석, 모바일 네이티브 전환 검토 (RN) | 예정 |

## MVP 제외 항목 (v2+)

- 증권사 API 자동 연동
- 실시간 시세 (현재: 지연 시세 비공식 API)
- 해외 주식 지원 (Yahoo Finance, USD/KRW 환율, 크로스 통화 분석 정합성 포함)
- AI 분석
- 푸시 알림 (v2.5 모바일앱에서)
- 세금 계산 자동화
