import posthog from "posthog-js";
import { POSTHOG_ENABLED } from "./config";

/** PostHog 헬퍼. 비활성(key 없음) 시 전부 no-op — 호출부는 활성 여부를 신경 쓰지 않는다. */

type AppVersionProps = {
  app_version: string;
  native_version: string;
  native_build: string | null;
  ready?: boolean;
};

type PendingCapture = {
  event: string;
  props?: Record<string, unknown>;
};

const MAX_PENDING_CAPTURES = 50;
const latestAppVersionProps: Record<string, string> = {};
const pendingCaptures: PendingCapture[] = [];
let appVersionResolved = false;

function registerLatestAppVersionProps() {
  if (Object.keys(latestAppVersionProps).length > 0) {
    posthog.register(latestAppVersionProps);
  }
}

function captureNow(event: string, props?: Record<string, unknown>) {
  posthog.capture(event, props);
}

function flushPendingCaptures() {
  if (pendingCaptures.length === 0) return;
  const captures = pendingCaptures.splice(0);
  captures.forEach(({ event, props }) => captureNow(event, props));
}

export function capture(event: string, props?: Record<string, unknown>) {
  if (!POSTHOG_ENABLED) return;
  if (!appVersionResolved) {
    if (pendingCaptures.length >= MAX_PENDING_CAPTURES) pendingCaptures.shift();
    pendingCaptures.push({ event, props });
    return;
  }
  captureNow(event, props);
}

export function identifyUser(id: string) {
  if (!POSTHOG_ENABLED) return;
  posthog.identify(id); // UUID 만 — email 등 person property 미전송
}

export function resetUser() {
  if (!POSTHOG_ENABLED) return;
  posthog.reset();
  registerLatestAppVersionProps();
}

export function capturePageview(pathname: string) {
  if (!POSTHOG_ENABLED) return;
  capture("$pageview", { $current_url: pathname });
}

/**
 * 앱 버전을 super property 로 등록 → 이후 모든 이벤트에 부착되어 PostHog 에서 버전별 점유율 집계.
 * 빈 값은 보내지 않는다(웹/초기 부팅 시 미상 값으로 차원 오염 방지).
 */
export function registerAppVersion(props: AppVersionProps) {
  if (!POSTHOG_ENABLED) return;
  const ready = props.ready ?? true;

  if (props.app_version) latestAppVersionProps.app_version = props.app_version;
  if (props.native_version) latestAppVersionProps.native_version = props.native_version;
  if (props.native_build) latestAppVersionProps.native_build = props.native_build;

  // 초기 부팅 중 빈 네이티브 값은 "미확정"이지 "없음"이 아니다. 확정 전에는 기존 값을 지우지 않는다.
  if (ready) {
    if (!props.native_version) delete latestAppVersionProps.native_version;
    if (!props.native_build) delete latestAppVersionProps.native_build;
  }

  registerLatestAppVersionProps();

  // 네이티브 버전 조회가 끝난 뒤에만 과거 persist 오염값을 제거한다.
  if (ready) {
    if (!props.native_version) posthog.unregister("native_version");
    if (!props.native_build) posthog.unregister("native_build");
    appVersionResolved = true;
    flushPendingCaptures();
  }
}
