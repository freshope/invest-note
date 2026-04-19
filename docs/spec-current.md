# Spec: 전체화면 패널 애니메이션 일관화

## 문제

`FullScreenPanel`이 **열릴 때는 슬라이드 애니메이션이 동작하지만 닫힐 때는 팝하듯 즉시 사라지는** 버그가 8개 사용처 전부에서 재현된다.

### 근본 원인

`FullScreenPanelContent`는 내부에 `mounted / visible / animating` state를 두고 enter + exit 애니메이션을 자체 관리하도록 설계되어 있다. 그러나 모든 호출부가 `{openState && <Panel open={openState} ...>}` 형태로 **부모에서 먼저 조건부 언마운트**하기 때문에 `openState=false` 순간 패널 전체가 날아가 exit transition이 재생될 틈이 없다.

부가 이슈: `TradeFormPanel.tsx`의 `setTimeout(() => reset, 350)` 이 부모 언마운트 후 setState를 호출하여 React 경고를 유발한다.

## 목표

8개 사용처 모두에서 열림/닫힘 300ms 슬라이드 애니메이션이 동일하게 재생된다.  
중첩 패널(StockDetail ↔ TradeDetail)에서도 body scroll lock이 정상 동작한다.

## 설계

### 접근: lifecycle을 `FullScreenPanel` 루트로 이관

- `FullScreenPanel` (루트): Context-only 래퍼 → lifecycle owner로 승격.
  - `mounted`, `visible` state를 보유.
  - `open=true` → `setMounted(true)` → double rAF → `setVisible(true)`.
  - `open=false` → `setVisible(false)` (mounted 유지) → transitionEnd → `setMounted(false)`.
  - `!mounted` 이면 `null` 반환 → children이 exit 애니메이션 종료 후 자연스럽게 사라짐.
  - body scroll lock을 루트로 이동. **모듈 스코프 카운터** (`lockCount`)로 중첩 패널에서 lock이 조기에 풀리는 문제 방어.
  - `transitionEnd` 이벤트에 `e.target === panelRef.current && e.propertyName === 'transform'` 가드 추가.
  - Context에 `visible`, `onClose`, `onTransitionEnd`, `panelRef` 제공.

- `FullScreenPanelContent` (콘텐츠): portal + translate 클래스만 담당.
  - `open` prop 제거. Context에서 `visible / onTransitionEnd / panelRef` 소비.

- `useSnapshotWhileOpen<T>(open, value)` export — null-risk props 보존용.
  ```ts
  function useSnapshotWhileOpen<T>(open: boolean, value: T): T {
    const ref = useRef(value);
    if (open) ref.current = value;
    return ref.current;
  }
  ```

### 호출부 변경 (8곳)

| 파일 | 변경 내용 |
|---|---|
| `src/components/settings/AccountList.tsx:54` | `{addOpen && ...}` → 가드 제거 |
| `src/components/settings/AccountCard.tsx:73` | `{editOpen && ...}` → 가드 제거 |
| `src/components/records/TradeList.tsx:78` | `{formOpen && ...}` → 가드 제거 |
| `src/components/records/TradeList.tsx:87` | `{detailOpen && selectedTrade && ...}` → 가드 제거, `selectedTrade` null-safe |
| `src/components/records/TradeDetail.tsx:290` | `{editOpen && ...}` → 가드 제거 |
| `src/components/home/HoldingsList.tsx:78` | `{selected && ...}` → 가드 제거, `StockDetailPanel` 내부 스냅샷 |
| `src/components/stocks/StockDetailPanel.tsx:98` | `{tradeDetailOpen && ...}` → 가드 제거, `TradeDetailPanel` 내부 스냅샷 |
| `src/components/records/TradeDetailPanel.tsx:72` | `{stockOpen && ...}` → 가드 제거 |

Null-risk 데이터가 있는 패널(`StockDetailPanel`, `TradeDetailPanel`)은 내부에서 `useSnapshotWhileOpen(open, props)`로 exit 중에도 마지막 값 유지.

`TradeFormPanel.tsx:33-41` `setTimeout` 블록 삭제.

## 수정 파일 목록

1. `src/components/base/FullScreenPanel.tsx` (핵심 리팩터)
2. `src/components/records/TradeFormPanel.tsx` (setTimeout 제거)
3. `src/components/home/HoldingsList.tsx`
4. `src/components/stocks/StockDetailPanel.tsx`
5. `src/components/records/TradeDetailPanel.tsx`
6. `src/components/records/TradeList.tsx`
7. `src/components/records/TradeDetail.tsx`
8. `src/components/settings/AccountList.tsx`
9. `src/components/settings/AccountCard.tsx`

## 검증

- 각 패널 열기/닫기 → 양방향 300ms 슬라이드 확인
- 홈 → StockDetail → TradeDetail 중첩 → 안쪽 닫기 시 바깥 유지, scroll lock 유지 확인
- 패널 닫힌 후 body에 `overflow: hidden` 없는지 DevTools 확인
- Console에 React 경고 없음
- `npm run lint && npm run build` 통과
