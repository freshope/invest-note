"use client";

import { useEffect, useState } from "react";
import { useTheme } from "next-themes";
import { Monitor, Sun, Moon } from "lucide-react";
import { ToggleGroup, ToggleGroupItem } from "@/components/base/ToggleGroup";

const THEME_OPTIONS = [
  { value: "system", label: "시스템", icon: Monitor },
  { value: "light", label: "라이트", icon: Sun },
  { value: "dark", label: "다크", icon: Moon },
] as const;

export function AppearanceSection() {
  const { theme, setTheme } = useTheme();
  const [mounted, setMounted] = useState(false);

  useEffect(() => {
    setMounted(true);
  }, []);

  if (!mounted) {
    return <div className="rounded-2xl bg-muted/60 p-5 h-[76px]" />;
  }

  return (
    <div className="rounded-2xl bg-muted/60 p-5 space-y-3">
      <p className="text-[14px] font-medium">테마</p>
      <ToggleGroup
        value={[theme ?? "system"]}
        onValueChange={(values) => {
          if (values.length > 0) setTheme(values[0]);
        }}
      >
        {THEME_OPTIONS.map(({ value, label, icon: Icon }) => (
          <ToggleGroupItem key={value} value={value} aria-label={label}>
            <Icon className="w-4 h-4 mr-1.5" />
            {label}
          </ToggleGroupItem>
        ))}
      </ToggleGroup>
    </div>
  );
}
