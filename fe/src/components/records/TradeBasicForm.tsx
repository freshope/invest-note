"use client";

import { useCallback, useRef, useState } from "react";
import { useForm, useWatch, Controller } from "react-hook-form";
import { zodResolver } from "@hookform/resolvers/zod";
import { z } from "zod";
import { useQuery, useQueryClient } from "@tanstack/react-query";
import { Button } from "@/components/base/Button";
import { FullScreenPanelFooter } from "@/components/base/FullScreenPanel";
import { AccountChip } from "@/components/shared/AccountChip";
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
import { QUERY_HOLDING_STALE_TIME_MS } from "@/lib/constants/query";
import { VALIDATION_LIMITS } from "@/lib/constants/validation";
import { COMMISSION_RATE, SELL_TAX_RATE, TRADE_TYPE } from "@/lib/constants/trading";
import { PNL_COLORS } from "@/lib/constants/colors";
import { STORAGE_KEYS } from "@/lib/constants/storage";
import { COUNTRY_CODES, DEFAULT_COUNTRY_CODE } from "@/lib/constants/market";
import { StockSearchInput, type SelectedStock } from "./StockSearchInput";
import { HoldingSelectInput } from "./HoldingSelectInput";
import { CountryBadge } from "./trade-display";
import { fmt, fmtNumberInput, parseNumberInput } from "@/lib/format";
import { cn, getFirstFormError } from "@/lib/utils";
import type { Account, TradeType } from "@/types/database";
import { CalendarIcon } from "lucide-react";
import { format } from "date-fns";
import { formatTradedAtLabel } from "@/lib/trade-utils";

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

// 마운트 직전 동기 초기화 — useEffect 로 setValue 하면 mount → effect → 재렌더 사이클이 발생하므로
// defaultValues 단계에서 미리 결정한다.
function getInitialAccountId(accounts: Account[]): string {
  if (typeof window === "undefined") return "";
  const stored = window.localStorage.getItem(STORAGE_KEYS.LAST_ACCOUNT_ID);
  return stored && accounts.some((a) => a.id === stored) ? stored : "";
}

interface TradeBasicFormProps {
  accounts: Account[];
  onTradeCreated: (tradeId: string, tradeType: TradeType) => void;
}

export function TradeBasicForm({ accounts, onTradeCreated }: TradeBasicFormProps) {
  const queryClient = useQueryClient();

  const {
    control,
    handleSubmit,
    setValue,
    setError,
    getValues,
    getFieldState,
    formState: { isSubmitting, errors },
  } = useForm<FormValues>({
    resolver: zodResolver(schema),
    defaultValues: {
      trade_type: TRADE_TYPE.BUY,
      account_id: getInitialAccountId(accounts),
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

  // 폼 상태를 한 번에 일괄 구독해 입력 시 form 전역 리렌더 횟수를 줄인다.
  const [tradeType, price, quantity, accountId, assetName, tickerSymbol, countryCode] = useWatch({
    control,
    name: ["trade_type", "price", "quantity", "account_id", "asset_name", "ticker_symbol", "country_code"],
  });
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

  // 매도 시 계좌별 보유 수량 조회 (계좌 + flexible ticker 기준)
  const holdingEnabled = tradeType === TRADE_TYPE.SELL && !!accountId && !!assetName;
  const { data: holdingData, isPending: holdingPending } = useQuery({
    queryKey: queryKeys.holding(accountId, tickerSymbol, assetName, countryCode ?? DEFAULT_COUNTRY_CODE),
    queryFn: async () => {
      try {
        return await portfolioApi.holding({
          accountId,
          assetName,
          ticker: tickerSymbol,
          country: countryCode ?? DEFAULT_COUNTRY_CODE,
        });
      } catch {
        return { quantity: 0, avgBuyPrice: null };
      }
    },
    enabled: holdingEnabled,
    staleTime: QUERY_HOLDING_STALE_TIME_MS,
  });

  // holdingPending: 쿼리가 활성화됐으나 아직 데이터를 받지 못한 상태
  const holdingLoading = holdingEnabled && holdingPending;
  const holdingQty = holdingEnabled ? (holdingData?.quantity ?? 0) : 0;
  const avgBuyPrice = holdingData?.avgBuyPrice ?? null;

  // 가격·수량·trade_type 변경 시 수수료/제세금 자동 계산.
  // 사용자가 수수료/제세금을 직접 수정한 경우(getFieldState().isDirty=true) 자동 계산을 건너뛴다.
  const recalcFees = useCallback((nextPrice: number, nextQty: number, nextType: TradeType) => {
    const total = (nextPrice || 0) * (nextQty || 0);
    if (!getFieldState("commission").isDirty) {
      setValue("commission", total > 0 ? calcCommission(total) : 0);
    }
    if (nextType === TRADE_TYPE.SELL) {
      if (!getFieldState("tax").isDirty) {
        setValue("tax", total > 0 ? calcTax(total) : 0);
      }
    } else {
      // BUY 전환 시 SELL에서 수동 입력한 stale 값이 다음 SELL에 노출되지 않도록 dirty 무시.
      setValue("tax", 0);
    }
  }, [getFieldState, setValue]);

  const total = (price || 0) * (quantity || 0);
  const totalDisplay = total > 0 ? fmt(total) : "-";

  const firstError = getFirstFormError(errors);

  async function onSubmit(values: FormValues) {
    try {
      // 클라 사전 검증 — 로딩 중이거나 보유 없으면 차단 (정확한 계좌별 검증은 서버에서 담당)
      if (values.trade_type === TRADE_TYPE.SELL && values.asset_name) {
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
        queryClient.invalidateQueries({ queryKey: queryKeys.assets }),
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
                  const next = v as TradeType;
                  setValue("asset_name", "");
                  clearStockSelection();
                  field.onChange(next);
                  recalcFees(getValues("price"), getValues("quantity"), next);
                }
              }}
            >
              <TabsList className="group-data-[orientation=horizontal]/tabs:h-12 p-1">
                <TabsTrigger
                  value={TRADE_TYPE.BUY}
                  className={cn(
                    "flex-1 text-[16px] font-bold data-[state=active]:text-white",
                    PNL_COLORS.rise.text,
                    PNL_COLORS.rise.dataActiveBg,
                  )}
                >
                  매수
                </TabsTrigger>
                <TabsTrigger
                  value={TRADE_TYPE.SELL}
                  className={cn(
                    "flex-1 text-[16px] font-bold data-[state=active]:text-white",
                    PNL_COLORS.fall.text,
                    PNL_COLORS.fall.dataActiveBg,
                  )}
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
                  <span>{formatTradedAtLabel(field.value)}</span>
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
                    return <AccountChip account={acc} size="md" className="flex-1 overflow-hidden" />;
                  })()}
                </SelectTrigger>
                <SelectContent>
                  {accounts.map((acc) => (
                    <SelectItem key={acc.id} value={acc.id}>
                      <AccountChip account={acc} size="md" className="overflow-hidden" />
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

              if (tradeType === TRADE_TYPE.SELL) {
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
              <Label>종목코드 (자동입력)</Label>
              <div className="flex h-12 items-center gap-2 rounded-xl bg-muted px-4 text-[15px] text-foreground">
                {field.value ? (
                  <>
                    <span className="font-mono font-medium">{field.value}</span>
                    <CountryBadge countryCode={countryCode} />
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
                onChange={(e) => {
                  const next = parseNumberInput(e.target.value);
                  field.onChange(next);
                  recalcFees(next, getValues("quantity"), getValues("trade_type"));
                }}
              />
            )}
          />
        </div>

        {/* 수량 */}
        <div className="space-y-1.5">
          <div className="flex items-center justify-between">
            <Label htmlFor="quantity">수량 <span className="text-destructive">*</span></Label>
            {tradeType === TRADE_TYPE.SELL && holdingQty > 0 && (
              <button
                type="button"
                onClick={() => {
                  setValue("quantity", holdingQty, { shouldValidate: true });
                  recalcFees(getValues("price"), holdingQty, getValues("trade_type"));
                }}
                className="text-[12px] font-medium text-primary underline underline-offset-2"
              >
                전량 ({fmt(holdingQty)}주)
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
                onChange={(e) => {
                  const next = parseNumberInput(e.target.value);
                  field.onChange(next);
                  recalcFees(getValues("price"), next, getValues("trade_type"));
                }}
              />
            )}
          />
          {tradeType === TRADE_TYPE.SELL && assetName && (
            <p className={cn(
              "text-[12px]",
              holdingLoading ? "text-muted-foreground" : holdingQty === 0 ? "text-destructive" : "text-muted-foreground"
            )}>
              {holdingLoading
                ? "보유 수량 조회 중..."
                : holdingQty === 0
                  ? "보유하지 않은 종목입니다"
                  : `보유 ${fmt(holdingQty)}주${avgBuyPrice ? ` · 평단가 ${fmt(Math.round(avgBuyPrice))}원` : ""}`}
            </p>
          )}
        </div>

        {/* 총액 */}
        <div className="space-y-1.5">
          <Label>총액 (자동계산)</Label>
          <div className="flex h-12 items-center rounded-xl bg-muted px-4 text-[15px] font-semibold text-foreground">
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
        {tradeType === TRADE_TYPE.SELL && (
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

      <FullScreenPanelFooter>
        <Button
          type="submit"
          size="xl"
          disabled={isSubmitting || holdingLoading || (tradeType === TRADE_TYPE.SELL && !!assetName && !holdingLoading && holdingQty === 0)}
          className="w-full"
        >
          {isSubmitting ? "저장 중..." : "다음"}
        </Button>
      </FullScreenPanelFooter>
    </form>
  );
}
