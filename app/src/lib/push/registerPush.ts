/**
 * 푸시 알림 등록(Phase 2, 활성화 게이트).
 *
 * 로그인 후 호출: 권한 요청 → 등록 → registration 토큰을 BE(`POST /v1/me/push-token`)에 전송.
 * 알림 탭(pushNotificationActionPerformed) 시 알림 이력/딥링크로 라우팅한다(라우팅은 콜백 위임 — router 는 React 소유).
 *
 * 가드:
 * - 웹/미지원 플랫폼에서는 no-op(네이티브 Capacitor 에서만 동작).
 * - 플러그인 로드·권한·토큰 전송 실패가 앱 흐름을 깨지 않게 전부 best-effort(예외 삼킴).
 * - Android 13+ POST_NOTIFICATIONS 런타임 권한은 requestPermissions 가 처리.
 * - iOS 실제 수신은 aps-environment=production 승격 + 시크릿(FCM/APNs) 활성화가 전제(게이트).
 */
import { isNativePlatform, getPlatform } from "@/lib/platform";
import { meApi } from "@/lib/api-client";

// 리스너 중복 등록 방지(재마운트/재로그인 시 1회만).
let started = false;

interface RegisterPushOptions {
  /** 푸시 알림 탭 시 호출 — 알림 이력 패널 오픈/딥링크(router.push 등). */
  onNotificationTap?: () => void;
}

export async function registerPush(opts?: RegisterPushOptions): Promise<void> {
  // 웹/미지원 플랫폼 no-op.
  if (!isNativePlatform()) return;
  if (started) return;
  started = true;

  try {
    const { PushNotifications } = await import("@capacitor/push-notifications");

    // registration 리스너를 register() 이전에 붙인다(토큰 콜백 유실 방지).
    await PushNotifications.addListener("registration", (token) => {
      const platform = getPlatform();
      if (platform !== "ios" && platform !== "android") return;
      // 토큰 전송 실패가 앱 흐름을 깨지 않게 best-effort.
      void meApi.registerPushToken(token.value, platform).catch(() => {});
    });

    // 등록 오류(미지원/시크릿 미설정 등)는 조용히 무시.
    await PushNotifications.addListener("registrationError", () => {});

    // 알림 탭 → 알림 이력/딥링크. 실제 라우팅은 콜백에 위임.
    await PushNotifications.addListener(
      "pushNotificationActionPerformed",
      () => {
        opts?.onNotificationTap?.();
      },
    );

    // Android 13+ 런타임 권한 포함. 거부 시 register 하지 않음.
    const perm = await PushNotifications.requestPermissions();
    if (perm.receive !== "granted") return;

    await PushNotifications.register();
  } catch {
    // 플러그인 로드/권한/등록 실패 — 앱 흐름 유지.
  }
}
