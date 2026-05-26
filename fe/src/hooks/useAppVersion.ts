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
      if (!cancelled) {
        setInfo({ version: native.version, build: native.build });
      }
    })();
    return () => {
      cancelled = true;
    };
  }, []);

  return info;
}
