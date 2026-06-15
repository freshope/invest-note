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

/**
 * 앱 버전을 super property 로 등록 → 이후 모든 이벤트에 부착되어 PostHog 에서 버전별 점유율 집계.
 * 빈 값은 보내지 않는다(웹/초기 부팅 시 미상 값으로 차원 오염 방지).
 */
export function registerAppVersion(props: {
  app_version: string;
  native_version: string;
  native_build: string | null;
}) {
  if (!POSTHOG_ENABLED) return;
  const toRegister: Record<string, string> = {};
  if (props.app_version) toRegister.app_version = props.app_version;
  if (props.native_version) toRegister.native_version = props.native_version;
  if (props.native_build) toRegister.native_build = props.native_build;
  if (Object.keys(toRegister).length > 0) posthog.register(toRegister);
}
