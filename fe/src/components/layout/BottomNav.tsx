"use client";

import Link from "next/link";
import { usePathname } from "next/navigation";
import {
  NavAnalysisIcon,
  NavHomeIcon,
  NavRecordsIcon,
  NavSettingsIcon,
} from "@/components/base/NavIcons";
import { useBottomNavHidden } from "@/components/providers/BottomNavProvider";
import { cn } from "@/lib/utils";

const tabs = [
  { href: "/", icon: NavHomeIcon, label: "홈" },
  { href: "/records", icon: NavRecordsIcon, label: "기록" },
  { href: "/analysis", icon: NavAnalysisIcon, label: "분석" },
  { href: "/settings", icon: NavSettingsIcon, label: "설정" },
] as const;

export function BottomNav() {
  const pathname = usePathname();
  const hidden = useBottomNavHidden();

  if (hidden) return null;

  return (
    <nav
      className="fixed bottom-0 left-0 right-0 z-50 flex justify-center pointer-events-none"
      style={{ paddingBottom: "var(--safe-area-inset-bottom, env(safe-area-inset-bottom))" }}
    >
      <div className="mx-5 mb-3 flex h-[62px] w-full max-w-sm rounded-full bg-background border border-border/40 shadow-[0_4px_24px_rgba(0,0,0,0.08)] pointer-events-auto">
        {tabs.map(({ href, icon: Icon, label }) => {
          const isActive =
            href === "/" ? pathname === "/" : pathname.startsWith(href);
          return (
            <Link
              key={href}
              href={href}
              className={cn(
                "flex flex-1 flex-col items-center justify-center gap-0.5 transition-colors rounded-full",
                isActive ? "text-foreground" : "text-muted-foreground/70"
              )}
            >
              <Icon active={isActive} size={24} />
              <span className={cn(
                "text-[10px] tracking-tight",
                isActive ? "font-bold" : "font-medium"
              )}>
                {label}
              </span>
            </Link>
          );
        })}
      </div>
    </nav>
  );
}
