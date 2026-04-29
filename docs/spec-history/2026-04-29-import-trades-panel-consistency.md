# Spec: 일괄 등록 판넬 디자인/레이아웃을 거래 등록·상세와 일관화

> 완료: 2026-04-29

## 배경 / 문제

거래 일괄 등록(`ImportTradesPanel`)은 거래 등록(`TradeFormPanel`)·거래 상세(`TradeDetail`)와 동일한 `FullScreenPanel` 위에 올라가지만, 내부 step 컴포넌트의 레이아웃·버튼 스타일·safe-area 처리가 다른 두 판넬과 시각적으로 어긋나 동일한 모달 시스템임에도 일괄 등록만 다르게 보인다.

구체적으로:
- **TradeFormPanel(거래 등록)** / **TradeEditPanel(거래 수정)** / **TradeDetail(거래 상세)** 의 본문은 모두 `flex flex-col min-h-full` + `flex-1 px-5 pt-2 pb-4 space-y-5/6` 본문 + `sticky bottom-0` + `paddingBottom: "calc(1rem + env(safe-area-inset-bottom))"` 풀-와이드 `size="xl"` 버튼 패턴을 사용
- **ImportTradesPanel의 4개 step**(AccountStep / FileStep / PreviewStep / ResultStep)은 padding 없이 `<div className="flex flex-col gap-6">`로 시작하고, default 크기의 우측 정렬 버튼(`self-end`)을 본문 안 인라인으로 배치 (sticky 없음, safe-area 없음)
- 헤더 타이틀: 다른 판넬은 `"거래 등록"` / `"근거 입력"` 등 단순 제목인데, 일괄 등록만 `"거래 일괄 등록 — 계좌 선택"`처럼 step명까지 노출
- PreviewStep의 "등록 대상 계좌" 카드는 `rounded-lg border bg-muted/30 p-3`라 TradeDetail의 readout 카드(`rounded-2xl bg-muted/60 p-4`)와 어긋남

애니메이션은 `FullScreenPanel`(300ms cubic-bezier slide)이 이미 동일하므로 그대로 둔다.

## 목표

- ImportTradesPanel의 각 step이 TradeFormPanel/TradeEditPanel/TradeDetail과 **동일한 본문+sticky 푸터 구조**로 동작한다.
- 메인 액션 버튼이 모두 `size="xl"` 풀-와이드(또는 `flex-1` 분할)로 sticky 하단 영역에 위치하고, safe-area-inset-bottom이 적용된다.
- 본문은 좌우 `px-5` 패딩 + `space-y-5` 수직 간격을 유지해 다른 판넬과 동일한 여백 리듬을 갖는다.
- 헤더 타이틀이 다른 판넬과 동일하게 단순 제목(`"거래 일괄 등록"`)으로 통일된다 — step명은 헤더에서 제거하고, 필요 시 본문 상단의 보조 텍스트로 이전.
- PreviewStep의 "등록 대상 계좌" 카드가 TradeDetail readout 스타일(`rounded-2xl bg-muted/60 p-4`)과 일치한다.
- 기능/흐름은 변경하지 않는다.

## 설계

### 접근 방식

#### A. 공통 래퍼 패턴 (모든 step)

각 step 컴포넌트를 **TradeBasicForm 패턴**으로 재구조화한다 (가장 가까운 동급 사례 — wizard step + sticky 풀-와이드 버튼).

```tsx
<div className="flex flex-col min-h-full">
  <div className="flex-1 px-5 pt-2 pb-4 space-y-5">
    {/* 본문 */}
  </div>
  <div
    className="sticky bottom-0 bg-background px-5 pt-3 pb-4"
    style={{ paddingBottom: "calc(1rem + env(safe-area-inset-bottom))" }}
  >
    <Button size="xl" className="w-full" ...>...</Button>
  </div>
</div>
```

`FullScreenPanelBody`는 이미 `flex-1 overflow-y-auto`이므로 그 안에 `min-h-full` 자식을 두면 sticky bottom이 정상 동작한다(TradeBasicForm·TradeMetaBuyForm·TradeEditPanel에서 동일 검증).

#### B. step별 적용

- **AccountStep**: 위 래퍼. 푸터 버튼 `size="xl" w-full` "다음".
  - 계좌 0개 분기는 본문 안에 안내 카드만 두고, 푸터에는 비활성 풀-와이드 "다음" 버튼을 그대로 노출 — 4개 step 모두 sticky 풀-와이드 풋터 리듬을 유지.
- **FileStep**: 위 래퍼. 명시적 "다음" 버튼이 없는 자동 진행 step이지만, 시각적 리듬을 위해 sticky 영역을 비활성 풀-와이드 XL 버튼으로 채운다.
  - 파일 선택 전: 비활성 `"파일을 선택해주세요"` 버튼 (드롭존이 실제 trigger).
  - `isLoading` 동안: 비활성 `"분석 중..."` 버튼.
  - 버튼 자체에는 click handler를 두지 않는다 (드롭존 클릭이 진입점, 버튼은 상태 표시 역할).
- **PreviewStep**: 위 래퍼. 푸터 버튼 `size="xl" w-full` "{N}건 등록하기". `disabled` 조건(`new_count === 0 || isLoading`)·`isLoading` 라벨 그대로.
- **ResultStep**: 위 래퍼. 푸터 버튼 `size="xl" w-full` "닫기". 본문은 중앙 정렬(`flex-1 flex flex-col items-center justify-center text-center`)로 두어 결과 아이콘·메시지가 수직 가운데 배치되도록 한다 (현재 `py-4`은 제거 — 패딩은 wrapper의 `pt-2 pb-4`로 일원화).

#### C. 헤더 타이틀 단순화

`ImportTradesPanel/index.tsx`의 `<FullScreenPanelHeader title={`거래 일괄 등록 — ${stepTitle[step]}`} />` → `<FullScreenPanelHeader title="거래 일괄 등록" />`로 변경.

step별 컨텍스트가 필요하면 각 step **본문 최상단**에 `text-sm text-muted-foreground` 한 줄로 보조 안내를 두는 것을 우선한다 (이미 AccountStep·PreviewStep·FileStep 안내 문구가 그 역할 수행 중). step 라벨을 헤더에서 제거하더라도 사용자 혼동이 없도록 본문 도입부 문구가 step 의도를 충분히 설명하는지만 확인하고, 부족하면 한 줄을 추가한다 (예: ResultStep 도입부에 "등록 결과" 보조 문구 추가 검토).

`stepTitle` 매핑은 사용처가 사라지므로 제거.

#### D. PreviewStep "등록 대상 계좌" 카드 정렬

현재:
```tsx
<div className="flex items-center gap-3 rounded-lg border bg-muted/30 p-3">
  <BrokerLogo broker={account.broker} size={32} />
  ...
</div>
```

→ TradeDetail readout 토큰으로 정렬:
```tsx
<div className="flex items-center gap-3 rounded-2xl bg-muted/60 p-4">
  <BrokerLogo broker={account.broker} size={32} />
  ...
</div>
```

(border 제거, radius `rounded-lg` → `rounded-2xl`, bg `bg-muted/30` → `bg-muted/60`, padding `p-3` → `p-4`).

상위 `등록 대상 계좌` 라벨은 `text-sm font-medium` 그대로 유지.

#### E. 의도적으로 그대로 두는 항목

- **AccountStep 계좌 옵션 카드** (`rounded-lg border p-3`): 클릭 가능한 옵션 카드라는 의미가 명확. radio-style border가 선택 상태(`border-primary bg-primary/5`)·비활성 상태(`bg-muted/30 opacity-60`)의 시각 표현으로 필수.
- **FileStep 드롭존** (`border-2 border-dashed`): 드래그 앤 드롭 시그널.
- **PreviewStep `CountCard`** (`rounded-lg border bg-card`): 통계 카드 표현.
- **PreviewStep 경고 박스/오류 토글**: 의미적 색(yellow)·접고 펼치기 인터랙션 그대로.

이들은 "동일성"의 대상이 아니라 각 step 고유 의미를 표현하는 컴포넌트이므로, 일괄 통일 시 의미 손실 발생.

### 주요 변경 파일

- `app/src/components/records/ImportTradesPanel/index.tsx` — 헤더 title을 `"거래 일괄 등록"`로 단순화, `stepTitle` 매핑 제거.
- `app/src/components/records/ImportTradesPanel/AccountStep.tsx` — 래퍼 패턴 적용, 풀-와이드 sticky "다음" 버튼. 계좌 0개 분기는 본문 안내 + 비활성 sticky 버튼.
- `app/src/components/records/ImportTradesPanel/FileStep.tsx` — 래퍼 패턴 적용, 비활성 풀-와이드 sticky 버튼(`"파일을 선택해주세요"` / `isLoading` 시 `"분석 중..."`).
- `app/src/components/records/ImportTradesPanel/PreviewStep.tsx` — 래퍼 패턴 적용, 풀-와이드 sticky "{N}건 등록하기" 버튼, "등록 대상 계좌" 카드 토큰 정렬(`rounded-2xl bg-muted/60 p-4`).
- `app/src/components/records/ImportTradesPanel/ResultStep.tsx` — 래퍼 패턴 적용, 풀-와이드 sticky "닫기" 버튼, 본문 중앙 정렬 보존.

### 재사용할 기존 자산

- `Button` (`@/components/base/Button`) — `size="xl"` variant.
- `BrokerLogo` (`@/components/base/BrokerLogo`).
- `FullScreenPanel*` 래퍼 — 변경 없음.
- safe-area 인라인 스타일 패턴 — 별도 헬퍼 추출 없이 4곳에 동일 인라인 사용 (다른 판넬과 일관).

## 구현 체크리스트

- [x] `ImportTradesPanel/index.tsx` — `FullScreenPanelHeader title`을 `"거래 일괄 등록"`로 단순화, `stepTitle` 매핑 제거.
- [x] `AccountStep.tsx` — 래퍼 `flex flex-col min-h-full` + 본문 `flex-1 px-5 pt-2 pb-4 space-y-5` + sticky 풀-와이드 `size="xl"` "다음" 버튼. 계좌 0개 케이스에서도 풋터 렌더(비활성 버튼).
- [x] `FileStep.tsx` — 래퍼 + 본문 + sticky 영역에 풀-와이드 `size="xl"` 버튼. simplify 단계에서 a11y 개선: 클릭 시 파일 픽커 트리거, `isLoading`에만 disabled (라벨 `"분석 중..."` / 그 외 `"파일을 선택해주세요"`).
- [x] `PreviewStep.tsx` — 래퍼 + 본문 + sticky 풀-와이드 `size="xl"` "{N}건 등록하기" 버튼. "등록 대상 계좌" 카드 클래스를 `rounded-2xl bg-muted/60 p-4`로 변경(border 제거).
- [x] `ResultStep.tsx` — 래퍼 + 본문(중앙 정렬: `flex-1 flex flex-col items-center justify-center text-center space-y-5`) + sticky 풀-와이드 `size="xl"` "닫기" 버튼. 기존 `py-4`/`mt-2` 제거.
- [x] iOS/모바일 뷰포트(devtools)에서 4개 step 모두 sticky 버튼이 하단에 고정되고 safe-area-inset-bottom이 반영되는지 확인.
- [x] 거래 등록(`TradeFormPanel`) → 거래 상세(`TradeDetail`) → 일괄 등록을 연속 열어 헤더 타이틀·본문 패딩·풀-와이드 XL 버튼·하단 여백이 동일한지 시각 비교.
- [x] step 흐름 회귀 — account 선택 → 다음 → 파일 업로드(자동 진행) → 미리보기 → 등록 → 결과 → 닫기.
- [x] 타입 체크 통과 (`pnpm -C app exec tsc --noEmit`).

## 검증 방법

1. `pnpm dev` 기동 → http://localhost:3000 → 거래 → "일괄 등록" 진입.
2. 4개 step 각각에서 다음 시각 확인:
   - 헤더 타이틀이 `"거래 일괄 등록"`로 step 무관하게 동일.
   - 본문이 `px-5 pt-2 pb-4 space-y-5` 패딩/간격을 가짐 (다른 판넬과 동일한 여백).
   - 메인 액션 버튼이 화면 하단에 풀-와이드 sticky로 고정 (FileStep도 비활성 버튼으로 자리 채움).
   - safe-area 영역(노치)이 있는 시뮬레이터에서 버튼 하단 패딩 자동 확장.
3. 거래 등록(`TradeFormPanel`) → 거래 상세(`TradeDetail`) → 일괄 등록을 연속 열어 풀-와이드 XL 버튼·하단 여백·본문 패딩이 시각적으로 동일.
4. PreviewStep에서 "등록 대상 계좌" 카드가 TradeDetail의 readout 카드(예: 종목 헤더 카드)와 동일한 radius/배경 톤으로 보이는지 확인.
5. 계좌 0개 상태 진입 — 본문 안내가 보이고, 풀-와이드 "다음" 버튼이 비활성 상태로 sticky 노출.
6. `pnpm -C app exec tsc --noEmit` 통과.

## 우려사항 / 리스크

- `min-h-full`이 `FullScreenPanelBody`(`flex-1 overflow-y-auto`) 내부에서 의도대로 동작해야 sticky가 붙음. TradeBasicForm·TradeEditPanel에서 동일 조합이 사용 중이라 회귀 가능성 낮음.
- ResultStep의 중앙 정렬이 `min-h-full`/`flex-1` 조합과 어울리는지 실측 — 본문이 짧을 때 수직 가운데 배치가 자연스러운지 확인. 어색하면 `justify-center` 제거하고 상단 정렬로 fallback.
- 헤더에서 step명을 제거하는 변화로 사용자가 "현재 어느 단계인지" 인지하기 어려워질 수 있음. 본문 도입부 안내 문구가 충분한지 4개 step 모두 점검 — 부족하면 ResultStep 등에 한 줄 보조 텍스트 추가.
- 카드 디자인 추가 토큰화(예: AccountStep 옵션 카드 → `rounded-xl bg-muted/60`)는 본 spec 범위 외 — 의미 변화가 발생하므로 의도적으로 제외.
