"use client";

import { cn } from "@/lib/utils";
import { getCountryLabel, MARKET_LABELS } from "./trade-formatters";
import type { MarketType } from "@/types/database";

export { getQuantityUnit, getCountryLabel, MARKET_LABELS } from "./trade-formatters";

export function CompactRow({ label, children }: { label: string; children: React.ReactNode }) {
  return (
    <div className="flex flex-col gap-0.5">
      <span className="text-[11px] text-muted-foreground">{label}</span>
      <span className="text-[13px] text-foreground">{children}</span>
    </div>
  );
}

const mutedBadgeClass = "text-[11px] font-bold px-1.5 py-0.5 rounded-md bg-muted text-foreground";

export function MarketTypeBadge({ marketType }: { marketType: MarketType }) {
  return (
    <span className={mutedBadgeClass}>
      {MARKET_LABELS[marketType] ?? marketType}
    </span>
  );
}

/** exchange가 빈 문자열("")이면 배지를 숨긴다 — 미상 거래소의 sentinel값 */
export function ExchangeBadge({ exchange }: { exchange: string }) {
  if (!exchange) return null;
  return <span className={mutedBadgeClass}>{exchange}</span>;
}

export function CountryBadge({ countryCode }: { countryCode: string }) {
  const label = getCountryLabel(countryCode) ?? "기타";
  return (
    <span
      className={cn(
        "text-[11px] font-bold px-1.5 py-0.5 rounded-md",
        countryCode === "KR"
          ? "bg-blue-100 text-blue-700 dark:bg-blue-900/40 dark:text-blue-300"
          : countryCode === "US"
          ? "bg-orange-100 text-orange-700 dark:bg-orange-900/40 dark:text-orange-300"
          : "bg-muted text-muted-foreground"
      )}
    >
      {label}
    </span>
  );
}
