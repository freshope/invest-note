"use client";

import { useMemo, useState } from "react";
import { useRouter } from "next/navigation";
import { useQuery } from "@tanstack/react-query";
import { cn } from "@/lib/utils";
import { Button } from "@/components/base/Button";
import { BrokerLogo } from "@/components/base/BrokerLogo";
import { FullScreenPanelFooter } from "@/components/base/FullScreenPanel";
import { TradeEditPanel } from "./TradeEditPanel";
import { TradeHeaderCard } from "./TradeHeaderCard";
import { ConfirmDeleteDialog } from "@/components/shared/ConfirmDeleteDialog";
import type { Account, TradeResult } from "@/types/database";
import { formatTradedAtLabel, type TradeWithAccount } from "@/lib/trade-utils";
import { tradesApi } from "@/lib/api-client";
import { queryKeys } from "@/lib/query-keys";
import { ChevronLeftIcon } from "lucide-react";
import { CompactRow } from "./trade-display";
import { STRATEGY_LABELS, EMOTION_LABELS, REASONING_TAG_LABELS } from "@/lib/constants/trading";
import { PNL_COLORS } from "@/lib/constants/colors";
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



const RESULT_BADGE: Record<TradeResult, { label: string; classes: string }> = {
  SUCCESS: {
    label: "수익 ✅",
    classes: cn(PNL_COLORS.rise.bgSoft, PNL_COLORS.rise.text, PNL_COLORS.rise.borderSoft),
  },
  FAIL: {
    label: "손실 ❌",
    classes: cn(PNL_COLORS.fall.bgSoft, PNL_COLORS.fall.text, PNL_COLORS.fall.borderSoft),
  },
  BREAKEVEN: {
    label: "본전 ➖",
    classes: "bg-muted text-foreground border-border",
  },
};
const RESULT_BADGE_FALLBACK = { label: "–", classes: "bg-muted text-muted-foreground border-border" };

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
  const [deletePending, setDeletePending] = useState(false);
  const [deleteError, setDeleteError] = useState<string | null>(null);

  const mountedAt = useMemo(() => Date.now(), []);
  const { data: trade = initialTrade } = useQuery({
    queryKey: queryKeys.trade(initialTrade.id),
    queryFn: () => tradesApi.get(initialTrade.id),
    initialData: initialTrade,
    initialDataUpdatedAt: mountedAt,
  });

  const handleDeleted = onDeleted ?? (() => router.push("/records"));

  async function handleDeleteConfirm() {
    setDeleteError(null);
    setDeletePending(true);
    try {
      await tradesApi.delete(trade.id);
      setDeleteOpen(false);
      handleDeleted();
    } catch (err) {
      setDeleteError(err instanceof Error ? err.message : "삭제할 수 없습니다.");
    } finally {
      setDeletePending(false);
    }
  }

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

  const tradedDate = formatTradedAtLabel(trade.traded_at);
  const priceNum = Number(trade.price);
  const quantity = Number(trade.quantity);
  const totalAmountNum = Number(trade.total_amount);
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
        <TradeHeaderCard
          trade={trade}
          isBuy={isBuy}
          totalAmount={totalAmountNum}
          price={priceNum}
          quantity={quantity}
          onStockPress={onStockPress}
          stockHref={stockHref}
        />

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
        {!isBuy && (() => {
          const badge = summary?.result ? RESULT_BADGE[summary.result] : RESULT_BADGE_FALLBACK;
          return (
          <div className="rounded-2xl bg-muted/60 p-4 space-y-3">
            <p className="text-[12px] font-semibold text-muted-foreground uppercase tracking-wide">거래 결과 (자동 계산)</p>
            <div className="flex items-center justify-between">
              <span className={cn(
                "inline-flex items-center rounded-full px-2.5 py-0.5 text-[12px] font-bold border",
                badge.classes,
              )}>
                {badge.label}
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
          );
        })()}

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

      <ConfirmDeleteDialog
        open={deleteOpen}
        onOpenChange={setDeleteOpen}
        title="거래 삭제"
        description={
          <>
            <strong>{trade.asset_name}</strong> 거래 기록을 삭제하시겠습니까?
            <br />
            이 작업은 되돌릴 수 없습니다.
          </>
        }
        pending={deletePending}
        error={deleteError}
        onConfirm={handleDeleteConfirm}
      />
    </div>
  );
}
