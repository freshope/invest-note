"use client";

import {
  createContext,
  useCallback,
  useContext,
  useEffect,
  useMemo,
  useState,
} from "react";
import { useQuery, useQueryClient } from "@tanstack/react-query";
import { usePathname } from "next/navigation";
import {
  FullScreenPanel,
  FullScreenPanelContent,
  useStaggeredPanel,
} from "@/components/base/FullScreenPanel";
import { TradeDetail } from "@/components/records/TradeDetail";
import { StockDetail } from "@/components/stocks/StockDetail";
import { StockSwitchSheet } from "@/components/stocks/StockSwitchSheet";
import { AssetHistoryView } from "@/components/assets/AssetHistoryView";
import { useOpenStock } from "@/hooks/useOpenStock";
import { buildPnlMap } from "@/lib/analysis/realized-pnl";
import { queryKeys } from "@/lib/query-keys";
import { tradesApi } from "@/lib/api-client";
import { TRADE_TYPE } from "@/lib/constants/trading";
import { DEFAULT_COUNTRY_CODE } from "@/lib/constants/market";
import { useEffectiveAccountId } from "@/components/providers/AccountFilterProvider";
import type { Account } from "@/types/database";
import type { TradeWithAccount } from "@/lib/trade-utils";
import type { Position } from "@/lib/portfolio";

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

// 필드가 모두 null 이면 계좌 전체 자산 뷰 (홈 헤더 진입), 값이 있으면 종목 뷰.
export type AssetHistoryPayload = {
  assetName: string | null;
  ticker: string | null;
  country: string | null;
};

interface DetailPanelContextValue {
  openTrade: (payload: TradePayload) => void;
  openStock: (payload: StockPayload) => void;
  openAssetHistory: (payload: AssetHistoryPayload) => void;
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
  const [assetPayload, setAssetPayload] = useState<AssetHistoryPayload | null>(null);

  const openTrade = useCallback((payload: TradePayload) => setTradePayload(payload), []);
  const openStock = useCallback((payload: StockPayload) => setStockPayload(payload), []);
  const openAssetHistory = useCallback(
    (payload: AssetHistoryPayload) => setAssetPayload(payload),
    [],
  );
  const closeTrade = useCallback(() => setTradePayload(null), []);
  const closeStock = useCallback(() => setStockPayload(null), []);
  const closeAssetHistory = useCallback(() => setAssetPayload(null), []);

  const pathname = usePathname();
  useEffect(() => {
    // 라우터(외부 상태) 변경 시 오버레이 패널을 닫는 것은 정당한 effect 사용.
    // eslint-disable-next-line react-hooks/set-state-in-effect
    setTradePayload(null);
    setStockPayload(null);
    setAssetPayload(null);
  }, [pathname]);

  const handleTradeMutated = useCallback(() => {
    setTradePayload(null);
    queryClient.invalidateQueries({ queryKey: queryKeys.portfolio });
    queryClient.invalidateQueries({ queryKey: queryKeys.trades });
    queryClient.invalidateQueries({ queryKey: queryKeys.assets });
  }, [queryClient]);

  const handleTradeSaved = useCallback(() => {
    queryClient.invalidateQueries({ queryKey: queryKeys.portfolio });
    queryClient.invalidateQueries({ queryKey: queryKeys.trades });
    queryClient.invalidateQueries({ queryKey: queryKeys.assets });
  }, [queryClient]);

  const value = useMemo<DetailPanelContextValue>(
    () => ({ openTrade, openStock, openAssetHistory }),
    [openTrade, openStock, openAssetHistory],
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
        openStock={openStock}
        openTrade={openTrade}
        openAssetHistory={openAssetHistory}
      />
      <AssetHistoryPanel
        externalPayload={assetPayload}
        onClose={closeAssetHistory}
        openAssetHistory={openAssetHistory}
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
              country: trade.country_code ?? DEFAULT_COUNTRY_CODE,
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
  openStock: (p: StockPayload) => void;
  openTrade: (p: TradePayload) => void;
  openAssetHistory: (p: AssetHistoryPayload) => void;
}

function StockPanel({ externalPayload, onClose, openStock, openTrade, openAssetHistory }: StockPanelProps) {
  const { open, payload, remountKey } = useStaggeredPanel(externalPayload);
  // 전환 시트는 리마운트되는 keyed content 밖(이 wrapper)에서 소유한다.
  // 종목 선택 → remountKey 증가로 content 가 unmount 돼도 시트는 살아남아 닫힘 애니메이션이 정상 동작.
  const [switchOpen, setSwitchOpen] = useState(false);
  const switchToStock = useOpenStock(openStock);

  if (payload === null) return null;

  const currentKey = `${payload.ticker}:${payload.country}`;
  const handleSelect = (pos: Position) => {
    setSwitchOpen(false);
    if (pos.key !== currentKey) switchToStock(pos);
  };

  return (
    <>
      {/* FullScreenPanel(슬라이드 lifecycle)은 유지하고 content surface(=스크롤 컨테이너)만
          remountKey 로 교체한다. visible 이 이미 true 라 새 surface 는 translate-x-0 으로 바로
          마운트돼 슬라이드 애니메이션이 재생되지 않고, 동시에 스크롤이 상단으로 리셋된다. */}
      <FullScreenPanel open={open} onOpenChange={onClose}>
        <FullScreenPanelContent key={`stock-${remountKey}`} className="overflow-y-auto">
          <StockPanelContent
            payload={payload}
            onClose={onClose}
            openTrade={openTrade}
            openAssetHistory={openAssetHistory}
            onSwitchStock={() => setSwitchOpen(true)}
          />
        </FullScreenPanelContent>
      </FullScreenPanel>
      <StockSwitchSheet
        open={switchOpen}
        onOpenChange={setSwitchOpen}
        currentKey={currentKey}
        onSelect={handleSelect}
      />
    </>
  );
}

interface StockPanelContentProps {
  payload: StockPayload;
  onClose: () => void;
  openTrade: (p: TradePayload) => void;
  openAssetHistory: (p: AssetHistoryPayload) => void;
  onSwitchStock: () => void;
}

function StockPanelContent({ payload, onClose, openTrade, openAssetHistory, onSwitchStock }: StockPanelContentProps) {
  const { assetName, ticker, country, allTrades: initialTrades, accounts: initialAccounts } = payload;

  // 거래 mutation 후 queryKeys.trades 가 invalidate 되면 prefix 매칭으로 함께 refetch 되도록
  // 종목 필터 리스트를 react-query 로 구독한다. 패널 오픈 시 이미 가져온 데이터는 initialData 로 주입.
  const [mountedAt] = useState(() => Date.now());
  const { data } = useQuery({
    queryKey: [...queryKeys.trades, ticker, country],
    queryFn: () => tradesApi.list({ ticker, country }),
    initialData: { trades: initialTrades, accounts: initialAccounts },
    initialDataUpdatedAt: mountedAt,
  });
  const allTrades = data?.trades ?? initialTrades;
  const accounts = data?.accounts ?? initialAccounts;

  const effectiveAccountId = useEffectiveAccountId(accounts);

  const filteredTrades = useMemo(
    () =>
      allTrades.filter(
        (t) =>
          (t.ticker_symbol ?? t.asset_name) === ticker &&
          (t.country_code ?? DEFAULT_COUNTRY_CODE) === country &&
          (effectiveAccountId === null || t.account_id === effectiveAccountId),
      ),
    [allTrades, ticker, country, effectiveAccountId],
  );

  const pnlMap = useMemo(() => buildPnlMap(allTrades), [allTrades]);

  const stats = useMemo(() => {
    const sellTrades = filteredTrades.filter((t) => t.trade_type === TRADE_TYPE.SELL);
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
    <StockDetail
      assetName={assetName}
      ticker={ticker}
      country={country}
      trades={filteredTrades}
      stats={stats}
      accounts={accounts}
      onBack={onClose}
      onTradePress={handleTradePress}
      onAssetHistoryPress={() => openAssetHistory({ assetName, ticker, country })}
      onSwitchStock={onSwitchStock}
    />
  );
}

interface AssetHistoryPanelProps {
  externalPayload: AssetHistoryPayload | null;
  onClose: () => void;
  openAssetHistory: (p: AssetHistoryPayload) => void;
}

function AssetHistoryPanel({ externalPayload, onClose, openAssetHistory }: AssetHistoryPanelProps) {
  const { open, payload, remountKey } = useStaggeredPanel(externalPayload);
  // 전환 시트는 remount 되는 keyed FullScreenPanel 밖(이 wrapper)에서 소유한다.
  const [switchOpen, setSwitchOpen] = useState(false);

  if (payload === null) return null;

  const currentKey = `${payload.ticker}:${payload.country}`;
  const handleSelect = (pos: Position) => {
    setSwitchOpen(false);
    if (pos.key !== currentKey) {
      openAssetHistory({ assetName: pos.assetName, ticker: pos.ticker, country: pos.country });
    }
  };

  return (
    <>
      {/* FullScreenPanel(슬라이드 lifecycle)은 유지하고 content surface 만 remountKey 로 교체한다.
          → 종목 전환 시 슬라이드 애니메이션 없이 내용만 즉시 바뀐다(StockPanel 과 동일 패턴). */}
      <FullScreenPanel open={open} onOpenChange={onClose}>
        <FullScreenPanelContent key={`asset-${remountKey}`}>
          <AssetHistoryView
            ticker={payload.ticker}
            country={payload.country}
            name={payload.assetName}
            onBack={onClose}
            onSwitchStock={() => setSwitchOpen(true)}
          />
        </FullScreenPanelContent>
      </FullScreenPanel>
      <StockSwitchSheet
        open={switchOpen}
        onOpenChange={setSwitchOpen}
        currentKey={currentKey}
        onSelect={handleSelect}
      />
    </>
  );
}
