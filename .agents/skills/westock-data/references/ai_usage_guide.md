# WeStock Data - AI 深度参考指南

> **定位**：本文档提供详细的数据格式参考、分析模板。命令列表和基本用法请参见 [SKILL.md](../SKILL.md)。
> 完整分析场景示例请参见 [scenarios-guide.md](./scenarios-guide.md)。

---

## 一、输出格式

命令执行后输出 **Markdown 表格**，AI 直接从表格中读取数据进行分析。

**单股查询**：输出一个 Markdown 表格，每列对应一个数据字段。

**批量查询**：输出批量摘要行 + 每个 symbol 的独立表格。

**查询失败**：输出 JSON 格式的错误信息（含 `success: false` 和 `error` 对象）。



---

## 二、各命令数据格式

### 实时行情（`westock quote`）

输出表格列（共通字段，三市场均返回）：
`code | name | price | prevClose | open | high | low | volume | amount | change | changePercent | turnoverRate | volumeRatio | rangePct | avgPrice | peRatio | peFwd | peLyr | pbRatio | dividendRatioTtm | totalMarketCap | circulatingMarketCap | totalShares | floatShares | high52week | low52week | chg5d | chg10d | chg20d | chg60d | chgYtd`

#### 市场差异化字段（按 `market_type` 区分）

| 字段 | 说明 | A股 | 港股 | 美股 |
|------|------|:---:|:---:|:---:|
| `price_ceiling` | 涨停价（元） | ✅ | — | — |
| `price_floor` | 跌停价（元） | ✅ | — | — |
| `inner_volume` | 内盘（主动卖出量） | ✅ | — | — |
| `outer_volume` | 外盘（主动买入量） | ✅ | — | — |
| `wb_ratio` | 委比（%） | ✅ | ✅ | — |
| `lot` | 每手股数 | — | ✅ | — |
| `adr_conversion_price` | ADR 换算价（港元） | — | ✅ | — |
| `relative_hk_stock_price` | 相对港股价格 | — | ✅ | — |
| `relative_hk_stock_chg_pct` | 相对港股涨跌幅（%） | — | ✅ | — |
| `dividend_ttm` | 股息 TTM（元） | — | ✅ | ✅ |
| `eps_ttm` | 每股收益 TTM（元） | — | — | ✅ |
| `pre_market_price` | 盘前价（美元） | — | — | ✅ |
| `pre_market_price_chg` | 盘前涨跌额 | — | — | ✅ |
| `pre_market_price_chg_pct` | 盘前涨跌幅（%） | — | — | ✅ |
| `post_market_price` | 盘后价（美元） | — | — | ✅ |
| `post_market_price_chg` | 盘后涨跌额 | — | — | ✅ |
| `post_market_price_chg_pct` | 盘后涨跌幅（%） | — | — | ✅ |

> `market_type` 取值：`1`=沪A，`51`=深A，`62`=北交所，`100`=港股，`200`=美股。
> 差异字段仅在对应市场返回，其他市场该字段为 `undefined`，分析时需先判断。

#### 可转债维度字段（仅可转债代码返回，来源 `Kzz_*`）

可转债（沪 `sh11xxxx`/`sh13xxxx`、深 `sz12xxxx`）走 `westock quote` 时，在上述通用 + A股交易机制字段之外，额外返回以下转债维度字段；单只查询以竖排「项目/内容」表展示（规模换算为亿元、日期规整为 `YYYY-MM-DD`，缺失字段自动跳过）。

| 字段 | 说明 |
|------|------|
| `bond_equity_value` | 转股价值 |
| `bond_pure_value` | 纯债价值 |
| `bond_equity_premium` | 转股溢价率（%） |
| `bond_pure_premium` | 纯债溢价率（%） |
| `bond_double_low` | 双低 |
| `bond_rating` | 转债评级 |
| `bond_total_size` | 总规模（万元） |
| `bond_undue_size` | 剩余规模（万元） |
| `bond_term` | 期限（年） |
| `bond_undue_term` | 剩余期限（年） |
| `bond_due_date` | 到期日期 |
| `bond_ytm` | 到期收益率（%） |
| `bond_convertible` | 是否转股 |
| `bond_convert_price` | 转股价（元） |
| `bond_convert_start_date` | 转股起始日 |
| `bond_redeem_price_due` | 到期赎回价（元） |
| `bond_redeem_price_compulsory` | 强制赎回价（元） |
| `bond_redeem_price_trigger` | 强赎触发价（元） |
| `bond_buyback_price_trigger` | 回售触发价（元） |
| `bond_buyback_start_date` | 回售起始日 |
| `bond_stock_pb` | 正股 PB |
| `bond_stock_code` | 正股代码 |

> 行情接口**不返回债券简称**（`name` 为空）；可交换债及临近到期老券可能缺失部分 `Kzz_*` 字段，分析时需判空。完整发行要素/条款/现金流用 `bond`。

### 财务三大表（`westock finance`）

默认输出**核心字段窄表**（`--fields core`，★ 标记字段）；`--fields all` 恢复全字段。

> **字段后缀**：`_Q` = 单季度值，`TTM` = 过去 12 月滚动值。无后缀 = 累计值。
> ⚠️ **易混淆**：`OperatingRevenue`（营业收入）≠ `OperatingProfit`（营业利润），二者数值差异大，切勿看错列。
> **比率类指标直读披露值**：ROE / ROA / 毛利率等比率类字段，优先直读报表返回值，**禁止**用「净利润 / 净资产」自行拼算后当作报表值。

#### ★ 常用中文指标 → 英文字段 快速映射

> 用户用中文问某个指标时，先查此表确定所在表 + 字段名，再发对应 `--type` 请求。

| 中文名称 | 所在表 | 英文字段 |
|---------|-------|---------|
| 营业总收入 | income | `TotalOperatingRevenue` |
| 营业收入 | income | `OperatingRevenue` |
| 营业成本 | income | `OperatingCost` |
| 营业利润 | income | `OperatingProfit` |
| 利润总额 | income | `TotalProfit` |
| 归母净利润 | income | `NPParentCompanyOwners` |
| 扣非净利润 | income | `NPDeductNonRecurringPL` |
| 研发费用 | income | `RAndD` |
| 毛利率 | income | `GrossIncomeRatio` |
| 净利率 | income | `NetProfitRatio` |
| ROE | income | `ROEWeighted` / `ROE` |
| ROA | income | `ROA` |
| 营收增长率 | income | `TORGrowRate` |
| 净利润增长率 | income | `NPParentCompanyYOY` |
| 基本每股收益 | income | `BasicEPS` |
| 营业收入TTM | income | `OperatingRevenueTTM` |
| 总资产 | balance | `TotalAssets` |
| 总负债 | balance | `TotalLiability` |
| 净资产(股东权益) | balance | `TotalShareholderEquity` |
| 资产负债率 | balance | `DebtAssetsRatio` |
| 流动比率 | balance | `CurrentRatio` |
| 速动比率 | balance | `QuickRatio` |
| 经营现金流净额 | cashflow | `NetOperateCashFlow` |
| 投资现金流净额 | cashflow | `NetInvestCashFlow` |
| 筹资现金流净额 | cashflow | `NetFinanceCashFlow` |
| 自由现金流(公司) | cashflow | `FCFF` |

> **使用规则**：用户只问营收/利润/ROE 等利润表指标 → `--type income`；只问资产/负债 → `--type balance`；只问现金流 → `--type cashflow`。**只在用户明确要求"三大报表""全面分析"时才不加 `--type`。**

#### A 股利润表（income）字段

| 字段 | 说明 |
|------|------|
| ★ `InfoPublDate` | 报告发布日 |
| `EnterpriseType` | 企业类型 |
| ★ `TotalOperatingRevenue` | 营业总收入（含其他业务收入） |
| `TotalOperatingCost` | 营业总成本 |
| ★ `OperatingRevenue` | 营业收入（主营业务） |
| `OperatingCost` | 营业成本 |
| `OperatingPayout` | 营业税金及附加 |
| `TotalAdminExpense` | 管理费用合计 |
| `OperatingExpense` | 销售费用 |
| ★ `RAndD` | 研发费用 |
| `FinancialExpense` | 财务费用 |
| ★ `OperatingProfit` | 营业利润（= 营业总收入 - 营业支出） |
| ★ `TotalProfit` | 利润总额 |
| ★ `NPParentCompanyOwners` | 归母净利润 |
| `BasicEPS` | 基本每股收益 |
| `DilutedEPS` | 稀释每股收益 |
| `PremiumsEarned` | 已赚保费（保险业） |
| `NetProxySecuIncome` | 代理买卖证券净收入（证券业） |
| `NetSubIssueSecuIncome` | 证券承销净收入（证券业） |
| `NetTrustIncome` | 信托业务净收入（信托业） |
| `_Q` 后缀 | 同名字段的单季度值（如 `OperatingRevenue_Q`） |
| `TotalOperatingRevenueTTM` | 营业总收入 TTM |
| `TotalOperatingCostTTM` | 营业总成本 TTM |
| `OperatingRevenueTTM` | 营业收入 TTM |
| `OperatingCostTTM` | 营业成本 TTM |
| `OperatingPayoutTTM` | 营业税金及附加 TTM |
| `GrossProfitTTM` | 毛利润 TTM |
| `OperatingProfitTTM` | 营业利润 TTM |
| ★ `NPParentCompanyOwnersTTM` | 归母净利润 TTM |

#### A 股资产负债表（balance）字段

| 字段 | 说明 |
|------|------|
| ★ `InfoPublDate` | 报告发布日 |
| `EnterpriseType` | 企业类型 |
| `CashEquivalents` | 货币资金 |
| `BillAccReceivable` | 应收票据及应收账款 |
| `Inventories` | 存货 |
| `OtherCurrentAssets` | 其他流动资产 |
| ★ `TotalCurrentAssets` | 流动资产合计 |
| `LongtermEquityInvest` | 长期股权投资 |
| `TotalFixedAsset` | 固定资产合计 |
| `IntangibleAssets` | 无形资产 |
| `GoodWill` | 商誉 |
| `TotalNonCurrentAssets` | 非流动资产合计 |
| `TotalLiabilities` | 总负债（含衍生） |
| `ShortTermLoan` | 短期借款 |
| `NotAccountsPayable` | 应付票据及应付账款 |
| `TotalCurrentLiability` | 流动负债合计 |
| `LongtermLoan` | 长期借款 |
| `TotalNonCurrentLiability` | 非流动负债合计 |
| ★ `TotalLiability` | 负债合计 |
| `PaidInCapital` | 实收资本（股本） |
| `CapitalReserveFund` | 资本公积 |
| `SurplusReserveFund` | 盈余公积 |
| `RetainedProfit` | 未分配利润 |
| `SEWithoutMI` | 归母股东权益 |
| ★ `TotalShareholderEquity` | 股东权益合计 |
| `TradingAssets` | 交易性金融资产 |
| `DerivativeAssets` | 衍生金融资产 |
| `ReceivablesFin` | 应收款项融资 |
| `AdvancePayment` | 预付款项 |
| `OtherReceivableED` | 其他应收款 |
| `BoughtSellbackAssets` | 买入返售金融资产 |
| `ContractAssets` | 合同资产 |
| `NonCurrentAssetIn1Year` | 一年内到期的非流动资产 |
| `LongtermReceivableAccount` | 长期应收款 |
| `InvestmentProperty` | 投资性房地产 |
| `TConstruInProcess` | 在建工程 |
| `OtherNonCurrentAssets` | 其他非流动资产 |
| `TradingLiability` | 交易性金融负债 |
| `OtherCurrentLiability` | 其他流动负债 |
| `AdvanceReceipts` | 预收款项 |
| `ContractLiability` | 合同负债 |
| `SalariesPayable` | 应付职工薪酬 |
| `OtherPayableED` | 其他应付款 |
| `NonCurrentLiabilityIn1Year` | 一年内到期的非流动负债 |
| `LTAccountPayableTotal` | 长期应付款合计 |
| `BondsPayable` | 应付债券 |
| `LeaseLiabilities` | 租赁负债 |
| `OtherNonCurrentLiability` | 其他非流动负债 |
| `OtherEquityinstruments` | 其他权益工具 |
| `Deposit` | 吸收存款（银行） |
| `LoanAndAdvance` | 发放贷款及垫款（银行） |
| `WorkingCapital` | 营运资金 |
| `InterestBearDebt` | 有息负债 |
| `EBIT` | 息税前利润 |
| `NPDeductNonRecurringPL` | 扣非净利润 |

#### A 股现金流量表（cashflow）字段

| 字段 | 说明 |
|------|------|
| ★ `InfoPublDate` | 报告发布日 |
| `EnterpriseType` | 企业类型 |
| `GoodsSaleServiceRenderCash` | 销售商品提供劳务收到的现金 |
| ★ `NetOperateCashFlow` | 经营活动现金流净额 |
| ★ `NetInvestCashFlow` | 投资活动现金流净额 |
| ★ `NetFinanceCashFlow` | 筹资活动现金流净额 |
| ★ `FCFF` | 自由现金流（企业） |
| ★ `FCFE` | 自由现金流（股权） |
| `_Q` 后缀 | 同名单季度值 |
| `NetOperateCashFlowTTM` | 经营活动现金流净额 TTM |
| `NetInvestCashFlowTTM` | 投资活动现金流净额 TTM |
| `NetFinanceCashFlowTTM` | 筹资活动现金流净额 TTM |
| `NetCashFlowTTM` | 现金净增加额 TTM |

#### 港股利润表（income）字段

| 字段 | 说明 |
|------|------|
| ★ `InfoPublDate` | 报告发布日 |
| `EnterpriseType` | 企业类型 |
| `CurrencyType` / `CurrencyUnit` | 币种 / 货币单位 |
| `PeriodMark` / `ReportType` | 报告期标识 / 类型 |
| ★ `OperatingIncome` | 营业收入 |
| `OperExpenses` | 营业支出 |
| `SalesExpense` | 销售费用 |
| `DevelopmentExpense` | 研发费用 |
| `AdministrationExpense` | 管理费用 |
| `DepDividerSale` | 折旧与摊销 |
| `AssetDeValue` | 资产减值损失 |
| ★ `OperatingProfit` | 营业利润 |
| `FinancialCost` | 财务成本 |
| `EarningBeforeTax` | 税前利润 |
| `Tax` | 所得税 |
| `AftaxProfitfcbusi` / `AftaxProfitfncbusi` | 税后本业务/非本业务利润 |
| ★ `EarningAfterTax` | 税后利润 |
| ★ `ProfitToShareholders` | 归股东利润 |
| `ProfitToMinority` | 少数股东利润 |
| ★ `BasicEPS` / `EPS` | 基本每股收益 |
| `NetAssetPS` | 每股净资产 |
| `OperCashFlowPs` / `CashflowPs` | 每股经营现金流 / 每股现金流 |
| `MainincomePs` | 每股主营收入 |
| ★ `RoeWeighted` | 加权平均净资产收益率（ROE） |
| ★ `ROA` | 总资产收益率 |
| ★ `GrossIncomeRatio` | 毛利率 |
| `OperatingProfitRatio` | 营业利润率 |
| `NetProfitRatio` | 净利率 |
| `EarningBeforeTaxRatio` | 税前利润率 |
| `Operprofittotp` / `Taxtotp` / `Opercashtotp` | 营业利润/税/经营现金流占营收比 |
| `DebtAssetsRatio` | 资产负债率 |
| `EquityMultipler` | 权益乘数 |
| `DebtEquityRatio` | 产权比率 |
| `CurrentRatio` / `QuickRatio` | 流动比率 / 速动比率 |
| `InventoryTRate` / `TotalAssetTRate` / `ArTRate` | 存货/总资产/应收账款周转率 |
| `InventoryTDays` / `ArTDays` | 存货/应收账款周转天数 |
| ★ `OperatingRevenueGr1y` | 营收同比增速 |
| `GrossIncomeGr1y` / `OperProfitGr1y` / `NetProfitGr1y` | 毛利/营业利润/净利润同比增速 |
| ★ `NpParentCompanyGr1y` | 归母净利同比增速 |
| `TotalAssetGr1y` / `BasicEpsGr1y` | 总资产/EPS 同比增速 |
| `OperatingRevenueGr3y` / `NetProfitGr3y` / `NpParentCompanyGr3y` | 营收/净利/归母净利 3 年复合增速 |
| `MainOperIncomeIndustry` / `MainOperIncomeProduct` / `MainOperIncomeRegion` | 主营收入行业/产品/地区分布 |

#### 美股利润表（income）字段

| 字段 | 说明 |
|------|------|
| `DisclosureCurrency` / `ShowCurrency` | 披露币种 / 展示币种 |
| `FinancialYear` | 财年 |
| ★ `Sales_Q` | 营业收入（单季度） |
| `Cogs_Q` | 营业成本（单季度） |
| ★ `GrossIncome_Q` | 毛利润（单季度） |
| `SaleGeneralAdminExp_Q` | 销售管理费用（单季度） |
| `OtherOperatingExp_Q` | 其他营业费用（单季度） |
| ★ `EBIT_Q` | 息税前利润（单季度） |
| `NonOperatingIncome_Q` | 非经营收入（单季度） |
| `InterestExpense_Q` | 利息费用（单季度） |
| `PretaxXordCharge_Q` | 税前特殊项目（单季度） |
| ★ `PretaxIncome_Q` | 税前利润（单季度） |
| `IncomeTax_Q` | 所得税（单季度） |
| `AffiliateCompIncome_Q` | 联营企业收益（单季度） |
| `OtherAdjustment_Q` | 其他调整（单季度） |
| `ConsolidateNetIncome_Q` | 合并净利润（单季度） |
| `MinorityInterestExp_Q` | 少数股东损益（单季度） |
| ★ `NetIncome_Q` | 净利润（单季度） |
| `PreferedStockDiv_Q` | 优先股股息（单季度） |
| `BasicNetIncome_Q` | 基本净利润（单季度） |
| ★ `BasicEPS_Q` / `DilutedEPS_Q` | 基本/稀释每股收益（单季度） |
| `NetIncomeAfterXord_Q` | 扣特殊项目后净利润（单季度） |
| `EBITDA_Q` | 息税折旧摊销前利润（单季度） |
| ★ `GrossMargin_Q` | 毛利率（单季度） |
| ★ `NetMargin_Q` | 净利率（单季度） |
| `OperatingMargin_Q` | 营业利润率（单季度） |
| `PretaxMargin_Q` | 税前利润率（单季度） |
| `SalesPs_Q` | 每股销售额（单季度） |
| 无后缀（如 `Sales`） | 累计值（美股数据源通常仅返回季度值 `_Q`，累计值可能为空） |

#### 美股资产负债表（balance）字段

| 字段 | 说明 |
|------|------|
| `DisclosureCurrency` / `ShowCurrency` | 披露币种 / 展示币种 |
| `FinancialYear` | 财年 |
| `CashShortTermInvestment` | 现金及短期投资 |
| `ShortTermReceivable` | 短期应收 |
| `Inventory` | 存货 |
| `OtherCurrentAssets` | 其他流动资产 |
| `CurrentAssets` | 流动资产合计 |
| `PPE` | 固定资产 |
| `AdvancedInvestment` | 预付投资 |
| `LongTermReceivables` | 长期应收 |
| `IntangibleAssets` | 无形资产 |
| `DeferredTaxAssets` | 递延所得税资产 |
| `OtherAssets` | 其他资产 |
| ★ `TotalAssets` | 总资产 |
| `ShortTermDebt` | 短期借款 |
| `AccountsPayable` | 应付账款 |
| `TaxPayable` | 应交税费 |
| `OtherCurrentLiabilities` | 其他流动负债 |
| `CurrentLiabilities` | 流动负债合计 |
| `LongTermDebt` | 长期借款 |
| `ProvisionRisk` | 风险准备金 |
| `DeferredTaxLiabilities` | 递延所得税负债 |
| `OtherLiabilities` | 其他负债 |
| ★ `TotalLiabilities` | 总负债 |
| `NonEquityReserve` | 非权益储备 |
| `PreferedStockValue` | 优先股价值 |
| `CommonStockEquity` | 普通股权益 |
| ★ `ShareHolderEquity` | 股东权益 |
| `CumMinorityInterest` | 累计少数股东权益 |
| ★ `TotalEquity` | 权益总额 |
| `TotalLiabilitiesAndEquity` | 负债与权益合计 |
| `BPS` / `TangiableBPS` | 每股净资产 / 每股有形净资产 |
| `CurrentRatio` / `QuickRatio` | 流动比率 / 速动比率 |
| ★ `LiabilityToAsset` | 资产负债率 |
| ★ `ROE` | 净资产收益率 |
| ★ `ROA` | 总资产收益率 |
| `AssetTurnover` | 总资产周转率 |
| `BusinessDist` / `RegionDist` | 业务分布 / 地区分布 |

#### 美股现金流量表（cashflow）字段

> 美股按季度披露，数据源仅返回 `_Q` 后缀字段，累计值字段为空。

| 字段 | 说明 |
|------|------|
| ★ `CFO_Q` | 经营活动现金流净额（单季度） |
| ★ `Capex_Q` | 资本支出（单季度） |
| ★ `CFI_Q` | 投资活动现金流净额（单季度） |
| ★ `CFF_Q` | 筹资活动现金流净额（单季度） |
| ★ `FreeCF_Q` | 自由现金流（单季度） |
| `NetIncomeCF_Q` | 净利润（单季度） |
| `DepCF_Q` | 折旧摊销（单季度） |
| `WorkingCapitalChg_Q` | 营运资金变动（单季度） |
| `DivCF_Q` / `StockChgCF_Q` / `DebtCF_Q` | 股息/回购/借款现金流（单季度） |

> ★ = `--fields core` 默认输出的核心字段；其余字段需 `--fields all` 或 `--raw` 获取。

### K线（`westock kline`）

输出表格列：`date | open | last | high | low | volume | amount | exchange | change_pct`

> `change_pct` = 当日涨跌幅（%），= (今收 - 前收) / 前收 × 100。

> K线数值为原始数值，AI 在分析时自行进行单位换算

> ⚠️ **周期支持差异**：**美股指数**（`us.DJI`/`us.IXIC`/`us.SPX` 等）**仅支持日K**（`--period day`），不支持分钟K和周/月/季/年K。

### 资金数据

#### 港股资金流向（`westock fund flow hk<代码>`）

| 字段 | 单位 | 说明 |
|------|------|------|
| `TotalNetFlow` | 港元 | 总净流入 |
| `MainNetFlow` | 港元 | 主力净流入 |
| `RetailNetFlow` | 港元 | 散户净流入 |

#### 港股卖空数据（`westock fund short hk<代码>`）

| 字段 | 单位 | 说明 |
|------|------|------|
| `ShortShares` | 股 | 卖空股数 |
| `ShortAmount` | 港元 | 卖空金额 |
| `ShortRatio` | % | 卖空比率（卖空股数/成交量） |

#### A股资金流向（`westock fund flow sh/sz<代码>`）

| 字段 | 单位 | 说明 |
|------|------|------|
| `MainNetFlow` | 元 | 主力净流入（正=流入，负=流出）|
| `JumboNetFlow` | 元 | 超大单净流入 |
| `BlockNetFlow` | 元 | 大单净流入 |
| `MidNetFlow` | 元 | 中单净流入 |
| `SmallNetFlow` | 元 | 小单净流入 |
| `MainInFlow` | 元 | 主力流入 |
| `MainOutFlow` | 元 | 主力流出 |
| `RetailInFlow` | 元 | 散户流入 |
| `RetailOutFlow` | 元 | 散户流出 |

> 扩展字段（历史数据）：`MainNetFlow5D`/`MainNetFlow10D`/`MainNetFlow20D`（5/10/20日主力净流入）、`MainInflowRank`（流入排名）、`MainInflowCircRate`（占流通盘比例）、`MainInflowIndustryRank`（行业排名）

#### 美股卖空数据（`westock fund short us<代码>`）

> ⚠️ **美股限制**：美股不支持 `westock fund flow`（资金流向），只支持 `westock fund short`（卖空数据）

| 字段 | 单位 | 说明 |
|------|------|------|
| `ShortRatio` | % | 卖空比率（卖空股数/流通股数） |
| `ShortShares` | 股 | 卖空股数 |
| `ShortRecoverDays` | 天 | 回补天数（卖空股数/日均成交量） |

#### 北向季度持仓（`westock fund north-holding <股票代码>`）

> 同时查询 `north_holding_detail_cur_quarterly`（最新季）与 `prev_quarterly`（次新季），合并为一张表输出。

| 字段 | 单位 | 说明 |
|------|------|------|
| `EndDate` | YYYYMMDD | 披露截止日 |
| `HoldingCap` | 元 | 持股市值 |
| `HoldingRatio` | % | 持股比例 |
| `HoldingShares` | 股 | 持股数量 |
| `CapChgQ` / `CapChgY` | 元 | 持股市值季/年变动 |

> ⚠️ 与日度 `westock fund flow` 不同：`westock north-holding` 是**季度披露**口径的全市场持仓明细。

#### 港股南下资金持仓（`westock fund south-holding <港股代码>`）

> 通过 `stock_quote_snapshot` 的 `LgtHoldInfo` 字段解析，支持批量。

| 字段 | 单位 | 说明 |
|------|------|------|
| `LgtHoldRatio` | % | 南下资金持有比例 |
| `LgtCapChgDaily` | 港元 | 日变动市值 |
| `LgtShareChgDaily` | 股 | 日变动份额 |
| `LgtCapChgQuarterly` | 港元 | 季变动市值 |
| `LgtShareChgQuarterly` | 股 | 季变动份额 |

#### 申万行业北向资金持仓分布（`westock fund north-holding <板块代码>`）

> 根据 `sw1_/sw2_/sw3_` 或 `pt…` 板块代码，查询 `north_holding_statis_sw*` 并按行业名称过滤。仅支持申万行业，不支持概念/地域板块。

| 字段 | 单位 | 说明 |
|------|------|------|
| `SW` | — | 申万行业名称 |
| `HoldingCap` | 元 | 行业北向持股市值 |
| `CapChgQ` / `CapChgY` | 元 | 持股市值季/年变动 |

### 机构评级（`westock rating`）

> 自 [Unreleased] 起重构为 **3 段精简结构**，A 股/港股/美股按市场自动分发，输出一致。

#### 段 1：目标价 & 当前评级摘要

输出表格列：`code | name | targetPriceAvg | targetPriceMax | targetPriceMin | upsideAvg | upsideMax | currentBuyCnt | currentIncCnt | currentHoldCnt | currentDecCnt | currentSellCnt | totalRatingCnt | forecastInstitutions`

- `targetPriceAvg/Max/Min`：目标价的平均/最高/最低值
- `upsideAvg/Max`：上涨空间百分比（基于当前价）
- `currentBuyCnt/IncCnt/...`：当前评级分布

#### 段 2：评级月度趋势统计（近 7 个月）

输出表格按月分布：`month | buyCnt | incCnt | holdCnt | decCnt | sellCnt`，反映买入/增持/中性/减持/卖出 5 档评级在最近 7 个月的变化趋势。

#### 段 3：价格 vs 目标价历史走势对比

输出表格列：`date | closePrice | targetPriceAvg`，逐日对比股价与机构目标价均值。

> **分析要点**：
> - 段 1 看共识强度（买入家数 vs 卖出家数）和上涨空间（upside）
> - 段 2 看评级动量（最近 1-2 个月评级是否上调/下调）
> - 段 3 看股价是否已 price-in 机构预期，或仍有低估空间

### 一致预期（`westock consensus`）

按代码前缀自动分发：A 股走 `queryCNConsensusForecast`，港股走 `queryHKConsensusForecast`，美股暂不支持。

#### A 股

输出表格，列含 `code | name | targetPrice`，以及 `forecasts` 数组中的 `year | revenue | netProfit | eps | pe | pb | ps | revenueYoy | netProfitYoy | institutionCnt`

#### 港股

按"时间维度"展示（行=季度，列=各指标）。顶层字段：`code | name | quarters`。

##### `quarters` 主表（按 `period` 升序）

| 字段 | 下游字段 | 说明 |
|------|---------|------|
| `period` | `ForecastPeriod` | 预测报告期（如 `2025Q4`、`2026Q1`） |
| `epsForecast` | `EPSForecast` | 每股收益-预测 |
| `revenueForecast` | `RevenueForecast` | 营业收入-预测（亿港币） |
| `netProfitForecast` | `NetProfitForecast` | 净利润-预测（亿港币） |
| `peRatioForecast` | `PERatioForecast` | 市盈率-预测 |
| `psRatioForecast` | `PSRatioForecast` | 市销率-预测 |
| `roeForecast` | `ROEForecast` | 净资产收益率-预测 |

> 列顺序固定为 EPS → 营收 → 净利润 → PE → PS → ROE（与微证券页面 tab 顺序一致）；某指标在该季度没有预测时该列为 `undefined`/缺省。

**分析要点**：目标价 vs 当前价（上涨空间）、EPS增速（盈利确定性）、PE走势（估值消化）、机构数（共识可信度）

---

### ESG 评级（`westock esg`）

查询中证 / 聚源两套 ESG 字母档评级。**与 `westock rating`（券商研报评级）和 `westock score`（量化评分）不同**；仅 A 股（`sh`/`sz`/`bj`）。

**命令用法**：

```bash
westock esg sh600519
westock esg sh600519,sz000651 --source csi

```

**输出格式**：
- 单股：按来源分行（中证 / 聚源），列含 `评级 | 发布日 | 截止日 | 变动`
- 批量：宽表 `中证评级 | 聚源评级 | …`

**字段（归一化后）**：

| 字段 | 下游字段 | 说明 |
|------|---------|------|
| `grade` | `EsgGrade` | 当前评级（中证：AAA/BBB…；聚源：A/B/C…，**不可跨源比高低**） |
| `endDate` | `EndDate` | 数据截止日 |
| `publDate` | `InfoPublDate` | 评级发布日 |
| `prevGrade` | （chg 清单，字段名待首条非空样本确认） | 上次评级 |

> **数据说明**：中证覆盖约 900 只，聚源覆盖更广（约 5000+），单股可能仅有聚源数据。

---

### 脱水研报（`westock dehydrated`）

通过 `research_report_list_get` 获取脱水研报摘要列表，包含机构调研和行业风口两种类型。

**命令用法**：
```bash
westock dehydrated                         # 脱水研报列表（默认返回10条）
westock dehydrated --limit 20 --offset 20    # 自定义分页
westock dehydrated detail <研报ID>         # 研报详情

```

**输出格式**：
- 列表：Markdown 表格，含 `id | title | summary | pub_time | institution`
- 详情：Markdown 格式，含关联标的、投资要点、正文（HTML）

> 研报ID 从列表的 `id` 字段获取，用于查询详情。

---

### 技术指标（`westock technical`）

> **指标**：MA_5/10/20/60/120/250、MACD/DIF/DEA、KDJ_K/D/J、RSI_6/12/24、BOLL_UPPER/MID/LOWER。

#### 用法与输出

输出表格列：`code | date | period | closePrice | ma.MA_5 | ma.MA_10 | ... | macd.DIF | macd.DEA | macd.MACD | kdj.KDJ_K | ...`

嵌套对象（ma/macd/kdj/rsi/boll）的字段会展平为 `分组.字段名` 格式。`period` 字段标识 K 线周期（day/week/month 等）。不指定 `--start/--end` 时按默认返回最新一期全量指标；在截面模式（不传 `--date`/`--start`/`--end`）下附加 `--limit N` 表示"最近 N 期"（自动按区间拉取后取末尾 N 条）；指定 `--start/--end` 后按区间逐交易日返回，`--limit` 控制条数（默认 2000）。支持 A 股/港股/美股 个股及指数/ETF/板块（与 `kline` 同源；分钟 K 的标的限制同 `kline`：除美股指数外均支持）。

**典型用法**：
- `westock technical sh600000` — 日K最新一期指标
- `westock technical sh600000 --date 2026-03-01` — 指定日期
- `westock technical sh600000 --period week` — 周K技术指标
- `westock technical sh600000 --start 2026-02-01 --end 2026-03-01 --limit 30` — 日K区间
- `westock technical sh600000 --period month --start 2025-01-01 --end 2026-07-10` — 月K序列
- `westock technical sh600519,sz000001` — 多股对比

#### 解读要点

- **MA**：MA_5/10/20/60/120/250，短期均线在长期均线之上为多头排列
- **MACD**：DIF 上穿 DEA 为金叉（买入信号），下穿为死叉
- **KDJ**：K > 80 超买区，K < 20 超卖区
- **RSI**：RSI_6 > 70 超买，RSI_6 < 30 超卖
- **BOLL**：价格突破上轨/下轨为超买/超卖信号
- **周期差异**：周K/月K 技术指标反映中期/长期趋势；分钟K反映短期波动

### 筹码成本（`westock chip`）

#### 截面

输出表格列：`code | name | date | closePrice | chipProfitRate | chipAvgCost | chipConcentration90 | chipConcentration70`

#### 历史区间

输出表格，每行一个交易日，列名同上。

**解读**：盈利率>80%=获利盘占优；收盘价>平均成本=整体盈利；集中度越低=筹码越集中（主力控盘可能）

### 市场/指数/板块（`market`）

#### 截面（`MarketQuoteData`）关键字段

| 字段 | 说明 |
|------|------|
| `closePrice`/`changePct` | 收盘价/涨跌幅 |
| `chg5D`/`chg10D`/`chg20D`/`chg60D`/`chgYtd` | 多日涨跌幅(%) |
| `advancingCount`/`decliningCount` | 上涨/下跌家数 |
| `mainNetFlow`/`jumboNetFlow`/`blockNetFlow` | 主力/超大单/大单净流入（沪深，元）|
| `midNetFlow`/`smallNetFlow` | 中单/小单净流入（沪深，元）|
| `totalNetFlow`/`retailNetFlow` | 总/散户净流入（港股，港元）|

> ⚠️ 美股不支持资金流向字段，仅支持 `westock fund short`（卖空数据）

#### 历史区间

输出表格，每行一个交易日，含 `date | closePrice | changePct | mainNetFlow | ...`

### 行业经营数据（`westock sector oper`）

查询各行业经营指标的历史序列数据，覆盖29个申万一级行业。数据包括价格、产量、销量、收入等经营指标。

**输出格式**：
- 按行业分组输出
- 每个行业输出一个 Markdown 表格，列含 `指标代码 | 指标名称 | 数据点 | 最新日期 | 最新值`

**返回字段说明**：

| 字段 | 说明 |
|------|------|
| `指标代码` | 经营指标的唯一代码（如 `F_COAL_INV_COAL_QHD_D`） |
| `指标名称` | 经营指标的中文名称（如"库存:煤炭:秦皇岛港:日"） |
| `数据点` | 该指标可用的历史数据点数量 |
| `最新日期` | 最新数据点的日期（格式：`YYYYMMDD`） |
| `最新值` | 最新数据点的数值 |

**使用示例**：

```bash
westock sector oper 煤炭                  # 查询煤炭行业经营数据
westock sector oper 煤炭 --date 2026-06-15  # 指定日期
westock sector oper --list                # 列出所有支持经营数据的行业

```

**支持行业**（共29个）：
传媒、电力设备、电子、房地产、纺织服饰、非银金融、钢铁、公用事业、国防军工、环保、机械设备、基础化工、计算机、家用电器、建筑材料、建筑装饰、交通运输、煤炭、美容护理、农林牧渔、汽车、商贸零售、社会服务、石油石化、食品饮料、通信、医药生物、银行、有色金属

**参数说明**：
- `<行业>`：支持中文名称（如"煤炭"）或标识（如 `coal`），**不要**传板块代码（如 `pt02021291`）
- `--list`：列出所有支持经营数据的行业
- `--date`：查询日期 YYYY-MM-DD（默认今天）

---

### 板块估值（`westock sector valuation`）

查询单个或多个板块的 PE/PB/PS/PCF/DIV 及**历史百分位**（相对自身历史区间）。**与 `westock market-overview --type valuation`（中证全指大盘估值）不同**；与 `westock sector forecast`（未来一致预期估值）互补。

**命令用法**：

```bash
westock sector valuation pt01801080
westock sector valuation pt01801080,pt01801081
westock sector valuation pt01801080 --start 2026-01-01 --end 2026-06-25

```

**输出格式**：
- 截面：Markdown 表，每行一个板块；支持多板块逗号批量对比
- 历史（`--start` + `--end`）：按 `EndDate` 升序的时间序列；**每次仅支持单板块**

**核心字段**（下游原始字段名，CLI 直接输出）：

| 字段 | 说明 |
|------|------|
| `code` / `name` | 板块代码 / 名称 |
| `EndDate` | 数据截止日（`YYYYMMDD`） |
| `PeTTM` / `PeTTMPct` | 市盈率 TTM / 历史百分位（**%**，越高表示相对历史越贵） |
| `PbLF` / `PbLFPct` | 市净率 LF / 历史百分位 |
| `PsTTM` / `PsTTMPct` | 市销率 TTM / 历史百分位 |
| `PcfTTM` / `PcfTTMPct` | 市现率 TTM / 历史百分位 |
| `DivTTM` / `DivTTMPct` | 股息率 TTM / 历史百分位 |
| `*PrevM/Q/W/Y` | 各指标相对上月/上季/上周/去年的变动 |

> **参数**：传**板块代码**（`pt*`）。支持申万行业及聚源概念/地域/产业。先用 `westock search --type sector` 获取代码。

**分析要点**：
- `PeTTMPct` / `PbLFPct` 等百分位：判断行业相对自身历史估值高低
- 与 `westock sector forecast` 的 `pe`/`peg` 对照：当前估值 vs 预期盈利增速是否匹配
- 与 `westock sector finance` 的 `roeTTM` 对照：盈利质量能否支撑估值

---

### 行业未来盈利预测（`westock sector forecast`）

查询申万一级/二级行业的机构一致预期盈利路径（未来 3 年）。**与 `westock consensus`（个股一致预期）不同**：无目标价/EPS，数值为**行业聚合**口径。

**命令用法**：

```bash
westock sector forecast pt01801780              # 申万一级银行
westock sector forecast pt01801081          # 申万二级半导体
westock sector forecast pt01801780 --date 2026-06-25

```

**输出格式**：
- 按行业分组，每组一个 Markdown 表（行=预测年度，按 `year` 升序）
- 顶层含行业名、`code`（pt 代码）、`swLevel`、`forecastDate`

**`forecasts` 主表字段**（列顺序：营收/利润 → 增速 → 估值）：

| 字段 | 下游字段 | 说明 |
|------|---------|------|
| `year` | `ConYear` | 一致预期年度 |
| `revenue` | `ConOr` | 一致预期营业收入（**万元**，行业加总） |
| `netProfit` | `ConNp` | 一致预期归母净利润（**万元**，行业加总） |
| `netAssets` | `ConNa` | 一致预期归母净资产（**万元**，行业加总） |
| `revenueYoy` | `ConOrYoy` | 营业收入同比增速（**%**） |
| `netProfitYoy` | `ConNpYoy` | 归母净利润同比增速（**%**） |
| `netProfitCagr2Y` | `ConNpYoy2Y` | 归母净利润两年复合增长率（**%**） |
| `pe` | `ConPe` | 一致预期市盈率（倍） |
| `pb` | `ConPb` | 一致预期市净率（倍） |
| `ps` | `ConPs` | 一致预期市销率（倍） |
| `roe` | `ConRoe` | 一致预期 ROE（**%**） |
| `peg` | `ConPeg` | 一致预期 PEG（**%**，清单口径，非常见 PEG 倍数） |

> **参数**：仅支持申万一级/二级板块代码（`pt*`）。**不支持**申万三级、聚源地域/产业/风格概念（如 `pt03001176` 海南地域概念会明确报错）。先用 `westock search --type sector` 获取申万行业代码。

**分析要点**：
- `netProfitYoy` / `netProfitCagr2Y`：盈利增速路径与确定性
- `pe` + `peg`：估值水平与成长性匹配（注意 `peg` 为 % 口径）
- `roe`：行业整体盈利能力
- 与 `westock sector valuation`（当前估值百分位）对照：预期利润增速能否消化估值

---

### 申万行业财务指标（`westock sector finance`）

查询申万行业成份股聚合的财报 TTM 指标。**与个股 `westock finance`（三大表）不同**；与 `westock sector forecast`（未来一致预期）互补。

**命令用法**：

```bash
westock sector finance pt01801780
westock sector finance pt01801780,pt01801080
westock sector finance pt01801780 --start 2020-01-01 --end 2026-03-31

```

**输出格式**：
- 默认：多行业合并为一张截面表（含 `name | code | swLevel`）
- `--start` + `--end`：按 `endDate` 升序的历史序列（同期业内变动）

**核心字段（归一化后）**：

| 字段 | 下游字段 | 说明 |
|------|---------|------|
| `endDate` | `EndDate` | 财报期（`YYYYMMDD`） |
| `revenueTTM` | `RevenueTTM` | 营业收入 TTM（**万元**，行业加总） |
| `netProfitTTM` | `NetProfitTTM` | 归母净利润 TTM（**万元**） |
| `netProfitYoY` | `NetProfitYoY` | 净利同比增速（**%**） |
| `roeTTM` | `RoeTTM` | ROE TTM（**%**） |
| `debtRatio` | `DebtRatio` | 资产负债率（**%**） |
| `grossProfitRatioTTM` | `GrossProfitRatioTTM` | 毛利率 TTM（%） |
| `netProfitRatioTTM` | `NetProftRatioTTM` | 净利率 TTM（%，下游字段有拼写 typo） |

> **参数**：支持 sw1/sw2/sw3；聚源概念/地域会明确报错。历史查询需同时指定 `--start` 与 `--end`（与 `westock sector valuation` 一致）。

**分析要点**：`netProfitYoY`+`roeTTM` 看盈利质量；`debtRatio` 看杠杆；配合 `westock sector valuation` / `westock sector forecast` 构成基本面→估值→预期链。

---

### 市场总览（`westock market-overview`，A 股大盘画像）

8 个子类（type）归并到单一入口，提供 A 股大盘"宏观体检"。来源是 8 个 `market_statis_*` 后端清单。

| type | 中文 | 说明 |
|------|------|------|
| `summary` | 画像总评（默认） | 14 维度得分 + 状态文案（估值/情绪/技术/趋势/风格轮动/股市规模/宏观情绪/北向资金/两融情绪/PMI 等） |
| `trade` | 三大指数收盘统计 | 上证/深证/创业板 + 成交额多周期均值（5D/20D/60D） |
| `interval` | 三大指数多周期涨跌 | 5D/20D/60D/250D 涨跌 + 52 周高低 |
| `westock technical` | 大盘技术面 | MACD / KDJ / RSI / BOLL / MA |
| `updown` | A 股涨跌停 / 红绿盘 | 涨停/跌停家数 + 红绿盘比 + 创新高/新低家数 |
| `margin` | 两融余额变动 | 两融余额 + 多周期变动 |
| `valuation` | 估值百分位 | 中证全指 PE/PB/PS + 历史百分位 |
| `rotation` | 风格轮动 | 沪深300 / 中证1000 / 成长 / 价值 板块轮动 |

**用法**：
```
westock market-overview                    # 默认 summary（最常用，给 LLM 做"今日市场点评"）
westock market-overview --type trade       # 单 type
westock market-overview --type technical,updown   # 多 type 一次拉
westock market-overview --type all         # 全量 8 个
westock market-overview list               # 列出所有 type
```

**summary 14 维度** 每个维度含：`name`（维度名）、`westock score`（0~100 得分）、`status`（状态文案，如"估值偏高"、"情绪乐观"）。**这是给 AI 做今日市场点评最直接的入口** —— 一次调用即可得到"估值/情绪/技术/趋势/风格"5 大类共 14 个维度的状态画像。

### 排行数据（`rank`）

输出 Markdown 表格，列头为字段中文标签（来自 `list_data_schema`），如"市盈率TTM(倍)"、"股息率TTM(%)"等。

**返回信息**：
- 清单名称、查询日期、总条数
- 排序字段（中文标签）和方向（升序/降序）
- 分页信息（offset/limit/hasMore）
- 每行含股票代码、名称及各指标字段

**参数说明**：

| 参数 | 说明 | 可选值 |
|------|------|--------|
| 清单代码 | 排行清单代码，如 `fin_valuation` | 见 SKILL.md 排行清单表 |
| --limit | 每页条数，默认20，最大50 | 数字 |
| --offset | 偏移量，默认0 | 数字 |
| --desc | 排序方向，默认true（降序） | `true`/`false` |

> 字段中文标签由 API 的 `list_data_schema` 自动解析，无需手动映射

---

### 市场/大盘资讯（`westock news list` + 指数代码）

与个股新闻同一命令，传**指数代码**。多指数逗号批量，按标的分段展示。常用代码见 [commands.md](./commands.md) 资讯章节对照表。

> 全市场**热文榜**用 `westock hot news`，与指数关联资讯不同。

### 分红数据（`westock dividend/calendar`）

输出表格，字段因市场不同：

- **A股**：`reportEndDate | dividendFlag | procedure | dividendType | proposalSn | rightRegDate | exDiviDate | bonusShareRatio | tranAddShareRatio | cashDiviRMB | totalCashDiviComRMB | dividendPlan`
- **港股**：`reportEndDate | exDiviDate | cashPayDate | cashDivPerShare | specialDivPerShare | totalCashDivi | dividendPlan`
- **美股**：`exDivDate | regDate | payDate | dividendCurrency | dividend | dividendPlan`

> 美股可能额外包含 `splitInfo`（拆合股信息）

**参数说明**：
- 默认查询最近分红数据
- `--years N`：查询近N年分红历史（如 `--years 5`、`--years 10`）
- `--all`：返回所有记录（含未实施分红方案），默认只返回已实施分红的记录
- 返回记录按报告期/除权日降序排列（最新的在前）

### 财报披露日历（`westock disclosure`）

输出表格，字段因市场不同：

- **A股**：`reportEndDate | disclosureEndDate | disclosureDate | disclosureDesc`
- **港股**：`reportEndDate | disclosureDesc`
- **美股**：`reportEndDate | disclosureDate | disclosureDesc`

### 命令参数详细说明

#### news list（资讯列表）

| 参数位置 | 说明 | 可选值 |
|---------|------|--------|
| 代码 | 标的代码，支持逗号分隔批量；**市场资讯传指数代码**（见上文对照表） | - |
| 每页数量 | 返回条数，默认20 | 数字 |
| 类型 | 资讯类型 | `0`=公告，`1`=研报，`2`=新闻，`3`=全部（默认） |

#### notice list（公告列表）

| 参数位置 | 说明 | 可选值 |
|---------|------|--------|
| 代码 | 股票代码，支持逗号分隔批量 | - |
| 类型 | 公告类型 | `0`=全部（默认），`1`=财务，`2`=配股，`3`=增发，`4`=股权变动，`5`=重大事项，`6`=风险，`7`=其他 |

#### report list（研报列表）

| 参数位置 | 说明 | 可选值 |
|---------|------|--------|
| 代码 | 标的代码：个股（如 sh600000）或行业/板块（如 pt01801080），支持逗号分隔批量 | - |
| 页码 | 页码，默认1 | 数字，从1开始 |
| 每页数量 | 每页返回条数，默认20 | 数字 |
| 类型 | 研报类型 | `0`=全部（默认），`1`=研报，`2`=业绩会 |

#### calendar（投资日历 — 个股事件日历）

查询指定日期有哪些股票发生分红/财报/IPO/停复牌/会议/解禁/增发事件，按事件类型分组输出。
宏观经济日历请使用 `westock macro indicator cn_calendar_future|cn_calendar_hist`。

| 参数 | 说明 | 可选值 |
|---------|------|--------|
| `--date` | 查询日期 | `YYYY-MM-DD`，默认今天 |
| `--event` | 事件类型过滤 | `financial_report`/`dividend`/`ipo`/`trading_halt`/`meeting`/`lockup_release`/`rights_issue`/`all`，支持逗号分隔多类型，默认 `all` |
| `--market` | 市场 | `hs`（沪深）/ `hk`（港股）/ `us`（美股），默认 `hs` |
| `--limit` | 返回条数 | 数字，默认 10 |
| `--offset` | 偏移量 | 数字，默认 0 |

#### index constituent（指数成份股）

| 参数 | 说明 |
|------|------|
| 代码 | 指数代码，支持逗号分隔批量。A 股（如 sh000300）、港股（如 hkHSI）自动路由 |
| --list | 查询指数清单 |
| --search 关键词 | 搜索指数 |

#### connect（沪深港通成份股 / 北向 · 陆股通）

> 沪深港通成份股名单（标的池），不是资金流量数据；如需资金买卖方向请用 `westock fund flow` / `westock fund margin` / `westock fund block`。

| 参数 | 说明 | 可选值 |
|---------|------|--------|
| `--exchange` | 交易所（必填） | `sh`=沪股通，`sz`=深股通 |
| `--limit` | 每页条数，默认 50，最多 100 | 数字 |
| `--offset` | 偏移量（用于翻页） | 数字 |

---

## 三、货币单位处理

> ⚠️ **重要**：港股财报返回港元/美元，美股返回美元，展示时**必须**标注正确货币单位

**港股**：检查 `CurrencyType`（"港币"/"美元"/"人民币"）和 `CurrencyUnit` 字段
- ✅ 正确：`营业收入：832.3亿港元`
- ❌ 错误：`营业收入：¥832.3亿`

**跨期对比注意**：同比/环比增长率可能受汇率换算影响，展示时建议添加说明：`"注：同比数据可能受汇率波动影响"`

---

## 四、单位换算

| 数据类型 | 原始单位 | 转换 |
|---------|---------|------|
| 成交量 | 手 | ÷10000=万手 |
| 成交额/市值/主力资金 | 元 | ÷100000000=亿元 |
| 港股金额 | 港元 | ÷100000000=亿港元 |
| 美股金额 | 美元 | ÷100000000=亿美元 |
| 卖空数量 | 股 | ÷1000000=百万股 |

---

## 四点五、ETF 数据字段

> **子命令**（必填）：`westock profile` 档案+资产配置 | `overview` 运作概览 | `holdings` 申赎清单+重仓涨跌 | `nav` 净值时序。

### ETF 档案（`westock etf profile`）

| 字段 | 说明 |
|------|------|
| `trackIndexCode/Name` | 跟踪指数（清单 `etf_track_index`） |
| `establishDate` | 成立日期 |
| `trusteeInstitution` | 托管人 |
| `purchaseStatus` / `redemptionStatus` | 申购/赎回状态 |
| `investScope` / `investStrategy` | 投资范围/策略 |
| `isTPlus0` | 是否支持 T+0 |
| `subscriptionFee` / `managementFee` / `custodyFee` / `serviceFee` | 认购/管理/托管/销售服务费率(%) |
| `managers` | 基金经理履历（snapshot `EtfManagerInfo`） |
| `classification` | 4 级分类（清单 `etf_classification`）：`primary`/`secondary`/`tertiary`/`quaternary`/`memo` |
| `managerHistory` | 经理历史（清单 `etf_manager`）：`current`/`first`/`longest`/`history` |
| `allocation` | 资产配置（snapshot `EtfAssetAllocation` + 清单规模） |

### ETF 运作概览（`westock etf overview`）

| 字段 | 说明 |
|------|------|
| `totalAsset` / `etfSize` | 总资产/规模及周月季年变化 |
| `chgPct` / `chgPct5D` / `chgPct20D` / `chgPct60D` / `chgPct52W` / `chgPctYtd` | 涨跌幅（多周期） |
| `etfDisc` / `etfDiscAvg*` | 溢折率及同指数均值 |
| `turnoverRate` / `turnoverValue` / `etfTurnover*` | 换手率/成交额 |
| `ytdMaxDrawdown` / `maxDrawdown1M/3M/6M/1Y/3Y` | 最大回撤（snapshot `EtfPerformance`） |
| `etfInFlow` / `etfInFlow*Avg` | 净申购及周月季年均值 |
| `peTtm` / `pb` / `psTtm` / `pcfTtm` / `peg` / `roe` / `divTtm` | 估值绝对值 |
| `peTtmPct` / `pbPct` / … | 估值历史百分位 |

### ETF 持仓（`westock etf holdings`）

| 字段 | 说明 |
|------|------|
| `holdings` | 申赎清单成分股（清单 `etf_prlist_{code}` 优先，snapshot 兜底） |
| `topStockChanges` | 重仓股涨跌：`code`/`name`/`ratio`/`rate`/`change` |

### ETF 净值时序（`westock etf nav`）

| 字段 | 说明 |
|------|------|
| `date` | 交易日 |
| `nav` | 单位净值（优先 `EtfNav`，缺失时回退 `ClosePrice`） |
| `closePrice` | 场内收盘价（可能与 nav 不同） |
| `navChange` | 净值涨跌额（相邻两日 `EtfNav` 差分；区间内首日不返回） |
| `navChangePct` | 净值涨跌幅(%)（同上） |

> ⚠️ `nav` 的涨跌由客户端按 `EtfNav` 差分计算，**不是** `ChangePrice`（收盘价涨跌）。查场内 OHLC 用 `westock kline`，不是 `westock etf nav`。

---

## 四点六、公司回购字段

### 回购数据（`westock buyback`）

**港股字段**：
| 字段 | 说明 |
|------|------|
| `BuybackShares` | 回购股份(股) |
| `BuybackMoney` | 回购金额(港元) |
| `BuybackPrice` | 回购均价(港元) |
| `BuybackCumMoney` | 本轮回购累计金额(港元) |

**A股字段**（BuybackAttach 数组）：
| 字段 | 说明 |
|------|------|
| `BuybackFunds` | 本次回购资金(元) |
| `BuybackSum` | 本次回购数量(股) |
| `BuybackPrice` | 本次回购均价(元) |

> 回购数据按日期降序排列，仅返回有回购记录的交易日。

---

### 风险事件（`westock risk`）

#### 特别处理（ST）

| 字段 | 说明 |
|------|------|
| `type` | 特别处理类型（ST/\*ST/SST/撤销ST） |
| `explain` | 事项描述 |
| `date` | 信息发布日期 |
| `riskLevel` | 风险等级：high（高风险）、medium（中风险）、low（低风险） |

#### 股权质押

| 字段 | 说明 |
|------|------|
| `date` | 股权质押披露截止日期 |
| `floatPledgedVolume` | 无限售股份质押数量（万股） |
| `nonFloatPledgedVolume` | 有限售股份质押数量（万股） |
| `pledgeNum` | 质押笔数 |
| `pledgeRatio` | 质押比例 |
| `totalPledge` | 质押数量（万股） |
| `riskLevel` | 风险等级：high（质押比例≥50%）、medium（30%-50%）、low（<30%） |

#### 解禁信息

| 字段 | 说明 |
|------|------|
| `initialInfoPublDate` | 解禁信息首次发布日期 |
| `infoPublDate` | 解禁信息最新发布日期 |
| `estimateActual` | 解禁日期类型 |
| `shareHolderName` | 解禁股东名 |
| `changeReason` | 解禁原因 |
| `restrictedCondition` | 限售条件说明 |
| `newAFloatListed` | 新增可售A股 |
| `actualFloatListedShares` | 实际上市流通数量 |
| `riskLevel` | 风险等级：high、medium、low |

#### 诉讼仲裁

| 字段 | 说明 |
|------|------|
| `date` | 诉讼仲裁最新公告日期 |
| `actionDesc` | 行为描述 |
| `subjectMatterStat` | 案由简称 |
| `latestSuitSum` | 涉诉金额（元） |
| `eventSubject` | 事件主体 |
| `eventSubjectRole` | 事件主体在诉讼中的角色 |
| `plaintiff` | 诉讼仲裁原告 |
| `defendant` | 诉讼仲裁被告 |
| `plaintiffAssociation` | 原告与上市公司关联关系 |
| `defendantAssociation` | 被告与上市公司关联关系 |
| `caseStatus` | 仲裁状态 |
| `firstInstanceStatus` | 一审状态 |
| `secondInstanceStatus` | 二审状态 |
| `sppStatus` | 最高院监督状态 |
| `adjudgementStatus` | 判决执行状态 |
| `riskLevel` | 风险等级：high（涉诉金额>1亿或作为被告）、medium（>1000万）、low |

#### 增发信息

| 字段 | 说明 |
|------|------|
| `issueType` | 增发类别 |
| `eventProcedure` | 事件进程 |
| `advanceDate` | 预案公告日期 |
| `smDeciPublDate` | 决案公告日期 |
| `intentLetterPublDate` | 意向书发布日期 |
| `prospectusPublDate` | 新股说明书发布日期 |
| `sacApprovalPublDate` | 国资委通过日期 |
| `csrcApprovalPublDate` | 证监会批准日期 |
| `advanceValidStartDate` | 预案有效期起始日期 |
| `advanceValidEndDate` | 预案有效期截止日期 |
| `newSharesListDate` | 增发新股上市日期 |
| `stockType` | 增发A股类型 |
| `issuePurpose` | 增发目的 |
| `issueObject` | 发行对象 |
| `issuePriceCeiling` | 发行价上限（元） |
| `issuePriceFloor` | 发行价下限（元） |
| `issuePrice` | 每股发行价（元） |
| `issueVol` | 发行量（万股） |
| `seoProceeds` | 增发新股募集资金总额（元） |
| `seoNetProceeds` | 增发新股募集资金净额（元） |

#### 高管变动（LeaderChange）

| 字段 | 说明 |
|------|------|
| `leaderName` | 高管姓名 |
| `leaderPosition` | 职位（如 副总裁/董事/总经理） |
| `leaderPositionType` | 职位类型（如 经营层/董事会） |
| `leaderStartDate` | 任职起始日期（已规范化为 YYYY-MM-DD） |
| `leaderChangeReason` | 变动原因（如 退休/辞职/换届） |

> **接入说明**：通过 `stock_quote_snapshot` 截面查询，`LeaderChange` 字段是嵌套 JSON 数组字符串。结果按任职起始日期倒序。

#### 高管增减持（ExecutiveTransferPlans）

| 字段 | 说明 |
|------|------|
| `managerName` | 高管姓名 |
| `managerSharesChange` | 股份变动数量（**负数表示减持，正数表示增持**） |
| `managerDealPrice` | 成交均价（元） |
| `managerHoldChangeDeclareDate` | 公告日期（已规范化为 YYYY-MM-DD） |

> **接入说明**：`stock_quote_history` 取近 1 年序列 + `stock_quote_snapshot` 兜底最新一条，按 (公告日期, 姓名, 变动数) 三元组去重，结果按公告日期倒序。

#### 评级信息（BondRatingInfo）

| 字段 | 说明 |
|------|------|
| `rating` | 评级（如 AAA/AA+/AA） |
| `ratingOutlook` | 评级展望（如 稳定/正面/负面） |
| `ratingChgDirection` | 变动方向（如 维持/上调/下调） |
| `ratingStandard` | 评级标准 |
| `ratingOrg` | 评级机构（如 中诚信国际/联合资信） |

> **注意**：风险事件只提供客观数据展示，不进行主观评分或风险等级判定。用户需根据实际情况自行判断风险程度。无效代码或无风险事件的股票会输出"暂无风险事件"，AI 应如实反馈不要编造风险信息。

---

### 事件总览（`westock events`，42 类标签）

> **与 risk 的差别**：`westock risk` 是 8 类风险事件**细查**（按个股取明细字段），`westock events` 是 42 类事件标签**速览**（按 `stock_event` 全市场清单一次拉取后客户端过滤）。`westock events` 仅展示挂在股票身上的事件 ID + 中文描述，覆盖中性+利好+风险全场景，不含明细字段。

**返回字段**：

| 字段 | 说明 |
|------|------|
| `date` | 查询日期（YYYY-MM-DD） |
| `stocks[].code` | 股票代码（如 sh600519） |
| `stocks[].name` | 股票名称（清单未返回时通过 `stock_quote_snapshot` 兜底补全） |
| `stocks[].tagIds` | 命中的事件 ID 数组（按 `--types` 过滤后） |
| `stocks[].tagDescs` | 事件 ID 对应中文描述（与 tagIds 顺序一致） |

**42 类事件 ID 映射（按大类分组）**：

| 大类 | 事件 ID | 说明 |
|------|---------|------|
| 交易异动 | 1 | 过去1个月内的大宗交易 |
| 交易异动 | 21 | 过去2周内的龙虎榜上榜详情 |
| 交易异动 | 22 | 过去2周内的龙虎榜上榜统计 |
| 股本变动 | 2 | 过去1个月内发生了回购披露的 |
| 股本变动 | 5 | 在过去1个月内发布了实施公告但尚未除权除息(含权期) |
| 股本变动 | 6 | 在过去3天内已经除权除息(正在填权观察窗口期) |
| 股本变动 | 7 | 在过去1个月内发布了分红预案(已过董事会) |
| 股本变动 | 8 | 在过去1个月内发布了分红决案(已过股东大会) |
| 股本变动 | 17 | 定增上市后一月 |
| 股本变动 | 18 | 定增上市后三月 |
| 股本变动 | 19 | 定增上市前一月 |
| 股本变动 | 20 | 定增上市前一周 |
| 业绩披露 | 9 | 过去1个月新增发布业绩快报 |
| 业绩披露 | 10 | 过去1个月新增发布业绩预告 |
| 业绩披露 | 11 | 过去7天新增发布财报 |
| 业绩披露 | 12 | 已经披露了将在未来1个月内发布新财报 |
| 指数变动 | 13 | 刚加入重要指数成分股一周内 |
| 指数变动 | 14 | 已披露即将加入重要指数成分股 |
| 指数变动 | 15 | 刚被踢出重要指数成分股一周内 |
| 指数变动 | 16 | 已披露即将踢出重要指数成分股 |
| 董监高 | 23 | 过去1个月内有董监高变动 |
| 董监高 | 24 | 过去1个月内发生了董监高增减持的披露 |
| 董监高 | 25 | 披露了计划增持且正在计划实施中的 |
| 董监高 | 26 | 已经披露计划增持但尚未进入实施 |
| 董监高 | 27 | 披露了计划减持且正在计划实施中的 |
| 董监高 | 28 | 已经披露计划减持但尚未进入实施 |
| 股权事件 | 29 | 将在1个月内召开股东大会 |
| 股权事件 | 30 | 尚未否决或结束的吸收合并 |
| 股权事件 | 31 | 尚未否决或结束的资产重组 |
| 股权事件 | 32 | 已公告即将更名，尚未生效 |
| 股权事件 | 33 | 过去3个月内刚更名的观察期 |
| 股权事件 | 38 | 尚未否决或结束的要约收购 |
| 限售解禁 | 34 | 已经发布了实际解禁公告将在不远的近期发生实际解禁 |
| 限售解禁 | 35 | 实际解禁份额已上市的2周观察期内 |
| 限售解禁 | 36 | 预计将在未来3个月内解禁 |
| 法律处罚 | 3 | 已经披露被处罚但尚未生效 |
| 法律处罚 | 4 | 已经生效的重大违规处罚一月内 |
| 法律处罚 | 37 | 过去一个月内披露涉诉 |
| 停复牌 | 39 | 预计将在未来3天内复牌 |
| 停复牌 | 40 | 过去1周内已复牌的 |
| 停复牌 | 41 | 处在停牌中的股票 |
| 停复牌 | 42 | 停牌已超过30天的股票 |

> 完整中文描述与最新分组见上表（与代码同源）。

**典型用法**：

```bash
westock events sh600519                  # 个股事件标签速览
westock events sh600519,sz000001         # 批量

```

**与 risk 的选择**：
- 想知道**有没有**某类事件 → `westock events`（轻量速览，1 次接口拉清单）
- 想拿到**明细字段**（如解禁数量、质押比例、诉讼金额、高管姓名） → `westock risk`

> **数据特性**：`westock events` 命中规则由 `stock_event` 清单维护方决定（如"过去 1 个月内"、"未来 3 天内"等窗口）；某些 ID（如停复牌系列）只在事件发生窗口内才会被打标。当某只股票 `westock events` 返回为空时，应明确告知用户"当前无事件命中"，**不应编造事件**。

---

## 五、分析模板

### 成交量分析

1. `westock kline <CODE> day 20` → 从表格中提取 `volume` 列
2. 计算：平均值、最大/最小值、前10日均值 vs 后10日均值
3. 识别：放量日（>均值×1.5）、缩量日（<均值×0.5）

### 资金流向分析

**A股**：`westock fund flow <CODE>` → 提取 `MainNetFlow`/`JumboNetFlow`/`BlockNetFlow` → 转换单位（元→亿元）→ 统计净流入/流出天数

**港股资金**：`westock fund flow <CODE>` → 提取 `TotalNetFlow`/`MainNetFlow` → 分析主力趋势

**港股卖空**：`westock fund short <CODE>` → 提取 `ShortShares`/`ShortAmount`/`ShortRatio` → 卖空比率>15%需关注

**美股卖空**：`westock fund short <CODE>` → 提取 `ShortRatio`/`ShortShares`/`ShortRecoverDays` → `ShortRatio`>10%或`ShortRecoverDays`>5天需关注

**指数/板块**：`market <CODE>` → 提取 `mainNetFlow`/`jumboNetFlow`/`blockNetFlow` → 转换单位 → 判断主力方向

### 技术指标分析

**MACD**：DIF与DEA交叉（金叉=买信号/死叉=卖信号）、MACD柱正负变化、DIF/DEA相对0轴位置

**KDJ**：K与D交叉、J值>80超买/<20超卖

**RSI**：RSI_6>70超买/<30超卖，RSI_6与RSI_12背离

**均线**：多头排列（MA5>MA10>MA20>MA60）、MA60/120/250作为支撑/压力位

### 筹码趋势分析（历史区间）

- 盈利率上升 = 获利盘增加（股价上涨）
- 平均成本抬升 = 筹码成本中枢上移（主力可能建仓）
- 集中度下降 = 筹码趋于集中（主力吸筹控盘）
- 集中度上升 = 筹码趋于分散（可能派发）

### 机构评级分析（港股/美股）

1. 评级共识度：`(ratingBuyCnt + ratingIncCnt) / ratingCnt`
2. 目标均价 vs 当前价 → 上涨/下跌空间
3. 港股：`earningsForecast` EPS × 目标PE → 合理估值区间

### A股一致预期分析

1. 目标价 vs 当前价 → 上涨空间
2. 多年度EPS增速 → 盈利增长确定性
3. PE走势 → 估值是否逐年降低（估值消化）
4. `institutionCnt` → 共识覆盖度

### 宏观经济数据分析

**可用指标**（短名带 region 前缀，详见 [macro-fields.md](./macro-fields.md)）：

| 短名 | 名称 | 分组 | 查询方式 |
|----------|------|------|----------|
| `cn_gdp` | GDP数量指标 | GDP | `--year` |
| `cn_cpi_ppi` | GDP价格指标(CPI/PPI) | GDP | `--year` |
| `cn_pmi` | GDP供给指标(PMI) | GDP | `--year` / `--start --end` |
| `cn_profit` | GDP供给指标(工业企业利润) | GDP | `--year` |
| `cn_valueadded` | GDP供给指标(工业增加值) | GDP | `--year` |
| `cn_consumption` | GDP需求指标(消费) | GDP | `--year` |
| `cn_investment` | GDP需求指标(投资) | GDP | `--year` |
| `cn_prosperity` | GDP供给指标(企业景气指数) | GDP | `--year` |
| `cn_fiscal` | GDP财政指标 | GDP | `--year` |
| `cn_power_consumption` | GDP供给指标(用电量) | GDP | `--year` |
| `cn_disposable_income` | GDP需求指标(可支配收入) | GDP | `--year` |
| `cn_capacity_utilization` | GDP供给指标(产能利用率) | GDP | `--year` |
| `cn_product_output` | GDP供给指标(宏观产量) | GDP | `--year` |
| `cn_export_value` | GDP需求指标(出口交货值) | GDP | `--year` |
| `cn_export` | GDP需求指标(进出口) | GDP | `--year` |
| `cn_financing` | 货币需求指标(社融) | 货币 | `--year` |
| `cn_fundquantity` | 货币供给指标(数量) | 货币 | `--year` |
| `cn_fundcost` | 货币供给指标(利率) | 货币 | `--year` |
| `cn_yield_curve` | 货币供给指标(国债收益率曲线) | 货币 | `--year` |
| `cn_mlf` | 货币供给指标(公开市场操作/MLF) | 货币 | `--year` |
| `cn_term_spread` | 期限利差与曲线形态 | 估值 | `--date`（最新值） |
| `cn_premium_curve` | 溢价率曲线（红利/股债） | 估值 | `--date`（日频历史） |
| `cn_premium_value` | 溢价率水平（含10年分位） | 估值 | `--date`（最新值） |
| `cn_core` | 最新核心宏观指标（聚合短名，一键拉 p1+p2） | 综合 | `--date` |
| `cn_forecast` | 宏观预测 | 综合 | `--year` |
| `cn_employment` | 就业情况 | 综合 | `--date`（日频） |
| `cn_calendar_hist` | 宏观日历历史 | 综合 | `--year` |
| `cn_calendar_future` | 宏观日历未来 | 综合 | `--date` |
| `cn_lpr` | 贷款市场报价利率(LPR) | 中国专项 | `--date` |
| `cn_caixin_pmi` | 财新PMI | 中国专项 | `--date` |
| `cn_installed_capacity` | 发电装机容量 | 中国专项 | `--date` |
| `us_*` (29 个主题) | 美股宏观（就业/通胀/货币政策/景气/经济增长/财政/能源/地产/消费/工业生产/对外贸易/国债持有/美联储/VIX/美元指数/三大股指/债务规模/期限利差/收益率曲线/政策利率锚/SOFR/广义利率） | 主题 | `--date` |
| `hk_*` (4 个主题) | 港股宏观（经济增长/进出口外储/货币/其它） | 主题 | `--date` |
| `jp_*` (6 个主题) | 日本宏观（经济增长/通胀/就业/景气/货币/进出口外储） | 主题 | `--date` |
| `eu_*` (6 个主题) | 欧元区宏观（经济增长/通胀/货币/景气/进出口外储/就业） | 主题 | `--date` |
| `expect_<iso3>` (36 个地区) | 海外预期日历（按 iso3 地区代码） | global | `--year` 或 `--start --end` |

> **三种查询方式**：
> 1. **`--year` / `--start --end`**（标准年份型）：cn_gdp/cn_cpi_ppi/cn_pmi 等大多数中国指标
> 2. **`--date`**（按指定日期）：`cn_core`/`cn_premium_*`/`cn_term_spread`/`cn_calendar_future`/`cn_lpr` 等中国日频指标，以及**所有海外主题**（us_/hk_/jp_/eu_）
> 3. **`westock macro expect --area <iso3> --year`**：海外预期日历（36 个地区）独立子命令
>
> **聚合短名**：`cn_core` 一键拉 `cn_core_p1 + cn_core_p2`（同时返回 7 大核心指标）
> **region 一键全套**：`westock macro indicator --region us --date <今天>` 一键拉该 region 全套主题。**推荐**加 `--limit 5` 仅取最近 5 条/指标
> **mode 校验**：传错 `--year` 给 mode=date 指标会报错；agent 不确定时先用 `westock macro list --region <r>` 查 mode

**PMI 分析要点**：
1. 制造业 PMI > 50 → 扩张，< 50 → 收缩
2. 关注新订单 vs 产成品库存差值 → 未来景气领先指标
3. 连续 3 个月趋势比单月数值更重要

**GDP 价格指标分析**：
1. CPI 同比 > 3% → 通胀压力，< 0 → 通缩风险
2. PPI vs CPI 剪刀差 → 上下游传导效率
3. 核心 CPI（剔除食品能源）→ 真实通胀水平

**货币指标分析**：
1. M2 增速 > 名义 GDP 增速 → 流动性宽裕
2. M1-M2 剪刀差收窄 → 企业活期存款增加（经营活跃）
3. 社融增量同比 → 实体经济融资需求
4. LPR/MLF 利率变动 → 央行政策信号

**国债收益率曲线分析**（`yield_curve`）：
1. 10Y-1Y 利差扩大 → 经济预期改善；倒挂 → 衰退预期
2. 长端利率（10Y/30Y）下行 → 风险偏好回落或宽松预期
3. 短端利率（1Y/2Y）跟随政策利率（MLF/逆回购）

**国债收益率曲线分析**（`cn_yield_curve`）：
1. 10Y-1Y 利差扩大 → 经济预期改善；倒挂 → 衰退预期
2. 长端利率（10Y/30Y）下行 → 风险偏好回落或宽松预期
3. 短端利率（1Y/2Y）跟随政策利率（MLF/逆回购）

**MLF 公开市场操作分析**（`cn_mlf`）：
1. 净投放（投放-到期）持续为正 → 央行主动宽松
2. 操作利率下调 → LPR 大概率跟随下调，宽松信号
3. 月末余额变化反映总量基调

**财政指标分析**（`cn_fiscal`）：
1. 财政赤字进度（`FISCAL_DEFICIT_PRG_YTD`）→ 全年赤字执行节奏
2. 税收/非税收占比 → 财政质量
3. 地方债发行（一般+专项）→ 基建发力强度
4. 民生支出占比（教育/医疗/社保）→ 财政结构

**就业指标分析**（`cn_employment`）：
1. 城镇调查失业率 → 整体就业景气
2. 16-24 岁青年失业率 → 结构性矛盾
3. 百度搜索指数（招聘/失业/找工作）→ 高频领先信号

**产能利用率分析**（`cn_capacity_utilization`）：
1. 制造业产能利用率 < 75% → 产能过剩；> 80% → 偏紧
2. 同比改善幅度大的行业 → 景气拐点

**进出口分析**（`cn_export`）：
1. 货物贸易差额 → 顺差/逆差对人民币汇率影响
2. 服务贸易差额（旅行/运输等）→ 跨境消费/物流变化
3. 外汇储备 + 黄金储备 → 央行储备资产配置

**宏观预测分析**（`cn_forecast`）：
1. 与官方公布值对比 → 市场一致预期偏离
2. PMI/CPI/M2 等核心指标的预测值 → 短期市场博弈基准
3. 多份预测值的中位数比单一来源更可靠

**溢价率分析**（`cn_premium_value` / `cn_premium_curve`）：
1. **股债溢价率（EquityPremium）= E/P - 10Y国债收益率**：衡量股票相对债券的吸引力
   - 数值越高 → 股票相对债券越便宜 → 股市性价比高
   - `EprPct10Y` 在 80%+ → 历史高位，股市偏便宜；< 20% → 历史低位，股市偏贵
2. **红利溢价率（DividendPremium）= 股息率 - 10Y国债收益率**：衡量高股息资产相对债券的吸引力
   - 高位 → 高股息策略胜率提升
3. **`cn_premium_curve`（约 2400 条历史日频）→ 长期分位上下轨**；`cn_premium_value`（1 条最新值 + 10 年分位）→ 当前快速判断

**期限利差分析**（`cn_term_spread`）：
1. **`TermSpread` = Yield10Y - Yield2Y（单位 bps）**：衡量长短端国债利差
   - 利差扩大（变陡） → 经济预期改善；倒挂 → 衰退预期信号
2. **`CurveForm*` 中文枚举**（牛陡/牛平/熊陡/熊平），多周期视角：
   - **牛陡**：短端下行更快 → 宽松预期/避险买短债
   - **牛平**：长端下行更快 → 衰退/通缩预期、避险买长债
   - **熊陡**：长端上行更快 → 通胀/经济过热预期
   - **熊平**：短端上行更快 → 央行紧缩预期
3. **长短端变化对比**（`LongDif*` vs `ShortDif*`）→ 判断曲线驱动来自哪一端

**海外主题宏观分析（事件日历型）**（`us_*` / `hk_*` / `jp_*` / `eu_*`）：

统一 schema：`OccurDate` / `IndicatorName` / `ActualValue` / `ForecastValue` / `FormerValue` / `OccurTime`

1. **三栏对比识别预期差**：
   - `ActualValue` > `ForecastValue` → 数据超预期（鹰派事件 / 利好风险资产视情况）
   - `ActualValue` < `ForecastValue` → 不及预期（鸽派事件）
   - `ActualValue` 与 `FormerValue` 比较 → 边际变化方向
2. **常用筛查模式**：
   - 通胀：核心 PCE/CPI 月率/年率（美联储锚 = 2%）；PPI 月率（上游传导）；通胀预期（脱锚警讯）
   - 就业：非农 vs 预期（强 → 削弱降息）；失业率 vs 自然失业率；时薪同比（粘性通胀来源）
   - 货币：联邦基金利率上下限；FFR 当前年度/后面 1-3 年/长期（点阵图含义）
3. **降息/加息预期跟踪**：组合 `us_monetary --date` + `westock macro expect --area usa --year`
4. **板块映射规则**：
   - 鸽派偏移 → 利好成长股 / 长久期资产 / 黄金
   - 鹰派偏移 → 利好金融股（净息差扩大）/ 价值股
   - 通胀粘性高 → 价值股 / 能源 / 必选消费
   - 通胀回落 → 长久期成长股 / 利率敏感板块

**海外预期日历**（`expect_<iso3>` 共 36 个地区，`westock macro expect --area <iso3> --year`）：

比海外主题宏观多一列 `Importance`（1=低 / 2=中 / 3=高）。

1. 按 `Importance` 筛重要事件（FOMC / 非农 / CPI / PPI / GDP）
2. 公布前看 `ForecastValue`（市场一致预期），公布后看 `ActualValue` vs `ForecastValue` 预期差
3. 与主题型差异：主题型按 region 分主题切片（适合"看美国通胀近期"）；海外预期按地区分单地区全套日历（适合"看某地区某年所有重要事件"）

**中美对比 / 全球三央行对比 / 港股联系汇率制度**：
- 详见 [scenarios-guide.md 场景 72-76](./scenarios-guide.md)

### 板块成份股分析

> ⚠️ **概念股查询重点**：当用户问"XX概念有哪些股票"（如"华为概念股"、"AI概念股"、"新能源汽车概念"），必须使用统一 `westock search` 入口两步查询：
> 1. `westock search 华为 --type sector` — 搜索板块代码
> 2. `westock sector constituent <搜索到的代码>` — 查询成份股
>
> **不要用外部搜索工具**。

**板块代码格式**：

| 前缀 | 类型 | 示例 |
|------|------|------|
| `sw1_` | 申万一级行业 | `sw1_pt01801080`(电子) |
| `sw2_` | 申万二级行业 | `sw2_pt01801081`(半导体) |
| `sw3_` | 申万三级行业 | `sw3_pt01801081` |
| `area_` | 聚源地域概念 | `area_pt0001`(北京) |
| `style_` | 聚源产业概念 | `style_pt0001` |
| `indus_` | 聚源风格概念 | `indus_pt0001` |

> 指数成份股请使用 `westock index` 命令：`westock index constituent sh000300`（A 股）/ `westock index constituent hkHSI`（港股）

**返回字段（港股指数成份股）**：

| 字段 | 说明 |
|------|------|
| `code` | 成份股代码（如 hk00700） |
| `name` | 成份股名称（如 腾讯控股） |
| `chg` | 涨跌幅（%） |
| `turnover` | 成交额 |

**与 A 股指数成份股的差别**：

| 对比项 | A 股指数 | 港股指数 |
|--------|----------|----------|
| 返回字段 | code, name | code, name, chg, turnover |
| 成份数量 | 全量（如沪深300返回300只） | 仅返回当前涨幅/跌幅前20只 |

> **注意**：港股指数 `BkComponentStocks` 仅返回涨跌幅前 20 只成份股，非完整成份股列表。如需恒生指数全部 80 只成份股，建议通过 A 股对应指数或 ETF 持仓间接获取。


---

## 六、格式化输出规范

- 金额超过亿元：使用"亿元"/"亿港元"/"亿美元"
- 成交量超过万手：使用"万手"
- 涨跌幅：保留2位小数，带 +/- 号
- 日期：YYYY-MM-DD 格式
- 数据为空时说明"暂无数据"，**不可伪造数据**
- 港股/美股财务数据必须标注货币单位
