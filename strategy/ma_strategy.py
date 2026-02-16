import pandas as pd
import numpy as np
from typing import Dict, Any

from strategy.base_strategy import BaseStrategy
from strategy.confidence_calculator import ConfidenceCalculator


class MACrossStrategy(BaseStrategy):
    """双均线交叉策略"""

    def __init__(self, params: Dict[str, Any] = None):
        default_params = {
            "short_window": 5,
            "long_window": 20,
            "stop_loss": 0.05,
            "take_profit": 0.10,
            "max_position": 0.3,
        }
        if params:
            default_params.update(params)
        super().__init__("MA_Cross", default_params)

    def generate_signals(self, df: pd.DataFrame) -> pd.DataFrame:
        """生成均线交叉信号"""
        result = df.copy()
        short_window = self.params["short_window"]
        long_window = self.params["long_window"]

        # 计算均线
        result[f"ma{short_window}"] = (
            result["close"].rolling(window=short_window).mean()
        )
        result[f"ma{long_window}"] = result["close"].rolling(window=long_window).mean()

        # 生成信号
        result["signal"] = 0
        result["position"] = 0

        # 金叉: 短期均线上穿长期均线
        result.loc[
            (result[f"ma{short_window}"] > result[f"ma{long_window}"])
            & (
                result[f"ma{short_window}"].shift(1)
                <= result[f"ma{long_window}"].shift(1)
            ),
            "signal",
        ] = 1

        # 死叉: 短期均线下穿长期均线
        result.loc[
            (result[f"ma{short_window}"] < result[f"ma{long_window}"])
            & (
                result[f"ma{short_window}"].shift(1)
                >= result[f"ma{long_window}"].shift(1)
            ),
            "signal",
        ] = -1

        # 计算持仓状态
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
        """获取当前信号 - 使用置信度计算器"""
        if len(df) < self.params["long_window"]:
            return {"signal": "HOLD", "confidence": 0, "reason": "数据不足"}

        result = self.generate_signals(df)
        latest = result.iloc[-1]
        prev = result.iloc[-2] if len(result) > 1 else latest

        short_window = self.params["short_window"]
        long_window = self.params["long_window"]

        ma_short_col = f"ma{short_window}"
        ma_long_col = f"ma{long_window}"

        reasons = []

        # 使用置信度计算器计算交叉信号
        signal_type, confidence = ConfidenceCalculator.calculate_crossover_confidence(
            fast_value=latest[ma_short_col],
            slow_value=latest[ma_long_col],
            prev_fast=prev[ma_short_col],
            prev_slow=prev[ma_long_col],
            fast_series=result[ma_short_col].tail(10) if len(result) >= 10 else None,
            slow_series=result[ma_long_col].tail(10) if len(result) >= 10 else None,
        )

        # 根据偏离度调整置信度
        if signal_type == "HOLD":
            # 没有交叉，计算趋势强度
            deviation = (
                abs(latest[ma_short_col] - latest[ma_long_col]) / latest[ma_long_col]
            )
            if latest[ma_short_col] > latest[ma_long_col]:
                confidence = min(0.7, 0.5 + deviation * 3)
                reasons.append(
                    f"MA{short_window}在MA{long_window}上方，偏离度{deviation:.2%}"
                )
            else:
                confidence = max(0.3, 0.5 - deviation * 3)
                reasons.append(
                    f"MA{short_window}在MA{long_window}下方，偏离度{deviation:.2%}"
                )
        else:
            # 有交叉信号
            if signal_type == "BUY":
                reasons.append(f"MA{short_window}金叉MA{long_window}")
                # 多头排列加成
                if latest["close"] > latest[ma_short_col] > latest[ma_long_col]:
                    confidence = min(0.95, confidence + 0.05)
                    reasons.append("价格多头排列")
            else:
                reasons.append(f"MA{short_window}死叉MA{long_window}")
                # 空头排列加成
                if latest["close"] < latest[ma_short_col] < latest[ma_long_col]:
                    confidence = min(0.95, confidence + 0.05)
                    reasons.append("价格空头排列")

        # 根据波动性调整
        confidence = ConfidenceCalculator.adjust_confidence_by_volatility(
            confidence, result["close"]
        )

        return {
            "signal": signal_type,
            "confidence": round(self.clamp_confidence(confidence), 4),
            "price": latest["close"],
            "ma_short": latest[ma_short_col],
            "ma_long": latest[ma_long_col],
            "reason": "; ".join(reasons),
        }
