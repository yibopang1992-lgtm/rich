---
name: ashare-refresh-before-analysis
description: Use before any rich A-share analysis, daily review, sector review, rotation/catch-up judgment, mainline report, or strategy endpoint reading when the user expects current data. This skill refreshes the fixed remote service http://9.134.113.106:8000 with Eastmoney/InStock money flow and derived features before analysis.
---

# A-share Refresh Before Analysis

Use this skill as the first step before analyzing the rich A-share rotation
agent when the user asks for current market, sector, rotation, catch-up,
limit-up linkage, high-low-switch, or daily review conclusions.

## Fixed Service

- Service URL: `http://9.134.113.106:8000`
- Server repo: `/data/home/yibopang/rich`
- SQLite: `/data/home/yibopang/rich/data/rich.sqlite3`
- Do not use `localhost` as the user-facing service endpoint.

## Required Refresh Workflow

1. Call `POST /data/sync?provider=instock-em&trade_date=YYYY-MM-DD` for the current China trading date.
2. Check `/data/quality`.
3. Continue analysis only after confirming the latest money-flow, sector, and feature timestamps.
4. If sync fails or timestamps are stale, continue only with a clearly downgraded confidence note.

## Commands

Use the current Asia/Shanghai date. Example:

```bash
curl -sS -X POST 'http://9.134.113.106:8000/data/sync?provider=instock-em&trade_date=YYYY-MM-DD'
curl -sS 'http://9.134.113.106:8000/data/quality'
```

Provider behavior:

- `instock-em`: refreshes Eastmoney individual stock money flow, sector fund flow, and derived features.
- `instock-em-stock`: refreshes only individual stock money flow and derived features.
- `instock-em-sector`: refreshes only sector fund flow.
- `derived-features`: rebuilds features from already stored quotes/money-flow.

## Freshness Rules

- For current analysis, latest `stock_moneyflow`, `sector_snapshots`, and
  `stock_features` should match the current trading date.
- If latest stock/realtime snapshots are older than money-flow rows, say that
  money-flow evidence is current but amount/turnover/quote evidence may lag.
- Limit-up and dragon-tiger events are separate after-close evidence; refresh
  them with `akshare-events` only when the analysis specifically needs latest
  event/ladder evidence.
- Never silently use mock or stale data as live evidence.

## Output Discipline

When reporting refresh status, include:

- Sync provider used.
- Trade date.
- Rows written for money-flow, sector rows, and features.
- Data quality confidence ceiling.
- Any stale timestamp or failed data source.

