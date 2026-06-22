import { useEffect, useState } from "react";
import { isNativePlatform } from "@/lib/platform";

type AppVersion = {
  version: string;
  build: string | null;
  ready: boolean;
  // OTA 와 무관한 네이티브 바이너리 마케팅 버전(스토어 라이브 버전). version 이 OTA 번들로
  // 덮인 경우와 구분해 분석(점유율)에서 따로 집계하기 위해 노출한다.
  nativeVersion: string;
};

const FALLBACK_VERSION = process.env.NEXT_PUBLIC_APP_VERSION ?? "";

export function useAppVersion(): AppVersion {
  const [info, setInfo] = useState<AppVersion>({
    version: FALLBACK_VERSION,
    build: null,
    ready: false,
    // 네이티브 버전은 App.getInfo() 로만 확정한다. fallback(JS 번들 pkg.version)으로 시드하면
    // 웹/getInfo 미보정 단말에서 번들 버전이 native_version 으로 새어(스토어 1.2.1 단말이
    // OTA 1.2.x 번들을 돌릴 때 native_version 에 1.2.x 가 찍힘) 분석을 오염시킨다.
    nativeVersion: "",
  });

  useEffect(() => {
    if (!isNativePlatform()) {
      setInfo((current) => ({ ...current, ready: true }));
      return;
    }
    let cancelled = false;
    (async () => {
      let nativeVersion = "";
      let build: string | null = null;
      let version = FALLBACK_VERSION;
      try {
        const { App } = await import("@capacitor/app");
        const native = await App.getInfo();
        // App.getInfo().version 은 네이티브 바이너리 마케팅 버전이라 OTA 후에도 안 바뀐다.
        nativeVersion = native.version;
        build = native.build;
        version = native.version;
      } catch {
        // getInfo 미가용/오류 — 네이티브 버전 미확정. native_version 은 빈 값으로 두어
        // 잘못된 값을 보고하지 않는다(app_version 은 번들 fallback 유지).
      }
      try {
        // OTA 로 적용된 web 번들이 있으면(= bundle.id 가 "builtin" 아님) 그 번들 버전을
        // app_version 으로 우선 표시. native_version/build 는 네이티브 바이너리 값 그대로 유지.
        const { CapacitorUpdater } = await import("@capgo/capacitor-updater");
        const current = await CapacitorUpdater.current();
        if (current.bundle.id !== "builtin" && current.bundle.version) {
          version = current.bundle.version;
        }
      } catch {
        // 플러그인 미가용/오류 — fail-open.
      }
      if (!cancelled) {
        setInfo({ version, build, nativeVersion, ready: true });
      }
    })();
    return () => {
      cancelled = true;
    };
  }, []);

  return info;
}
