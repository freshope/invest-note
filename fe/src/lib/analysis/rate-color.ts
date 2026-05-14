import { PNL_COLORS } from "@/lib/constants/colors";
import { WIN_THRESHOLD, LOSS_THRESHOLD } from "@/lib/constants/analysis";

interface RateThresholds {
  win: number;
  loss: number;
}

interface RateColor {
  bg: string;
  text: string;
}

const NEUTRAL_COLOR: RateColor = {
  bg: "bg-amber-400",
  text: "text-amber-500",
};

export function pickRateColor(
  rate: number,
  thresholds: RateThresholds = { win: WIN_THRESHOLD, loss: LOSS_THRESHOLD },
): RateColor {
  if (rate >= thresholds.win) return { bg: PNL_COLORS.rise.bg, text: PNL_COLORS.rise.text };
  if (rate < thresholds.loss) return { bg: PNL_COLORS.fall.bg, text: PNL_COLORS.fall.text };
  return NEUTRAL_COLOR;
}
