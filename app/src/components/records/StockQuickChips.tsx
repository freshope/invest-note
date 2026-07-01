"use client";

import { useMemo } from "react";
import { useQuery } from "@tanstack/react-query";
import { tradesApi, type TradesListResponse } from "@/lib/api-client";
import { queryKeys } from "@/lib/query-keys";
import { usePortfolioSummary } from "@/hooks/usePortfolioSummary";
import { TRADE_TYPE } from "@/lib/constants/trading";
import { COUNTRY_CODES, type CountryCode } from "@/lib/constants/market";
import type { SelectedStock } from "./StockSearchInput";
import type { TradeType } from "@/types/database";

const MAX_CHIPS = 8;

// Position.country / Trade.country_code(string) → SelectedStock.market 로 좁힘.
function toMarket(country: string): SelectedStock["market"] {
  return (COUNTRY_CODES as readonly string[]).includes(country)
    ? (country as CountryCode)
    : "OTHER";
}

interface Chip {
  key: string; // `${ticker}:${country}` 중복 제거용
  stock: SelectedStock; // 선택 시 폼에 주입 (name=asset_name 계산키)
  label: string; // 표시명 (nameKo ?? asset_name)
}

interface Props {
  tradeType: TradeType;
  accountId: string;
  onSelect: (stock: SelectedStock) => void;
}

/**
 * 최근/보유 종목 빠른선택 칩. 반복 기록 가속용 — 첫 거래(0거래·0보유) 사용자에겐 소스가
 * 비어 렌더하지 않는다.
 * - BUY: 최근 거래 종목 + 보유 종목
 * - SELL: 보유 종목만 (매도는 보유해야 함 — HoldingSelectInput 정합)
 */
export function StockQuickChips({ tradeType, accountId, onSelect }: Props) {
  const isSell = tradeType === TRADE_TYPE.SELL;

  // 보유 종목 — SELL 은 계좌 스코프(HoldingSelectInput 과 일치), BUY 는 전체(null).
  const { data: summary } = usePortfolioSummary(isSell ? accountId || null : null);

  // 최근 거래 종목 — BUY 에서만 사용. 기록 화면과 같은 캐시 키라 중복 요청 없음.
  const { data: tradesData } = useQuery<TradesListResponse>({
    queryKey: queryKeys.trades,
    queryFn: () => tradesApi.list(),
    enabled: !isSell && !!accountId,
  });

  const chips = useMemo<Chip[]>(() => {
    const out: Chip[] = [];
    const seen = new Set<string>();

    const push = (chip: Chip) => {
      if (seen.has(chip.key)) return;
      seen.add(chip.key);
      out.push(chip);
    };

    // 보유 종목 (holdingQuantity > 0)
    for (const p of summary?.positions ?? []) {
      if (p.holdingQuantity <= 0) continue;
      push({
        key: `${p.ticker}:${p.country}`,
        stock: { name: p.assetName, code: p.ticker, market: toMarket(p.country), exchange: p.exchange },
        label: p.nameKo || p.assetName,
      });
    }

    // 최근 거래 종목 (BUY 만) — 최신순.
    if (!isSell) {
      const recent = [...(tradesData?.trades ?? [])].sort(
        (a, b) => new Date(b.traded_at).getTime() - new Date(a.traded_at).getTime(),
      );
      for (const t of recent) {
        if (!t.ticker_symbol) continue;
        push({
          key: `${t.ticker_symbol}:${t.country_code}`,
          stock: {
            name: t.asset_name,
            code: t.ticker_symbol,
            market: toMarket(t.country_code),
            exchange: t.exchange,
          },
          label: t.name_ko || t.asset_name,
        });
      }
    }

    return out.slice(0, MAX_CHIPS);
  }, [summary, tradesData, isSell]);

  // 계좌 미선택이면 칩을 숨긴다(계좌 선택 전에는 표시하지 않음). 0건도 렌더하지 않음(빈 자리·혼란 방지).
  if (!accountId || chips.length === 0) return null;

  return (
    // 입력 상자 아래 한 줄 가로 스크롤 — 줄바꿈 없이 넘치면 스크롤(모바일 터치). 스크롤바는 숨김.
    <div className="flex gap-2 overflow-x-auto pb-0.5 [scrollbar-width:none] [&::-webkit-scrollbar]:hidden">
      {chips.map((chip) => (
        <button
          key={chip.key}
          type="button"
          onClick={() => onSelect(chip.stock)}
          className="shrink-0 whitespace-nowrap rounded-full border bg-card px-3 py-1.5 text-[13px] font-medium text-foreground transition-colors hover:bg-accent active:scale-95"
        >
          {chip.label}
        </button>
      ))}
    </div>
  );
}
