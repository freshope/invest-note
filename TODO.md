# 투자노트 MVP — 구현 TODO

각 단계는 독립적으로 실행 가능. 순서대로 하나씩 진행.

---

## Step 1: 프로젝트 기초 세팅
- [ ] Supabase 패키지 설치 (`@supabase/supabase-js`, `@supabase/ssr`)
- [ ] Pretendard 폰트 적용
- [ ] 글로벌 CSS — 색상 변수 정의 (상승 `#F04452`, 하락 `#1B6AC9`, 브랜드 `#3366FF`)
- [ ] `.env.local.example` 작성
- [ ] Supabase 클라이언트 유틸 (`src/lib/supabase/client.ts`, `server.ts`)
- [ ] 모바일 우선 뷰포트 메타 설정

## Step 2: DB 스키마 & 타입 정의
- [ ] Supabase migration: `accounts` 테이블
- [ ] Supabase migration: `trades` 테이블 (전략/감정/복기 포함)
- [ ] enum 타입 정의 (marketType, tradeType, strategyType, reasoningTag, emotion, result)
- [ ] RLS 정책 설정
- [ ] TypeScript 타입 정의 (`src/types/database.ts`)

## Step 3: 인증
- [ ] 로그인/회원가입 페이지 (`src/app/login/page.tsx`)
- [ ] Supabase Auth 미들웨어 (세션 관리)
- [ ] 인증 상태 체크 & 리다이렉트
- [ ] 로그아웃 기능

## Step 4: 레이아웃 & 네비게이션
- [ ] 모바일 바텀 탭 네비게이션 (홈 / 기록 / 자산)
- [ ] 앱 레이아웃 (`src/app/(app)/layout.tsx`) — 인증 보호
- [ ] 각 탭 빈 페이지 생성

## Step 5: 계좌 관리
- [ ] 설정 페이지 (`src/app/(app)/settings/page.tsx`)
- [ ] 계좌 CRUD (추가/수정/삭제)
- [ ] 예수금 수동 입력 필드 (`cash_balance`)
- [ ] 증권사 선택

## Step 6: 거래 기록 입력 폼
- [ ] 거래 입력 페이지 (`src/app/(app)/records/new/page.tsx`)
- [ ] 종목명 입력
- [ ] 매수/매도 토글
- [ ] 가격/수량 입력 (자동 총액 계산)
- [ ] 날짜 선택, 계좌 선택

## Step 7: 전략·감정·메모 입력
- [ ] 전략 버튼 그룹 (SCALPING / SWING / LONG_TERM / UNKNOWN)
- [ ] 감정 버튼 그룹 (CONFIDENT / ANXIOUS / FOMO / IMPULSIVE / CALM)
- [ ] 분석태그 다중 선택 (TECHNICAL / FUNDAMENTAL / NEWS / FEELING)
- [ ] 매매 이유 텍스트 입력 (선택)
- [ ] 폼 제출 → Supabase insert

## Step 8: 거래 목록 & 상세
- [ ] 기록 탭 — 거래 목록 (최신순)
- [ ] 거래 카드 UI
- [ ] 거래 상세 보기
- [ ] 거래 수정/삭제

## Step 9: 복기 (회고)
- [ ] 매도 거래에 복기 작성
- [ ] result 선택 (SUCCESS / FAIL / BREAKEVEN)
- [ ] reflectionNote, improvementNote 입력
- [ ] 기존 거래에 복기 추가/수정

## Step 10: 홈 대시보드
- [ ] 총 자산 표시 (주식 평가 + 예수금)
- [ ] 계좌별 스냅샷 카드
- [ ] 보유 종목 상위 목록
- [ ] 빈 상태 온보딩 UI

## Step 11: 자산 탭
- [ ] 보유 종목 목록 (평균단가 WAC 계산)
- [ ] 종목별 평가손익 표시
- [ ] 계좌별 필터
- [ ] 예수금 행 표시

## Step 12: 기본 통계
- [ ] 총 거래 수
- [ ] 승률 (SUCCESS / FAIL 기반)
- [ ] 총 수익/손실 합계
- [ ] 홈 대시보드에 통계 카드 추가
