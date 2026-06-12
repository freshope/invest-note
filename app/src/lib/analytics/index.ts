import posthog from "posthog-js";
import { POSTHOG_ENABLED } from "./config";

/** PostHog 헬퍼. 비활성(key 없음) 시 전부 no-op — 호출부는 활성 여부를 신경 쓰지 않는다. */

export function capture(event: string, props?: Record<string, unknown>) {
  if (!POSTHOG_ENABLED) return;
  posthog.capture(event, props);
}

export function identifyUser(id: string) {
  if (!POSTHOG_ENABLED) return;
  posthog.identify(id); // UUID 만 — email 등 person property 미전송
}

export function resetUser() {
  if (!POSTHOG_ENABLED) return;
  posthog.reset();
}

export function capturePageview(pathname: string) {
  if (!POSTHOG_ENABLED) return;
  posthog.capture("$pageview", { $current_url: pathname });
}
