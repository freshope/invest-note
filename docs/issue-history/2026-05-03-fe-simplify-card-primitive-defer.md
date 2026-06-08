# Spec: FE simplify — Card primitive 추출 미진행 결정

> 완료: 2026-05-03

## 배경 / 문제

`docs/backlog.md` 의 "FE simplify · 컴포넌트 추출" 섹션에 남아 있던 `Card` primitive 항목 (30+ 곳) 처리 여부 평가. 탐색 결과 추상화 가치가 마이그레이션 비용을 정당화하지 못해 미진행 결정.

탐색 근거:

- 셸 마크업이 단 2 개 유틸 클래스 (`rounded-2xl bg-muted/60`)
- 사용처 32 개 / 18 파일이지만 시맨틱 콘텐츠 없는 순수 시각 셸
- padding 변종이 백로그 메모 (sm/md/lg) 보다 다양 (실제 7 가지 + interaction/overflow/element 혼합)
- Round 2~7 추출은 모두 시맨틱 콘텐츠가 있어 prop API 가 자연스러웠음 — Card 셸은 escape-hatch className 만연 위험

## 목표

1. `docs/decisions.md` 상단에 미진행 결정 항목 추가 (재검토 트리거 포함)
2. `docs/backlog.md` 의 Card primitive 줄 종결 마킹 + 인용 문단 갱신
3. 향후 동일 항목 재제기 시 본 결정을 참조해 차단

## 설계

### 결정 요지

- `<Card>` 컴포넌트도 CSS 유틸 (`.card-shell`) 도 도입하지 않고 현 인라인 클래스 유지
- backlog 항목 `[x]` 로 종결, decisions.md 인용

### 주요 변경 파일

- `docs/decisions.md` — 상단에 `## 2026-05-03 | FE simplify — Card primitive 추출 미진행` 신설 (맥락/결정/이유/트레이드오프 4 섹션, 기존 `aggregate.py 미진행 결정` 항목 형식 답습)
- `docs/backlog.md` — `Card primitive 30+ 곳` 줄 `[x]` + decisions.md 인용 부기, 인용 문단 (Round 2~7 처리 메모) 갱신

## 구현 체크리스트

- [x] `docs/decisions.md` 상단에 미진행 결정 항목 추가
- [x] `docs/backlog.md` Card primitive 줄 `[x]` 마킹 + decisions.md 인용
- [x] `docs/backlog.md` 인용 문단 (Round 2~7) 갱신
- [x] (커밋) `docs: decisions — Card primitive 추출 미진행 결정 + backlog 종결`

## 우려사항 / 리스크

- 재검토 트리거 조건이 모호하면 동일 항목이 다시 backlog 에 올라올 수 있음 — decisions.md 트레이드오프 섹션에 명시 (셸 클래스 변경 PR 6 개월 2 회 이상 / 인터랙티브 카드 5 곳 이상으로 증가)
- 코드 변경이 없어 시각/타입 회귀 위험 무
