"use client";

import { useMemo, useState } from "react";
import Link from "next/link";
import { useRouter } from "next/navigation";
import { format } from "date-fns";
import { ko } from "date-fns/locale";
import { useQuery } from "@tanstack/react-query";
import { cn } from "@/lib/utils";
import { Button } from "@/components/base/Button";
import { BrokerLogo } from "@/components/base/BrokerLogo";
import { FullScreenPanelFooter } from "@/components/base/FullScreenPanel";
import { TradeEditPanel } from "./TradeEditPanel";
import { DeleteTradeDialog } from "./DeleteTradeDialog";
import type { Account } from "@/types/database";
import type { TradeWithAccount } from "@/lib/trade-utils";
import { tradesApi } from "@/lib/api-client";
import { queryKeys } from "@/lib/query-keys";
import { ChevronLeftIcon } from "lucide-react";
import { getQuantityUnit, CompactRow, CountryBadge, MarketTypeBadge, ExchangeBadge } from "./trade-display";
import { STRATEGY_LABELS, EMOTION_LABELS, REASONING_TAG_LABELS } from "@/lib/constants/trading";
import { fmt, formatPnL, signColor } from "@/lib/format";
import { TradeStrategyResultSection } from "./TradeStrategyResultSection";

interface TradeDetailProps {
  trade: TradeWithAccount;
  accounts: Account[];
  onBack?: () => void;
  onDeleted?: () => void;
  onSaved?: () => void;
  onStockPress?: () => void;
}



function InfoRow({ label, children }: { label: string; children: React.ReactNode }) {
  return (
    <div className="flex items-start justify-between gap-4 py-3 border-b border-border/50 last:border-0">
      <span className="text-[13px] text-muted-foreground flex-shrink-0">{label}</span>
      <span className="text-[14px] text-foreground text-right">{children}</span>
    </div>
  );
}

export function TradeDetail({ trade: initialTrade, accounts, onBack, onDeleted, onSaved, onStockPress }: TradeDetailProps) {
  const router = useRouter();
  const [editOpen, setEditOpen] = useState(false);
  const [deleteOpen, setDeleteOpen] = useState(false);

  const mountedAt = useMemo(() => Date.now(), []);
  const { data: trade = initialTrade } = useQuery({
    queryKey: queryKeys.trade(initialTrade.id),
    queryFn: () => tradesApi.get(initialTrade.id),
    initialData: initialTrade,
    initialDataUpdatedAt: mountedAt,
  });

  const handleDeleted = onDeleted ?? (() => router.push("/records"));

  const isBuy = trade.trade_type === "BUY";

  const { data: summary } = useQuery({
    queryKey: queryKeys.tradeSummary(trade.id),
    queryFn: () => tradesApi.summary(trade.id),
    enabled: !isBuy,
  });
  const hasStock = !!trade.ticker_symbol;
  const stockHref = hasStock && !onStockPress
    ? `/stocks/${trade.country_code ?? "KR"}/${trade.ticker_symbol}`
    : null;

  const tradedDate = format(new Date(trade.traded_at), "yyyy년 M월 d일 (EEE)", { locale: ko });
  const price = fmt(Number(trade.price));
  const quantity = Number(trade.quantity);
  const totalAmount = fmt(Number(trade.total_amount));
  const commission = fmt(Number(trade.commission));
  const tax = fmt(Number(trade.tax));

  return (
    <div className="h-[100dvh] flex flex-col overflow-hidden">
      {/* 헤더 */}
      <div
        className="flex-none bg-background"
        style={{ paddingTop: "env(safe-area-inset-top)" }}
      >
        <div className="relative flex h-14 items-center px-2">
          <button
            type="button"
            onClick={onBack ?? (() => router.back())}
            className="flex h-10 w-10 items-center justify-center rounded-full text-foreground transition-colors hover:bg-muted active:bg-muted"
            aria-label="뒤로"
          >
            <ChevronLeftIcon className="h-6 w-6" strokeWidth={2.2} />
          </button>
          <span className="absolute inset-x-0 text-center text-[17px] font-bold text-foreground pointer-events-none">
            거래 상세
          </span>
        </div>
      </div>

      <div className="flex-1 min-h-0 overflow-y-auto px-5 py-5 space-y-5">
        {/* 종목 헤더 카드 */}
        <div className={cn(
          "rounded-2xl overflow-hidden",
          "bg-muted/60"
        )}>
          <div className={cn(
            "h-1",
            isBuy ? "bg-[var(--rise)]" : "bg-[var(--fall)]"
          )} />
          <div className="p-5">
            <div className="flex items-center gap-2 mb-1">
              {onStockPress && hasStock ? (
                <button
                  type="button"
                  onClick={onStockPress}
                  className="text-[20px] font-bold text-foreground underline-offset-2 hover:underline text-left"
                >
                  {trade.asset_name}
                </button>
              ) : stockHref ? (
                <Link
                  href={stockHref}
                  className="text-[20px] font-bold text-foreground underline-offset-2 hover:underline"
                >
                  {trade.asset_name}
                </Link>
              ) : (
                <span className="text-[20px] font-bold text-foreground">{trade.asset_name}</span>
              )}
              <span
                className={cn(
                  "text-[12px] font-bold px-2 py-0.5 rounded-md",
                  isBuy
                    ? "bg-[var(--rise)]/10 text-[var(--rise)]"
                    : "bg-[var(--fall)]/10 text-[var(--fall)]"
                )}
              >
                {isBuy ? "매수" : "매도"}
              </span>
            </div>
            <div className="flex items-center gap-2 flex-wrap">
              {trade.ticker_symbol && (
                <span className="text-[13px] font-mono text-muted-foreground">{trade.ticker_symbol}</span>
              )}
              <MarketTypeBadge marketType={trade.market_type} />
              {trade.market_type === "STOCK" && (
                <>
                  <CountryBadge countryCode={trade.country_code ?? "KR"} />
                  <ExchangeBadge exchange={trade.exchange} />
                </>
              )}
            </div>
            <div className="mt-4 pt-4 border-t border-border/40">
              <p className={cn(
                "text-[24px] font-bold tabular-nums text-right",
                isBuy ? "text-[var(--rise)]" : "text-[var(--fall)]"
              )}>
                {totalAmount}원
              </p>
              <p className="text-[12px] text-muted-foreground text-right mt-0.5 tabular-nums">
                {price}원 × {quantity}{getQuantityUnit(trade.market_type)}
              </p>
            </div>
          </div>
        </div>

        {/* 기본 거래 정보 */}
        <div className="rounded-2xl bg-muted/60 p-4">
          <div className="grid grid-cols-2 gap-x-4 gap-y-3">
            <CompactRow label="날짜">{tradedDate}</CompactRow>
            <CompactRow label="계좌">
              {trade.account ? (
                <span className="inline-flex items-center gap-1">
                  {trade.account.broker && <BrokerLogo broker={trade.account.broker} size={16} />}
                  {trade.account.name}
                </span>
              ) : "-"}
            </CompactRow>
            <CompactRow label="수수료">{commission}원</CompactRow>
            {!isBuy && <CompactRow label="제세금">{tax}원</CompactRow>}
          </div>
        </div>

        {/* 거래 결과 (매도 자동 계산) */}
        {!isBuy && (
          <div className="rounded-2xl bg-muted/60 p-4 space-y-3">
            <p className="text-[12px] font-semibold text-muted-foreground uppercase tracking-wide">거래 결과 (자동 계산)</p>
            <div className="flex items-center justify-between">
              <span className={cn(
                "inline-flex items-center rounded-full px-2.5 py-0.5 text-[12px] font-bold border",
                summary?.result === "SUCCESS" && "bg-[var(--rise)]/10 text-[var(--rise)] border-[var(--rise)]/30",
                summary?.result === "FAIL" && "bg-[var(--fall)]/10 text-[var(--fall)] border-[var(--fall)]/30",
                summary?.result === "BREAKEVEN" && "bg-muted text-foreground border-border",
                !summary?.result && "bg-muted text-muted-foreground border-border",
              )}>
                {summary?.result === "SUCCESS" ? "수익 ✅" : summary?.result === "FAIL" ? "손실 ❌" : summary?.result === "BREAKEVEN" ? "본전 ➖" : "–"}
              </span>
              {summary?.pnl != null && (
                <span className={cn(
                  "text-[16px] font-bold tabular-nums",
                  signColor(summary.pnl, "none"),
                )}>
                  {formatPnL(summary.pnl)}
                </span>
              )}
            </div>
            {summary?.breakdown && !summary.breakdown.isManualInput && (
              <div className="rounded-lg bg-background border border-border/60 px-3 py-2.5 space-y-1.5">
                <div className="flex justify-between items-center">
                  <span className="text-[11px] text-muted-foreground">{`매도금액 (${fmt(summary.breakdown.sellPrice)}원 × ${summary.breakdown.quantity}주)`}</span>
                  <span className="text-[12px] tabular-nums text-foreground">+{fmt(summary.breakdown.sellAmount)}원</span>
                </div>
                <div className="flex justify-between items-center">
                  <span className="text-[11px] text-muted-foreground">{`매수비용 (평단 ${fmt(Math.round(summary.breakdown.avgCostPrice))}원 × ${summary.breakdown.quantity}주)`}</span>
                  <span className="text-[12px] tabular-nums text-foreground">-{fmt(summary.breakdown.costBasis)}원</span>
                </div>
                {summary.breakdown.commission > 0 && (
                  <div className="flex justify-between items-center">
                    <span className="text-[11px] text-muted-foreground">수수료</span>
                    <span className="text-[12px] tabular-nums text-foreground">-{fmt(summary.breakdown.commission)}원</span>
                  </div>
                )}
                {summary.breakdown.tax > 0 && (
                  <div className="flex justify-between items-center">
                    <span className="text-[11px] text-muted-foreground">세금</span>
                    <span className="text-[12px] tabular-nums text-foreground">-{fmt(summary.breakdown.tax)}원</span>
                  </div>
                )}
                <div className="border-t border-border/60 pt-1.5 flex justify-between items-center">
                  <span className="text-[12px] font-semibold text-foreground">실현손익</span>
                  <span className={cn(
                    "text-[13px] font-bold tabular-nums",
                    summary.pnl != null && signColor(summary.pnl, "none"),
                  )}>
                    {summary.pnl != null ? formatPnL(summary.pnl) : "–"}
                  </span>
                </div>
              </div>
            )}
          </div>
        )}

        {/* 전략 결과 (매도) */}
        {!isBuy && (
          <TradeStrategyResultSection
            tradedAt={trade.traded_at}
            holdingDays={summary?.holdingDays ?? null}
            strategyEvaluation={summary?.strategyEvaluation ?? null}
          />
        )}

        {/* 근거 / 감정 */}
        {((isBuy && trade.strategy_type) || trade.emotion || trade.reasoning_tags?.length || trade.buy_reason) && (
          <div className="rounded-2xl bg-muted/60 px-4 py-1">
            {isBuy && trade.strategy_type && (
              <InfoRow label="전략">{STRATEGY_LABELS[trade.strategy_type] ?? trade.strategy_type}</InfoRow>
            )}
            {trade.emotion && (
              <InfoRow label={isBuy ? "감정" : "감정 (자동)"}>
                {EMOTION_LABELS[trade.emotion] ?? trade.emotion}
              </InfoRow>
            )}
            {trade.reasoning_tags && trade.reasoning_tags.length > 0 && (
              <InfoRow label={isBuy ? "분석 태그" : "분석 태그 (자동)"}>
                <div className="flex flex-wrap gap-1 justify-end">
                  {trade.reasoning_tags.map((tag) => (
                    <span key={tag} className="text-[11px] px-2 py-0.5 rounded-full bg-primary/10 text-primary font-medium">
                      {REASONING_TAG_LABELS[tag] ?? tag}
                    </span>
                  ))}
                </div>
              </InfoRow>
            )}
            {trade.buy_reason && (
              <div className="py-3 border-b border-border/50 last:border-0 space-y-1">
                <span className="text-[13px] text-muted-foreground">매수 근거</span>
                <p className="text-[14px] text-foreground whitespace-pre-wrap">{trade.buy_reason}</p>
              </div>
            )}
          </div>
        )}

        {/* 매도 이유 */}
        {!isBuy && trade.sell_reason && (
          <div className="rounded-2xl bg-muted/60 px-4 py-3 space-y-1">
            <span className="text-[13px] text-muted-foreground">매도 이유</span>
            <p className="text-[14px] text-foreground whitespace-pre-wrap">{trade.sell_reason}</p>
          </div>
        )}
      </div>

      {/* 하단 버튼 */}
      <FullScreenPanelFooter sticky={false} className="flex-none flex gap-3">
        <Button
          type="button"
          variant="outline"
          size="xl"
          className="flex-1 text-destructive border-destructive/30 hover:bg-destructive/5"
          onClick={() => setDeleteOpen(true)}
        >
          삭제
        </Button>
        <Button
          type="button"
          size="xl"
          className="flex-1"
          onClick={() => setEditOpen(true)}
        >
          수정
        </Button>
      </FullScreenPanelFooter>

      <TradeEditPanel
        open={editOpen}
        onOpenChange={setEditOpen}
        trade={trade}
        accounts={accounts}
        onSaved={onSaved}
      />

      <DeleteTradeDialog
        open={deleteOpen}
        onOpenChange={setDeleteOpen}
        tradeId={trade.id}
        assetName={trade.asset_name}
        onDeleted={handleDeleted}
      />
    </div>
  );
}
