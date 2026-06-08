# 출시 노트 요약 — v1.1.21_26 (스토어 제출 생략 — 백엔드 배포 중심)

> 작성일: 2026-06-08
> 비교 기준: v1.1.20_25 (2026-06-06)
> 대상 빌드: fe-v1.1.21_26 / be-v1.1.21 (준비 중 — release/fe-v1.1.21_26, bump 커밋 완료, 태그 전)
> 스토어 노트: 없음 — 사용자 가시 변경 0건이라 모바일 스토어 제출 생략 결정

## Git 로그 (v1.1.20_25..HEAD, --no-merges)

| 해시 | 날짜 | 메시지 |
|------|------|--------|
| 3ad1e40 | 2026-06-08 | chore: bump version fe-v1.1.21_26 |
| 2a06f25 | 2026-06-07 | test(be): conftest 에서 .env.local dotenv 소스 전역 격리 |
| d474b85 | 2026-06-07 | fix(be): 코드리뷰 후속 — KIS 토큰 발급 가드·공급자 env fail-fast 보강 |
| 7bb6ed2 | 2026-06-07 | chore: Makefile 을 devtools 멀티 프로젝트 구성(PROJECTS)으로 전환 |
| 25fa22a | 2026-06-07 | fix(be): 코드리뷰 후속 — 공급자 env 가드 3건 보강 |
| be68c94 | 2026-06-07 | feat: KIS 토큰 DB 영속화 — kis_tokens 테이블 + advisory lock 발급 직렬화 |
| e0bebc6 | 2026-06-07 | fix(be): KIS 레이트리밋 실측 반영 — 전역 페이싱 + 시세 budget fallback |
| f4986e3 | 2026-06-07 | feat(be): KIS 종목마스터 seed 소스 + 교차검증 provider 토글 |
| db9ffc8 | 2026-06-07 | feat(be): KIS 일별 종가 provider — primary/gap registry 등록 |
| 680a4b2 | 2026-06-07 | feat(be): KIS 시세 provider — _QUOTE_REGISTRY 등록 |
| b81a725 | 2026-06-07 | feat(be): KIS Open API 공통 클라이언트 — 토큰 캐시 + 요청 헬퍼 + config |
| 499ee92 | 2026-06-07 | ci: 통합 ci.yml 을 BE/FE 경로 필터 워크플로로 분리 |
| af1c86c | 2026-06-07 | fix(be): 공급자 env 리뷰 후속 — 값 정규화·기본값 단일화·전달 테스트 보강 |
| f182bc6 | 2026-06-07 | feat(be): 외부 데이터 공급자 env 토글 구조 도입 |
| 786f592 | 2026-06-06 | chore(fe): 파비콘을 새 앱 아이콘 디자인으로 교체 |
| 58fedd9 | 2026-06-06 | chore(fe): 앱 아이콘 이미지 용량 최적화 |

(docs 이동/문서 갱신 커밋은 표에서 생략)

## 동기간 issue-history 항목

- 2026-06-07-env-provider-toggle.md — 외부 데이터 공급자 env 토글 구조 도입 (provider registry + 환경변수 선택)
- 2026-06-07-kis-data-providers.md — KIS Open API 시세/일별 종가/종목마스터 provider 등록 (env 토글 뒤 대기, prod 미활성)
- 2026-06-07-kis-token-persistence.md — KIS 토큰 DB 영속화 (kis_tokens 테이블 + advisory lock 발급 직렬화)

## 분류표

| 라벨 | 항목 | 출시 노트 반영 |
|------|------|--------------|
| INTERNAL | KIS Open API 공통 클라이언트 + 시세/일별종가/종목마스터 provider 등록 (b81a725, 680a4b2, db9ffc8, f4986e3) — prod env 게이트오프, 사용자 무영향 | ✗ |
| INTERNAL | KIS 토큰 DB 영속화 + advisory lock (be68c94), 레이트리밋 페이싱 (e0bebc6), 발급 가드 (d474b85) | ✗ |
| INTERNAL | 외부 데이터 공급자 env 토글 구조 (f182bc6, af1c86c) | ✗ |
| INTERNAL | Makefile devtools 멀티프로젝트 전환 (7bb6ed2), CI 경로 필터 분리 (499ee92), conftest env 격리 (2a06f25) | ✗ |
| INTERNAL | 웹 파비콘/아이콘 최적화 (786f592, 58fedd9) — Capacitor 네이티브 앱에 비노출 | ✗ |

사용자 가시(NEW/IMPROVE/FIX) 항목: 0건.

## 검증 결과

- app-store-ko.md / play-store-ko.md: 작성 안 함 (스토어 제출 생략)
- 사용자 가시 변경 0건 확인 — KIS provider 전부 prod env 게이트오프 (`QUOTE_PROVIDERS=naver,yahoo`, `DAILY_PRICE_PROVIDER=data_go_kr`, `STOCK_SEARCH_PROVIDER=naver`, `CROSSVALIDATE_PROVIDER=naver`)
- 버전: fe 1.1.21/26 (3곳 일치), be 1.1.21 (독립 SemVer)

## 배포 체크리스트 (출시 노트 외 운영 작업 — 6.5 단계)

- **DB 마이그레이션: 필요** — 신규 `supabase/migrations/028_kis_tokens.sql` (kis_tokens 테이블 추가). 신규 BE 코드가 startup/import 경로에서 이 테이블을 참조하므로 **BE 배포(main push) 전에 `supabase db push --linked` 선행 필수** (순서 뒤바뀌면 운영 500)
- **BE 배포: 필요** — be/ 런타임 다수 변경 (KIS 클라이언트·provider·토큰 영속화·env 토글). main push 시 Coolify 자동 배포
- MIN_SUPPORTED_VERSION: 현재값 빈 값(OFF) — 변경 불필요. 028은 테이블 추가만, 기존 API 계약 변경 없음 → 구버전 앱 하위호환 OK
- 모바일 스토어 제출: **불필요(생략)** — fe 변경은 웹 파비콘뿐, 네이티브 앱 사용자 가시 변경 0. fe 태그(fe-v1.1.21_26)는 finish 시 함께 부여하되 빌드/제출은 하지 않음
- **실행 순서**: `supabase db push --linked` → main push (BE 자동 배포)

## 다음 빌드를 위한 메모

- KIS provider는 dark-ship 상태 (env 게이트). prod 에서 `QUOTE_PROVIDERS`/`DAILY_PRICE_PROVIDER`/`STOCK_SEARCH_PROVIDER` 등을 `kis` 로 flip 하는 릴리즈가 실제 사용자 가시 변경이며, 그때 출시 노트로 announce 할 것 (시세 데이터 안정성/정확도 개선).
- release-notes 최상위 v* 폴더 9개가 old/ 로 미정리 상태 — 별도 정리 작업 필요 (이번 릴리즈 범위 밖).
