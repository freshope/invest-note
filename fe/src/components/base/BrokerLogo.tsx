"use client";

import { useState } from "react";
import { cn } from "@/lib/utils";
import { findBroker } from "@/lib/brokers";

interface BrokerLogoProps {
  broker: string | null | undefined;
  size?: number;
  className?: string;
}

export function BrokerLogo({ broker, size = 28, className }: BrokerLogoProps) {
  const found = findBroker(broker);
  const [imgError, setImgError] = useState(false);

  if (found && !imgError) {
    return (
      <img
        src={`/logos/securities/${found.slug}.svg`}
        alt={found.name}
        title={found.name}
        width={size}
        height={size}
        loading="lazy"
        className={cn("rounded-full object-contain shrink-0", className)}
        style={{ width: size, height: size }}
        onError={() => setImgError(true)}
      />
    );
  }

  // fallback: 색 원형 배지 (매칭 실패 또는 이미지 로드 오류)
  const initial = broker ? broker.slice(0, 2) : "?";
  return (
    <span
      className={cn(
        "inline-flex items-center justify-center rounded-full text-white font-bold shrink-0",
        found ? found.color : "bg-muted-foreground/40",
        className
      )}
      style={{ width: size, height: size, fontSize: size * 0.35 }}
      title={broker ?? undefined}
      aria-label={broker ?? undefined}
    >
      {initial}
    </span>
  );
}
