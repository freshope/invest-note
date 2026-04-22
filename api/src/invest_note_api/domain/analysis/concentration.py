"""집중도(HHI) 계산."""
from __future__ import annotations

from dataclasses import dataclass
from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from invest_note_api.domain.portfolio import Position
    from invest_note_api.domain.trade_types import Trade

HHI_HIGH = 0.5
HHI_MID = 0.25
TOP1_WEIGHT_HIGH = 0.4


@dataclass
class ConcentrationData:
    hhi: float
    top3: list[dict]          # [{"asset": str, "weight": float}]
    by_country: list[dict]    # [{"code": str, "weight": float}]
    by_market: list[dict]     # [{"type": str, "weight": float}]


def compute_concentration(positions: list[Position], trades: list[Trade]) -> ConcentrationData:
    values = [
        {
            "key": p.key,
            "asset": p.asset_name,
            "country": p.country,
            "value": p.evaluation if p.evaluation is not None else p.cost_basis,
        }
        for p in positions
    ]

    total = sum(v["value"] for v in values)
    if total == 0:
        return ConcentrationData(hhi=0.0, top3=[], by_country=[], by_market=[])

    hhi = sum((v["value"] / total) ** 2 for v in values)

    top3 = [
        {"asset": v["asset"], "weight": v["value"] / total}
        for v in sorted(values, key=lambda x: x["value"], reverse=True)[:3]
    ]

    country_map: dict[str, float] = {}
    for v in values:
        country_map[v["country"]] = country_map.get(v["country"], 0.0) + v["value"]
    by_country = sorted(
        [{"code": k, "weight": val / total} for k, val in country_map.items()],
        key=lambda x: x["weight"],
        reverse=True,
    )

    market_by_key: dict[str, str] = {}
    for t in sorted(trades, key=lambda t: t.traded_at):
        if t.trade_type == "BUY":
            key = f"{t.ticker_symbol or t.asset_name}:{t.country_code or 'KR'}"
            market_by_key[key] = t.market_type

    market_map: dict[str, float] = {}
    for v in values:
        mt = market_by_key.get(v["key"], "ETC")
        market_map[mt] = market_map.get(mt, 0.0) + v["value"]
    by_market = sorted(
        [{"type": k, "weight": val / total} for k, val in market_map.items()],
        key=lambda x: x["weight"],
        reverse=True,
    )

    return ConcentrationData(hhi=hhi, top3=top3, by_country=by_country, by_market=by_market)
