# Spec: components/records/constants.ts shim 제거

## 배경 / 문제

`app/src/components/records/constants.ts`는 `@/lib/constants/trading`의 10개 심볼을 그대로 re-export하는 단순 shim. simplify-fe-followup 작업에서 호환성 유지 목적으로 남겨둔 항목(backlog 등록 완료). 5개 consumer가 여전히 이 shim을 통해 import하고 있어, 정의 출처가 분산된 채로 유지되고 있다. 가치 없는 간접 레이어를 제거해 import 경로를 단일화한다.

## 목표

- `app/src/components/records/constants.ts` 파일이 삭제된다.
- 5개 consumer의 import 경로가 `@/lib/constants/trading`으로 일괄 교체된다.
- 타입 체크와 테스트가 통과한다.
- 동작 변경 없음(순수 정리 작업).

## 설계

### 접근 방식

1. 5개 consumer에서 `./constants` (또는 `../constants` 등) → `@/lib/constants/trading`으로 import 경로 변경. 심볼 목록은 그대로 유지.
2. shim 파일 (`app/src/components/records/constants.ts`) 삭제.
3. 타입 체크로 누락된 참조가 없음을 검증.

### 주요 변경 파일

- `app/src/components/records/constants.ts` — **삭제**
- `app/src/components/records/AutoMetaField.tsx` — import 경로 교체 (`EMOTION_LABELS`, `REASONING_TAG_LABELS`)
- `app/src/components/records/StrategyEmotionFields.tsx` — import 경로 교체 (`STRATEGIES`, `EMOTIONS`)
- `app/src/components/records/TradeMetaBuyForm.tsx` — import 경로 교체 (`REASONING_TAGS`, `STRATEGY_VALUES`, `EMOTION_VALUES`, `REASONING_TAG_VALUES`)
- `app/src/components/records/TradeEditPanel.tsx` — import 경로 교체 (동일 심볼군)
- `app/src/components/records/TradeDetail.tsx` — import 경로 교체 (`STRATEGY_LABELS`, `EMOTION_LABELS`, `REASONING_TAG_LABELS`)

> 참고: `TradeBasicForm.tsx`는 이미 `@/lib/constants/trading`에서 직접 import 중(작업 불필요).

## 구현 체크리스트

- [ ] `AutoMetaField.tsx` import 경로 교체
- [ ] `StrategyEmotionFields.tsx` import 경로 교체
- [ ] `TradeMetaBuyForm.tsx` import 경로 교체
- [ ] `TradeEditPanel.tsx` import 경로 교체
- [ ] `TradeDetail.tsx` import 경로 교체
- [ ] `app/src/components/records/constants.ts` 삭제
- [ ] 타입 체크 통과 (`pnpm tsc`)
- [ ] 테스트 통과 (`pnpm -C app test`)
- [ ] 잔존 참조 없음 검증 (`grep -r "components/records/constants" app/src`, `grep -rE "from ['\"]\\./constants['\"]" app/src/components/records`)

## 우려사항 / 리스크

- 없음. 단순 re-export shim 제거이며, 모든 심볼이 원본(`@/lib/constants/trading`)에 존재함을 사전 확인. 동작 변경 없음.
