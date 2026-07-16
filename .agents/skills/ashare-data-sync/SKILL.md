---
name: ashare-data-sync
description: Use when the user wants to sync, refresh, inspect, or troubleshoot A-share market data for the rich A-share rotation agent, including Sina realtime quotes, Baostock daily bars, Eastmoney/InStock money flow, AKShare limit-up/dragon-tiger events, derived stock features, SQLite status, or the deployed Linux service.
---

# A-share Data Sync

Use this skill to update or inspect the local data warehouse for the A-share rotation agent.

This skill only manages data freshness and quality. Strategy interpretation,
emotion-cycle classification, position bias, and Yangjia-style red-line checks
live in `ashare-daily-review`, `ashare-sector-review`, and
`../references/yangjia-emotion-framework.md`.

## Service Context

- Local repo: `/Users/yibopang/Documents/rich`
- Deployed server repo: `/data/home/yibopang/rich`
- Server host: `yibopang@9.134.113.106`
- Service URL: `http://9.134.113.106:8000`
- SQLite path on server: `/data/home/yibopang/rich/data/rich.sqlite3`

## Data Source Rules

- Prefer `instock-em` for the current validated free money-flow path. It uses public Eastmoney pages plus `EASTMONEY_COOKIE` / optional `EASTMONEY_PROXY`.
- Prefer `sina` for realtime individual stock quotes.
- Prefer `baostock` for real daily bars and historical stock snapshots.
- Use `akshare-events`, `limit-up-events`, or `dragon-tiger` for real AKShare/Eastmoney event sync.
- Use `derived-features` after quote and money-flow sync to build amount/turnover/fund-flow/rush-accumulation features.
- `auto` may try multiple public sources and can be slower or noisier; for controlled validation run provider-specific syncs.
- Use `tushare`, `tushare-sector`, or `tushare-stock` only when `TUSHARE_TOKEN` is configured in the server environment or `/data/home/yibopang/rich/.env`.
- Never silently treat mock data as live data. If `/health` returns `mock_fallback`, say that sector-level strategy conclusions are not fully validated.
- If `/data/quality` reports missing sector fund-flow or stock money-flow rows, say strategy confidence is capped by data availability even when sector snapshots exist.
- If `/data/quality` reports missing limit-up events or derived features, say emotion-cycle and rush-accumulation conclusions are incomplete.
- Dragon-tiger data is after-close evidence. Do not use it as an intraday signal.

## Common Commands

Refresh Eastmoney money flow through the fixed remote API before analysis:

```bash
curl -sS -X POST 'http://9.134.113.106:8000/data/sync?provider=instock-em&trade_date=YYYY-MM-DD'
curl -sS 'http://9.134.113.106:8000/data/quality'
```

Use `instock-em` when the goal is "refresh current Eastmoney data". It refreshes
individual money flow, sector fund flow, and derived features. The read-only
endpoints such as `/data/moneyflow/latest` do not fetch new data; they only read
the latest rows already stored in SQLite.

Check service:

```bash
ssh yibopang@9.134.113.106 'cd /data/home/yibopang/rich && ./scripts/rich-service.sh status && curl -sS http://127.0.0.1:8000/health && echo && curl -sS http://127.0.0.1:8000/data/status'
```

Check data quality:

```bash
ssh yibopang@9.134.113.106 'curl -sS http://127.0.0.1:8000/data/quality'
```

Sync selected realtime quotes:

```bash
ssh yibopang@9.134.113.106 'cd /data/home/yibopang/rich && ./scripts/rich-service.sh sync --provider sina --symbols 600118.SH,600000.SH,000001.SZ'
```

Sync Baostock daily bars:

```bash
ssh yibopang@9.134.113.106 'cd /data/home/yibopang/rich && ./scripts/rich-service.sh sync --provider baostock --trade-date YYYY-MM-DD --max-symbols 500'
```

Sync Tushare fund-flow after configuring `TUSHARE_TOKEN`:

```bash
ssh yibopang@9.134.113.106 'cd /data/home/yibopang/rich && ./scripts/rich-service.sh sync --provider tushare --trade-date YYYY-MM-DD'
```

Sync InStock-compatible Eastmoney fund-flow:

```bash
ssh yibopang@9.134.113.106 'cd /data/home/yibopang/rich && ./scripts/rich-service.sh sync --provider instock-em --trade-date YYYY-MM-DD'
```

Equivalent remote API call:

```bash
curl -sS -X POST 'http://9.134.113.106:8000/data/sync?provider=instock-em&trade_date=YYYY-MM-DD'
```

If Eastmoney blocks the server, put `EASTMONEY_COOKIE` and/or `EASTMONEY_PROXY` in `/data/home/yibopang/rich/.env`.

Sync events and derived features:

```bash
ssh yibopang@9.134.113.106 'cd /data/home/yibopang/rich && ./scripts/rich-service.sh sync --provider akshare-events --trade-date YYYY-MM-DD'
ssh yibopang@9.134.113.106 'cd /data/home/yibopang/rich && ./scripts/rich-service.sh sync --provider derived-features --trade-date YYYY-MM-DD'
```

View latest realtime quotes:

```bash
curl -sS 'http://9.134.113.106:8000/data/realtime/latest?limit=20'
```

View latest stock snapshots:

```bash
curl -sS 'http://9.134.113.106:8000/data/stocks/latest?limit=20'
```

View latest stock money-flow rows:

```bash
curl -sS 'http://9.134.113.106:8000/data/moneyflow/latest?limit=20'
```

View latest features and events:

```bash
curl -sS 'http://9.134.113.106:8000/data/features/latest?limit=20'
curl -sS 'http://9.134.113.106:8000/data/events/limit-up/latest?limit=20'
curl -sS 'http://9.134.113.106:8000/data/events/latest?event_type=dragon_tiger&limit=20'
curl -sS 'http://9.134.113.106:8000/data/events/latest?event_type=rush_accumulation&limit=20'
```

## Output Discipline

When reporting data status, include:

- Data source used.
- Timestamp.
- Row counts.
- Whether sector/fund-flow data is present.
- Whether stock-level money-flow data is present.
- Whether limit-up events, dragon-tiger events, and derived stock features are present.
- Whether conclusions must be downgraded due to missing sector data.
