"use client";

import { cn } from "@/lib/utils";
import { formatPnL, signColor } from "@/lib/format";

interface PnLLineProps {
  value: number;
  muted?: boolean;
}

/** 0이면 렌더링하지 않음 — 호출부에서 conditional 없이 사용 가능. */
export function PnLLine({ value, muted = false }: PnLLineProps) {
  if (value === 0) return null;
  return (
    <span className={cn("ml-1.5", muted ? "text-muted-foreground" : signColor(value, "none"))}>
      {formatPnL(value)}
    </span>
  );
}
