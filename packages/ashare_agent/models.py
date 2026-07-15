from __future__ import annotations

from datetime import datetime
from enum import StrEnum
from typing import Literal

from pydantic import BaseModel, Field


class SectorType(StrEnum):
    INDUSTRY = "industry"
    CONCEPT = "concept"


class SectorStage(StrEnum):
    STARTING = "starting"
    FERMENTING = "fermenting"
    MARKUP = "markup"
    CLIMAX = "climax"
    DIVERGENCE = "divergence"
    FADING = "fading"


class CandidateTier(StrEnum):
    CORE = "core"
    WATCH = "watch"
    BACKUP = "backup"
    REJECTED = "rejected"


class StockRole(StrEnum):
    SENTIMENT_LEADER = "sentiment_leader"
    TREND_ANCHOR = "trend_anchor"
    TWENTY_CM_CORE = "twenty_cm_core"
    CATCHUP_LEADER = "catchup_leader"
    FOLLOWER = "follower"


class StockSnapshot(BaseModel):
    symbol: str
    name: str
    timestamp: datetime
    price: float = Field(ge=0)
    pct_change: float
    open: float = Field(ge=0)
    high: float = Field(ge=0)
    low: float = Field(ge=0)
    prev_close: float = Field(ge=0)
    volume: float = Field(ge=0)
    amount: float = Field(ge=0)
    turnover_rate: float = Field(ge=0)
    main_net_inflow: float
    large_order_net_inflow: float
    super_large_order_net_inflow: float
    limit_up: bool = False
    limit_down: bool = False
    sealed_amount: float = Field(default=0, ge=0)
    board_open_count: int = Field(default=0, ge=0)
    recent_5d_gain: float = 0
    market_cap: float = Field(default=0, ge=0)
    sector_names: list[str] = Field(default_factory=list)


class SectorSnapshot(BaseModel):
    sector_id: str
    sector_name: str
    sector_type: SectorType = SectorType.CONCEPT
    timestamp: datetime
    pct_change: float
    main_net_inflow: float
    amount: float = Field(ge=0)
    amount_growth: float
    up_count: int = Field(ge=0)
    down_count: int = Field(ge=0)
    limit_up_count: int = Field(ge=0)
    limit_down_count: int = Field(default=0, ge=0)
    new_high_count: int = Field(default=0, ge=0)
    breadth: float = Field(ge=0, le=1)
    top_symbols: list[str] = Field(default_factory=list)
    continuity_days: int = Field(default=0, ge=0)
    catalyst_strength: float = Field(default=0, ge=0, le=100)
    board_open_rate: float = Field(default=0, ge=0, le=1)
    tail_support: float = Field(default=50, ge=0, le=100)


class LimitUpEvent(BaseModel):
    symbol: str
    name: str
    sector_name: str
    timestamp: datetime
    first_limit_time: str
    consecutive_boards: int = Field(ge=1)
    sealed_amount: float = Field(ge=0)
    board_open_count: int = Field(default=0, ge=0)


class NewsEvent(BaseModel):
    event_id: str
    timestamp: datetime
    source: str
    title: str
    content: str = ""
    symbols: list[str] = Field(default_factory=list)
    sectors: list[str] = Field(default_factory=list)
    event_type: Literal[
        "policy",
        "earnings",
        "contract",
        "risk",
        "industry",
        "limit_up_reason",
        "dragon_tiger",
        "rush_accumulation",
    ]
    sentiment: float = Field(ge=-1, le=1)
    importance: float = Field(ge=0, le=100)
    is_confirmed: bool = True


class StockFeature(BaseModel):
    symbol: str
    name: str
    timestamp: datetime
    pct_change: float = 0
    amount: float = Field(default=0, ge=0)
    turnover_rate: float = Field(default=0, ge=0)
    amount_rank: int = Field(default=0, ge=0)
    amount_percentile: float = Field(default=0, ge=0, le=1)
    main_net_inflow: float = 0
    main_net_inflow_rank: int = Field(default=0, ge=0)
    main_net_inflow_percentile: float = Field(default=0, ge=0, le=1)
    main_net_inflow_to_amount: float = 0
    rush_accumulation_score: float = Field(default=0, ge=0, le=100)
    limit_up: bool = False
    limit_down: bool = False
    recent_5d_gain: float = 0
    sector_names: list[str] = Field(default_factory=list)


class MainlineScore(BaseModel):
    sector_name: str
    score: float = Field(ge=0, le=100)
    stage: SectorStage
    tier: Literal["strong_mainline", "candidate_mainline", "rotation_hotspot", "weak"]
    reasons: list[str]
    risks: list[str]
    as_of: datetime


class LeaderCandidate(BaseModel):
    symbol: str
    name: str
    sector_name: str
    role: StockRole
    score: float = Field(ge=0, le=100)
    reasons: list[str]
    risks: list[str]
    as_of: datetime


class CatchupCandidate(BaseModel):
    symbol: str
    name: str
    sector_name: str
    score: float = Field(ge=0, le=100)
    tier: CandidateTier
    role: str
    reasons: list[str]
    risks: list[str]
    trigger_conditions: list[str]
    invalid_conditions: list[str]
    as_of: datetime


class RotationStatus(BaseModel):
    old_sector: str | None
    new_sector: str | None
    rotation_score: float = Field(ge=0, le=100)
    is_confirmed: bool
    reasons: list[str]
    risks: list[str]
    as_of: datetime


class MarketOverview(BaseModel):
    as_of: datetime
    data_mode: Literal["mock", "live", "historical"]
    market_sentiment: str
    mainlines: list[MainlineScore]
    leaders: list[LeaderCandidate]
    catchup_candidates: list[CatchupCandidate]
    rotation_status: RotationStatus


class BacktestTrade(BaseModel):
    symbol: str
    name: str
    sector_name: str
    signal_date: datetime
    entry_return: float
    next_day_close_return: float
    two_day_high_return: float
    three_day_high_return: float
    max_drawdown: float
    stopped_out: bool


class BacktestResult(BaseModel):
    as_of: datetime
    sample_size: int
    win_rate: float
    average_return: float
    median_return: float
    payoff_ratio: float
    max_drawdown: float
    trades: list[BacktestTrade]
