/**
 * 가져오기(일괄등록) 화면 딥링크용 1회성 모듈 플래그 + 구독.
 * import 패널 상태는 TradeList 내부 지역 상태라 외부에서 직접 열 수 없다.
 * output:"export" 환경이라 useSearchParams 는 Suspense 경계가 필요해, 라우팅 쿼리 대신
 * 모듈 플래그로 신호를 넘긴다.
 *
 * 교차 라우트(다른 화면→/records): TradeList 가 마운트 시 consumeImportOpen() 으로 소비.
 * 동일 라우트(이미 /records): router.push 가 no-op 이라 마운트가 없으므로, requestImportOpen()
 * 이 listener 를 즉시 호출 → 마운트된 TradeList 가 consume. 둘 다 플래그를 소비해 잔존 방지.
 */

let pending = false;
let listener: (() => void) | null = null;

export function requestImportOpen(): void {
  pending = true;
  listener?.();
}

export function consumeImportOpen(): boolean {
  if (!pending) return false;
  pending = false;
  return true;
}

export function subscribeImportOpen(fn: () => void): () => void {
  listener = fn;
  return () => {
    if (listener === fn) listener = null;
  };
}
