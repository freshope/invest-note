> 완료: 2026-04-25

# Spec: HoldingCard 매수 근거 정렬 + 펼침 토글

## 배경 / 문제

홈 탭의 보유 종목 카드(`HoldingCard.tsx`) "매수 근거" 영역에 두 가지 이슈가 있다.

1. **한 줄 정렬 어긋남**: 컨테이너가 `flex items-start`이고 배지에 `mt-0.5` 보정이 있어, 본문이 한 줄일 때 배지/텍스트가 라인 중앙에서 위로 살짝 치우쳐 보인다. (HoldingCard.tsx:112-113)
2. **줄바꿈 무시**: 본문 `<p>`에 `line-clamp-2`만 있고 `whitespace-*` 클래스가 없어 CSS 기본값(`whitespace: normal`)이 사용자 입력의 `\n`을 공백으로 collapse한다. DB의 `buy_reason`에는 줄바꿈이 보존되며 상세 화면(`TradeDetail.tsx:271`)은 `whitespace-pre-wrap`으로 표시한다 — 컨벤션 불일치.

## 목표

- 매수 근거 본문이 한 줄일 때 배지와 텍스트가 라인 vertical center에 깔끔하게 정렬된다.
- 매수 근거가 여러 줄(`\n` 포함)일 때 우측 끝에 펼침 토글(▼)이 표시된다.
- 토글을 누르면 전체 텍스트가 줄바꿈을 보존(`whitespace-pre-line`)한 채 펼쳐지고, 아이콘이 ▲로 바뀐다.
- 한 줄짜리 입력일 때는 토글 버튼이 표시되지 않는다.
- 토글 클릭이 카드 자체의 `onPress`로 전파되지 않는다.

## 설계

### 접근 방식

1. **정렬 수정**: 컨테이너의 `items-start` → `items-center`로 변경, 배지의 `mt-0.5` 제거. 펼친 상태에서는 본문이 멀티라인이 되므로 `items-start`로 동적 전환.
2. **멀티라인 판별**: `lastNote.includes('\n')` — DB에 저장된 원본 줄바꿈 기준.
3. **접힘 상태 표시**: 첫 줄만 추출(`lastNote.split('\n')[0]`)하고 `line-clamp-1`로 긴 첫 줄도 한 줄에 안전 truncate.
4. **펼침 상태 표시**: 전체 `lastNote`를 `whitespace-pre-line`으로 줄바꿈 보존하여 표시. `line-clamp` 해제.
5. **토글 버튼**: `useState<boolean>`으로 상태 관리. `onClick`에서 `e.stopPropagation()`. `aria-label`/`aria-expanded` 부여.
6. **Nested button 해결**: 외부 카드를 `<button>` → `<div role="button" tabIndex={0} onClick onKeyDown>`로 변경.

### 주요 변경 파일

- `app/src/components/home/HoldingCard.tsx` — 위 6개 변경 모두.

## 구현 체크리스트

- [x] `HoldingCard.tsx`에서 외부 `<button>` → `<div role="button" tabIndex={0}>`로 변경 (onClick 유지, onKeyDown으로 Enter/Space 처리)
- [x] `useState<boolean>` 으로 `expanded` 상태 추가
- [x] `hasMultipleLines = lastNote?.includes('\n')`, `firstLine = lastNote?.split('\n')[0]` 파생값 계산
- [x] 매수 근거 컨테이너: `items-center`(접힘) / `items-start`(펼침) 동적 전환, 배지 `mt-0.5` 제거
- [x] 본문 `<p>`: 접힘 = `firstLine` + `line-clamp-1`, 펼침 = `lastNote` + `whitespace-pre-line` (둘 다 `flex-1`로 토글 영역 확보)
- [x] 토글 버튼: `hasMultipleLines`일 때만 렌더, `▼/▲` 표시, `aria-expanded`/`aria-label`, `e.stopPropagation()`
- [x] 타입 체크 통과 (`pnpm tsc --noEmit`)
- [x] 모바일 뷰포트에서 시각 확인: 한 줄/여러 줄/펼침/접힘 4가지 케이스

## 우려사항 / 리스크

- 카드 외부 요소 변경(`button` → `div role="button"`)으로 키보드 접근성(Enter/Space 핸들러)을 명시적으로 추가해야 한다.
- 토글 펼침 상태는 컴포넌트 로컬. 카드 리렌더 시 접힘으로 초기화될 수 있음 — 의도된 동작으로 간주.
- 매우 긴 단일 라인(`\n` 없음)은 토글이 없어 첫 줄 truncate만 됨. 전문 확인은 상세 화면 사용.
