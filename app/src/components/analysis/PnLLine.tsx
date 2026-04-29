"use client";

import { cn } from "@/lib/utils";
import { formatPnL } from "@/lib/format";

interface PnLLineProps {
  value: number;
}

/** 0이면 렌더링하지 않음 — 호출부에서 conditional 없이 사용 가능. */
export function PnLLine({ value }: PnLLineProps) {
  if (value === 0) return null;
  return (
    <span
      className={cn(
        "ml-1.5",
        value > 0 ? "text-[var(--rise)]" : "text-[var(--fall)]",
      )}
    >
      {formatPnL(value)}
    </span>
  );
}
