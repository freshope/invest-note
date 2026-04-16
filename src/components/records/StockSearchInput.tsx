"use client";

import { useState, useRef, useEffect, useCallback } from "react";
import { Input } from "@/components/base/Input";

interface StockResult {
  symbol: string;
  code: string;
  name: string;
  market: "KR" | "US" | "OTHER";
  exchange: string;
}

export interface SelectedStock {
  name: string;
  code: string;
  market: "KR" | "US" | "OTHER";
  exchange: string;
}

interface StockSearchInputProps {
  onSelect: (stock: SelectedStock) => void;
  value: string;
  onChange: (value: string) => void;
}

const MARKET_BADGE: Record<string, { label: string; className: string }> = {
  KR: { label: "국내", className: "bg-blue-100 text-blue-700 dark:bg-blue-900/40 dark:text-blue-300" },
  US: { label: "해외", className: "bg-orange-100 text-orange-700 dark:bg-orange-900/40 dark:text-orange-300" },
  OTHER: { label: "기타", className: "bg-gray-100 text-gray-600 dark:bg-gray-800 dark:text-gray-400" },
};

export function StockSearchInput({ onSelect, value, onChange }: StockSearchInputProps) {
  const [suggestions, setSuggestions] = useState<StockResult[]>([]);
  const [open, setOpen] = useState(false);
  const [loading, setLoading] = useState(false);
  const [activeIndex, setActiveIndex] = useState(-1);
  const containerRef = useRef<HTMLDivElement>(null);
  const abortRef = useRef<AbortController | null>(null);
  const debounceRef = useRef<ReturnType<typeof setTimeout>>(null);

  const fetchStocks = useCallback(async (query: string) => {
    if (!query.trim() || query.length < 1) {
      setSuggestions([]);
      setOpen(false);
      return;
    }

    // 이전 요청 취소
    abortRef.current?.abort();
    const controller = new AbortController();
    abortRef.current = controller;

    setLoading(true);
    try {
      const res = await fetch(
        `/api/stocks/search?q=${encodeURIComponent(query)}`,
        { signal: controller.signal }
      );
      if (!res.ok) return;
      const data: StockResult[] = await res.json();
      setSuggestions(data);
      setOpen(data.length > 0);
      setActiveIndex(-1);
    } catch (e) {
      if (e instanceof DOMException && e.name === "AbortError") return;
      setSuggestions([]);
      setOpen(false);
    } finally {
      setLoading(false);
    }
  }, []);

  const handleInput = useCallback((raw: string) => {
    onChange(raw);
    if (debounceRef.current) clearTimeout(debounceRef.current);
    debounceRef.current = setTimeout(() => fetchStocks(raw), 300);
  }, [onChange, fetchStocks]);

  useEffect(() => {
    return () => {
      if (debounceRef.current) clearTimeout(debounceRef.current);
      abortRef.current?.abort();
    };
  }, []);

  const handleSelect = useCallback((stock: StockResult) => {
    onChange(stock.name);
    onSelect({
      name: stock.name,
      code: stock.code,
      market: stock.market,
      exchange: stock.exchange,
    });
    setSuggestions([]);
    setOpen(false);
    setActiveIndex(-1);
  }, [onChange, onSelect]);

  const handleKeyDown = useCallback((e: React.KeyboardEvent<HTMLInputElement>) => {
    if (!open) return;
    if (e.key === "ArrowDown") {
      e.preventDefault();
      setActiveIndex((i) => Math.min(i + 1, suggestions.length - 1));
    } else if (e.key === "ArrowUp") {
      e.preventDefault();
      setActiveIndex((i) => Math.max(i - 1, -1));
    } else if (e.key === "Enter") {
      if (activeIndex >= 0 && suggestions[activeIndex]) {
        e.preventDefault();
        handleSelect(suggestions[activeIndex]);
      }
    } else if (e.key === "Escape") {
      setOpen(false);
    }
  }, [open, suggestions, activeIndex, handleSelect]);

  // 외부 클릭 시 닫기
  useEffect(() => {
    function handleClickOutside(e: MouseEvent) {
      if (containerRef.current && !containerRef.current.contains(e.target as Node)) {
        setOpen(false);
      }
    }
    document.addEventListener("mousedown", handleClickOutside);
    return () => document.removeEventListener("mousedown", handleClickOutside);
  }, []);

  return (
    <div ref={containerRef} className="relative">
      <Input
        type="text"
        placeholder="예: 삼성전자, AAPL, 005930"
        value={value}
        onChange={(e) => handleInput(e.target.value)}
        onKeyDown={handleKeyDown}
        onFocus={() => { if (suggestions.length > 0) setOpen(true); }}
        autoComplete="off"
        autoCorrect="off"
      />
      {loading && (
        <div className="absolute right-4 top-1/2 -translate-y-1/2">
          <div className="h-4 w-4 animate-spin rounded-full border-2 border-muted-foreground/30 border-t-primary" />
        </div>
      )}
      {open && suggestions.length > 0 && (
        <ul className="absolute left-0 right-0 top-[calc(100%+4px)] z-50 max-h-[280px] overflow-y-auto rounded-xl bg-popover shadow-md ring-1 ring-foreground/10">
          {suggestions.map((stock, i) => {
            const badge = MARKET_BADGE[stock.market];
            return (
              <li
                key={`${stock.market}-${stock.code}`}
                onMouseDown={(e) => {
                  e.preventDefault();
                  handleSelect(stock);
                }}
                className={`flex items-center gap-3 px-4 py-3 text-[15px] cursor-default transition-colors ${
                  i === activeIndex
                    ? "bg-accent text-accent-foreground"
                    : "hover:bg-accent hover:text-accent-foreground"
                }`}
              >
                <span className={`shrink-0 rounded-md px-1.5 py-0.5 text-[11px] font-bold ${badge.className}`}>
                  {badge.label}
                </span>
                <span className="flex-1 font-medium truncate">{stock.name}</span>
                <span className="shrink-0 text-[12px] text-muted-foreground font-mono">{stock.code}</span>
                <span className="shrink-0 text-[11px] text-muted-foreground">{stock.exchange}</span>
              </li>
            );
          })}
        </ul>
      )}
    </div>
  );
}
