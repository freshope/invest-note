"use client";

import { useEffect } from "react";
import { useAppVersion } from "@/hooks/useAppVersion";
import { registerAppVersion } from "@/lib/analytics";

/**
 * 앱 버전 → PostHog super property 브리지.
 * useAppVersion 은 네이티브/OTA 버전을 비동기로 채우므로, 값이 확정되면 register 한다.
 * - app_version: OTA 반영 실제 실행 버전 (번들 적용 시 그 값, 아니면 네이티브)
 * - native_version / native_build: 스토어 라이브 바이너리 기준 점유율
 */
export function PostHogVersionBridge() {
  const { version, nativeVersion, build, ready } = useAppVersion();

  useEffect(() => {
    registerAppVersion({
      app_version: version,
      native_version: nativeVersion,
      native_build: build,
      ready,
    });
  }, [version, nativeVersion, build, ready]);

  return null;
}
