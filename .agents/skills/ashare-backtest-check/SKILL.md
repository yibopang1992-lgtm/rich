---
name: ashare-backtest-check
description: Use when the user asks to backtest, validate, tune, or evaluate the rich A-share rotation/catch-up strategy, including mainline score, catch-up pool, derived features, limit-up events, dragon-tiger after-close events, win rate, next-day premium, 2-3 day return, drawdown, and future-leakage checks.
---

# A-share Backtest Check

Use this skill to validate the rotation and catch-up strategy against historical data.

When evaluating strategy validity, read
`../references/yangjia-emotion-framework.md` and segment results by emotion
cycle, leader state, climax-next-day risk, and position-cap rules.

## Required Workflow

1. Check which historical data exists in SQLite.
2. Run the available backtest endpoint or script.
3. Inspect whether the data source is mock, Baostock, Eastmoney money flow, AKShare events, or derived features.
4. Segment performance by emotion cycle when data allows: 冰点, 启动, 发酵, 高潮, 分歧, 退潮.
5. Separate intraday-available signals from after-close signals.
6. Report metrics, red-line violations, and data gaps.
7. Check future-leakage risks before interpreting results.

## Commands

```bash
curl -sS http://9.134.113.106:8000/data/status
curl -sS http://9.134.113.106:8000/backtest/daily
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

## Future Leakage Rules

- 龙虎榜 can only be used after close.
- AKShare limit-up pool first/last seal time can be used only at or after the observed timestamp.
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
