/**
 * 가져오기(일괄등록) 화면 딥링크 — 공용 신호 팩토리(createDeeplinkSignal) 기반.
 * import 패널 상태는 TradeList 내부 지역 상태라 외부에서 직접 열 수 없어 모듈 플래그로 신호를 넘긴다.
 */
import { createDeeplinkSignal } from "./deeplink-signal";

const signal = createDeeplinkSignal();

export const requestImportOpen = signal.request;
export const consumeImportOpen = signal.consume;
export const subscribeImportOpen = signal.subscribe;
