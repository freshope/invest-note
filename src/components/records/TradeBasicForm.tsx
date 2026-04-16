"use client";

import { useActionState, useEffect, useState, useCallback } from "react";
import { useFormStatus } from "react-dom";
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
import { createTrade, type TradeActionState } from "@/app/(app)/records/actions";
import { StockSearchInput, type SelectedStock } from "./StockSearchInput";
import { cn } from "@/lib/utils";
import type { Account, TradeType } from "@/types/database";
import { CalendarIcon } from "lucide-react";
import { format } from "date-fns";
import { ko } from "date-fns/locale";

interface TradeBasicFormProps {
  accounts: Account[];
  onTradeCreated: (tradeId: string, tradeType: TradeType) => void;
}

// 가격/수량: 소수점 허용 (crypto, 소수 단위 주식 대응)
function formatNumber(raw: string): string {
  const cleaned = raw.replace(/[^0-9.]/g, "");
  // 소수점 중복 방지
  const parts = cleaned.split(".");
  const integer = parts[0] || "";
  const decimal = parts.length > 1 ? "." + parts[1] : "";
  if (!integer && !decimal) return "";
  const formatted = integer ? Number(integer).toLocaleString("ko-KR") : "";
  return formatted + decimal;
}

function parseRaw(formatted: string): string {
  return formatted.replace(/,/g, "");
}

// 수수료 자동계산: 총액 × 0.015%
function calcCommission(total: number): number {
  return Math.round(total * 0.00015);
}

// 제세금 자동계산 (매도): 총액 × 0.18%
function calcTax(total: number): number {
  return Math.round(total * 0.0018);
}

function SubmitButton() {
  const { pending } = useFormStatus();
  return (
    <Button type="submit" size="xl" disabled={pending} className="w-full">
      {pending ? "저장 중..." : "다음"}
    </Button>
  );
}

export function TradeBasicForm({ accounts, onTradeCreated }: TradeBasicFormProps) {
  const [state, formAction] = useActionState<TradeActionState, FormData>(createTrade, undefined);

  const [tradeType, setTradeType] = useState<TradeType>("BUY");
  const [date, setDate] = useState<Date>(new Date());
  const [calOpen, setCalOpen] = useState(false);

  const [assetName, setAssetName] = useState("");
  const [tickerSymbol, setTickerSymbol] = useState("");
  const [stockMarket, setStockMarket] = useState<"KR" | "US" | "OTHER" | "">("");
  const [stockExchange, setStockExchange] = useState("");

  const [priceDisplay, setPriceDisplay] = useState("");
  const [quantityDisplay, setQuantityDisplay] = useState("");
  const [commDisplay, setCommDisplay] = useState("");
  const [taxDisplay, setTaxDisplay] = useState("");

  // 총액 자동계산
  const price = Number(parseRaw(priceDisplay)) || 0;
  const quantity = Number(parseRaw(quantityDisplay)) || 0;
  const total = price * quantity;
  const totalDisplay = total > 0 ? total.toLocaleString("ko-KR") : "-";

  // 수수료/제세금 재계산
  const recalcFees = useCallback((p: number, q: number, type: TradeType) => {
    const t = p * q;
    if (t > 0) {
      setCommDisplay(calcCommission(t).toLocaleString("ko-KR"));
      if (type === "SELL") {
        setTaxDisplay(calcTax(t).toLocaleString("ko-KR"));
      } else {
        setTaxDisplay("0");
      }
    } else {
      setCommDisplay("");
      setTaxDisplay("");
    }
  }, []);

  useEffect(() => {
    recalcFees(price, quantity, tradeType);
  // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [price, quantity, tradeType]);

  useEffect(() => {
    if (state && "success" in state && state.success) {
      onTradeCreated(state.tradeId, state.tradeType);
    }
  }, [state, onTradeCreated]);

  const tradedAtValue = format(date, "yyyy-MM-dd'T'HH:mm");

  return (
    <form action={formAction} className="flex flex-col min-h-full">
      <div className="flex-1 px-5 pt-2 pb-4 space-y-5">
        {/* 매수/매도 토글 */}
        <div className="space-y-1.5">
          <input type="hidden" name="trade_type" value={tradeType} />
          <ToggleGroup
            spacing={2}
            className="gap-2"
          >
            <ToggleGroupItem
              value="BUY"
              pressed={tradeType === "BUY"}
              onPressedChange={(pressed) => { if (pressed) setTradeType("BUY"); }}
              className={cn(
                "h-12 text-[16px] font-bold",
                tradeType === "BUY"
                  ? "!bg-[var(--rise)] !text-white !border-[var(--rise)]"
                  : "text-[var(--rise)] border-[var(--rise)]/30"
              )}
            >
              매수
            </ToggleGroupItem>
            <ToggleGroupItem
              value="SELL"
              pressed={tradeType === "SELL"}
              onPressedChange={(pressed) => { if (pressed) setTradeType("SELL"); }}
              className={cn(
                "h-12 text-[16px] font-bold",
                tradeType === "SELL"
                  ? "!bg-[var(--fall)] !text-white !border-[var(--fall)]"
                  : "text-[var(--fall)] border-[var(--fall)]/30"
              )}
            >
              매도
            </ToggleGroupItem>
          </ToggleGroup>
        </div>

        {/* 날짜 선택 */}
        <div className="space-y-1.5">
          <Label>날짜 <span className="text-destructive">*</span></Label>
          <input type="hidden" name="traded_at" value={tradedAtValue} />
          <Popover open={calOpen} onOpenChange={setCalOpen}>
            <PopoverTrigger
              className="flex h-12 w-full items-center justify-between rounded-xl bg-muted px-4 text-[15px] text-foreground"
            >
              <span>{format(date, "yyyy년 M월 d일 (EEE)", { locale: ko })}</span>
              <CalendarIcon className="h-4 w-4 text-muted-foreground" />
            </PopoverTrigger>
            <PopoverContent side="bottom" align="start" className="w-auto">
              <Calendar
                mode="single"
                selected={date}
                onSelect={(d) => {
                  if (d) {
                    setDate(d);
                    setCalOpen(false);
                  }
                }}
                initialFocus
              />
            </PopoverContent>
          </Popover>
        </div>

        {/* 계좌 선택 */}
        <div className="space-y-1.5">
          <Label>계좌 <span className="text-destructive">*</span></Label>
          <Select
            name="account_id"
            required
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
          <input type="hidden" name="asset_name" value={assetName} />
          <input type="hidden" name="ticker_symbol" value={tickerSymbol} />
          <StockSearchInput
            value={assetName}
            onChange={(v) => {
              setAssetName(v);
              if (!v) {
                setTickerSymbol("");
                setStockMarket("");
                setStockExchange("");
              }
            }}
            onSelect={(stock: SelectedStock) => {
              setAssetName(stock.name);
              setTickerSymbol(stock.code);
              setStockMarket(stock.market);
              setStockExchange(stock.exchange);
            }}
          />
        </div>

        {/* 종목코드 + 마켓 (자동 입력) */}
        <div className="space-y-1.5">
          <Label>종목코드</Label>
          <div className="flex h-12 items-center gap-2 rounded-xl bg-muted/50 px-4 text-[15px] text-foreground">
            {tickerSymbol ? (
              <>
                <span className="font-mono font-medium">{tickerSymbol}</span>
                {stockMarket === "KR" && (
                  <span className="rounded-md bg-blue-100 px-1.5 py-0.5 text-[11px] font-bold text-blue-700 dark:bg-blue-900/40 dark:text-blue-300">
                    국내 · {stockExchange}
                  </span>
                )}
                {stockMarket === "US" && (
                  <span className="rounded-md bg-orange-100 px-1.5 py-0.5 text-[11px] font-bold text-orange-700 dark:bg-orange-900/40 dark:text-orange-300">
                    해외 · {stockExchange}
                  </span>
                )}
                {stockMarket === "OTHER" && (
                  <span className="rounded-md bg-gray-100 px-1.5 py-0.5 text-[11px] font-bold text-gray-600 dark:bg-gray-800 dark:text-gray-400">
                    {stockExchange}
                  </span>
                )}
              </>
            ) : (
              <span className="text-muted-foreground font-normal">종목 선택 시 자동 입력</span>
            )}
          </div>
        </div>

        {/* 가격 */}
        <div className="space-y-1.5">
          <Label htmlFor="price">가격 (원) <span className="text-destructive">*</span></Label>
          <input type="hidden" name="price" value={parseRaw(priceDisplay)} />
          <Input
            id="price"
            type="text"
            inputMode="numeric"
            placeholder="0"
            value={priceDisplay}
            onChange={(e) => setPriceDisplay(formatNumber(e.target.value))}
          />
        </div>

        {/* 수량 */}
        <div className="space-y-1.5">
          <Label htmlFor="quantity">수량 <span className="text-destructive">*</span></Label>
          <input type="hidden" name="quantity" value={parseRaw(quantityDisplay)} />
          <Input
            id="quantity"
            type="text"
            inputMode="decimal"
            placeholder="0"
            value={quantityDisplay}
            onChange={(e) => setQuantityDisplay(formatNumber(e.target.value))}
          />
        </div>

        {/* 총액 (자동계산) */}
        <div className="space-y-1.5">
          <Label>총액 (자동계산)</Label>
          <div className="flex h-12 items-center rounded-xl bg-muted/50 px-4 text-[15px] font-semibold text-foreground">
            {totalDisplay !== "-" ? `${totalDisplay} 원` : "-"}
          </div>
        </div>

        {/* 수수료 */}
        <div className="space-y-1.5">
          <Label htmlFor="commission">수수료 (원)</Label>
          <input type="hidden" name="commission" value={parseRaw(commDisplay) || "0"} />
          <Input
            id="commission"
            type="text"
            inputMode="numeric"
            placeholder="0"
            value={commDisplay}
            onChange={(e) => setCommDisplay(formatNumber(e.target.value))}
          />
        </div>

        {/* 제세금 (매도시만 표시) */}
        {tradeType === "SELL" && (
          <div className="space-y-1.5">
            <Label htmlFor="tax">제세금 (원)</Label>
            <input type="hidden" name="tax" value={parseRaw(taxDisplay) || "0"} />
            <Input
              id="tax"
              type="text"
              inputMode="numeric"
              placeholder="0"
              value={taxDisplay}
              onChange={(e) => setTaxDisplay(formatNumber(e.target.value))}
            />
          </div>
        )}
        {tradeType === "BUY" && (
          <input type="hidden" name="tax" value="0" />
        )}

        <input type="hidden" name="market_type" value="STOCK" />

        {state && "error" in state && (
          <p className="text-sm text-destructive">{state.error}</p>
        )}
      </div>

      {/* 하단 고정 제출 버튼 */}
      <div
        className="sticky bottom-0 bg-background px-5 pt-3 pb-4"
        style={{ paddingBottom: "calc(1rem + env(safe-area-inset-bottom))" }}
      >
        <SubmitButton />
      </div>
    </form>
  );
}
