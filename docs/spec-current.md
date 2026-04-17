# 현재 작업 사양: 분석 탭 구현

## 목표

`/analysis` 탭에 **성과 + 투자 성향 + 방향성 제안** 3축을 모두 다루는 화면을 구현해 MVP를 완성한다.
현재 해당 경로는 스켈레톤(빈 페이지) 상태다.

확정 범위:
- Phase A(성과) + B(성향) + C(방향성) 모두 1차 릴리즈에 포함
- 기간 필터(1M/3M/6M/YTD/전체) 포함
- v3 AI 자연어 코멘트는 backlog로 유지 (이번 범위 제외)

---

## 정보 구조 (위 → 아래)

| # | 섹션 | Phase |
|---|------|-------|
| 0 | 기간 필터 탭 (1M/3M/6M/YTD/전체) | A |
| 1 | 핵심 성과 4-카드 (총거래/매도/승률/총 실현손익) | A |
| 2 | 오늘의 인사이트 카드 (최대 3장, severity 기반) | A(seed) → C(본격) |
| 3 | 투자 성향 프로필 (레이더 차트, 5차원) | B |
| 4 | 감정 × 성과 | A |
| 5 | 전략 × 성과 | A |
| 6 | 근거 태그 × 성과 + 근거 품질 경고 | A |
| 7 | 분산 / 집중도 (HHI, 국가·자산군·상위 3종목) | B |
| 8 | 회고 품질 (reflection/improvement 작성률) | B |
| 9 | 방향성 제안 카드 (룰 매치된 것만) | C |
| 10 | 드릴다운 (보유기간·포지션사이즈 히스토그램) | B |

---

## 데이터 계산 규칙

### 승률 (winRate)
- 분모: `trade_type = 'SELL' AND result IS NOT NULL`
- 분자: 분모 중 `result = 'SUCCESS'`
- `resultInputRate`(입력률) 병기로 신뢰도 표기

### 실현 손익 (profit_loss) fallback
- 수동 입력값이 있으면 그대로 사용
- `profit_loss IS NULL`이면 fallback 계산:
  `(매도가 − WAC) × 매도수량 − commission − tax`
- WAC는 해당 종목의 매수 기록으로 `src/lib/portfolio.ts`의 `buildPositions` 로직 재사용

### 보유 기간 (holding days)
- FIFO 기준 종목별 타임라인 시뮬레이션
- 매도 건마다 "매칭된 매수 시점"의 가중 평균 경과일(KST 기준) 산출
- 신규 유틸 `src/lib/analysis/holding-period.ts`

### 태그 승률 귀속 (reasoning_tags는 BUY에만 존재)
- SELL의 태그 승률은 "해당 종목 **최근 BUY**의 `reasoning_tags`"로 귀속
- 태그 없는 BUY는 `missingTagRate`에 카운트, 승률 집계에서는 제외

### 기간 필터
- `traded_at` 기준 KST (`src/lib/trade-utils.ts` `toKST` 재사용)
- 파라미터: `?period=1m|3m|6m|ytd|all`

---

## 투자 성향 5차원 (섹션 3)

각 차원 0~100 점수 + 3단 라벨. 입력률 낮은 차원은 "입력률 N%" 보조 텍스트.

| 차원 | 산식 | 극성 라벨 |
|------|------|-----------|
| 거래 템포 (tempo) | 평균 보유일 & 전략 분포 가중 | 스캘퍼 ↔ 스윙 ↔ 장기 |
| 분산도 (diversification) | `(1 − HHI) × 100`, HHI = Σ(평가금액 비중²) | 집중형 ↔ 적정 ↔ 분산형 |
| 감정 안정성 (emotionStability) | `(1 − (FOMO+IMPULSIVE+ANXIOUS)/total_emotion_tagged) × 100` | 충동형 ↔ 균형 ↔ 차분형 |
| 근거 품질 (reasoningQuality) | `(1 − (FEELING 포함 BUY + 태그 0개 BUY) / BUY) × 100` | 감각형 ↔ 혼합 ↔ 분석형 |
| 복기 습관 (reviewHabit) | `SELL 중 reflection_note 작성 비율 × 100` | 무복기 ↔ 기본 ↔ 복기형 |

---

## 방향성 제안 룰 (섹션 9)

룰은 `src/lib/analysis/rules.ts`에 데이터 구조로 정의. 서버에서 매치된 룰만 반환.

| ID | 트리거 | 메시지 | severity |
|----|--------|--------|----------|
| `emotion_fomo_low_winrate` | FOMO 거래 ≥ 5건 & winRate < 40% | FOMO 상태 매매 승률이 낮아요. 해당 감정에서는 관망을 권장합니다 | warn |
| `emotion_calm_high_winrate` | CALM 승률 상위 & count ≥ 5 | 평온할 때 성과가 가장 좋아요. 체크리스트 기반 매매를 유지하세요 | info |
| `concentration_high` | HHI > 0.5 OR top1 비중 > 40% | 한 종목 비중이 높습니다. 분산을 고려해보세요 | warn |
| `feeling_heavy` | BUY 중 FEELING 태그 ≥ 40% | '감'으로 진입하는 비율이 높아요. 기술/펀더멘털 근거 1개 추가를 권장합니다 | warn |
| `no_reflection` | SELL 회고 작성률 < 30% | 매도 후 회고가 드물어요. 최근 매도 3건 회고를 남겨보세요 | info |
| `holding_mismatch` | SCALPING 선언 vs 평균 보유 > 7일 | 스캘핑으로 분류했지만 실제 보유가 깁니다. 전략 태그를 재검토하세요 | info |
| `losing_strategy` | 특정 전략 승률 < 30% & count ≥ 5 | {전략}의 평균 승률이 낮습니다. 해당 전략 포지션 축소를 검토하세요 | critical |
| `tag_missing_rate_high` | BUY 태그 0개 비율 > 30% | 근거 태그 누락이 많습니다. 매수 시 최소 1개 태그 입력을 권장합니다 | info |

---

## API 엔드포인트

Phase별 독립 릴리즈를 위해 3개로 분리. 클라이언트에서 `Promise.all` 병렬 호출.
공통 파라미터: `?period=1m|3m|6m|ytd|all`

### `GET /api/analysis/summary` (Phase A)

```ts
{
  period: '1m' | '3m' | '6m' | 'ytd' | 'all',
  totalTrades: number,
  sellTrades: number,
  winRate: number,                // 0~100, result 입력된 SELL 기준
  totalProfitLoss: number,        // fallback 계산 포함
  byStrategy: { type: string; count: number; winRate: number; avgPnL: number; avgHoldingDays: number }[],
  byEmotion:  { type: string; count: number; winRate: number; avgPnL: number }[],
  byTag:      { tag: string;  count: number; winRate: number; avgPnL: number }[],
  missingTagRate: number,         // BUY 중 태그 0개 비율
  feelingRate: number,            // BUY 중 FEELING 포함 비율
  reflectionRate: number,         // SELL 중 reflection_note 작성률
  resultInputRate: number         // SELL 중 result 입력률 (winRate 신뢰도)
}
```

### `GET /api/analysis/behavior` (Phase B)

```ts
{
  period: string,
  profile: {
    tempo: number,                // 0~100
    diversification: number,
    emotionStability: number,
    reasoningQuality: number,
    reviewHabit: number
  },
  holdingPeriodDist: { bucket: '1d'|'1w'|'1m'|'3m'|'6m'|'1y+'; count: number }[],
  positionSizeDist:  { bucket: string; count: number }[],
  concentration: {
    hhi: number,
    top3: { asset: string; weight: number }[],
    byCountry: { code: 'KR'|'US'|'OTHER'; weight: number }[],
    byMarket:  { type: 'STOCK'|'CRYPTO'|'ETC'; weight: number }[]
  }
}
```

### `GET /api/analysis/suggestions` (Phase C)

```ts
{
  period: string,
  suggestions: {
    id: string,
    severity: 'info' | 'warn' | 'critical',
    title: string,
    body: string,
    metric?: { label: string; value: string },
    linkSection?: 'strategy' | 'emotion' | 'tag' | 'concentration' | 'review'
  }[]
}
```

---

## 파일 구조 (신규/수정)

```
src/app/api/analysis/
  summary/route.ts              [신규, A]
  behavior/route.ts             [신규, B]
  suggestions/route.ts          [신규, C]

src/lib/analysis/               [신규 폴더 — portfolio.ts와 격리]
  aggregate.ts                  byStrategy/byEmotion/byTag 집계
  realized-pnl.ts               profit_loss fallback (WAC × 수량 − 수수료)
  holding-period.ts             FIFO 기반 종목별 보유일
  concentration.ts              HHI / top-k / 국가·자산군 비중
  profile.ts                    5차원 점수 산출
  rules.ts                      제안 룰 정의 + 평가기
  period.ts                     period → (from, to) KST 변환

src/components/analysis/        [신규 폴더]
  AnalysisDashboard.tsx         최상위 fetch + 섹션 조합
  PeriodFilterTabs.tsx
  SummaryCards.tsx
  InsightHighlights.tsx         섹션 2/9 공용 severity 카드
  EmotionBreakdown.tsx
  StrategyBreakdown.tsx
  ReasoningBreakdown.tsx
  BehaviorRadar.tsx             recharts RadarChart
  DiversificationPanel.tsx
  ReviewQualityPanel.tsx
  SuggestionList.tsx
  DrilldownHistograms.tsx
  AnalysisEmptyState.tsx

src/components/base/
  DonutChart.tsx                [선택] AllocationTabs에서 Donut 추출

src/app/(app)/analysis/page.tsx placeholder 제거 → <AnalysisDashboard />
```

### 재사용 (중복 구현 금지)

- `src/lib/portfolio.ts` `buildPositions / mergeQuotes` → 분산/평가금액
- `src/lib/trade-utils.ts` `toKST` → 기간 필터
- `src/lib/format.ts` `fmt / fmtCompact`
- `src/components/records/constants.ts` STRATEGIES/EMOTIONS/REASONING_TAGS 라벨
- `src/components/home/HomeDashboard.tsx` 로딩/에러 패턴
- `src/components/home/AllocationTabs.tsx` CHART_COLORS + Donut 구현
- `src/components/stocks/StockDetail.tsx` 3-grid 카드 마크업
- `src/lib/api-server/{auth,errors,validators}.ts` 라우트 공통 헬퍼

---

## 빈 상태 / 신뢰도 처리

- 거래 0건: `AnalysisEmptyState` — "첫 거래를 기록하면 성향 분석이 생깁니다"
- SELL 0건: 승률/손익 카드 dimmed, 성향 차원은 일부만 표시
- 필드 입력률 < 50%인 차원/섹션: 상단에 "입력률 N% — 분석 정확도에 영향" 1줄
- 룰 매치 0개: "아직 특이 패턴이 감지되지 않았어요" placeholder

---

## 구현 순서 (Step)

1. `src/lib/analysis/period.ts` + `realized-pnl.ts` + `aggregate.ts` 기본 유틸
2. `GET /api/analysis/summary` Route 구현 + 검증
3. `AnalysisDashboard`, `PeriodFilterTabs`, `SummaryCards`, 감정/전략/태그 Breakdown (Phase A 완성)
4. `holding-period.ts` + `concentration.ts` + `profile.ts`
5. `GET /api/analysis/behavior` Route + `BehaviorRadar` + `DiversificationPanel` + `ReviewQualityPanel` + `DrilldownHistograms` (Phase B 완성)
6. `rules.ts` + `GET /api/analysis/suggestions` Route + `SuggestionList` + `InsightHighlights` 본격화 (Phase C 완성)
7. 빈 상태/신뢰도/에러 UX 마감

---

## 완료 기준

### Phase A
- [ ] `/analysis` 페이지에 핵심 성과 4-카드 표시
- [ ] 기간 필터 탭 (1M/3M/6M/YTD/전체) 동작
- [ ] 감정별 / 전략별 / 태그별 성과 시각화
- [ ] FEELING 비율 경고 / 태그 누락률 표시
- [ ] `/api/analysis/summary` Route 구현 (fallback 손익 계산 포함)
- [ ] `resultInputRate` 신뢰도 문구 노출

### Phase B
- [ ] 투자 성향 5차원 레이더 차트 표시
- [ ] HHI 기반 분산 패널 + 상위 3종목 / 국가 / 자산군 비중
- [ ] 회고 품질 패널 (reflection/improvement 작성률)
- [ ] 보유기간 / 포지션 사이즈 히스토그램
- [ ] `/api/analysis/behavior` Route 구현

### Phase C
- [ ] 방향성 제안 카드 (최소 8개 룰 중 매치된 것 노출)
- [ ] 상단 "오늘의 인사이트" 카드 (severity 기반 pick)
- [ ] `/api/analysis/suggestions` Route 구현

### 공통
- [ ] 거래 0 / SELL 0 / 입력률 낮음 빈 상태 대응
- [ ] 360px 모바일 레이아웃 깨짐 없음
- [ ] 다크/라이트 색상 (--rise/--fall) 적용
- [ ] `pnpm typecheck`, `pnpm lint` 통과
- [ ] `src/lib/analysis/*` 유틸 단위 테스트 (aggregate, holding-period, concentration, rules 경계값)

---

## 검증

1. **타입/린트**: `pnpm typecheck && pnpm lint`
2. **단위 테스트**: mock trades로 승률·HHI·FIFO 보유일·룰 트리거 경계값 확인
3. **수동 E2E**:
   - 분석 탭 진입 → 기간 전환 시 전 섹션 재계산 확인
   - 거래 추가/삭제 후 `portfolio:refresh` 이벤트로 재조회 연동
   - emotion/tag/result 누락 거래 생성 → 신뢰도 문구 노출
4. **시각 확인**: 360px / 768px 레이아웃, 다크/라이트 색상
