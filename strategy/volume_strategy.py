import pandas as pd
import numpy as np
from typing import Dict, Any

from strategy.base_strategy import BaseStrategy


class VolumeStrategy(BaseStrategy):
    """成交量策略 - 基于成交量变化"""

    def __init__(self, params: Dict[str, Any] = None):
        default_params = {
            "volume_ma_period": 20,
            "volume_surge_threshold": 1.5,  # 放量阈值
            "volume_shrink_threshold": 0.7,  # 缩量阈值
            "price_change_threshold": 0.02,  # 价格变化阈值
            "stop_loss": 0.05,
            "take_profit": 0.10,
            "max_position": 0.3,
        }
        if params:
            default_params.update(params)
        super().__init__("Volume", default_params)

    def _calculate_volume_indicators(self, df: pd.DataFrame) -> pd.DataFrame:
        """计算成交量指标"""
        result = df.copy()
        period = self.params["volume_ma_period"]

        # 成交量移动平均
        result["volume_ma"] = result["volume"].rolling(window=period).mean()
        result["volume_ratio"] = result["volume"] / result["volume_ma"]

        # 成交量变化率
        result["volume_change"] = result["volume"].pct_change()

        # OBV (On Balance Volume)
        obv = [0]
        for i in range(1, len(result)):
            if result["close"].iloc[i] > result["close"].iloc[i - 1]:
                obv.append(obv[-1] + result["volume"].iloc[i])
            elif result["close"].iloc[i] < result["close"].iloc[i - 1]:
                obv.append(obv[-1] - result["volume"].iloc[i])
            else:
                obv.append(obv[-1])
        result["obv"] = obv

        # 价格变化
        result["price_change"] = result["close"].pct_change()

        return result

    def generate_signals(self, df: pd.DataFrame) -> pd.DataFrame:
        """生成成交量信号"""
        result = self._calculate_volume_indicators(df)
        surge_threshold = self.params["volume_surge_threshold"]
        price_threshold = self.params["price_change_threshold"]

        result["signal"] = 0
        result["position"] = 0

        # 放量上涨 - 买入
        result.loc[
            (result["volume_ratio"] > surge_threshold)
            & (result["price_change"] > price_threshold),
            "signal",
        ] = 1

        # 放量下跌 - 卖出
        result.loc[
            (result["volume_ratio"] > surge_threshold)
            & (result["price_change"] < -price_threshold),
            "signal",
        ] = -1

        # 计算持仓
        position = 0
        positions = []
        for idx, row in result.iterrows():
            if row["signal"] == 1:
                position = 1
            elif row["signal"] == -1:
                position = 0
            positions.append(position)
        result["position"] = positions

        return result

    def get_current_signal(self, df: pd.DataFrame) -> Dict[str, Any]:
        """获取当前成交量信号"""
        if len(df) < self.params["volume_ma_period"]:
            return {"signal": "HOLD", "confidence": 0, "reason": "数据不足"}

        result = self._calculate_volume_indicators(df)
        latest = result.iloc[-1]
        prev = result.iloc[-2] if len(result) > 1 else latest

        volume_ratio = latest["volume_ratio"]
        price_change = latest["price_change"]
        surge_threshold = self.params["volume_surge_threshold"]
        shrink_threshold = self.params["volume_shrink_threshold"]
        price_threshold = self.params["price_change_threshold"]
        volume_anomaly = abs(volume_ratio - 1.0)
        price_pressure = abs(price_change) / max(price_threshold, 1e-9)

        signal_type = "HOLD"
        confidence = self.scale_confidence(
            min(1.0, volume_anomaly * 0.7 + price_pressure * 0.3),
            lower=0.33,
            upper=0.68,
        )
        reasons = []

        # 判断成交量信号
        if volume_ratio > surge_threshold:
            if price_change > price_threshold:
                signal_type = "BUY"
                signal_strength = min(
                    1.0,
                    (volume_ratio - surge_threshold) / max(surge_threshold, 1e-9)
                    + abs(price_change) / max(price_threshold, 1e-9) * 0.4,
                )
                confidence = self.scale_confidence(signal_strength, lower=0.62, upper=0.88)
                reasons.append(f"放量上涨 ({volume_ratio:.2f}倍, {price_change:.2%})")
            elif price_change < -price_threshold:
                signal_type = "SELL"
                signal_strength = min(
                    1.0,
                    (volume_ratio - surge_threshold) / max(surge_threshold, 1e-9)
                    + abs(price_change) / max(price_threshold, 1e-9) * 0.4,
                )
                confidence = self.scale_confidence(signal_strength, lower=0.62, upper=0.88)
                reasons.append(f"放量下跌 ({volume_ratio:.2f}倍, {price_change:.2%})")
            else:
                reasons.append(f"成交量放大 ({volume_ratio:.2f}倍)")
        elif volume_ratio < shrink_threshold:
            reasons.append(f"成交量萎缩 ({volume_ratio:.2f}倍)")
            if abs(price_change) < 0.01:
                reasons.append("价格横盘，可能变盘")
        else:
            reasons.append(f"成交量正常 ({volume_ratio:.2f}倍)")

        # OBV趋势
        obv_trend = "UP" if latest["obv"] > prev["obv"] else "DOWN"
        if obv_trend == "UP":
            reasons.append("OBV上升")
        else:
            reasons.append("OBV下降")

        return {
            "signal": signal_type,
            "confidence": self.clamp_confidence(confidence),
            "price": latest["close"],
            "volume_ratio": volume_ratio,
            "volume": latest["volume"],
            "obv": latest["obv"],
            "reason": "; ".join(reasons),
        }
