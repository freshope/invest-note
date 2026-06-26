"use client";

import Link from "next/link";
import { usePathname } from "next/navigation";
import { NAV_ITEMS, NAV_GROUPS, type NavItem } from "@/lib/nav";
import { cn } from "@/lib/utils";

export function Sidebar() {
  const pathname = usePathname();

  function NavLink({ item, indent }: { item: NavItem; indent?: boolean }) {
    // 루트("/")는 정확 일치, 그 외는 prefix 일치로 활성 표시.
    const active =
      item.href === "/" ? pathname === "/" : pathname.startsWith(item.href);
    const Icon = item.icon;
    return (
      <Link
        href={item.href}
        className={cn(
          "flex items-center gap-3 rounded-md px-3 py-2 text-[14px] font-medium transition-colors",
          indent && "ml-3",
          active
            ? "bg-sidebar-primary text-sidebar-primary-foreground"
            : "text-sidebar-foreground hover:bg-sidebar-accent",
        )}
      >
        <Icon className="size-4" />
        {item.label}
      </Link>
    );
  }

  return (
    <aside className="flex h-svh w-60 shrink-0 flex-col border-r border-sidebar-border bg-sidebar">
      <div className="flex h-14 items-center px-5">
        <span className="text-[15px] font-bold text-sidebar-foreground">
          투자노트 어드민
        </span>
      </div>
      <nav className="flex-1 space-y-0.5 px-3 py-2">
        {NAV_ITEMS.map((item) => (
          <NavLink key={item.href} item={item} />
        ))}
        {NAV_GROUPS.map((group) => {
          const GroupIcon = group.icon;
          return (
            <div key={group.label} className="pt-2">
              <div className="flex items-center gap-3 px-3 py-1.5 text-[12px] font-semibold uppercase tracking-wide text-muted-foreground">
                <GroupIcon className="size-4" />
                {group.label}
              </div>
              <div className="space-y-0.5">
                {group.children.map((child) => (
                  <NavLink key={child.href} item={child} indent />
                ))}
              </div>
            </div>
          );
        })}
      </nav>
    </aside>
  );
}
