> 완료: 2026-04-30

# Spec: 투자 행동 프로필(BehaviorRadar) 차원 재구성 및 계산식 정직화

## 배경 / 문제

분석탭의 "투자 성향 프로필"은 5차원 레이더(거래 템포/분산도/감정 안정성/근거 품질/복기 습관)를 표시하지만 다음 문제가 있다.

- **분산도 중복**: 같은 HHI 데이터를 별도 섹션 "포트폴리오 분산"(DiversificationPanel)에서 더 상세히 표시. 또한 분산도만 "현재 보유 기준"이라 기간 필터를 따르는 다른 차원과 일관성이 깨짐.
- **거래 템포 왜곡**: 평균 보유일 기반이라 장기 보유 1건이 단타 다수 건을 덮음(예: 1일 9건 + 600일 1건 → 평균 60.9일 → "장기"로 분류).
- **명칭 부정직**: 측정 대상은 본질적 "성향"이 아니라 기록된 행동/입력 품질. "감정 안정성"은 실제로는 "불안정 감정 미기록" 비율이고, 빈 데이터에 50점을 줘 "균형"으로 보이는 misleading.
- **전략 정렬 부재**: `strategy_adherence_rate`가 별도 섹션에서만 표시돼 행동 프로필과 한눈에 비교가 어려움.

## 목표

- 레이더 차원을 **분산도 제거 + 전략 일관성 추가**로 재구성(여전히 5차원)
- 거래 템포가 중앙값 보유일 기반으로 동작
- 감정 차원의 빈 데이터 처리가 입력률 경고로 통일됨(50점 fallback 제거)
- 섹션 타이틀이 "투자 행동 프로필"로 변경되고 라벨이 측정 의미와 일치
- 백엔드/프론트 타입·테스트가 모두 일관

## 설계

### 최종 레이더 차원

| # | 키 | 라벨 | low/high | 계산 |
|---|---|---|---|---|
| 1 | tempo | 거래 템포 | 스캘퍼 / 장기 | `중앙값 보유일 / 60 × 100` |
| 2 | emotionStability | 감정 안정도 | 불안정 / 안정 | 안정 감정 비율 × 100, 빈 데이터=0 |
| 3 | reasoningQuality | 근거 체계성 | 감각형 / 분석형 | `1 - (FEELING+무태그)/BUY × 100` (계산 유지) |
| 4 | reviewHabit | 복기 습관 | 무복기 / 복기형 | `sell_reason 입력 SELL / SELL × 100` (변경 없음) |
| 5 | strategyConsistency | 전략 일관성 | 이탈형 / 준수형 | judged 거래의 FOLLOWED 비율 × 100 |

### Codex 의미 반전 미채택

레이더의 "모든 차원은 높을수록 좋음" 일관성을 유지하기 위해, 감정 차원을 "감정 리스크"(낮을수록 좋음)로 뒤집지 않는다. 라벨/이름만 정직하게 변경.

### 빈 데이터 처리(advisor 보강)

- tempo, emotion 모두 데이터 없을 때 0점 + 입력률 경고로 통일.
- 감정 50점 fallback 제거(misleading).

### 주요 변경 파일

- `api/src/invest_note_api/domain/analysis/profile.py` — `BehaviorProfile`/`ProfileInputRates` 필드 재구성, `compute_profile`에 `strategy_evals` 추가, 중앙값 tempo
- `api/src/invest_note_api/schemas/analysis_response.py` — 응답 스키마 갱신
- `api/src/invest_note_api/routers/analysis.py` — `build_strategy_evaluations` 호출 후 `compute_profile`에 전달
- `api/tests/test_analysis_logic.py`, `api/tests/test_analysis.py` — 테스트 갱신
- `app/src/lib/analysis/profile.ts` — 타입 갱신
- `app/src/components/analysis/BehaviorRadar.tsx` — DIMENSIONS/라벨/입력률 매핑 갱신
- `app/src/components/analysis/AnalysisDashboard.tsx` — 섹션 타이틀 변경

## 구현 체크리스트

- [x] 1. `profile.py` — 필드 재구성(`diversification` 제거, `strategy_consistency` 추가, `strategy` 입력률), `compute_profile(..., strategy_evals=None)`, 중앙값 tempo, 감정 빈 데이터 0점
- [x] 2. `analysis_response.py` — 응답 스키마 동기화
- [x] 3. `routers/analysis.py` — `build_strategy_evaluations` 호출하여 `compute_profile`에 전달
- [x] 4. 백엔드 테스트 갱신 — `test_analysis_logic.py` + `test_analysis.py` + `cd api && poetry run pytest -q`
- [x] 5. `app/src/lib/analysis/profile.ts` — 타입 변경
- [x] 6. `BehaviorRadar.tsx` — DIMENSIONS 5개 재구성, 라벨 갱신, `dimInputRates` 갱신, 분산도 주석 제거
- [x] 7. `AnalysisDashboard.tsx` — 섹션 타이틀 변경
- [x] 8. `pnpm tsc --noEmit`
- [x] 9. `compute_profile` 호출부 검색으로 영향 범위 재확인

## 우려사항 / 리스크

- 클라이언트가 `diversification` 필드를 기대하면 깨짐. 단일 통합 배포라 동기화 가능.
- 전략 일관성 차원과 StrategyAdherencePanel은 같은 데이터의 다른 표현(레이더는 단일 점수, 섹션 6은 상세). 의도된 역할 분리.
- 백엔드는 전체 `pytest -q`로 검증해 누락 방지.
