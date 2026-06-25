import { isNativePlatform } from "@/lib/platform";

/**
 * 외부 URL 열기. 네이티브에서는 in-app browser(@capacitor/browser),
 * 웹에서는 새 탭으로 연다.
 */
export async function openExternal(url: string) {
  if (isNativePlatform()) {
    const { Browser } = await import("@capacitor/browser");
    await Browser.open({ url, presentationStyle: "popover" });
  } else {
    window.open(url, "_blank", "noopener");
  }
}
