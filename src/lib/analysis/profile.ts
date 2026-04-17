import type { Trade } from "@/types/database";

export interface BehaviorProfile {
  tempo: number;             // 0(스캘퍼) ~ 100(장기)
  diversification: number;   // 0(집중형) ~ 100(분산형) — 현재 보유 포트폴리오 기준
  emotionStability: number;  // 0(충동형) ~ 100(차분형)
  reasoningQuality: number;  // 0(감각형) ~ 100(분석형)
  reviewHabit: number;       // 0(무복기) ~ 100(복기형)
}

export interface ProfileInputRates {
  holdingDays: number;   // SELL 중 계산 가능한 비율
  emotion: number;       // 전체 거래 중 emotion 입력 비율
  reasoningTag: number;  // BUY 중 태그 입력 비율
  result: number;        // SELL 중 result 입력 비율
  reflection: number;    // SELL 중 reflection_note 작성 비율
}

function clamp(v: number): number {
  return Math.min(100, Math.max(0, v));
}

// holdingDaysMap: computeHoldingDays(trades) 결과 — 호출부에서 주입해 중복 계산 방지
export function computeProfile(
  trades: Trade[],
  hhi: number,
  holdingDaysMap: Map<string, number>,
): { profile: BehaviorProfile; inputRates: ProfileInputRates } {
  const sells = trades.filter((t) => t.trade_type === "SELL");
  const buys = trades.filter((t) => t.trade_type === "BUY");

  // --- 거래 템포 ---
  // holdingDaysMap은 allTrades 기준이므로, 기간 내 SELL만 필터링
  const sellIds = new Set(sells.map((t) => t.id));
  const allDays = Array.from(holdingDaysMap.entries())
    .filter(([id]) => sellIds.has(id))
    .map(([, days]) => days);
  const avgDays = allDays.length > 0 ? allDays.reduce((a, b) => a + b, 0) / allDays.length : 0;
  // 0일 → 0점, 60일 이상 → 100점. SCALPING 비율로 10점 추가 하향.
  const scalping = sells.filter((t) => t.strategy_type === "SCALPING").length;
  const scalpingRatio = sells.length > 0 ? scalping / sells.length : 0;
  const tempoBase = clamp((avgDays / 60) * 100);
  const tempo = clamp(tempoBase - scalpingRatio * 10);

  // --- 분산도 (현재 포트폴리오 기준 HHI 주입) ---
  // 보유 종목 없음(hhi=0)과 완전분산(hhi→0)을 구분 — 거래 이력 없으면 50점(중립)
  const diversification = sells.length === 0 && buys.length === 0 ? 50 : clamp((1 - hhi) * 100);

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
  const reasoningQuality = clamp((1 - Math.min(1, poorRatio)) * 100);

  // --- 복기 습관 ---
  const withReflection = sells.filter(
    (t) => t.reflection_note != null && t.reflection_note.trim() !== "",
  ).length;
  const reviewHabit = sells.length > 0 ? clamp((withReflection / sells.length) * 100) : 0;

  // --- 입력률 ---
  // allDays는 이미 기간 내 SELL로 필터링됐으므로 allDays.length = 보유일 계산 가능한 SELL 수
  const sellsWithHoldingData = allDays.length;
  const inputRates: ProfileInputRates = {
    holdingDays: sells.length > 0 ? (sellsWithHoldingData / sells.length) * 100 : 0,
    emotion: trades.length > 0 ? (emotionTagged.length / trades.length) * 100 : 0,
    reasoningTag:
      buys.length > 0 ? ((buys.length - buysWithNoTag) / buys.length) * 100 : 0,
    result:
      sells.length > 0
        ? (sells.filter((t) => t.result != null).length / sells.length) * 100
        : 0,
    reflection: sells.length > 0 ? (withReflection / sells.length) * 100 : 0,
  };

  return {
    profile: { tempo, diversification, emotionStability, reasoningQuality, reviewHabit },
    inputRates,
  };
}
