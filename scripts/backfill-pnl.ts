/**
 * 기존 SELL 거래 중 profit_loss 또는 avg_buy_price가 null인 항목을 WAC 계산값으로 백필
 * 배포 전 1회 실행: pnpm tsx scripts/backfill-pnl.ts
 */

import { createClient } from "@supabase/supabase-js";
import { computeGroupPnL, groupKey } from "../src/lib/analysis/realized-pnl";
import type { Trade } from "../src/types/database";
import * as dotenv from "dotenv";
import * as path from "path";

dotenv.config({ path: path.join(process.cwd(), ".env.local") });

const supabaseUrl = process.env.NEXT_PUBLIC_SUPABASE_URL;
const supabaseKey = process.env.SUPABASE_SECRET_KEY;

if (!supabaseUrl || !supabaseKey) {
  console.error("❌ NEXT_PUBLIC_SUPABASE_URL 또는 SUPABASE_SECRET_KEY가 없습니다.");
  process.exit(1);
}

const supabase = createClient(supabaseUrl, supabaseKey);

async function main() {
  console.log("🔍 모든 사용자 SELL 거래 조회 중...");

  const { data: allTrades, error } = await supabase
    .from("trades")
    .select("*")
    .order("traded_at", { ascending: true });

  if (error) {
    console.error("❌ 거래 조회 실패:", error.message);
    process.exit(1);
  }

  const trades = (allTrades ?? []) as Trade[];
  const sellsWithNull = trades.filter(
    (t) => t.trade_type === "SELL" && (t.profit_loss == null || t.avg_buy_price == null)
  );
  console.log(`📊 전체 거래: ${trades.length}개, 백필 대상 SELL: ${sellsWithNull.length}개`);

  if (sellsWithNull.length === 0) {
    console.log("✅ 백필할 항목이 없습니다.");
    return;
  }

  // 그룹별로 한 번만 계산
  const groupKeys = [...new Set(sellsWithNull.map((t) => groupKey(t)))];
  const pnlEntryMap = new Map<string, { profit_loss: number; avg_buy_price: number }>();

  for (const key of groupKeys) {
    const [ticker, country, accountId] = key.split(":");
    const groupPnL = computeGroupPnL(trades, {
      ticker: ticker || null,
      assetName: ticker || "",
      country: country || "KR",
      accountId: accountId || "",
    });
    for (const [id, entry] of groupPnL.entries()) {
      pnlEntryMap.set(id, { profit_loss: entry.profit_loss, avg_buy_price: entry.avg_buy_price });
    }
  }

  let updated = 0;
  let skipped = 0;

  for (const sell of sellsWithNull) {
    const entry = pnlEntryMap.get(sell.id);
    if (!entry) {
      console.warn(`⚠️ ${sell.id} (${sell.asset_name}) — P&L 계산 불가, 스킵`);
      skipped++;
      continue;
    }

    const patch: Record<string, number> = {};
    if (sell.profit_loss == null) patch.profit_loss = entry.profit_loss;
    if (sell.avg_buy_price == null) patch.avg_buy_price = entry.avg_buy_price;

    const { error: updateError } = await supabase
      .from("trades")
      .update(patch)
      .eq("id", sell.id);

    if (updateError) {
      console.error(`❌ ${sell.id} 업데이트 실패:`, updateError.message);
      skipped++;
    } else {
      updated++;
    }
  }

  console.log(`\n✅ 완료: 업데이트 ${updated}건, 스킵 ${skipped}건`);
}

main().catch((e) => {
  console.error("❌ 예기치 않은 오류:", e);
  process.exit(1);
});
