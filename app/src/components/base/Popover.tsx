"use client";

import {
  Popover as PopoverUI,
  PopoverContent as PopoverContentUI,
  PopoverTrigger,
} from "@/components/ui/popover";
import { cn } from "@/lib/utils";
import type { ComponentProps } from "react";

function Popover(props: ComponentProps<typeof PopoverUI>) {
  return <PopoverUI {...props} />;
}

function PopoverContent({ className, ...props }: ComponentProps<typeof PopoverContentUI>) {
  return (
    <PopoverContentUI
      className={cn("p-0 rounded-2xl overflow-hidden", className)}
      {...props}
    />
  );
}

export { Popover, PopoverContent, PopoverTrigger };
