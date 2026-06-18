import posthog from "posthog-js";
import {
  POSTHOG_KEY,
  POSTHOG_HOST,
  POSTHOG_ENV,
  POSTHOG_PROJECT,
  DENYLIST,
  scrubEvent,
} from "@/lib/analytics/config";

// Next.js 가 클라이언트 부팅 시 자동 로드(import 불필요). 정적 export 에서도 클라이언트 전용으로 실행.
if (POSTHOG_KEY) {
  posthog.init(POSTHOG_KEY, {
    api_host: POSTHOG_HOST,
    persistence: "localStorage", // 웹뷰(capacitor://, https://localhost) 쿠키 불안정 회피
    autocapture: false, // 금융 입력 DOM 자동 캡처 차단
    capture_pageview: false, // usePathname 기반 수동 추적
    capture_pageleave: true, // 모바일 웹뷰는 unload 불안정 — 참고용
    person_profiles: "identified_only", // 익명 프로필 미생성(MAU·PII 축소)
    disable_session_recording: true, // 금융 앱 — 우발 활성화 차단
    // 전역 예외 자동 추적. console error 는 제외(민감 로그 누수 표면·이벤트 볼륨 축소 → 무료 한도 보호).
    // $exception 이벤트도 property_denylist/before_send 를 거치지만, message/stack 자유텍스트는 안 걸러짐(수용된 잔여 위험).
    capture_exceptions: {
      capture_unhandled_errors: true,
      capture_unhandled_rejections: true,
      capture_console_errors: false,
    },
    property_denylist: DENYLIST,
    before_send: scrubEvent,
  });
  // 모든 이벤트에 환경/프로젝트 부착 → PostHog 에서 필터로 dev/prod·앱 구분.
  posthog.register({ environment: POSTHOG_ENV, project: POSTHOG_PROJECT });
}
