import pandas as pd
import numpy as np
from typing import Dict, Any

from strategy.base_strategy import BaseStrategy
from strategy.confidence_calculator import ConfidenceCalculator


class MACDStrategy(BaseStrategy):
    """MACD策略"""

    def __init__(self, params: Dict[str, Any] = None):
        default_params = {
            "fast": 12,
            "slow": 26,
            "signal": 9,
            "stop_loss": 0.05,
            "take_profit": 0.10,
            "max_position": 0.3,
        }
        if params:
            default_params.update(params)
        super().__init__("MACD", default_params)

    def _calculate_macd(self, df: pd.DataFrame) -> pd.DataFrame:
        """计算MACD指标"""
        result = df.copy()
        fast = self.params["fast"]
        slow = self.params["slow"]
        signal_period = self.params["signal"]

        # EMA
        ema_fast = result["close"].ewm(span=fast, adjust=False).mean()
        ema_slow = result["close"].ewm(span=slow, adjust=False).mean()

        result["macd_dif"] = ema_fast - ema_slow
        result["macd_dea"] = (
            result["macd_dif"].ewm(span=signal_period, adjust=False).mean()
        )
        result["macd_histogram"] = (result["macd_dif"] - result["macd_dea"]) * 2

        return result

    def generate_signals(self, df: pd.DataFrame) -> pd.DataFrame:
        """生成MACD信号"""
        result = self._calculate_macd(df)

        result["signal"] = 0
        result["position"] = 0

        # MACD金叉: DIF上穿DEA且MACD>0
        result.loc[
            (result["macd_dif"] > result["macd_dea"])
            & (result["macd_dif"].shift(1) <= result["macd_dea"].shift(1))
            & (result["macd_histogram"] > 0),
            "signal",
        ] = 1

        # MACD死叉: DIF下穿DEA
        result.loc[
            (result["macd_dif"] < result["macd_dea"])
            & (result["macd_dif"].shift(1) >= result["macd_dea"].shift(1)),
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
        """获取当前MACD信号 - 使用置信度计算器"""
        if len(df) < self.params["slow"]:
            return {"signal": "HOLD", "confidence": 0, "reason": "数据不足"}

        result = self._calculate_macd(df)
        latest = result.iloc[-1]
        prev = result.iloc[-2] if len(result) > 1 else latest

        # 使用置信度计算器计算交叉信号
        signal_type, confidence = ConfidenceCalculator.calculate_crossover_confidence(
            fast_value=latest["macd_dif"],
            slow_value=latest["macd_dea"],
            prev_fast=prev["macd_dif"],
            prev_slow=prev["macd_dea"],
            fast_series=result["macd_dif"].tail(10) if len(result) >= 10 else None,
            slow_series=result["macd_dea"].tail(10) if len(result) >= 10 else None,
        )

        reasons = []
        macd_strength = abs(latest["macd_histogram"])

        if signal_type == "BUY":
            reasons.append("MACD金叉")
            # 柱状图强度加成
            if latest["macd_histogram"] > 0:
                histogram_bonus = min(0.1, macd_strength / 100)
                confidence = min(0.95, confidence + histogram_bonus)
                reasons.append(f"MACD柱状图为正 (强度:{macd_strength:.2f})")
            # 零轴上方金叉更强
            if latest["macd_dif"] > 0 and latest["macd_dea"] > 0:
                confidence = min(0.95, confidence + 0.05)
                reasons.append("零轴上方金叉")
        elif signal_type == "SELL":
            reasons.append("MACD死叉")
            if latest["macd_histogram"] < 0:
                reasons.append(f"MACD柱状图为负 (强度:{macd_strength:.2f})")
            # 零轴下方死叉更强
            if latest["macd_dif"] < 0 and latest["macd_dea"] < 0:
                confidence = min(0.95, confidence + 0.05)
                reasons.append("零轴下方死叉")
        else:
            # 无交叉，根据位置判断
            denom = max(abs(latest["macd_dea"]), abs(latest["macd_dif"]), 1e-9)
            if latest["macd_dif"] > latest["macd_dea"]:
                deviation = (latest["macd_dif"] - latest["macd_dea"]) / denom
                hold_strength = min(1.0, max(0.0, deviation) * 2.5)
                confidence = self.scale_confidence(
                    hold_strength, lower=0.35, upper=0.72
                )
                reasons.append(f"DIF在DEA上方 (偏离:{deviation:.2%})")
            else:
                deviation = (latest["macd_dea"] - latest["macd_dif"]) / denom
                hold_strength = min(1.0, max(0.0, deviation) * 2.5)
                confidence = self.scale_confidence(
                    hold_strength, lower=0.35, upper=0.72
                )
                reasons.append(f"DIF在DEA下方 (偏离:{deviation:.2%})")

        # 检测背离
        if len(df) >= 20:
            divergence_signal, divergence_conf = (
                ConfidenceCalculator.calculate_divergence_confidence(
                    price_series=df["close"].tail(20),
                    indicator_series=result["macd_dif"].tail(20),
                    lookback=20,
                )
            )

            if divergence_signal != "HOLD":
                # 背离信号优先
                if divergence_signal != signal_type:
                    reasons.append(
                        f"检测到{'顶' if divergence_signal == 'SELL' else '底'}背离信号"
                    )
                    # 背离增加置信度但不改变信号，除非原信号也是同向
                    if divergence_signal == signal_type:
                        confidence = min(0.95, confidence + 0.1)

        return {
            "signal": signal_type,
            "confidence": round(self.clamp_confidence(confidence), 4),
            "price": latest["close"],
            "macd_dif": latest["macd_dif"],
            "macd_dea": latest["macd_dea"],
            "macd_histogram": latest["macd_histogram"],
            "reason": "; ".join(reasons),
        }
