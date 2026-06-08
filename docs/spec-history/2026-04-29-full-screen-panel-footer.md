# Spec: FullScreenPanelFooter 컴포넌트 추출

> 완료: 2026-04-29

## 배경 / 문제

`<div className="sticky bottom-0 bg-background px-5 pt-3 pb-4" style={{ paddingBottom: "calc(1rem + env(safe-area-inset-bottom))" }}>` 패턴이 풀스크린 패널 9곳에 동일하게 복붙되어 있다. magic 인라인 `calc(1rem + env(safe-area-inset-bottom))`가 한 곳만 바뀌어도 어긋날 위험이 있고, 안전 영역 처리 로직이 단일 지점이 아니다. `FullScreenPanel`에는 이미 `Header`/`Body`가 sub-component로 추출되어 있는데 `Footer`만 누락된 상태.

## 목표

- `FullScreenPanelFooter` 컴포넌트가 `@/components/base/FullScreenPanel`에서 export되어 동일한 sticky + safe-area 인라인 스타일을 단일 지점에서 정의한다.
- 9곳의 footer 패턴이 새 컴포넌트로 일괄 마이그레이션되어 `sticky bottom-0` raw 클래스와 `paddingBottom: "calc(1rem + env(safe-area-inset-bottom))"` 인라인 스타일이 코드베이스 footer 사용처에서 사라진다(TradeDetail 제외).
- 기존 동작/렌더 결과는 변하지 않는다 (UI 회귀 없음).
- `pnpm tsc --noEmit` 통과.

## 설계

### 접근 방식

1. `app/src/components/base/FullScreenPanel.tsx`에 `FullScreenPanelFooter` 추가:
   - Props: `children`, `className?: string`, `sticky?: boolean = true`
   - 기본 className: `"bg-background px-5 pt-3 pb-4"` + sticky=true일 때 `"sticky bottom-0"` 추가
   - 인라인 style: `{ paddingBottom: "calc(1rem + env(safe-area-inset-bottom))" }`
   - className은 `cn()` 유틸로 합성 (기존 컴포넌트 스타일 follow)
   - `Header`/`Body` 옆에서 `export`
2. 9개 사용처 마이그레이션:
   - 단일 버튼 7곳: `<FullScreenPanelFooter>{button}</FullScreenPanelFooter>`로 단순 치환
   - 이중 버튼 2곳(`TradeMetaBuyForm`, `TradeMetaSellForm`): `<FullScreenPanelFooter className="flex gap-3">` 형태로 추가 className 전달
3. `sticky` prop은 향후 `TradeDetail`(flex-none 변형) 등의 후속 마이그레이션 여지를 남기되, 본 작업에서는 default `true`만 사용. TradeDetail 자체 마이그레이션은 본 작업 범위 외(백로그 명시 9곳에 포함되지 않음).

### 주요 변경 파일

- `app/src/components/base/FullScreenPanel.tsx` — `FullScreenPanelFooter` 추가 및 export
- `app/src/components/records/TradeBasicForm.tsx` — footer div 치환 (단일 버튼)
- `app/src/components/records/TradeEditPanel.tsx` — footer div 치환 (단일 버튼)
- `app/src/components/records/TradeMetaBuyForm.tsx` — footer div 치환 (`className="flex gap-3"`)
- `app/src/components/records/TradeMetaSellForm.tsx` — footer div 치환 (`className="flex gap-3"`)
- `app/src/components/accounts/AccountFormPanel.tsx` — footer div 치환 (단일 버튼 + 에러 메시지)
- `app/src/components/import/ImportTradesPanel/FileStep.tsx` — footer div 치환
- `app/src/components/import/ImportTradesPanel/AccountStep.tsx` — footer div 치환
- `app/src/components/import/ImportTradesPanel/PreviewStep.tsx` — footer div 치환
- `app/src/components/import/ImportTradesPanel/ResultStep.tsx` — footer div 치환

## 구현 체크리스트

- [x] `FullScreenPanel.tsx`에 `FullScreenPanelFooter` 컴포넌트 추가 + export
- [x] `TradeBasicForm.tsx` 마이그레이션
- [x] `TradeEditPanel.tsx` 마이그레이션
- [x] `TradeMetaBuyForm.tsx` 마이그레이션 (이중 버튼)
- [x] `TradeMetaSellForm.tsx` 마이그레이션 (이중 버튼)
- [x] `AccountFormPanel.tsx` 마이그레이션
- [x] `ImportTradesPanel/FileStep.tsx` 마이그레이션
- [x] `ImportTradesPanel/AccountStep.tsx` 마이그레이션
- [x] `ImportTradesPanel/PreviewStep.tsx` 마이그레이션
- [x] `ImportTradesPanel/ResultStep.tsx` 마이그레이션
- [x] grep으로 잔여 `sticky bottom-0 bg-background px-5 pt-3 pb-4` 또는 `calc(1rem + env(safe-area-inset-bottom))` 누락 확인 (TradeDetail 제외)
- [x] 타입 체크 통과 (`pnpm tsc --noEmit`)

## 검증

- `pnpm -C app exec tsc --noEmit` 통과
- 각 패널 화면(거래 추가/수정, 계좌 추가, 일괄 등록 4 step)을 dev 서버 또는 모바일 시뮬레이터에서 열어 footer 위치/안전영역 패딩이 마이그레이션 전과 동일한지 시각 확인
- `git grep -n "sticky bottom-0 bg-background"` 및 `git grep -n "calc(1rem + env(safe-area-inset-bottom))"` 결과에 footer 패턴이 남아있지 않은지 확인 (TradeDetail의 flex-none 변형은 현재 작업 범위 외 — 백로그 후속과제로 남김)

## 우려사항 / 리스크

- TradeDetail의 flex-none 변형은 본 작업에서 마이그레이션하지 않는다. `sticky` prop으로 향후 통합 여지는 남기지만, 백로그 명시 범위(9곳)에만 집중.
- `cn()` 유틸로 className 합성 시, 기존 인라인 className 순서가 다르게 보일 수 있으나 Tailwind 클래스 의미상 동일해야 함.
