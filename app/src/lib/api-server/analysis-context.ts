import type { NextRequest } from "next/server";
import { requireUser } from "@/lib/api-server/auth";
import { HttpError } from "@/lib/api-server/errors";
import { parsePeriod, filterByPeriod, type Period } from "@/lib/analysis/period";
import type { Trade } from "@/types/database";

export interface UserTradesContext {
  allTrades: Trade[];
  trades: Trade[];
  period: Period;
}

export async function fetchUserTradesWithPeriod(req: NextRequest): Promise<UserTradesContext> {
  const { supabase, user } = await requireUser();
  const period = parsePeriod(req.nextUrl.searchParams.get("period"));

  const { data: tradesRaw, error: dbError } = await supabase
    .from("trades")
    .select("*")
    .eq("user_id", user.id)
    .order("traded_at", { ascending: true });

  if (dbError) throw new HttpError("거래 데이터를 불러올 수 없습니다.", 500);

  const allTrades = (tradesRaw ?? []) as Trade[];
  const trades = filterByPeriod(allTrades, period);

  return { allTrades, trades, period };
}
