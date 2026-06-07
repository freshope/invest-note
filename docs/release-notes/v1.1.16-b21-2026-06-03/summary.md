# 출시 노트 요약 — v1.1.16_21

> 작성일: 2026-06-03
> 비교 기준: v1.1.15_20 (2026-05-27)
> 대상 빌드: v1.1.16_21 (준비 중 — 버전 4곳 bump 가 working tree 에만 반영, 아직 미커밋. 본 노트는 1.1.16_21 기준 초안)

## Git 로그 (v1.1.15_20..HEAD, --no-merges)

| 해시 | 날짜 | 메시지 |
|------|------|--------|
| 23be7da | 2026-06-03 | docs: spec-current → issue-history 이동 (종목 검색 provider 토글) |
| 70b68fb | 2026-06-03 | docs: 종목 검색 Naver 임시 복귀 결정 + backlog |
| f8e5584 | 2026-06-03 | feat(be): 종목 검색 provider env 토글 (Naver ↔ DB) |
| 33bc9c0 | 2026-06-03 | fix(fe): 안드로이드 상단 safe-area 미충전 수정 — 네이티브 edge-to-edge + WindowInsets 주입 |
| dceb2d5 | 2026-06-02 | docs: spec-current → issue-history 이동 (NPS reconcile) |
| fdedf62 | 2026-06-02 | docs: NPS 우선주 보강 + 미매칭 reconcile 결정·백로그 |
| d9645f0 | 2026-06-02 | feat(be): NPS 미매칭 과거사명 reconcile — alias 보강 |
| f28d73c | 2026-06-02 | feat(be): NPS 미매칭 해소 — 우선주 보강 + (주) 접두 정제 |
| d4ed102 | 2026-06-02 | docs: spec-current → issue-history 이동 (NPS seed) |
| 1a42d54 | 2026-06-02 | docs: 국민연금 odcloud 자동 fetch 정정 + 라이브 검증 |
| 617eff3 | 2026-06-02 | fix(be): stocks seed getItemInfo basDt 누락 + 게이트웨이 재시도 |
| cfc7a4a | 2026-06-02 | feat(be): 국민연금(NPS) 보유종목 적재 odcloud API 자동화 |
| 7942b88 | 2026-06-02 | chore(be): poetry.lock 재생성 |
| a88eaac | 2026-06-02 | fix(be): 종목 적재 리뷰 지적 4건 수정 (오상폐·단일 item 크래시·Naver 무한질의·stale rank) |
| 6bf2d47 | 2026-06-01 | docs: spec-current → issue-history 이동 (data.go.kr marcap) |
| 90db955 | 2026-06-01 | docs: 종목 적재 data.go.kr 단일화 결정 + backlog |
| 4e84162 | 2026-06-01 | feat(be): 종목 적재 data.go.kr 단일화 + 시가총액 + 웹 라우터 |
| 36a3b27 | 2026-05-31 | fix(be): seed_stocks 멀티 인스턴스 advisory lock 가드 |
| 55bb63c | 2026-05-30 | fix(be): naver_search 타임아웃 트레이스백 한 줄 로그 축소 |
| 001ecd8 | 2026-05-30 | docs: spec-current → issue-history 이동 (stock master data) |
| bffc39d | 2026-05-30 | feat(be): 종목 검색 자체 데이터 운영 (stocks 마스터 재도입) |
| fb6384f | 2026-05-29 | fix(be): 일괄 import 거래의 exchange 빈 값 누락 수정 |
| cfe1fc1 | 2026-05-27 | fix(be): App Store URL에 누락된 /app/ 경로 세그먼트 추가 |

## 동기간 issue-history 항목

- 2026-05-30-stock-master-data.md — 종목 검색용 자체 stocks 마스터 데이터 재도입
- 2026-06-01-stocks-data-go-kr-marcap.md — 종목 적재를 data.go.kr 단일 소스로 통합 + 시가총액
- 2026-06-02-nps-holding-seed.md — 국민연금 보유종목 odcloud API 자동 적재
- 2026-06-02-nps-unmatched-reconcile.md — NPS 미매칭 과거사명 reconcile(alias 보강)
- 2026-06-03-stock-search-provider-toggle.md — 종목 검색 provider 토글(Naver ↔ DB), 기본값 Naver 임시 복귀

## 분류표

| 라벨 | 항목 | 출시 노트 반영 |
|------|------|----------------|
| FIX | 안드로이드 상단 safe-area 미충전(상태바·카메라 영역 배경 미충전) 수정 (33bc9c0) | ✓ |
| FIX | 파일 일괄 import 거래의 거래소(exchange) 빈 값 저장 버그 수정 (fb6384f) | ✓ |
| INTERNAL | 종목 검색 자체 stocks 마스터 재도입 (bffc39d) | ✗ |
| INTERNAL | 종목 적재 data.go.kr 단일화 + 시가총액 (4e84162) | ✗ |
| INTERNAL | NPS 보유종목 odcloud 자동 적재 (cfc7a4a) | ✗ |
| INTERNAL | NPS 미매칭 reconcile / 우선주 보강 (d9645f0, f28d73c) | ✗ |
| INTERNAL | 종목 검색 provider env 토글 — net 사용자 변화 없음(Naver 유지) (f8e5584) | ✗ |
| INTERNAL | seed 안정화: advisory lock·게이트웨이 재시도·basDt·리뷰 4건·로그 축소 (36a3b27, 617eff3, a88eaac, 55bb63c) | ✗ |
| INTERNAL | App Store URL `/app/` 경로 — `.env.example` 만 수정, 빌드 무영향 (cfe1fc1) | ✗ |
| INTERNAL | poetry.lock 재생성 (7942b88) | ✗ |

## 검증 결과

- app-store-ko.md: 검증 명령으로 측정 (아래 wc -m)
- play-store-ko.md: 검증 명령으로 측정 (≤ 500자 한도)
- 내부 식별자/커밋 해시/PR 번호 본문 노출 없음
- INTERNAL 항목 본문 미혼입
- 대상 버전(1.1.16 / 21) 폴더명·summary·노트 본문 일치
- NEW 0 · IMPROVE 0 · FIX 2 · INTERNAL 다수

## 다음 빌드를 위한 메모

- 버전 bump(1.1.16/21) 가 working tree 에만 있고 미커밋 상태. release 브랜치에서 bump 커밋 후 본 폴더 그대로 포함 권장.
- 종목 검색은 이번 빌드에서 Naver 자동완성으로 임시 복귀. data.go.kr seed 모니터링 종료 후 `STOCK_SEARCH_PROVIDER=db` 로 전환 예정 — 그 전환은 사용자 가시(검색 결과 출처 변경) 가능성이 있으므로 다음 빌드 노트에서 재평가.
- App Store URL 수정은 `.env.example` 만 반영됨. 운영 env(STORE_URL_IOS) 실제 값 점검 필요 시 별도 확인.
