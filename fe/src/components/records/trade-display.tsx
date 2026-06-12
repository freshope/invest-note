"use client";

import { cn } from "@/lib/utils";
import { getCountryLabel, MARKET_LABELS } from "./trade-formatters";
import type { MarketType } from "@/types/database";

export { getQuantityUnit, getCountryLabel, MARKET_LABELS } from "./trade-formatters";

export function CompactRow({ label, children }: { label: string; children: React.ReactNode }) {
  return (
    <div className="flex flex-col gap-0.5 min-w-0">
      <span className="text-[11px] text-muted-foreground">{label}</span>
      <div className="text-[13px] text-foreground min-w-0">{children}</div>
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

const COUNTRY_BADGE_CLASS: Record<string, string> = {
  KR: "bg-blue-100 text-blue-700",
  US: "bg-orange-100 text-orange-700",
};

export function CountryBadge({ countryCode, className }: { countryCode: string; className?: string }) {
  const label = getCountryLabel(countryCode) ?? "기타";
  return (
    <span
      className={cn(
        "shrink-0 whitespace-nowrap text-[11px] font-bold px-1.5 py-0.5 rounded-md",
        COUNTRY_BADGE_CLASS[countryCode] ?? "bg-muted text-muted-foreground",
        className,
      )}
    >
      {label}
    </span>
  );
}
