"use client";

import { useCallback, useEffect, useMemo, useRef, useState } from "react";
import { useForm, useWatch, Controller } from "react-hook-form";
import { zodResolver } from "@hookform/resolvers/zod";
import { z } from "zod";
import { useQuery, useQueryClient } from "@tanstack/react-query";
import { Button } from "@/components/base/Button";
import { FullScreenPanelFooter } from "@/components/base/FullScreenPanel";
import { AccountChip } from "@/components/shared/AccountChip";
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
import { StockQuickChips } from "./StockQuickChips";
import { AccountFormPanel } from "@/components/settings/AccountFormPanel";
import { PlusIcon } from "lucide-react";
import { NumericInput } from "./NumericInput";
import { CountryBadge } from "./trade-display";
import { currencyForCountry, fmt, formatMoney } from "@/lib/format";
import { impliedExchangeRate, fxHintText } from "./fx-input";
import { useFxRate } from "@/hooks/useFxRate";
import { cn, getFirstFormError } from "@/lib/utils";
import type { Account, TradeType } from "@/types/database";
import { CalendarIcon } from "lucide-react";
import { format } from "date-fns";
import { formatTradedAtLabel } from "@/lib/trade-utils";
import { capture } from "@/lib/analytics";

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
  // 해외 거래의 체결 원화(가격×수량의 원금 KRW). 환율은 제출 시 amount_krw / (price×quantity) 로 역산.
  amount_krw: z.number().min(0),
  traded_at: z.date().refine((date) => date.getTime() <= Date.now(), FUTURE_TRADE_MESSAGE),
  price: z.number().positive("올바른 가격을 입력해주세요."),
  quantity: z.number().positive("올바른 수량을 입력해주세요."),
  commission: z.number().min(0),
  tax: z.number().min(0),
}).superRefine((val, ctx) => {
  const isForeign = currencyForCountry(val.country_code) === "USD";
  if (isForeign && !(val.amount_krw > 0)) {
    ctx.addIssue({ code: z.ZodIssueCode.custom, path: ["amount_krw"], message: "체결 원화를 입력해주세요." });
    return;
  }
  // 체결 원화 = 가격×수량이면 역산 환율이 1.0 → BE 가 해외 거래로 거부(400). 사전 차단.
  if (isForeign && impliedExchangeRate(val.amount_krw, val.price, val.quantity) === 1) {
    ctx.addIssue({ code: z.ZodIssueCode.custom, path: ["amount_krw"], message: "체결 원화가 가격×수량과 같으면 환율이 1이 되어 등록할 수 없어요." });
  }
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

// prefillAccountId 가 현재 계좌 목록에 있으면 우선, 없으면 localStorage 기본값.
function resolveAccountId(accounts: Account[], prefillAccountId?: string | null): string {
  if (prefillAccountId && accounts.some((a) => a.id === prefillAccountId)) return prefillAccountId;
  return getInitialAccountId(accounts);
}

// 계좌 Select 행 — 좌측 AccountChip, 우측 account_number(있을 때만). 공유 AccountChip 은 미변경(blast radius 최소).
function AccountSelectRow({ account, flex }: { account: Account; flex?: boolean }) {
  return (
    <span className={cn("flex items-center justify-between gap-2 overflow-hidden", flex && "flex-1")}>
      <AccountChip account={account} size="md" className="overflow-hidden" />
      {account.account_number && (
        <span className="shrink-0 truncate text-xs tabular-nums text-muted-foreground">
          {account.account_number}
        </span>
      )}
    </span>
  );
}

interface TradeBasicFormProps {
  accounts: Account[];
  onTradeCreated: (tradeId: string, tradeType: TradeType) => void;
  prefillStock?: SelectedStock;
  prefillTradeType?: TradeType;
  prefillAccountId?: string | null;
  source?: string;
}

export function TradeBasicForm({
  accounts,
  onTradeCreated,
  prefillStock,
  prefillTradeType,
  prefillAccountId,
  source = "manual",
}: TradeBasicFormProps) {
  const queryClient = useQueryClient();

  // 인라인 계좌등록: 생성 직후 invalidate→refetch 착지 전까지 accounts prop 에 새 계좌가 없어
  // Select 의 accounts.find 가 undefined 가 되는 ★타이밍 함정 → 로컬 옵티미스틱 병합으로 즉시 노출.
  const [accountPanelOpen, setAccountPanelOpen] = useState(false);
  const [createdAccounts, setCreatedAccounts] = useState<Account[]>([]);
  const mergedAccounts = useMemo(() => {
    if (createdAccounts.length === 0) return accounts;
    const ids = new Set(accounts.map((a) => a.id));
    return [...accounts, ...createdAccounts.filter((a) => !ids.has(a.id))];
  }, [accounts, createdAccounts]);

  const {
    control,
    handleSubmit,
    setValue,
    resetField,
    setError,
    getValues,
    getFieldState,
    formState: { isSubmitting, errors },
  } = useForm<FormValues>({
    resolver: zodResolver(schema),
    defaultValues: {
      trade_type: prefillTradeType ?? TRADE_TYPE.BUY,
      account_id: resolveAccountId(accounts, prefillAccountId),
      asset_name: prefillStock?.name ?? "",
      ticker_symbol: prefillStock?.code ?? "",
      country_code: prefillStock?.market ?? "OTHER",
      exchange: prefillStock?.exchange ?? "",
      amount_krw: 0,
      traded_at: new Date(),
      price: 0,
      quantity: 0,
      commission: 0,
      tax: 0,
    },
  });

  // 폼 상태를 한 번에 일괄 구독해 입력 시 form 전역 리렌더 횟수를 줄인다.
  const [tradeType, price, quantity, accountId, assetName, tickerSymbol, countryCode, amountKrw] = useWatch({
    control,
    name: ["trade_type", "price", "quantity", "account_id", "asset_name", "ticker_symbol", "country_code", "amount_krw"],
  });
  // 해외(USD) 거래 여부 — 체결 원화 입력칸·역산 환율 미리보기·자동 수수료 OFF 분기.
  const isForeign = currencyForCountry(countryCode ?? "KR") === "USD";
  const { usdkrw } = useFxRate(isForeign);
  // 해외 거래는 체결 원화를 현재 시세 환율 기준으로 제안(가격·수량 변경 시 갱신). 사용자가 직접 입력하면(dirty) 갱신 중단.
  useEffect(() => {
    if (isForeign && usdkrw != null && !getFieldState("amount_krw").isDirty) {
      const totalNative = (price || 0) * (quantity || 0);
      setValue("amount_krw", totalNative > 0 ? Math.round(totalNative * usdkrw) : 0);
    }
  }, [isForeign, usdkrw, price, quantity, getFieldState, setValue]);
  const [calOpen, setCalOpen] = useState(false);
  const priceInputRef = useRef<HTMLInputElement>(null);
  // prefill 종목명을 "선택됨"으로 초기화 → 자동완성 드롭다운 억제 + clearStockSelection 오발동 방지.
  const selectedAssetNameRef = useRef(prefillStock?.name ?? "");
  const handleFocusPrice = useCallback(() => priceInputRef.current?.focus(), []);

  const clearStockSelection = useCallback(() => {
    selectedAssetNameRef.current = "";
    setValue("ticker_symbol", "");
    setValue("country_code", "OTHER");
    setValue("exchange", "");
    setValue("amount_krw", 0);
    // 종목이 바뀌면 이전 종목 기준 숫자도 리셋 — 총액은 파생(자동)이라 별도 초기화 불필요.
    setValue("price", 0);
    setValue("quantity", 0);
    // ★commission/tax 는 resetField(dirty clear). 단순 setValue 면 이전에 수동편집한 dirty 가
    // 남아 다음 price/qty 입력 시 recalcFees 가 skip → 0 고정되는 버그. dirty 까지 지워 auto-recalc 복귀.
    resetField("commission", { defaultValue: 0 });
    resetField("tax", { defaultValue: 0 });
  }, [setValue, resetField]);

  // 인라인 생성된 계좌를 옵티미스틱 병합 + 폼에 즉시 주입 → refetch 착지 전에도 Select 에 선택 표시.
  const handleAccountCreated = useCallback((account: Account) => {
    setCreatedAccounts((prev) =>
      prev.some((a) => a.id === account.id) ? prev : [...prev, account],
    );
    setValue("account_id", account.id, { shouldValidate: true });
  }, [setValue]);

  const handleAssetNameChange = useCallback((value: string, onChange: (value: string) => void) => {
    onChange(value);
    if (value !== selectedAssetNameRef.current) {
      clearStockSelection();
    }
  }, [clearStockSelection]);

  // 종목 선택 공통 경로 — 자동완성/보유선택/빠른선택 칩 모두 이 핸들러를 쓴다(칩에서 호출하려 hoist).
  const handleStockSelect = useCallback((stock: SelectedStock) => {
    selectedAssetNameRef.current = stock.name;
    // shouldValidate: 보유선택(SELL)·빠른선택 칩은 onChange 를 안 거쳐(setValue 만) 재검증이
    // 안 돌아 "종목명 입력" 필수 에러가 남는다 → 명시적으로 재검증해 에러를 지운다.
    setValue("asset_name", stock.name, { shouldValidate: true });
    setValue("ticker_symbol", stock.code, { shouldValidate: true });
    setValue("country_code", stock.market);
    setValue("exchange", stock.exchange);
    // 종목이 바뀌면 이전 종목의 금액 입력값을 모두 초기화한다(칩/자동완성/보유선택 공통 경로).
    // 타이핑 경로(clearStockSelection)와 동일하게 맞춘 것 — 칩으로 바꿔도 리셋되도록.
    // commission/tax 는 resetField 로 dirty 도 클리어(안 하면 recalcFees 자동재계산이 스킵됨).
    setValue("price", 0);
    setValue("quantity", 0);
    setValue("amount_krw", 0);
    resetField("commission", { defaultValue: 0 });
    resetField("tax", { defaultValue: 0 });
  }, [setValue, resetField]);

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
    // 해외(US) 거래는 KR 수수료율/거래세 체계가 달라 자동 계산하지 않는다(수동 입력).
    if (isForeign) return;
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
  }, [getFieldState, setValue, isForeign]);

  const total = (price || 0) * (quantity || 0);
  const totalDisplay = total > 0 ? formatMoney(total, isForeign ? "USD" : "KRW") : "-";

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

      // 환율은 체결 원화 / 체결 달러(가격×수량)로 역산. 국내(KRW)는 1.0.
      const implied = impliedExchangeRate(values.amount_krw, values.price, values.quantity);
      const exchangeRate =
        currencyForCountry(values.country_code) === "USD" && implied != null
          ? implied
          : 1;

      const result = await tradesApi.create({
        trade_type: values.trade_type,
        market_type: "STOCK",
        account_id: values.account_id,
        asset_name: values.asset_name,
        ticker_symbol: values.ticker_symbol,
        country_code: values.country_code,
        exchange: values.exchange,
        exchange_rate: exchangeRate,
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
      capture("trade_recorded", {
        trade_type: result.trade_type, // BUY/SELL 만
        source,
        country: values.country_code, // KR/US 등 — 민감값 아님
      });
      onTradeCreated(result.id, result.trade_type);
    } catch (err) {
      setError("root", { message: err instanceof Error ? err.message : "저장에 실패했습니다." });
    }
  }

  return (
    <>
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
          <div className="flex items-center justify-between">
            <Label>계좌 <span className="text-destructive">*</span></Label>
            {mergedAccounts.length > 0 && (
              <button
                type="button"
                onClick={() => setAccountPanelOpen(true)}
                className="inline-flex items-center gap-1 text-[13px] font-medium text-primary"
              >
                <PlusIcon className="h-3.5 w-3.5" />
                새 계좌 추가
              </button>
            )}
          </div>
          {mergedAccounts.length === 0 ? (
            // 0계좌: 빈 Select(막다른 길) 대신 새 계좌 추가 CTA.
            <button
              type="button"
              onClick={() => setAccountPanelOpen(true)}
              className="flex h-12 w-full items-center justify-center gap-2 rounded-xl border border-dashed border-primary/50 bg-primary/5 text-[15px] font-medium text-primary"
            >
              <PlusIcon className="h-4 w-4" />
              새 계좌 추가
            </button>
          ) : (
            <Controller
              control={control}
              name="account_id"
              render={({ field }) => (
                <Select value={field.value} onValueChange={field.onChange}>
                  <SelectTrigger>
                    {(() => {
                      const acc = mergedAccounts.find((a) => a.id === field.value);
                      if (!acc) return <span className="text-muted-foreground">계좌를 선택하세요</span>;
                      return <AccountSelectRow account={acc} flex />;
                    })()}
                  </SelectTrigger>
                  <SelectContent>
                    {mergedAccounts.map((acc) => (
                      <SelectItem key={acc.id} value={acc.id}>
                        <AccountSelectRow account={acc} />
                      </SelectItem>
                    ))}
                  </SelectContent>
                </Select>
              )}
            />
          )}
        </div>

        {/* 종목명 */}
        <div className="space-y-1.5">
          <Label>종목명 <span className="text-destructive">*</span></Label>
          <Controller
            control={control}
            name="asset_name"
            render={({ field }) => {
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
                  initialSelectedName={prefillStock?.name}
                />
              );
            }}
          />
          {/* 최근/보유 종목 빠른선택 — 입력 상자 아래 한 줄 가로 스크롤 */}
          <StockQuickChips
            tradeType={tradeType}
            accountId={accountId}
            onSelect={handleStockSelect}
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
          <Label htmlFor="price">가격 ({isForeign ? "USD" : "원"}) <span className="text-destructive">*</span></Label>
          <Controller
            control={control}
            name="price"
            render={({ field }) => (
              <NumericInput
                inputRef={priceInputRef}
                id="price"
                inputMode={isForeign ? "decimal" : "numeric"}
                value={field.value}
                onValueChange={(next) => {
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
              <NumericInput
                id="quantity"
                inputMode="decimal"
                value={field.value}
                onValueChange={(next) => {
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
                  : `보유 ${fmt(holdingQty)}주${avgBuyPrice ? ` · 평단가 ${isForeign ? formatMoney(avgBuyPrice, "USD") : `${fmt(Math.round(avgBuyPrice))}원`}` : ""}`}
            </p>
          )}
        </div>

        {/* 체결 원화 (해외만) — 가격×수량의 원금 KRW. 환율은 제출 시 역산. 기본값은 현재 시세 환율 기준 제안값, 수정 가능. */}
        {isForeign && (
          <div className="space-y-1.5">
            <Label htmlFor="amount_krw">체결 원화 · 총액 (KRW) <span className="text-destructive">*</span></Label>
            <Controller
              control={control}
              name="amount_krw"
              render={({ field }) => (
                <NumericInput
                  id="amount_krw"
                  inputMode="numeric"
                  value={field.value}
                  onValueChange={field.onChange}
                />
              )}
            />
            <p className="text-[12px] text-muted-foreground">
              {fxHintText(amountKrw, price, quantity, usdkrw)}
            </p>
          </div>
        )}

        {/* 총액 */}
        <div className="space-y-1.5">
          <Label>총액 (자동계산)</Label>
          <div className="flex h-12 items-center rounded-xl bg-muted px-4 text-[15px] font-semibold text-foreground">
            {totalDisplay}
          </div>
        </div>

        {/* 수수료 */}
        <div className="space-y-1.5">
          <Label htmlFor="commission">수수료 ({isForeign ? "USD" : "원"})</Label>
          <Controller
            control={control}
            name="commission"
            render={({ field }) => (
              <NumericInput
                id="commission"
                inputMode={isForeign ? "decimal" : "numeric"}
                value={field.value}
                onValueChange={field.onChange}
              />
            )}
          />
        </div>

        {/* 제세금 (매도) */}
        {tradeType === TRADE_TYPE.SELL && (
          <div className="space-y-1.5">
            <Label htmlFor="tax">제세금 ({isForeign ? "USD" : "원"})</Label>
            <Controller
              control={control}
              name="tax"
              render={({ field }) => (
                <NumericInput
                  id="tax"
                  inputMode={isForeign ? "decimal" : "numeric"}
                  value={field.value}
                  onValueChange={field.onChange}
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

    {/* 인라인 계좌등록 — 생성 시 옵티미스틱 병합 + account_id 주입 (중첩 패널) */}
    <AccountFormPanel
      open={accountPanelOpen}
      onOpenChange={setAccountPanelOpen}
      onCreated={handleAccountCreated}
    />
    </>
  );
}
