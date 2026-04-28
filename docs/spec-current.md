# Spec: 전략 준수 분석 그래프 통합 (좌우 stacked bar)

## 배경 / 문제

분석 탭(`/analysis`)의 "전략 준수 분석" 섹션은 현재 전략 준수(FOLLOWED)와 전략 이탈(DEVIATED) 두 항목 각각에 대해 별도의 가로 막대(`WinRateBar`)를 그린다. 두 항목은 둘이서 100%를 차지하는 상호배타적 비율이므로, 좌우로 합쳐 하나의 stacked horizontal bar로 표현하면 비교가 직관적이고 시각적 노이즈가 줄어든다.

## 목표

- 전략 준수 분석 섹션이 한 개의 가로 stacked bar(좌측: 전략 준수 비율, 우측: 전략 이탈 비율)를 표시한다.
- 막대의 좌측·우측에 각 그룹의 라벨(전략 준수 ✓ / 전략 이탈 ✗), 건수, 승률, 평균 PnL을 그대로 노출한다.
- UNKNOWN(분류 불가) 항목은 막대에서 제외하고, UNKNOWN 건수가 있을 때 패널 하단에 보조 텍스트로 작게 표시한다.
- 데이터가 없거나 판정 건수가 0이면 기존 안내 문구를 유지한다.

## 설계

### 접근 방식

`StrategyAdherencePanel`이 직접 stacked horizontal bar를 인라인으로 렌더링한다. 신규 컴포넌트나 차트 라이브러리는 도입하지 않고, 기존 `WinRateBar`처럼 `div` + Tailwind로 구현한다.

- `data`에서 `FOLLOWED`/`DEVIATED`만 추출하고, 두 항목의 `count` 합을 분모로 비율을 계산한다.
- 한 막대 안에 두 색 영역(좌: 준수 = 녹색, 우: 이탈 = 주황)을 `flex` + `style={{ width: % }}`로 채운다.
- 색상은 ADHERENCE 의미와 일관되게: 준수 = 녹색, 이탈 = 주황. `WinRateBar`의 승률 색 의미와 충돌하지 않도록 새 막대는 항상 동일 색을 사용한다.
- 막대 바로 위에 좌측 정렬된 `전략 준수 ✓ N건 (승률 X%, +○○원)` 라벨, 우측 정렬된 `N건 (승률 X%, ○○원) 전략 이탈 ✗` 라벨을 둔다 (한 줄, `flex justify-between`).
- UNKNOWN(`item.type === "UNKNOWN"`)이 데이터에 있으면 패널 하단에 `text-[11px] text-muted-foreground`로 "분류 불가 N건은 통계에서 제외" 형태의 보조 텍스트를 표시한다.
- 한쪽만 존재하는 엣지 케이스(예: FOLLOWED만, DEVIATED 0): 막대를 한 색으로 100% 채우고 반대편 라벨은 `0건`으로 표시.
- 패널 상단의 "전략 준수율 X%" / "N건 판정" 헤더 블록은 변경하지 않는다.

### 주요 변경 파일

- `app/src/components/analysis/StrategyAdherencePanel.tsx` — `data.map`으로 두 막대를 그리던 부분을 단일 stacked bar 렌더링으로 교체. UNKNOWN 보조 표시 추가. `WinRateBar` import 제거.
- `app/src/lib/constants/trading.ts` — `ADHERENCE_CONFIG`의 `FOLLOWED`/`DEVIATED`/`UNKNOWN`에 막대 fill 색용 `barClassName` 필드 추가. 기존 `label` / `className`은 유지(다른 곳에서 사용될 수 있음).

데이터 계산 로직(`computeSummary`의 `byStrategyAdherence` / `strategyAdherenceRate`)은 변경하지 않고 그대로 사용한다.

## 구현 체크리스트

- [ ] `ADHERENCE_CONFIG`에 `barClassName` 필드 추가 (FOLLOWED/DEVIATED/UNKNOWN)
- [ ] `StrategyAdherencePanel.tsx`를 수정해 FOLLOWED/DEVIATED만 추출 → 비율 계산 → 단일 stacked horizontal bar + 좌/우 라벨로 렌더링
- [ ] UNKNOWN 건수가 있을 때 패널 하단에 보조 텍스트 노출
- [ ] 한쪽만 있는 엣지 케이스 처리(FOLLOWED만, DEVIATED만, 둘 다 0)
- [ ] `WinRateBar` import 정리(사용하지 않으면 제거). 다른 컴포넌트가 여전히 사용하는지 grep 후 결정.
- [ ] 타입 체크 통과: `pnpm tsc --noEmit`
- [ ] 분석 탭 시각 확인: 둘 다 있는 케이스, FOLLOWED만, DEVIATED만, 데이터 0건

## 검증 방법

1. `pnpm tsc --noEmit` 통과
2. 개발 서버 기동 후 `/analysis` 진입 → "전략 준수 분석" 섹션 확인
   - 좌측에 녹색 영역 + "전략 준수 ✓ N건 (승률 X%)" 라벨
   - 우측에 주황 영역 + "N건 (승률 Y%) 전략 이탈 ✗" 라벨
   - UNKNOWN 보유 데이터로도 막대에는 두 영역만 보이고 하단에 분류 불가 안내가 뜨는지 확인
3. 모바일 폭(360px 정도)에서 라벨 줄바꿈/오버플로 확인 (Capacitor 모바일 우선)

## 우려사항 / 리스크

- `ADHERENCE_CONFIG`의 기존 키(`label`, `className`)는 다른 곳에서 사용될 수 있어, 새 키만 **추가**하고 기존 키는 건드리지 않는다.
- 좁은 화면에서 좌/우 라벨이 길어지면 줄바꿈 가능 → 모바일 가독성 검토 필요.
- `WinRateBar` 자체는 다른 패널(감정/전략별 성과 등)에서 쓰일 수 있으므로 파일 자체는 삭제하지 않는다.
