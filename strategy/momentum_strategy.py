import pandas as pd
import numpy as np
from typing import Dict, Any

from strategy.base_strategy import BaseStrategy


class MomentumStrategy(BaseStrategy):
    """动量策略 - 追涨杀跌"""

    def __init__(self, params: Dict[str, Any] = None):
        default_params = {
            "momentum_period": 10,
            "ma_period": 20,
            "threshold": 0.03,  # 动量阈值
            "stop_loss": 0.05,
            "take_profit": 0.10,
            "max_position": 0.3,
        }
        if params:
            default_params.update(params)
        super().__init__("Momentum", default_params)

    def _calculate_momentum(self, df: pd.DataFrame) -> pd.DataFrame:
        """计算动量指标"""
        result = df.copy()
        period = self.params["momentum_period"]
        ma_period = self.params["ma_period"]

        # 价格动量（N日收益率）
        result["momentum"] = result["close"].pct_change(period)

        # 移动平均线
        result["ma"] = result["close"].rolling(window=ma_period).mean()

        # 价格相对均线的位置
        result["price_ma_ratio"] = (result["close"] - result["ma"]) / result["ma"]

        # 成交量动量
        result["volume_ma"] = result["volume"].rolling(window=period).mean()
        result["volume_ratio"] = result["volume"] / result["volume_ma"]

        return result

    def generate_signals(self, df: pd.DataFrame) -> pd.DataFrame:
        """生成动量信号"""
        result = self._calculate_momentum(df)
        threshold = self.params["threshold"]

        result["signal"] = 0
        result["position"] = 0

        # 动量转正且价格在均线上方 - 买入
        result.loc[
            (result["momentum"] > threshold)
            & (result["close"] > result["ma"])
            & (result["volume_ratio"] > 1.2),
            "signal",
        ] = 1

        # 动量转负或跌破均线 - 卖出
        result.loc[
            (result["momentum"] < -threshold) | (result["close"] < result["ma"] * 0.95),
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
        """获取当前动量信号"""
        min_period = max(self.params["momentum_period"], self.params["ma_period"])
        if len(df) < min_period:
            return {"signal": "HOLD", "confidence": 0, "reason": "数据不足"}

        result = self._calculate_momentum(df)
        latest = result.iloc[-1]
        prev = result.iloc[-2] if len(result) > 1 else latest

        threshold = self.params["threshold"]
        momentum = latest["momentum"]
        price = latest["close"]
        ma = latest["ma"]
        volume_ratio = latest["volume_ratio"]
        momentum_strength = abs(momentum) / max(threshold, 1e-9)
        ma_deviation = abs(price - ma) / max(abs(ma), 1e-9)

        signal_type = "HOLD"
        confidence = self.scale_confidence(
            min(1.0, momentum_strength * 0.5 + ma_deviation * 5),
            lower=0.33,
            upper=0.68,
        )
        reasons = []

        # 判断动量信号
        if momentum > threshold and price > ma:
            signal_type = "BUY"
            confidence = self.scale_confidence(
                min(1.0, momentum_strength), lower=0.62, upper=0.9
            )
            reasons.append(f"动量强劲 ({momentum:.2%})")
            if volume_ratio > 1.5:
                confidence += min(0.08, (volume_ratio - 1.5) * 0.1)
                reasons.append(f"成交量放大 ({volume_ratio:.2f}倍)")
            if price > ma:
                reasons.append(f"价格在均线上方")
        elif momentum < -threshold or price < ma * 0.97:
            signal_type = "SELL"
            confidence = self.scale_confidence(
                min(1.0, momentum_strength), lower=0.62, upper=0.9
            )
            reasons.append(f"动量转弱 ({momentum:.2%})")
            if price < ma:
                reasons.append(f"跌破均线")
        else:
            if momentum > 0:
                reasons.append(f"动量较弱 ({momentum:.2%})")
            else:
                reasons.append(f"动量中性 ({momentum:.2%})")

        return {
            "signal": signal_type,
            "confidence": self.clamp_confidence(confidence),
            "price": price,
            "momentum": momentum,
            "ma": ma,
            "volume_ratio": volume_ratio,
            "reason": "; ".join(reasons),
        }
