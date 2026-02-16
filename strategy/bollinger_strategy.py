import pandas as pd
import numpy as np
from typing import Dict, Any

from strategy.base_strategy import BaseStrategy


class BollingerStrategy(BaseStrategy):
    """布林带突破策略"""

    def __init__(self, params: Dict[str, Any] = None):
        default_params = {
            "period": 20,
            "std_dev": 2.0,
            "stop_loss": 0.05,
            "take_profit": 0.15,
            "max_position": 0.3,
        }
        if params:
            default_params.update(params)
        super().__init__("Bollinger", default_params)

    def _calculate_bollinger(self, df: pd.DataFrame) -> pd.DataFrame:
        """计算布林带"""
        result = df.copy()
        period = self.params["period"]
        std_dev = self.params["std_dev"]

        result["boll_mid"] = result["close"].rolling(window=period).mean()
        rolling_std = result["close"].rolling(window=period).std()
        result["boll_upper"] = result["boll_mid"] + (rolling_std * std_dev)
        result["boll_lower"] = result["boll_mid"] - (rolling_std * std_dev)
        result["boll_width"] = (result["boll_upper"] - result["boll_lower"]) / result[
            "boll_mid"
        ]
        result["boll_position"] = (result["close"] - result["boll_lower"]) / (
            result["boll_upper"] - result["boll_lower"]
        )

        return result

    def generate_signals(self, df: pd.DataFrame) -> pd.DataFrame:
        """生成布林带信号"""
        result = self._calculate_bollinger(df)

        result["signal"] = 0
        result["position"] = 0

        # 突破上轨买入
        result.loc[
            (result["close"] > result["boll_upper"])
            & (result["close"].shift(1) <= result["boll_upper"].shift(1)),
            "signal",
        ] = 1

        # 跌破下轨卖出
        result.loc[
            (result["close"] < result["boll_lower"])
            & (result["close"].shift(1) >= result["boll_lower"].shift(1)),
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
        """获取当前布林带信号"""
        if len(df) < self.params["period"]:
            return {"signal": "HOLD", "confidence": 0, "reason": "数据不足"}

        result = self._calculate_bollinger(df)
        latest = result.iloc[-1]
        prev = result.iloc[-2] if len(result) > 1 else latest

        price = latest["close"]
        upper = latest["boll_upper"]
        lower = latest["boll_lower"]
        mid = latest["boll_mid"]
        band_width = max(upper - lower, 1e-9)
        band_position = min(1.0, max(0.0, (price - lower) / band_width))
        edge_bias = abs(band_position - 0.5) * 2

        signal_type = "HOLD"
        confidence = self.scale_confidence(edge_bias, lower=0.35, upper=0.68)
        reasons = []

        # 判断突破
        if price > upper:
            signal_type = "BUY"
            breakout_strength = min(1.0, (price - upper) / max(abs(upper), 1e-9) * 12)
            confidence = self.scale_confidence(breakout_strength, lower=0.62, upper=0.9)
            reasons.append(f"价格上破布林带上轨 ({price:.2f} > {upper:.2f})")
        elif price < lower:
            signal_type = "SELL"
            breakout_strength = min(1.0, (lower - price) / max(abs(lower), 1e-9) * 12)
            confidence = self.scale_confidence(breakout_strength, lower=0.62, upper=0.9)
            reasons.append(f"价格下破布林带下轨 ({price:.2f} < {lower:.2f})")
        else:
            # 在布林带内部
            if prev["close"] <= prev["boll_lower"] and price > lower:
                signal_type = "BUY"
                rebound_strength = min(
                    1.0, abs(price - prev["close"]) / max(abs(prev["close"]), 1e-9) * 20
                )
                confidence = self.scale_confidence(
                    min(1.0, rebound_strength + edge_bias * 0.4),
                    lower=0.6,
                    upper=0.88,
                )
                reasons.append(f"价格从下轨回升 ({prev['close']:.2f} -> {price:.2f})")
            elif prev["close"] >= prev["boll_upper"] and price < upper:
                signal_type = "SELL"
                rebound_strength = min(
                    1.0, abs(price - prev["close"]) / max(abs(prev["close"]), 1e-9) * 20
                )
                confidence = self.scale_confidence(
                    min(1.0, rebound_strength + edge_bias * 0.4),
                    lower=0.6,
                    upper=0.88,
                )
                reasons.append(f"价格从上轨回落 ({prev['close']:.2f} -> {price:.2f})")
            else:
                if band_position > 0.7:
                    reasons.append(f"价格接近上轨 ({band_position:.1%})")
                elif band_position < 0.3:
                    reasons.append(f"价格接近下轨 ({band_position:.1%})")
                else:
                    reasons.append(f"价格在布林带中部 ({band_position:.1%})")

        return {
            "signal": signal_type,
            "confidence": self.clamp_confidence(confidence),
            "price": price,
            "boll_upper": upper,
            "boll_mid": mid,
            "boll_lower": lower,
            "reason": "; ".join(reasons),
        }
