"use client";

import { cn } from "@/lib/utils";
import { TRADE_TYPE_LABELS } from "@/lib/constants/trading";
import { getTradeTypeAccent } from "@/lib/constants/colors";
import type { TradeType } from "@/types/database";

type TradeTypeBadgeSize = "sm" | "md";

const SIZE_CLASSES: Record<TradeTypeBadgeSize, string> = {
  sm: "text-[11px] px-1.5 py-0.5 rounded-md shrink-0",
  md: "text-[12px] px-2 py-0.5 rounded-md",
};

interface TradeTypeBadgeProps {
  tradeType: TradeType;
  size?: TradeTypeBadgeSize;
  className?: string;
}

export function TradeTypeBadge({ tradeType, size = "md", className }: TradeTypeBadgeProps) {
  const accent = getTradeTypeAccent(tradeType);
  return (
    <span
      className={cn(
        "font-bold",
        SIZE_CLASSES[size],
        accent.bgSoft,
        accent.text,
        className,
      )}
    >
      {TRADE_TYPE_LABELS[tradeType]}
    </span>
  );
}
