> 완료: 2026-04-30

# Spec: 분석탭 전략 라벨 정리 — 계획 전략 → 전략, 분류 불가 → 미입력, 안내문 단순화

## 배경 / 문제

분석탭의 전략 관련 표기가 사용자 멘탈 모델과 어긋난다.

1. **"계획 전략"이라는 표현**: Sell 거래에서는 사용자가 strategy_type을 별도로 지정하지 않고, Buy 거래의 strategy_type이 유일한 입력값이다. "계획 전략"이라고 부르면 마치 별개의 "실제 전략" 입력이 있는 것처럼 오해를 유발한다 (보유일로 추론하는 actual은 별개 자동 계산값). 단수 "전략"으로 충분하다.
2. **"분류 불가" 표현**: 전략 준수 분석에서 strategy_type을 입력하지 않은 거래를 "분류 불가"로 표시한다. 시스템 한계처럼 들리지만 실제로는 사용자가 전략을 입력해야 통계가 채워지는 상황이다. "미입력"으로 바꾸면 사용자가 입력 누락임을 즉시 인지한다.
3. **"두 금액 합이 총 실현손익과 다를 수 있습니다" 안내문**: amber 박스에 같이 표시되는 부가 설명이 길고, 핵심 정보(미입력 건수·PnL이 통계에서 제외)와 분리되어 인지 부담을 늘린다.

## 목표

1. 분석탭/거래상세에서 "계획 전략"이라는 표기가 모두 "전략"으로 단수화된다.
2. 전략 준수 분석의 amber 안내문 + 빈 상태 메시지에서 "분류 불가"가 "미입력"으로 표시되어, 전략을 입력해야 통계가 정상 표시된다는 신호가 된다.
3. amber 안내문에서 "— 두 금액 합이 총 실현손익과 다를 수 있습니다." 부분이 제거되어 안내문이 단순해진다 (박스 자체와 건수·PnL·통계 제외 안내는 유지).

## 설계

### 접근 방식

순수 FE 텍스트 변경. 백엔드 데이터·계산 로직, 색상/박스 스타일은 그대로 유지.

- "계획 전략" → "전략": 3개 위치 (분석 대시보드 섹션 제목, 준수율 부제, 거래상세 라벨).
- "분류 불가" → "미입력": ADHERENCE_CONFIG.UNKNOWN.label + 빈 상태 메시지 + amber 안내문 본문 (총 3곳).
  - "미입력" 채택 이유: 코드베이스의 다른 미입력 버킷 라벨(EMOTION_LABELS, REASONING_TAG_LABELS)과 일관 — 모두 UNTAGGED 키에 "미입력" 라벨을 사용. 신규 어휘 도입을 피한다.
- amber 안내문에서 "— 두 금액 합이 총 실현손익과 다를 수 있습니다." 부분만 제거. amber 박스·아이콘·"미입력 N건 (PnL)은 통계에서 제외" 본문은 유지.

### 주요 변경 파일

- `app/src/components/analysis/AnalysisDashboard.tsx` — SectionCard 제목 "계획 전략별 성과" → "전략별 성과" (1곳).
- `app/src/components/analysis/StrategyAdherencePanel.tsx` — 부제 "계획 전략과 실제 보유일 기준" → "전략과 실제 보유일 기준", 빈 상태 메시지 "분류 불가" → "미입력", amber 안내문 "분류 불가" → "미입력" + "— 두 금액 합이…" 제거 (3곳).
- `app/src/components/records/TradeStrategyResultSection.tsx` — InfoRow label "계획 전략" → "전략" (1곳). "실제 전략"은 자동 계산값임을 드러내는 별개 필드이므로 유지.
- `app/src/lib/constants/trading.ts` — ADHERENCE_CONFIG.UNKNOWN.label "분류 불가" → "미입력" (1곳). 현재 직접 렌더링되는 곳은 거의 없으나 향후 사용 시 일관성 유지.

### 안내문 변경 전후

```
변경 전: "분류 불가 N건 (₩-1,234)은 통계에서 제외 — 두 금액 합이 총 실현손익과 다를 수 있습니다."
변경 후: "미입력 N건 (₩-1,234)은 통계에서 제외"
```

## 구현 체크리스트

- [x] `app/src/components/analysis/AnalysisDashboard.tsx` SectionCard 제목 수정
- [x] `app/src/components/analysis/StrategyAdherencePanel.tsx` 3곳 텍스트 수정 (부제 + 빈 상태 + amber 안내문)
- [x] `app/src/components/records/TradeStrategyResultSection.tsx` "계획 전략" 라벨 수정
- [x] `app/src/lib/constants/trading.ts` ADHERENCE_CONFIG.UNKNOWN.label 수정
- [x] BE 주석 일관성 — `api/src/invest_note_api/domain/analysis/aggregate.py:94` 주석 "계획 전략" → "전략"
- [x] 잔여 사용처 재검색 — `grep -rn "계획 전략\|분류 불가\|두 금액" app/ api/`로 누락 없는지 확인 (spec-history 제외)
- [x] 타입 체크 통과 (`pnpm tsc`)
- [ ] 분석탭 시각 확인 — 전략 준수 분석 박스에서 "미입력 N건 … 통계에서 제외" 한 줄로 표시되는지 (테스트 데이터 또는 dev 서버에서 확인)

## 우려사항 / 리스크

- "전략" 단독 라벨은 "실제 전략"(보유일 추론값)과 한 화면에 함께 표시될 때 비대칭으로 보일 수 있음 (`TradeStrategyResultSection`). 사용자 요청은 "계획 전략" 단수 변경이므로 "실제 전략"은 그대로 유지 — 자동 계산값임을 라벨에서 명확히 구분.
- ADHERENCE_CONFIG.UNKNOWN.label은 현재 panel/거래상세에서 직접 렌더링되지 않지만 (`adherence !== "UNKNOWN"` 가드), 라벨 일관성을 위해 함께 변경.

## 검증

1. `pnpm -C app exec tsc --noEmit` 통과.
2. 분석탭 진입 → "전략별 성과" 섹션 제목, "전략 준수 분석" 박스의 "전략과 실제 보유일 기준" 부제, 미입력 거래가 있을 때 amber 박스의 "미입력 N건 (PnL)은 통계에서 제외" 한 줄 표시 확인.
3. 거래상세(매도) 진입 → "전략 결과" 섹션의 InfoRow가 "전략" / "실제 전략" 페어로 표시되는지 확인.
