"use client";

import { cn } from "@/lib/utils";
import { getCountryLabel } from "./trade-formatters";

export { buildMarketDisplay, getQuantityUnit, getCountryLabel } from "./trade-formatters";

export function CompactRow({ label, children }: { label: string; children: React.ReactNode }) {
  return (
    <div className="flex flex-col gap-0.5">
      <span className="text-[11px] text-muted-foreground">{label}</span>
      <span className="text-[13px] text-foreground">{children}</span>
    </div>
  );
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
