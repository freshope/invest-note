/**
 * 등록 chooser 딥링크 — 공용 신호 팩토리(createDeeplinkSignal) 기반.
 * 등록 chooser(매수/매도/거래내역서 업로드) 상태는 TradeList 내부 지역 상태라 홈 빈상태 CTA 등
 * 외부에서 직접 열 수 없어 모듈 플래그로 신호를 넘긴다.
 */
import { createDeeplinkSignal } from "./deeplink-signal";

const signal = createDeeplinkSignal();

export const requestRegisterChooserOpen = signal.request;
export const consumeRegisterChooserOpen = signal.consume;
export const subscribeRegisterChooserOpen = signal.subscribe;
