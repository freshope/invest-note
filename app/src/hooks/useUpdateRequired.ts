"use client";

import { useEffect, useState } from "react";
import { isNativePlatform } from "@/lib/platform";
import { isUpdateRequired } from "@/lib/version";
import { fetchAppConfig } from "@/lib/api/app-config";

/**
 * 네이티브 강제 업데이트 필요 여부. `undefined`=판정 중, `false`=비강제, `true`=강제.
 * - 웹은 즉시 `false`. 조회/판정 실패 시 `false`(fail-open).
 * - `fetchAppConfig` 는 메모이즈되어 추가 네트워크가 발생하지 않는다.
 * ForceUpdateGate(차단 오버레이)와 MySubmissionsPopupGate(팝업 억제)가 동일 판정을 공유한다.
 */
export function useUpdateRequired(): boolean | undefined {
  const [required, setRequired] = useState<boolean | undefined>(undefined);

  useEffect(() => {
    if (!isNativePlatform()) {
      setRequired(false);
      return;
    }
    let cancelled = false;
    (async () => {
      try {
        const { App } = await import("@capacitor/app");
        const [config, info] = await Promise.all([
          fetchAppConfig(),
          App.getInfo(),
        ]);
        if (cancelled) return;
        setRequired(isUpdateRequired(info.version, config.minSupportedVersion));
      } catch {
        // fail-open: 판정 실패 시 강제 아님으로 간주.
        if (!cancelled) setRequired(false);
      }
    })();
    return () => {
      cancelled = true;
    };
  }, []);

  return required;
}
