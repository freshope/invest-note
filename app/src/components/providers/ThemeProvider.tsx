"use client";

import { ThemeProvider as NextThemesProvider } from "next-themes";
import { DEFAULT_THEME, THEME_ATTRIBUTE } from "@/lib/constants/theme";

export function ThemeProvider({ children }: { children: React.ReactNode }) {
  return (
    <NextThemesProvider
      attribute={THEME_ATTRIBUTE}
      defaultTheme={DEFAULT_THEME}
      enableSystem
      disableTransitionOnChange
    >
      {children}
    </NextThemesProvider>
  );
}
