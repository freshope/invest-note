"use client";

import { useEffect } from "react";
import { useForm, Controller } from "react-hook-form";
import { zodResolver } from "@hookform/resolvers/zod";
import { z } from "zod";
import { useQueryClient } from "@tanstack/react-query";
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

const RESULTS: { value: TradeResult; label: string; color: string }[] = [
  { value: "SUCCESS", label: "수익 ✅", color: "bg-[var(--rise)] text-white border-[var(--rise)]" },
  { value: "FAIL", label: "손실 ❌", color: "bg-[var(--fall)] text-white border-[var(--fall)]" },
  { value: "BREAKEVEN", label: "본전 ➖", color: "bg-muted text-foreground border-border" },
];

function fmtNum(n: number | null | undefined): string {
  if (n == null || n === 0) return "";
  return n.toLocaleString("ko-KR");
}

function fmtPnL(n: number | null | undefined): string {
  if (n == null) return "";
  return n.toLocaleString("ko-KR");
}

function parseNum(s: string): number {
  return Number(s.replace(/,/g, "")) || 0;
}

function formatInput(raw: string): string {
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

const schema = z.object({
  account_id: z.string().min(1),
  asset_name: z.string().min(1, "종목명을 입력해주세요.").max(100),
  ticker_symbol: z.string().nullable(),
  country_code: z.enum(["KR", "US", "OTHER"]),
  traded_at: z.date(),
  price_display: z.string(),
  quantity_display: z.string(),
  commission_display: z.string(),
  tax_display: z.string(),
  profit_loss_display: z.string(),
  strategy_type: z.enum(["SCALPING", "SWING", "LONG_TERM", "UNKNOWN"]).nullable(),
  emotion: z.enum(["CONFIDENT", "ANXIOUS", "FOMO", "IMPULSIVE", "CALM"]).nullable(),
  reasoning_tags: z.array(z.enum(["TECHNICAL", "FUNDAMENTAL", "NEWS", "FEELING"])),
  result: z.enum(["SUCCESS", "FAIL", "BREAKEVEN"]).nullable(),
  buy_reason: z.string(),
  sell_reason: z.string(),
  reflection_note: z.string(),
  improvement_note: z.string(),
});

type FormValues = z.infer<typeof schema>;

interface TradeEditPanelProps {
  open: boolean;
  onOpenChange: (open: boolean) => void;
  trade: Trade & { account?: Pick<Account, "name" | "broker"> };
  accounts: Account[];
  onSaved?: () => void;
}

export function TradeEditPanel({ open, onOpenChange, trade, accounts, onSaved }: TradeEditPanelProps) {
  const queryClient = useQueryClient();
  const isSell = trade.trade_type === "SELL";

  const {
    control,
    register,
    handleSubmit,
    watch,
    setValue,
    reset,
    formState: { isSubmitting, errors },
  } = useForm<FormValues>({
    resolver: zodResolver(schema),
    defaultValues: {
      account_id: trade.account_id,
      asset_name: trade.asset_name,
      ticker_symbol: trade.ticker_symbol ?? null,
      country_code: (trade.country_code as "KR" | "US" | "OTHER") ?? "KR",
      traded_at: new Date(trade.traded_at),
      price_display: fmtNum(trade.price),
      quantity_display: fmtNum(trade.quantity),
      commission_display: fmtNum(trade.commission),
      tax_display: fmtNum(trade.tax),
      profit_loss_display: fmtPnL(trade.profit_loss),
      strategy_type: trade.strategy_type ?? null,
      emotion: trade.emotion ?? null,
      reasoning_tags: (trade.reasoning_tags ?? []) as ReasoningTag[],
      result: trade.result ?? null,
      buy_reason: trade.buy_reason ?? "",
      sell_reason: trade.sell_reason ?? "",
      reflection_note: trade.reflection_note ?? "",
      improvement_note: trade.improvement_note ?? "",
    },
  });

  useEffect(() => {
    reset({
      account_id: trade.account_id,
      asset_name: trade.asset_name,
      ticker_symbol: trade.ticker_symbol ?? null,
      country_code: (trade.country_code as "KR" | "US" | "OTHER") ?? "KR",
      traded_at: new Date(trade.traded_at),
      price_display: fmtNum(trade.price),
      quantity_display: fmtNum(trade.quantity),
      commission_display: fmtNum(trade.commission),
      tax_display: fmtNum(trade.tax),
      profit_loss_display: fmtPnL(trade.profit_loss),
      strategy_type: trade.strategy_type ?? null,
      emotion: trade.emotion ?? null,
      reasoning_tags: (trade.reasoning_tags ?? []) as ReasoningTag[],
      result: trade.result ?? null,
      buy_reason: trade.buy_reason ?? "",
      sell_reason: trade.sell_reason ?? "",
      reflection_note: trade.reflection_note ?? "",
      improvement_note: trade.improvement_note ?? "",
    });
  }, [trade, reset]);

  const [tags, result] = [watch("reasoning_tags"), watch("result")];

  function toggleTag(tag: ReasoningTag) {
    const next = tags.includes(tag) ? tags.filter((t) => t !== tag) : [...tags, tag];
    setValue("reasoning_tags", next);
  }

  async function onSubmit(values: FormValues) {
    const parseRaw = (s: string) => Number(s.replace(/,/g, "")) || 0;
    await tradesApi.update(trade.id, {
      trade_type: trade.trade_type,
      market_type: trade.market_type,
      account_id: values.account_id,
      asset_name: values.asset_name,
      ticker_symbol: values.ticker_symbol || null,
      country_code: values.country_code,
      traded_at: format(values.traded_at, "yyyy-MM-dd'T'HH:mm"),
      price: parseRaw(values.price_display),
      quantity: parseRaw(values.quantity_display),
      commission: parseRaw(values.commission_display),
      tax: parseRaw(values.tax_display),
      strategy_type: values.strategy_type,
      emotion: values.emotion,
      reasoning_tags: values.reasoning_tags,
      result: values.result,
      profit_loss: values.profit_loss_display ? Number(values.profit_loss_display.replace(/,/g, "")) : null,
      buy_reason: values.buy_reason.trim() || null,
      sell_reason: values.sell_reason.trim() || null,
      reflection_note: values.reflection_note.trim() || null,
      improvement_note: values.improvement_note.trim() || null,
    });
    await queryClient.invalidateQueries({ queryKey: ["trade", trade.id] });
    await queryClient.invalidateQueries({ queryKey: ["portfolio"] });
    onOpenChange(false);
    onSaved?.();
  }

  const firstError = Object.values(errors)[0]?.message as string | undefined;

  return (
    <FullScreenPanel open={open} onOpenChange={() => onOpenChange(false)}>
      <FullScreenPanelContent open={open}>
        <FullScreenPanelHeader title="거래 수정" />
        <FullScreenPanelBody>
          <form onSubmit={handleSubmit(onSubmit)} className="flex flex-col min-h-full">
            <div className="flex-1 px-5 pt-2 pb-4 space-y-5">
              {/* 거래 유형 (수정 불가) */}
              <div className="space-y-1.5">
                <Label>거래 유형</Label>
                <div className={cn(
                  "flex h-12 items-center rounded-xl px-4 text-[15px] font-bold",
                  isSell ? "bg-[var(--fall)]/10 text-[var(--fall)]" : "bg-[var(--rise)]/10 text-[var(--rise)]"
                )}>
                  {isSell ? "매도" : "매수"}
                </div>
              </div>

              {/* 날짜 */}
              <div className="space-y-1.5">
                <Label>날짜 <span className="text-destructive">*</span></Label>
                <Controller
                  control={control}
                  name="traded_at"
                  render={({ field }) => (
                    <Popover>
                      <PopoverTrigger className="flex h-12 w-full items-center justify-between rounded-xl bg-muted px-4 text-[15px] text-foreground">
                        <span>{format(field.value, "yyyy년 M월 d일 (EEE)", { locale: ko })}</span>
                        <CalendarIcon className="h-4 w-4 text-muted-foreground" />
                      </PopoverTrigger>
                      <PopoverContent side="bottom" align="start" className="w-auto">
                        <Calendar
                          mode="single"
                          selected={field.value}
                          onSelect={(d) => {
                            if (d) {
                              const updated = new Date(d);
                              updated.setHours(field.value.getHours(), field.value.getMinutes());
                              field.onChange(updated);
                            }
                          }}
                          initialFocus
                        />
                      </PopoverContent>
                    </Popover>
                  )}
                />
              </div>

              {/* 계좌 */}
              <div className="space-y-1.5">
                <Label>계좌 <span className="text-destructive">*</span></Label>
                <Controller
                  control={control}
                  name="account_id"
                  render={({ field }) => (
                    <Select
                      value={field.value}
                      onValueChange={field.onChange}
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
                  )}
                />
              </div>

              {/* 종목명 */}
              <div className="space-y-1.5">
                <Label>종목명 <span className="text-destructive">*</span></Label>
                <Controller
                  control={control}
                  name="asset_name"
                  render={({ field }) => (
                    <StockSearchInput
                      value={field.value}
                      onChange={(v) => {
                        field.onChange(v);
                        if (!v) { setValue("ticker_symbol", null); setValue("country_code", "KR"); }
                      }}
                      onSelect={(stock: SelectedStock) => {
                        field.onChange(stock.name);
                        setValue("ticker_symbol", stock.code);
                        setValue("country_code", stock.market === "KR" ? "KR" : stock.market === "US" ? "US" : "OTHER");
                      }}
                    />
                  )}
                />
              </div>

              {/* 가격 */}
              <div className="space-y-1.5">
                <Label>가격 (원) <span className="text-destructive">*</span></Label>
                <Controller
                  control={control}
                  name="price_display"
                  render={({ field }) => (
                    <Input type="text" inputMode="numeric" placeholder="0"
                      value={field.value}
                      onChange={(e) => field.onChange(formatInput(e.target.value))}
                    />
                  )}
                />
              </div>

              {/* 수량 */}
              <div className="space-y-1.5">
                <Label>수량 <span className="text-destructive">*</span></Label>
                <Controller
                  control={control}
                  name="quantity_display"
                  render={({ field }) => (
                    <Input type="text" inputMode="decimal" placeholder="0"
                      value={field.value}
                      onChange={(e) => field.onChange(formatInput(e.target.value))}
                    />
                  )}
                />
              </div>

              {/* 수수료 */}
              <div className="space-y-1.5">
                <Label>수수료 (원)</Label>
                <Controller
                  control={control}
                  name="commission_display"
                  render={({ field }) => (
                    <Input type="text" inputMode="numeric" placeholder="0"
                      value={field.value}
                      onChange={(e) => field.onChange(formatInput(e.target.value))}
                    />
                  )}
                />
              </div>

              {/* 제세금 (매도) */}
              {isSell && (
                <div className="space-y-1.5">
                  <Label>제세금 (원)</Label>
                  <Controller
                    control={control}
                    name="tax_display"
                    render={({ field }) => (
                      <Input type="text" inputMode="numeric" placeholder="0"
                        value={field.value}
                        onChange={(e) => field.onChange(formatInput(e.target.value))}
                      />
                    )}
                  />
                </div>
              )}

              <div className="border-t border-border pt-4 mt-2">
                <p className="text-[13px] font-semibold text-muted-foreground mb-4">
                  {isSell ? "회고 / 결과" : "근거 / 감정"}
                </p>

                {/* 거래 결과 (매도) */}
                {isSell && (
                  <div className="space-y-2 mb-5">
                    <Label>거래 결과</Label>
                    <div className="grid grid-cols-3 gap-2">
                      {RESULTS.map((r) => (
                        <button key={r.value} type="button"
                          onClick={() => setValue("result", result === r.value ? null : r.value)}
                          className={`rounded-xl border py-3 text-[13px] font-bold transition-colors ${
                            result === r.value ? r.color : "border-border bg-muted/50 text-muted-foreground"
                          }`}
                        >{r.label}</button>
                      ))}
                    </div>
                  </div>
                )}

                {/* 손익 (매도) */}
                {isSell && (
                  <div className="space-y-1.5 mb-5">
                    <Label>손익 금액 (원) <span className="text-[12px] font-normal text-muted-foreground">음수=손실</span></Label>
                    <Controller
                      control={control}
                      name="profit_loss_display"
                      render={({ field }) => (
                        <Input type="text" inputMode="numeric"
                          placeholder="예: 150,000 또는 -50,000"
                          value={field.value}
                          onChange={(e) => field.onChange(formatPnL(e.target.value))}
                        />
                      )}
                    />
                  </div>
                )}

                {/* 전략 */}
                <div className="space-y-2 mb-5">
                  <Label>전략</Label>
                  <Controller
                    control={control}
                    name="strategy_type"
                    render={({ field }) => (
                      <div className="grid grid-cols-4 gap-2">
                        {STRATEGIES.map((s) => (
                          <button key={s.value} type="button"
                            onClick={() => field.onChange(field.value === s.value ? null : s.value)}
                            className={`rounded-xl border py-2.5 text-[13px] font-semibold transition-colors ${
                              field.value === s.value
                                ? "bg-primary text-primary-foreground border-primary"
                                : "border-border bg-muted/50 text-muted-foreground"
                            }`}
                          >{s.label}</button>
                        ))}
                      </div>
                    )}
                  />
                </div>

                {/* 감정 */}
                <div className="space-y-2 mb-5">
                  <Label>감정</Label>
                  <Controller
                    control={control}
                    name="emotion"
                    render={({ field }) => (
                      <div className="grid grid-cols-3 gap-2">
                        {EMOTIONS.map((e) => (
                          <button key={e.value} type="button"
                            onClick={() => field.onChange(field.value === e.value ? null : e.value)}
                            className={`rounded-xl border py-2.5 text-[13px] font-semibold transition-colors ${
                              field.value === e.value
                                ? "bg-primary text-primary-foreground border-primary"
                                : "border-border bg-muted/50 text-muted-foreground"
                            }`}
                          >{e.label}</button>
                        ))}
                      </div>
                    )}
                  />
                </div>

                {/* 분석 태그 (매수) */}
                {!isSell && (
                  <div className="space-y-2 mb-5">
                    <Label>분석 태그 <span className="text-[12px] font-normal text-muted-foreground">(복수 선택)</span></Label>
                    <div className="grid grid-cols-2 gap-2">
                      {REASONING_TAGS.map((t) => (
                        <button key={t.value} type="button"
                          onClick={() => toggleTag(t.value)}
                          className={`rounded-xl border py-2.5 text-[13px] font-semibold transition-colors ${
                            tags.includes(t.value)
                              ? "bg-primary text-primary-foreground border-primary"
                              : "border-border bg-muted/50 text-muted-foreground"
                          }`}
                        >{t.label}</button>
                      ))}
                    </div>
                  </div>
                )}

                {/* 매수 근거 */}
                {!isSell && (
                  <div className="space-y-1.5 mb-5">
                    <Label>매수 근거</Label>
                    <Textarea {...register("buy_reason")} placeholder="매수한 근거를 간단히 적어주세요" rows={3} />
                  </div>
                )}

                {/* 매도 이유 */}
                {isSell && (
                  <div className="space-y-1.5 mb-5">
                    <Label>매도 이유</Label>
                    <Textarea {...register("sell_reason")} placeholder="왜 매도했나요?" rows={2} />
                  </div>
                )}

                {/* 잘한 점 (매도) */}
                {isSell && (
                  <div className="space-y-1.5 mb-5">
                    <Label>잘한 점 / 배운 점</Label>
                    <Textarea {...register("reflection_note")} placeholder="이번 거래에서 잘한 점이나 배운 것을 기록해보세요" rows={3} />
                  </div>
                )}

                {/* 개선할 점 (매도) */}
                {isSell && (
                  <div className="space-y-1.5 mb-5">
                    <Label>개선할 점 / 다음에는</Label>
                    <Textarea {...register("improvement_note")} placeholder="다음 거래에서 개선하고 싶은 점을 적어주세요" rows={3} />
                  </div>
                )}
              </div>

              {firstError && <p className="text-sm text-destructive">{firstError}</p>}
            </div>

            <div
              className="sticky bottom-0 bg-background px-5 pt-3 pb-4"
              style={{ paddingBottom: "calc(1rem + env(safe-area-inset-bottom))" }}
            >
              <Button type="submit" size="xl" disabled={isSubmitting} className="w-full">
                {isSubmitting ? "저장 중..." : "저장"}
              </Button>
            </div>
          </form>
        </FullScreenPanelBody>
      </FullScreenPanelContent>
    </FullScreenPanel>
  );
}
