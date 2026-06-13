import { useEffect, useState } from "react";
import { isNativePlatform } from "@/lib/platform";

type AppVersion = { version: string; build: string | null };

const FALLBACK_VERSION = process.env.NEXT_PUBLIC_APP_VERSION ?? "";

export function useAppVersion(): AppVersion {
  const [info, setInfo] = useState<AppVersion>({
    version: FALLBACK_VERSION,
    build: null,
  });

  useEffect(() => {
    if (!isNativePlatform()) return;
    let cancelled = false;
    (async () => {
      const { App } = await import("@capacitor/app");
      const native = await App.getInfo();
      // App.getInfo().version 은 네이티브 바이너리 마케팅 버전이라 OTA 후에도 안 바뀐다.
      // OTA 로 적용된 web 번들이 있으면(= bundle.id 가 "builtin" 아님) 그 번들 버전을
      // 우선 표시한다. 빌드번호(native.build)는 네이티브 바이너리 값이라 그대로 유지.
      let version = native.version;
      try {
        const { CapacitorUpdater } = await import("@capgo/capacitor-updater");
        const current = await CapacitorUpdater.current();
        if (current.bundle.id !== "builtin" && current.bundle.version) {
          version = current.bundle.version;
        }
      } catch {
        // 플러그인 미가용/오류 — 네이티브 버전으로 폴백(fail-open).
      }
      if (!cancelled) {
        setInfo({ version, build: native.build });
      }
    })();
    return () => {
      cancelled = true;
    };
  }, []);

  return info;
}
