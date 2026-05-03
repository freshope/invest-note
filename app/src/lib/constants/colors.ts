import type { TradeType } from "@/types/database";
import { PNL_COLORS, type PnlAccent } from "./pnl-colors";

export { PNL_COLORS, type PnlAccent };

export function getTradeTypeAccent(tradeType: TradeType): PnlAccent {
  return tradeType === "BUY" ? PNL_COLORS.rise : PNL_COLORS.fall;
}
