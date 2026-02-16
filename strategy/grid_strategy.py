import pandas as pd
import numpy as np
from typing import Dict, Any, List, Tuple

from strategy.base_strategy import BaseStrategy


class GridStrategy(BaseStrategy):
    """网格交易策略 - 在价格区间内低买高卖"""

    def __init__(self, params: Dict[str, Any] = None):
        default_params = {
            "grid_levels": 5,  # 网格层数
            "grid_spacing": 0.02,  # 网格间距 (2%)
            "grid_type": "arithmetic",  # 网格类型: arithmetic(等差) / geometric(等比)
            "base_price_period": 20,  # 基准价格计算周期
            "trailing_stop": True,  # 是否启用移动止损
            "stop_loss": 0.10,  # 整体止损比例
            "take_profit": 0.15,  # 整体止盈比例
            "max_position": 0.5,  # 最大仓位
        }
        if params:
            default_params.update(params)
        super().__init__("Grid", default_params)

        # 网格状态
        self.grid_prices: List[float] = []  # 网格价格
        self.last_trade_price: float = None
        self.total_trades: int = 0

    def _calculate_grid_levels(self, df: pd.DataFrame) -> pd.DataFrame:
        """计算网格水平"""
        result = df.copy()
        period = self.params["base_price_period"]

        # 基准价格 (N日均价)
        result["base_price"] = result["close"].rolling(window=period).mean()

        # 计算网格价格
        spacing = self.params["grid_spacing"]
        levels = self.params["grid_levels"]

        for i in range(levels):
            # 上轨
            result[f"grid_upper_{i}"] = result["base_price"] * (1 + spacing * (i + 1))
            # 下轨
            result[f"grid_lower_{i}"] = result["base_price"] * (1 - spacing * (i + 1))

        # 当前价格相对基准的网格位置
        result["grid_position"] = (result["close"] - result["base_price"]) / result[
            "base_price"
        ]

        return result

    def generate_signals(self, df: pd.DataFrame) -> pd.DataFrame:
        """生成网格交易信号"""
        result = self._calculate_grid_levels(df)
        spacing = self.params["grid_spacing"]

        result["signal"] = 0
        result["position"] = 0
        result["grid_trade"] = False
        result["grid_level"] = -1

        position = 0
        last_buy_price = None

        for i in range(1, len(result)):
            current_price = result["close"].iloc[i]
            prev_price = result["close"].iloc[i - 1]
            base_price = result["base_price"].iloc[i]

            if pd.isna(base_price):
                result.loc[result.index[i], "position"] = position
                continue

            # 计算当前网格层级
            price_deviation = (current_price - base_price) / base_price
            grid_level = int(abs(price_deviation) / spacing)

            result.loc[result.index[i], "grid_level"] = min(
                grid_level, self.params["grid_levels"] - 1
            )

            # 网格买入逻辑: 价格下跌进入新网格
            if position < self.params["max_position"]:
                for level in range(self.params["grid_levels"]):
                    lower_price = base_price * (1 - spacing * (level + 1))

                    # 价格跌破网格下轨且上一周期在上方
                    if current_price <= lower_price and prev_price > lower_price:
                        if position == 0 or (
                            last_buy_price
                            and current_price <= last_buy_price * (1 - spacing)
                        ):
                            result.loc[result.index[i], "signal"] = 1
                            result.loc[result.index[i], "grid_trade"] = True
                            position += 1 / self.params["grid_levels"]
                            last_buy_price = current_price
                            self.total_trades += 1
                            break

            # 网格卖出逻辑: 价格上涨到上一买入网格的上方
            if position > 0 and last_buy_price:
                upper_target = last_buy_price * (1 + spacing)

                # 整体止盈
                if current_price >= last_buy_price * (1 + self.params["take_profit"]):
                    result.loc[result.index[i], "signal"] = -1
                    position = 0
                    last_buy_price = None
                # 网格卖出
                elif current_price >= upper_target:
                    result.loc[result.index[i], "signal"] = -1
                    result.loc[result.index[i], "grid_trade"] = True
                    position = max(0, position - 1 / self.params["grid_levels"])
                    if position == 0:
                        last_buy_price = None
                    self.total_trades += 1

            # 整体止损
            if (
                position > 0
                and last_buy_price
                and current_price <= last_buy_price * (1 - self.params["stop_loss"])
            ):
                result.loc[result.index[i], "signal"] = -1
                position = 0
                last_buy_price = None

            result.loc[result.index[i], "position"] = min(position, 1.0)

        return result

    def get_current_signal(self, df: pd.DataFrame) -> Dict[str, Any]:
        """获取当前网格信号"""
        if len(df) < self.params["base_price_period"]:
            return {"signal": "HOLD", "confidence": 0, "reason": "数据不足"}

        result = self._calculate_grid_levels(df)
        latest = result.iloc[-1]

        price = latest["close"]
        base_price = latest["base_price"]

        if pd.isna(base_price):
            return {"signal": "HOLD", "confidence": 0, "reason": "基准价格计算中"}

        spacing = self.params["grid_spacing"]
        deviation = (price - base_price) / base_price
        grid_level = int(abs(deviation) / spacing)
        deviation_strength = min(1.0, abs(deviation) / max(spacing, 1e-9))

        signal_type = "HOLD"
        confidence = self.scale_confidence(deviation_strength, lower=0.34, upper=0.68)
        reasons = []

        # 判断网格位置
        if deviation < -spacing:
            signal_type = "BUY"
            confidence = self.scale_confidence(
                min(1.0, abs(deviation) / max(spacing * 2, 1e-9)),
                lower=0.55,
                upper=0.82,
            )
            reasons.append(
                f"价格低于基准 {abs(deviation):.2%} (网格{min(grid_level, self.params['grid_levels'] - 1)})"
            )
            reasons.append(f"建议网格买入")
        elif deviation > spacing:
            signal_type = "SELL"
            confidence = self.scale_confidence(
                min(1.0, abs(deviation) / max(spacing * 2, 1e-9)),
                lower=0.55,
                upper=0.82,
            )
            reasons.append(f"价格高于基准 {deviation:.2%}")
            reasons.append(f"建议网格卖出")
        else:
            reasons.append(f"价格在基准附近 ({deviation:.2%})")
            reasons.append("等待网格触发")

        # 计算网格价格
        grid_prices = []
        for i in range(self.params["grid_levels"]):
            buy_price = base_price * (1 - spacing * (i + 1))
            sell_price = base_price * (1 + spacing * (i + 1))
            grid_prices.append(
                {"level": i, "buy": round(buy_price, 2), "sell": round(sell_price, 2)}
            )

        return {
            "signal": signal_type,
            "confidence": self.clamp_confidence(confidence),
            "price": price,
            "base_price": base_price,
            "deviation": deviation,
            "grid_level": min(grid_level, self.params["grid_levels"] - 1),
            "grid_prices": grid_prices,
            "total_trades": self.total_trades,
            "reason": "; ".join(reasons),
        }

    def reset_grid(self):
        """重置网格状态"""
        self.grid_prices = []
        self.last_trade_price = None
        self.total_trades = 0
