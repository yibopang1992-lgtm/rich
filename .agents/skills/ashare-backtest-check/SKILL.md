---
name: ashare-backtest-check
description: Use when the user asks to backtest, validate, tune, or evaluate the rich A-share rotation/catch-up strategy, including mainline score, catch-up pool, derived features, limit-up events, dragon-tiger after-close events, win rate, next-day premium, 2-3 day return, drawdown, and future-leakage checks.
---

# A-share Backtest Check

Use this skill to validate the rotation and catch-up strategy against historical data.

When evaluating strategy validity, read
`../references/yangjia-emotion-framework.md` and segment results by emotion
cycle, leader state, climax-next-day risk, and position-cap rules.
For limit-up linkage or high-low-switch validation, also read
`../references/limitup-linkage-framework.md` and
`../references/high-low-switch-framework.md`.

## Required Workflow

1. Check which historical data exists in SQLite.
2. Run the available backtest endpoint or script.
3. Inspect whether the data source is mock, Baostock, Eastmoney money flow, AKShare events, or derived features.
4. Segment performance by emotion cycle when data allows: 冰点, 启动, 发酵, 高潮, 分歧, 退潮.
5. Segment limit-up linkage samples by same-sector limit-up count, market limit-up count, leader premium, and next-day profit-taking risk.
6. Segment high-low-switch samples by leader divergence, middle-tier weakness, low-position evidence, and whether candidates avoided the middle tier.
7. Separate intraday-available signals from after-close signals.
8. Report metrics, red-line violations, and data gaps.
9. Check future-leakage risks before interpreting results.

## Commands

```bash
curl -sS http://9.134.113.106:8000/data/status
curl -sS http://9.134.113.106:8000/backtest/daily
curl -sS http://9.134.113.106:8000/strategy/limitup-linkage
curl -sS http://9.134.113.106:8000/strategy/high-low-switch
```

For local test runs:

```bash
cd /Users/yibopang/Documents/rich
.venv/bin/pytest
```

## Metrics

Always include:

- Sample size.
- Win rate.
- Average return.
- Median return.
- Payoff ratio.
- Max drawdown.
- Stop-loss trigger rate if available.
- Market environment and sector stage split if available.
- Emotion-cycle split if available.
- Results after applying red-line filters: no 退潮 trades, no rear-stock chasing after 高潮, no high-confidence position when data quality is capped.
- Linkage samples: sector limit-up count >= 3, one-leader classification, next-day premium/stop-loss behavior.
- High-low-switch samples: low-position filter pass rate, middle-tier veto effect, leader-breakdown dependency.

## Future Leakage Rules

- 龙虎榜 can only be used after close.
- AKShare limit-up pool first/last seal time can be used only at or after the observed timestamp.
- Same-sector limit-up count can be used only after the relevant limit-up event time or after-close, depending on signal definition.
- Leader classification by final封板/连板 can be used after the observed timestamp only; after-close classification cannot be used for intraday entry backtests.
- Derived rush-accumulation features are valid only after the underlying quote and money-flow timestamp.
- Announcements must use actual publish time.
- Do not use future industry classifications.
- Do not use future sector membership revisions for past dates.
- Intraday signals must only use data available at that timestamp.

## Output Template

```markdown
## 回测结论

- 是否可用：
- 样本数量：
- 核心指标：
- 最大风险：
- 情绪周期有效性：
- 红线过滤效果：
- 板块联动有效性：
- 高低切换有效性：

## 指标表

| 指标 | 数值 | 说明 |
|---|---:|---|

## 数据质量

- 

## 情绪周期分层

| 周期 | 样本 | 胜率 | 平均收益 | 最大回撤 | 结论 |
|---|---:|---:|---:|---:|---|

## 下一步调参

- 
```
