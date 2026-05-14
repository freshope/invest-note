> 완료: 2026-04-21

# Spec: 거래 등록 페이지 개선

## 배경 / 문제

거래 수정 후 상세 페이지에서 수정 내용이 반영되지 않고, 매수/매도 선택 UI가
ToggleGroup이며, 날짜 캘린더가 항상 현재 월을 표시한다.

## 목표

- 거래 수정 저장 후 상세 페이지에 변경된 가격/수량 등이 즉시 반영된다
- 거래 등록 폼에서 매수/매도 선택이 Tabs UI로 표시된다
- 날짜 캘린더 오픈 시 입력된 날짜의 월이 표시된다

## 설계

### 접근 방식

1. **캐시 갱신**: `TradeDetail`에 `useQuery({ queryKey: ["trade", id], initialData: trade })`
   추가. `TradeEditPanel.onSubmit`이 이미 `invalidateQueries(["trade", id])`를 호출하므로
   자동 리패치됨.

2. **매수/매도 탭 UI**: `TradeBasicForm`의 ToggleGroup → `Tabs`/`TabsList`/`TabsTrigger`
   교체. BUY=초록(--rise), SELL=빨강(--fall) 색상 유지.

3. **캘린더 월 수정**: `TradeBasicForm`의 `<Calendar>`에 `defaultMonth={field.value}` 추가.
   팝오버가 열릴 때마다 Calendar가 리마운트되므로 defaultMonth로 충분.

### 주요 변경 파일

- `src/components/records/TradeDetail.tsx` — useQuery로 trade 데이터 반응형 관리
- `src/components/records/TradeBasicForm.tsx` — Tabs UI 교체 + Calendar defaultMonth

## 구현 체크리스트

- [x] `TradeDetail.tsx`: useQuery 추가, trade prop을 initialData로 사용
- [x] `TradeBasicForm.tsx`: ToggleGroup → Tabs/TabsList/TabsTrigger 교체
- [x] `TradeBasicForm.tsx`: Calendar에 defaultMonth={field.value} 추가
- [x] 타입 체크 통과 (`pnpm tsc --noEmit`)

## 우려사항 / 리스크

- TabsTrigger의 data-active 스타일링 오버라이드 필요 (기존 스타일과 충돌 가능)
