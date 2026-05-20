"""투자 행동 프로파일 계산."""
from __future__ import annotations

from dataclasses import dataclass
from statistics import median
from typing import TYPE_CHECKING

from invest_note_api.domain.analysis._math import _percent
from invest_note_api.domain.analysis.strategy_adherence import (
    ADHERENCE_FOLLOWED,
    ADHERENCE_UNKNOWN,
)
from invest_note_api.domain.trade_types import (
    EMOTION_ANXIOUS,
    EMOTION_FOMO,
    EMOTION_IMPULSIVE,
    TAG_FEELING,
    TRADE_TYPE_BUY,
    TRADE_TYPE_SELL,
)

if TYPE_CHECKING:
    from invest_note_api.domain.analysis.strategy_adherence import StrategyEvaluation
    from invest_note_api.domain.trade_types import Trade


@dataclass
class BehaviorProfile:
    tempo: float
    emotion_stability: float
    reasoning_quality: float
    review_habit: float
    strategy_consistency: float


@dataclass
class ProfileInputRates:
    holding_days: float
    emotion: float
    reasoning_tag: float
    buy_reason: float
    reflection: float
    strategy: float


def _clamp(v: float) -> float:
    return min(100.0, max(0.0, v))


def compute_profile(
    trades: list[Trade],
    holding_days_map: dict[str, int],
    strategy_evals: dict[str, StrategyEvaluation] | None = None,
) -> tuple[BehaviorProfile, ProfileInputRates]:
    """trades와 holding_days_map은 모두 동일 period 범위에서 빌드된 입력이어야 한다."""
    sells = [t for t in trades if t.trade_type == TRADE_TYPE_SELL]
    buys = [t for t in trades if t.trade_type == TRADE_TYPE_BUY]

    # 기간 내 SELL 기준 보유일만 사용 (이상치에 강하도록 중앙값 사용)
    sell_ids = {t.id for t in sells}
    period_days = [v for k, v in holding_days_map.items() if k in sell_ids]
    median_days = median(period_days) if period_days else 0.0
    tempo = _clamp((median_days / 60) * 100)

    emotion_tagged = [t for t in trades if t.emotion is not None]
    if emotion_tagged:
        unstable = sum(
            1 for t in emotion_tagged if t.emotion in (EMOTION_FOMO, EMOTION_IMPULSIVE, EMOTION_ANXIOUS)
        )
        emotion_stability = _clamp((1 - unstable / len(emotion_tagged)) * 100)
    else:
        # 입력 없을 때 50점 부여는 misleading → 0점 + 입력률 경고로 표시
        emotion_stability = 0.0

    buys_with_feeling = sum(1 for t in buys if TAG_FEELING in (t.reasoning_tags or []))
    buys_with_no_tag = sum(1 for t in buys if not t.reasoning_tags)
    # buys_with_feeling과 buys_with_no_tag는 mutually exclusive → poor_ratio ∈ [0, 1]
    poor_ratio = (buys_with_feeling + buys_with_no_tag) / len(buys) if buys else 0.0
    reasoning_quality = (1 - poor_ratio) * 100

    with_sell_reason = sum(
        1 for t in sells if t.sell_reason and t.sell_reason.strip()
    )
    review_habit = _percent(with_sell_reason, len(sells))

    # 전략 일관성: 기간 내 SELL 중 UNKNOWN 제외 평가에서 FOLLOWED 비율
    if strategy_evals:
        period_evals = [
            e for sid, e in strategy_evals.items() if sid in sell_ids
        ]
        judged = [e for e in period_evals if e.adherence != ADHERENCE_UNKNOWN]
        followed = sum(1 for e in judged if e.adherence == ADHERENCE_FOLLOWED)
        strategy_consistency = _percent(followed, len(judged))
        strategy_input_rate = _percent(len(judged), len(sells))
    else:
        strategy_consistency = 0.0
        strategy_input_rate = 0.0

    input_rates = ProfileInputRates(
        holding_days=_percent(len(period_days), len(sells)),
        emotion=_percent(len(emotion_tagged), len(trades)),
        reasoning_tag=_percent(len(buys) - buys_with_no_tag, len(buys)),
        buy_reason=_percent(
            sum(1 for t in buys if t.buy_reason and t.buy_reason.strip()), len(buys)
        ),
        reflection=review_habit,
        strategy=strategy_input_rate,
    )

    profile = BehaviorProfile(
        tempo=tempo,
        emotion_stability=emotion_stability,
        reasoning_quality=reasoning_quality,
        review_habit=review_habit,
        strategy_consistency=strategy_consistency,
    )
    return profile, input_rates
