import type { Trade } from "@/types/database";
import { computeHoldingDays } from "./holding-period";

export interface BehaviorProfile {
  tempo: number;             // 0(스캘퍼) ~ 100(장기)
  diversification: number;   // 0(집중형) ~ 100(분산형)
  emotionStability: number;  // 0(충동형) ~ 100(차분형)
  reasoningQuality: number;  // 0(감각형) ~ 100(분석형)
  reviewHabit: number;       // 0(무복기) ~ 100(복기형)
}

export interface ProfileInputRates {
  holdingDays: number;   // SELL 중 계산 가능한 비율
  emotion: number;       // 전체 거래 중 emotion 입력 비율
  reasoningTag: number;  // BUY 중 태그 입력 비율
  result: number;        // SELL 중 result 입력 비율
}

function clamp(v: number): number {
  return Math.min(100, Math.max(0, v));
}

export function computeProfile(
  trades: Trade[],
  hhi: number,
): { profile: BehaviorProfile; inputRates: ProfileInputRates } {
  const sells = trades.filter((t) => t.trade_type === "SELL");
  const buys = trades.filter((t) => t.trade_type === "BUY");

  // --- 거래 템포 ---
  const holdingDaysMap = computeHoldingDays(trades);
  const allDays = Array.from(holdingDaysMap.values());
  const avgDays = allDays.length > 0 ? allDays.reduce((a, b) => a + b, 0) / allDays.length : 0;
  // 0일 → 0점, 60일 이상 → 100점. SCALPING 비율로 10점 추가 하향.
  const scalping = sells.filter((t) => t.strategy_type === "SCALPING").length;
  const scalpingRatio = sells.length > 0 ? scalping / sells.length : 0;
  const tempoBase = clamp((avgDays / 60) * 100);
  const tempo = clamp(tempoBase - scalpingRatio * 10);

  // --- 분산도 ---
  const diversification = clamp((1 - hhi) * 100);

  // --- 감정 안정성 ---
  const emotionTagged = trades.filter((t) => t.emotion != null);
  const unstable = emotionTagged.filter(
    (t) => t.emotion === "FOMO" || t.emotion === "IMPULSIVE" || t.emotion === "ANXIOUS",
  ).length;
  const emotionStability =
    emotionTagged.length > 0 ? clamp((1 - unstable / emotionTagged.length) * 100) : 50;

  // --- 근거 품질 ---
  const buysWithFeeling = buys.filter((t) => t.reasoning_tags.includes("FEELING")).length;
  const buysWithNoTag = buys.filter((t) => t.reasoning_tags.length === 0).length;
  const poorRatio = buys.length > 0 ? (buysWithFeeling + buysWithNoTag) / buys.length : 0;
  // 중복 방지: FEELING + 0개가 같은 거래일 수도 있어서 min(1)
  const reasoningQuality = clamp((1 - Math.min(1, poorRatio)) * 100);

  // --- 복기 습관 ---
  const withReflection = sells.filter(
    (t) => t.reflection_note != null && t.reflection_note.trim() !== "",
  ).length;
  const reviewHabit = sells.length > 0 ? clamp((withReflection / sells.length) * 100) : 0;

  // --- 입력률 ---
  const inputRates: ProfileInputRates = {
    holdingDays: sells.length > 0 ? (allDays.length / sells.length) * 100 : 0,
    emotion: trades.length > 0 ? (emotionTagged.length / trades.length) * 100 : 0,
    reasoningTag: buys.length > 0 ? ((buys.length - buysWithNoTag) / buys.length) * 100 : 0,
    result:
      sells.length > 0
        ? (sells.filter((t) => t.result != null).length / sells.length) * 100
        : 0,
  };

  return {
    profile: { tempo, diversification, emotionStability, reasoningQuality, reviewHabit },
    inputRates,
  };
}
