> 완료: 2026-04-22

# Spec: 증권사 로고 UI 반영

## 배경 / 문제

`public/logos/securities/` 에 24개 증권사 로고(.svg) 자산이 추가되었지만 현재 UI는 증권사명을 순수 텍스트(또는 색 배지 + 짧은 한글)로만 표시한다. 계좌 등록 시 증권사 선택 카드에 로고를 도입하고, 증권사명이 표시되는 모든 UI에 로고를 반영해 브랜드 식별성과 스캔 속도를 높인다.

## 목표

- `설정 > 계좌 추가` 의 증권사 선택 그리드가 24개 증권사 로고로 표시된다.
- 기록 탭의 거래 카드·상세·편집 패널·계좌 선택 Select, 설정 탭의 계좌 카드에서 증권사 텍스트(`· 미래에셋증권` 등)가 제거되고 `[로고] 계좌명` 형태로 표시된다.
- 매칭 실패(오타·미등록 브로커 레코드) 시 기존 색 원형 배지가 fallback 으로 렌더된다.
- 로고 이미지는 `.svg` 만 사용한다.
- `pnpm tsc --noEmit` 통과.

## 설계

### 접근 방식

1. 증권사 데이터를 `src/lib/brokers.ts` 로 일원화 (한글명·슬러그·색·단축명 24개).
2. 로고 렌더 전담 base 컴포넌트 `src/components/base/BrokerLogo.tsx` 신설 (plain `<img>` 로 `/logos/securities/{slug}.svg` 렌더, 매칭 실패 시 기존 색 배지 fallback).
3. 하드코딩된 `AccountFormPanel` 의 BROKERS 는 lib 에서 import, 선택 카드를 로고 기반으로 교체.
4. 나머지 5곳은 `[로고] 계좌명` 포맷으로 통일 (broker 텍스트 suffix 제거).

### 주요 변경 파일

- `src/lib/brokers.ts` (신규) — 24개 증권사 마스터 목록 + `findBroker(name)` 헬퍼.
- `src/components/base/BrokerLogo.tsx` (신규) — 로고 컴포넌트. plain `<img>` + fallback 배지.
- `src/components/settings/AccountFormPanel.tsx` — 하드코딩 BROKERS 제거, 선택 카드에 `BrokerLogo` 적용.
- `src/components/settings/AccountCard.tsx` — broker 텍스트 subtitle 제거, 계좌명 옆에 `BrokerLogo`.
- `src/components/records/TradeCard.tsx` — footer `· {broker}` 제거, 계좌명 앞에 `BrokerLogo`.
- `src/components/records/TradeDetail.tsx` — 계좌 행의 broker 텍스트 제거, `BrokerLogo` + 계좌명.
- `src/components/records/TradeBasicForm.tsx` — `SelectItem` 에 `BrokerLogo` 적용, 사용되지 않는 `items` prop 제거.
- `src/components/records/TradeEditPanel.tsx` — `accountDisplay` 문자열 변수 제거, JSX 로 `BrokerLogo` + 계좌명 헤더.

## 구현 체크리스트

- [x] `src/lib/brokers.ts` 생성 (24개 BROKERS + findBroker 헬퍼)
- [x] `src/components/base/BrokerLogo.tsx` 생성 (plain `<img>` + fallback 배지)
- [x] `src/components/settings/AccountFormPanel.tsx` — lib import 로 교체 + 선택 카드에 BrokerLogo
- [x] `src/components/settings/AccountCard.tsx` — broker subtitle 제거 + 계좌명 옆 BrokerLogo
- [x] `src/components/records/TradeCard.tsx` — footer 포맷을 `[로고] 계좌명` 으로 변경
- [x] `src/components/records/TradeDetail.tsx` — 계좌 행 포맷을 `[로고] 계좌명` 으로 변경
- [x] `src/components/records/TradeBasicForm.tsx` — SelectItem JSX + dead `items` prop 제거
- [x] `src/components/records/TradeEditPanel.tsx` — accountDisplay 문자열 → JSX 로 교체
- [x] 로컬 `pnpm dev` 로 각 화면 수동 확인 (피커 24개 로고, 카드/상세/폼/편집 인라인 포맷, fallback 동작)
- [x] `pnpm tsc --noEmit` 통과

## 우려사항 / 리스크

- `shadcn/ui` `SelectValue` 가 선택된 `SelectItem` 의 JSX 를 그대로 미러링할지 불확실. 문자열만 표시될 경우 대응 필요.
- `.svg` 로고 배경이 흰색이라 다크 모드에서 튈 수 있음. `rounded-full bg-white` 로 통일 후 실제 화면에서 시각 확인.
- DB에 기존 텍스트 표기와 다르게 저장된 레코드는 fallback 경로로 안전 처리.
