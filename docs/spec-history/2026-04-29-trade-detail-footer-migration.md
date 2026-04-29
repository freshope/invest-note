# Spec: TradeDetail footer를 FullScreenPanelFooter(sticky={false})로 통합

> 완료: 2026-04-29

## 배경 / 문제

2026-04-29의 풀스크린 패널 9곳 마이그레이션(`3f507c1`)은 form 기반 **sticky** footer만 통합했고, `TradeDetail.tsx`의 정적(`flex-none`) footer는 변형이 달라 범위 외로 남겼다. 그 결과 동일한 safe-area 인라인 `paddingBottom: "calc(1rem + env(safe-area-inset-bottom))"`이 `app/src/components/base/FullScreenPanel.tsx:216`과 `app/src/components/records/TradeDetail.tsx:295` 두 곳에 분산돼 단일 지점화가 미완 상태다. `FullScreenPanelFooter`는 이미 `sticky` prop(기본 `true`)을 지원하므로 `sticky={false}`로 전달하면 `flex-none` 변형도 동일 컴포넌트로 통합 가능하다.

## 목표

- `TradeDetail.tsx`의 footer가 `<FullScreenPanelFooter sticky={false} className="flex-none flex gap-3">`로 교체된다.
- safe-area 인라인 `calc(1rem + env(safe-area-inset-bottom))`이 코드베이스 전체에서 `FullScreenPanel.tsx` 한 곳만 남는다.
- 마이그레이션 전후로 거래 상세 패널의 footer 시각/레이아웃 동작이 동일하다 (하단 정적 위치, 본문 스크롤과 분리, safe-area 패딩 동일).

## 설계

### 접근 방식

- `FullScreenPanelFooter` 컴포넌트의 cn() 합성:
  `"bg-background px-5 pt-3 pb-4" + (sticky && "sticky bottom-0") + className`.
- `sticky={false}` 전달 시 `sticky bottom-0` 클래스가 제거된다. TradeDetail 부모는 `h-[100dvh] flex flex-col overflow-hidden` 구조이므로 footer가 줄어들지 않도록 `className`에 `flex-none`을 포함해야 한다.
- 기존 footer의 `flex gap-3`도 className에 합쳐 전달 → `className="flex-none flex gap-3"`.
- 컴포넌트 내부 `pb-4`가 남아 있지만 인라인 `paddingBottom`(safe-area calc)이 우선 적용되므로 시각 결과는 기존과 동일.
- import: `import { FullScreenPanelFooter } from "@/components/base/FullScreenPanel";` (다른 마이그레이션 파일과 동일 경로).

### 주요 변경 파일

- `app/src/components/records/TradeDetail.tsx` — footer div(L292-314) 를 `FullScreenPanelFooter`로 교체 + import 추가.

### 교체 대상 (현재 L292-314)

```tsx
<div
  className="flex-none bg-background px-5 pt-3 flex gap-3"
  style={{ paddingBottom: "calc(1rem + env(safe-area-inset-bottom))" }}
>
  <Button … 삭제 …/>
  <Button … 수정 …/>
</div>
```

### 교체 후

```tsx
<FullScreenPanelFooter sticky={false} className="flex-none flex gap-3">
  <Button … 삭제 …/>
  <Button … 수정 …/>
</FullScreenPanelFooter>
```

## 구현 체크리스트

- [x] `TradeDetail.tsx`에 `FullScreenPanelFooter` import 추가
- [x] footer div(L292-314)를 `<FullScreenPanelFooter sticky={false} className="flex-none flex gap-3">`로 교체 (인라인 style 제거, 자식 Button 2개 그대로 유지)
- [x] grep 확인: `calc(1rem + env(safe-area-inset-bottom))` 패턴이 `FullScreenPanel.tsx:216` 단일 지점만 매치 (BottomNav.tsx의 다른 변형은 범위 외)
- [x] 타입 체크 통과 (`pnpm tsc`)

## 검증

1. `pnpm -C app exec tsc --noEmit` — 타입 통과.
2. `grep -rn "safe-area-inset-bottom" /Users/jwlee/workspace/invest-note/app/src` — `FullScreenPanel.tsx` 한 곳만 매치되는지.
3. 개발 서버에서 거래 상세 패널 진입 → footer가 하단에 정적 위치하고, 삭제/수정 버튼이 동일 레이아웃·간격으로 노출되며, safe-area 인셋(iOS) 패딩이 기존과 동일하게 적용되는지 시각 확인.

## 우려사항 / 리스크

- `FullScreenPanelFooter` 내부의 `pb-4` 클래스는 인라인 `paddingBottom` 덕분에 현재 무력화되어 있어 시각 변화 없음. 향후 인라인 style → 클래스화 리팩토링이 발생할 때 `pb-4`가 실제 적용된다는 점만 인지.
- 부모 컨테이너(`flex flex-col h-[100dvh]`)에서 `flex-none`이 누락되면 footer가 줄어들 수 있으므로 className 포함 필수.
