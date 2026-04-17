import type { AnalysisSummary } from "./aggregate";
import type { BehaviorProfile } from "./profile";
import type { ConcentrationData } from "./concentration";
import { HHI_HIGH, TOP1_WEIGHT_HIGH } from "./concentration";

export interface Suggestion {
  id: string;
  severity: "info" | "warn" | "critical";
  title: string;
  body: string;
  metric?: { label: string; value: string };
  linkSection?: "strategy" | "emotion" | "tag" | "concentration" | "review";
}

export interface RuleInput {
  summary: AnalysisSummary;
  profile?: BehaviorProfile;
  concentration?: ConcentrationData;
}

type RuleFn = (input: RuleInput) => Suggestion | null;

const rules: RuleFn[] = [
  // FOMO 승률 낮음 — sellCount 기준으로 판단 (실제 매도 결과가 있는 건수)
  ({ summary }) => {
    const fomo = summary.byEmotion.find((e) => e.type === "FOMO");
    if (!fomo || fomo.sellCount < 5 || fomo.resultCount < 3 || fomo.winRate >= 40) return null;
    return {
      id: "emotion_fomo_low_winrate",
      severity: "warn",
      title: "FOMO 상태에서의 매매 승률이 낮아요",
      body: `FOMO 상태로 진입한 거래의 승률이 ${Math.round(fomo.winRate)}%입니다. 해당 감정에서는 관망을 권장합니다.`,
      metric: { label: "FOMO 승률", value: `${Math.round(fomo.winRate)}%` },
      linkSection: "emotion",
    };
  },

  // 평온할 때 성과 우수 — sellCount 기준
  ({ summary }) => {
    const calm = summary.byEmotion.find((e) => e.type === "CALM");
    if (!calm || calm.sellCount < 5 || calm.winRate < 60) return null;
    return {
      id: "emotion_calm_high_winrate",
      severity: "info",
      title: "평온할 때 성과가 가장 좋아요",
      body: `CALM 상태 거래 승률 ${Math.round(calm.winRate)}% — 현재 매매 패턴을 유지하세요.`,
      metric: { label: "평온 승률", value: `${Math.round(calm.winRate)}%` },
      linkSection: "emotion",
    };
  },

  // 집중도 과다 — concentration 없으면 건너뜀
  ({ concentration }) => {
    if (!concentration) return null;
    const top1Weight = concentration.top3[0]?.weight ?? 0;
    if (concentration.hhi <= HHI_HIGH && top1Weight <= TOP1_WEIGHT_HIGH) return null;
    return {
      id: "concentration_high",
      severity: "warn",
      title: "한 종목 비중이 높습니다",
      body: `상위 종목 비중 ${Math.round(top1Weight * 100)}%, 집중도(HHI) ${concentration.hhi.toFixed(2)} — 분산 투자를 고려해보세요.`,
      metric: { label: "HHI", value: concentration.hhi.toFixed(2) },
      linkSection: "concentration",
    };
  },

  // 감/직감 진입 비율 높음
  ({ summary }) => {
    if (summary.feelingRate < 40 || summary.totalTrades < 5) return null;
    return {
      id: "feeling_heavy",
      severity: "warn",
      title: "'감'으로 진입하는 비율이 높아요",
      body: `전체 매수 중 ${Math.round(summary.feelingRate)}%가 감/직감 태그. 기술적 또는 펀더멘털 근거 1개 추가를 권장합니다.`,
      metric: { label: "감/직감 비율", value: `${Math.round(summary.feelingRate)}%` },
      linkSection: "tag",
    };
  },

  // 회고 부족
  ({ summary }) => {
    if (summary.reflectionRate >= 30 || summary.sellTrades < 3) return null;
    return {
      id: "no_reflection",
      severity: "info",
      title: "매도 후 회고가 드물어요",
      body: `매도 ${summary.sellTrades}건 중 회고 작성률 ${Math.round(summary.reflectionRate)}%. 최근 매도 거래에 회고를 남겨보세요.`,
      metric: { label: "회고 작성률", value: `${Math.round(summary.reflectionRate)}%` },
      linkSection: "review",
    };
  },

  // 전략-보유기간 불일치 (SCALPING인데 실제 보유기간 길수도 있는 경우)
  ({ summary }) => {
    const scalping = summary.byStrategy.find((s) => s.type === "SCALPING");
    if (!scalping || scalping.count < 3 || scalping.avgHoldingDays <= 7) return null;
    return {
      id: "holding_mismatch",
      severity: "info",
      title: "스캘핑 전략인데 보유 기간이 깁니다",
      body: `스캘핑으로 분류된 거래의 평균 보유일이 ${Math.round(scalping.avgHoldingDays)}일입니다. 전략 태그를 재검토해보세요.`,
      metric: { label: "평균 보유일", value: `${Math.round(scalping.avgHoldingDays)}일` },
      linkSection: "strategy",
    };
  },

  // 특정 전략 승률 낮음 — resultCount 부족 시 오발동 방지
  ({ summary }) => {
    const worst = summary.byStrategy.find((s) => s.count >= 5 && s.resultCount >= 3 && s.winRate < 30);
    if (!worst) return null;
    const labels: Record<string, string> = {
      SCALPING: "스캘핑",
      SWING: "스윙",
      LONG_TERM: "장기",
      UNKNOWN: "전략 미설정",
    };
    return {
      id: "losing_strategy",
      severity: "critical",
      title: `${labels[worst.type] ?? worst.type} 전략 승률이 낮습니다`,
      body: `${labels[worst.type] ?? worst.type} ${worst.count}건의 승률이 ${Math.round(worst.winRate)}%입니다. 해당 전략의 포지션 축소를 검토해보세요.`,
      metric: { label: "승률", value: `${Math.round(worst.winRate)}%` },
      linkSection: "strategy",
    };
  },

  // 태그 누락 비율 높음
  ({ summary }) => {
    if (summary.missingTagRate < 30 || summary.totalTrades < 5) return null;
    return {
      id: "tag_missing_rate_high",
      severity: "info",
      title: "매수 근거 태그 입력이 적어요",
      body: `매수 거래 중 ${Math.round(summary.missingTagRate)}%에 근거 태그가 없습니다. 매수 시 최소 1개 태그 입력을 권장합니다.`,
      metric: { label: "태그 누락률", value: `${Math.round(summary.missingTagRate)}%` },
      linkSection: "tag",
    };
  },

  // 거래 결과 입력 부족 (승률 신뢰도 낮음)
  ({ summary }) => {
    if (summary.resultInputRate >= 50 || summary.sellTrades < 3) return null;
    return {
      id: "result_missing",
      severity: "info",
      title: "거래 결과 입력이 부족해요",
      body: `매도 거래 중 ${Math.round(100 - summary.resultInputRate)}%에 결과(성공/실패)가 미입력되어 승률 분석 정확도가 낮습니다.`,
      metric: { label: "미입력률", value: `${Math.round(100 - summary.resultInputRate)}%` },
      linkSection: "strategy",
    };
  },

  // 승률 우수 — 현재 패턴 유지 권장
  ({ summary }) => {
    if (summary.winRate < 65 || summary.sellTrades < 5 || summary.resultInputRate < 50) return null;
    return {
      id: "high_winrate",
      severity: "info",
      title: "좋은 승률을 유지하고 있어요",
      body: `현재 승률 ${Math.round(summary.winRate)}%로 좋은 성과를 내고 있습니다. 지금의 매매 패턴을 유지해보세요.`,
      metric: { label: "승률", value: `${Math.round(summary.winRate)}%` },
      linkSection: "strategy",
    };
  },
];

export function evaluateRules(input: RuleInput): Suggestion[] {
  const results: Suggestion[] = [];
  for (const rule of rules) {
    const s = rule(input);
    if (s) results.push(s);
  }
  // critical → warn → info 순 정렬
  const order = { critical: 0, warn: 1, info: 2 };
  return results.sort((a, b) => order[a.severity] - order[b.severity]);
}
