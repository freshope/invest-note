import type { ReactNode } from "react";
import { cn } from "@/lib/utils";

interface EmptyCardProps {
  title: string;
  description?: ReactNode;
  action?: ReactNode;
  className?: string;
  compact?: boolean;
}

export function EmptyCard({ title, description, action, className, compact }: EmptyCardProps) {
  return (
    <div
      className={cn(
        "rounded-2xl bg-muted/60 p-8 text-center",
        compact ? "space-y-1" : "space-y-4",
        className,
      )}
    >
      <p
        className={cn(
          "font-semibold text-foreground",
          compact ? "text-[14px]" : "text-[15px]",
        )}
      >
        {title}
      </p>
      {description && (
        <p className="text-[13px] text-muted-foreground leading-relaxed">{description}</p>
      )}
      {action}
    </div>
  );
}
