# Spec: 행동 프로파일 tempo 식 단순화

> 완료: 2026-04-29

## 배경 / 문제

현재 BE `profile.py:55-59`의 tempo 계산식은 두 개의 축(평균 보유기간 + 스캘핑 페널티)이 한 점수에 혼합되어 있어 의미 해석이 어렵다.

```python
tempo_base = _clamp((avg_days / 60) * 100)
tempo = _clamp(tempo_base - scalping_ratio * 10)
```

또한 FE `app/src/lib/analysis/profile.ts`의 `computeProfile` 함수는 production 미사용(테스트에서만 호출)이며 2026-04-28 SOT 통합 후 잔재 코드로 남아있다. 백로그 "분석 탭 성능 / 유지보수" 항목 (이슈 B)으로 등록된 정리 작업.

## 목표

1. BE tempo 계산식이 평균 보유기간 단일 축으로만 산출된다 (scalping 패널티 제거).
2. 관련 BE 테스트(`test_tempo_long_term`)가 새 식 기준으로 통과한다.
3. FE `computeProfile` 함수와 그에 대응하는 6개 테스트 케이스가 삭제되고, 타입 정의(`BehaviorProfile`, `ProfileInputRates`)는 보존되어 기존 import(`BehaviorRadar.tsx`, `ReviewQualityPanel.tsx`, `api-client.ts`)가 그대로 동작한다.
4. `pnpm tsc --noEmit`, `pnpm -C app test`, `cd api && poetry run pytest -q` 모두 통과.

## 설계

### 접근 방식

**BE — tempo 식 단순화**
- `api/src/invest_note_api/domain/analysis/profile.py:55-59`에서 `scalping_ratio` 산출 코드와 패널티 차감 로직을 제거.
- 새 식: `tempo = _clamp((avg_days / 60) * 100)` — clamp는 그대로 유지(0~100 정규화).
- `infer_actual_strategy` import가 다른 곳에서 사용되지 않으면 함께 정리 (사용되면 보존).

**FE — dead code 삭제**
- `app/src/lib/analysis/profile.ts`에서 `computeProfile` 함수 + 내부 `clamp` 헬퍼 + `Trade` import 제거.
- `BehaviorProfile`, `ProfileInputRates` 인터페이스만 유지. 타입 전용 파일이 됨.
- `app/src/lib/analysis/__tests__/analysis.test.ts`에서 `computeProfile` import 라인 + 6개 테스트 케이스(line 532-580) 삭제.

**테스트 갱신**
- `api/tests/test_analysis_logic.py:325-332`의 `test_tempo_long_term` 기댓값 검증 후 식과 일관되게 유지.
- scalping 페널티 검증용 케이스가 있으면 제거 또는 단순화. (현재 backlog에 따르면 1개뿐 — 새 식에서도 `avg_days=120 → tempo=100`은 동일하므로 통과 예상)

### 주요 변경 파일

- `api/src/invest_note_api/domain/analysis/profile.py` — tempo 계산식 단순화, scalping 변수/import 정리
- `api/tests/test_analysis_logic.py` — tempo 테스트 검증 (필요 시 케이스 추가)
- `app/src/lib/analysis/profile.ts` — `computeProfile` 함수와 헬퍼 삭제, 타입만 보존
- `app/src/lib/analysis/__tests__/analysis.test.ts` — `computeProfile` 관련 테스트 6건 + import 제거
- `docs/backlog.md` — 완료 항목 제거

## 구현 체크리스트

- [x] BE `profile.py` tempo 계산식 단순화 + 미사용 import/변수 정리
- [x] BE `test_analysis_logic.py` tempo 테스트 갱신 (필요 시 단순 보유기간 케이스 추가)
- [x] FE `profile.ts`에서 `computeProfile` 함수와 `clamp` 헬퍼, `Trade` import 삭제 (타입만 보존)
- [x] FE `analysis.test.ts`에서 computeProfile 관련 테스트 6건 + import 삭제
- [x] `cd api && poetry run pytest tests/test_analysis_logic.py -q` 통과
- [x] `pnpm -C app test` 통과
- [x] `pnpm tsc --noEmit` 통과
- [x] `docs/backlog.md`에서 완료 항목 제거
- [x] spec-history로 사양서 이관 (`/custom:spec-finish`)

## 우려사항 / 리스크

- **BE 호출자 영향 없음** — `compute_profile` signature가 그대로 유지되므로 `analysis.py:155, 221` 호출자는 무수정.
- **FE 타입 import 보존 검증** — 3개 모듈(`BehaviorRadar.tsx`, `ReviewQualityPanel.tsx`, `api-client.ts`)이 타입 import만 사용하므로 함수 삭제 후에도 영향 없음 (탐색 시 확인됨).
- **사용자 점수 변화** — 기존 사용자 데이터에서 tempo가 scalping 패널티만큼 상승할 수 있음. 분석 점수는 매 요청마다 계산되므로 마이그레이션 불필요. 사용자 가시 변화 가능성은 작은 점수 차이 수준.
