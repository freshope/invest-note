"use client";

import { useEffect, useState } from "react";
import { useForm, Controller } from "react-hook-form";
import { zodResolver } from "@hookform/resolvers/zod";
import { z } from "zod";
import { useQueryClient } from "@tanstack/react-query";
import { Button } from "@/components/base/Button";
import { Input } from "@/components/base/Input";
import { Label } from "@/components/base/Label";
import { ToggleGroup, ToggleGroupItem } from "@/components/base/ToggleGroup";
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
import { cn } from "@/lib/utils";
import type { Account, TradeType } from "@/types/database";
import { CalendarIcon } from "lucide-react";
import { format } from "date-fns";
import { ko } from "date-fns/locale";

const schema = z.object({
  trade_type: z.enum(["BUY", "SELL"]),
  account_id: z.string().min(1, "계좌를 선택해주세요."),
  asset_name: z.string().min(1, "종목명을 입력해주세요.").max(100),
  ticker_symbol: z.string().nullable(),
  country_code: z.enum(["KR", "US", "OTHER"]),
  traded_at: z.date(),
  price: z.number({ message: "올바른 가격을 입력해주세요." }).positive("올바른 가격을 입력해주세요."),
  quantity: z.number({ message: "올바른 수량을 입력해주세요." }).positive("올바른 수량을 입력해주세요."),
  commission: z.number().min(0),
  tax: z.number().min(0),
});

type FormValues = z.infer<typeof schema>;

function fmtNum(n: number): string {
  return n > 0 ? n.toLocaleString("ko-KR") : "";
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

function calcCommission(total: number) { return Math.round(total * 0.00015); }
function calcTax(total: number) { return Math.round(total * 0.0018); }

interface TradeBasicFormProps {
  accounts: Account[];
  onTradeCreated: (tradeId: string, tradeType: TradeType) => void;
}

export function TradeBasicForm({ accounts, onTradeCreated }: TradeBasicFormProps) {
  const queryClient = useQueryClient();

  const {
    control,
    handleSubmit,
    watch,
    setValue,
    setError,
    formState: { isSubmitting, errors },
  } = useForm<FormValues>({
    resolver: zodResolver(schema),
    defaultValues: {
      trade_type: "BUY",
      account_id: "",
      asset_name: "",
      ticker_symbol: null,
      country_code: "OTHER",
      traded_at: new Date(),
      price: 0,
      quantity: 0,
      commission: 0,
      tax: 0,
    },
  });

  const [tradeType, price, quantity] = [
    watch("trade_type"),
    watch("price"),
    watch("quantity"),
  ];
  const [calOpen, setCalOpen] = useState(false);

  // 가격·수량 변경 시 수수료/제세금 자동 계산
  useEffect(() => {
    const total = (price || 0) * (quantity || 0);
    if (total > 0) {
      setValue("commission", calcCommission(total));
      setValue("tax", tradeType === "SELL" ? calcTax(total) : 0);
    } else {
      setValue("commission", 0);
      setValue("tax", 0);
    }
  }, [price, quantity, tradeType, setValue]);

  const total = (price || 0) * (quantity || 0);
  const totalDisplay = total > 0 ? total.toLocaleString("ko-KR") : "-";

  const firstError = errors.root?.message ?? (Object.values(errors)[0]?.message as string | undefined);

  async function onSubmit(values: FormValues) {
    try {
      const result = await tradesApi.create({
        trade_type: values.trade_type,
        market_type: "STOCK",
        account_id: values.account_id,
        asset_name: values.asset_name,
        ticker_symbol: values.ticker_symbol || null,
        country_code: values.country_code,
        price: values.price,
        quantity: values.quantity,
        commission: values.commission,
        tax: values.tax,
        traded_at: format(values.traded_at, "yyyy-MM-dd'T'HH:mm"),
      });
      await queryClient.invalidateQueries({ queryKey: ["portfolio"] });
      onTradeCreated(result.id, result.trade_type);
    } catch (err) {
      setError("root", { message: err instanceof Error ? err.message : "저장에 실패했습니다." });
    }
  }

  return (
    <form onSubmit={handleSubmit(onSubmit)} className="flex flex-col min-h-full">
      <div className="flex-1 px-5 pt-2 pb-4 space-y-5">
        {firstError && <p className="text-sm text-destructive">{firstError}</p>}

        {/* 매수/매도 토글 */}
        <div className="space-y-1.5">
          <Controller
            control={control}
            name="trade_type"
            render={({ field }) => (
              <ToggleGroup spacing={2} className="gap-2">
                <ToggleGroupItem
                  value="BUY"
                  pressed={field.value === "BUY"}
                  onPressedChange={(pressed) => { if (pressed) field.onChange("BUY"); }}
                  className={cn(
                    "h-12 text-[16px] font-bold",
                    field.value === "BUY"
                      ? "!bg-[var(--rise)] !text-white !border-[var(--rise)]"
                      : "text-[var(--rise)] border-[var(--rise)]/30"
                  )}
                >
                  매수
                </ToggleGroupItem>
                <ToggleGroupItem
                  value="SELL"
                  pressed={field.value === "SELL"}
                  onPressedChange={(pressed) => { if (pressed) field.onChange("SELL"); }}
                  className={cn(
                    "h-12 text-[16px] font-bold",
                    field.value === "SELL"
                      ? "!bg-[var(--fall)] !text-white !border-[var(--fall)]"
                      : "text-[var(--fall)] border-[var(--fall)]/30"
                  )}
                >
                  매도
                </ToggleGroupItem>
              </ToggleGroup>
            )}
          />
        </div>

        {/* 날짜 */}
        <div className="space-y-1.5">
          <Label>날짜 <span className="text-destructive">*</span></Label>
          <Controller
            control={control}
            name="traded_at"
            render={({ field }) => (
              <Popover open={calOpen} onOpenChange={setCalOpen}>
                <PopoverTrigger className="flex h-12 w-full items-center justify-between rounded-xl bg-muted px-4 text-[15px] text-foreground">
                  <span>{format(field.value, "yyyy년 M월 d일 (EEE)", { locale: ko })}</span>
                  <CalendarIcon className="h-4 w-4 text-muted-foreground" />
                </PopoverTrigger>
                <PopoverContent side="bottom" align="start" className="w-auto">
                  <Calendar
                    mode="single"
                    selected={field.value}
                    onSelect={(d) => { if (d) { field.onChange(d); setCalOpen(false); } }}
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
                  if (!v) { setValue("ticker_symbol", null); setValue("country_code", "OTHER"); }
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

        {/* 종목코드 표시 */}
        <Controller
          control={control}
          name="ticker_symbol"
          render={({ field }) => (
            <div className="space-y-1.5">
              <Label>종목코드</Label>
              <div className="flex h-12 items-center gap-2 rounded-xl bg-muted/50 px-4 text-[15px] text-foreground">
                {field.value ? (
                  <>
                    <span className="font-mono font-medium">{field.value}</span>
                    {watch("country_code") === "KR" && (
                      <span className="rounded-md bg-blue-100 px-1.5 py-0.5 text-[11px] font-bold text-blue-700">국내</span>
                    )}
                    {watch("country_code") === "US" && (
                      <span className="rounded-md bg-orange-100 px-1.5 py-0.5 text-[11px] font-bold text-orange-700">해외</span>
                    )}
                  </>
                ) : (
                  <span className="text-muted-foreground font-normal">종목 선택 시 자동 입력</span>
                )}
              </div>
            </div>
          )}
        />

        {/* 가격 */}
        <div className="space-y-1.5">
          <Label htmlFor="price">가격 (원) <span className="text-destructive">*</span></Label>
          <Controller
            control={control}
            name="price"
            render={({ field }) => (
              <Input
                id="price"
                type="text"
                inputMode="numeric"
                placeholder="0"
                value={fmtNum(field.value)}
                onChange={(e) => field.onChange(parseNum(formatInput(e.target.value)))}
              />
            )}
          />
        </div>

        {/* 수량 */}
        <div className="space-y-1.5">
          <Label htmlFor="quantity">수량 <span className="text-destructive">*</span></Label>
          <Controller
            control={control}
            name="quantity"
            render={({ field }) => (
              <Input
                id="quantity"
                type="text"
                inputMode="decimal"
                placeholder="0"
                value={fmtNum(field.value)}
                onChange={(e) => field.onChange(parseNum(formatInput(e.target.value)))}
              />
            )}
          />
        </div>

        {/* 총액 */}
        <div className="space-y-1.5">
          <Label>총액 (자동계산)</Label>
          <div className="flex h-12 items-center rounded-xl bg-muted/50 px-4 text-[15px] font-semibold text-foreground">
            {totalDisplay !== "-" ? `${totalDisplay} 원` : "-"}
          </div>
        </div>

        {/* 수수료 */}
        <div className="space-y-1.5">
          <Label htmlFor="commission">수수료 (원)</Label>
          <Controller
            control={control}
            name="commission"
            render={({ field }) => (
              <Input
                id="commission"
                type="text"
                inputMode="numeric"
                placeholder="0"
                value={fmtNum(field.value)}
                onChange={(e) => field.onChange(parseNum(formatInput(e.target.value)))}
              />
            )}
          />
        </div>

        {/* 제세금 (매도) */}
        {tradeType === "SELL" && (
          <div className="space-y-1.5">
            <Label htmlFor="tax">제세금 (원)</Label>
            <Controller
              control={control}
              name="tax"
              render={({ field }) => (
                <Input
                  id="tax"
                  type="text"
                  inputMode="numeric"
                  placeholder="0"
                  value={fmtNum(field.value)}
                  onChange={(e) => field.onChange(parseNum(formatInput(e.target.value)))}
                />
              )}
            />
          </div>
        )}
      </div>

      <div
        className="sticky bottom-0 bg-background px-5 pt-3 pb-4"
        style={{ paddingBottom: "calc(1rem + env(safe-area-inset-bottom))" }}
      >
        <Button type="submit" size="xl" disabled={isSubmitting} className="w-full">
          {isSubmitting ? "저장 중..." : "다음"}
        </Button>
      </div>
    </form>
  );
}
