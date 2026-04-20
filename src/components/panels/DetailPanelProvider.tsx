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
import { useRouter, usePathname } from "next/navigation";
import {
  FullScreenPanel,
  FullScreenPanelContent,
  PANEL_ANIMATION_MS,
  useSnapshotWhileOpen,
} from "@/components/base/FullScreenPanel";
import { TradeDetail } from "@/components/records/TradeDetail";
import { StockDetail } from "@/components/stocks/StockDetail";
import { buildPnlMap } from "@/lib/analysis/realized-pnl";
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

type Mode = "trade" | "stock" | null;

interface DetailPanelContextValue {
  openTrade: (payload: TradePayload) => void;
  openStock: (payload: StockPayload) => void;
  close: () => void;
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
  const router = useRouter();

  const [mode, setMode] = useState<Mode>(null);
  const [tradePayload, setTradePayload] = useState<TradePayload | null>(null);
  const [stockPayload, setStockPayload] = useState<StockPayload | null>(null);

  const openTrade = useCallback((payload: TradePayload) => {
    setTradePayload(payload);
    setMode("trade");
  }, []);

  const openStock = useCallback((payload: StockPayload) => {
    setStockPayload(payload);
    setMode("stock");
  }, []);

  const close = useCallback(() => {
    setMode(null);
    // 슬라이드 아웃 애니메이션 완료 후 payload 정리 — 닫힌 패널의 useMemo 재계산 방지
    setTimeout(() => {
      setTradePayload(null);
      setStockPayload(null);
    }, PANEL_ANIMATION_MS + 50);
  }, []);

  // 라우트 이동 시 열린 패널 자동 닫기
  const pathname = usePathname();
  useEffect(() => {
    close();
  }, [pathname, close]);

  const handleTradeMutated = useCallback(() => {
    setMode(null);
    queryClient.invalidateQueries({ queryKey: ["portfolio"] });
    router.refresh();
  }, [queryClient, router]);

  const value = useMemo<DetailPanelContextValue>(
    () => ({ openTrade, openStock, close }),
    [openTrade, openStock, close],
  );

  // close 애니메이션 동안에도 직전 payload로 렌더되도록 스냅샷 유지
  const tradeOpen = mode === "trade";
  const stockOpen = mode === "stock";
  const tradeSnap = useSnapshotWhileOpen(tradeOpen, tradePayload);
  const stockSnap = useSnapshotWhileOpen(stockOpen, stockPayload);

  return (
    <DetailPanelContext.Provider value={value}>
      {children}
      {tradeSnap && (
        <TradePanel
          open={tradeOpen}
          payload={tradeSnap}
          onClose={close}
          onMutated={handleTradeMutated}
          openStock={openStock}
        />
      )}
      {stockSnap && (
        <StockPanel
          open={stockOpen}
          payload={stockSnap}
          onClose={close}
          openTrade={openTrade}
        />
      )}
    </DetailPanelContext.Provider>
  );
}

interface TradePanelProps {
  open: boolean;
  payload: TradePayload;
  onClose: () => void;
  onMutated: () => void;
  openStock: (p: StockPayload) => void;
}

function TradePanel({ open, payload, onClose, onMutated, openStock }: TradePanelProps) {
  const { trade, accounts, allTrades } = payload;

  const handleStockPress = trade.ticker_symbol
    ? () =>
        openStock({
          assetName: trade.asset_name,
          ticker: trade.ticker_symbol!,
          country: trade.country_code ?? "KR",
          allTrades,
          accounts,
        })
    : undefined;

  return (
    <FullScreenPanel open={open} onOpenChange={onClose}>
      <FullScreenPanelContent className="overflow-hidden">
        <TradeDetail
          trade={trade}
          accounts={accounts}
          onBack={onClose}
          onDeleted={onMutated}
          onSaved={onMutated}
          onStockPress={handleStockPress}
        />
      </FullScreenPanelContent>
    </FullScreenPanel>
  );
}

interface StockPanelProps {
  open: boolean;
  payload: StockPayload;
  onClose: () => void;
  openTrade: (p: TradePayload) => void;
}

function StockPanel({ open, payload, onClose, openTrade }: StockPanelProps) {
  const { assetName, ticker, country, allTrades, accounts } = payload;

  const filteredTrades = useMemo(
    () =>
      allTrades.filter(
        (t) =>
          (t.ticker_symbol ?? t.asset_name) === ticker &&
          (t.country_code ?? "KR") === country,
      ),
    [allTrades, ticker, country],
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
          onBack={onClose}
          onTradePress={handleTradePress}
        />
      </FullScreenPanelContent>
    </FullScreenPanel>
  );
}
