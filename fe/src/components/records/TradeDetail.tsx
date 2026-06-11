"use client";

import { useState } from "react";
import { useRouter } from "next/navigation";
import { useQuery } from "@tanstack/react-query";
import { useDialogState } from "@/hooks/useDialogState";
import { Button } from "@/components/base/Button";
import { FullScreenPanelFooter } from "@/components/base/FullScreenPanel";
import { TradeEditPanel } from "./TradeEditPanel";
import { TradeHeaderCard } from "./TradeHeaderCard";
import { AccountChip } from "@/components/shared/AccountChip";
import { ConfirmDeleteDialog } from "@/components/shared/ConfirmDeleteDialog";
import type { Account } from "@/types/database";
import { formatTradedAtLabel, type TradeWithAccount } from "@/lib/trade-utils";
import { tradesApi } from "@/lib/api-client";
import { queryKeys } from "@/lib/query-keys";
import { ChevronLeftIcon } from "lucide-react";
import { CompactRow } from "./trade-display";
import { STRATEGY_LABELS, EMOTION_LABELS, REASONING_TAG_LABELS, TRADE_TYPE } from "@/lib/constants/trading";
import { DEFAULT_COUNTRY_CODE } from "@/lib/constants/market";
import { currencyForCountry, formatMoney } from "@/lib/format";
import { TradeStrategyResultSection } from "./TradeStrategyResultSection";
import { SellResultSection } from "./SellResultSection";

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
  const deleteDialog = useDialogState();

  const [mountedAt] = useState(() => Date.now());
  const { data: trade = initialTrade } = useQuery({
    queryKey: queryKeys.trade(initialTrade.id),
    queryFn: () => tradesApi.get(initialTrade.id),
    initialData: initialTrade,
    initialDataUpdatedAt: mountedAt,
  });

  const handleDeleted = onDeleted ?? (() => router.push("/records"));

  function handleDeleteConfirm() {
    return deleteDialog.run(async () => {
      await tradesApi.delete(trade.id);
      handleDeleted();
    }, "삭제할 수 없습니다.");
  }

  const isBuy = trade.trade_type === TRADE_TYPE.BUY;

  const { data: summary } = useQuery({
    queryKey: queryKeys.tradeSummary(trade.id),
    queryFn: () => tradesApi.summary(trade.id),
    enabled: !isBuy,
  });
  const hasStock = !!trade.ticker_symbol;
  const stockHref = hasStock && !onStockPress
    ? `/stocks/${trade.country_code ?? DEFAULT_COUNTRY_CODE}/${trade.ticker_symbol}`
    : null;

  const tradedDate = formatTradedAtLabel(trade.traded_at);
  const tradeCurrency = currencyForCountry(trade.country_code ?? DEFAULT_COUNTRY_CODE);
  const priceNum = Number(trade.price);
  const quantity = Number(trade.quantity);
  const totalAmountNum = Number(trade.total_amount);
  const commission = formatMoney(Number(trade.commission), tradeCurrency);
  const tax = formatMoney(Number(trade.tax), tradeCurrency);

  return (
    <div className="h-[100dvh] flex flex-col overflow-hidden">
      {/* 헤더 */}
      <div
        className="flex-none bg-background"
        style={{ paddingTop: "var(--safe-area-inset-top, env(safe-area-inset-top))" }}
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
          tradeType={trade.trade_type}
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
              {trade.account ? <AccountChip account={trade.account} size="md" /> : "-"}
            </CompactRow>
            <CompactRow label="수수료">{commission}</CompactRow>
            {!isBuy && <CompactRow label="제세금">{tax}</CompactRow>}
          </div>
        </div>

        {!isBuy && <SellResultSection summary={summary} />}

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
                <span className="text-[13px] text-muted-foreground">매수 메모</span>
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
          onClick={() => deleteDialog.setOpen(true)}
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
        open={deleteDialog.open}
        onOpenChange={deleteDialog.setOpen}
        title="거래 삭제"
        description={
          <>
            <strong>{trade.asset_name}</strong> 거래 기록을 삭제하시겠습니까?
            <br />
            이 작업은 되돌릴 수 없습니다.
          </>
        }
        pending={deleteDialog.pending}
        error={deleteDialog.error}
        onConfirm={handleDeleteConfirm}
      />
    </div>
  );
}
