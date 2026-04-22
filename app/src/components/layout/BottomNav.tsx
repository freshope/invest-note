"use client";

import Link from "next/link";
import { usePathname } from "next/navigation";
import { Home, FileText, BarChart2, Settings2 } from "lucide-react";
import { cn } from "@/lib/utils";

const tabs = [
  { href: "/", icon: Home, label: "홈" },
  { href: "/records", icon: FileText, label: "기록" },
  { href: "/analysis", icon: BarChart2, label: "분석" },
  { href: "/settings", icon: Settings2, label: "설정" },
] as const;

export function BottomNav() {
  const pathname = usePathname();

  return (
    <nav
      className="fixed bottom-0 left-0 right-0 z-50 flex justify-center pointer-events-none"
      style={{ paddingBottom: "env(safe-area-inset-bottom)" }}
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
              <Icon size={24} strokeWidth={isActive ? 2.5 : 1.8} />
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
