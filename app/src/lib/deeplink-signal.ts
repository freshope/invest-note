/**
 * 1회성 모듈 플래그 + 구독 신호 팩토리.
 *
 * import 패널·거래 등록 폼처럼 TradeList 내부 지역 상태라 외부(다른 라우트·홈 빈상태 CTA)에서
 * 직접 열 수 없는 화면을 딥링크로 여는 신호. output:"export" 환경이라 useSearchParams(Suspense
 * 경계 필요) 대신 모듈 플래그로 신호를 넘긴다.
 *
 * 교차 라우트(다른 화면→/records): 대상이 마운트 시 consume() 으로 소비.
 * 동일 라우트(이미 /records): router.push 가 no-op 이라 마운트가 없으므로 request() 가
 * listener 를 즉시 호출 → 마운트된 대상이 consume. 둘 다 플래그를 소비해 잔존 방지.
 */
export interface DeeplinkSignal {
  request: () => void;
  consume: () => boolean;
  subscribe: (fn: () => void) => () => void;
}

export function createDeeplinkSignal(): DeeplinkSignal {
  let pending = false;
  let listener: (() => void) | null = null;

  return {
    request() {
      pending = true;
      listener?.();
    },
    consume() {
      if (!pending) return false;
      pending = false;
      return true;
    },
    subscribe(fn) {
      listener = fn;
      return () => {
        if (listener === fn) listener = null;
      };
    },
  };
}
