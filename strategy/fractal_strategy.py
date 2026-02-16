import pandas as pd
import numpy as np
from typing import Dict, Any

from strategy.base_strategy import BaseStrategy


class FractalStrategy(BaseStrategy):
    """
    分形交易策略 - 基于比尔·威廉姆斯的分形指标

    买入分形：中间K线的低点低于左右各2根K线的低点（看涨反转信号）
    卖出分形：中间K线的高点高于左右各2根K线的高点（看跌反转信号）

    结合趋势过滤：只在趋势方向一致时交易
    """

    def __init__(self, params: Dict[str, Any] = None):
        default_params = {
            "fractal_window": 2,  # 分形窗口大小（左右各n根K线）
            "trend_filter": True,  # 是否使用趋势过滤
            "trend_ma_period": 20,  # 趋势判断均线周期
            "volume_confirm": True,  # 是否需成交量确认
            "stop_loss": 0.05,
            "take_profit": 0.10,
            "max_position": 0.3,
        }
        if params:
            default_params.update(params)
        super().__init__("Fractal", default_params)

    def _calculate_fractals(self, df: pd.DataFrame) -> pd.DataFrame:
        """计算分形指标"""
        result = df.copy()
        window = self.params["fractal_window"]

        # 买入分形（低点分形）：中间低点低于两侧window根K线的低点
        result["bullish_fractal"] = False
        for i in range(window, len(result) - window):
            center_low = result.iloc[i]["low"]
            # 检查左侧window根K线
            left_lows = result.iloc[i - window : i]["low"].values
            # 检查右侧window根K线
            right_lows = result.iloc[i + 1 : i + window + 1]["low"].values

            if all(center_low < left_lows) and all(center_low < right_lows):
                result.iloc[i, result.columns.get_loc("bullish_fractal")] = True

        # 卖出分形（高点分形）：中间高点高于两侧window根K线的高点
        result["bearish_fractal"] = False
        for i in range(window, len(result) - window):
            center_high = result.iloc[i]["high"]
            # 检查左侧window根K线
            left_highs = result.iloc[i - window : i]["high"].values
            # 检查右侧window根K线
            right_highs = result.iloc[i + 1 : i + window + 1]["high"].values

            if all(center_high > left_highs) and all(center_high > right_highs):
                result.iloc[i, result.columns.get_loc("bearish_fractal")] = True

        # 趋势判断
        result["trend_ma"] = (
            result["close"].rolling(window=self.params["trend_ma_period"]).mean()
        )
        result["trend_up"] = result["close"] > result["trend_ma"]

        # 成交量均值
        result["volume_ma"] = result["volume"].rolling(window=20).mean()

        return result

    def generate_signals(self, df: pd.DataFrame) -> pd.DataFrame:
        """生成分形交易信号"""
        result = self._calculate_fractals(df)
        trend_filter = self.params["trend_filter"]
        volume_confirm = self.params["volume_confirm"]

        result["signal"] = 0
        result["position"] = 0

        position = 0
        positions = []

        for idx, row in result.iterrows():
            signal = 0

            # 买入信号：买入分形 + 趋势向上 + 成交量确认
            if row["bullish_fractal"]:
                if not trend_filter or row["trend_up"]:
                    if not volume_confirm or row["volume"] > row["volume_ma"] * 0.8:
                        signal = 1

            # 卖出信号：卖出分形 + 趋势向下 + 成交量确认
            elif row["bearish_fractal"]:
                if not trend_filter or not row["trend_up"]:
                    if not volume_confirm or row["volume"] > row["volume_ma"] * 0.8:
                        signal = -1

            result.at[idx, "signal"] = signal

            # 更新持仓
            if signal == 1:
                position = 1
            elif signal == -1:
                position = 0
            positions.append(position)

        result["position"] = positions
        return result

    def get_current_signal(self, df: pd.DataFrame) -> Dict[str, Any]:
        """获取当前分形信号"""
        window = self.params["fractal_window"]
        min_periods = self.params["trend_ma_period"] + window * 2

        if len(df) < min_periods:
            return {"signal": "HOLD", "confidence": 0, "reason": "数据不足"}

        result = self._calculate_fractals(df)
        latest = result.iloc[-1]
        prev_idx = -2

        # 检查最近的分形信号
        bullish_fractals = result[result["bullish_fractal"]].index
        bearish_fractals = result[result["bearish_fractal"]].index

        last_bullish = bullish_fractals[-1] if len(bullish_fractals) > 0 else None
        last_bearish = bearish_fractals[-1] if len(bearish_fractals) > 0 else None

        price = latest["close"]
        trend_up = latest["trend_up"]
        trend_ma = latest["trend_ma"]
        volume_ratio = (
            latest["volume"] / latest["volume_ma"] if latest["volume_ma"] > 0 else 1
        )

        signal_type = "HOLD"
        confidence = 0.0
        reasons = []

        # 判断信号
        if last_bullish is not None and (
            last_bearish is None or last_bullish > last_bearish
        ):
            # 最近是买入分形
            bars_since_fractal = len(result) - 1 - result.index.get_loc(last_bullish)
            fractal_data = result.loc[last_bullish]

            if bars_since_fractal <= 3:  # 分形形成后3根K线内有效
                signal_type = "BUY"

                # 计算置信度
                # 1. 趋势一致性
                trend_score = 1.0 if trend_up else 0.5

                # 2. 成交量确认
                vol_score = min(1.0, volume_ratio)

                # 3. 距离分形低点的反弹强度
                rebound = (price - fractal_data["low"]) / fractal_data["low"] * 100
                rebound_score = min(1.0, rebound / 2)  # 2%反弹为满分

                # 4. 新鲜度（越近越好）
                freshness = 1.0 - (bars_since_fractal * 0.2)

                confidence = (
                    trend_score * 0.35
                    + vol_score * 0.25
                    + rebound_score * 0.25
                    + freshness * 0.15
                )
                confidence = self.scale_confidence(confidence, lower=0.55, upper=0.90)

                reasons.append(f"检测到买入分形 ({bars_since_fractal}根K线前)")
                if trend_up:
                    reasons.append(
                        f"趋势向上 (价格{price:.2f} > MA{self.params['trend_ma_period']}{trend_ma:.2f})"
                    )
                else:
                    reasons.append(f"趋势向下，但出现反转信号")
                reasons.append(
                    f"分形低点: {fractal_data['low']:.2f}, 当前反弹: {rebound:.2f}%"
                )

            else:
                reasons.append(f"买入分形已过期 ({bars_since_fractal}根K线前)")

        elif last_bearish is not None and (
            last_bullish is None or last_bearish > last_bullish
        ):
            # 最近是卖出分形
            bars_since_fractal = len(result) - 1 - result.index.get_loc(last_bearish)
            fractal_data = result.loc[last_bearish]

            if bars_since_fractal <= 3:
                signal_type = "SELL"

                # 计算置信度
                # 1. 趋势一致性
                trend_score = 1.0 if not trend_up else 0.5

                # 2. 成交量确认
                vol_score = min(1.0, volume_ratio)

                # 3. 距离分形高点的下跌强度
                decline = (fractal_data["high"] - price) / fractal_data["high"] * 100
                decline_score = min(1.0, decline / 2)

                # 4. 新鲜度
                freshness = 1.0 - (bars_since_fractal * 0.2)

                confidence = (
                    trend_score * 0.35
                    + vol_score * 0.25
                    + decline_score * 0.25
                    + freshness * 0.15
                )
                confidence = self.scale_confidence(confidence, lower=0.55, upper=0.90)

                reasons.append(f"检测到卖出分形 ({bars_since_fractal}根K线前)")
                if not trend_up:
                    reasons.append(
                        f"趋势向下 (价格{price:.2f} < MA{self.params['trend_ma_period']}{trend_ma:.2f})"
                    )
                else:
                    reasons.append(f"趋势向上，但出现反转信号")
                reasons.append(
                    f"分形高点: {fractal_data['high']:.2f}, 当前下跌: {decline:.2f}%"
                )

            else:
                reasons.append(f"卖出分形已过期 ({bars_since_fractal}根K线前)")
        else:
            # 无分形信号
            reasons.append("未检测到有效分形信号")
            if trend_up:
                reasons.append(f"趋势向上，寻找买入分形")
            else:
                reasons.append(f"趋势向下，寻找卖出分形")

            # HOLD时的动态置信度
            if trend_up and price > trend_ma:
                confidence = self.scale_confidence(
                    min(1.0, (price - trend_ma) / trend_ma * 10), lower=0.35, upper=0.55
                )
            elif not trend_up and price < trend_ma:
                confidence = self.scale_confidence(
                    min(1.0, (trend_ma - price) / trend_ma * 10), lower=0.35, upper=0.55
                )

        return {
            "signal": signal_type,
            "confidence": self.clamp_confidence(confidence),
            "price": price,
            "trend_ma": trend_ma,
            "trend_up": trend_up,
            "volume_ratio": volume_ratio,
            "last_bullish_fractal": str(last_bullish) if last_bullish else None,
            "last_bearish_fractal": str(last_bearish) if last_bearish else None,
            "reason": "; ".join(reasons),
        }
