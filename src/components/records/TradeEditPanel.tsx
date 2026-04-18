"use client";

import { useState, useCallback } from "react";
import { useRouter } from "next/navigation";
import {
  FullScreenPanel,
  FullScreenPanelContent,
  FullScreenPanelHeader,
  FullScreenPanelBody,
} from "@/components/base/FullScreenPanel";
import { Button } from "@/components/base/Button";
import { Input } from "@/components/base/Input";
import { Label } from "@/components/base/Label";
import { Textarea } from "@/components/base/Textarea";
import {
  Select,
  SelectContent,
  SelectItem,
  SelectTrigger,
  SelectValue,
} from "@/components/base/Select";
import { Popover, PopoverContent, PopoverTrigger } from "@/components/base/Popover";
import { Calendar } from "@/components/base/Calendar";
import { tradesApi } from "@/lib/api-client";
import { StockSearchInput, type SelectedStock } from "./StockSearchInput";
import { STRATEGIES, EMOTIONS, REASONING_TAGS } from "./constants";
import { cn } from "@/lib/utils";
import type { Trade, Account, TradeType, TradeResult, ReasoningTag } from "@/types/database";
import { CalendarIcon } from "lucide-react";
import { format } from "date-fns";
import { ko } from "date-fns/locale";

interface TradeEditPanelProps {
  open: boolean;
  onOpenChange: (open: boolean) => void;
  trade: Trade & { account?: Pick<Account, "name" | "broker"> };
  accounts: Account[];
  onSaved?: () => void;
}

const RESULTS: { value: TradeResult; label: string; color: string }[] = [
  { value: "SUCCESS", label: "수익 ✅", color: "bg-[var(--rise)] text-white border-[var(--rise)]" },
  { value: "FAIL", label: "손실 ❌", color: "bg-[var(--fall)] text-white border-[var(--fall)]" },
  { value: "BREAKEVEN", label: "본전 ➖", color: "bg-muted text-foreground border-border" },
];

function formatNumber(raw: string): string {
  const cleaned = raw.replace(/[^0-9.]/g, "");
  const parts = cleaned.split(".");
  const integer = parts[0] || "";
  const decimal = parts.length > 1 ? "." + parts[1] : "";
  if (!integer && !decimal) return "";
  return (integer ? Number(integer).toLocaleString("ko-KR") : "") + decimal;
}

function formatPnL(raw: string): string {
  const cleaned = raw.replace(/[^0-9-]/g, "");
  if (!cleaned || cleaned === "-") return cleaned;
  const isNeg = cleaned.startsWith("-");
  const digits = cleaned.replace(/-/g, "");
  if (!digits) return isNeg ? "-" : "";
  return (isNeg ? "-" : "") + Number(digits).toLocaleString("ko-KR");
}

function parseRaw(formatted: string): string {
  return formatted.replace(/,/g, "");
}

export function TradeEditPanel({ open, onOpenChange, trade, accounts, onSaved }: TradeEditPanelProps) {
  const router = useRouter();

  const [tradeType] = useState<TradeType>(trade.trade_type);
  const [date, setDate] = useState<Date>(new Date(trade.traded_at));
  const [calOpen, setCalOpen] = useState(false);
  const [accountId, setAccountId] = useState(trade.account_id);

  const [assetName, setAssetName] = useState(trade.asset_name);
  const [tickerSymbol, setTickerSymbol] = useState(trade.ticker_symbol ?? "");
  const [countryCode, setCountryCode] = useState(trade.country_code ?? "KR");

  const initNum = (v: number) => v ? v.toLocaleString("ko-KR") : "";
  const [priceDisplay, setPriceDisplay] = useState(initNum(trade.price));
  const [quantityDisplay, setQuantityDisplay] = useState(initNum(trade.quantity));
  const [commDisplay, setCommDisplay] = useState(initNum(trade.commission));
  const [taxDisplay, setTaxDisplay] = useState(initNum(trade.tax));
  const [profitLossDisplay, setProfitLossDisplay] = useState(
    trade.profit_loss != null ? trade.profit_loss.toLocaleString("ko-KR") : ""
  );

  const [strategy, setStrategy] = useState(trade.strategy_type ?? "");
  const [emotion, setEmotion] = useState(trade.emotion ?? "");
  const [tags, setTags] = useState<ReasoningTag[]>(trade.reasoning_tags ?? []);
  const [result, setResult] = useState<TradeResult | "">(trade.result ?? "");

  const [buyReason, setBuyReason] = useState(trade.buy_reason ?? "");
  const [sellReason, setSellReason] = useState(trade.sell_reason ?? "");
  const [reflectionNote, setReflectionNote] = useState(trade.reflection_note ?? "");
  const [improvementNote, setImprovementNote] = useState(trade.improvement_note ?? "");

  const [error, setError] = useState<string | null>(null);
  const [pending, setPending] = useState(false);

  function toggleTag(tag: ReasoningTag) {
    setTags((prev) =>
      prev.includes(tag) ? prev.filter((t) => t !== tag) : [...prev, tag]
    );
  }

  const handleClose = useCallback(() => onOpenChange(false), [onOpenChange]);

  async function handleSubmit(e: React.FormEvent) {
    e.preventDefault();
    setError(null);
    setPending(true);
    try {
      await tradesApi.update(trade.id, {
        trade_type: tradeType,
        market_type: trade.market_type,
        account_id: accountId,
        asset_name: assetName,
        ticker_symbol: tickerSymbol || null,
        country_code: countryCode,
        traded_at: format(date, "yyyy-MM-dd'T'HH:mm"),
        price: Number(parseRaw(priceDisplay)),
        quantity: Number(parseRaw(quantityDisplay)),
        commission: Number(parseRaw(commDisplay)) || 0,
        tax: Number(parseRaw(taxDisplay)) || 0,
        strategy_type: (strategy || null) as import("@/types/database").StrategyType | null,
        emotion: (emotion || null) as import("@/types/database").EmotionType | null,
        reasoning_tags: tags,
        result: (result || null) as TradeResult | null,
        profit_loss: profitLossDisplay ? Number(parseRaw(profitLossDisplay)) : null,
        buy_reason: buyReason.trim() || null,
        sell_reason: sellReason.trim() || null,
        reflection_note: reflectionNote.trim() || null,
        improvement_note: improvementNote.trim() || null,
      });
      router.refresh();
      handleClose();
      onSaved?.();
    } catch (err) {
      setError(err instanceof Error ? err.message : "저장할 수 없습니다.");
    } finally {
      setPending(false);
    }
  }

  const isSell = tradeType === "SELL";

  return (
    <FullScreenPanel open={open} onOpenChange={handleClose}>
      <FullScreenPanelContent open={open}>
        <FullScreenPanelHeader title="거래 수정" />
        <FullScreenPanelBody>
          <form onSubmit={handleSubmit} className="flex flex-col min-h-full">
            <div className="flex-1 px-5 pt-2 pb-4 space-y-5">
              {/* 거래 유형 표시 (수정 불가) */}
              <div className="space-y-1.5">
                <Label>거래 유형</Label>
                <div className={cn(
                  "flex h-12 items-center rounded-xl px-4 text-[15px] font-bold",
                  tradeType === "BUY"
                    ? "bg-[var(--rise)]/10 text-[var(--rise)]"
                    : "bg-[var(--fall)]/10 text-[var(--fall)]"
                )}>
                  {tradeType === "BUY" ? "매수" : "매도"}
                </div>
              </div>

              {/* 날짜 */}
              <div className="space-y-1.5">
                <Label>날짜 <span className="text-destructive">*</span></Label>
                <Popover open={calOpen} onOpenChange={setCalOpen}>
                  <PopoverTrigger className="flex h-12 w-full items-center justify-between rounded-xl bg-muted px-4 text-[15px] text-foreground">
                    <span>{format(date, "yyyy년 M월 d일 (EEE)", { locale: ko })}</span>
                    <CalendarIcon className="h-4 w-4 text-muted-foreground" />
                  </PopoverTrigger>
                  <PopoverContent side="bottom" align="start" className="w-auto">
                    <Calendar
                      mode="single"
                      selected={date}
                      onSelect={(d) => {
                        if (d) {
                          const updated = new Date(d);
                          updated.setHours(date.getHours(), date.getMinutes());
                          setDate(updated);
                          setCalOpen(false);
                        }
                      }}
                      initialFocus
                    />
                  </PopoverContent>
                </Popover>
              </div>

              {/* 계좌 */}
              <div className="space-y-1.5">
                <Label>계좌 <span className="text-destructive">*</span></Label>
                <Select
                  value={accountId}
                  onValueChange={(v) => setAccountId(v as string)}
                  items={accounts.map((acc) => ({
                    value: acc.id,
                    label: `${acc.name}${acc.broker ? ` · ${acc.broker}` : ""}`,
                  }))}
                >
                  <SelectTrigger>
                    <SelectValue placeholder="계좌를 선택하세요" />
                  </SelectTrigger>
                  <SelectContent>
                    {accounts.map((acc) => (
                      <SelectItem key={acc.id} value={acc.id}>
                        {acc.name}{acc.broker ? ` · ${acc.broker}` : ""}
                      </SelectItem>
                    ))}
                  </SelectContent>
                </Select>
              </div>

              {/* 종목명 */}
              <div className="space-y-1.5">
                <Label>종목명 <span className="text-destructive">*</span></Label>
                <StockSearchInput
                  value={assetName}
                  onChange={(v) => {
                    setAssetName(v);
                    if (!v) { setTickerSymbol(""); setCountryCode("KR"); }
                  }}
                  onSelect={(stock: SelectedStock) => {
                    setAssetName(stock.name);
                    setTickerSymbol(stock.code);
                    setCountryCode(stock.market === "KR" ? "KR" : stock.market === "US" ? "US" : "OTHER");
                  }}
                />
              </div>

              {/* 가격 */}
              <div className="space-y-1.5">
                <Label>가격 (원) <span className="text-destructive">*</span></Label>
                <Input
                  type="text"
                  inputMode="numeric"
                  placeholder="0"
                  value={priceDisplay}
                  onChange={(e) => setPriceDisplay(formatNumber(e.target.value))}
                />
              </div>

              {/* 수량 */}
              <div className="space-y-1.5">
                <Label>수량 <span className="text-destructive">*</span></Label>
                <Input
                  type="text"
                  inputMode="decimal"
                  placeholder="0"
                  value={quantityDisplay}
                  onChange={(e) => setQuantityDisplay(formatNumber(e.target.value))}
                />
              </div>

              {/* 수수료 */}
              <div className="space-y-1.5">
                <Label>수수료 (원)</Label>
                <Input
                  type="text"
                  inputMode="numeric"
                  placeholder="0"
                  value={commDisplay}
                  onChange={(e) => setCommDisplay(formatNumber(e.target.value))}
                />
              </div>

              {/* 제세금 (매도) */}
              {isSell && (
                <div className="space-y-1.5">
                  <Label>제세금 (원)</Label>
                  <Input
                    type="text"
                    inputMode="numeric"
                    placeholder="0"
                    value={taxDisplay}
                    onChange={(e) => setTaxDisplay(formatNumber(e.target.value))}
                  />
                </div>
              )}

              <div className="border-t border-border pt-4 mt-2">
                <p className="text-[13px] font-semibold text-muted-foreground mb-4">
                  {tradeType === "BUY" ? "근거 / 감정" : "회고 / 결과"}
                </p>

                {/* 거래 결과 (매도) */}
                {isSell && (
                  <div className="space-y-2 mb-5">
                    <Label>거래 결과</Label>
                    <div className="grid grid-cols-3 gap-2">
                      {RESULTS.map((r) => (
                        <button
                          key={r.value}
                          type="button"
                          onClick={() => setResult(result === r.value ? "" : r.value)}
                          className={`rounded-xl border py-3 text-[13px] font-bold transition-colors ${
                            result === r.value ? r.color : "border-border bg-muted/50 text-muted-foreground"
                          }`}
                        >
                          {r.label}
                        </button>
                      ))}
                    </div>
                  </div>
                )}

                {/* 손익 금액 (매도) */}
                {isSell && (
                  <div className="space-y-1.5 mb-5">
                    <Label>손익 금액 (원) <span className="text-[12px] font-normal text-muted-foreground">음수=손실</span></Label>
                    <Input
                      type="text"
                      inputMode="numeric"
                      placeholder="예: 150,000 또는 -50,000"
                      value={profitLossDisplay}
                      onChange={(e) => setProfitLossDisplay(formatPnL(e.target.value))}
                    />
                  </div>
                )}

                {/* 전략 */}
                <div className="space-y-2 mb-5">
                  <Label>전략</Label>
                  <div className="grid grid-cols-4 gap-2">
                    {STRATEGIES.map((s) => (
                      <button
                        key={s.value}
                        type="button"
                        onClick={() => setStrategy(strategy === s.value ? "" : s.value)}
                        className={`rounded-xl border py-2.5 text-[13px] font-semibold transition-colors ${
                          strategy === s.value
                            ? "bg-primary text-primary-foreground border-primary"
                            : "border-border bg-muted/50 text-muted-foreground"
                        }`}
                      >
                        {s.label}
                      </button>
                    ))}
                  </div>
                </div>

                {/* 감정 */}
                <div className="space-y-2 mb-5">
                  <Label>감정</Label>
                  <div className="grid grid-cols-3 gap-2">
                    {EMOTIONS.map((e) => (
                      <button
                        key={e.value}
                        type="button"
                        onClick={() => setEmotion(emotion === e.value ? "" : e.value)}
                        className={`rounded-xl border py-2.5 text-[13px] font-semibold transition-colors ${
                          emotion === e.value
                            ? "bg-primary text-primary-foreground border-primary"
                            : "border-border bg-muted/50 text-muted-foreground"
                        }`}
                      >
                        {e.label}
                      </button>
                    ))}
                  </div>
                </div>

                {/* 분석 태그 (매수) */}
                {!isSell && (
                  <div className="space-y-2 mb-5">
                    <Label>분석 태그 <span className="text-[12px] font-normal text-muted-foreground">(복수 선택)</span></Label>
                    <div className="grid grid-cols-2 gap-2">
                      {REASONING_TAGS.map((t) => (
                        <button
                          key={t.value}
                          type="button"
                          onClick={() => toggleTag(t.value)}
                          className={`rounded-xl border py-2.5 text-[13px] font-semibold transition-colors ${
                            tags.includes(t.value)
                              ? "bg-primary text-primary-foreground border-primary"
                              : "border-border bg-muted/50 text-muted-foreground"
                          }`}
                        >
                          {t.label}
                        </button>
                      ))}
                    </div>
                  </div>
                )}

                {/* 매수 근거 */}
                {!isSell && (
                  <div className="space-y-1.5 mb-5">
                    <Label>매수 근거</Label>
                    <Textarea
                      value={buyReason}
                      onChange={(e) => setBuyReason(e.target.value)}
                      placeholder="매수한 근거를 간단히 적어주세요"
                      rows={3}
                    />
                  </div>
                )}

                {/* 매도 이유 */}
                {isSell && (
                  <div className="space-y-1.5 mb-5">
                    <Label>매도 이유</Label>
                    <Textarea
                      value={sellReason}
                      onChange={(e) => setSellReason(e.target.value)}
                      placeholder="왜 매도했나요?"
                      rows={2}
                    />
                  </div>
                )}

                {/* 잘한 점 (매도) */}
                {isSell && (
                  <div className="space-y-1.5 mb-5">
                    <Label>잘한 점 / 배운 점</Label>
                    <Textarea
                      value={reflectionNote}
                      onChange={(e) => setReflectionNote(e.target.value)}
                      placeholder="이번 거래에서 잘한 점이나 배운 것을 기록해보세요"
                      rows={3}
                    />
                  </div>
                )}

                {/* 개선할 점 (매도) */}
                {isSell && (
                  <div className="space-y-1.5 mb-5">
                    <Label>개선할 점 / 다음에는</Label>
                    <Textarea
                      value={improvementNote}
                      onChange={(e) => setImprovementNote(e.target.value)}
                      placeholder="다음 거래에서 개선하고 싶은 점을 적어주세요"
                      rows={3}
                    />
                  </div>
                )}
              </div>

              {error && <p className="text-sm text-destructive">{error}</p>}
            </div>

            <div
              className="sticky bottom-0 bg-background px-5 pt-3 pb-4"
              style={{ paddingBottom: "calc(1rem + env(safe-area-inset-bottom))" }}
            >
              <Button type="submit" size="xl" disabled={pending} className="w-full">
                {pending ? "저장 중..." : "저장"}
              </Button>
            </div>
          </form>
        </FullScreenPanelBody>
      </FullScreenPanelContent>
    </FullScreenPanel>
  );
}
