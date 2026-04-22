"""투자 행동 프로파일 계산."""
from __future__ import annotations

from dataclasses import dataclass
from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from invest_note_api.domain.trade_types import Trade


@dataclass
class BehaviorProfile:
    tempo: float
    diversification: float
    emotion_stability: float
    reasoning_quality: float
    review_habit: float


@dataclass
class ProfileInputRates:
    holding_days: float
    emotion: float
    reasoning_tag: float
    result: float
    reflection: float


def _clamp(v: float) -> float:
    return min(100.0, max(0.0, v))


def compute_profile(
    trades: list[Trade],
    hhi: float,
    holding_days_map: dict[str, int],
) -> tuple[BehaviorProfile, ProfileInputRates]:
    sells = [t for t in trades if t.trade_type == "SELL"]
    buys = [t for t in trades if t.trade_type == "BUY"]

    # holding_days_map은 allTrades 기준이므로 기간 내 SELL id로 필터링
    sell_ids = {t.id for t in sells}
    all_days = [v for k, v in holding_days_map.items() if k in sell_ids]
    avg_days = sum(all_days) / len(all_days) if all_days else 0.0
    scalping = sum(1 for t in sells if t.strategy_type == "SCALPING")
    scalping_ratio = scalping / len(sells) if sells else 0.0
    tempo_base = _clamp((avg_days / 60) * 100)
    tempo = _clamp(tempo_base - scalping_ratio * 10)

    if not sells and not buys:
        diversification = 50.0
    else:
        diversification = _clamp((1 - hhi) * 100)

    emotion_tagged = [t for t in trades if t.emotion is not None]
    unstable = sum(1 for t in emotion_tagged if t.emotion in ("FOMO", "IMPULSIVE", "ANXIOUS"))
    emotion_stability = (
        _clamp((1 - unstable / len(emotion_tagged)) * 100) if emotion_tagged else 50.0
    )

    buys_with_feeling = sum(1 for t in buys if "FEELING" in (t.reasoning_tags or []))
    buys_with_no_tag = sum(1 for t in buys if not t.reasoning_tags)
    poor_ratio = (buys_with_feeling + buys_with_no_tag) / len(buys) if buys else 0.0
    reasoning_quality = _clamp((1 - min(1.0, poor_ratio)) * 100)

    with_reflection = sum(
        1 for t in sells if t.reflection_note and t.reflection_note.strip()
    )
    review_habit = _clamp((with_reflection / len(sells)) * 100) if sells else 0.0

    sells_with_holding = len(all_days)
    input_rates = ProfileInputRates(
        holding_days=sells_with_holding / len(sells) * 100 if sells else 0.0,
        emotion=len(emotion_tagged) / len(trades) * 100 if trades else 0.0,
        reasoning_tag=(len(buys) - buys_with_no_tag) / len(buys) * 100 if buys else 0.0,
        result=sum(1 for t in sells if t.result is not None) / len(sells) * 100 if sells else 0.0,
        reflection=with_reflection / len(sells) * 100 if sells else 0.0,
    )

    profile = BehaviorProfile(
        tempo=tempo,
        diversification=diversification,
        emotion_stability=emotion_stability,
        reasoning_quality=reasoning_quality,
        review_habit=review_habit,
    )
    return profile, input_rates
