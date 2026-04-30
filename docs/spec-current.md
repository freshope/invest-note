# Spec: 분석 탭 — 미입력 항목 정렬·시각화 + 승률/비중 혼동 방지 + 전략 준수 분류 불가 PnL 표시

## 배경 / 문제

이전 spec(2026-04-30)에서 분석 탭 합계 일치 작업을 마쳤지만, 사용자 검증 과정에서 후속 UX 이슈 3건이 발견되었다.

1. **미입력 항목이 다른 항목과 동일하게 표시·정렬되어 시선이 분산됨.** 미입력은 "참고용 잔여 버킷"인데 건수가 많으면 맨 위에 와서 본 데이터처럼 보인다.
2. **WinRateBar의 진행 막대 + "60%"를 사용자들이 "비중(Share)"으로 착각.** 항목 % 합이 100%가 아니어서 데이터 오류로 의심한다 — 실제로는 항목별 독립 승률이라 합산 의미가 없다.
3. **StrategyAdherencePanel 화면에는 FOLLOWED/DEVIATED 금액만 표시**되고 UNKNOWN(분류 불가) PnL은 숨겨져 있어, 두 금액 합이 총 실현손익과 다르다 — 백엔드 byStrategyAdherence 합계는 일치하지만 화면에 다 안 나오는 것이 원인.

## 목표

1. 성과 섹션(감정별/전략별/근거 태그별)에서 미입력/UNKNOWN 항목이 항상 **마지막** 위치에 오고, 막대 색상·텍스트 톤이 회색(muted)으로 다른 항목과 시각적으로 구분된다.
2. WinRateBar의 % 옆에 "승률" 라벨이 명시되어 비중과의 혼동이 사라진다.
3. StrategyAdherencePanel에서 분류 불가 거래가 있을 때 안내문에 **건수 + PnL 금액**이 같이 표시되고, amber 박스로 강조되어 사용자가 "FOLLOWED + DEVIATED ≠ 총 실현손익"의 이유를 즉시 이해한다.

백엔드 집계 로직은 이미 미입력 버킷을 포함하고 합계가 일치하므로 **FE 전용 변경**이다.

## 설계

### 이슈 1: 미입력 마지막 정렬 + 시각적 차별화

- 백엔드는 `count desc` 정렬로 응답 → FE 컴포넌트에서 미입력만 분리해 마지막으로 push.
- 미입력 키 식별:
  - 감정: `EMOTION_UNTAGGED = "UNTAGGED"` ([trade_types.py](api/src/invest_note_api/domain/trade_types.py))
  - 태그: `TAG_UNTAGGED = "UNTAGGED"`
  - 전략: `STRATEGY_UNKNOWN = "UNKNOWN"` (사용자 선택 옵션 "없음"과 동일)
- FE에서는 `app/src/lib/constants/trading.ts`의 `UNTAGGED_KEY = "UNTAGGED"`를 export하고 컴포넌트에서 비교에 사용. 전략은 STRATEGIES 배열의 `UNKNOWN`을 그대로 사용.
- 시각적 차별화: 미입력 row에서 `WinRateBar`의 막대 + 텍스트를 회색으로 (새 `muted` prop). 라벨/PnL 텍스트도 muted 톤.

### 이슈 2: 승률 vs 비중 혼동 방지

- `WinRateBar` 우측 % 표시를 `60%` → `승률 60%`로 변경 (라벨 추가).
- 우측 영역 폭(`w-8`)을 라벨 포함 길이로 확장(`w-16`).
- `muted` prop이 true이면 색상 회색 + 텍스트 muted-foreground.

### 이슈 3: 전략 준수 분석 — 분류 불가 안내 강화

`StrategyAdherencePanel.tsx`의 기존 안내문 (line 110-113):
```tsx
{judged > 0 && unknownCount > 0 && (
  <p className="text-[11px] text-muted-foreground">
    분류 불가 {unknownCount}건은 통계에서 제외
  </p>
)}
```

다음으로 강화:
- `byStrategyAdherence`에서 `UNKNOWN` row의 `sumPnL`을 함께 표시
- amber 박스(`ReasoningBreakdown.tsx:20-29` 패턴 재사용) + `AlertTriangle` 아이콘
- 문구: `분류 불가 N건 (PnL ±X원)은 통계에서 제외 — 두 금액 합이 총 실현손익과 다를 수 있습니다`

`unknown.sumPnL`은 이미 백엔드 응답에 포함되어 있으므로 추가 API 변경 불필요.

### 주요 변경 파일

- `app/src/lib/constants/trading.ts` — `UNTAGGED_KEY` export
- `app/src/components/analysis/WinRateBar.tsx` — `muted` prop, "승률" 라벨, 폭 조정
- `app/src/components/analysis/EmotionBreakdown.tsx` — 미입력 마지막 정렬, muted 적용
- `app/src/components/analysis/StrategyBreakdown.tsx` — UNKNOWN("없음") 마지막 정렬, muted 적용
- `app/src/components/analysis/ReasoningBreakdown.tsx` — 미입력 마지막 정렬, muted 적용
- `app/src/components/analysis/StrategyAdherencePanel.tsx` — 분류 불가 안내문 강화 (PnL 금액, amber 박스)

## 구현 체크리스트

- [x] `trading.ts` `UNTAGGED_KEY` + `STRATEGY_UNKNOWN_KEY` export
- [x] `WinRateBar.tsx`에 `muted` prop, "승률" 라벨, w-16 폭 적용
- [x] `PnLLine.tsx`에 `muted` prop 추가 (muted 항목 PnL 색상 통일)
- [x] `EmotionBreakdown.tsx`: 미입력 row 마지막 + WinRateBar muted + 라벨/PnL muted 톤
- [x] `StrategyBreakdown.tsx`: UNKNOWN row 마지막 + 동일 처리 (라벨은 기존 "없음" 유지)
- [x] `ReasoningBreakdown.tsx`: 미입력 row 마지막 + 동일 처리
- [x] `StrategyAdherencePanel.tsx`: 분류 불가 안내문 → amber 박스 + `AlertTriangle` + `formatPnL(unknownPnL)` 포함
- [x] 타입 체크 통과 (`pnpm tsc`)
- [x] 프론트엔드 테스트 통과 (`pnpm -C app test` — 96/96)
- [ ] 수동 검증

## 검증

1. **타입 체크**: `pnpm tsc --noEmit` 통과
2. **수동 검증** (분석 탭):
   - 감정별 성과: 미입력 항목이 항상 마지막, 회색 막대로 표시
   - 계획 전략별 성과: "없음(UNKNOWN)" 항목이 마지막, 회색 막대
   - 근거 태그별 성과: 미입력 마지막, 회색
   - WinRateBar 우측: "승률 60%" 형태로 표시되어 승률임이 명확
   - 전략 준수 분석: 분류 불가 거래가 있는 계정에서 amber 박스 + "분류 불가 N건 (±X원)은 통계에서 제외" 안내
3. **기존 동작 유지**: byStrategy/byEmotion/byTag 합계 등식, 다중 태그 안내문, behavior/diversification 패널 등은 변경 없음

## 우려사항 / 리스크

- WinRateBar 폭 변경(`w-8 → w-16`)으로 좁은 화면(360px 이하)에서 좌측 막대 영역이 좁아질 수 있음 → flex-1로 흡수되므로 큰 영향 없음. 시각적 점검 필요.
- 전략 준수 amber 박스가 데이터 입력 품질이 낮은 사용자에게 자주 노출됨 — `ReasoningBreakdown` amber 박스와 톤이 일관되어 있어 OK.
- 미입력 정렬 로직을 컴포넌트 3곳에서 반복 — 중복은 작아서 (3줄) 공통 유틸로 빼지 않음.
