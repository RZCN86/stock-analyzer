import tempfile
import unittest
from unittest.mock import patch

import numpy as np
import pandas as pd

import main
from database.db_manager import DatabaseManager
from fetcher.akshare_fetcher import AKShareFetcher
from strategy.bollinger_strategy import BollingerStrategy
from strategy.breakout_strategy import BreakoutStrategy
from strategy.engine import StrategyEngine
from strategy.grid_strategy import GridStrategy
from strategy.kdj_strategy import KDJStrategy
from strategy.mean_reversion_strategy import MeanReversionStrategy
from strategy.momentum_strategy import MomentumStrategy
from strategy.volume_strategy import VolumeStrategy
from utils.helpers import setup_logging


def _sample_daily_df():
    return pd.DataFrame(
        {
            "date": [pd.Timestamp("2026-02-13")],
            "open": [10.0],
            "high": [10.5],
            "low": [9.8],
            "close": [10.2],
            "volume": [100000],
            "pct_change": [1.0],
            "change_amount": [0.1],
        }
    )


class DummyDB:
    def __init__(self, *, local_has_data=False, last_date=None):
        self.local_has_data = local_has_data
        self.last_date = last_date
        self.saved = []

    def get_daily_data(self, symbol, start_date=None, end_date=None):
        if start_date is None and end_date is None and self.local_has_data:
            return _sample_daily_df()
        return pd.DataFrame()

    def get_last_update_date(self, symbol):
        return self.last_date

    def save_daily_data(self, symbol, df):
        self.saved.append((symbol, len(df)))


class DummyAKFetcher:
    def __init__(self, daily_df=None, etf_df=None):
        self.daily_calls = []
        self.etf_calls = []
        self.daily_df = _sample_daily_df() if daily_df is None else daily_df
        self.etf_df = _sample_daily_df() if etf_df is None else etf_df

    def fetch_daily_data(self, symbol, start_date=None, end_date=None):
        self.daily_calls.append((symbol, start_date, end_date))
        return self.daily_df

    def fetch_etf_data(self, symbol, start_date=None, end_date=None):
        self.etf_calls.append((symbol, start_date, end_date))
        return self.etf_df


class DummyUSFetcher:
    def fetch_daily_data(self, symbol, start_date=None, end_date=None):
        return _sample_daily_df()


class RegressionTests(unittest.TestCase):
    def test_fetch_and_store_handles_last_date_with_time(self):
        dummy_db = DummyDB(local_has_data=True, last_date="2026-02-13 00:00:00")
        dummy_ak = DummyAKFetcher()

        with patch.object(main, "db", dummy_db):
            analyzer = main.StockAnalyzer()
            analyzer.ak_fetcher = dummy_ak
            analyzer.us_fetcher = DummyUSFetcher()
            analyzer.fetch_and_store("000001", market="A")

        self.assertEqual(dummy_ak.daily_calls[0][1], "2026-02-14")

    def test_fetch_and_store_supports_etf_market(self):
        dummy_db = DummyDB(local_has_data=False, last_date=None)
        dummy_ak = DummyAKFetcher()

        with patch.object(main, "db", dummy_db):
            analyzer = main.StockAnalyzer()
            analyzer.ak_fetcher = dummy_ak
            analyzer.us_fetcher = DummyUSFetcher()
            df = analyzer.fetch_and_store(
                "510300", market="ETF", start_date="2024-01-01", end_date="2024-12-31"
            )

        self.assertFalse(df.empty)
        self.assertEqual(len(dummy_ak.etf_calls), 1)
        self.assertEqual(dummy_ak.etf_calls[0][0], "510300")

    def test_fetch_and_store_falls_back_to_local_data_when_increment_is_empty(self):
        dummy_db = DummyDB(local_has_data=True, last_date="2026-02-13 00:00:00")
        dummy_ak = DummyAKFetcher(daily_df=pd.DataFrame())

        with patch.object(main, "db", dummy_db):
            analyzer = main.StockAnalyzer()
            analyzer.ak_fetcher = dummy_ak
            analyzer.us_fetcher = DummyUSFetcher()
            df = analyzer.fetch_and_store("000001", market="A")

        self.assertFalse(df.empty)
        self.assertEqual(len(df), 1)

    def test_fetch_and_store_normalizes_symbol_input(self):
        dummy_db = DummyDB(local_has_data=False, last_date=None)
        dummy_ak = DummyAKFetcher()

        with patch.object(main, "db", dummy_db):
            analyzer = main.StockAnalyzer()
            analyzer.ak_fetcher = dummy_ak
            analyzer.us_fetcher = DummyUSFetcher()
            analyzer.fetch_and_store(
                " 518880 ", market="ETF", start_date="2024-01-01", end_date="2024-12-31"
            )

        self.assertEqual(dummy_ak.etf_calls[0][0], "518880")

    def test_save_daily_data_is_idempotent_for_same_symbol_and_date(self):
        with tempfile.NamedTemporaryFile(suffix=".db") as f:
            manager = DatabaseManager(db_path=f.name)

            df = pd.DataFrame(
                {
                    "date": [pd.Timestamp("2026-02-13 00:00:00-05:00")],
                    "open": [190.0],
                    "high": [192.0],
                    "low": [189.0],
                    "close": [191.0],
                    "volume": [1000],
                    "pct_change": [0.5],
                    "change_amount": [1.0],
                }
            )

            manager.save_daily_data("AAPL", df)
            manager.save_daily_data("AAPL", df)

            rows = manager.get_daily_data("AAPL")
            self.assertEqual(len(rows), 1)

    def test_get_daily_data_handles_mixed_date_formats_and_deduplicates_by_day(self):
        with tempfile.NamedTemporaryFile(suffix=".db") as f:
            manager = DatabaseManager(db_path=f.name)

            with manager._get_connection() as conn:
                conn.executemany(
                    """
                    INSERT INTO daily_data
                    (symbol, date, open, high, low, close, volume)
                    VALUES (?, ?, ?, ?, ?, ?, ?)
                    """,
                    [
                        ("510300", "2026-02-12", 10.0, 10.2, 9.8, 10.1, 1000),
                        ("510300", "2026-02-12 00:00:00", 10.0, 10.2, 9.8, 10.1, 1000),
                        ("510300", "2026-02-13", 10.1, 10.3, 9.9, 10.2, 1100),
                        ("510300", "2026-02-13 00:00:00", 10.1, 10.3, 9.9, 10.2, 1100),
                    ],
                )
                conn.commit()

            rows = manager.get_daily_data("510300")
            self.assertEqual(rows["date"].isna().sum(), 0)
            self.assertEqual(len(rows), 2)
            self.assertEqual(
                rows["date"].dt.strftime("%Y-%m-%d").tolist(),
                ["2026-02-12", "2026-02-13"],
            )

    def test_fetch_stock_list_tolerates_missing_industry_column(self):
        sh = pd.DataFrame({"代码": ["600000"], "名称": ["浦发银行"]})
        sz = pd.DataFrame({"代码": ["000001"], "名称": ["平安银行"]})

        with (
            patch("fetcher.akshare_fetcher.ak.stock_sh_a_spot_em", return_value=sh),
            patch("fetcher.akshare_fetcher.ak.stock_sz_a_spot_em", return_value=sz),
        ):
            fetcher = AKShareFetcher()
            result = fetcher.fetch_stock_list()

        self.assertEqual(len(result), 2)
        self.assertIn("industry", result.columns)

    def test_setup_logging_closes_previous_file_handler(self):
        with tempfile.NamedTemporaryFile(suffix=".log") as f:
            logger = setup_logging(log_file=f.name)
            old_file_handler = next(
                h for h in logger.handlers if h.__class__.__name__ == "FileHandler"
            )

            setup_logging(log_file=f.name)

            self.assertTrue(old_file_handler.stream is None)

    def test_fetch_etf_data_falls_back_to_sina_when_em_empty(self):
        em_empty = pd.DataFrame()
        sina_df = pd.DataFrame(
            {
                "date": ["2026-02-12", "2026-02-13"],
                "open": [10.1, 10.2],
                "high": [10.3, 10.4],
                "low": [10.0, 10.1],
                "close": [10.2, 10.3],
                "volume": [10000, 11000],
                "amount": [100000, 110000],
            }
        )

        with (
            patch("fetcher.akshare_fetcher.ak.fund_etf_hist_em", return_value=em_empty),
            patch("fetcher.akshare_fetcher.ak.fund_etf_hist_sina", return_value=sina_df) as mock_sina,
        ):
            fetcher = AKShareFetcher()
            result = fetcher.fetch_etf_data("518880")

        self.assertFalse(result.empty)
        self.assertEqual(mock_sina.call_args.kwargs["symbol"], "sh518880")
        self.assertIn("pct_change", result.columns)
        self.assertIn("change_amount", result.columns)


class ConfidenceRegressionTests(unittest.TestCase):
    def _dummy_input_df(self, rows=80):
        dates = pd.date_range("2025-01-01", periods=rows, freq="B")
        close = np.linspace(100, 102, rows)
        return pd.DataFrame(
            {
                "date": dates,
                "open": close,
                "high": close * 1.01,
                "low": close * 0.99,
                "close": close,
                "volume": np.full(rows, 1_000_000.0),
            }
        )

    def _assert_hold_confidence_changes(
        self, strategy, calc_method, scenario_a: pd.DataFrame, scenario_b: pd.DataFrame
    ):
        input_df = self._dummy_input_df()

        with patch.object(strategy, calc_method, return_value=scenario_a):
            conf_a = strategy.get_current_signal(input_df)["confidence"]
            signal_a = strategy.get_current_signal(input_df)["signal"]

        with patch.object(strategy, calc_method, return_value=scenario_b):
            conf_b = strategy.get_current_signal(input_df)["confidence"]
            signal_b = strategy.get_current_signal(input_df)["signal"]

        self.assertEqual(signal_a, "HOLD")
        self.assertEqual(signal_b, "HOLD")
        self.assertNotEqual(conf_a, conf_b)

    def test_hold_confidence_is_dynamic_for_breakout_bollinger_and_momentum(self):
        breakout = BreakoutStrategy()
        breakout_a = pd.DataFrame(
            [
                {
                    "close": 100.0,
                    "high": 110.0,
                    "low": 90.0,
                    "volume": 1_000_000.0,
                    "recent_high": 110.0,
                    "recent_low": 90.0,
                    "breakout_high": 112.2,
                    "breakout_low": 88.2,
                    "volume_ma": 1_000_000.0,
                },
                {
                    "close": 101.0,
                    "high": 110.0,
                    "low": 90.0,
                    "volume": 1_000_000.0,
                    "recent_high": 110.0,
                    "recent_low": 90.0,
                    "breakout_high": 112.2,
                    "breakout_low": 88.2,
                    "volume_ma": 1_000_000.0,
                },
            ]
        )
        breakout_b = breakout_a.copy()
        breakout_b.loc[1, "close"] = 109.5
        self._assert_hold_confidence_changes(
            breakout, "_calculate_breakout_levels", breakout_a, breakout_b
        )

        bollinger = BollingerStrategy()
        bollinger_a = pd.DataFrame(
            [
                {
                    "close": 100.0,
                    "boll_upper": 110.0,
                    "boll_lower": 90.0,
                    "boll_mid": 100.0,
                },
                {
                    "close": 100.2,
                    "boll_upper": 110.0,
                    "boll_lower": 90.0,
                    "boll_mid": 100.0,
                },
            ]
        )
        bollinger_b = bollinger_a.copy()
        bollinger_b.loc[1, "close"] = 108.8
        self._assert_hold_confidence_changes(
            bollinger, "_calculate_bollinger", bollinger_a, bollinger_b
        )

        momentum = MomentumStrategy()
        momentum_a = pd.DataFrame(
            [
                {"close": 100.0, "momentum": 0.005, "ma": 99.8, "volume_ratio": 1.0},
                {"close": 100.3, "momentum": 0.006, "ma": 100.0, "volume_ratio": 1.1},
            ]
        )
        momentum_b = momentum_a.copy()
        momentum_b.loc[1, "momentum"] = 0.028
        self._assert_hold_confidence_changes(
            momentum, "_calculate_momentum", momentum_a, momentum_b
        )

    def test_hold_confidence_is_dynamic_for_mean_reversion_kdj_volume_and_grid(self):
        mean_rev = MeanReversionStrategy()
        mean_a = pd.DataFrame(
            [
                {"close": 100.0, "zscore": 0.2, "rsi": 50.0, "ma": 100.0},
                {"close": 100.4, "zscore": 0.3, "rsi": 52.0, "ma": 100.1},
            ]
        )
        mean_b = mean_a.copy()
        mean_b.loc[1, "zscore"] = 1.8
        self._assert_hold_confidence_changes(
            mean_rev, "_calculate_zscore", mean_a, mean_b
        )

        kdj = KDJStrategy()
        kdj_a = pd.DataFrame(
            [
                {"close": 100.0, "kdj_k": 53.0, "kdj_d": 50.0, "kdj_j": 56.0},
                {"close": 100.2, "kdj_k": 54.0, "kdj_d": 51.0, "kdj_j": 57.0},
            ]
        )
        kdj_b = kdj_a.copy()
        kdj_b.loc[1, "kdj_k"] = 63.0
        kdj_b.loc[1, "kdj_j"] = 72.0
        self._assert_hold_confidence_changes(kdj, "_calculate_kdj", kdj_a, kdj_b)

        volume = VolumeStrategy()
        volume_a = pd.DataFrame(
            [
                {
                    "close": 100.0,
                    "volume_ratio": 1.0,
                    "price_change": 0.001,
                    "obv": 100_000.0,
                    "volume": 1_000_000.0,
                },
                {
                    "close": 100.2,
                    "volume_ratio": 1.05,
                    "price_change": 0.002,
                    "obv": 101_000.0,
                    "volume": 1_050_000.0,
                },
            ]
        )
        volume_b = volume_a.copy()
        volume_b.loc[1, "volume_ratio"] = 1.45
        volume_b.loc[1, "price_change"] = 0.018
        self._assert_hold_confidence_changes(
            volume, "_calculate_volume_indicators", volume_a, volume_b
        )

        grid = GridStrategy()
        grid_a = pd.DataFrame(
            [
                {"close": 100.0, "base_price": 100.0},
                {"close": 100.4, "base_price": 100.0},
            ]
        )
        grid_b = grid_a.copy()
        grid_b.loc[1, "close"] = 101.8
        self._assert_hold_confidence_changes(grid, "_calculate_grid_levels", grid_a, grid_b)

    def test_engine_hold_confidence_uses_strategy_outputs(self):
        class HoldStrategyA:
            def __init__(self, params=None):
                pass

            def get_current_signal(self, df):
                return {"signal": "HOLD", "confidence": 0.33, "reason": "A"}

        class HoldStrategyB:
            def __init__(self, params=None):
                pass

            def get_current_signal(self, df):
                return {"signal": "HOLD", "confidence": 0.69, "reason": "B"}

        engine = StrategyEngine()
        engine.strategies = {"s1": HoldStrategyA, "s2": HoldStrategyB}
        engine.active_strategies = {}

        result = engine.analyze(self._dummy_input_df(), strategy_names=["s1", "s2"])
        self.assertEqual(result["final_signal"], "HOLD")
        self.assertAlmostEqual(result["confidence"], 0.51, places=2)

    def test_engine_clamps_strategy_confidence_to_unit_interval(self):
        class BuyStrategy:
            def __init__(self, params=None):
                pass

            def get_current_signal(self, df):
                return {"signal": "BUY", "confidence": 1.4, "reason": "over"}

        class SellStrategy:
            def __init__(self, params=None):
                pass

            def get_current_signal(self, df):
                return {"signal": "SELL", "confidence": -0.2, "reason": "under"}

        engine = StrategyEngine()
        engine.strategies = {"buy": BuyStrategy, "sell": SellStrategy}
        engine.active_strategies = {}

        result = engine.analyze(self._dummy_input_df(), strategy_names=["buy", "sell"])
        self.assertGreaterEqual(result["confidence"], 0.0)
        self.assertLessEqual(result["confidence"], 1.0)


if __name__ == "__main__":
    unittest.main()
