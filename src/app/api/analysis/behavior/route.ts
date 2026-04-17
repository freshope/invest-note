import { NextResponse } from "next/server";
import type { NextRequest } from "next/server";
import { requireUser } from "@/lib/api-server/auth";
import { HttpError } from "@/lib/api-server/errors";
import { parsePeriod, filterByPeriod } from "@/lib/analysis/period";
import { computeConcentration } from "@/lib/analysis/concentration";
import { computeProfile } from "@/lib/analysis/profile";
import { computeHoldingDays } from "@/lib/analysis/holding-period";
import { buildPositions, mergeQuotes } from "@/lib/portfolio";
import { fetchQuotesByKeys } from "@/lib/quotes";
import type { Trade } from "@/types/database";

const HOLDING_BUCKETS: { label: string; maxDays: number }[] = [
  { label: "1일 이내", maxDays: 1 },
  { label: "1주 이내", maxDays: 7 },
  { label: "1개월 이내", maxDays: 30 },
  { label: "3개월 이내", maxDays: 90 },
  { label: "6개월 이내", maxDays: 180 },
  { label: "1년 이내", maxDays: 365 },
  { label: "1년 이상", maxDays: Infinity },
];

function holdingBucket(days: number): string {
  for (const b of HOLDING_BUCKETS) {
    if (days <= b.maxDays) return b.label;
  }
  return "1년 이상";
}

function sizeBucket(amount: number): string {
  if (amount < 500_000) return "50만 미만";
  if (amount < 1_000_000) return "50~100만";
  if (amount < 5_000_000) return "100~500만";
  if (amount < 10_000_000) return "500만~1천만";
  if (amount < 50_000_000) return "1천~5천만";
  return "5천만 이상";
}

const SIZE_ORDER = ["50만 미만", "50~100만", "100~500만", "500만~1천만", "1천~5천만", "5천만 이상"];
const HOLDING_ORDER = HOLDING_BUCKETS.map((b) => b.label);

export async function GET(req: NextRequest) {
  try {
    const { supabase, user } = await requireUser();
    const period = parsePeriod(req.nextUrl.searchParams.get("period"));

    const { data: tradesRaw, error: dbError } = await supabase
      .from("trades")
      .select("*")
      .eq("user_id", user.id)
      .order("traded_at", { ascending: true });

    if (dbError) throw new HttpError(dbError.message, 500);
    const allTrades = (tradesRaw ?? []) as Trade[];
    const trades = filterByPeriod(allTrades, period);

    // 분산 계산: 현재 보유 포지션 기반 (전체 trades 사용 — 기간 필터 전)
    // 시세 취득 실패 시 costBasis로 fallback
    const positions0 = buildPositions(allTrades);
    let positions = positions0;
    try {
      const quotes = await fetchQuotesByKeys(positions0.map((p) => p.key));
      positions = mergeQuotes(positions0, quotes);
    } catch {
      // 시세 API 실패 — costBasis 기준으로 집중도 계산
    }

    const concentration = computeConcentration(positions, allTrades);

    // FIFO 정확도를 위해 allTrades 기준으로 보유일 계산 (기간 이전 매수 포함)
    const allHoldingDaysMap = computeHoldingDays(allTrades);
    const { profile, inputRates } = computeProfile(trades, concentration.hhi, allHoldingDaysMap);

    // 히스토그램은 기간 필터 내 SELL만 카운트
    const periodSellIds = new Set(trades.filter((t) => t.trade_type === "SELL").map((t) => t.id));
    const holdingDist = new Map<string, number>();
    for (const [id, days] of allHoldingDaysMap) {
      if (!periodSellIds.has(id)) continue;
      const b = holdingBucket(days);
      holdingDist.set(b, (holdingDist.get(b) ?? 0) + 1);
    }
    const holdingPeriodDist = HOLDING_ORDER.filter((b) => holdingDist.has(b)).map((b) => ({
      bucket: b,
      count: holdingDist.get(b) ?? 0,
    }));

    // 포지션 사이즈 분포 (기간 필터 내 BUY 기준)
    const sizeDist = new Map<string, number>();
    for (const t of trades.filter((t) => t.trade_type === "BUY")) {
      const b = sizeBucket(t.total_amount);
      sizeDist.set(b, (sizeDist.get(b) ?? 0) + 1);
    }
    const positionSizeDist = SIZE_ORDER.filter((b) => sizeDist.has(b)).map((b) => ({
      bucket: b,
      count: sizeDist.get(b) ?? 0,
    }));

    return NextResponse.json({
      period,
      profile,
      inputRates,
      holdingPeriodDist,
      positionSizeDist,
      concentration,
    });
  } catch (e) {
    if (e instanceof HttpError) return e.toResponse();
    return NextResponse.json({ error: "서버 오류가 발생했습니다." }, { status: 500 });
  }
}
