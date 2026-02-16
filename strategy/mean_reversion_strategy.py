import pandas as pd
import numpy as np
from typing import Dict, Any

from strategy.base_strategy import BaseStrategy


class MeanReversionStrategy(BaseStrategy):
    """均值回归策略 - 价格偏离均值后回归"""

    def __init__(self, params: Dict[str, Any] = None):
        default_params = {
            "ma_period": 20,
            "std_period": 20,
            "entry_threshold": 2.0,  # 进入阈值（标准差倍数）
            "exit_threshold": 0.5,  # 退出阈值
            "stop_loss": 0.05,
            "take_profit": 0.08,
            "max_position": 0.3,
        }
        if params:
            default_params.update(params)
        super().__init__("MeanReversion", default_params)

    def _calculate_zscore(self, df: pd.DataFrame) -> pd.DataFrame:
        """计算Z-Score（价格偏离度）"""
        result = df.copy()
        ma_period = self.params["ma_period"]
        std_period = self.params["std_period"]

        result["ma"] = result["close"].rolling(window=ma_period).mean()
        result["std"] = result["close"].rolling(window=std_period).std()
        result["zscore"] = (result["close"] - result["ma"]) / result["std"]

        #  RSI作为辅助指标
        delta = result["close"].diff()
        gain = delta.where(delta > 0, 0).rolling(window=14).mean()
        loss = (-delta.where(delta < 0, 0)).rolling(window=14).mean()
        rs = gain / loss
        result["rsi"] = 100 - (100 / (1 + rs))

        return result

    def generate_signals(self, df: pd.DataFrame) -> pd.DataFrame:
        """生成均值回归信号"""
        result = self._calculate_zscore(df)
        entry_threshold = self.params["entry_threshold"]
        exit_threshold = self.params["exit_threshold"]

        result["signal"] = 0
        result["position"] = 0

        # Z-Score低于负阈值 - 超卖买入（预期回归）
        result.loc[
            (result["zscore"] < -entry_threshold) & (result["rsi"] < 30), "signal"
        ] = 1

        # Z-Score高于正阈值 - 超买卖出（预期回归）
        result.loc[
            (result["zscore"] > entry_threshold) & (result["rsi"] > 70), "signal"
        ] = -1

        # 计算持仓
        position = 0
        positions = []
        for idx, row in result.iterrows():
            if row["signal"] == 1:
                position = 1
            elif row["signal"] == -1:
                position = 0
            elif abs(row["zscore"]) < exit_threshold and position != 0:
                # 回归均值时平仓
                position = 0
            positions.append(position)
        result["position"] = positions

        return result

    def get_current_signal(self, df: pd.DataFrame) -> Dict[str, Any]:
        """获取当前均值回归信号"""
        min_period = max(self.params["ma_period"], self.params["std_period"])
        if len(df) < min_period:
            return {"signal": "HOLD", "confidence": 0, "reason": "数据不足"}

        result = self._calculate_zscore(df)
        latest = result.iloc[-1]
        prev = result.iloc[-2] if len(result) > 1 else latest

        entry_threshold = self.params["entry_threshold"]
        zscore = latest["zscore"]
        rsi = latest["rsi"]
        price = latest["close"]
        ma = latest["ma"]
        zscore_strength = abs(zscore) / max(entry_threshold, 1e-9)

        signal_type = "HOLD"
        confidence = self.scale_confidence(
            min(1.0, zscore_strength), lower=0.32, upper=0.7
        )
        reasons = []

        # 判断偏离程度
        if zscore < -entry_threshold:
            signal_type = "BUY"
            confidence = self.scale_confidence(
                min(1.0, zscore_strength / 1.5), lower=0.62, upper=0.9
            )
            reasons.append(f"价格严重偏离均值 (Z-Score: {zscore:.2f})")
            if rsi < 30:
                confidence += min(0.08, (30 - rsi) / 30 * 0.08)
                reasons.append(f"RSI超卖 ({rsi:.1f})")
            reasons.append(f"预期价格回归均线 {ma:.2f}")
        elif zscore > entry_threshold:
            signal_type = "SELL"
            confidence = self.scale_confidence(
                min(1.0, zscore_strength / 1.5), lower=0.62, upper=0.9
            )
            reasons.append(f"价格严重偏离均值 (Z-Score: {zscore:.2f})")
            if rsi > 70:
                confidence += min(0.08, (rsi - 70) / 30 * 0.08)
                reasons.append(f"RSI超买 ({rsi:.1f})")
            reasons.append(f"预期价格回归均线 {ma:.2f}")
        else:
            if abs(zscore) > 1.5:
                if zscore < 0:
                    reasons.append(f"价格略低于均值 (Z-Score: {zscore:.2f})")
                else:
                    reasons.append(f"价格略高于均值 (Z-Score: {zscore:.2f})")
            else:
                reasons.append(f"价格在正常区间 (Z-Score: {zscore:.2f})")

        return {
            "signal": signal_type,
            "confidence": self.clamp_confidence(confidence),
            "price": price,
            "ma": ma,
            "zscore": zscore,
            "rsi": rsi,
            "reason": "; ".join(reasons),
        }
