import pandas as pd
import numpy as np
from typing import Dict, Any

from strategy.base_strategy import BaseStrategy


class BreakoutStrategy(BaseStrategy):
    """突破策略 - 突破近期高点买入，跌破近期低点卖出"""

    def __init__(self, params: Dict[str, Any] = None):
        default_params = {
            "lookback_period": 20,
            "breakout_threshold": 0.02,  # 突破阈值
            "volume_confirm": True,  # 是否需成交量确认
            "stop_loss": 0.05,
            "take_profit": 0.15,
            "max_position": 0.3,
        }
        if params:
            default_params.update(params)
        super().__init__("Breakout", default_params)

    def _calculate_breakout_levels(self, df: pd.DataFrame) -> pd.DataFrame:
        """计算突破水平"""
        result = df.copy()
        period = self.params["lookback_period"]

        # 近期高点和低点
        result["recent_high"] = result["high"].rolling(window=period).max()
        result["recent_low"] = result["low"].rolling(window=period).min()

        # 突破水平（含阈值）
        threshold = self.params["breakout_threshold"]
        result["breakout_high"] = result["recent_high"] * (1 + threshold)
        result["breakout_low"] = result["recent_low"] * (1 - threshold)

        # 成交量均值
        result["volume_ma"] = result["volume"].rolling(window=period).mean()

        # ATR（平均真实波幅）
        high_low = result["high"] - result["low"]
        high_close = np.abs(result["high"] - result["close"].shift())
        low_close = np.abs(result["low"] - result["close"].shift())
        tr = pd.concat([high_low, high_close, low_close], axis=1).max(axis=1)
        result["atr"] = tr.rolling(window=14).mean()

        return result

    def generate_signals(self, df: pd.DataFrame) -> pd.DataFrame:
        """生成突破信号"""
        result = self._calculate_breakout_levels(df)
        volume_confirm = self.params["volume_confirm"]

        result["signal"] = 0
        result["position"] = 0

        # 突破近期高点买入
        breakout_buy = result["close"] > result["breakout_high"]
        if volume_confirm:
            breakout_buy = breakout_buy & (result["volume"] > result["volume_ma"] * 1.2)

        result.loc[breakout_buy, "signal"] = 1

        # 跌破近期低点卖出
        breakout_sell = result["close"] < result["breakout_low"]
        result.loc[breakout_sell, "signal"] = -1

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
        """获取当前突破信号"""
        if len(df) < self.params["lookback_period"]:
            return {"signal": "HOLD", "confidence": 0, "reason": "数据不足"}

        result = self._calculate_breakout_levels(df)
        latest = result.iloc[-1]
        prev = result.iloc[-2] if len(result) > 1 else latest

        price = latest["close"]
        recent_high = latest["recent_high"]
        recent_low = latest["recent_low"]
        volume_ratio = (
            latest["volume"] / latest["volume_ma"] if latest["volume_ma"] > 0 else 1
        )

        signal_type = "HOLD"
        range_width = max(recent_high - recent_low, price * 1e-9)
        center = (recent_high + recent_low) / 2
        range_pressure = min(1.0, abs(price - center) / (range_width / 2))
        confidence = self.scale_confidence(range_pressure, lower=0.35, upper=0.65)
        reasons = []

        # 判断突破状态
        if price > latest["breakout_high"]:
            signal_type = "BUY"
            breakout_strength = min(
                1.0, (price - latest["breakout_high"]) / max(abs(recent_high), 1e-9) * 8
            )
            confidence = self.scale_confidence(breakout_strength, lower=0.62, upper=0.92)
            reasons.append(f"价格上破近期高点 ({price:.2f} > {recent_high:.2f})")
            if volume_ratio > 1.3:
                confidence += min(0.08, (volume_ratio - 1.3) * 0.1)
                reasons.append(f"成交量确认 ({volume_ratio:.2f}倍)")
        elif price < latest["breakout_low"]:
            signal_type = "SELL"
            breakout_strength = min(
                1.0, (latest["breakout_low"] - price) / max(abs(recent_low), 1e-9) * 8
            )
            confidence = self.scale_confidence(breakout_strength, lower=0.62, upper=0.92)
            reasons.append(f"价格下破近期低点 ({price:.2f} < {recent_low:.2f})")
        else:
            # 计算距离突破点的远近
            to_high = (recent_high - price) / price
            to_low = (price - recent_low) / price

            if to_high < 0.02:
                reasons.append(f"接近近期高点 ({to_high:.2%})")
            elif to_low < 0.02:
                reasons.append(f"接近近期低点 ({to_low:.2%})")
            else:
                reasons.append(
                    f"价格在区间内 (高:{recent_high:.2f} 低:{recent_low:.2f})"
                )

        return {
            "signal": signal_type,
            "confidence": self.clamp_confidence(confidence),
            "price": price,
            "recent_high": recent_high,
            "recent_low": recent_low,
            "volume_ratio": volume_ratio,
            "reason": "; ".join(reasons),
        }
