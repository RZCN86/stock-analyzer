import pandas as pd
import numpy as np
from typing import Optional, Dict, Any, List


class TechnicalIndicators:
    """技术指标计算类"""

    @staticmethod
    def calculate_ma(
        df: pd.DataFrame, periods: List[int] = [5, 10, 20, 30, 60]
    ) -> pd.DataFrame:
        """计算移动平均线"""
        result = df.copy()

        for period in periods:
            result[f"ma{period}"] = result["close"].rolling(window=period).mean()

        return result

    @staticmethod
    def calculate_macd(
        df: pd.DataFrame, fast: int = 12, slow: int = 26, signal: int = 9
    ) -> pd.DataFrame:
        """计算MACD指标"""
        result = df.copy()

        # 计算EMA
        ema_fast = result["close"].ewm(span=fast, adjust=False).mean()
        ema_slow = result["close"].ewm(span=slow, adjust=False).mean()

        # MACD线
        result["macd_dif"] = ema_fast - ema_slow
        # 信号线
        result["macd_dea"] = result["macd_dif"].ewm(span=signal, adjust=False).mean()
        # MACD柱状图
        result["macd_histogram"] = (result["macd_dif"] - result["macd_dea"]) * 2

        return result

    @staticmethod
    def calculate_rsi(df: pd.DataFrame, period: int = 14) -> pd.DataFrame:
        """计算RSI指标"""
        result = df.copy()

        # 计算价格变化
        delta = result["close"].diff()

        # 分离上涨和下跌
        gain = delta.where(delta > 0, 0)
        loss = (-delta).where(delta < 0, 0)

        # 计算平均上涨和下跌
        avg_gain = gain.rolling(window=period).mean()
        avg_loss = loss.rolling(window=period).mean()

        # 计算RS和RSI
        rs = avg_gain / avg_loss
        result["rsi"] = 100 - (100 / (1 + rs))

        return result

    @staticmethod
    def calculate_kdj(
        df: pd.DataFrame, k_period: int = 9, d_period: int = 3, j_period: int = 3
    ) -> pd.DataFrame:
        """计算KDJ指标"""
        result = df.copy()

        # 计算最低价和最高价的滚动值
        low_list = result["low"].rolling(window=k_period, min_periods=k_period).min()
        high_list = result["high"].rolling(window=k_period, min_periods=k_period).max()

        # 计算RSV
        rsv = (result["close"] - low_list) / (high_list - low_list) * 100

        # 计算K、D、J值
        result["kdj_k"] = rsv.ewm(com=d_period - 1, adjust=False).mean()
        result["kdj_d"] = result["kdj_k"].ewm(com=j_period - 1, adjust=False).mean()
        result["kdj_j"] = 3 * result["kdj_k"] - 2 * result["kdj_d"]

        return result

    @staticmethod
    def calculate_bollinger(
        df: pd.DataFrame, period: int = 20, std_dev: float = 2.0
    ) -> pd.DataFrame:
        """计算布林带指标"""
        result = df.copy()

        # 中轨（移动平均线）
        result["boll_mid"] = result["close"].rolling(window=period).mean()

        # 标准差
        rolling_std = result["close"].rolling(window=period).std()

        # 上轨和下轨
        result["boll_upper"] = result["boll_mid"] + (rolling_std * std_dev)
        result["boll_lower"] = result["boll_mid"] - (rolling_std * std_dev)

        # 布林带宽度
        result["boll_width"] = (result["boll_upper"] - result["boll_lower"]) / result[
            "boll_mid"
        ]

        return result

    @staticmethod
    def calculate_volume_ma(
        df: pd.DataFrame, periods: List[int] = [5, 10, 20]
    ) -> pd.DataFrame:
        """计算成交量移动平均线"""
        result = df.copy()

        for period in periods:
            result[f"volume_ma{period}"] = (
                result["volume"].rolling(window=period).mean()
            )

        return result

    @staticmethod
    def calculate_atr(df: pd.DataFrame, period: int = 14) -> pd.DataFrame:
        """计算ATR（平均真实波幅）"""
        result = df.copy()

        # 计算真实波幅
        high_low = result["high"] - result["low"]
        high_close = np.abs(result["high"] - result["close"].shift())
        low_close = np.abs(result["low"] - result["close"].shift())

        ranges = pd.concat([high_low, high_close, low_close], axis=1)
        true_range = np.max(ranges, axis=1)

        # ATR
        result["atr"] = true_range.rolling(window=period).mean()

        return result

    @staticmethod
    def calculate_all(df: pd.DataFrame) -> pd.DataFrame:
        """计算所有技术指标"""
        result = df.copy()

        # 计算各类指标
        result = TechnicalIndicators.calculate_ma(result)
        result = TechnicalIndicators.calculate_macd(result)
        result = TechnicalIndicators.calculate_rsi(result)
        result = TechnicalIndicators.calculate_kdj(result)
        result = TechnicalIndicators.calculate_bollinger(result)
        result = TechnicalIndicators.calculate_volume_ma(result)
        result = TechnicalIndicators.calculate_atr(result)

        return result

    @staticmethod
    def get_signal_summary(df: pd.DataFrame) -> Dict[str, Any]:
        """获取技术指标信号汇总"""
        if df.empty:
            return {}

        latest = df.iloc[-1]

        signals = {
            "ma_trend": "UP" if latest["close"] > latest.get("ma20", 0) else "DOWN",
            "macd_signal": "BUY"
            if latest.get("macd_dif", 0) > latest.get("macd_dea", 0)
            else "SELL",
            "rsi_signal": "OVERSOLD"
            if latest.get("rsi", 50) < 30
            else ("OVERBOUGHT" if latest.get("rsi", 50) > 70 else "NEUTRAL"),
            "kdj_signal": "BUY"
            if latest.get("kdj_k", 0) > latest.get("kdj_d", 0)
            else "SELL",
            "boll_position": "UPPER"
            if latest["close"] > latest.get("boll_upper", float("inf"))
            else (
                "LOWER" if latest["close"] < latest.get("boll_lower", 0) else "MIDDLE"
            ),
        }

        return signals
