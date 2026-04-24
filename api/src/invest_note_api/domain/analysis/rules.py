"""10개 투자 패턴 규칙 + evaluateRules 등가."""
from __future__ import annotations

import math
from dataclasses import dataclass
from typing import TYPE_CHECKING, Callable, TypedDict

from invest_note_api.domain.analysis.concentration import HHI_HIGH, TOP1_WEIGHT_HIGH
from invest_note_api.domain.trade_types import (
    EMOTION_CALM,
    EMOTION_FOMO,
    STRATEGY_LONG_TERM,
    STRATEGY_SCALPING,
    STRATEGY_SWING,
    STRATEGY_UNKNOWN,
)

if TYPE_CHECKING:
    from invest_note_api.domain.analysis.aggregate import AnalysisSummary
    from invest_note_api.domain.analysis.concentration import ConcentrationData
    from invest_note_api.domain.analysis.profile import BehaviorProfile


SEVERITY_INFO = "info"
SEVERITY_WARN = "warn"
SEVERITY_CRITICAL = "critical"

SECTION_STRATEGY = "strategy"
SECTION_EMOTION = "emotion"
SECTION_TAG = "tag"
SECTION_CONCENTRATION = "concentration"
SECTION_REVIEW = "review"


def _round(x: float) -> int:
    """JS Math.round 동작 (HALF_UP)."""
    return math.floor(x + 0.5)


@dataclass
class Suggestion:
    id: str
    severity: str    # "info" | "warn" | "critical"
    title: str
    body: str
    metric: dict | None = None        # {"label": str, "value": str}
    link_section: str | None = None   # "strategy" | "emotion" | "tag" | "concentration" | "review"


class RuleInput(TypedDict, total=False):
    summary: AnalysisSummary
    profile: BehaviorProfile
    concentration: ConcentrationData


_RuleFn = Callable[[RuleInput], Suggestion | None]


def _rule_fomo(inp: RuleInput) -> Suggestion | None:
    summary = inp["summary"]
    fomo = next((e for e in summary.by_emotion if e.type == EMOTION_FOMO), None)
    if not fomo or fomo.sell_count < 5 or fomo.result_count < 3 or fomo.win_rate >= 40:
        return None
    pct = _round(fomo.win_rate)
    return Suggestion(
        id="emotion_fomo_low_winrate",
        severity=SEVERITY_WARN,
        title="FOMO 상태에서의 매매 승률이 낮아요",
        body=f"FOMO 상태로 진입한 거래의 승률이 {pct}%입니다. 해당 감정에서는 관망을 권장합니다.",
        metric={"label": "FOMO 승률", "value": f"{pct}%"},
        link_section=SECTION_EMOTION,
    )


def _rule_calm(inp: RuleInput) -> Suggestion | None:
    summary = inp["summary"]
    calm = next((e for e in summary.by_emotion if e.type == EMOTION_CALM), None)
    if not calm or calm.sell_count < 5 or calm.win_rate < 60:
        return None
    pct = _round(calm.win_rate)
    return Suggestion(
        id="emotion_calm_high_winrate",
        severity=SEVERITY_INFO,
        title="평온할 때 성과가 가장 좋아요",
        body=f"CALM 상태 거래 승률 {pct}% — 현재 매매 패턴을 유지하세요.",
        metric={"label": "평온 승률", "value": f"{pct}%"},
        link_section=SECTION_EMOTION,
    )


def _rule_concentration(inp: RuleInput) -> Suggestion | None:
    concentration = inp.get("concentration")
    if not concentration:
        return None
    top1_weight = concentration.top3[0]["weight"] if concentration.top3 else 0.0
    if concentration.hhi <= HHI_HIGH and top1_weight <= TOP1_WEIGHT_HIGH:
        return None
    return Suggestion(
        id="concentration_high",
        severity=SEVERITY_WARN,
        title="한 종목 비중이 높습니다",
        body=f"상위 종목 비중 {_round(top1_weight * 100)}%, 집중도(HHI) {concentration.hhi:.2f} — 분산 투자를 고려해보세요.",
        metric={"label": "HHI", "value": f"{concentration.hhi:.2f}"},
        link_section=SECTION_CONCENTRATION,
    )


def _rule_feeling_heavy(inp: RuleInput) -> Suggestion | None:
    summary = inp["summary"]
    if summary.feeling_rate < 40 or summary.total_trades < 5:
        return None
    pct = _round(summary.feeling_rate)
    return Suggestion(
        id="feeling_heavy",
        severity=SEVERITY_WARN,
        title="'감'으로 진입하는 비율이 높아요",
        body=f"전체 매수 중 {pct}%가 감/직감 태그. 기술적 또는 펀더멘털 근거 1개 추가를 권장합니다.",
        metric={"label": "감/직감 비율", "value": f"{pct}%"},
        link_section=SECTION_TAG,
    )


def _rule_no_reflection(inp: RuleInput) -> Suggestion | None:
    summary = inp["summary"]
    if summary.reflection_rate >= 30 or summary.sell_trades < 3:
        return None
    pct = _round(summary.reflection_rate)
    return Suggestion(
        id="no_reflection",
        severity=SEVERITY_INFO,
        title="매도 후 회고가 드물어요",
        body=f"매도 {summary.sell_trades}건 중 회고 작성률 {pct}%. 최근 매도 거래에 회고를 남겨보세요.",
        metric={"label": "회고 작성률", "value": f"{pct}%"},
        link_section=SECTION_REVIEW,
    )


def _rule_holding_mismatch(inp: RuleInput) -> Suggestion | None:
    summary = inp["summary"]
    scalping = next((s for s in summary.by_strategy if s.type == STRATEGY_SCALPING), None)
    if not scalping or scalping.count < 3 or scalping.avg_holding_days <= 7:
        return None
    days = _round(scalping.avg_holding_days)
    return Suggestion(
        id="holding_mismatch",
        severity=SEVERITY_INFO,
        title="스캘핑 전략인데 보유 기간이 깁니다",
        body=f"스캘핑으로 분류된 거래의 평균 보유일이 {days}일입니다. 전략 태그를 재검토해보세요.",
        metric={"label": "평균 보유일", "value": f"{days}일"},
        link_section=SECTION_STRATEGY,
    )


def _rule_losing_strategy(inp: RuleInput) -> Suggestion | None:
    summary = inp["summary"]
    worst = next(
        (s for s in summary.by_strategy if s.count >= 5 and s.result_count >= 3 and s.win_rate < 30),
        None,
    )
    if not worst:
        return None
    label = _STRATEGY_LABELS.get(worst.type, worst.type)
    pct = _round(worst.win_rate)
    return Suggestion(
        id="losing_strategy",
        severity=SEVERITY_CRITICAL,
        title=f"{label} 전략 승률이 낮습니다",
        body=f"{label} {worst.count}건의 승률이 {pct}%입니다. 해당 전략의 포지션 축소를 검토해보세요.",
        metric={"label": "승률", "value": f"{pct}%"},
        link_section=SECTION_STRATEGY,
    )


def _rule_tag_missing(inp: RuleInput) -> Suggestion | None:
    summary = inp["summary"]
    if summary.missing_tag_rate < 30 or summary.total_trades < 5:
        return None
    pct = _round(summary.missing_tag_rate)
    return Suggestion(
        id="tag_missing_rate_high",
        severity=SEVERITY_INFO,
        title="매수 근거 태그 입력이 적어요",
        body=f"매수 거래 중 {pct}%에 근거 태그가 없습니다. 매수 시 최소 1개 태그 입력을 권장합니다.",
        metric={"label": "태그 누락률", "value": f"{pct}%"},
        link_section=SECTION_TAG,
    )


def _rule_result_missing(inp: RuleInput) -> Suggestion | None:
    summary = inp["summary"]
    if summary.result_input_rate >= 50 or summary.sell_trades < 3:
        return None
    pct = _round(100 - summary.result_input_rate)
    return Suggestion(
        id="result_missing",
        severity=SEVERITY_INFO,
        title="거래 결과 입력이 부족해요",
        body=f"매도 거래 중 {pct}%에 결과(성공/실패)가 미입력되어 승률 분석 정확도가 낮습니다.",
        metric={"label": "미입력률", "value": f"{pct}%"},
        link_section=SECTION_STRATEGY,
    )


def _rule_high_winrate(inp: RuleInput) -> Suggestion | None:
    summary = inp["summary"]
    if summary.win_rate < 65 or summary.sell_trades < 5 or summary.result_input_rate < 50:
        return None
    pct = _round(summary.win_rate)
    return Suggestion(
        id="high_winrate",
        severity=SEVERITY_INFO,
        title="좋은 승률을 유지하고 있어요",
        body=f"현재 승률 {pct}%로 좋은 성과를 내고 있습니다. 지금의 매매 패턴을 유지해보세요.",
        metric={"label": "승률", "value": f"{pct}%"},
        link_section=SECTION_STRATEGY,
    )


_RULES: list[_RuleFn] = [
    _rule_fomo,
    _rule_calm,
    _rule_concentration,
    _rule_feeling_heavy,
    _rule_no_reflection,
    _rule_holding_mismatch,
    _rule_losing_strategy,
    _rule_tag_missing,
    _rule_result_missing,
    _rule_high_winrate,
]

_SEVERITY_ORDER = {SEVERITY_CRITICAL: 0, SEVERITY_WARN: 1, SEVERITY_INFO: 2}
_STRATEGY_LABELS = {
    STRATEGY_SCALPING: "스캘핑",
    STRATEGY_SWING: "스윙",
    STRATEGY_LONG_TERM: "장기",
    STRATEGY_UNKNOWN: "전략 미설정",
}


def evaluate_rules(inp: RuleInput) -> list[Suggestion]:
    results = [s for rule in _RULES if (s := rule(inp)) is not None]
    return sorted(results, key=lambda s: _SEVERITY_ORDER.get(s.severity, 99))
