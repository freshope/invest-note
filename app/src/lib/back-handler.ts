/**
 * Android 하드웨어 백버튼이 닫아야 할 오버레이의 LIFO 스택.
 *
 * radix 계열(Dialog/Drawer, z-[200])은 DismissableLayer 가 Escape 로 스스로 닫으므로
 * 등록 대상이 아니다. 여기 등록되는 것은 자체 구현 오버레이인 FullScreenPanel(z-[100]) 뿐이며,
 * 백버튼 처리 순서(radix → 이 스택)는 그 z-index 계약을 그대로 따른다.
 */
const handlers: Array<() => void> = [];

/** 오버레이가 열려 있는 동안 닫기 함수를 등록한다. 반환값은 해제 함수. */
export function pushBackHandler(handler: () => void): () => void {
  handlers.push(handler);
  return () => {
    // 중첩 패널이 항상 역순으로 언마운트되지는 않으므로 pop 이 아니라 identity 로 제거한다.
    const index = handlers.indexOf(handler);
    if (index >= 0) handlers.splice(index, 1);
  };
}

/** 최상위 핸들러를 실행한다. 실행할 것이 없으면 false. */
export function runTopBackHandler(): boolean {
  const handler = handlers.at(-1);
  if (!handler) return false;
  handler();
  return true;
}
