"use client";

import { useEffect } from "react";
import { useRouter } from "next/navigation";
import { isNativePlatform } from "@/lib/platform";
import { NATIVE_URL_SCHEME, NATIVE_CALLBACK_HOST } from "@/lib/auth/oauth-config";
import { exchangeAndRoute } from "@/lib/auth/exchange-and-route";

export const OAUTH_BROWSER_FINISHED_EVENT = "oauth:browser-finished";

export function CapacitorDeepLinkHandler() {
  const router = useRouter();

  useEffect(() => {
    if (!isNativePlatform()) return;

    let cancelled = false;
    let appRemove: (() => void) | undefined;
    let browserRemove: (() => void) | undefined;
    // G4: getLaunchUrl(cold start)+appUrlOpen 이중 발화 dedup. code 는 일회용이라
    // 같은 URL 을 두 번 처리하면 두 번째가 실패 페이지로 덮어쓴다(OS 미중복 시 무해).
    const handledUrls = new Set<string>();

    const handleUrl = async (
      urlStr: string,
      closeBrowser: () => Promise<void>,
    ) => {
      let url: URL;
      try {
        url = new URL(urlStr);
      } catch {
        return;
      }

      if (
        url.protocol !== `${NATIVE_URL_SCHEME}:` ||
        url.hostname !== NATIVE_CALLBACK_HOST
      ) {
        return;
      }

      if (handledUrls.has(urlStr)) return;
      handledUrls.add(urlStr);

      await closeBrowser().catch(() => {});

      const errorDesc = url.searchParams.get("error_description");
      if (errorDesc) {
        router.replace(`/login/?error=${encodeURIComponent(errorDesc)}`);
        return;
      }

      // BE flow: 딥링크엔 일회용 code 만 온다(access/refresh 직접 미노출, C6/B4).
      // 웹 콜백 페이지와 동일한 post-code 라우팅(exchangeAndRoute 단일 출처).
      const code = url.searchParams.get("code");
      await exchangeAndRoute(code, router);
    };

    (async () => {
      const [{ App }, { Browser }] = await Promise.all([
        import("@capacitor/app"),
        import("@capacitor/browser"),
      ]);
      if (cancelled) return;

      const closeBrowser = () => Browser.close();

      // Cold start: 앱이 딥링크로 기동된 경우 launchUrl 우선 처리 (appUrlOpen 미발화 케이스)
      try {
        const launch = await App.getLaunchUrl();
        if (!cancelled && launch?.url) {
          await handleUrl(launch.url, closeBrowser);
        }
      } catch {
        // no-op
      }

      if (cancelled) return;

      const appListener = await App.addListener("appUrlOpen", (evt) => {
        void handleUrl(evt.url, closeBrowser);
      });
      appRemove = () => {
        void appListener.remove();
      };

      // 사용자가 브라우저를 수동으로 닫았을 때 login 페이지의 pending 상태 해제 용
      const browserListener = await Browser.addListener("browserFinished", () => {
        window.dispatchEvent(new CustomEvent(OAUTH_BROWSER_FINISHED_EVENT));
      });
      browserRemove = () => {
        void browserListener.remove();
      };
    })().catch(() => {
      // plugin 로드 실패 시 조용히 무시 (웹에서는 애초에 진입 안 함)
    });

    return () => {
      cancelled = true;
      appRemove?.();
      browserRemove?.();
    };
  }, [router]);

  return null;
}
