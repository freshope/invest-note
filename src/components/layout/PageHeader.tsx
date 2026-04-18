import { cn } from "@/lib/utils";
import type { ReactNode } from "react";

interface PageHeaderProps {
  title?: ReactNode;
  actions?: ReactNode;
  children?: ReactNode;
  sticky?: boolean;
  className?: string;
}

export function PageHeader({
  title,
  actions,
  children,
  sticky = true,
  className,
}: PageHeaderProps) {
  return (
    <header
      className={cn(
        sticky && "sticky top-0 z-10",
        "bg-background px-5 pb-3",
        className,
      )}
      style={{ paddingTop: "calc(1.5rem + env(safe-area-inset-top))" }}
    >
      {children ?? (
        <div className="flex items-center justify-between gap-3">
          <h1 className="text-[20px] font-bold text-foreground leading-tight">
            {title}
          </h1>
          {actions && <div className="shrink-0">{actions}</div>}
        </div>
      )}
    </header>
  );
}
