import os
import sqlite3
from datetime import datetime
from typing import List, Optional, Dict, Any, Tuple
import pandas as pd
from contextlib import contextmanager

from utils.config import config
from utils.helpers import logger


class DatabaseManager:
    """SQLite数据库管理器"""

    def __init__(self, db_path: Optional[str] = None):
        self.db_path = db_path or config.get_database_path()
        self._init_database()

    @contextmanager
    def _get_connection(self):
        """获取数据库连接（上下文管理器）"""
        conn = sqlite3.connect(self.db_path)
        conn.row_factory = sqlite3.Row
        try:
            yield conn
        finally:
            conn.close()

    def _init_database(self):
        """初始化数据库表结构"""
        with self._get_connection() as conn:
            cursor = conn.cursor()

            # 股票基本信息表
            cursor.execute("""
                CREATE TABLE IF NOT EXISTS stock_info (
                    symbol TEXT PRIMARY KEY,
                    name TEXT NOT NULL,
                    market TEXT NOT NULL,  -- A: A股, US: 美股, HK: 港股
                    industry TEXT,
                    exchange TEXT,
                    list_date TEXT,
                    update_time TIMESTAMP DEFAULT CURRENT_TIMESTAMP
                )
            """)

            # 日线数据表
            cursor.execute("""
                CREATE TABLE IF NOT EXISTS daily_data (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    symbol TEXT NOT NULL,
                    date TEXT NOT NULL,
                    open REAL,
                    high REAL,
                    low REAL,
                    close REAL,
                    volume INTEGER,
                    amount REAL,
                    amplitude REAL,
                    pct_change REAL,
                    change_amount REAL,
                    turnover REAL,
                    update_time TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                    UNIQUE(symbol, date)
                )
            """)

            # 创建索引
            cursor.execute("""
                CREATE INDEX IF NOT EXISTS idx_daily_symbol_date 
                ON daily_data(symbol, date)
            """)

            # 技术指标数据表
            cursor.execute("""
                CREATE TABLE IF NOT EXISTS indicators (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    symbol TEXT NOT NULL,
                    date TEXT NOT NULL,
                    ma5 REAL,
                    ma10 REAL,
                    ma20 REAL,
                    ma30 REAL,
                    ma60 REAL,
                    macd_dif REAL,
                    macd_dea REAL,
                    macd_histogram REAL,
                    rsi REAL,
                    kdj_k REAL,
                    kdj_d REAL,
                    kdj_j REAL,
                    boll_upper REAL,
                    boll_mid REAL,
                    boll_lower REAL,
                    update_time TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                    UNIQUE(symbol, date)
                )
            """)

            cursor.execute("""
                CREATE INDEX IF NOT EXISTS idx_indicators_symbol_date 
                ON indicators(symbol, date)
            """)

            # 交易信号表
            cursor.execute("""
                CREATE TABLE IF NOT EXISTS signals (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    symbol TEXT NOT NULL,
                    date TEXT NOT NULL,
                    strategy TEXT NOT NULL,
                    signal TEXT NOT NULL,  -- BUY, SELL, HOLD
                    confidence REAL,
                    price REAL,
                    notes TEXT,
                    created_time TIMESTAMP DEFAULT CURRENT_TIMESTAMP
                )
            """)

            conn.commit()

    def save_stock_info(self, info_df: pd.DataFrame):
        """保存股票基本信息"""
        with self._get_connection() as conn:
            info_df.to_sql("stock_info", conn, if_exists="append", index=False)

    def save_daily_data(self, symbol: str, df: pd.DataFrame):
        """保存日线数据"""
        if df.empty:
            return

        # 添加symbol列
        df_copy = df.copy()
        df_copy["symbol"] = symbol

        # 确保列名匹配
        column_mapping = {
            "日期": "date",
            "开盘": "open",
            "收盘": "close",
            "最高": "high",
            "最低": "low",
            "成交量": "volume",
            "成交额": "amount",
            "振幅": "amplitude",
            "涨跌幅": "pct_change",
            "涨跌额": "change_amount",
            "换手率": "turnover",
        }
        df_copy = df_copy.rename(columns=column_mapping)

        # 统一日期格式，避免时区/时间部分导致重复键冲突
        df_copy["date"] = (
            pd.to_datetime(df_copy["date"], utc=True, errors="coerce")
            .dt.strftime("%Y-%m-%d")
        )
        df_copy = df_copy.dropna(subset=["date"])

        # 补齐可选列，使用INSERT OR REPLACE实现幂等写入
        target_columns = [
            "symbol",
            "date",
            "open",
            "high",
            "low",
            "close",
            "volume",
            "amount",
            "amplitude",
            "pct_change",
            "change_amount",
            "turnover",
        ]
        for col in target_columns:
            if col not in df_copy.columns:
                df_copy[col] = None

        df_copy = (
            df_copy[target_columns]
            .drop_duplicates(subset=["symbol", "date"], keep="last")
            .reset_index(drop=True)
        )

        sql = """
            INSERT OR REPLACE INTO daily_data
            (symbol, date, open, high, low, close, volume, amount, amplitude, pct_change, change_amount, turnover)
            VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
        """
        with self._get_connection() as conn:
            conn.executemany(sql, list(df_copy.itertuples(index=False, name=None)))
            conn.commit()

    def get_daily_data(
        self,
        symbol: str,
        start_date: Optional[str] = None,
        end_date: Optional[str] = None,
    ) -> pd.DataFrame:
        """获取日线数据"""
        query = "SELECT * FROM daily_data WHERE symbol = ?"
        params = [symbol]

        if start_date:
            query += " AND date >= ?"
            params.append(start_date)
        if end_date:
            query += " AND date <= ?"
            params.append(end_date)

        query += " ORDER BY date"

        with self._get_connection() as conn:
            df = pd.read_sql_query(query, conn, params=params)
            if not df.empty:
                parsed_date = pd.to_datetime(
                    df["date"], format="mixed", utc=True, errors="coerce"
                )
                df["date"] = parsed_date.dt.tz_localize(None).dt.normalize()
                df = df.dropna(subset=["date"])
                # 兼容历史数据中同一天存在多种日期格式（YYYY-MM-DD / YYYY-MM-DD HH:MM:SS）
                df = df.drop_duplicates(subset=["date"], keep="last")
                df = df.sort_values("date").reset_index(drop=True)
            return df

    def save_indicators(self, symbol: str, df: pd.DataFrame):
        """保存技术指标数据"""
        if df.empty:
            return

        df_copy = df.copy()
        df_copy["symbol"] = symbol

        with self._get_connection() as conn:
            df_copy.to_sql("indicators", conn, if_exists="append", index=False)

    def get_indicators(
        self,
        symbol: str,
        start_date: Optional[str] = None,
        end_date: Optional[str] = None,
    ) -> pd.DataFrame:
        """获取技术指标数据"""
        query = "SELECT * FROM indicators WHERE symbol = ?"
        params = [symbol]

        if start_date:
            query += " AND date >= ?"
            params.append(start_date)
        if end_date:
            query += " AND date <= ?"
            params.append(end_date)

        query += " ORDER BY date"

        with self._get_connection() as conn:
            df = pd.read_sql_query(query, conn, params=params)
            return df

    def save_signal(self, signal_data: Dict[str, Any]):
        """保存交易信号"""
        with self._get_connection() as conn:
            cursor = conn.cursor()
            cursor.execute(
                """
                INSERT INTO signals 
                (symbol, date, strategy, signal, confidence, price, notes)
                VALUES (?, ?, ?, ?, ?, ?, ?)
            """,
                (
                    signal_data["symbol"],
                    signal_data["date"],
                    signal_data["strategy"],
                    signal_data["signal"],
                    signal_data.get("confidence"),
                    signal_data.get("price"),
                    signal_data.get("notes", ""),
                ),
            )
            conn.commit()

    def get_signals(
        self,
        symbol: Optional[str] = None,
        strategy: Optional[str] = None,
        start_date: Optional[str] = None,
        end_date: Optional[str] = None,
        limit: int = 100,
    ) -> pd.DataFrame:
        """获取交易信号"""
        query = "SELECT * FROM signals WHERE 1=1"
        params = []

        if symbol:
            query += " AND symbol = ?"
            params.append(symbol)
        if strategy:
            query += " AND strategy = ?"
            params.append(strategy)
        if start_date:
            query += " AND date >= ?"
            params.append(start_date)
        if end_date:
            query += " AND date <= ?"
            params.append(end_date)

        query += f" ORDER BY created_time DESC LIMIT {limit}"

        with self._get_connection() as conn:
            df = pd.read_sql_query(query, conn, params=params)
            return df

    def get_stock_list(self, market: Optional[str] = None) -> pd.DataFrame:
        """获取股票列表"""
        query = "SELECT * FROM stock_info WHERE 1=1"
        params = []

        if market:
            query += " AND market = ?"
            params.append(market)

        with self._get_connection() as conn:
            df = pd.read_sql_query(query, conn, params=params)
            return df

    def get_last_update_date(self, symbol: str) -> Optional[str]:
        """获取股票最后更新日期"""
        with self._get_connection() as conn:
            cursor = conn.cursor()
            cursor.execute(
                """
                SELECT MAX(date) FROM daily_data WHERE symbol = ?
            """,
                (symbol,),
            )
            result = cursor.fetchone()
            return result[0] if result and result[0] else None

    def delete_old_data(self, days: int = 30):
        """删除过期数据"""
        cutoff_date = (datetime.now() - pd.Timedelta(days=days)).strftime("%Y-%m-%d")

        with self._get_connection() as conn:
            cursor = conn.cursor()
            cursor.execute("DELETE FROM signals WHERE date < ?", (cutoff_date,))
            conn.commit()


# 全局数据库实例
db = DatabaseManager()
