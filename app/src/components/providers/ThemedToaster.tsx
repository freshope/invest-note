"use client";

import { useTheme } from "next-themes";
import { Toaster } from "sonner";
import { DEFAULT_THEME, type Theme } from "@/lib/constants/theme";

export function ThemedToaster() {
  const { resolvedTheme } = useTheme();
  return (
    <Toaster
      position="top-center"
      richColors
      theme={(resolvedTheme ?? DEFAULT_THEME) as Theme}
    />
  );
}
