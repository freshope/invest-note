export const DEFAULT_THEME = "system" as const;
export const THEME_ATTRIBUTE = "class" as const;

export type Theme = "light" | "dark" | typeof DEFAULT_THEME;
