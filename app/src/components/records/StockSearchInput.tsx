"use client";

import { useState, useRef, useEffect, useCallback } from "react";
import { useQuery } from "@tanstack/react-query";
import { useDebounce } from "@/hooks/useDebounce";
import { Input } from "@/components/base/Input";
import { stocksApi, type StockSearchResult } from "@/lib/api-client";
import { queryKeys } from "@/lib/query-keys";

export interface SelectedStock {
  name: string;
  code: string;
  market: "KR" | "US" | "OTHER";
  exchange: string;
}

interface StockSearchInputProps {
  onSelect: (stock: SelectedStock) => void;
  onSelectComplete?: () => void;
  value: string;
  onChange: (value: string) => void;
}

const MARKET_BADGE: Record<string, { label: string; className: string }> = {
  KR: { label: "국내", className: "bg-blue-100 text-blue-700 dark:bg-blue-900/40 dark:text-blue-300" },
  US: { label: "해외", className: "bg-orange-100 text-orange-700 dark:bg-orange-900/40 dark:text-orange-300" },
  OTHER: { label: "기타", className: "bg-gray-100 text-gray-600 dark:bg-gray-800 dark:text-gray-400" },
};

async function fetchStocks(query: string): Promise<StockSearchResult[]> {
  return stocksApi.search(query);
}

export function StockSearchInput({ onSelect, onSelectComplete, value, onChange }: StockSearchInputProps) {
  // hidden: 사용자가 명시적으로 닫은 상태 (Escape / 외부 클릭)
  const [hidden, setHidden] = useState(false);
  const [activeIndex, setActiveIndex] = useState(-1);
  // 마지막으로 선택한 종목명 — value와 일치하면 드롭다운 억제
  const [lastSelected, setLastSelected] = useState("");
  const containerRef = useRef<HTMLDivElement>(null);
  const debouncedValue = useDebounce(value, 300);

  const { data: suggestions = [], isFetching } = useQuery({
    queryKey: queryKeys.stockSearch(debouncedValue),
    queryFn: () => fetchStocks(debouncedValue),
    enabled: debouncedValue.trim().length >= 1,
    staleTime: 60_000,
  });

  // 쿼리 키(debouncedValue) 변경 시 activeIndex 초기화 — 렌더 중 state 비교 패턴.
  // suggestions 참조 비교는 useQuery 구조분해 기본값 `= []`가 매 렌더 새 배열을 만들어 무한 루프 유발.
  const [prevQuery, setPrevQuery] = useState(debouncedValue);
  if (prevQuery !== debouncedValue) {
    setPrevQuery(debouncedValue);
    setActiveIndex(-1);
  }

  // open은 렌더 시점에 직접 파생 — useEffect 불필요
  const open = !hidden
    && value.trim().length > 0
    && value !== lastSelected
    && suggestions.length > 0;

  const handleInputChange = useCallback((e: React.ChangeEvent<HTMLInputElement>) => {
    setLastSelected("");
    setHidden(false);
    onChange(e.target.value);
  }, [onChange]);

  const handleSelect = useCallback((stock: StockSearchResult) => {
    setLastSelected(stock.name);
    onChange(stock.name);
    onSelect({ name: stock.name, code: stock.code, market: stock.market, exchange: stock.exchange });
    setActiveIndex(-1);
    onSelectComplete?.();
  }, [onChange, onSelect, onSelectComplete]);

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
      setHidden(true);
    }
  }, [open, suggestions, activeIndex, handleSelect]);

  useEffect(() => {
    function handleClickOutside(e: MouseEvent) {
      if (containerRef.current && !containerRef.current.contains(e.target as Node)) {
        setHidden(true);
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
        onChange={handleInputChange}
        onKeyDown={handleKeyDown}
        onFocus={() => { if (suggestions.length > 0) setHidden(false); }}
        autoComplete="off"
        autoCorrect="off"
      />
      {isFetching && (
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
                onMouseDown={(e) => { e.preventDefault(); handleSelect(stock); }}
                className={`flex items-center gap-3 px-4 py-3 text-[15px] cursor-default transition-colors ${
                  i === activeIndex ? "bg-accent text-accent-foreground" : "hover:bg-accent hover:text-accent-foreground"
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
