# Repository Instructions

## Product Boundary

- This repository is a research and decision-support system for A-share market
  analysis. Do not present outputs as investment advice.
- Do not promise returns, use deterministic phrases such as "must rise", or
  frame any stock as a guaranteed buy.
- Leader symbols are for observing sector strength only. Do not automatically
  treat leaders as buy candidates.
- Every strategy output must include data timestamps, reasons, risks, trigger
  conditions, and invalidation conditions.
- If source data is incomplete, stale, delayed, or mocked, lower confidence and
  say so clearly.

## Engineering Rules

- Keep the strategy layer independent from concrete data providers.
- Prefer typed Pydantic models at service boundaries.
- Do not add real brokerage or order execution code.
- Avoid future leakage in backtests. Only use data that would have been
  available at the evaluated timestamp.
- Add or update focused tests when changing scoring, filtering, report, API, or
  MCP behavior.

## Verification

- Run `pytest` after changes to strategy logic, models, API handlers, or MCP
  tools.
