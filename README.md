# A-share Rotation Agent MVP

This repository contains a research-oriented MVP for an A-share short-term
capital rotation and catch-up strategy agent.

The service now supports a SQLite-first local data path. Use `ashare-sync` or
`scripts/rich-service.sh sync` to fetch real public-market snapshots through
AKShare and persist them into SQLite. If no local data exists, the API falls
back to mock data so the service stays alive.

## What It Does

- Scores market mainlines by sector.
- Classifies sector lifecycle stage.
- Identifies leader observation symbols.
- Produces catch-up candidates with reasons, risks, triggers, and invalidation
  conditions.
- Provides a simple historical backtest scaffold.
- Syncs AKShare limit-up and dragon-tiger events.
- Derives stock features such as amount rank, fund-flow rank, and rush-accumulation score.
- Exposes the research functions through FastAPI and MCP tools for Codex.

## Quickstart

```bash
python3 -m venv .venv
source .venv/bin/activate
python -m pip install -e ".[dev]"
pytest
ashare-report
```

Run the API:

```bash
ashare-api
```

Sync real market snapshots into SQLite:

```bash
ashare-sync
ashare-sync --provider sina --symbols 600000.SH,000001.SZ
ashare-sync --provider baostock --trade-date 2026-07-13 --max-symbols 200
```

Check whether the stored data is strong enough for sector rotation analysis:

```bash
curl -sS http://127.0.0.1:8000/data/quality
```

Free Sina sector data provides price/turnover heat, but not real main-fund
flow. For higher-confidence mainline/catch-up analysis, configure a real
fund-flow source such as Tushare:

```bash
cat > .env <<'EOF'
TUSHARE_TOKEN=your_token_here
EOF

./scripts/rich-service.sh sync --provider tushare --trade-date 2026-07-14
curl -sS 'http://127.0.0.1:8000/data/moneyflow/latest?limit=20'
```

The service also includes a lightweight InStock-compatible Eastmoney provider
for public money-flow pages. It does not import InStock's MySQL, web UI, or
trading modules. If the server can reach Eastmoney directly, run:

```bash
./scripts/rich-service.sh sync --provider instock-em --trade-date 2026-07-14
```

If Eastmoney blocks the server IP, configure optional access helpers in `.env`:

```bash
EASTMONEY_COOKIE=your_browser_cookie_here
EASTMONEY_PROXY=http://user:pass@host:port
```

Sync after-close events and derived features:

```bash
./scripts/rich-service.sh sync --provider akshare-events --trade-date 2026-07-14
./scripts/rich-service.sh sync --provider derived-features --trade-date 2026-07-14
curl -sS 'http://127.0.0.1:8000/data/events/limit-up/latest?limit=20'
curl -sS 'http://127.0.0.1:8000/data/events/latest?event_type=dragon_tiger&limit=20'
curl -sS 'http://127.0.0.1:8000/data/features/latest?limit=20'
```

The default database is `data/rich.sqlite3`. Override it with:

```bash
RICH_DB_PATH=/path/to/rich.sqlite3 ashare-sync
RICH_DB_PATH=/path/to/rich.sqlite3 ashare-api
```

Linux service helper:

```bash
./scripts/rich-service.sh start
./scripts/rich-service.sh sync
./scripts/rich-service.sh status
./scripts/rich-service.sh logs
```

Run the MCP server:

```bash
ashare-mcp
```

## Codex Skills

Repository-scoped Codex skills live in `.agents/skills`:

- `ashare-data-sync`: sync and inspect market data.
- `ashare-sector-review`: review sectors such as 医药, PCB, CPO, 半导体, AI算力.
- `ashare-daily-review`: generate the daily rotation report.
- `ashare-backtest-check`: validate strategy metrics and future-leakage risks.

If a newly added skill does not appear immediately, restart the Codex task from
this repository.

## Codex MCP Configuration

You can add the local MCP server to Codex with:

```bash
codex mcp add ashare_rotation -- ashare-mcp
```

For local development without installing the package globally:

```bash
codex mcp add ashare_rotation -- python -m ashare_agent.apps.mcp_server.server
```

## Safety Boundary

This project is for research and decision support only. It must not place
orders, promise returns, or present any output as investment advice.

AKShare uses public data sources. Availability, field names, delay, and rate
limits may change. Treat synced data as research input and verify critical
fields before relying on them.

If `/data/quality` reports missing sector fund-flow or stock money-flow rows,
strategy confidence is intentionally capped. That is a data-source limitation,
not a signal-strength conclusion.

Dragon-tiger rows are after-close evidence. Do not use them as intraday signals
or in historical tests before their actual availability timestamp.
