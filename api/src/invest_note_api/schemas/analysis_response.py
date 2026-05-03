"""분석 응답 스키마 — /api/analysis/dashboard."""
from __future__ import annotations

from invest_note_api.domain.trade_types import EmotionBucket, ReasoningTagBucket
from invest_note_api.schemas._base import CamelModel


class StrategyStatsResponse(CamelModel):
    type: str
    count: int
    result_count: int
    win_rate: float
    sum_pnl: float
    avg_holding_days: float


class EmotionStatsResponse(CamelModel):
    type: EmotionBucket
    count: int
    result_count: int
    win_rate: float
    sum_pnl: float


class TagStatsResponse(CamelModel):
    tag: ReasoningTagBucket
    count: int
    win_rate: float
    sum_pnl: float


class StrategyAdherenceStatsResponse(CamelModel):
    type: str
    count: int
    result_count: int
    win_rate: float
    sum_pnl: float


class AnalysisSummaryResponse(CamelModel):
    period: str
    total_trades: int
    sell_trades: int
    win_rate: float
    total_profit_loss: float
    by_strategy: list[StrategyStatsResponse]
    by_emotion: list[EmotionStatsResponse]
    by_tag: list[TagStatsResponse]
    strategy_adherence_rate: float
    by_strategy_adherence: list[StrategyAdherenceStatsResponse]
    missing_tag_rate: float
    feeling_rate: float
    reflection_rate: float
    result_input_rate: float


class BehaviorProfileResponse(CamelModel):
    tempo: float
    emotion_stability: float
    reasoning_quality: float
    review_habit: float
    strategy_consistency: float


class ProfileInputRatesResponse(CamelModel):
    holding_days: float
    emotion: float
    reasoning_tag: float
    result: float
    reflection: float
    strategy: float


class HistogramBucket(CamelModel):
    bucket: str
    count: int


class ConcentrationResponse(CamelModel):
    hhi: float
    top3: list[dict]
    by_country: list[dict]
    by_market: list[dict]


class BehaviorResponse(CamelModel):
    period: str
    profile: BehaviorProfileResponse
    input_rates: ProfileInputRatesResponse
    holding_period_dist: list[HistogramBucket]
    position_size_dist: list[HistogramBucket]
    concentration: ConcentrationResponse


class SuggestionResponse(CamelModel):
    id: str
    severity: str
    title: str
    body: str
    metric: dict | None = None
    link_section: str | None = None


class SuggestionsResponse(CamelModel):
    period: str
    suggestions: list[SuggestionResponse]


class AnalysisDashboardResponse(CamelModel):
    period: str
    summary: AnalysisSummaryResponse
    behavior: BehaviorResponse
    suggestions: SuggestionsResponse
