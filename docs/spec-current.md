# Spec: 어드민 대시보드 누적 사용자수 차트

> 완료: 2026-06-18

## 배경 / 문제

어드민 대시보드(`admin/src/app/(dash)/page.tsx`)는 현재 사용자/계좌/거래/종목/NPS 큐를 단순 숫자 카드로만 보여준다. 사용자 증가 추세를 한눈에 볼 수단이 없다. `public.users.created_at`(timestamptz, NOT NULL) 으로 가입 시각이 기록되므로, 이를 일별 누적으로 집계해 시계열 라인 차트로 표시한다.

**확정 사항**: 시간 단위 = **일별**, 표시 = **누적선만**(일별 신규 가입 바 없음).

## 목표

- 어드민 대시보드 통계 카드 아래에 "누적 사용자수" 라인 차트가 표시된다.
- 차트는 일별 누적 가입자 수(단조증가)를 보여준다.
- 비-admin 계정은 기존 가드대로 데이터 접근 불가(403).
- BE/FE 타입 체크·테스트 통과.

## 설계

### 접근 방식

- **BE**: 신규 `GET /admin/user-growth` 엔드포인트 추가(기존 `/stats` 확장 금지 — flat 모델·shape 테스트 보호). `require_admin` 가드 재사용. 응답은 타입드 모델 리스트 `list[UserGrowthPoint]`, point = `{date, cumulative}`.
  - SQL: `GROUP BY day` 후 `SUM(cnt) OVER (ORDER BY day)` 윈도우 함수.
  - 타임존: `(created_at at time zone 'Asia/Seoul')::date` 로 버킷팅(단순 `::date`는 UTC 버킷이라 가입일 ±9h 어긋남).
  - 가입 없는 날은 생략(누적이라 단조증가 유지, 차트 라인은 연속).
- **FE**: 차트 라이브러리는 **recharts**(shadcn `chart` 컴포넌트의 기반). React 19.2.4 호환 위해 **recharts v3+** 설치.
  - shadcn `chart` 컴포넌트 추가 → `src/components/ui/chart.tsx` 생성.
  - AGENTS.md 래퍼 규칙은 *shadcn 컴포넌트*에만 적용 → `src/components/base/Chart.tsx` 신설(`ui/chart.tsx`의 helper를 `base/Dialog.tsx`와 동일한 re-export 패턴으로 노출). recharts primitive는 차트 컴포넌트 내부에서 직접 import.
  - `globals.css`에 `--chart-1`~`--chart-5` 이미 존재 → 색상 변수 추가 불필요.

### 주요 변경 파일 (의존 순서: BE → FE)

**Backend**
- `api/src/invest_note_api/schemas/admin.py` — `UserGrowthPoint(BaseModel)` 추가.
- `api/src/invest_note_api/db_ops/admin_repo.py` — `get_user_growth(conn)` 추가.
- `api/src/invest_note_api/routers/admin.py` — `GET /admin/user-growth` 핸들러(catch-all `/{table}` 앞 등록).
- `api/tests/test_admin_crud.py` — 신규 엔드포인트 게이트+shape 테스트.

**Admin Frontend**
- recharts v3+ 설치, `admin/src/components/ui/chart.tsx`(shadcn) 추가.
- `admin/src/components/base/Chart.tsx` — 신규 래퍼.
- `admin/src/lib/api.ts` — `adminApi.userGrowth` + `UserGrowthPoint` 타입.
- `admin/src/components/UserGrowthChart.tsx` — 신규 차트 컴포넌트(로딩/에러/누적선).
- `admin/src/app/(dash)/page.tsx` — 카드 grid 아래 차트 섹션 추가.

## 구현 체크리스트

- [x] BE: `UserGrowthPoint` 스키마 추가
- [x] BE: `admin_repo.get_user_growth` 일별 누적 쿼리(Asia/Seoul 버킷)
- [x] BE: `GET /admin/user-growth` 핸들러 (catch-all 앞 등록)
- [x] BE: `test_admin_crud.py` 게이트+shape 테스트 → 26 passed
- [x] FE: recharts v3.8.1 설치 + shadcn `chart` 컴포넌트
- [x] FE: `base/Chart.tsx` 래퍼
- [x] FE: `lib/api.ts` `adminApi.userGrowth` + 타입
- [x] FE: `UserGrowthChart` 컴포넌트(로딩/에러/누적선)
- [x] FE: `page.tsx`에 차트 섹션 추가
- [x] 타입 체크: `pnpm -C admin exec tsc --noEmit` 통과, `pnpm -C admin build` 통과 (lint 는 프로젝트 전역 eslint.config 부재로 실패 — 본 작업과 무관)

## 우려사항 / 리스크

- **recharts 버전**: React 19.2.4 + Next 16.2.3 → recharts v2 peer-dep 충돌 가능. v3+ 필수.
- **타임존**: UTC `::date` 버킷팅 시 KST 가입일 ±9h 어긋남 → `at time zone 'Asia/Seoul'` 필수.
- **라우트 순서**: `/user-growth`를 catch-all `/{table}` 뒤에 두면 오매칭 → 반드시 앞에 등록.
- **데이터 0건**: users 비어있으면 빈 배열 → FE 빈 상태 처리.
