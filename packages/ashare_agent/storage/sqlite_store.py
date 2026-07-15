from __future__ import annotations

import sqlite3
from collections import defaultdict
from datetime import datetime
from pathlib import Path
from typing import Any

from ashare_agent.models import LimitUpEvent, NewsEvent, SectorSnapshot, SectorType, StockFeature, StockSnapshot


class SQLiteMarketStore:
    def __init__(self, db_path: str | Path) -> None:
        self.db_path = Path(db_path)

    def connect(self) -> sqlite3.Connection:
        self.db_path.parent.mkdir(parents=True, exist_ok=True)
        conn = sqlite3.connect(self.db_path)
        conn.row_factory = sqlite3.Row
        conn.execute("PRAGMA journal_mode=WAL")
        conn.execute("PRAGMA synchronous=NORMAL")
        return conn

    def init_db(self) -> None:
        with self.connect() as conn:
            conn.executescript(
                """
                CREATE TABLE IF NOT EXISTS stock_snapshots (
                  as_of TEXT NOT NULL,
                  trade_date TEXT NOT NULL,
                  symbol TEXT NOT NULL,
                  name TEXT NOT NULL,
                  price REAL NOT NULL,
                  pct_change REAL NOT NULL,
                  open REAL NOT NULL,
                  high REAL NOT NULL,
                  low REAL NOT NULL,
                  prev_close REAL NOT NULL,
                  volume REAL NOT NULL,
                  amount REAL NOT NULL,
                  turnover_rate REAL NOT NULL,
                  main_net_inflow REAL NOT NULL DEFAULT 0,
                  large_order_net_inflow REAL NOT NULL DEFAULT 0,
                  super_large_order_net_inflow REAL NOT NULL DEFAULT 0,
                  limit_up INTEGER NOT NULL DEFAULT 0,
                  limit_down INTEGER NOT NULL DEFAULT 0,
                  sealed_amount REAL NOT NULL DEFAULT 0,
                  board_open_count INTEGER NOT NULL DEFAULT 0,
                  recent_5d_gain REAL NOT NULL DEFAULT 0,
                  market_cap REAL NOT NULL DEFAULT 0,
                  raw_source TEXT NOT NULL DEFAULT 'unknown',
                  PRIMARY KEY (as_of, symbol)
                );

                CREATE TABLE IF NOT EXISTS sector_snapshots (
                  as_of TEXT NOT NULL,
                  trade_date TEXT NOT NULL,
                  sector_id TEXT NOT NULL,
                  sector_name TEXT NOT NULL,
                  sector_type TEXT NOT NULL,
                  pct_change REAL NOT NULL,
                  main_net_inflow REAL NOT NULL DEFAULT 0,
                  amount REAL NOT NULL DEFAULT 0,
                  amount_growth REAL NOT NULL DEFAULT 0,
                  up_count INTEGER NOT NULL DEFAULT 0,
                  down_count INTEGER NOT NULL DEFAULT 0,
                  limit_up_count INTEGER NOT NULL DEFAULT 0,
                  limit_down_count INTEGER NOT NULL DEFAULT 0,
                  new_high_count INTEGER NOT NULL DEFAULT 0,
                  breadth REAL NOT NULL DEFAULT 0,
                  continuity_days INTEGER NOT NULL DEFAULT 0,
                  catalyst_strength REAL NOT NULL DEFAULT 0,
                  board_open_rate REAL NOT NULL DEFAULT 0,
                  tail_support REAL NOT NULL DEFAULT 50,
                  top_symbols_json TEXT NOT NULL DEFAULT '[]',
                  raw_source TEXT NOT NULL DEFAULT 'unknown',
                  PRIMARY KEY (as_of, sector_id)
                );

                CREATE TABLE IF NOT EXISTS sector_membership (
                  as_of TEXT NOT NULL,
                  sector_name TEXT NOT NULL,
                  sector_type TEXT NOT NULL,
                  symbol TEXT NOT NULL,
                  name TEXT NOT NULL,
                  PRIMARY KEY (as_of, sector_name, symbol)
                );

                CREATE TABLE IF NOT EXISTS stock_realtime_quotes (
                  as_of TEXT NOT NULL,
                  trade_date TEXT NOT NULL,
                  symbol TEXT NOT NULL,
                  name TEXT NOT NULL,
                  price REAL NOT NULL,
                  pct_change REAL NOT NULL,
                  open REAL NOT NULL,
                  high REAL NOT NULL,
                  low REAL NOT NULL,
                  prev_close REAL NOT NULL,
                  volume REAL NOT NULL,
                  amount REAL NOT NULL,
                  raw_source TEXT NOT NULL DEFAULT 'unknown',
                  PRIMARY KEY (as_of, symbol)
                );

                CREATE TABLE IF NOT EXISTS stock_moneyflow (
                  as_of TEXT NOT NULL,
                  trade_date TEXT NOT NULL,
                  symbol TEXT NOT NULL,
                  name TEXT NOT NULL,
                  pct_change REAL NOT NULL DEFAULT 0,
                  latest REAL NOT NULL DEFAULT 0,
                  main_net_inflow REAL NOT NULL DEFAULT 0,
                  large_order_net_inflow REAL NOT NULL DEFAULT 0,
                  raw_source TEXT NOT NULL DEFAULT 'unknown',
                  PRIMARY KEY (as_of, symbol)
                );

                CREATE TABLE IF NOT EXISTS limit_up_events (
                  as_of TEXT NOT NULL,
                  trade_date TEXT NOT NULL,
                  symbol TEXT NOT NULL,
                  name TEXT NOT NULL,
                  sector_name TEXT NOT NULL DEFAULT '',
                  first_limit_time TEXT NOT NULL DEFAULT '',
                  consecutive_boards INTEGER NOT NULL DEFAULT 1,
                  sealed_amount REAL NOT NULL DEFAULT 0,
                  board_open_count INTEGER NOT NULL DEFAULT 0,
                  raw_source TEXT NOT NULL DEFAULT 'unknown',
                  PRIMARY KEY (as_of, symbol)
                );

                CREATE TABLE IF NOT EXISTS news_events (
                  event_id TEXT PRIMARY KEY,
                  as_of TEXT NOT NULL,
                  trade_date TEXT NOT NULL,
                  source TEXT NOT NULL,
                  title TEXT NOT NULL,
                  content TEXT NOT NULL DEFAULT '',
                  symbols_json TEXT NOT NULL DEFAULT '[]',
                  sectors_json TEXT NOT NULL DEFAULT '[]',
                  event_type TEXT NOT NULL,
                  sentiment REAL NOT NULL DEFAULT 0,
                  importance REAL NOT NULL DEFAULT 0,
                  is_confirmed INTEGER NOT NULL DEFAULT 1
                );

                CREATE TABLE IF NOT EXISTS stock_features (
                  as_of TEXT NOT NULL,
                  trade_date TEXT NOT NULL,
                  symbol TEXT NOT NULL,
                  name TEXT NOT NULL,
                  pct_change REAL NOT NULL DEFAULT 0,
                  amount REAL NOT NULL DEFAULT 0,
                  turnover_rate REAL NOT NULL DEFAULT 0,
                  amount_rank INTEGER NOT NULL DEFAULT 0,
                  amount_percentile REAL NOT NULL DEFAULT 0,
                  main_net_inflow REAL NOT NULL DEFAULT 0,
                  main_net_inflow_rank INTEGER NOT NULL DEFAULT 0,
                  main_net_inflow_percentile REAL NOT NULL DEFAULT 0,
                  main_net_inflow_to_amount REAL NOT NULL DEFAULT 0,
                  rush_accumulation_score REAL NOT NULL DEFAULT 0,
                  limit_up INTEGER NOT NULL DEFAULT 0,
                  limit_down INTEGER NOT NULL DEFAULT 0,
                  recent_5d_gain REAL NOT NULL DEFAULT 0,
                  sector_names_json TEXT NOT NULL DEFAULT '[]',
                  raw_source TEXT NOT NULL DEFAULT 'derived',
                  PRIMARY KEY (as_of, symbol)
                );

                CREATE INDEX IF NOT EXISTS idx_stock_snapshots_latest
                  ON stock_snapshots (as_of DESC);
                CREATE INDEX IF NOT EXISTS idx_sector_snapshots_latest
                  ON sector_snapshots (as_of DESC);
                CREATE INDEX IF NOT EXISTS idx_sector_membership_latest
                  ON sector_membership (as_of DESC, symbol);
                CREATE INDEX IF NOT EXISTS idx_stock_realtime_quotes_latest
                  ON stock_realtime_quotes (as_of DESC);
                CREATE INDEX IF NOT EXISTS idx_stock_moneyflow_latest
                  ON stock_moneyflow (as_of DESC);
                CREATE INDEX IF NOT EXISTS idx_limit_up_events_latest
                  ON limit_up_events (as_of DESC);
                CREATE INDEX IF NOT EXISTS idx_news_events_latest
                  ON news_events (as_of DESC, event_type);
                CREATE INDEX IF NOT EXISTS idx_stock_features_latest
                  ON stock_features (as_of DESC);
                """
            )

    def save_stock_snapshots(self, snapshots: list[StockSnapshot], source: str) -> int:
        if not snapshots:
            return 0
        self.init_db()
        rows = [
            (
                item.timestamp.isoformat(),
                item.timestamp.date().isoformat(),
                item.symbol,
                item.name,
                item.price,
                item.pct_change,
                item.open,
                item.high,
                item.low,
                item.prev_close,
                item.volume,
                item.amount,
                item.turnover_rate,
                item.main_net_inflow,
                item.large_order_net_inflow,
                item.super_large_order_net_inflow,
                int(item.limit_up),
                int(item.limit_down),
                item.sealed_amount,
                item.board_open_count,
                item.recent_5d_gain,
                item.market_cap,
                source,
            )
            for item in snapshots
        ]
        with self.connect() as conn:
            conn.executemany(
                """
                INSERT OR REPLACE INTO stock_snapshots (
                  as_of, trade_date, symbol, name, price, pct_change, open, high, low,
                  prev_close, volume, amount, turnover_rate, main_net_inflow,
                  large_order_net_inflow, super_large_order_net_inflow, limit_up,
                  limit_down, sealed_amount, board_open_count, recent_5d_gain,
                  market_cap, raw_source
                ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                """,
                rows,
            )
        return len(rows)

    def save_sector_snapshots(self, snapshots: list[SectorSnapshot], source: str) -> int:
        if not snapshots:
            return 0
        self.init_db()
        rows = [
            (
                item.timestamp.isoformat(),
                item.timestamp.date().isoformat(),
                item.sector_id,
                item.sector_name,
                item.sector_type.value,
                item.pct_change,
                item.main_net_inflow,
                item.amount,
                item.amount_growth,
                item.up_count,
                item.down_count,
                item.limit_up_count,
                item.limit_down_count,
                item.new_high_count,
                item.breadth,
                item.continuity_days,
                item.catalyst_strength,
                item.board_open_rate,
                item.tail_support,
                __import__("json").dumps(item.top_symbols, ensure_ascii=False),
                source,
            )
            for item in snapshots
        ]
        with self.connect() as conn:
            conn.executemany(
                """
                INSERT OR REPLACE INTO sector_snapshots (
                  as_of, trade_date, sector_id, sector_name, sector_type, pct_change,
                  main_net_inflow, amount, amount_growth, up_count, down_count,
                  limit_up_count, limit_down_count, new_high_count, breadth,
                  continuity_days, catalyst_strength, board_open_rate, tail_support,
                  top_symbols_json, raw_source
                ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                """,
                rows,
            )
        return len(rows)

    def save_sector_memberships(self, as_of: datetime, memberships: list[dict[str, str]]) -> int:
        if not memberships:
            return 0
        self.init_db()
        rows = [
            (
                as_of.isoformat(),
                item["sector_name"],
                item.get("sector_type", SectorType.CONCEPT.value),
                item["symbol"],
                item.get("name", ""),
            )
            for item in memberships
        ]
        with self.connect() as conn:
            conn.executemany(
                """
                INSERT OR REPLACE INTO sector_membership (
                  as_of, sector_name, sector_type, symbol, name
                ) VALUES (?, ?, ?, ?, ?)
                """,
                rows,
            )
        return len(rows)

    def save_realtime_quotes(self, snapshots: list[StockSnapshot], source: str) -> int:
        if not snapshots:
            return 0
        self.init_db()
        rows = [
            (
                item.timestamp.isoformat(),
                item.timestamp.date().isoformat(),
                item.symbol,
                item.name,
                item.price,
                item.pct_change,
                item.open,
                item.high,
                item.low,
                item.prev_close,
                item.volume,
                item.amount,
                source,
            )
            for item in snapshots
        ]
        with self.connect() as conn:
            conn.executemany(
                """
                INSERT OR REPLACE INTO stock_realtime_quotes (
                  as_of, trade_date, symbol, name, price, pct_change, open, high, low,
                  prev_close, volume, amount, raw_source
                ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                """,
                rows,
            )
        return len(rows)

    def save_stock_moneyflow(self, snapshots: list[StockSnapshot], source: str) -> int:
        if not snapshots:
            return 0
        self.init_db()
        rows = [
            (
                item.timestamp.isoformat(),
                item.timestamp.date().isoformat(),
                item.symbol,
                item.name,
                item.pct_change,
                item.price,
                item.main_net_inflow,
                item.large_order_net_inflow,
                source,
            )
            for item in snapshots
        ]
        with self.connect() as conn:
            conn.executemany(
                """
                INSERT OR REPLACE INTO stock_moneyflow (
                  as_of, trade_date, symbol, name, pct_change, latest,
                  main_net_inflow, large_order_net_inflow, raw_source
                ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)
                """,
                rows,
            )
        return len(rows)

    def save_limit_up_events(self, events: list[LimitUpEvent], source: str) -> int:
        if not events:
            return 0
        self.init_db()
        rows = [
            (
                item.timestamp.isoformat(),
                item.timestamp.date().isoformat(),
                item.symbol,
                item.name,
                item.sector_name,
                item.first_limit_time,
                item.consecutive_boards,
                item.sealed_amount,
                item.board_open_count,
                source,
            )
            for item in events
        ]
        with self.connect() as conn:
            conn.executemany(
                """
                INSERT OR REPLACE INTO limit_up_events (
                  as_of, trade_date, symbol, name, sector_name, first_limit_time,
                  consecutive_boards, sealed_amount, board_open_count, raw_source
                ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                """,
                rows,
            )
        return len(rows)

    def save_news_events(self, events: list[NewsEvent]) -> int:
        if not events:
            return 0
        self.init_db()
        json = __import__("json")
        rows = [
            (
                item.event_id,
                item.timestamp.isoformat(),
                item.timestamp.date().isoformat(),
                item.source,
                item.title,
                item.content,
                json.dumps(item.symbols, ensure_ascii=False),
                json.dumps(item.sectors, ensure_ascii=False),
                item.event_type,
                item.sentiment,
                item.importance,
                int(item.is_confirmed),
            )
            for item in events
        ]
        with self.connect() as conn:
            conn.executemany(
                """
                INSERT OR REPLACE INTO news_events (
                  event_id, as_of, trade_date, source, title, content,
                  symbols_json, sectors_json, event_type, sentiment,
                  importance, is_confirmed
                ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                """,
                rows,
            )
        return len(rows)

    def delete_news_events(self, trade_date: str, event_type: str) -> int:
        self.init_db()
        with self.connect() as conn:
            cursor = conn.execute(
                "DELETE FROM news_events WHERE trade_date = ? AND event_type = ?",
                (trade_date, event_type),
            )
        return cursor.rowcount

    def save_stock_features(self, features: list[StockFeature], source: str = "derived") -> int:
        if not features:
            return 0
        self.init_db()
        json = __import__("json")
        rows = [
            (
                item.timestamp.isoformat(),
                item.timestamp.date().isoformat(),
                item.symbol,
                item.name,
                item.pct_change,
                item.amount,
                item.turnover_rate,
                item.amount_rank,
                item.amount_percentile,
                item.main_net_inflow,
                item.main_net_inflow_rank,
                item.main_net_inflow_percentile,
                item.main_net_inflow_to_amount,
                item.rush_accumulation_score,
                int(item.limit_up),
                int(item.limit_down),
                item.recent_5d_gain,
                json.dumps(item.sector_names, ensure_ascii=False),
                source,
            )
            for item in features
        ]
        with self.connect() as conn:
            conn.executemany(
                """
                INSERT OR REPLACE INTO stock_features (
                  as_of, trade_date, symbol, name, pct_change, amount, turnover_rate,
                  amount_rank, amount_percentile, main_net_inflow,
                  main_net_inflow_rank, main_net_inflow_percentile,
                  main_net_inflow_to_amount, rush_accumulation_score,
                  limit_up, limit_down, recent_5d_gain, sector_names_json,
                  raw_source
                ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                """,
                rows,
            )
        return len(rows)

    def latest_as_of(self, table: str) -> str | None:
        if table not in {
            "stock_snapshots",
            "sector_snapshots",
            "sector_membership",
            "stock_realtime_quotes",
            "stock_moneyflow",
            "limit_up_events",
            "news_events",
            "stock_features",
        }:
            raise ValueError(f"unsupported table: {table}")
        self.init_db()
        with self.connect() as conn:
            row = conn.execute(f"SELECT MAX(as_of) AS as_of FROM {table}").fetchone()
        return row["as_of"] if row and row["as_of"] else None

    def load_latest_stock_snapshots(self) -> list[StockSnapshot]:
        if not self.latest_as_of("stock_snapshots"):
            return []
        memberships = self.load_latest_memberships()
        with self.connect() as conn:
            rows = conn.execute(
                """
                SELECT s.*
                FROM stock_snapshots s
                JOIN (
                  SELECT symbol, MAX(as_of) AS as_of
                  FROM stock_snapshots
                  GROUP BY symbol
                ) latest
                  ON latest.symbol = s.symbol AND latest.as_of = s.as_of
                ORDER BY s.amount DESC
                """
            ).fetchall()
        return [self._row_to_stock(row, memberships.get(row["symbol"], [])) for row in rows]

    def load_stock_snapshots_by_trade_date(self, trade_date: str) -> list[StockSnapshot]:
        self.init_db()
        memberships = self.load_latest_memberships()
        with self.connect() as conn:
            rows = conn.execute(
                """
                SELECT s.*
                FROM stock_snapshots s
                JOIN (
                  SELECT symbol, MAX(as_of) AS as_of
                  FROM stock_snapshots
                  WHERE trade_date = ?
                  GROUP BY symbol
                ) latest
                  ON latest.symbol = s.symbol AND latest.as_of = s.as_of
                WHERE s.trade_date = ?
                ORDER BY s.amount DESC
                """,
                (trade_date, trade_date),
            ).fetchall()
        return [self._row_to_stock(row, memberships.get(row["symbol"], [])) for row in rows]

    def load_latest_stock_snapshot_dicts(self, limit: int = 50) -> list[dict[str, Any]]:
        if not self.latest_as_of("stock_snapshots"):
            return []
        with self.connect() as conn:
            rows = conn.execute(
                """
                SELECT s.as_of, s.symbol, s.name, s.price, s.pct_change, s.volume,
                       s.amount, s.turnover_rate, s.raw_source
                FROM stock_snapshots s
                JOIN (
                  SELECT symbol, MAX(as_of) AS as_of
                  FROM stock_snapshots
                  GROUP BY symbol
                ) latest
                  ON latest.symbol = s.symbol AND latest.as_of = s.as_of
                ORDER BY s.amount DESC
                LIMIT ?
                """,
                (limit,),
            ).fetchall()
        return [dict(row) for row in rows]

    def load_latest_realtime_quote_dicts(self, limit: int = 50) -> list[dict[str, Any]]:
        as_of = self.latest_as_of("stock_realtime_quotes")
        if not as_of:
            return []
        with self.connect() as conn:
            rows = conn.execute(
                """
                SELECT as_of, symbol, name, price, pct_change, volume, amount, raw_source
                FROM stock_realtime_quotes
                WHERE as_of = ?
                ORDER BY amount DESC
                LIMIT ?
                """,
                (as_of, limit),
            ).fetchall()
        return [dict(row) for row in rows]

    def load_latest_moneyflow_dicts(self, limit: int = 50) -> list[dict[str, Any]]:
        as_of = self.latest_as_of("stock_moneyflow")
        if not as_of:
            return []
        with self.connect() as conn:
            rows = conn.execute(
                """
                SELECT as_of, symbol, name, pct_change, latest, main_net_inflow,
                       large_order_net_inflow, raw_source
                FROM stock_moneyflow
                WHERE as_of = ?
                ORDER BY main_net_inflow DESC
                LIMIT ?
                """,
                (as_of, limit),
            ).fetchall()
        return [dict(row) for row in rows]

    def load_moneyflow_dicts_by_trade_date(self, trade_date: str, limit: int = 20_000) -> list[dict[str, Any]]:
        self.init_db()
        with self.connect() as conn:
            rows = conn.execute(
                """
                SELECT m.as_of, m.symbol, m.name, m.pct_change, m.latest,
                       m.main_net_inflow, m.large_order_net_inflow, m.raw_source
                FROM stock_moneyflow m
                JOIN (
                  SELECT symbol, MAX(as_of) AS as_of
                  FROM stock_moneyflow
                  WHERE trade_date = ?
                  GROUP BY symbol
                ) latest
                  ON latest.symbol = m.symbol AND latest.as_of = m.as_of
                WHERE m.trade_date = ?
                ORDER BY m.main_net_inflow DESC
                LIMIT ?
                """,
                (trade_date, trade_date, limit),
            ).fetchall()
        return [dict(row) for row in rows]

    def load_latest_limit_up_event_dicts(self, limit: int = 100) -> list[dict[str, Any]]:
        as_of = self.latest_as_of("limit_up_events")
        if not as_of:
            return []
        with self.connect() as conn:
            rows = conn.execute(
                """
                SELECT as_of, symbol, name, sector_name, first_limit_time,
                       consecutive_boards, sealed_amount, board_open_count, raw_source
                FROM limit_up_events
                WHERE as_of = ?
                ORDER BY consecutive_boards DESC, sealed_amount DESC
                LIMIT ?
                """,
                (as_of, limit),
            ).fetchall()
        return [dict(row) for row in rows]

    def load_latest_limit_up_events(self) -> list[LimitUpEvent]:
        as_of = self.latest_as_of("limit_up_events")
        if not as_of:
            return []
        with self.connect() as conn:
            rows = conn.execute(
                """
                SELECT as_of, symbol, name, sector_name, first_limit_time,
                       consecutive_boards, sealed_amount, board_open_count
                FROM limit_up_events
                WHERE as_of = ?
                ORDER BY consecutive_boards DESC, sealed_amount DESC
                """,
                (as_of,),
            ).fetchall()
        return [
            LimitUpEvent(
                symbol=row["symbol"],
                name=row["name"],
                sector_name=row["sector_name"],
                timestamp=datetime.fromisoformat(row["as_of"]),
                first_limit_time=row["first_limit_time"],
                consecutive_boards=row["consecutive_boards"],
                sealed_amount=row["sealed_amount"],
                board_open_count=row["board_open_count"],
            )
            for row in rows
        ]

    def load_latest_news_event_dicts(self, event_type: str | None = None, limit: int = 100) -> list[dict[str, Any]]:
        self.init_db()
        latest_sql = "SELECT MAX(as_of) AS as_of FROM news_events"
        params: tuple[Any, ...] = ()
        if event_type:
            latest_sql += " WHERE event_type = ?"
            params = (event_type,)
        with self.connect() as conn:
            row = conn.execute(latest_sql, params).fetchone()
            as_of = row["as_of"] if row and row["as_of"] else None
            if not as_of:
                return []
            sql = """
                SELECT event_id, as_of, source, title, content, symbols_json,
                       sectors_json, event_type, sentiment, importance, is_confirmed
                FROM news_events
                WHERE as_of = ?
            """
            query_params: list[Any] = [as_of]
            if event_type:
                sql += " AND event_type = ?"
                query_params.append(event_type)
            sql += " ORDER BY importance DESC LIMIT ?"
            query_params.append(limit)
            rows = conn.execute(sql, tuple(query_params)).fetchall()
        json = __import__("json")
        result = []
        for item in rows:
            row_dict = dict(item)
            row_dict["symbols"] = json.loads(row_dict.pop("symbols_json"))
            row_dict["sectors"] = json.loads(row_dict.pop("sectors_json"))
            row_dict["is_confirmed"] = bool(row_dict["is_confirmed"])
            result.append(row_dict)
        return result

    def load_latest_stock_feature_dicts(self, limit: int = 100) -> list[dict[str, Any]]:
        as_of = self.latest_as_of("stock_features")
        if not as_of:
            return []
        with self.connect() as conn:
            rows = conn.execute(
                """
                SELECT as_of, symbol, name, pct_change, amount, turnover_rate,
                       amount_rank, amount_percentile, main_net_inflow,
                       main_net_inflow_rank, main_net_inflow_percentile,
                       main_net_inflow_to_amount, rush_accumulation_score,
                       limit_up, limit_down, recent_5d_gain, sector_names_json,
                       raw_source
                FROM stock_features
                WHERE as_of = ?
                ORDER BY rush_accumulation_score DESC, main_net_inflow DESC
                LIMIT ?
                """,
                (as_of, limit),
            ).fetchall()
        json = __import__("json")
        result = []
        for item in rows:
            row_dict = dict(item)
            row_dict["sector_names"] = json.loads(row_dict.pop("sector_names_json"))
            row_dict["limit_up"] = bool(row_dict["limit_up"])
            row_dict["limit_down"] = bool(row_dict["limit_down"])
            result.append(row_dict)
        return result

    def load_latest_symbols(self, limit: int | None = None) -> list[str]:
        if not self.latest_as_of("stock_snapshots"):
            return []
        sql = """
            SELECT s.symbol
            FROM stock_snapshots s
            JOIN (
              SELECT symbol, MAX(as_of) AS as_of
              FROM stock_snapshots
              GROUP BY symbol
            ) latest
              ON latest.symbol = s.symbol AND latest.as_of = s.as_of
            ORDER BY s.amount DESC
        """
        params: tuple[Any, ...] = ()
        if limit is not None and limit > 0:
            sql += " LIMIT ?"
            params = (limit,)
        with self.connect() as conn:
            rows = conn.execute(sql, params).fetchall()
        return [row["symbol"] for row in rows]

    def load_latest_sector_snapshots(self) -> list[SectorSnapshot]:
        as_of = self.latest_as_of("sector_snapshots")
        if not as_of:
            return []
        with self.connect() as conn:
            rows = conn.execute(
                "SELECT * FROM sector_snapshots WHERE as_of = ? ORDER BY pct_change DESC",
                (as_of,),
            ).fetchall()
        return [self._row_to_sector(row) for row in rows]

    def load_latest_memberships(self) -> dict[str, list[str]]:
        as_of = self.latest_as_of("sector_membership")
        if not as_of:
            return {}
        sectors_by_symbol: dict[str, list[str]] = defaultdict(list)
        with self.connect() as conn:
            rows = conn.execute(
                "SELECT symbol, sector_name FROM sector_membership WHERE as_of = ?",
                (as_of,),
            ).fetchall()
        for row in rows:
            sectors_by_symbol[row["symbol"]].append(row["sector_name"])
        return dict(sectors_by_symbol)

    def status(self) -> dict[str, Any]:
        self.init_db()
        with self.connect() as conn:
            stock_count = conn.execute("SELECT COUNT(*) AS c FROM stock_snapshots").fetchone()["c"]
            sector_count = conn.execute("SELECT COUNT(*) AS c FROM sector_snapshots").fetchone()["c"]
            membership_count = conn.execute("SELECT COUNT(*) AS c FROM sector_membership").fetchone()["c"]
            realtime_count = conn.execute("SELECT COUNT(*) AS c FROM stock_realtime_quotes").fetchone()["c"]
            moneyflow_count = conn.execute("SELECT COUNT(*) AS c FROM stock_moneyflow").fetchone()["c"]
            sector_flow_count = conn.execute(
                "SELECT COUNT(*) AS c FROM sector_snapshots WHERE main_net_inflow != 0"
            ).fetchone()["c"]
            limit_up_count = conn.execute("SELECT COUNT(*) AS c FROM limit_up_events").fetchone()["c"]
            news_count = conn.execute("SELECT COUNT(*) AS c FROM news_events").fetchone()["c"]
            dragon_tiger_count = conn.execute(
                "SELECT COUNT(*) AS c FROM news_events WHERE event_type = 'dragon_tiger'"
            ).fetchone()["c"]
            rush_event_count = conn.execute(
                "SELECT COUNT(*) AS c FROM news_events WHERE event_type = 'rush_accumulation'"
            ).fetchone()["c"]
            feature_count = conn.execute("SELECT COUNT(*) AS c FROM stock_features").fetchone()["c"]
        return {
            "db_path": str(self.db_path),
            "stock_snapshot_rows": stock_count,
            "stock_realtime_quote_rows": realtime_count,
            "stock_moneyflow_rows": moneyflow_count,
            "sector_snapshot_rows": sector_count,
            "sector_fund_flow_rows": sector_flow_count,
            "sector_membership_rows": membership_count,
            "limit_up_event_rows": limit_up_count,
            "news_event_rows": news_count,
            "dragon_tiger_event_rows": dragon_tiger_count,
            "rush_accumulation_event_rows": rush_event_count,
            "stock_feature_rows": feature_count,
            "latest_stock_as_of": self.latest_as_of("stock_snapshots"),
            "latest_realtime_as_of": self.latest_as_of("stock_realtime_quotes"),
            "latest_moneyflow_as_of": self.latest_as_of("stock_moneyflow"),
            "latest_sector_as_of": self.latest_as_of("sector_snapshots"),
            "latest_membership_as_of": self.latest_as_of("sector_membership"),
            "latest_limit_up_as_of": self.latest_as_of("limit_up_events"),
            "latest_news_event_as_of": self.latest_as_of("news_events"),
            "latest_feature_as_of": self.latest_as_of("stock_features"),
        }

    def quality(self) -> dict[str, Any]:
        status = self.status()
        has_stock = status["stock_snapshot_rows"] > 0 or status["stock_realtime_quote_rows"] > 0
        has_sector = status["sector_snapshot_rows"] > 0
        has_membership = status["sector_membership_rows"] > 0
        has_sector_fund_flow = status["sector_fund_flow_rows"] > 0
        has_stock_moneyflow = status["stock_moneyflow_rows"] > 0
        has_limit_up_events = status["limit_up_event_rows"] > 0
        has_dragon_tiger_events = status["dragon_tiger_event_rows"] > 0
        has_features = status["stock_feature_rows"] > 0
        blockers = []
        if not has_stock:
            blockers.append("missing stock quote/daily snapshots")
        if not has_sector:
            blockers.append("missing sector snapshots")
        if not has_membership:
            blockers.append("missing sector membership")
        if not has_sector_fund_flow:
            blockers.append("missing sector fund-flow rows")
        if not has_stock_moneyflow:
            blockers.append("missing stock money-flow rows")
        if not has_limit_up_events:
            blockers.append("missing limit-up event rows")
        if not has_features:
            blockers.append("missing derived stock feature rows")

        confidence = "high"
        if blockers:
            confidence = "medium" if has_stock and has_sector else "low"
        if not has_sector_fund_flow or not has_stock_moneyflow:
            confidence = "medium-low" if has_stock and has_sector else "low"

        return {
            **status,
            "has_stock_data": has_stock,
            "has_sector_data": has_sector,
            "has_membership_data": has_membership,
            "has_sector_fund_flow": has_sector_fund_flow,
            "has_stock_moneyflow": has_stock_moneyflow,
            "has_limit_up_events": has_limit_up_events,
            "has_dragon_tiger_events": has_dragon_tiger_events,
            "has_derived_features": has_features,
            "analysis_confidence_ceiling": confidence,
            "blockers": blockers,
        }

    def _row_to_stock(self, row: sqlite3.Row, sector_names: list[str]) -> StockSnapshot:
        return StockSnapshot(
            symbol=row["symbol"],
            name=row["name"],
            timestamp=datetime.fromisoformat(row["as_of"]),
            price=row["price"],
            pct_change=row["pct_change"],
            open=row["open"],
            high=row["high"],
            low=row["low"],
            prev_close=row["prev_close"],
            volume=row["volume"],
            amount=row["amount"],
            turnover_rate=row["turnover_rate"],
            main_net_inflow=row["main_net_inflow"],
            large_order_net_inflow=row["large_order_net_inflow"],
            super_large_order_net_inflow=row["super_large_order_net_inflow"],
            limit_up=bool(row["limit_up"]),
            limit_down=bool(row["limit_down"]),
            sealed_amount=row["sealed_amount"],
            board_open_count=row["board_open_count"],
            recent_5d_gain=row["recent_5d_gain"],
            market_cap=row["market_cap"],
            sector_names=sector_names,
        )

    def _row_to_sector(self, row: sqlite3.Row) -> SectorSnapshot:
        top_symbols = __import__("json").loads(row["top_symbols_json"])
        return SectorSnapshot(
            sector_id=row["sector_id"],
            sector_name=row["sector_name"],
            sector_type=SectorType(row["sector_type"]),
            timestamp=datetime.fromisoformat(row["as_of"]),
            pct_change=row["pct_change"],
            main_net_inflow=row["main_net_inflow"],
            amount=row["amount"],
            amount_growth=row["amount_growth"],
            up_count=row["up_count"],
            down_count=row["down_count"],
            limit_up_count=row["limit_up_count"],
            limit_down_count=row["limit_down_count"],
            new_high_count=row["new_high_count"],
            breadth=row["breadth"],
            top_symbols=top_symbols,
            continuity_days=row["continuity_days"],
            catalyst_strength=row["catalyst_strength"],
            board_open_rate=row["board_open_rate"],
            tail_support=row["tail_support"],
        )
