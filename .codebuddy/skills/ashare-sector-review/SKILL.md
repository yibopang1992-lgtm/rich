---
name: ashare-sector-review
description: Use when the user asks whether an A-share sector such as 医药, PCB, CPO, AI算力, 半导体, 消费电子, or another theme is a mainline, rotation candidate, catch-up opportunity, climax risk, or fading sector, using the rich service's SQLite data, Eastmoney fund flow, AKShare events, derived features, and Yangjia emotion rules.
---

# A-share Sector Review

Use this skill to answer sector-level questions such as “医药是不是补涨机会” or “PCB 还在主线吗”.

When the request involves mainline status, catch-up, leader validation,
climax/fading risk, or trade plan, read
`../references/yangjia-emotion-framework.md` before giving the conclusion.
When the request involves limit-up diffusion, sector linkage, dragon/follower
classification, or high-low catch-up switching, also read
`../references/limitup-linkage-framework.md` and
`../references/high-low-switch-framework.md`.

## Required Workflow

1. First refresh the fixed remote service with `POST /data/sync?provider=instock-em&trade_date=YYYY-MM-DD` using the current Asia/Shanghai trading date.
2. Check the service, data status, and `/data/quality`.
3. Read `/strategy/mainlines`, `/strategy/rotation`, `/strategy/limitup-linkage`, `/strategy/high-low-switch`, `/data/moneyflow/latest`, `/data/features/latest`, and relevant `/data/events/*` endpoints.
4. Sync or read realtime quotes if the user names specific symbols.
5. Classify the sector within the current emotion cycle: 冰点, 启动, 发酵, 高潮, 分歧, or 退潮.
6. Compare the target sector against current strongest and weakest sectors, not in isolation.
7. If money-flow, limit-up, feature, or event data is missing/stale, clearly downgrade confidence.
8. Output conclusion, evidence, trigger conditions, invalidation conditions, position bias, and data gaps.

## Commands

Check data:

```bash
curl -sS -X POST 'http://9.134.113.106:8000/data/sync?provider=instock-em&trade_date=YYYY-MM-DD'
curl -sS http://9.134.113.106:8000/health
curl -sS http://9.134.113.106:8000/data/status
curl -sS http://9.134.113.106:8000/data/quality
curl -sS 'http://9.134.113.106:8000/data/realtime/latest?limit=20'
curl -sS 'http://9.134.113.106:8000/data/moneyflow/latest?limit=50'
curl -sS 'http://9.134.113.106:8000/data/features/latest?limit=50'
curl -sS 'http://9.134.113.106:8000/data/events/limit-up/latest?limit=50'
curl -sS 'http://9.134.113.106:8000/data/events/latest?event_type=dragon_tiger&limit=50'
curl -sS 'http://9.134.113.106:8000/data/events/latest?event_type=rush_accumulation&limit=50'
```

Try service strategy endpoints:

```bash
curl -sS http://9.134.113.106:8000/strategy/mainlines
curl -sS http://9.134.113.106:8000/strategy/catchup-candidates
curl -sS http://9.134.113.106:8000/strategy/limitup-linkage
curl -sS http://9.134.113.106:8000/strategy/high-low-switch
curl -sS http://9.134.113.106:8000/strategy/rotation
```

If the service reports `mock_fallback` or has no `sector_snapshot_rows`, do not rely on service mainline output as live evidence.
If `sector_snapshot_rows` is nonzero but fund-flow fields are zero, treat service rankings as price/amount heat rankings, not full fund-flow confirmation.
If `/data/quality` caps `analysis_confidence_ceiling` at `medium-low`, do not output a high-confidence sector conclusion unless external verified fund-flow evidence is added and cited.
If `limit_up_event_rows=0`, do not make a strong emotion-cycle or ladder conclusion.
If `stock_feature_rows=0`, do not make a strong rush-accumulation or catch-up-pool conclusion.
If `dragon_tiger_event_rows=0`, say after-close institutional/seat evidence is missing; do not lower intraday money-flow conclusions solely for that.

## Sector Review Logic

Classify a sector using this hierarchy:

- **Strong mainline**: sector fund flow leads, turnover expands, breadth is high, limit-up ladder exists, leaders and mid-cap anchors confirm.
- **Candidate mainline**: strong one-day or two-day improvement, but continuity or internal ladder is not fully confirmed.
- **Catch-up opportunity**: old mainline remains strong or just diffused; second-tier stocks in related sectors begin receiving funds while not yet accelerated.
- **Rotation hotspot**: price action is visible, but funding or breadth evidence is incomplete.
- **Climax risk**: many stocks surge together, leaders accelerate, rear stocks are pulled rapidly, next-day consistency risk rises.
- **Fading**: leaders break down, fund flow turns negative, rear stocks lose premium, new sector absorbs funds.

Apply the linkage and high-low-switch overlays:

- **Sector limit-up linkage**: same-sector limit-up count >= 3 confirms short-term force, but only one leader may be marked; all others are follower or diffusion observations.
- **Leader-only observation**: leader symbols validate sector strength and next-day premium, not automatic buy eligibility.
- **High-low switch**: valid only when the mainline remains recognized while high/mid-tier symbols diverge; prefer absolute low-position candidates and reject middle-tier acceleration.
- **Middle-tier veto**: candidates with accelerated recent gains but no leader status should be rejected even if their score is high.
- **Climax and diffusion risk**: when linkage is too broad or 20cm symbols accelerate together, mark the next session as a profit-taking observation window unless leaders hold premium.

Map the classification to emotion-cycle action:

- 冰点: only observe or tiny test if a reversal signal appears.
- 启动: confirm new leader; first divergence is better than chasing consistency.
- 发酵: mainline/core can be prioritized; qualified catch-up may be considered.
- 高潮: sell consistency, reduce exposure, reject rear acceleration.
- 分歧: only keep true leader/core; downgrade weak followers.
- 退潮: no catch-up; output observation/empty-position bias.

## Catch-up Risk Rules

When evaluating catch-up opportunities, especially after a strong sector day,
apply these checks before naming candidates:

- **Climax-next-day rule**: if the sector had many limit-up symbols, 20cm
  symbols, or several high-amount leaders surging together in the prior
  session, classify the next session as a profit-taking observation window by
  default. Downgrade all catch-up candidates unless leaders continue to show
  premium.
- **Leader-premium confirmation**: catch-up is valid only if sentiment leaders,
  trend anchors, and mid-cap anchors remain strong. If leaders open weak, fail
  to hold VWAP, lose prior-day premium, or break down together, rear candidates
  should be rejected or moved to observation.
- **Rear-stock weakness invalidation**: if a proposed catch-up stock was weak
  on the sector climax day while leaders were very strong, do not treat it as
  a preferred catch-up candidate the next day. Weakness during a broad sector
  surge often means low fund recognition.
- **Sector purity filter**: do not mix broad adjacent themes into a narrow
  sector catch-up pool. For example, 京东方A can be part of a panel/consumer
  electronics/broad hardware review, but it should not be labeled as a pure PCB
  catch-up candidate. Prefer names whose business and market recognition match
  the reviewed sector.
- **New-hotspot diversion rule**: if a new sector develops stronger breadth,
  more limit-up symbols, or higher intraday heat while the reviewed sector rear
  stocks weaken, classify the reviewed sector as losing marginal funds and
  suspend catch-up selection.
- **Amount-heat limitation**: high turnover alone is not enough. If money-flow
  data is missing, call the result "amount-heat catch-up" and require stronger
  trigger/invalidation conditions.

For a catch-up candidate to pass, it should have: sector purity, adequate
liquidity, non-accelerated recent gains, leader premium confirmation, and
relative strength versus other rear stocks in the same sector.
For a high-low-switch candidate to pass, it should additionally avoid the
middle tier, remain low-position, and require post-divergence confirmation
such as weak-to-strong sealing or sustained VWAP strength.

Apply Yangjia veto rules:

- If the sector is in 退潮, all catch-up candidates fail.
- If the sector is in 高潮 or 高潮次日, rear candidates need exceptional leader
  premium; otherwise mark as profit-taking risk.
- If the only evidence is amount heat, call it "amount-heat catch-up" and do
  not raise confidence above medium-low without external confirmation.
- If a candidate makes the trader passive under plausible next-session
  scenarios, reject it even if the score is high.

## Data Needed

For each sector, try to gather:

- Sector涨跌幅, 成交额, 成交额增量.
- 主力净流入, 超大单/大单净流入.
- 上涨家数, 下跌家数, 涨停数量.
- 派生特征: 成交额排名, 主力净流入排名, 净流入/成交额, 抢筹分.
- 事件: 涨停池, 涨停行业/原因提示, 龙虎榜上榜原因和净买额.
- 龙头/中军/20cm核心/补涨股.
- 最近 3/5 日涨幅 and whether candidates are already accelerated.
- News catalyst and risk events.
- Previous-session climax signals: number of limit-up/20cm symbols, leader
  acceleration, high-amount leaders, and whether rear stocks lagged.
- Next-session confirmation: leader premium, VWAP holding, breadth retention,
  and whether another sector is absorbing funds.

## Output Template

```markdown
## 结论

- 板块状态：
- 情绪周期：
- 是否补涨机会：
- 置信度：
- 仓位倾向：

## 证据

| 维度 | 观察 | 含义 |
|---|---|---|

## 板块联动与高低切换

| 信号 | 观察 | 结论 |
|---|---|---|

## 候选方向

| 股票/细分 | 角色 | 触发条件 | 放弃条件 |
|---|---|---|---|

## 风险

- 

## 仓位与红线

- 

## 触发条件

- 

## 失效条件

- 

## 数据缺口

- 
```

Never say a stock “必涨”. Treat leaders as observation symbols, not automatic buy candidates.
