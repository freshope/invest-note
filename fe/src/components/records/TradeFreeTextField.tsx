"use client";

import type { ComponentProps } from "react";
import { Label } from "@/components/base/Label";
import { Textarea } from "@/components/base/Textarea";
import { VALIDATION_LIMITS } from "@/lib/constants/validation";
import { cn } from "@/lib/utils";

const WARNING_RATIO = 0.9;

type TradeFreeTextFieldProps = ComponentProps<typeof Textarea> & {
  id: string;
  label: string;
  valueLength: number;
  optional?: boolean;
};

export function TradeFreeTextField({
  id,
  label,
  valueLength,
  optional,
  className,
  ...props
}: TradeFreeTextFieldProps) {
  const limit = VALIDATION_LIMITS.TRADE_FREE_TEXT_MAX;
  const countId = `${id}-count`;
  const describedBy = [props["aria-describedby"], countId].filter(Boolean).join(" ");
  const isWarning = valueLength >= limit * WARNING_RATIO;

  return (
    <div className="space-y-1.5">
      <div className="flex items-center justify-between gap-3">
        <Label htmlFor={id}>
          {label}{" "}
          {optional && (
            <span className="text-[12px] font-normal text-muted-foreground">(선택)</span>
          )}
        </Label>
        <span
          id={countId}
          className={cn(
            "shrink-0 text-[12px] tabular-nums text-muted-foreground",
            isWarning && "text-destructive",
          )}
        >
          {valueLength}/{limit}
        </span>
      </div>
      <Textarea
        {...props}
        id={id}
        maxLength={limit}
        aria-describedby={describedBy}
        className={className}
      />
    </div>
  );
}
