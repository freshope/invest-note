"use client";

import { useState, useCallback } from "react";
import { useRouter } from "next/navigation";
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

interface TradeBasicFormProps {
  accounts: Account[];
  onTradeCreated: (tradeId: string, tradeType: TradeType) => void;
}

function formatNumber(raw: string): string {
  const cleaned = raw.replace(/[^0-9.]/g, "");
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

function calcCommission(total: number): number {
  return Math.round(total * 0.00015);
}

function calcTax(total: number): number {
  return Math.round(total * 0.0018);
}

export function TradeBasicForm({ accounts, onTradeCreated }: TradeBasicFormProps) {
  const router = useRouter();

  const [tradeType, setTradeType] = useState<TradeType>("BUY");
  const [date, setDate] = useState<Date>(new Date());
  const [calOpen, setCalOpen] = useState(false);
  const [accountId, setAccountId] = useState<string>("");

  const [assetName, setAssetName] = useState("");
  const [tickerSymbol, setTickerSymbol] = useState("");
  const [stockMarket, setStockMarket] = useState<"KR" | "US" | "OTHER" | "">("");

  const [priceDisplay, setPriceDisplay] = useState("");
  const [quantityDisplay, setQuantityDisplay] = useState("");
  const [commDisplay, setCommDisplay] = useState("");
  const [taxDisplay, setTaxDisplay] = useState("");

  const [error, setError] = useState<string | null>(null);
  const [pending, setPending] = useState(false);

  const price = Number(parseRaw(priceDisplay)) || 0;
  const quantity = Number(parseRaw(quantityDisplay)) || 0;
  const total = price * quantity;
  const totalDisplay = total > 0 ? total.toLocaleString("ko-KR") : "-";

  const recalcFees = useCallback((p: number, q: number, type: TradeType) => {
    const t = p * q;
    if (t > 0) {
      setCommDisplay(calcCommission(t).toLocaleString("ko-KR"));
      setTaxDisplay(type === "SELL" ? calcTax(t).toLocaleString("ko-KR") : "0");
    } else {
      setCommDisplay("");
      setTaxDisplay("");
    }
  }, []);

  function handlePriceChange(v: string) {
    const formatted = formatNumber(v);
    setPriceDisplay(formatted);
    recalcFees(Number(parseRaw(formatted)) || 0, quantity, tradeType);
  }

  function handleQuantityChange(v: string) {
    const formatted = formatNumber(v);
    setQuantityDisplay(formatted);
    recalcFees(price, Number(parseRaw(formatted)) || 0, tradeType);
  }

  function handleTradeTypeChange(type: TradeType) {
    setTradeType(type);
    recalcFees(price, quantity, type);
  }

  async function handleSubmit(e: React.FormEvent) {
    e.preventDefault();
    setError(null);

    if (!accountId) { setError("계좌를 선택해주세요."); return; }
    if (!assetName) { setError("종목명을 입력해주세요."); return; }

    const priceVal = Number(parseRaw(priceDisplay));
    const quantityVal = Number(parseRaw(quantityDisplay));
    if (!priceVal || priceVal <= 0) { setError("올바른 가격을 입력해주세요."); return; }
    if (!quantityVal || quantityVal <= 0) { setError("올바른 수량을 입력해주세요."); return; }

    setPending(true);
    try {
      const result = await tradesApi.create({
        trade_type: tradeType,
        market_type: "STOCK",
        account_id: accountId,
        asset_name: assetName,
        ticker_symbol: tickerSymbol || null,
        country_code: stockMarket === "KR" ? "KR" : stockMarket === "US" ? "US" : "OTHER",
        price: priceVal,
        quantity: quantityVal,
        commission: Number(parseRaw(commDisplay)) || 0,
        tax: Number(parseRaw(taxDisplay)) || 0,
        traded_at: format(date, "yyyy-MM-dd'T'HH:mm"),
      });
      router.refresh();
      onTradeCreated(result.id, result.trade_type);
    } catch (err) {
      setError(err instanceof Error ? err.message : "오류가 발생했습니다.");
    } finally {
      setPending(false);
    }
  }

  return (
    <form onSubmit={handleSubmit} className="flex flex-col min-h-full">
      <div className="flex-1 px-5 pt-2 pb-4 space-y-5">
        {/* 매수/매도 토글 */}
        <div className="space-y-1.5">
          <ToggleGroup spacing={2} className="gap-2">
            <ToggleGroupItem
              value="BUY"
              pressed={tradeType === "BUY"}
              onPressedChange={(pressed) => { if (pressed) handleTradeTypeChange("BUY"); }}
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
              onPressedChange={(pressed) => { if (pressed) handleTradeTypeChange("SELL"); }}
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
          <Popover open={calOpen} onOpenChange={setCalOpen}>
            <PopoverTrigger className="flex h-12 w-full items-center justify-between rounded-xl bg-muted px-4 text-[15px] text-foreground">
              <span>{format(date, "yyyy년 M월 d일 (EEE)", { locale: ko })}</span>
              <CalendarIcon className="h-4 w-4 text-muted-foreground" />
            </PopoverTrigger>
            <PopoverContent side="bottom" align="start" className="w-auto">
              <Calendar
                mode="single"
                selected={date}
                onSelect={(d) => { if (d) { setDate(d); setCalOpen(false); } }}
                initialFocus
              />
            </PopoverContent>
          </Popover>
        </div>

        {/* 계좌 선택 */}
        <div className="space-y-1.5">
          <Label>계좌 <span className="text-destructive">*</span></Label>
          <Select
            value={accountId}
            onValueChange={(v) => setAccountId(v as string)}
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
              if (!v) { setTickerSymbol(""); setStockMarket(""); }
            }}
            onSelect={(stock: SelectedStock) => {
              setAssetName(stock.name);
              setTickerSymbol(stock.code);
              setStockMarket(stock.market);
            }}
          />
        </div>

        {/* 종목코드 */}
        <div className="space-y-1.5">
          <Label>종목코드</Label>
          <div className="flex h-12 items-center gap-2 rounded-xl bg-muted/50 px-4 text-[15px] text-foreground">
            {tickerSymbol ? (
              <>
                <span className="font-mono font-medium">{tickerSymbol}</span>
                {stockMarket === "KR" && (
                  <span className="rounded-md bg-blue-100 px-1.5 py-0.5 text-[11px] font-bold text-blue-700">국내</span>
                )}
                {stockMarket === "US" && (
                  <span className="rounded-md bg-orange-100 px-1.5 py-0.5 text-[11px] font-bold text-orange-700">해외</span>
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
          <Input
            id="price"
            type="text"
            inputMode="numeric"
            placeholder="0"
            value={priceDisplay}
            onChange={(e) => handlePriceChange(e.target.value)}
          />
        </div>

        {/* 수량 */}
        <div className="space-y-1.5">
          <Label htmlFor="quantity">수량 <span className="text-destructive">*</span></Label>
          <Input
            id="quantity"
            type="text"
            inputMode="decimal"
            placeholder="0"
            value={quantityDisplay}
            onChange={(e) => handleQuantityChange(e.target.value)}
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
          <Input
            id="commission"
            type="text"
            inputMode="numeric"
            placeholder="0"
            value={commDisplay}
            onChange={(e) => setCommDisplay(formatNumber(e.target.value))}
          />
        </div>

        {/* 제세금 (매도시만) */}
        {tradeType === "SELL" && (
          <div className="space-y-1.5">
            <Label htmlFor="tax">제세금 (원)</Label>
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

        {error && <p className="text-sm text-destructive">{error}</p>}
      </div>

      <div
        className="sticky bottom-0 bg-background px-5 pt-3 pb-4"
        style={{ paddingBottom: "calc(1rem + env(safe-area-inset-bottom))" }}
      >
        <Button type="submit" size="xl" disabled={pending} className="w-full">
          {pending ? "저장 중..." : "다음"}
        </Button>
      </div>
    </form>
  );
}
