---
name: ashare-daily-review
description: Use when the user asks for the A-share daily review, market mainline report, next-day plan, rotation/catch-up strategy report, or a fixed-format trading research report from the rich A-share rotation agent using real SQLite data, Eastmoney money flow, AKShare limit-up/dragon-tiger events, derived stock features, and Yangjia emotion rules.
---

# A-share Daily Review

Generate a daily research report for the A-share short-term rotation and catch-up strategy.

Before producing the report, read `../references/yangjia-emotion-framework.md`
and apply it to cycle classification, leader validation, catch-up filtering,
position bias, and red-line checks.

## Required Workflow

1. Check service health, SQLite status, and `/data/quality`.
2. Sync current realtime quotes for user-specified symbols or watchlists when needed.
3. Call strategy, feature, money-flow, limit-up, dragon-tiger, and rush-accumulation endpoints.
4. Classify the current market emotion cycle: 冰点, 启动, 发酵, 高潮, 分歧, or 退潮.
5. Separate evidence into: live/realtime, after-close, derived feature, and missing-data buckets.
6. If sector/fund-flow, limit-up, event, or feature data is missing, mark the affected conclusion lower confidence.
7. Produce a fixed-format report with timestamps, sources, reasons, risks, triggers, invalidation conditions, and position bias.

If Sina sector data is present but Eastmoney/Tushare fund-flow data is missing, classify it as “行情热度证据充分，资金流证据不足” rather than “没有数据”.

## Required Risk Checks

Add these checks to every rotation/catch-up review:

- **Emotion-cycle gate**: if the market is 退潮, output 空仓/观察 as the primary plan. If 高潮, favor reducing exposure and reject rear-stock chasing. If 发酵, focus only on confirmed mainline/core and qualified catch-up.
- **Money-making/loss-making effect check**: infer buy opportunity from赚钱效应 and sell risk from亏钱效应. Do not let a single stock override broad market emotion.
- **Prior-session climax check**: identify sectors that had broad limit-up
  ladders, 20cm symbols, high-amount leaders, or news-driven one-day consensus.
  Mark the next session as a potential profit-taking window unless leaders
  keep premium.
- **Leader premium check**: for each active sector, observe sentiment leaders,
  trend anchors, and mid-cap anchors. If leaders fail to hold VWAP, lose
  previous-day premium, or break down together, reject rear catch-up trades.
- **Rear weakness check**: if a rear candidate lagged during a sector-wide
  surge, label it as "low recognition" and do not rank it above stronger
  same-sector rear names.
- **Sector purity check**: separate pure sector candidates from adjacent-theme
  candidates. For example, panel/consumer electronics names should not be
  counted as pure PCB catch-up candidates unless the report explicitly uses a
  broader "AI hardware/electronics" bucket.
- **New hotspot diversion check**: if a new sector shows stronger breadth,
  limit-up count, or intraday heat while yesterday's hot sector rear stocks
  weaken, classify the old sector as marginal-fund losing and suspend catch-up
  selection.
- **Amount-heat caveat**: when money-flow rows are missing, label candidates as
  "amount-heat candidates", not fund-flow-confirmed candidates.
- **Position-cap check**: cap position bias by cycle phase and confidence. Missing fund-flow or only amount-heat evidence cannot support a high-confidence heavy-position conclusion.

## Commands

```bash
curl -sS http://9.134.113.106:8000/health
curl -sS http://9.134.113.106:8000/data/status
curl -sS http://9.134.113.106:8000/data/quality
curl -sS http://9.134.113.106:8000/market/overview
curl -sS 'http://9.134.113.106:8000/data/moneyflow/latest?limit=50'
curl -sS 'http://9.134.113.106:8000/data/features/latest?limit=50'
curl -sS 'http://9.134.113.106:8000/data/events/limit-up/latest?limit=50'
curl -sS 'http://9.134.113.106:8000/data/events/latest?event_type=dragon_tiger&limit=50'
curl -sS 'http://9.134.113.106:8000/data/events/latest?event_type=rush_accumulation&limit=50'
curl -sS http://9.134.113.106:8000/reports/daily
```

If the service is stale or down:

```bash
ssh yibopang@9.134.113.106 'cd /data/home/yibopang/rich && ./scripts/rich-service.sh restart'
```

## Report Template

```markdown
# A股资金轮动报告

## 一、市场状态

- 数据时间：
- 数据源：
- 数据完整性：
- 情绪周期：
- 市场情绪：
- 主线板块：
- 候选主线：
- 退潮板块：
- 资金风格：
- 板块是否切换：
- 置信度：
- 仓位倾向：

## 二、养家五项复盘

| 指标 | 观察 | 结论 |
|---|---|---|

## 三、真实数据证据

| 数据层 | 时间 | 行数/样本 | 用途 | 限制 |
|---|---|---:|---|---|

## 四、主线周期

| 板块 | 主线评分 | 情绪阶段 | 持续性 | 风险 |
|---|---:|---|---|---|

## 五、龙头观察

| 股票 | 角色 | 当日状态 | 用途 |
|---|---|---|---|

说明：龙头只用于判断板块，不自动视为买入候选。

## 六、补涨候选

| 排名 | 股票 | 评分 | 逻辑 | 触发条件 | 放弃条件 |
|---|---|---:|---|---|---|

## 七、事件与抢筹观察

| 类型 | 股票/板块 | 证据 | 风险 |
|---|---|---|---|

## 八、风险标的

- 已加速：
- 高位兑现：
- 资金背离：
- 板块退潮：
- 公告风险：
- 高潮次日兑现：
- 后排弱证伪：
- 板块纯度不足：
- 新热点分流：
- 退潮/高潮红线：

## 九、明日预案

### 剧本 A：主线延续
### 剧本 B：高开分化
### 剧本 C：资金切换
### 剧本 D：高潮次日兑现

## 十、数据缺口

-
```

## Safety

- This is research only, not investment advice.
- Do not promise returns.
- Do not output large undifferentiated stock lists.
- If data is incomplete, explicitly lower confidence.
