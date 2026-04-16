"use client";

import { useState } from "react";
import Link from "next/link";
import { useRouter } from "next/navigation";
import { format } from "date-fns";
import { ko } from "date-fns/locale";
import { cn } from "@/lib/utils";
import { Button } from "@/components/base/Button";
import { TradeEditPanel } from "./TradeEditPanel";
import { DeleteTradeDialog } from "./DeleteTradeDialog";
import type { Account } from "@/types/database";
import type { TradeWithAccount } from "@/lib/trade-utils";
import { ChevronLeftIcon } from "lucide-react";

interface TradeDetailProps {
  trade: TradeWithAccount;
  accounts: Account[];
  onBack?: () => void;
  onDeleted?: () => void;
  onSaved?: () => void;
  onStockPress?: () => void;
}

const STRATEGY_LABELS: Record<string, string> = {
  SCALPING: "스캘핑",
  SWING: "스윙",
  LONG_TERM: "장기",
  UNKNOWN: "없음",
};

const EMOTION_LABELS: Record<string, string> = {
  CONFIDENT: "확신 😊",
  ANXIOUS: "불안 😰",
  FOMO: "FOMO 😤",
  IMPULSIVE: "충동 ⚡",
  CALM: "평온 😌",
};

const REASONING_TAG_LABELS: Record<string, string> = {
  TECHNICAL: "기술적 분석",
  FUNDAMENTAL: "펀더멘탈",
  NEWS: "뉴스/이슈",
  FEELING: "감/직감",
};

const RESULT_LABELS: Record<string, string> = {
  SUCCESS: "수익 ✅",
  FAIL: "손실 ❌",
  BREAKEVEN: "본전 ➖",
};

const MARKET_LABELS: Record<string, string> = {
  STOCK: "주식",
  CRYPTO: "암호화폐",
  ETC: "기타",
};

function InfoRow({ label, children }: { label: string; children: React.ReactNode }) {
  return (
    <div className="flex items-start justify-between gap-4 py-3 border-b border-border/50 last:border-0">
      <span className="text-[13px] text-muted-foreground flex-shrink-0">{label}</span>
      <span className="text-[14px] text-foreground text-right">{children}</span>
    </div>
  );
}

export function TradeDetail({ trade, accounts, onBack, onDeleted, onSaved, onStockPress }: TradeDetailProps) {
  const router = useRouter();
  const [editOpen, setEditOpen] = useState(false);
  const [deleteOpen, setDeleteOpen] = useState(false);

  const handleDeleted = onDeleted ?? (() => router.push("/records"));

  const isBuy = trade.trade_type === "BUY";
  const hasStock = !!trade.ticker_symbol;
  const stockHref = hasStock && !onStockPress
    ? `/stocks/${trade.country_code ?? "KR"}/${trade.ticker_symbol}`
    : null;

  const tradedDate = format(new Date(trade.traded_at), "yyyy년 M월 d일 (EEE) HH:mm", { locale: ko });
  const price = Number(trade.price).toLocaleString("ko-KR");
  const quantity = Number(trade.quantity);
  const totalAmount = Number(trade.total_amount).toLocaleString("ko-KR");
  const commission = Number(trade.commission).toLocaleString("ko-KR");
  const tax = Number(trade.tax).toLocaleString("ko-KR");

  return (
    <>
      {/* 헤더 */}
      <div
        className="sticky top-0 z-10 bg-background flex items-center px-2"
        style={{ height: "calc(3.5rem + env(safe-area-inset-top))", paddingTop: "env(safe-area-inset-top)" }}
      >
        <button
          type="button"
          onClick={onBack ?? (() => router.back())}
          className="flex h-10 w-10 items-center justify-center rounded-full text-foreground transition-colors hover:bg-muted active:bg-muted"
          aria-label="뒤로"
        >
          <ChevronLeftIcon className="h-6 w-6" strokeWidth={2.2} />
        </button>
        <span className="absolute left-1/2 -translate-x-1/2 text-[17px] font-bold text-foreground">
          거래 상세
        </span>
      </div>

      <div className="px-5 pb-32 space-y-5">
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
            {trade.ticker_symbol && (
              <div className="flex items-center gap-2">
                <span className="text-[13px] font-mono text-muted-foreground">{trade.ticker_symbol}</span>
                <span className={cn(
                  "text-[11px] font-bold px-1.5 py-0.5 rounded-md",
                  (trade.country_code ?? "KR") === "KR"
                    ? "bg-blue-100 text-blue-700 dark:bg-blue-900/40 dark:text-blue-300"
                    : (trade.country_code ?? "KR") === "US"
                    ? "bg-orange-100 text-orange-700 dark:bg-orange-900/40 dark:text-orange-300"
                    : "bg-muted text-muted-foreground"
                )}>
                  {(trade.country_code ?? "KR") === "KR" ? "국내" : (trade.country_code ?? "KR") === "US" ? "해외" : "기타"}
                </span>
              </div>
            )}
          </div>
        </div>

        {/* 기본 거래 정보 */}
        <div className="rounded-2xl bg-muted/60 px-4 py-1">
          <InfoRow label="날짜">{tradedDate}</InfoRow>
          <InfoRow label="계좌">
            {trade.account
              ? `${trade.account.name}${trade.account.broker ? ` · ${trade.account.broker}` : ""}`
              : "-"}
          </InfoRow>
          <InfoRow label="시장">{MARKET_LABELS[trade.market_type] ?? trade.market_type}</InfoRow>
          <InfoRow label="가격">{price}원</InfoRow>
          <InfoRow label="수량">{quantity}주</InfoRow>
          <InfoRow label="총액"><span className="font-semibold">{totalAmount}원</span></InfoRow>
          <InfoRow label="수수료">{commission}원</InfoRow>
          {isBuy ? null : <InfoRow label="제세금">{tax}원</InfoRow>}
        </div>

        {/* 결과 (매도) */}
        {!isBuy && (trade.result || trade.profit_loss != null) && (
          <div className="rounded-2xl bg-muted/60 px-4 py-1">
            {trade.result && (
              <InfoRow label="결과">
                <span className={cn(
                  "font-bold",
                  trade.result === "SUCCESS" && "text-[var(--rise)]",
                  trade.result === "FAIL" && "text-[var(--fall)]",
                )}>
                  {RESULT_LABELS[trade.result]}
                </span>
              </InfoRow>
            )}
            {trade.profit_loss != null && (
              <InfoRow label="손익">
                <span className={cn(
                  "font-bold",
                  Number(trade.profit_loss) > 0 && "text-[var(--rise)]",
                  Number(trade.profit_loss) < 0 && "text-[var(--fall)]",
                )}>
                  {Number(trade.profit_loss) > 0 ? "+" : ""}
                  {Number(trade.profit_loss).toLocaleString("ko-KR")}원
                </span>
              </InfoRow>
            )}
          </div>
        )}

        {/* 근거 / 감정 */}
        {(trade.strategy_type || trade.emotion || (trade.reasoning_tags && trade.reasoning_tags.length > 0) || trade.buy_reason) && (
          <div className="rounded-2xl bg-muted/60 px-4 py-1">
            {trade.strategy_type && (
              <InfoRow label="전략">{STRATEGY_LABELS[trade.strategy_type] ?? trade.strategy_type}</InfoRow>
            )}
            {trade.emotion && (
              <InfoRow label="감정">{EMOTION_LABELS[trade.emotion] ?? trade.emotion}</InfoRow>
            )}
            {trade.reasoning_tags && trade.reasoning_tags.length > 0 && (
              <InfoRow label="분석 태그">
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

        {/* 회고 (매도) */}
        {!isBuy && (trade.sell_reason || trade.reflection_note || trade.improvement_note) && (
          <div className="rounded-2xl bg-muted/60 px-4 py-3 space-y-4">
            {trade.sell_reason && (
              <div className="space-y-1">
                <span className="text-[13px] text-muted-foreground">매도 이유</span>
                <p className="text-[14px] text-foreground whitespace-pre-wrap">{trade.sell_reason}</p>
              </div>
            )}
            {trade.reflection_note && (
              <div className="space-y-1">
                <span className="text-[13px] text-muted-foreground">잘한 점 / 배운 점</span>
                <p className="text-[14px] text-foreground whitespace-pre-wrap">{trade.reflection_note}</p>
              </div>
            )}
            {trade.improvement_note && (
              <div className="space-y-1">
                <span className="text-[13px] text-muted-foreground">개선할 점</span>
                <p className="text-[14px] text-foreground whitespace-pre-wrap">{trade.improvement_note}</p>
              </div>
            )}
          </div>
        )}
      </div>

      {/* 하단 버튼 */}
      <div
        className="fixed bottom-0 left-0 right-0 bg-background border-t border-border px-5 pt-3 pb-4 flex gap-3"
        style={{ paddingBottom: "calc(1rem + env(safe-area-inset-bottom))" }}
      >
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
      </div>

      {editOpen && (
        <TradeEditPanel
          open={editOpen}
          onOpenChange={setEditOpen}
          trade={trade}
          accounts={accounts}
          onSaved={onSaved}
        />
      )}

      <DeleteTradeDialog
        open={deleteOpen}
        onOpenChange={setDeleteOpen}
        tradeId={trade.id}
        assetName={trade.asset_name}
        onDeleted={handleDeleted}
      />
    </>
  );
}
