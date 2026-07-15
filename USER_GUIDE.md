# Rich A-share Rotation Agent User Guide

This system is for A-share market research and decision support only. It is not
investment advice, does not guarantee returns, and does not place trades.

## Quick Start

Install locally:

```bash
python3 -m venv .venv
source .venv/bin/activate
python -m pip install -e ".[dev]"
pytest
```

Start the API:

```bash
ashare-api
```

Or use the Linux service helper:

```bash
./scripts/rich-service.sh start
./scripts/rich-service.sh status
./scripts/rich-service.sh logs
```

Default API URL:

```text
http://127.0.0.1:8000
```

The deployed development server used by this project:

```text
http://9.134.113.106:8000
```

## Environment Variables

Create `.env` when you need authenticated or optional data access:

```bash
EASTMONEY_COOKIE=your_browser_cookie_here
EASTMONEY_PROXY=http://user:pass@host:port
TUSHARE_TOKEN=your_tushare_token_here
RICH_DB_PATH=data/rich.sqlite3
RICH_PROVIDER_MODE=sqlite
```

Do not commit `.env`.

## Daily Data Sync

Sync the validated free Eastmoney money-flow path:

```bash
./scripts/rich-service.sh sync --provider instock-em --trade-date YYYY-MM-DD
```

Sync limit-up and dragon-tiger events:

```bash
./scripts/rich-service.sh sync --provider akshare-events --trade-date YYYY-MM-DD
```

Build derived features and rush-accumulation events:

```bash
./scripts/rich-service.sh sync --provider derived-features --trade-date YYYY-MM-DD
```

Sync selected realtime quotes:

```bash
./scripts/rich-service.sh sync --provider sina --symbols 600276.SH,002821.SZ,002558.SZ
```

Sync Baostock daily bars:

```bash
./scripts/rich-service.sh sync --provider baostock --trade-date YYYY-MM-DD --max-symbols 500
```

Optional Tushare sync after configuring `TUSHARE_TOKEN`:

```bash
./scripts/rich-service.sh sync --provider tushare --trade-date YYYY-MM-DD
```

## Health and Data Quality

Always check health and quality before analysis:

```bash
curl -sS http://127.0.0.1:8000/health
curl -sS http://127.0.0.1:8000/data/quality
```

Important quality fields:

| Field | Meaning |
|---|---|
| `analysis_confidence_ceiling` | Maximum allowed confidence based on available data. |
| `blockers` | Missing data that should downgrade conclusions. |
| `latest_moneyflow_as_of` | Latest stock money-flow timestamp. |
| `latest_sector_as_of` | Latest sector snapshot timestamp. |
| `latest_limit_up_as_of` | Latest limit-up event timestamp. |
| `latest_news_event_as_of` | Latest after-close event timestamp. |
| `latest_feature_as_of` | Latest derived feature timestamp. |

If blockers are present, do not make high-confidence strategy conclusions.

## Useful API Calls

Mainline and rotation:

```bash
curl -sS http://127.0.0.1:8000/strategy/mainlines
curl -sS http://127.0.0.1:8000/strategy/rotation
curl -sS 'http://127.0.0.1:8000/strategy/catchup-candidates?max_candidates=10'
```

Data inspection:

```bash
curl -sS 'http://127.0.0.1:8000/data/moneyflow/latest?limit=20'
curl -sS 'http://127.0.0.1:8000/data/features/latest?limit=20'
curl -sS 'http://127.0.0.1:8000/data/events/limit-up/latest?limit=20'
curl -sS 'http://127.0.0.1:8000/data/events/latest?event_type=dragon_tiger&limit=20'
curl -sS 'http://127.0.0.1:8000/data/events/latest?event_type=rush_accumulation&limit=20'
```

Daily report:

```bash
curl -sS http://127.0.0.1:8000/reports/daily
```

## How To Ask Codex

Examples:

```text
用 ashare-data-sync 检查今天数据是否完整
```

```text
用 ashare-sector-review 分析医药是不是补涨机会，和 PCB/CPO 对比
```

```text
用 ashare-daily-review 生成今天的主线轮动复盘和明日预案
```

```text
用 ashare-backtest-check 检查当前补涨策略有没有未来函数风险
```

Codex skills live in `.agents/skills`. They should use the service endpoints,
read `/data/quality`, and clearly state timestamps, reasons, risks, trigger
conditions, invalidation conditions, and confidence.

## Reading Strategy Output

Key concepts:

- `strong_mainline`: sector has strong evidence across money flow, heat, and
  continuity.
- `candidate_mainline`: sector is improving but still needs confirmation.
- `rotation_hotspot`: visible heat but incomplete confirmation.
- `weak`: not enough evidence for mainline treatment.
- `rush_accumulation_score`: derived score from fund-flow rank, amount rank,
  price strength, and net-inflow-to-amount ratio.

Leaders are for observing sector strength only. Do not automatically treat
leaders as buy candidates.

## Risk Rules

Use these rules whenever interpreting the system:

- If data is stale, mocked, delayed, or incomplete, lower confidence.
- Dragon-tiger rows are after-close evidence and should not be used as intraday
  signals.
- A catch-up candidate must have trigger and invalidation conditions.
- Do not chase rear stocks during climax or retreat phases.
- If the market is in retreat, observation or empty-position bias should be the
  default research conclusion.

## Testing

Run tests after changing providers, storage, strategy logic, API handlers, MCP
tools, or skills:

```bash
pytest
```

Expected current suite:

```text
16 passed
```

## Troubleshooting

Service down:

```bash
./scripts/rich-service.sh restart
./scripts/rich-service.sh logs
```

Eastmoney money-flow sync fails:

- Refresh `EASTMONEY_COOKIE` from a browser session.
- Configure `EASTMONEY_PROXY` if the server IP is blocked.
- Re-run `instock-em`.

No catch-up candidates:

- Check `/data/quality` first.
- If quality is high, an empty list usually means current filters found no
  qualified candidate, not that the database is empty.
- Inspect `/data/features/latest` and `/strategy/mainlines` for context.

Low confidence:

- Check which blocker is present in `/data/quality`.
- Re-sync the missing data layer.
- Do not override confidence unless another verified current source is cited.
