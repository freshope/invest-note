"use client";

import Link from "next/link";
import { usePathname } from "next/navigation";
import { cn } from "@/lib/utils";

function HomeIcon({ filled }: { filled?: boolean }) {
  if (filled) {
    return (
      <svg width="26" height="26" viewBox="0 0 24 24" fill="currentColor" aria-hidden="true">
        <path d="M12.0002 3.31152L3.91113 9.93365V20.5H9.00014V14.5H15.0001V20.5H20.0891V9.93365L12.0002 3.31152Z" />
      </svg>
    );
  }
  return (
    <svg width="26" height="26" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="1.8" strokeLinecap="round" strokeLinejoin="round" aria-hidden="true">
      <path d="M15 21V13H9V21M3 10.5L12 3L21 10.5V20C21 20.5523 20.5523 21 20 21H4C3.44772 21 3 20.5523 3 20V10.5Z" />
    </svg>
  );
}

function RecordsIcon({ filled }: { filled?: boolean }) {
  if (filled) {
    return (
      <svg width="26" height="26" viewBox="0 0 24 24" fill="currentColor" aria-hidden="true">
        <path d="M14 2H6C4.89543 2 4 2.89543 4 4V20C4 21.1046 4.89543 22 6 22H18C19.1046 22 20 21.1046 20 20V8L14 2Z" />
        <path d="M14 2V8H20" fill="none" stroke="var(--background)" strokeWidth="1.5" strokeLinecap="round" strokeLinejoin="round" />
        <line x1="8" y1="13" x2="16" y2="13" stroke="var(--background)" strokeWidth="1.6" strokeLinecap="round" />
        <line x1="8" y1="17" x2="13" y2="17" stroke="var(--background)" strokeWidth="1.6" strokeLinecap="round" />
      </svg>
    );
  }
  return (
    <svg width="26" height="26" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="1.8" strokeLinecap="round" strokeLinejoin="round" aria-hidden="true">
      <path d="M14 2H6C4.89543 2 4 2.89543 4 4V20C4 21.1046 4.89543 22 6 22H18C19.1046 22 20 21.1046 20 20V8L14 2Z" />
      <polyline points="14 2 14 8 20 8" />
      <line x1="16" y1="13" x2="8" y2="13" />
      <line x1="13" y1="17" x2="8" y2="17" />
    </svg>
  );
}

function AnalysisIcon({ filled }: { filled?: boolean }) {
  if (filled) {
    return (
      <svg width="26" height="26" viewBox="0 0 24 24" fill="currentColor" aria-hidden="true">
        <rect x="3" y="11" width="4" height="10" rx="1.2" />
        <rect x="10" y="6" width="4" height="15" rx="1.2" />
        <rect x="17" y="2" width="4" height="19" rx="1.2" />
      </svg>
    );
  }
  return (
    <svg width="26" height="26" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="1.8" strokeLinecap="round" strokeLinejoin="round" aria-hidden="true">
      <rect x="3" y="11" width="4" height="10" rx="1" />
      <rect x="10" y="6" width="4" height="15" rx="1" />
      <rect x="17" y="2" width="4" height="19" rx="1" />
    </svg>
  );
}

function SettingsIcon({ filled }: { filled?: boolean }) {
  if (filled) {
    return (
      <svg width="26" height="26" viewBox="0 0 24 24" fill="currentColor" aria-hidden="true">
        <path fillRule="evenodd" clipRule="evenodd" d="M10.325 2.317a1.75 1.75 0 0 1 3.35 0l.291 1.118a6.028 6.028 0 0 1 1.443.832l1.1-.364a1.75 1.75 0 0 1 2.1 2.366l-.525 1.048a6.053 6.053 0 0 1 0 1.666l.525 1.048a1.75 1.75 0 0 1-2.1 2.366l-1.1-.364a6.029 6.029 0 0 1-1.443.832l-.291 1.118a1.75 1.75 0 0 1-3.35 0l-.291-1.118a6.028 6.028 0 0 1-1.443-.832l-1.1.364a1.75 1.75 0 0 1-2.1-2.366l.525-1.048a6.054 6.054 0 0 1 0-1.666L5.39 6.269a1.75 1.75 0 0 1 2.1-2.366l1.1.364a6.028 6.028 0 0 1 1.443-.832l.291-1.118zM12 15a3 3 0 1 0 0-6 3 3 0 0 0 0 6z" />
      </svg>
    );
  }
  return (
    <svg width="26" height="26" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="1.8" strokeLinecap="round" strokeLinejoin="round" aria-hidden="true">
      <circle cx="12" cy="12" r="3" />
      <path d="M19.4 15a1.65 1.65 0 0 0 .33 1.82l.06.06a2 2 0 0 1-2.83 2.83l-.06-.06a1.65 1.65 0 0 0-1.82-.33 1.65 1.65 0 0 0-1 1.51V21a2 2 0 0 1-4 0v-.09A1.65 1.65 0 0 0 9 19.4a1.65 1.65 0 0 0-1.82.33l-.06.06a2 2 0 0 1-2.83-2.83l.06-.06A1.65 1.65 0 0 0 4.68 15a1.65 1.65 0 0 0-1.51-1H3a2 2 0 0 1 0-4h.09A1.65 1.65 0 0 0 4.6 9a1.65 1.65 0 0 0-.33-1.82l-.06-.06a2 2 0 0 1 2.83-2.83l.06.06A1.65 1.65 0 0 0 9 4.68a1.65 1.65 0 0 0 1-1.51V3a2 2 0 0 1 4 0v.09a1.65 1.65 0 0 0 1 1.51 1.65 1.65 0 0 0 1.82-.33l.06-.06a2 2 0 0 1 2.83 2.83l-.06.06A1.65 1.65 0 0 0 19.4 9a1.65 1.65 0 0 0 1.51 1H21a2 2 0 0 1 0 4h-.09a1.65 1.65 0 0 0-1.51 1z" />
    </svg>
  );
}

const tabs = [
  { href: "/", icon: HomeIcon, label: "홈" },
  { href: "/records", icon: RecordsIcon, label: "기록" },
  { href: "/analysis", icon: AnalysisIcon, label: "분석" },
  { href: "/settings", icon: SettingsIcon, label: "설정" },
] as const;

export function BottomNav() {
  const pathname = usePathname();

  return (
    <nav
      className="fixed bottom-0 left-0 right-0 z-50 bg-background/90 backdrop-blur-xl border-t border-border/50"
      style={{ paddingBottom: "env(safe-area-inset-bottom)" }}
    >
      <div className="mx-auto flex h-16 max-w-lg">
        {tabs.map(({ href, icon: Icon, label }) => {
          const isActive =
            href === "/" ? pathname === "/" : pathname.startsWith(href);
          return (
            <Link
              key={href}
              href={href}
              className={cn(
                "flex flex-1 flex-col items-center justify-center gap-0.5 transition-colors",
                isActive ? "text-foreground" : "text-muted-foreground"
              )}
            >
              <Icon filled={isActive} />
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
