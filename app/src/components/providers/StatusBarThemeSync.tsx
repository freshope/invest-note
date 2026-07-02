"use client";

import { useEffect } from "react";
import { useTheme } from "next-themes";
import { isNativePlatform } from "@/lib/platform";

/**
 * 네이티브 StatusBar(텍스트색·배경)를 앱 테마(resolvedTheme)에 맞춘다.
 * - 다크: 밝은 텍스트(Style.Dark) + 어두운 배경(--background 다크값)
 * - 라이트: 어두운 텍스트(Style.Light) + 밝은 배경
 * - 배경색은 Android 에만 실효(iOS 는 no-op). setStyle 은 양 OS 적용.
 * - web 은 no-op.
 */
export function StatusBarThemeSync() {
  const { resolvedTheme } = useTheme();

  useEffect(() => {
    if (!isNativePlatform()) return;
    if (!resolvedTheme) return;
    const isDark = resolvedTheme === "dark";
    (async () => {
      try {
        const { StatusBar, Style } = await import("@capacitor/status-bar");
        await StatusBar.setStyle({ style: isDark ? Style.Dark : Style.Light });
        await StatusBar.setBackgroundColor({
          color: isDark ? "#17171C" : "#FFFFFF",
        });
      } catch {
        // 실패해도 앱 동작을 막지 않는다(fail-open).
      }
    })();
  }, [resolvedTheme]);

  return null;
}
