# Spec: StockSearchInput / HoldingCard 접근성 보강

## 배경 / 문제

두 위젯이 키보드 동작은 자체 구현으로 처리하지만 ARIA 속성이 부재해 스크린리더 사용자에게 역할/상태가 전달되지 않는다.

### StockSearchInput (`app/src/components/records/StockSearchInput.tsx`)

- `<Input>` (line 102) 은 일반 텍스트 입력으로만 노출됨. 자동완성 드롭다운이 있다는 사실을 스크린리더가 알 수 없음.
- 드롭다운 `<ul>` (line 118) / `<li>` (line 120) 에 `role="listbox"`, `role="option"`, `aria-selected` 등 부재.
- 키보드 네비게이션(`ArrowUp/Down`, `Enter`, `Escape`) 로직은 이미 구현돼 있어 ARIA만 보강하면 WAI-ARIA combobox 패턴 충족.

### HoldingCard (`app/src/components/home/HoldingCard.tsx`)

- 외곽 `<div role="button" tabIndex={0}>` (line 37-39) 에 `aria-label` 부재. 카드 콘텐츠 읽기는 되지만 "OOO 보유 종목 상세 열기" 같은 의도가 명시되지 않음.
- 카드 내부 "매수 근거" 영역 (line 121) 이 별도 onClick 을 가져 button-in-button 안티패턴이 되지만 — **본 spec 비범위**(별도 spec 검토 권장).

## 목표

- `StockSearchInput`: WAI-ARIA Combobox 1.2 (listbox autocomplete) 패턴으로 ARIA 속성 보강. 키보드/마우스 동작 변경 없음.
- `HoldingCard`: 외곽 `role="button"` 에 의미 있는 `aria-label` 추가.
- `pnpm tsc`, `pnpm test` 통과.
- 기존 동작/스타일 회귀 없음.

## 설계

### StockSearchInput — Combobox 패턴

**Input (combobox role):**
- `role="combobox"`
- `aria-expanded={open}`
- `aria-controls="stock-search-listbox"`
- `aria-autocomplete="list"`
- `aria-activedescendant={activeIndex >= 0 ? \`stock-option-\${activeIndex}\` : undefined}`

**`<ul>` (listbox):**
- `id="stock-search-listbox"`
- `role="listbox"`
- `aria-label="종목 검색 결과"`

**`<li>` (option):**
- `id={\`stock-option-\${i}\`}`
- `role="option"`
- `aria-selected={i === activeIndex}`

> base/Input 래퍼는 `{...props}` 로 모든 prop pass-through 하므로(`base/Input.tsx:15`) 별도 수정 불필요.

### HoldingCard

- `role="button"` 유지 (button-in-button 회피)
- `aria-label={\`\${assetName} 보유 종목 상세\`}` 추가

### 비범위

- StockSearchInput 의 render 중 setState 우회 패턴(line 54-58) 정리 — 별도 spec
- HoldingCard 내부 nested clickable (note expand) 의 button-in-button 패턴 — 별도 spec
- `useClickOutside` 의 `react-hooks/refs` 위반 — backlog `feature/eslint-cleanup` 에서 처리
- 자동화된 a11y 테스트(axe-core/Playwright) 도입 — 별도 spec

## 구현 체크리스트

- [x] `StockSearchInput`: Input 에 combobox ARIA 4종 추가 (role, aria-expanded, aria-controls, aria-autocomplete, aria-activedescendant)
- [x] `StockSearchInput`: ul 에 listbox role + id + aria-label
- [x] `StockSearchInput`: li 에 option role + id + aria-selected
- [x] `HoldingCard`: 외곽 div 에 aria-label 추가
- [x] `pnpm tsc` ✅, `pnpm test` ✅ (124 passed)
- [ ] 수동 검증: VoiceOver 또는 chrome devtools accessibility tree 에서 combobox/option 역할 확인 (개발 환경에서 사용자가 확인)

## 검증

1. **타입/테스트**: `pnpm tsc`, `pnpm test` 통과
2. **DOM 검증**: chrome devtools → Elements → Accessibility 탭에서 input 의 Computed Role 이 "combobox", listbox 의 자식 option 이 정상 인식되는지
3. **수동 키보드**: 화살표/Enter/Escape 가 기존과 동일하게 동작하는지 (ARIA 추가로 동작 변화 없어야 함)

## 우려사항 / 리스크

- **`aria-activedescendant` 와 키보드 네비게이션 동기화**: activeIndex 변경 시 자동으로 새 ARIA 값 반영(렌더 driven). 추가 effect 불필요.
- **id 충돌**: 같은 페이지에 StockSearchInput 이 2개 이상 마운트되면 `stock-option-0` id 가 중복됨. 현재 마운트 패턴(거래 등록 폼 1개) 에선 문제 없으나, 향후 다중 마운트 시 `useId()` 로 prefix 부여 필요. 본 spec 에선 단일 마운트 가정.
- **HoldingCard aria-label**: assetName 만 사용 → 같은 이름 종목이 여러 계좌에 있어도 카드별 의미 차이 없음(상세 패널에서 분기). 충분.
