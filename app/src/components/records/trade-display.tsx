"use client";

import { useState } from "react";
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

// public/flags/4x3 에 보유한 국기 코드(소문자 ISO2). 이 집합에 있으면 국기,
// 없으면(OTHER 등) 텍스트 뱃지로 폴백한다.
const FLAG_CODES = new Set([
  "kr", "us", "jp", "cn", "hk", "gb", "de", "fr", "in",
  "tw", "vn", "ca", "au", "sg", "ch", "nl", "it", "es",
]);

export function CountryBadge({ countryCode, className }: { countryCode: string; className?: string }) {
  const label = getCountryLabel(countryCode) ?? "기타";
  const code = countryCode.toLowerCase();
  const src = `/flags/4x3/${code}.svg`;
  // 실패한 src 자체를 기억한다 — boolean 으로 두면 인스턴스 재사용 시(리스트 재정렬)
  // 다른 정상 국가까지 폴백에 고착된다.
  const [erroredSrc, setErroredSrc] = useState<string | null>(null);

  if (FLAG_CODES.has(code) && erroredSrc !== src) {
    return (
      <img
        src={src}
        alt={label}
        title={label}
        loading="lazy"
        className={cn("shrink-0 rounded-[3px] object-cover ring-1 ring-black/10", className)}
        style={{ width: 20, height: 15 }}
        onError={() => setErroredSrc(src)}
      />
    );
  }

  return (
    <span
      className={cn(
        "shrink-0 whitespace-nowrap text-[11px] font-bold px-1.5 py-0.5 rounded-md bg-muted text-muted-foreground",
        className,
      )}
    >
      {label}
    </span>
  );
}
