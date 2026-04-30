import type { TradeType } from "@/types/database";

/**
 * PnL(상승/하강) 색상 클래스 토큰.
 *
 * Tailwind JIT가 정적 string에서 추출하므로 동적 보간(`text-[var(--${dir})]`)은 금지.
 * 색 자체의 hex 값은 globals.css의 `:root --rise / --fall`에서 정의.
 */
export const PNL_COLORS = {
  rise: {
    text: "text-[var(--rise)]",
    bg: "bg-[var(--rise)]",
    bgSoft: "bg-[var(--rise)]/10",
    border: "border-[var(--rise)]",
    borderSoft: "border-[var(--rise)]/30",
    dataActiveBg: "data-active:bg-[var(--rise)]",
  },
  fall: {
    text: "text-[var(--fall)]",
    bg: "bg-[var(--fall)]",
    bgSoft: "bg-[var(--fall)]/10",
    border: "border-[var(--fall)]",
    borderSoft: "border-[var(--fall)]/30",
    dataActiveBg: "data-active:bg-[var(--fall)]",
  },
} as const;

export type PnlAccent = (typeof PNL_COLORS)[keyof typeof PNL_COLORS];

export function getTradeTypeAccent(tradeType: TradeType): PnlAccent {
  return tradeType === "BUY" ? PNL_COLORS.rise : PNL_COLORS.fall;
}
