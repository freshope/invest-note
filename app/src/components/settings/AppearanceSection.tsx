"use client";

import { useEffect, useState } from "react";
import { useTheme } from "next-themes";
import { Monitor, Sun, Moon, Check } from "lucide-react";
import {
  FullScreenPanel,
  FullScreenPanelContent,
  FullScreenPanelHeader,
  FullScreenPanelBody,
} from "@/components/base/FullScreenPanel";
import { SettingsMenuRow } from "@/components/settings/SettingsMenuRow";
import { DEFAULT_THEME } from "@/lib/constants/theme";
import { cn } from "@/lib/utils";

const THEME_OPTIONS = [
  { value: "system", label: "시스템", icon: Monitor },
  { value: "light", label: "라이트", icon: Sun },
  { value: "dark", label: "다크", icon: Moon },
] as const;

const MENU_GROUP = "rounded-2xl bg-muted/60 overflow-hidden";

export function AppearanceSection() {
  const { theme, setTheme } = useTheme();
  const [mounted, setMounted] = useState(false);
  const [open, setOpen] = useState(false);

  // next-themes 는 클라이언트에서만 실제 theme 을 알 수 있어, 마운트 전 렌더는
  // hydration 불일치를 유발한다. mounted 전에는 현재값(value)만 비운다.
  useEffect(() => {
    setMounted(true);
  }, []);

  const current = theme ?? DEFAULT_THEME;
  const currentLabel = THEME_OPTIONS.find((o) => o.value === current)?.label;

  return (
    <>
      <div className={MENU_GROUP}>
        <SettingsMenuRow
          label="테마"
          value={mounted ? currentLabel : undefined}
          onClick={() => setOpen(true)}
        />
      </div>

      <FullScreenPanel open={open} onOpenChange={setOpen}>
        <FullScreenPanelContent>
          <FullScreenPanelHeader title="테마" />
          <FullScreenPanelBody>
            <div className="px-5 pt-2 pb-6">
              <div className={MENU_GROUP}>
                {THEME_OPTIONS.map(({ value, label, icon: Icon }) => {
                  const selected = current === value;
                  return (
                    <button
                      key={value}
                      type="button"
                      onClick={() => {
                        setTheme(value);
                        setOpen(false);
                      }}
                      className={cn(
                        "flex w-full items-center gap-3 px-5 py-4 text-left transition-colors",
                        "border-t border-border/60 first:border-t-0",
                        "text-foreground hover:bg-foreground/5",
                      )}
                    >
                      <Icon className="size-5 shrink-0 text-muted-foreground" />
                      <span className="flex-1 text-[15px] font-medium">{label}</span>
                      {selected ? (
                        <Check className="size-5 shrink-0 text-primary" />
                      ) : null}
                    </button>
                  );
                })}
              </div>
            </div>
          </FullScreenPanelBody>
        </FullScreenPanelContent>
      </FullScreenPanel>
    </>
  );
}
