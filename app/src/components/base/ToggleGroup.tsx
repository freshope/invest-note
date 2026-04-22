"use client";

import { cn } from "@/lib/utils";
import {
  ToggleGroup as ToggleGroupUI,
  ToggleGroupItem as ToggleGroupItemUI,
} from "@/components/ui/toggle-group";
import type { ComponentProps } from "react";

function ToggleGroup({ className, ...props }: ComponentProps<typeof ToggleGroupUI>) {
  return (
    <ToggleGroupUI
      className={cn("flex w-full gap-0", className)}
      {...props}
    />
  );
}

function ToggleGroupItem({ className, ...props }: ComponentProps<typeof ToggleGroupItemUI>) {
  return (
    <ToggleGroupItemUI
      className={cn(
        "flex-1 h-10 rounded-xl border border-border bg-muted/50 text-[14px] font-semibold text-muted-foreground transition-colors",
        "aria-pressed:bg-primary aria-pressed:text-primary-foreground aria-pressed:border-primary",
        className
      )}
      {...props}
    />
  );
}

export { ToggleGroup, ToggleGroupItem };
