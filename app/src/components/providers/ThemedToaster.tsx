"use client";

import { useTheme } from "next-themes";
import { Toaster } from "sonner";
import { DEFAULT_THEME, type Theme } from "@/lib/constants/theme";

export function ThemedToaster() {
  const { resolvedTheme } = useTheme();
  return (
    <Toaster
      position="top-center"
      offset="16px"
      mobileOffset={{
        top: "calc(env(safe-area-inset-top) + 16px)",
        right: "16px",
        bottom: "16px",
        left: "16px",
      }}
      richColors
      theme={(resolvedTheme ?? DEFAULT_THEME) as Theme}
    />
  );
}
