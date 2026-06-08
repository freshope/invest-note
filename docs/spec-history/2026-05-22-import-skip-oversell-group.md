# Spec: 거래 일괄 등록 시 매도 보유부족 그룹만 제외하고 나머지 등록

> 완료: 2026-05-22

## 배경 / 문제

현재 거래내역서 일괄 등록(`/trades/import/preview` → `/trades/import/commit`)은 보유 수량이 부족한 매도(SELL)가 1건이라도 감지되면 FE가 commit 버튼을 disable 하여 **전체 등록을 차단**한다.

- BE는 이미 그룹(=계좌·종목·국가) 단위로 부분 성공을 지원한다 (`be/src/invest_note_api/routers/trades.py:664-814`). 문제 그룹만 skip, 다른 그룹은 INSERT 된다.
- 그러나 FE `PreviewStep.tsx:161-164`의 `hasValidationError` disabled 조건이 commit 자체를 막아 BE의 부분 성공 경로에 도달하지 못한다.

사용자 요구:
1. 문제 매도가 있는 종목 그룹은 그 그룹 전체를 제외하고, 정상 종목은 등록되게 한다.
2. 어느 종목·어떤 사유로 제외되는지 사용자가 인지할 수 있게 한다.

## 목표 (완료 기준)

- 같은 import에 정상 종목 그룹 + 보유부족 SELL 그룹이 섞여 있으면 정상 그룹은 등록되고, 문제 그룹만 제외된다.
- Preview 단계에서 제외 예정 그룹의 종목·사유가 노출되며, **등록 버튼은 활성** 상태로 사용자가 "제외하고 등록" 의사를 클릭으로 표현한다.
- Result 단계에서 등록/갱신 건수와 함께 제외된 그룹의 종목·사유가 함께 표시된다.
- 사용자 안내 문구가 "전체 차단"이 아닌 "일부 제외"에 맞게 정정된다.

## 설계

### 접근 방식 — 그룹 단위 제외 (사용자 결정)

BE는 동작이 이미 맞으므로 **메시지 문구**와 **응답 메타데이터** 만 다듬고, FE의 차단을 풀어 부분 등록 흐름을 노출한다.

- 같은 종목 그룹 안의 BUY까지 함께 제외된다 (사용자 합의). 추후 사용자가 누락 매도를 보완해 다시 업로드하면 signature dedup으로 BUY가 중복 등록되지 않고, 매도는 신규로 들어간다.
- "row 단위로 SELL만 빼는" 옵션은 채택하지 않음 (BUY만 들어가고 SELL이 누락된 일시 왜곡 상태를 만들 수 있음).

### 주요 변경 파일

**BE**
- `be/src/invest_note_api/routers/trades.py`
  - `_find_import_oversell()` (208-236): 안내 메시지 끝의 "거래내역서 기간을 더 길게 받아 다시 시도해주세요" → "해당 종목은 등록되지 않고, 나머지 거래는 등록됩니다." 로 정정.
  - `_validate_import_groups()` (105-205): 제외 그룹의 row 수 합계를 계산해 응답에 채움.
  - `import_commit()` (629-823): oversell 그룹 skip 시 `commit_errors` reason도 동일 문구로 정정.
- `be/src/invest_note_api/schemas/trade_import.py`
  - `ImportPreviewResponse`에 `excluded_count: int = 0` 추가.

**FE**
- `fe/src/components/records/ImportTradesPanel/PreviewStep.tsx`
  - 배너 톤 red → yellow, 헤더 "정합성 오류 — 등록할 수 없습니다" → "일부 거래가 제외됩니다".
  - 등록 버튼 `disabled` 조건에서 `hasValidationError` 제거.
  - 등록 버튼 라벨에 제외 정보 반영 ("제외하고 N건 등록하기" 또는 "N건 등록 · M건 제외"). 전 그룹 제외 시 disabled 유지.
  - 카운트 카드 정확도: `excluded_count` 반영 또는 별도 warn 카드 추가.
- `fe/src/lib/api-client.ts`
  - `ImportPreviewResponse` 타입에 `excluded_count: number` 추가.

## 구현 체크리스트

- [x] BE: `_find_import_oversell()` 메시지 문구 정정 (`trades.py:208-236`).
- [x] BE: `ImportPreviewResponse`에 `excluded_count: int = 0` 추가 (`schemas/trade_import.py`).
- [x] BE: `_validate_import_groups()`가 제외 그룹 row 수 합계를 계산해 응답에 채우도록 수정.
- [x] BE: 기존 `test_oversell_*` 테스트 메시지 기대값 정정 + `excluded_count` 검증 케이스 추가 (`be/tests/test_trades.py`).
- [x] BE: `cd be && poetry run pytest tests/test_trades.py -q` 통과 (전체 292개 통과).
- [x] FE: `ImportPreviewResponse` 타입에 `excluded_count` 추가 (`fe/src/lib/api-client.ts`).
- [x] FE: `PreviewStep.tsx` 배너 톤·문구·disabled·라벨 정정.
- [x] FE: PreviewStep 단위 테스트 — validation_errors 존재 시 등록 버튼 활성, 배너 warn 톤, 라벨에 "제외" 표시 (`__tests__/PreviewStep.test.tsx`).
- [x] FE: `pnpm -C fe exec tsc --noEmit` 통과.
- [x] FE: `pnpm -C fe test` 통과 (129개 통과).

## 검증 (E2E)

1. 한 계좌에 종목A 보유 0주 + 종목B 신규 BUY 가 섞인 거래내역서 준비.
2. 일괄 등록 → preview 단계에서 노란 배너에 "종목A 매도: 보유 수량 없음" 표시, 등록 버튼 활성, 라벨에 "제외하고 X건 등록" 확인.
3. 등록 클릭 → ResultStep에서 종목B 만 inserted, 종목A 는 errors[]에 표시.
4. trades 목록에 종목B만 추가됐는지 확인.

## 우려사항 / 리스크

- 같은 그룹의 BUY까지 함께 제외되므로 사용자는 누락 매도 보완 시 한 번 더 업로드 필요 (dedup으로 중복 방지됨).
- 메시지 문구 변경으로 기존 BE 테스트가 깨질 수 있어 함께 정정 필요.
- `excluded_count` 는 응답 schema 추가이므로 FE 타입 동기화를 빠뜨리면 런타임 undefined → default 0 처리.
