import pandas as pd
import numpy as np
from typing import Dict, Any

from strategy.base_strategy import BaseStrategy


class KDJStrategy(BaseStrategy):
    """KDJ随机指标策略"""

    def __init__(self, params: Dict[str, Any] = None):
        default_params = {
            "k_period": 9,
            "d_period": 3,
            "j_period": 3,
            "oversold": 20,  # KDJ超卖线
            "overbought": 80,  # KDJ超买线
            "stop_loss": 0.05,
            "take_profit": 0.10,
            "max_position": 0.3,
        }
        if params:
            default_params.update(params)
        super().__init__("KDJ", default_params)

    def _calculate_kdj(self, df: pd.DataFrame) -> pd.DataFrame:
        """计算KDJ指标"""
        result = df.copy()
        k_period = self.params["k_period"]
        d_period = self.params["d_period"]
        j_period = self.params["j_period"]

        # 计算 RSV (Raw Stochastic Value)
        low_list = result["low"].rolling(window=k_period, min_periods=k_period).min()
        high_list = result["high"].rolling(window=k_period, min_periods=k_period).max()
        rsv = (result["close"] - low_list) / (high_list - low_list) * 100

        # 计算 K、D、J值
        result["kdj_k"] = rsv.ewm(com=d_period - 1, adjust=False).mean()
        result["kdj_d"] = result["kdj_k"].ewm(com=j_period - 1, adjust=False).mean()
        result["kdj_j"] = 3 * result["kdj_k"] - 2 * result["kdj_d"]

        return result

    def generate_signals(self, df: pd.DataFrame) -> pd.DataFrame:
        """生成KDJ信号"""
        result = self._calculate_kdj(df)
        oversold = self.params["oversold"]
        overbought = self.params["overbought"]

        result["signal"] = 0
        result["position"] = 0

        # K线上穿D线且J值在低位 - 买入
        result.loc[
            (result["kdj_k"] > result["kdj_d"])
            & (result["kdj_k"].shift(1) <= result["kdj_d"].shift(1))
            & (result["kdj_j"] < 50),
            "signal",
        ] = 1

        # K线下穿D线或J值过高 - 卖出
        result.loc[
            (result["kdj_k"] < result["kdj_d"])
            & (result["kdj_k"].shift(1) >= result["kdj_d"].shift(1))
            | (result["kdj_j"] > overbought),
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
        """获取当前KDJ信号"""
        if len(df) < self.params["k_period"]:
            return {"signal": "HOLD", "confidence": 0, "reason": "数据不足"}

        result = self._calculate_kdj(df)
        latest = result.iloc[-1]
        prev = result.iloc[-2] if len(result) > 1 else latest

        oversold = self.params["oversold"]
        overbought = self.params["overbought"]

        k = latest["kdj_k"]
        d = latest["kdj_d"]
        j = latest["kdj_j"]
        spread_strength = min(1.0, abs(k - d) / 25)
        j_extreme = min(1.0, abs(j - 50) / 50)

        signal_type = "HOLD"
        confidence = self.scale_confidence(
            min(1.0, spread_strength * 0.6 + j_extreme * 0.4), lower=0.32, upper=0.7
        )
        reasons = []

        # 判断KDJ金叉死叉
        if k > d:
            if prev["kdj_k"] <= prev["kdj_d"]:
                signal_type = "BUY"
                low_j_bonus = min(1.0, max(0.0, 30 - j) / 30)
                confidence = self.scale_confidence(
                    min(1.0, spread_strength + low_j_bonus * 0.7),
                    lower=0.65,
                    upper=0.95,
                )
                reasons.append(f"KDJ金叉 (K:{k:.1f}, D:{d:.1f})")
                if j < 30:
                    reasons.append(f"J值低位 ({j:.1f})")
            else:
                if j < oversold:
                    signal_type = "BUY"
                    oversold_strength = min(1.0, (oversold - j) / max(oversold, 1))
                    confidence = self.scale_confidence(
                        min(1.0, oversold_strength * 0.8 + spread_strength * 0.4),
                        lower=0.58,
                        upper=0.88,
                    )
                    reasons.append(f"KDJ超卖区 (J:{j:.1f})")
                else:
                    reasons.append(f"K线在D线上方 (K:{k:.1f}, D:{d:.1f})")
        else:
            if prev["kdj_k"] >= prev["kdj_d"]:
                signal_type = "SELL"
                high_j_bonus = min(1.0, max(0.0, j - 70) / 30)
                confidence = self.scale_confidence(
                    min(1.0, spread_strength + high_j_bonus * 0.7),
                    lower=0.65,
                    upper=0.95,
                )
                reasons.append(f"KDJ死叉 (K:{k:.1f}, D:{d:.1f})")
            else:
                if j > overbought:
                    signal_type = "SELL"
                    overbought_strength = min(
                        1.0, (j - overbought) / max(100 - overbought, 1)
                    )
                    confidence = self.scale_confidence(
                        min(1.0, overbought_strength * 0.8 + spread_strength * 0.4),
                        lower=0.58,
                        upper=0.88,
                    )
                    reasons.append(f"KDJ超买区 (J:{j:.1f})")
                else:
                    reasons.append(f"K线在D线下方 (K:{k:.1f}, D:{d:.1f})")

        return {
            "signal": signal_type,
            "confidence": self.clamp_confidence(confidence),
            "price": latest["close"],
            "kdj_k": k,
            "kdj_d": d,
            "kdj_j": j,
            "reason": "; ".join(reasons),
        }
