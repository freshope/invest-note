"use client";

import { cn } from "@/lib/utils";
import {
  Select as SelectUI,
  SelectContent as SelectContentUI,
  SelectGroup,
  SelectItem as SelectItemUI,
  SelectLabel,
  SelectScrollDownButton,
  SelectScrollUpButton,
  SelectSeparator,
  SelectTrigger as SelectTriggerUI,
  SelectValue,
} from "@/components/ui/select";
import type { ComponentProps } from "react";

function Select(props: ComponentProps<typeof SelectUI>) {
  return <SelectUI {...props} />;
}

function SelectTrigger({ className, ...props }: ComponentProps<typeof SelectTriggerUI>) {
  return (
    <SelectTriggerUI
      className={cn(
        "h-12 data-[size=default]:h-12 w-full rounded-xl border-0 bg-muted px-4 text-[15px] focus-visible:ring-2 focus-visible:ring-primary/50",
        className
      )}
      {...props}
    />
  );
}

function SelectContent({ className, ...props }: ComponentProps<typeof SelectContentUI>) {
  return (
    <SelectContentUI
      className={cn("rounded-xl", className)}
      {...props}
    />
  );
}

function SelectItem({ className, ...props }: ComponentProps<typeof SelectItemUI>) {
  return (
    <SelectItemUI
      className={cn("py-2.5 text-[15px]", className)}
      {...props}
    />
  );
}

export {
  Select,
  SelectContent,
  SelectGroup,
  SelectItem,
  SelectLabel,
  SelectScrollDownButton,
  SelectScrollUpButton,
  SelectSeparator,
  SelectTrigger,
  SelectValue,
};
