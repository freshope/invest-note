"use client";

import { useState, useRef, useEffect, useCallback, useMemo } from "react";
import { usePortfolioSummary } from "@/hooks/usePortfolioSummary";
import { Input } from "@/components/base/Input";
import { CountryBadge } from "./trade-display";
import type { SelectedStock } from "./StockSearchInput";

interface HoldingSelectInputProps {
  accountId: string;
  value: string;
  onChange: (value: string) => void;
  onSelect: (stock: SelectedStock) => void;
  onSelectComplete?: () => void;
}

export function HoldingSelectInput({ accountId, value, onChange, onSelect, onSelectComplete }: HoldingSelectInputProps) {
  const [open, setOpen] = useState(false);
  const containerRef = useRef<HTMLDivElement>(null);
  const { data, loading } = usePortfolioSummary();

  const handleClickOutside = useCallback((e: MouseEvent) => {
    if (containerRef.current && !containerRef.current.contains(e.target as Node)) {
      setOpen(false);
    }
  }, []);

  useEffect(() => {
    document.addEventListener("mousedown", handleClickOutside);
    return () => document.removeEventListener("mousedown", handleClickOutside);
  }, [handleClickOutside]);

  const allPositions = useMemo(
    () => accountId
      ? (data?.positions ?? []).filter((p) => p.accountIds.includes(accountId) && p.holdingQuantity > 0)
      : [],
    [data?.positions, accountId],
  );

  const trimmed = value.trim();
  const lowerTrimmed = trimmed.toLowerCase();
  const filtered = trimmed
    ? allPositions.filter((p) => p.assetName.includes(trimmed) || p.ticker.toLowerCase().includes(lowerTrimmed))
    : allPositions;

  const handleSelect = (pos: typeof allPositions[number]) => {
    const market = pos.country === "KR" ? "KR" : pos.country === "US" ? "US" : "OTHER";
    onSelect({ name: pos.assetName, code: pos.ticker, market, exchange: pos.exchange });
    setOpen(false);
    onSelectComplete?.();
  };

  const placeholder = !accountId
    ? "계좌를 먼저 선택하세요"
    : loading
    ? "보유 종목 조회 중..."
    : allPositions.length === 0
    ? "보유 중인 종목이 없습니다"
    : "보유 종목을 선택하세요";

  return (
    <div ref={containerRef} className="relative">
      <Input
        type="text"
        placeholder={placeholder}
        value={value}
        disabled={!accountId || loading || allPositions.length === 0}
        onChange={(e) => {
          onChange(e.target.value);
          setOpen(true);
        }}
        onFocus={() => { if (accountId && !loading && allPositions.length > 0) setOpen(true); }}
        autoComplete="off"
        autoCorrect="off"
      />
      {open && filtered.length > 0 && (
        <ul className="absolute left-0 right-0 top-[calc(100%+4px)] z-50 max-h-[280px] overflow-y-auto rounded-xl bg-popover shadow-md ring-1 ring-foreground/10">
          {filtered.map((pos) => (
            <li
              key={pos.key}
              onMouseDown={(e) => { e.preventDefault(); handleSelect(pos); }}
              className="flex items-center gap-3 px-4 py-3 text-[15px] cursor-default transition-colors hover:bg-accent hover:text-accent-foreground"
            >
              <CountryBadge countryCode={pos.country} />
              <span className="flex-1 font-medium truncate">{pos.assetName}</span>
              <span className="shrink-0 text-[12px] text-muted-foreground font-mono">{pos.ticker}</span>
              <span className="shrink-0 text-[12px] text-muted-foreground">
                {pos.holdingQuantity.toLocaleString("ko-KR")}주
              </span>
            </li>
          ))}
        </ul>
      )}
    </div>
  );
}
