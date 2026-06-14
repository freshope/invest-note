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
import { TradeFormPanel } from "@/components/records/TradeFormPanel";
import { StockDetail } from "@/components/stocks/StockDetail";
import { StockSwitchSheet } from "@/components/stocks/StockSwitchSheet";
import { AssetHistoryView } from "@/components/assets/AssetHistoryView";
import { useOpenStock } from "@/hooks/useOpenStock";
import { buildPnlMap } from "@/lib/analysis/realized-pnl";
import { queryKeys } from "@/lib/query-keys";
import { tradesApi } from "@/lib/api-client";
import { capture } from "@/lib/analytics";
import { TRADE_TYPE } from "@/lib/constants/trading";
import { DEFAULT_COUNTRY_CODE, isCountryCode } from "@/lib/constants/market";
import { useEffectiveAccountId } from "@/components/providers/AccountFilterProvider";
import type { SelectedStock } from "@/components/records/StockSearchInput";
import type { Account, TradeType } from "@/types/database";
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

export type TradeFormPayload = {
  accounts: Account[];
  prefill: { stock: SelectedStock; tradeType: TradeType; accountId: string | null };
};

// 필드가 모두 null 이면 계좌 전체 자산 뷰 (홈 헤더 진입), 모두 값이 있으면 종목 뷰.
// 판별 유니온 — 부분 null(예: ticker 만 있고 country 없음)을 타입 레벨에서 차단한다.
export type AssetHistoryPayload =
  | { assetName: string; ticker: string; country: string }
  | { assetName: null; ticker: null; country: null };

interface DetailPanelContextValue {
  openTrade: (payload: TradePayload, source?: string) => void;
  openStock: (payload: StockPayload, source?: string) => void;
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
  const [tradeFormPayload, setTradeFormPayload] = useState<TradeFormPayload | null>(null);

  // 상세 진입 수집(방식 A): 익명 메타데이터만 — ticker/assetName 등 종목 식별자는 절대 싣지 않는다.
  const openTrade = useCallback((payload: TradePayload, source?: string) => {
    capture("trade_detail_viewed", { source });
    setTradePayload(payload);
  }, []);
  const openStock = useCallback((payload: StockPayload, source?: string) => {
    capture("stock_detail_viewed", { country: payload.country, source });
    setStockPayload(payload);
  }, []);
  const openAssetHistory = useCallback((payload: AssetHistoryPayload) => {
    capture("asset_history_viewed", {
      scope: payload.assetName === null ? "all" : "stock",
      country: payload.country,
    });
    setAssetPayload(payload);
  }, []);
  // 종목 상세에서 prefill 된 거래 등록 폼. stockPayload 를 닫지 않고 위에 겹친다(openTrade 와 동일 패턴).
  const openTradeForm = useCallback((payload: TradeFormPayload) => {
    capture("trade_form_opened", {
      trade_type: payload.prefill.tradeType,
      country: payload.prefill.stock.market, // KR/US/OTHER — 민감값 아님
      source: "stock_detail",
    });
    setTradeFormPayload(payload);
  }, []);
  const closeTrade = useCallback(() => setTradePayload(null), []);
  const closeStock = useCallback(() => setStockPayload(null), []);
  const closeAssetHistory = useCallback(() => setAssetPayload(null), []);
  const closeTradeForm = useCallback(() => setTradeFormPayload(null), []);

  const pathname = usePathname();
  useEffect(() => {
    // 라우터(외부 상태) 변경 시 오버레이 패널을 닫는 것은 정당한 effect 사용.
    // eslint-disable-next-line react-hooks/set-state-in-effect
    setTradePayload(null);
    setStockPayload(null);
    setAssetPayload(null);
    setTradeFormPayload(null);
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
        openTradeForm={openTradeForm}
      />
      <AssetHistoryPanel
        externalPayload={assetPayload}
        onClose={closeAssetHistory}
        openAssetHistory={openAssetHistory}
      />
      <TradeFormHost externalPayload={tradeFormPayload} onClose={closeTradeForm} />
    </DetailPanelContext.Provider>
  );
}

interface TradePanelProps {
  externalPayload: TradePayload | null;
  onClose: () => void;
  onMutated: () => void;
  onSaved: () => void;
  openStock: (p: StockPayload, source?: string) => void;
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
  openStock: (p: StockPayload, source?: string) => void;
}

function TradePanelContent({ open, payload, onClose, onMutated, onSaved, openStock }: TradePanelContentProps) {
  const { trade, accounts, allTrades } = payload;

  const handleStockPress = useMemo(
    () =>
      trade.ticker_symbol
        ? () =>
            openStock(
              {
                assetName: trade.asset_name,
                ticker: trade.ticker_symbol!,
                country: trade.country_code ?? DEFAULT_COUNTRY_CODE,
                allTrades,
                accounts,
              },
              "trade_detail",
            )
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
  openStock: (p: StockPayload, source?: string) => void;
  openTrade: (p: TradePayload, source?: string) => void;
  openAssetHistory: (p: AssetHistoryPayload) => void;
  openTradeForm: (p: TradeFormPayload) => void;
}

function StockPanel({ externalPayload, onClose, openStock, openTrade, openAssetHistory, openTradeForm }: StockPanelProps) {
  const { open, payload, remountKey } = useStaggeredPanel(externalPayload);
  // 전환 시트는 리마운트되는 keyed content 밖(이 wrapper)에서 소유한다.
  // 종목 선택 → remountKey 증가로 content 가 unmount 돼도 시트는 살아남아 닫힘 애니메이션이 정상 동작.
  const [switchOpen, setSwitchOpen] = useState(false);
  const switchToStock = useOpenStock(openStock, "switch_sheet");

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
            openTradeForm={openTradeForm}
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
  openTrade: (p: TradePayload, source?: string) => void;
  openAssetHistory: (p: AssetHistoryPayload) => void;
  openTradeForm: (p: TradeFormPayload) => void;
  onSwitchStock: () => void;
}

function StockPanelContent({ payload, onClose, openTrade, openAssetHistory, openTradeForm, onSwitchStock }: StockPanelContentProps) {
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

  // 보유 수량 = 표시 중인(계좌 필터 반영) 거래의 net(BUY +, SELL -). 덧셈이라 정렬 무관.
  const holdingQuantity = useMemo(() => {
    const net = filteredTrades.reduce(
      (sum, t) => sum + (t.trade_type === TRADE_TYPE.BUY ? t.quantity : -t.quantity),
      0,
    );
    return Math.max(0, net);
  }, [filteredTrades]);

  const selectedStock = useMemo<SelectedStock>(
    () => ({
      name: assetName,
      code: ticker,
      market: isCountryCode(country) ? country : "OTHER",
      exchange: filteredTrades.find((t) => t.exchange)?.exchange ?? "",
    }),
    [assetName, ticker, country, filteredTrades],
  );

  const handleTradePress = useCallback(
    (trade: TradeWithAccount) => {
      openTrade({ trade, accounts, allTrades }, "stock_detail");
    },
    [openTrade, accounts, allTrades],
  );

  // 전체 계좌 뷰(effectiveAccountId=null)에서 매도 시: 이 종목을 보유한 계좌(net 최대)를 자동 선택한다.
  // 매도 버튼 활성 기준(전 계좌 합산 보유)과 폼 prefill 계좌의 출처를 일치시켜 "버튼은 켜졌는데 폼이 막힘"을 방지.
  const resolveFormAccountId = useCallback(
    (tradeType: TradeType): string | null => {
      if (effectiveAccountId !== null) return effectiveAccountId;
      if (tradeType !== TRADE_TYPE.SELL) return null; // 매수는 localStorage 기본 계좌에 맡김
      const netByAccount = new Map<string, number>();
      for (const t of filteredTrades) {
        const delta = t.trade_type === TRADE_TYPE.BUY ? t.quantity : -t.quantity;
        netByAccount.set(t.account_id, (netByAccount.get(t.account_id) ?? 0) + delta);
      }
      let best: string | null = null;
      let bestQty = 0;
      for (const [accId, qty] of netByAccount) {
        if (qty > bestQty) {
          bestQty = qty;
          best = accId;
        }
      }
      return best;
    },
    [effectiveAccountId, filteredTrades],
  );

  const handleOpenForm = useCallback(
    (tradeType: TradeType) => {
      openTradeForm({ accounts, prefill: { stock: selectedStock, tradeType, accountId: resolveFormAccountId(tradeType) } });
    },
    [openTradeForm, accounts, selectedStock, resolveFormAccountId],
  );

  return (
    <StockDetail
      assetName={assetName}
      ticker={ticker}
      country={country}
      trades={filteredTrades}
      stats={stats}
      accounts={accounts}
      holdingQuantity={holdingQuantity}
      onBack={onClose}
      onTradePress={handleTradePress}
      onAssetHistoryPress={() => openAssetHistory({ assetName, ticker, country })}
      onSwitchStock={onSwitchStock}
      onBuy={() => handleOpenForm(TRADE_TYPE.BUY)}
      onSell={() => handleOpenForm(TRADE_TYPE.SELL)}
    />
  );
}

interface TradeFormHostProps {
  externalPayload: TradeFormPayload | null;
  onClose: () => void;
}

function TradeFormHost({ externalPayload, onClose }: TradeFormHostProps) {
  // TradePanel/StockPanel 과 동일한 staggered 패턴 — 매 오픈마다 remountKey 로 폼/step 을 reset.
  const { open, payload, remountKey } = useStaggeredPanel(externalPayload);
  if (payload === null) return null;
  return (
    <TradeFormPanel
      key={`tradeform-${remountKey}`}
      open={open}
      onOpenChange={onClose}
      accounts={payload.accounts}
      prefillStock={payload.prefill.stock}
      prefillTradeType={payload.prefill.tradeType}
      prefillAccountId={payload.prefill.accountId}
      source="stock_detail"
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
