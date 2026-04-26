"use client";

import { useCallback, useEffect, useRef, useState } from "react";
import { useForm, Controller } from "react-hook-form";
import { zodResolver } from "@hookform/resolvers/zod";
import { z } from "zod";
import { useQuery, useQueryClient } from "@tanstack/react-query";
import { Button } from "@/components/base/Button";
import { BrokerLogo } from "@/components/base/BrokerLogo";
import { Input } from "@/components/base/Input";
import { Label } from "@/components/base/Label";
import { Tabs, TabsList, TabsTrigger } from "@/components/base/Tabs";
import {
  Select,
  SelectContent,
  SelectItem,
  SelectTrigger,
} from "@/components/base/Select";
import { Popover, PopoverContent, PopoverTrigger } from "@/components/base/Popover";
import { Calendar } from "@/components/base/Calendar";
import { tradesApi, portfolioApi } from "@/lib/api-client";
import { queryKeys } from "@/lib/query-keys";
import { VALIDATION_LIMITS } from "@/lib/constants/validation";
import { COMMISSION_RATE, SELL_TAX_RATE } from "@/lib/constants/trading";
import { STORAGE_KEYS } from "@/lib/constants/storage";
import { COUNTRY_CODES } from "@/lib/constants/market";
import { StockSearchInput, type SelectedStock } from "./StockSearchInput";
import { HoldingSelectInput } from "./HoldingSelectInput";
import { CountryBadge } from "./trade-display";
import { fmtNumberInput, parseNumberInput } from "@/lib/format";
import { cn } from "@/lib/utils";
import type { Account, TradeType } from "@/types/database";
import { CalendarIcon } from "lucide-react";
import { format } from "date-fns";
import { ko } from "date-fns/locale";

const FUTURE_TRADE_MESSAGE = "미래 날짜의 거래는 등록할 수 없습니다.";

const schema = z.object({
  trade_type: z.enum(["BUY", "SELL"]),
  account_id: z.string().min(1, "계좌를 선택해주세요."),
  asset_name: z
    .string()
    .min(1, "종목명을 입력해주세요.")
    .max(VALIDATION_LIMITS.ASSET_NAME_MAX),
  ticker_symbol: z.string().min(1, "자동완성으로 종목을 선택해주세요."),
  country_code: z.enum(COUNTRY_CODES),
  exchange: z.string().trim().max(VALIDATION_LIMITS.EXCHANGE_MAX),
  traded_at: z.date().refine((date) => date.getTime() <= Date.now(), FUTURE_TRADE_MESSAGE),
  price: z.number().positive("올바른 가격을 입력해주세요."),
  quantity: z.number().positive("올바른 수량을 입력해주세요."),
  commission: z.number().min(0),
  tax: z.number().min(0),
});

type FormValues = z.infer<typeof schema>;

function calcCommission(total: number) { return Math.round(total * COMMISSION_RATE); }
function calcTax(total: number) { return Math.round(total * SELL_TAX_RATE); }

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
      ticker_symbol: "",
      country_code: "OTHER",
      exchange: "",
      traded_at: new Date(),
      price: 0,
      quantity: 0,
      commission: 0,
      tax: 0,
    },
  });

  const [tradeType, price, quantity, accountId, assetName, tickerSymbol, countryCode] = [
    watch("trade_type"),
    watch("price"),
    watch("quantity"),
    watch("account_id"),
    watch("asset_name"),
    watch("ticker_symbol"),
    watch("country_code"),
  ];
  const [calOpen, setCalOpen] = useState(false);
  const priceInputRef = useRef<HTMLInputElement>(null);
  const selectedAssetNameRef = useRef("");
  const handleFocusPrice = useCallback(() => priceInputRef.current?.focus(), []);

  const clearStockSelection = useCallback(() => {
    selectedAssetNameRef.current = "";
    setValue("ticker_symbol", "");
    setValue("country_code", "OTHER");
    setValue("exchange", "");
  }, [setValue]);

  const handleAssetNameChange = useCallback((value: string, onChange: (value: string) => void) => {
    onChange(value);
    if (value !== selectedAssetNameRef.current) {
      clearStockSelection();
    }
  }, [clearStockSelection]);

  // 마운트 후 localStorage에서 마지막 사용 계좌 복원
  useEffect(() => {
    const stored = window.localStorage.getItem(STORAGE_KEYS.LAST_ACCOUNT_ID);
    if (stored && accounts.some((a) => a.id === stored)) {
      setValue("account_id", stored);
    }
  // eslint-disable-next-line react-hooks/exhaustive-deps
  }, []);

  // 매도 시 계좌별 보유 수량 조회 (계좌 + flexible ticker 기준)
  const holdingEnabled = tradeType === "SELL" && !!accountId && !!assetName;
  const { data: holdingData, isPending: holdingPending } = useQuery({
    queryKey: queryKeys.holding(accountId, tickerSymbol, assetName, countryCode ?? "KR"),
    queryFn: async () => {
      try {
        return await portfolioApi.holding({
          accountId,
          assetName,
          ticker: tickerSymbol,
          country: countryCode ?? "KR",
        });
      } catch {
        return { quantity: 0, avgBuyPrice: null };
      }
    },
    enabled: holdingEnabled,
    staleTime: 0,
  });

  // holdingPending: 쿼리가 활성화됐으나 아직 데이터를 받지 못한 상태
  const holdingLoading = holdingEnabled && holdingPending;
  const holdingQty = holdingEnabled ? (holdingData?.quantity ?? 0) : 0;
  const avgBuyPrice = holdingData?.avgBuyPrice ?? null;

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
      // 클라 사전 검증 — 로딩 중이거나 보유 없으면 차단 (정확한 계좌별 검증은 서버에서 담당)
      if (values.trade_type === "SELL" && values.asset_name) {
        if (holdingLoading) return; // 아직 데이터 미도착 — 버튼이 disabled이므로 여기 도달하지 않음
        if (holdingQty === 0) {
          setError("root", { message: "보유하지 않은 종목입니다." });
          return;
        }
      }

      const result = await tradesApi.create({
        trade_type: values.trade_type,
        market_type: "STOCK",
        account_id: values.account_id,
        asset_name: values.asset_name,
        ticker_symbol: values.ticker_symbol,
        country_code: values.country_code,
        exchange: values.exchange,
        price: values.price,
        quantity: values.quantity,
        commission: values.commission,
        tax: values.tax,
        traded_at: format(values.traded_at, "yyyy-MM-dd'T'HH:mm"),
      });
      window.localStorage.setItem(STORAGE_KEYS.LAST_ACCOUNT_ID, values.account_id);
      await Promise.all([
        queryClient.invalidateQueries({ queryKey: queryKeys.portfolio }),
        queryClient.invalidateQueries({ queryKey: queryKeys.trades }),
      ]);
      onTradeCreated(result.id, result.trade_type);
    } catch (err) {
      setError("root", { message: err instanceof Error ? err.message : "저장에 실패했습니다." });
    }
  }

  return (
    <form onSubmit={handleSubmit(onSubmit)} className="flex flex-col min-h-full">
      <div className="flex-1 px-5 pt-2 pb-4 space-y-5">
        {firstError && <p className="text-sm text-destructive">{firstError}</p>}

        <Controller
          control={control}
          name="trade_type"
          render={({ field }) => (
            <Tabs
              value={field.value}
              onValueChange={(v) => {
                if (v && v !== field.value) {
                  setValue("asset_name", "");
                  clearStockSelection();
                  field.onChange(v);
                }
              }}
            >
              <TabsList className="group-data-horizontal/tabs:h-12 p-1">
                <TabsTrigger
                  value="BUY"
                  className="flex-1 text-[16px] font-bold text-[var(--rise)] data-active:bg-[var(--rise)] data-active:text-white"
                >
                  매수
                </TabsTrigger>
                <TabsTrigger
                  value="SELL"
                  className="flex-1 text-[16px] font-bold text-[var(--fall)] data-active:bg-[var(--fall)] data-active:text-white"
                >
                  매도
                </TabsTrigger>
              </TabsList>
            </Tabs>
          )}
        />

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
                    defaultMonth={field.value}
                    disabled={{ after: new Date() }}
                    onSelect={(d) => { if (d) { field.onChange(d); setCalOpen(false); } }}
                    initialFocus
                    className="[--cell-size:--spacing(10)]"
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
              <Select value={field.value} onValueChange={field.onChange}>
                <SelectTrigger>
                  {(() => {
                    const acc = accounts.find((a) => a.id === field.value);
                    if (!acc) return <span className="text-muted-foreground">계좌를 선택하세요</span>;
                    return (
                      <span className="flex min-w-0 flex-1 items-center gap-1.5 overflow-hidden">
                        {acc.broker && (
                          <span className="shrink-0">
                            <BrokerLogo broker={acc.broker} size={16} />
                          </span>
                        )}
                        <span className="min-w-0 truncate">{acc.name}</span>
                      </span>
                    );
                  })()}
                </SelectTrigger>
                <SelectContent>
                  {accounts.map((acc) => (
                    <SelectItem key={acc.id} value={acc.id}>
                      <span className="flex min-w-0 items-center gap-1.5 overflow-hidden">
                        {acc.broker && (
                          <span className="shrink-0">
                            <BrokerLogo broker={acc.broker} size={16} />
                          </span>
                        )}
                        <span className="min-w-0 truncate">{acc.name}</span>
                      </span>
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
            render={({ field }) => {
              const handleStockSelect = (stock: SelectedStock) => {
                selectedAssetNameRef.current = stock.name;
                field.onChange(stock.name);
                setValue("ticker_symbol", stock.code);
                setValue("country_code", stock.market);
                setValue("exchange", stock.exchange);
              };

              if (tradeType === "SELL") {
                return (
                  <HoldingSelectInput
                    accountId={accountId}
                    value={field.value}
                    onChange={(v) => handleAssetNameChange(v, field.onChange)}
                    onSelect={handleStockSelect}
                    onSelectComplete={handleFocusPrice}
                  />
                );
              }

              return (
                <StockSearchInput
                  value={field.value}
                  onChange={(v) => handleAssetNameChange(v, field.onChange)}
                  onSelect={handleStockSelect}
                  onSelectComplete={handleFocusPrice}
                />
              );
            }}
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
                    <CountryBadge countryCode={watch("country_code")} />
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
                ref={priceInputRef}
                id="price"
                type="text"
                inputMode="numeric"
                placeholder="0"
                value={fmtNumberInput(field.value)}
                onChange={(e) => field.onChange(parseNumberInput(e.target.value))}
              />
            )}
          />
        </div>

        {/* 수량 */}
        <div className="space-y-1.5">
          <div className="flex items-center justify-between">
            <Label htmlFor="quantity">수량 <span className="text-destructive">*</span></Label>
            {tradeType === "SELL" && holdingQty > 0 && (
              <button
                type="button"
                onClick={() => setValue("quantity", holdingQty, { shouldValidate: true })}
                className="text-[12px] font-medium text-primary underline underline-offset-2"
              >
                전량 ({holdingQty.toLocaleString("ko-KR")}주)
              </button>
            )}
          </div>
          <Controller
            control={control}
            name="quantity"
            render={({ field }) => (
              <Input
                id="quantity"
                type="text"
                inputMode="decimal"
                placeholder="0"
                value={fmtNumberInput(field.value)}
                onChange={(e) => field.onChange(parseNumberInput(e.target.value))}
              />
            )}
          />
          {tradeType === "SELL" && assetName && (
            <p className={cn(
              "text-[12px]",
              holdingLoading ? "text-muted-foreground" : holdingQty === 0 ? "text-destructive" : "text-muted-foreground"
            )}>
              {holdingLoading
                ? "보유 수량 조회 중..."
                : holdingQty === 0
                  ? "보유하지 않은 종목입니다"
                  : `보유 ${holdingQty.toLocaleString("ko-KR")}주${avgBuyPrice ? ` · 평단가 ${Math.round(avgBuyPrice).toLocaleString("ko-KR")}원` : ""}`}
            </p>
          )}
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
                value={fmtNumberInput(field.value)}
                onChange={(e) => field.onChange(parseNumberInput(e.target.value))}
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
                  value={fmtNumberInput(field.value)}
                  onChange={(e) => field.onChange(parseNumberInput(e.target.value))}
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
        <Button
          type="submit"
          size="xl"
          disabled={isSubmitting || holdingLoading || (tradeType === "SELL" && !!assetName && !holdingLoading && holdingQty === 0)}
          className="w-full"
        >
          {isSubmitting ? "저장 중..." : "다음"}
        </Button>
      </div>
    </form>
  );
}
