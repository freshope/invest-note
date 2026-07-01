/**
 * 거래 등록 폼 딥링크용 1회성 모듈 플래그 + 구독.
 * import-deeplink 와 동일 패턴 — TradeFormPanel 상태는 TradeList 내부 지역 상태라
 * 홈 빈 상태 CTA 등 외부에서 직접 열 수 없어 모듈 플래그로 신호를 넘긴다.
 *
 * 교차 라우트(홈→/records): TradeList 가 마운트 시 consumeTradeFormOpen() 으로 소비.
 * 동일 라우트(이미 /records): requestTradeFormOpen() 이 listener 를 즉시 호출.
 */

let pending = false;
let listener: (() => void) | null = null;

export function requestTradeFormOpen(): void {
  pending = true;
  listener?.();
}

export function consumeTradeFormOpen(): boolean {
  if (!pending) return false;
  pending = false;
  return true;
}

export function subscribeTradeFormOpen(fn: () => void): () => void {
  listener = fn;
  return () => {
    if (listener === fn) listener = null;
  };
}
