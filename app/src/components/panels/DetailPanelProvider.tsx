"use client";

import {
  createContext,
  useCallback,
  useContext,
  useEffect,
  useMemo,
  useRef,
  useState,
} from "react";
import { useQueryClient } from "@tanstack/react-query";
import { usePathname } from "next/navigation";
import {
  FullScreenPanel,
  FullScreenPanelContent,
  PANEL_ANIMATION_MS,
} from "@/components/base/FullScreenPanel";
import { TradeDetail } from "@/components/records/TradeDetail";
import { StockDetail } from "@/components/stocks/StockDetail";
import { buildPnlMap } from "@/lib/analysis/realized-pnl";
import { queryKeys } from "@/lib/query-keys";
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

  // open과 payload를 분리해 슬라이드 아웃 중에도 payload가 살아있도록 함
  const [tradeOpen, setTradeOpen] = useState(false);
  const [tradePayload, setTradePayload] = useState<TradePayload | null>(null);
  const [stockOpen, setStockOpen] = useState(false);
  const [stockPayload, setStockPayload] = useState<StockPayload | null>(null);
  // key가 바뀌면 React가 기존 Panel을 즉시 언마운트(portal 제거)하고 새로 마운트
  const [tradeKey, setTradeKey] = useState(0);
  const [stockKey, setStockKey] = useState(0);

  // 콜백 안에서 최신 payload를 읽기 위한 ref (deps 없이 stable 콜백 유지)
  const tradePayloadRef = useRef<TradePayload | null>(null);
  const stockPayloadRef = useRef<StockPayload | null>(null);
  tradePayloadRef.current = tradePayload;
  stockPayloadRef.current = stockPayload;

  // 슬라이드 아웃 후 payload를 정리하는 타이머 ref
  const tradeCloseTimer = useRef<ReturnType<typeof setTimeout> | null>(null);
  const stockCloseTimer = useRef<ReturnType<typeof setTimeout> | null>(null);

  // 언마운트 시 대기 중인 타이머 정리
  useEffect(() => {
    return () => {
      if (tradeCloseTimer.current !== null) clearTimeout(tradeCloseTimer.current);
      if (stockCloseTimer.current !== null) clearTimeout(stockCloseTimer.current);
    };
  }, []);

  const openTrade = useCallback((payload: TradePayload) => {
    // 닫히는 중이면 payload 정리 타이머를 취소해 현재 payload를 유지
    if (tradeCloseTimer.current !== null) {
      clearTimeout(tradeCloseTimer.current);
      tradeCloseTimer.current = null;
    }
    if (tradePayloadRef.current !== null) {
      // 이미 열려 있으면 key를 바꿔 기존 portal을 즉시 제거 후 새 panel slide-in
      setTradeKey((k) => k + 1);
    }
    setTradePayload(payload);
    setTradeOpen(true);
  }, []);

  const openStock = useCallback((payload: StockPayload) => {
    if (stockCloseTimer.current !== null) {
      clearTimeout(stockCloseTimer.current);
      stockCloseTimer.current = null;
    }
    if (stockPayloadRef.current !== null) {
      setStockKey((k) => k + 1);
    }
    setStockPayload(payload);
    setStockOpen(true);
  }, []);

  const closeTrade = useCallback(() => {
    setTradeOpen(false);
    // 슬라이드 아웃 완료 후 payload를 비워 Panel을 React 트리에서 제거
    tradeCloseTimer.current = setTimeout(() => {
      tradeCloseTimer.current = null;
      setTradePayload(null);
    }, PANEL_ANIMATION_MS + 50);
  }, []);

  const closeStock = useCallback(() => {
    setStockOpen(false);
    stockCloseTimer.current = setTimeout(() => {
      stockCloseTimer.current = null;
      setStockPayload(null);
    }, PANEL_ANIMATION_MS + 50);
  }, []);

  const closeAll = useCallback(() => {
    if (tradeCloseTimer.current !== null) {
      clearTimeout(tradeCloseTimer.current);
      tradeCloseTimer.current = null;
    }
    if (stockCloseTimer.current !== null) {
      clearTimeout(stockCloseTimer.current);
      stockCloseTimer.current = null;
    }
    setTradeOpen(false);
    setStockOpen(false);
    tradeCloseTimer.current = setTimeout(() => {
      tradeCloseTimer.current = null;
      setTradePayload(null);
    }, PANEL_ANIMATION_MS + 50);
    stockCloseTimer.current = setTimeout(() => {
      stockCloseTimer.current = null;
      setStockPayload(null);
    }, PANEL_ANIMATION_MS + 50);
  }, []);

  // 라우트 이동 시 열린 판넬 자동 닫기
  const pathname = usePathname();
  useEffect(() => {
    closeAll();
  }, [pathname, closeAll]);

  const handleTradeMutated = useCallback(() => {
    closeTrade();
    queryClient.invalidateQueries({ queryKey: queryKeys.portfolio });
    queryClient.invalidateQueries({ queryKey: queryKeys.trades });
  }, [closeTrade, queryClient]);

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
      {tradePayload !== null && (
        <TradePanel
          key={`trade-${tradeKey}`}
          open={tradeOpen}
          payload={tradePayload}
          onClose={closeTrade}
          onMutated={handleTradeMutated}
          onSaved={handleTradeSaved}
          openStock={openStock}
        />
      )}
      {stockPayload !== null && (
        <StockPanel
          key={`stock-${stockKey}`}
          open={stockOpen}
          payload={stockPayload}
          onClose={closeStock}
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
  onSaved: () => void;
  openStock: (p: StockPayload) => void;
}

function TradePanel({ open, payload, onClose, onMutated, onSaved, openStock }: TradePanelProps) {
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
