"use client";

import { useEffect } from "react";
import { useRouter } from "next/navigation";
import { setSession, exchangeCodeForSession } from "@/lib/auth";
import { isNativePlatform } from "@/lib/platform";
import { NATIVE_URL_SCHEME, NATIVE_CALLBACK_HOST } from "@/lib/auth/oauth-config";
import { LOGIN_OAUTH_FAILED_PATH_WITH_SLASH } from "@/lib/auth/errors";

export const OAUTH_BROWSER_FINISHED_EVENT = "oauth:browser-finished";

export function CapacitorDeepLinkHandler() {
  const router = useRouter();

  useEffect(() => {
    if (!isNativePlatform()) return;

    let cancelled = false;
    let appRemove: (() => void) | undefined;
    let browserRemove: (() => void) | undefined;

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

      await closeBrowser().catch(() => {});

      const errorDesc = url.searchParams.get("error_description");
      if (errorDesc) {
        router.replace(`/login/?error=${encodeURIComponent(errorDesc)}`);
        return;
      }

      // Implicit flow: fragment에 access_token/refresh_token 이 담겨 돌아옴
      const hash = url.hash.startsWith("#") ? url.hash.slice(1) : url.hash;
      if (hash) {
        const hashParams = new URLSearchParams(hash);
        const accessToken = hashParams.get("access_token");
        const refreshToken = hashParams.get("refresh_token");
        if (accessToken && refreshToken) {
          try {
            await setSession(accessToken, refreshToken);
            router.replace("/");
            return;
          } catch {
            router.replace(LOGIN_OAUTH_FAILED_PATH_WITH_SLASH);
            return;
          }
        }
      }

      // PKCE flow: ?code=... 로 돌아옴
      const code = url.searchParams.get("code");
      if (!code) {
        router.replace(LOGIN_OAUTH_FAILED_PATH_WITH_SLASH);
        return;
      }

      try {
        await exchangeCodeForSession(code);
        router.replace("/");
      } catch {
        router.replace(LOGIN_OAUTH_FAILED_PATH_WITH_SLASH);
      }
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
