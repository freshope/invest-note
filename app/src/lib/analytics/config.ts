import type { CaptureResult } from "posthog-js";

/** PostHog(제품 분석) 설정. key 없으면 전체 비활성(no-op) — 로컬/CI 에서 키 없이도 빌드·동작. */
export const POSTHOG_KEY = process.env.NEXT_PUBLIC_POSTHOG_KEY ?? "";
export const POSTHOG_HOST =
  process.env.NEXT_PUBLIC_POSTHOG_HOST ?? "https://us.i.posthog.com";
export const POSTHOG_ENABLED = POSTHOG_KEY.length > 0;

// PostHog 필터용 super property. 같은 프로젝트에 dev/prod 데이터가 섞여도 environment 로 분리.
// env 명시값 우선, 없으면 NODE_ENV(dev 서버=development, 빌드=production)로 자동 판별.
export const POSTHOG_ENV =
  process.env.NEXT_PUBLIC_POSTHOG_ENV ??
  (process.env.NODE_ENV === "production" ? "production" : "development");
export const POSTHOG_PROJECT = "invest-note-app";

/**
 * 금융 민감값 차단 키 목록. property_denylist(전송 전 키 제거)와 scrubEvent 양쪽에서 사용.
 * 종목/금액/수량/계좌명 등은 이벤트 프로퍼티로 절대 전송하지 않는다.
 */
export const DENYLIST = [
  "price",
  "amount",
  "quantity",
  "commission",
  "tax",
  "exchange_rate",
  "ticker_symbol",
  "asset_name",
  "account_name",
  "email",
];

/**
 * before_send 훅(런타임 1차 방어선). property_denylist 와 더해 2중으로 민감 키를 제거한다.
 * 명시적으로 골라 보내는 게 원칙이지만, 실수로 섞인 민감 키를 전송 직전에 한 번 더 거른다.
 */
export function scrubEvent(event: CaptureResult | null): CaptureResult | null {
  if (!event?.properties) return event;
  for (const key of DENYLIST) {
    if (key in event.properties) delete event.properties[key];
  }
  return event;
}
