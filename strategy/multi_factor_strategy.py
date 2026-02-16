import pandas as pd
import numpy as np
from typing import Dict, Any, List

from strategy.base_strategy import BaseStrategy


class MultiFactorStrategy(BaseStrategy):
    """多因子组合策略 - 综合多个技术指标"""

    def __init__(self, params: Dict[str, Any] = None):
        default_params = {
            # 均线参数
            "ma_short": 5,
            "ma_long": 20,
            # MACD参数
            "macd_fast": 12,
            "macd_slow": 26,
            "macd_signal": 9,
            # RSI参数
            "rsi_period": 14,
            "rsi_oversold": 30,
            "rsi_overbought": 70,
            # 权重配置
            "weight_ma": 0.25,
            "weight_macd": 0.25,
            "weight_rsi": 0.25,
            "weight_trend": 0.25,
            # 信号阈值
            "buy_threshold": 0.6,
            "sell_threshold": 0.4,
            "stop_loss": 0.05,
            "take_profit": 0.10,
            "max_position": 0.3,
        }
        if params:
            default_params.update(params)
        super().__init__("MultiFactor", default_params)

    def _calculate_all_indicators(self, df: pd.DataFrame) -> pd.DataFrame:
        """计算所有指标"""
        result = df.copy()

        # 均线
        result["ma_short"] = (
            result["close"].rolling(window=self.params["ma_short"]).mean()
        )
        result["ma_long"] = (
            result["close"].rolling(window=self.params["ma_long"]).mean()
        )

        # MACD
        ema_fast = (
            result["close"].ewm(span=self.params["macd_fast"], adjust=False).mean()
        )
        ema_slow = (
            result["close"].ewm(span=self.params["macd_slow"], adjust=False).mean()
        )
        result["macd_dif"] = ema_fast - ema_slow
        result["macd_dea"] = (
            result["macd_dif"].ewm(span=self.params["macd_signal"], adjust=False).mean()
        )
        result["macd_histogram"] = (result["macd_dif"] - result["macd_dea"]) * 2

        # RSI
        delta = result["close"].diff()
        gain = (
            delta.where(delta > 0, 0).rolling(window=self.params["rsi_period"]).mean()
        )
        loss = (
            (-delta.where(delta < 0, 0))
            .rolling(window=self.params["rsi_period"])
            .mean()
        )
        rs = gain / loss
        result["rsi"] = 100 - (100 / (1 + rs))

        # 趋势强度（价格相对均线的位置）
        result["trend_strength"] = (result["close"] - result["ma_long"]) / result[
            "ma_long"
        ]

        return result

    def _calculate_factor_score(self, row: pd.Series) -> float:
        """计算多因子得分 (0-1)"""
        score = 0

        # MA因子 (价格在短期均线上方加分)
        if row["close"] > row["ma_short"] > row["ma_long"]:
            score += self.params["weight_ma"]
        elif row["close"] > row["ma_short"]:
            score += self.params["weight_ma"] * 0.5

        # MACD因子
        if row["macd_dif"] > row["macd_dea"] > 0:
            score += self.params["weight_macd"]
        elif row["macd_dif"] > row["macd_dea"]:
            score += self.params["weight_macd"] * 0.5

        # RSI因子 (30-50区间加分最多)
        rsi = row["rsi"]
        if 30 <= rsi <= 50:
            score += self.params["weight_rsi"]
        elif 50 < rsi <= 70:
            score += self.params["weight_rsi"] * 0.5
        elif rsi < 30:
            score += self.params["weight_rsi"] * 0.3

        # 趋势因子
        trend = row["trend_strength"]
        if trend > 0.05:
            score += self.params["weight_trend"]
        elif trend > 0:
            score += self.params["weight_trend"] * 0.5

        return score

    def generate_signals(self, df: pd.DataFrame) -> pd.DataFrame:
        """生成多因子信号"""
        result = self._calculate_all_indicators(df)

        # 计算因子得分
        result["factor_score"] = result.apply(self._calculate_factor_score, axis=1)

        buy_threshold = self.params["buy_threshold"]
        sell_threshold = self.params["sell_threshold"]

        result["signal"] = 0
        result["position"] = 0

        # 得分超过买入阈值 - 买入
        result.loc[result["factor_score"] >= buy_threshold, "signal"] = 1

        # 得分低于卖出阈值 - 卖出
        result.loc[result["factor_score"] <= sell_threshold, "signal"] = -1

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
        """获取当前多因子信号"""
        min_period = max(
            self.params["ma_long"], self.params["macd_slow"], self.params["rsi_period"]
        )
        if len(df) < min_period:
            return {"signal": "HOLD", "confidence": 0, "reason": "数据不足"}

        result = self._calculate_all_indicators(df)
        latest = result.iloc[-1]

        score = self._calculate_factor_score(latest)
        buy_threshold = self.params["buy_threshold"]
        sell_threshold = self.params["sell_threshold"]

        signal_type = "HOLD"
        confidence = self.scale_confidence(
            min(1.0, abs(score - 0.5) * 2), lower=0.3, upper=0.7
        )
        reasons = []

        # 判断信号
        if score >= buy_threshold:
            signal_type = "BUY"
            confidence = self.scale_confidence(score, lower=0.6, upper=0.95)
            reasons.append(f"多因子得分强劲 ({score:.2f})")
        elif score <= sell_threshold:
            signal_type = "SELL"
            confidence = self.scale_confidence(1 - score, lower=0.6, upper=0.95)
            reasons.append(f"多因子得分疲软 ({score:.2f})")
        else:
            reasons.append(f"多因子得分中性 ({score:.2f})")

        # 添加各因子状态
        factor_status = []
        if latest["close"] > latest["ma_short"]:
            factor_status.append("MA强势")
        if latest["macd_dif"] > latest["macd_dea"]:
            factor_status.append("MACD金叉")
        if 30 <= latest["rsi"] <= 70:
            factor_status.append("RSI正常")
        if latest["trend_strength"] > 0:
            factor_status.append("趋势向上")

        if factor_status:
            reasons.append(f"信号来源: {', '.join(factor_status)}")

        return {
            "signal": signal_type,
            "confidence": self.clamp_confidence(confidence),
            "price": latest["close"],
            "factor_score": score,
            "ma_status": "UP" if latest["close"] > latest["ma_short"] else "DOWN",
            "macd_status": "BULL"
            if latest["macd_dif"] > latest["macd_dea"]
            else "BEAR",
            "rsi": latest["rsi"],
            "reason": "; ".join(reasons),
        }
