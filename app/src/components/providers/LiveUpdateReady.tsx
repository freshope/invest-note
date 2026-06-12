"use client";

import { useEffect } from "react";
import { isNativePlatform } from "@/lib/platform";

/**
 * 네이티브 앱 부팅 직후 OTA 플러그인에 새 번들이 정상 기동했음을 알린다.
 * - `notifyAppReady()` 미호출 시 플러그인이 번들을 실패로 간주해 직전 번들로
 *   자동 롤백한다(롤백 루프 방지를 위해 필수).
 * - web 플랫폼은 no-op.
 */
export function LiveUpdateReady() {
  useEffect(() => {
    if (!isNativePlatform()) return;
    (async () => {
      try {
        const { CapacitorUpdater } = await import("@capgo/capacitor-updater");
        await CapacitorUpdater.notifyAppReady();
      } catch {
        // 실패해도 앱 부팅을 막지 않는다(fail-open).
      }
    })();
  }, []);

  return null;
}
