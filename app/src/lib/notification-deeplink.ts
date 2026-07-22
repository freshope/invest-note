/**
 * 알림 이력 패널 딥링크 — 공용 신호 팩토리(createDeeplinkSignal) 기반.
 * 알림 패널은 홈/설정 내부 지역 상태라 외부(푸시 탭 등)에서 직접 열 수 없어 모듈 플래그로 신호를 넘긴다.
 * 푸시 알림 탭(pushNotificationActionPerformed) → requestNotificationOpen() → 홈이 consume 해 패널 오픈.
 */
import { createDeeplinkSignal } from "./deeplink-signal";

const signal = createDeeplinkSignal();

export const requestNotificationOpen = signal.request;
export const consumeNotificationOpen = signal.consume;
export const subscribeNotificationOpen = signal.subscribe;
