/**
 * 푸시 알림 등록.
 *
 * 로그인 후 호출: 권한 요청 → FCM 토큰 발급 → BE(`POST /v1/me/push-token`)에 전송.
 * 알림 탭(notificationActionPerformed) 시 알림 이력/딥링크로 라우팅한다(라우팅은 콜백 위임 —
 * router 는 React 소유).
 *
 * `@capacitor-firebase/messaging` 은 iOS/Android 모두 **FCM 토큰**을 돌려준다(iOS 는 내부적으로
 * APNs 등록을 선행). 서버도 Firebase Admin 단일 채널로 발송하므로 두 플랫폼의 토큰 형식이 같다.
 *
 * 가드:
 * - 웹/미지원 플랫폼에서는 no-op(네이티브 Capacitor 에서만 동작).
 * - 플러그인 로드·권한·토큰 전송 실패가 앱 흐름을 깨지 않게 전부 best-effort(예외 삼킴).
 * - Android 13+ POST_NOTIFICATIONS 런타임 권한은 requestPermissions 가 처리.
 */
import { isNativePlatform, getPlatform } from "@/lib/platform";
import { meApi } from "@/lib/api-client";

// 리스너 중복 등록 방지(재마운트/재로그인 시 1회만).
let started = false;

interface RegisterPushOptions {
  /** 푸시 알림 탭 시 호출 — 알림 이력 패널 오픈/딥링크(router.push 등). */
  onNotificationTap?: () => void;
}

function sendToken(token: string): void {
  const platform = getPlatform();
  if (platform !== "ios" && platform !== "android") return;
  // 토큰 전송 실패가 앱 흐름을 깨지 않게 best-effort.
  void meApi.registerPushToken(token, platform).catch(() => {});
}

export async function registerPush(opts?: RegisterPushOptions): Promise<void> {
  // 웹/미지원 플랫폼 no-op.
  if (!isNativePlatform()) return;
  if (started) return;
  started = true;

  try {
    const { FirebaseMessaging } = await import("@capacitor-firebase/messaging");

    // 토큰 회전 리스너를 getToken() 이전에 붙인다(콜백 유실 방지).
    await FirebaseMessaging.addListener("tokenReceived", (event) => {
      sendToken(event.token);
    });

    // 알림 탭 → 알림 이력/딥링크. 실제 라우팅은 콜백에 위임.
    await FirebaseMessaging.addListener("notificationActionPerformed", () => {
      opts?.onNotificationTap?.();
    });

    // Android 13+ 런타임 권한 포함. 거부 시 토큰을 발급받지 않음.
    const perm = await FirebaseMessaging.requestPermissions();
    if (perm.receive !== "granted") return;

    const { token } = await FirebaseMessaging.getToken();
    if (token) sendToken(token);
  } catch {
    // 플러그인 로드/권한/등록 실패 — 앱 흐름 유지.
  }
}
