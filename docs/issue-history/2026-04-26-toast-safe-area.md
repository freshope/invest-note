# Spec: 토스트 Safe Area 보정

> Completed: 2026-04-26

## Background / Problem

기록 탭에서 파일 업로드 버튼을 눌렀을 때 표시되는 토스트가 iPhone 상단 카메라/Dynamic Island 영역과 겹쳐 보인다. 앱은 `viewportFit: "cover"`를 사용하므로 상단 토스트 위치에도 iOS safe area inset을 반영해야 한다.

## Goals

- 파일 업로드 토스트가 iPhone 상단 safe area 아래에 표시된다.
- 전역 토스트 위치를 보정해 같은 문제가 다른 상단 토스트에서도 재발하지 않는다.
- 기존 토스트 테마 동기화와 `top-center` 위치는 유지한다.

## Design

### Approach

전역 `ThemedToaster`의 sonner `<Toaster />`에 `offset`과 `mobileOffset`을 명시한다. 모바일 상단 offset은 `calc(env(safe-area-inset-top) + 16px)`로 설정해 notch/Dynamic Island 영역을 피한다.

### Primary Files

- `app/src/components/providers/ThemedToaster.tsx` - sonner Toaster의 desktop/mobile offset 설정

## Implementation Checklist

- [x] `ThemedToaster`에 safe-area-aware offset 추가
- [x] Type check passes (`pnpm tsc --noEmit`)

## Risks / Open Questions

- 실제 iPhone 기기/시뮬레이터에서 safe area 적용 여부를 수동 확인해야 한다.
