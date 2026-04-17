# 기술 결정 로그

중요한 설계/기술 선택을 기록합니다. "왜 이렇게 했지?"를 나중에 다시 묻지 않기 위해.

---

## 2026-04-17 | 시세 API: 비공식 API 사용

- **결정:** 네이버 금융(KR), Yahoo Finance(US) 비공식 API 사용
- **이유:** KIS Open API 연동은 인증 절차가 복잡하고 MVP 범위 초과
- **트레이드오프:** 언제든 응답 포맷이 깨질 수 있음
- **향후:** v2에서 KIS 공식 API로 교체 예정

---

## 2026-04-17 | 평균단가: WAC(가중평균단가) 방식

- **결정:** 보유 종목 평균단가를 WAC 방식으로 계산
- **이유:** 한국 증권사 대부분이 WAC 방식 사용 — 사용자 익숙도 높음
- **트레이드오프:** FIFO 방식 대비 세금 계산 정확도 낮음 (세금 계산은 MVP 외)

---

## 2026-04-17 | 자산 탭 제거 → 홈 대시보드에 통합

- **결정:** 별도 자산 탭(`/assets`) 없이 홈(`/`)에 보유 종목 현황 통합
- **이유:** 탭을 분리하면 탐색 depth가 늘어남. 홈에서 한눈에 보는 게 모바일 UX에 적합
- **트레이드오프:** 보유 종목이 많아지면 홈이 길어질 수 있음

---

## 2026-04-17 | CSV 임포트: UI만 선구현

- **결정:** `CsvUploadButton` UI는 구현했으나 파싱/임포트 로직은 미구현 (alert placeholder)
- **이유:** 포맷 정의(컬럼 매핑)가 확정되지 않은 상태에서 로직을 먼저 짜면 낭비
- **향후:** 임포트 포맷 확정 후 구현 — `docs/backlog.md` 참고

---

## 2026-04-17 | 데이터 접근 레이어: API Route 단일화

- **결정:** 모든 DB 접근을 `src/app/api/**/route.ts`로 통일. Server Actions 완전 제거, Server Component도 `serverFetch()` 헬퍼로 내부 API 경유
- **이유:** 추후 API를 독립 백엔드 서버로 분리할 계획 — 분리 시점에 `API_BASE_URL` 환경변수만 교체하면 핸들러 본체를 그대로 이식 가능
- **트레이드오프:** Server Actions 대비 네트워크 홉 1회 추가 (SSR → 내부 API). 성능 차이는 미미하나 분리 유연성이 더 중요
- **공용 헬퍼:** `requireUser()`, `serverFetch()`, `api-client.ts` 래퍼로 보일러플레이트 최소화

---

## 2026-04-17 | API 서버 유틸: 공용 validators.ts 추출

- **결정:** Route Handler들이 공유하는 파싱/검증 함수를 `src/lib/api-server/validators.ts`로 통합
- **이유:** `parsePositiveNumber`, `parseCashBalance`, `VALID_TRADE_TYPES` 등이 accounts/trades 4개 파일에 중복 정의되어 있었음 — 한 곳에서 수정하면 전체 반영
- **포함 항목:** account 상수(MAX_NAME_LENGTH 등), trade enum 배열(VALID_STRATEGIES 등), 숫자 파서, `parseTradedAt`(KST +09:00 보정 포함)

---

## 2026-04-17 | 탭 구조: 분석 탭 포함

- **결정:** 홈 / 기록 / 분석 / 설정 4개 탭 (초기 계획의 "자산" 탭 대신 "분석" 탭)
- **이유:** 매매 패턴 분석이 핵심 목표 중 하나. 자산 현황은 홈으로 커버 가능
- **현재 상태:** 분석 탭(`/analysis`)은 스켈레톤 상태 — MVP 마지막 구현 대상
