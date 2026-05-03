"use client";

import {
  createContext,
  useCallback,
  useContext,
  useEffect,
  useMemo,
  useState,
} from "react";
import { useQueryClient } from "@tanstack/react-query";
import { usePathname } from "next/navigation";
import {
  FullScreenPanel,
  FullScreenPanelContent,
  useStaggeredPanel,
} from "@/components/base/FullScreenPanel";
import { TradeDetail } from "@/components/records/TradeDetail";
import { StockDetail } from "@/components/stocks/StockDetail";
import { buildPnlMap } from "@/lib/analysis/realized-pnl";
import { queryKeys } from "@/lib/query-keys";
import { useEffectiveAccountId } from "@/components/providers/AccountFilterProvider";
import type { Account } from "@/types/database";
import type { TradeWithAccount } from "@/lib/trade-utils";

export type TradePayload = {
  trade: TradeWithAccount;
  accounts: Account[];
  allTrades: TradeWithAccount[];
};

export type StockPayload = {
  assetName: string;
  ticker: string;
  country: string;
  allTrades: TradeWithAccount[];
  accounts: Account[];
};

interface DetailPanelContextValue {
  openTrade: (payload: TradePayload) => void;
  openStock: (payload: StockPayload) => void;
}

const DetailPanelContext = createContext<DetailPanelContextValue | null>(null);

export function useDetailPanel(): DetailPanelContextValue {
  const ctx = useContext(DetailPanelContext);
  if (!ctx) {
    throw new Error("useDetailPanel must be used within <DetailPanelProvider>");
  }
  return ctx;
}

export function DetailPanelProvider({ children }: { children: React.ReactNode }) {
  const queryClient = useQueryClient();

  const [tradePayload, setTradePayload] = useState<TradePayload | null>(null);
  const [stockPayload, setStockPayload] = useState<StockPayload | null>(null);

  const openTrade = useCallback((payload: TradePayload) => setTradePayload(payload), []);
  const openStock = useCallback((payload: StockPayload) => setStockPayload(payload), []);
  const closeTrade = useCallback(() => setTradePayload(null), []);
  const closeStock = useCallback(() => setStockPayload(null), []);

  const pathname = usePathname();
  useEffect(() => {
    setTradePayload(null);
    setStockPayload(null);
  }, [pathname]);

  const handleTradeMutated = useCallback(() => {
    setTradePayload(null);
    queryClient.invalidateQueries({ queryKey: queryKeys.portfolio });
    queryClient.invalidateQueries({ queryKey: queryKeys.trades });
  }, [queryClient]);

  const handleTradeSaved = useCallback(() => {
    queryClient.invalidateQueries({ queryKey: queryKeys.portfolio });
    queryClient.invalidateQueries({ queryKey: queryKeys.trades });
  }, [queryClient]);

  const value = useMemo<DetailPanelContextValue>(
    () => ({ openTrade, openStock }),
    [openTrade, openStock],
  );

  return (
    <DetailPanelContext.Provider value={value}>
      {children}
      <TradePanel
        externalPayload={tradePayload}
        onClose={closeTrade}
        onMutated={handleTradeMutated}
        onSaved={handleTradeSaved}
        openStock={openStock}
      />
      <StockPanel
        externalPayload={stockPayload}
        onClose={closeStock}
        openTrade={openTrade}
      />
    </DetailPanelContext.Provider>
  );
}

interface TradePanelProps {
  externalPayload: TradePayload | null;
  onClose: () => void;
  onMutated: () => void;
  onSaved: () => void;
  openStock: (p: StockPayload) => void;
}

function TradePanel({ externalPayload, onClose, onMutated, onSaved, openStock }: TradePanelProps) {
  const { open, payload, remountKey } = useStaggeredPanel(externalPayload);
  if (payload === null) return null;
  return (
    <TradePanelContent
      key={`trade-${remountKey}`}
      open={open}
      payload={payload}
      onClose={onClose}
      onMutated={onMutated}
      onSaved={onSaved}
      openStock={openStock}
    />
  );
}

interface TradePanelContentProps {
  open: boolean;
  payload: TradePayload;
  onClose: () => void;
  onMutated: () => void;
  onSaved: () => void;
  openStock: (p: StockPayload) => void;
}

function TradePanelContent({ open, payload, onClose, onMutated, onSaved, openStock }: TradePanelContentProps) {
  const { trade, accounts, allTrades } = payload;

  const handleStockPress = useMemo(
    () =>
      trade.ticker_symbol
        ? () =>
            openStock({
              assetName: trade.asset_name,
              ticker: trade.ticker_symbol!,
              country: trade.country_code ?? "KR",
              allTrades,
              accounts,
            })
        : undefined,
    [trade.ticker_symbol, trade.asset_name, trade.country_code, allTrades, accounts, openStock],
  );

  return (
    <FullScreenPanel open={open} onOpenChange={onClose}>
      <FullScreenPanelContent className="overflow-hidden">
        <TradeDetail
          trade={trade}
          accounts={accounts}
          onBack={onClose}
          onDeleted={onMutated}
          onSaved={onSaved}
          onStockPress={handleStockPress}
        />
      </FullScreenPanelContent>
    </FullScreenPanel>
  );
}

interface StockPanelProps {
  externalPayload: StockPayload | null;
  onClose: () => void;
  openTrade: (p: TradePayload) => void;
}

function StockPanel({ externalPayload, onClose, openTrade }: StockPanelProps) {
  const { open, payload, remountKey } = useStaggeredPanel(externalPayload);
  if (payload === null) return null;
  return (
    <StockPanelContent
      key={`stock-${remountKey}`}
      open={open}
      payload={payload}
      onClose={onClose}
      openTrade={openTrade}
    />
  );
}

interface StockPanelContentProps {
  open: boolean;
  payload: StockPayload;
  onClose: () => void;
  openTrade: (p: TradePayload) => void;
}

function StockPanelContent({ open, payload, onClose, openTrade }: StockPanelContentProps) {
  const { assetName, ticker, country, allTrades, accounts } = payload;
  const effectiveAccountId = useEffectiveAccountId(accounts);

  const filteredTrades = useMemo(
    () =>
      allTrades.filter(
        (t) =>
          (t.ticker_symbol ?? t.asset_name) === ticker &&
          (t.country_code ?? "KR") === country &&
          (effectiveAccountId === null || t.account_id === effectiveAccountId),
      ),
    [allTrades, ticker, country, effectiveAccountId],
  );

  const pnlMap = useMemo(() => buildPnlMap(allTrades), [allTrades]);

  const stats = useMemo(() => {
    const sellTrades = filteredTrades.filter((t) => t.trade_type === "SELL");
    const winCount = sellTrades.filter((t) => t.result === "SUCCESS").length;
    const totalProfitLoss = sellTrades.reduce(
      (sum, t) => sum + (pnlMap.get(t.id) ?? 0),
      0,
    );
    return {
      totalTrades: filteredTrades.length,
      sellCount: sellTrades.length,
      winCount,
      totalProfitLoss,
    };
  }, [filteredTrades, pnlMap]);

  const handleTradePress = useCallback(
    (trade: TradeWithAccount) => {
      openTrade({ trade, accounts, allTrades });
    },
    [openTrade, accounts, allTrades],
  );

  return (
    <FullScreenPanel open={open} onOpenChange={onClose}>
      <FullScreenPanelContent className="overflow-y-auto">
        <StockDetail
          assetName={assetName}
          ticker={ticker}
          country={country}
          trades={filteredTrades}
          stats={stats}
          accounts={accounts}
          onBack={onClose}
          onTradePress={handleTradePress}
        />
      </FullScreenPanelContent>
    </FullScreenPanel>
  );
}
