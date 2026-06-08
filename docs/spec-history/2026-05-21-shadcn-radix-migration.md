# Spec: shadcn 컴포넌트 base-ui → radix-ui 전환

> 완료: 2026-05-21

## 배경 / 문제

현재 `fe` 프로젝트의 shadcn 컴포넌트는 `@base-ui/react` 프리미티브 기반의 `base-nova` 스타일을 사용한다. 그러나 shadcn 생태계의 표준은 `@radix-ui/react-*` 이며, 향후 shadcn registry 업데이트·예시 코드·새 컴포넌트 추가 시 호환성을 잃는다. base-nova 의 `Backdrop`/`Popup`/`Positioner`·`alignItemWithTrigger`·`render` prop 등 base-ui 고유 API가 ui/ 레이어 곳곳에 박혀있어 표준에서 벗어난 유지보수 부담을 야기한다.

## 목표

- `fe/package.json` 에서 `@base-ui/react` 의존성이 완전히 제거된다.
- `fe/src/components/ui/` 의 9개 컴포넌트가 `@radix-ui/react-*` 기반으로 동작한다.
- `fe/src/components/base/` 래퍼 11개의 외부 API(export 이름·시그니처)는 유지되어 컨슈머 코드는 import 경로 변경 없이 동작한다.
- `data-active:` / `group-data-horizontal:` 등 base-ui 고유 데이터 속성 className 이 radix 의 `data-[state=active|on]:` / `data-[orientation=horizontal]:` 로 치환된다.
- 거래 추가/수정 다이얼로그, 종목 Select, BUY/SELL 탭, ToggleGroup(매수/매도) UI가 시각·기능적으로 회귀 없이 동작한다.
- `pnpm -C fe exec tsc --noEmit`, `pnpm -C fe test`, `pnpm -C fe build` 가 모두 통과한다.

## 설계

### 접근 방식

base-ui 와 radix-ui 의 API 차이가 컴포넌트별로 크기 때문에 **shadcn registry 의 표준 radix 버전을 재설치하지 않고** 우리 ui/ 컴포넌트를 직접 손으로 포팅한다. 이유는 (1) `base/` 래퍼가 기대하는 export 이름(예: `tabsListVariants`, `showCloseButton` 옵션)과 커스텀 className 을 보존해야 하고, (2) `base-nova` → `new-york` 스타일 변경에 따른 시각적 회귀를 최소화하기 위함이다.

작업은 **컴포넌트 단위 PR/커밋 분할**로 진행한다. 각 step 종료마다 tsc/test 통과 + 해당 컴포넌트 사용 화면 수동 회귀 확인 후 다음 step 으로 넘어간다.

base-nova → radix 전환의 핵심 매핑:
- `render={<X/>}` → `asChild` + `<X>`
- `Backdrop`/`Popup`/`Positioner` → `Overlay`/`Content` (Dialog/Popover/Select)
- `Tab`/`Panel` → `Trigger`/`Content` (Tabs)
- `data-open` / `data-closed` → `data-[state=open]` / `data-[state=closed]`
- `data-active` → `data-[state=active]` (Tabs) / `data-[state=on]` (Toggle)
- `data-horizontal` / `data-vertical` → `data-[orientation=horizontal|vertical]`
- `data-placeholder` (Select trigger) → `data-[placeholder]` 유지 또는 SelectValue placeholder prop 사용
- `alignItemWithTrigger` (Select) → radix 에 1:1 대응 없음. SelectContent 의 `position="popper"` + `align` 으로 시각적 근사 매칭.

### 주요 변경 파일

- `fe/package.json` — `@base-ui/react` 제거, `@radix-ui/react-{dialog,popover,select,tabs,toggle,toggle-group,slot}` 추가
- `fe/components.json` — `style: "base-nova"` → `"new-york"`
- `fe/src/app/globals.css` — base-ui 전용 키프레임/data 속성 토큰을 radix `data-[state=*]` 로 호환 점검 및 정리
- `fe/src/components/ui/button.tsx` — `ButtonPrimitive` 제거, `Slot` 기반 `asChild` 패턴으로 전환
- `fe/src/components/ui/input.tsx` — `InputPrimitive` 제거, 표준 `<input>` 으로 전환
- `fe/src/components/ui/toggle.tsx` — `@radix-ui/react-toggle` 사용, `aria-pressed` 기반 className 유지
- `fe/src/components/ui/toggle-group.tsx` — `@radix-ui/react-toggle-group` 사용, Context 로직 유지
- `fe/src/components/ui/tabs.tsx` — `@radix-ui/react-tabs`, `Tab`→`Trigger`/`Panel`→`Content`, data 속성 매핑
- `fe/src/components/ui/popover.tsx` — `@radix-ui/react-popover`, `Positioner`+`Popup` → `Content`
- `fe/src/components/ui/dialog.tsx` — `@radix-ui/react-dialog`, `Backdrop`→`Overlay`/`Popup`→`Content`, `render` → `asChild`, `showCloseButton` 옵션 유지
- `fe/src/components/ui/select.tsx` — `@radix-ui/react-select`, API 가장 광범위하게 재작성, `SelectScrollUpButton`/`ScrollDownButton`/`Viewport` 추가
- `fe/src/components/base/Tabs.tsx` — `import type { Tabs as TabsPrimitive } from "@base-ui/react/tabs"` 제거, `React.ComponentProps<typeof UITabs>` 로 치환
- `fe/src/components/base/Dialog.tsx`·`Popover.tsx`·`Select.tsx`·`Button.tsx`·`Input.tsx`·`ToggleGroup.tsx`·`Textarea.tsx`·`Label.tsx`·`Calendar.tsx` — export/타입 정합성 검토 (대부분 변경 불필요)
- `fe/src/components/records/TradeBasicForm.tsx` — `data-active:`(2건), `group-data-horizontal/tabs:`(1건) 치환
- `fe/src/lib/constants/pnl-colors.ts` — `dataActiveBg: "data-active:bg-..."`(2건) 을 radix 데이터 속성으로 치환

## 구현 체크리스트

- [x] **Step A 패키지·설정**: `fe/package.json` 의존성 교체, `fe/components.json` style 변경, `pnpm install` 후 tsc 베이스라인 확인
- [x] **Step B Button + Input**: `ui/button.tsx`·`ui/input.tsx` radix(slot/native) 포팅, base-ui import 0건 확인
- [x] **Step C Toggle + ToggleGroup**: `ui/toggle.tsx`·`ui/toggle-group.tsx` radix 포팅, Context·variant 보존, `data-[state=on]` 매핑
- [x] **Step D Tabs + 컨슈머 치환**: `ui/tabs.tsx` radix 포팅, `TradeBasicForm.tsx` 의 `data-active`/`group-data-horizontal` 치환, `pnl-colors.ts` 치환
- [x] **Step E Popover**: `ui/popover.tsx` radix 포팅, `Positioner`+`Popup` → `Content` 한 단계 통합
- [x] **Step F Dialog**: `ui/dialog.tsx` radix 포팅, `render` → `asChild`, `showCloseButton`·`DialogFooter` 옵션 유지
- [x] **Step G Select**: `ui/select.tsx` radix 포팅, `Viewport`/`ScrollUpButton`/`ScrollDownButton` 추가, `alignItemWithTrigger` 대체 방안 적용
- [x] **Step H 마무리**: `base/Tabs.tsx` 의 base-ui type-only import 제거, `globals.css` 점검, `@base-ui/react` 패키지 완전 제거 확인, 전체 tsc/test/build/수동 회귀

## 우려사항 / 리스크

- **Select 의 `alignItemWithTrigger` 동작 손실 가능**: base-ui 의 "선택된 아이템을 트리거 위치에 정렬" 동작이 radix 에는 없음. 시각적 차이가 있을 수 있어 사용자 확인 필요.
- **`base-nova` → `new-york` 스타일 차이**: 그림자/radius/색 토큰 미세 차이가 모바일 화면에서 두드러질 수 있음. Capacitor 빌드로도 한 번 확인 필요.
- **`globals.css` 의 애니메이션 토큰**: `tw-animate-css` 가 base-ui 의 `data-open`/`data-closed` 와 radix 의 `data-[state=open]`/`data-[state=closed]` 모두 매칭되는지 점검 필요. 매칭 안 되면 키프레임 클래스 셀렉터 추가/조정.
- **PR 분할로 중간 상태 노출**: Step A~G 진행 중에는 ui/ 일부는 base-ui, 일부는 radix 가 공존한다. 의존성 충돌이 없도록 Step A 에서 두 패키지를 모두 install 한 상태로 시작하고 Step H 에서 base-ui 제거를 마지막에 수행.

## 예상 작업량

11~18시간 (1.5~2.5 인일). Select(2h) 와 Dialog(1.5h) 가 가장 큰 비중.
