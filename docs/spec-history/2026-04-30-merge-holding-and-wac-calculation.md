# Spec: Merge Holding And WAC Calculation

> 완료: 2026-04-30

## Background / Problem

`compute_total_holding` and `compute_wac` both walk the same trade list in `domain/holdings.py`, and `routers/portfolio.py` calls them back-to-back. This causes duplicated sorting/filtering work and keeps closely related holding accounting split across two functions.

## Goals

- Replace the two public calculations with one function that returns both total quantity and weighted average cost.
- Update portfolio code to call the combined function once per symbol/group.
- Preserve existing accounting behavior and test coverage.

## Design

### Approach

Introduce a single holdings-domain helper that sorts and applies BUY/SELL effects once, returning both `quantity` and `avg_buy_price`. Preserve the current `float`-based behavior used by the API response models.

### Primary Files

- `api/src/invest_note_api/domain/holdings.py` - merge duplicated holding and WAC loops.
- `api/src/invest_note_api/routers/portfolio.py` - call the combined helper once.
- `api/src/invest_note_api/routers/trades.py` - use the combined helper for SELL quantity validation.
- `api/tests/` - update or add focused tests for the combined calculation if needed.

## Implementation Checklist

- [x] Merge `compute_total_holding` and `compute_wac` into one cohesive holdings calculation.
- [x] Update portfolio router call sites to use the combined result.
- [x] Run backend tests for the affected domain/router behavior.

## Risks / Open Questions

- Need to preserve current sell clamping behavior when SELL quantity exceeds tracked buys.
