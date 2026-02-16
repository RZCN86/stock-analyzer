import pandas as pd
import numpy as np
from typing import Dict, Any

from strategy.base_strategy import BaseStrategy
from strategy.confidence_calculator import ConfidenceCalculator


class RSIStrategy(BaseStrategy):
    """RSI超买卖策略"""

    def __init__(self, params: Dict[str, Any] = None):
        default_params = {
            "period": 14,
            "oversold": 30,
            "overbought": 70,
            "stop_loss": 0.05,
            "take_profit": 0.10,
            "max_position": 0.3,
        }
        if params:
            default_params.update(params)
        super().__init__("RSI", default_params)

    def _calculate_rsi(self, df: pd.DataFrame) -> pd.DataFrame:
        """计算RSI"""
        result = df.copy()
        period = self.params["period"]

        delta = result["close"].diff()
        gain = delta.where(delta > 0, 0)
        loss = (-delta).where(delta < 0, 0)

        avg_gain = gain.rolling(window=period).mean()
        avg_loss = loss.rolling(window=period).mean()

        rs = avg_gain / avg_loss
        result["rsi"] = 100 - (100 / (1 + rs))

        return result

    def generate_signals(self, df: pd.DataFrame) -> pd.DataFrame:
        """生成RSI信号"""
        result = self._calculate_rsi(df)
        oversold = self.params["oversold"]
        overbought = self.params["overbought"]

        result["signal"] = 0
        result["position"] = 0

        # RSI上穿超卖线（从超卖区回到正常区）买入
        result.loc[
            (result["rsi"] > oversold) & (result["rsi"].shift(1) <= oversold), "signal"
        ] = 1

        # RSI下穿超买线（从超买区回到正常区）卖出
        result.loc[
            (result["rsi"] < overbought) & (result["rsi"].shift(1) >= overbought),
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
        """获取当前RSI信号 - 使用置信度计算器"""
        if len(df) < self.params["period"]:
            return {"signal": "HOLD", "confidence": 0, "reason": "数据不足"}

        result = self._calculate_rsi(df)
        latest = result.iloc[-1]
        prev = result.iloc[-2] if len(result) > 1 else latest

        oversold = self.params["oversold"]
        overbought = self.params["overbought"]

        rsi_value = latest["rsi"]

        # 使用置信度计算器计算极端值置信度
        signal_type, confidence = ConfidenceCalculator.calculate_extreme_confidence(
            value=rsi_value,
            lower_bound=oversold,
            upper_bound=overbought,
            recent_values=result["rsi"].tail(10) if len(result) >= 10 else None,
            mean_reversion=True,  # RSI是均值回归指标
        )

        reasons = []

        # 细化原因描述
        if rsi_value < oversold:
            extreme_degree = (oversold - rsi_value) / oversold
            reasons.append(
                f"RSI超卖 ({rsi_value:.2f} < {oversold}, 极度:{extreme_degree:.1%})"
            )

            # 从超卖区回升确认
            if prev["rsi"] < rsi_value:
                confidence = min(0.95, confidence + 0.05)
                reasons.append(f"RSI开始回升 ({prev['rsi']:.2f} -> {rsi_value:.2f})")

        elif rsi_value > overbought:
            extreme_degree = (rsi_value - overbought) / (100 - overbought)
            reasons.append(
                f"RSI超买 ({rsi_value:.2f} > {overbought}, 极度:{extreme_degree:.1%})"
            )

            # 从超买区回落确认
            if prev["rsi"] > rsi_value:
                confidence = min(0.95, confidence + 0.05)
                reasons.append(f"RSI开始回落 ({prev['rsi']:.2f} -> {rsi_value:.2f})")

        else:
            # 在区间内
            position = (rsi_value - oversold) / (overbought - oversold)

            if prev["rsi"] <= oversold and rsi_value > oversold:
                signal_type = "BUY"
                rebound_strength = min(
                    1.0,
                    (rsi_value - oversold) / max(overbought - oversold, 1e-9)
                    + abs(rsi_value - prev["rsi"]) / 20,
                )
                confidence = self.scale_confidence(
                    rebound_strength, lower=0.62, upper=0.88
                )
                reasons.append(
                    f"RSI从超卖区回升 ({prev['rsi']:.2f} -> {rsi_value:.2f})"
                )
            elif prev["rsi"] >= overbought and rsi_value < overbought:
                signal_type = "SELL"
                rebound_strength = min(
                    1.0,
                    (overbought - rsi_value) / max(overbought - oversold, 1e-9)
                    + abs(rsi_value - prev["rsi"]) / 20,
                )
                confidence = self.scale_confidence(
                    rebound_strength, lower=0.62, upper=0.88
                )
                reasons.append(
                    f"RSI从超买区回落 ({prev['rsi']:.2f} -> {rsi_value:.2f})"
                )
            else:
                # 在区间内，根据位置给出不同程度的倾向
                if position < 0.3:
                    signal_type = "BUY"
                    confidence = 0.5 + (0.3 - position) * 0.3
                    reasons.append(
                        f"RSI接近超卖区 ({rsi_value:.2f}, 位置:{position:.1%})"
                    )
                elif position > 0.7:
                    signal_type = "SELL"
                    confidence = 0.5 + (position - 0.7) * 0.3
                    reasons.append(
                        f"RSI接近超买区 ({rsi_value:.2f}, 位置:{position:.1%})"
                    )
                else:
                    signal_type = "HOLD"
                    center_bias = abs(position - 0.5) * 2
                    confidence = self.scale_confidence(
                        center_bias, lower=0.32, upper=0.66
                    )
                    reasons.append(
                        f"RSI在合理区间 ({rsi_value:.2f}, 位置:{position:.1%})"
                    )

        # 根据波动性调整
        confidence = ConfidenceCalculator.adjust_confidence_by_volatility(
            confidence, df["close"]
        )

        return {
            "signal": signal_type,
            "confidence": round(self.clamp_confidence(confidence), 4),
            "price": latest["close"],
            "rsi": rsi_value,
            "oversold": oversold,
            "overbought": overbought,
            "reason": "; ".join(reasons),
        }
