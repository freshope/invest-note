# 출시 노트 요약 — v1.1.15_20

> 작성일: 2026-05-27
> 비교 기준: v1.1.14_19 (2026-05-27)
> 대상 빌드: v1.1.15_20 (준비 중 — 버전 4곳 bump 완료, 미커밋 상태. 본 노트는 v1.1.15_20 기준 초안)

## Git 로그 (v1.1.14_19..HEAD, --no-merges)

| 해시 | 날짜 | 메시지 |
|------|------|--------|
| adbc1ee | 2026-05-27 | feat: 포트폴리오 요약 시세 조회를 요청 경로에서 분리 (옵션 B) |
| dd586f3 | 2026-05-27 | docs: feature 완료 후 문서 업데이트 (시세 요청경로 분리) |
| 724a44f | 2026-05-27 | docs: spec-current → spec-history/2026-05-27-portfolio-summary-lite-quotes.md 이동 |

> 작업 트리에 버전 4곳 bump(1.1.14→1.1.15, build 19→20)가 미커밋으로 존재. 모두 INTERNAL이라 본문에 영향 없음.

## 동기간 spec-history 항목

- `2026-05-27-portfolio-summary-lite-quotes.md` — `/portfolio/summary`(홈 단일 데이터 소스)에서 외부 시세 fetch를 응답 임계 경로에서 분리. BE는 `withQuotes=false`로 시세 없이 즉시 응답하고, FE가 `/stocks/quote`를 별도·병렬 호출해 현재가·평가손익·총자산을 overlay. 구버전 앱은 `withQuotes` 기본 true로 하위호환 유지.

## 분류표

| 라벨 | 항목 | 출시 노트 반영 |
|------|------|--------------|
| IMPROVE | 홈 화면이 시세 fetch를 기다리지 않고 핵심 수치(보유종목·원가·실현손익·현금) 먼저 표시, 시세는 도착하는 대로 overlay | ✓ |
| IMPROVE | 시세 조회를 응답 임계 경로에서 분리 → 외부 시세 서버가 느려도 홈 진입 미지연 | ✓ |
| INTERNAL | 버전 bump 4곳 (1.1.15 / build 20) | ✗ |
| INTERNAL | docs 업데이트 + spec-history 이동 | ✗ |
| INTERNAL | 버전 skew 가드 `snapshot.holdings ?? []` (구 BE 응답 크래시 방지) — 미출시 코드의 사전 방어라 사용자 가시 증상 없음 | ✗ |

## 검증 결과

- app-store-ko.md: 202자 / 4000자 한도 ✓
- play-store-ko.md: 156자 / 500자 한도 ✓
- 내부 식별자/커밋 해시/PR 번호 노출 없음 ✓
- INTERNAL 항목 본문 미혼입 ✓
- 대상 버전(1.1.15 / 20) 폴더명·summary·양쪽 노트 일치 ✓
- 과장 방지: spec의 "병목 미확정" 리스크 고려, "절대 속도"가 아닌 아키텍처상 보장되는 동작(핵심 수치 선표시 + 임계 경로 분리)을 중심으로 표현
- 톤: 직전 노트(v1.1.14-b19) 패턴 따름 — 헤드라인 한 줄 + "개선된 점" 섹션 + "소중한 의견을 보내주세요. 더 나은 앱으로 보답하겠습니다." 마무리

## 다음 빌드를 위한 메모

- **사후 검증 필요**: spec Step 0(병목 측정) 생략하고 진행. 배포 후 홈 진입 체감 개선이 없으면 DB·콜드부트·네트워크 RTT 등 원인 재조사 (spec 리스크 항목).
- **배포 순서 BE→FE 필수**: 계좌별 탭 `totalValue` overlay가 BE의 `holdings` additive 필드에 의존. 앱+Coolify 동시 릴리즈면 무관하나, 구 BE에 신 FE가 붙으면 `holdings` 부재 가드는 있으나 overlay 정확도 영향.
- **후속 별도 spec**: 분석 대시보드(`/analysis/dashboard`)도 동일 패턴 적용 가능 — concentration cost_basis fallback 차이로 별도 작업 필요. 이번 빌드는 홈 `/portfolio/summary`만.
- dead code `fe/src/lib/quotes.ts`(네이버 직접 호출, SSR 유물) 제거는 미해결 — 범위 외로 남김.
