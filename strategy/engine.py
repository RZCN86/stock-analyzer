import pandas as pd
import numpy as np
from typing import Dict, Any, List, Tuple

from strategy.base_strategy import BaseStrategy
from strategy.ma_strategy import MACrossStrategy
from strategy.macd_strategy import MACDStrategy
from strategy.rsi_strategy import RSIStrategy
from strategy.bollinger_strategy import BollingerStrategy
from strategy.momentum_strategy import MomentumStrategy
from strategy.mean_reversion_strategy import MeanReversionStrategy
from strategy.breakout_strategy import BreakoutStrategy
from strategy.kdj_strategy import KDJStrategy
from strategy.volume_strategy import VolumeStrategy
from strategy.multi_factor_strategy import MultiFactorStrategy
from strategy.grid_strategy import GridStrategy
from strategy.fractal_strategy import FractalStrategy


class StrategyEngine:
    """策略引擎 - 管理所有策略"""

    def __init__(self):
        self.strategies = {
            "ma_cross": MACrossStrategy,
            "macd": MACDStrategy,
            "rsi": RSIStrategy,
            "bollinger": BollingerStrategy,
            "momentum": MomentumStrategy,
            "mean_reversion": MeanReversionStrategy,
            "breakout": BreakoutStrategy,
            "kdj": KDJStrategy,
            "volume": VolumeStrategy,
            "multi_factor": MultiFactorStrategy,
            "grid": GridStrategy,
            "fractal": FractalStrategy,
        }
        self.active_strategies = {}

    @staticmethod
    def _clamp_confidence(confidence: Any) -> float:
        try:
            value = float(confidence)
        except (TypeError, ValueError):
            return 0.0
        return max(0.0, min(1.0, value))

    def add_strategy(self, name: str, strategy_class, params: Dict[str, Any] = None):
        """添加策略"""
        self.strategies[name] = strategy_class
        if params:
            self.active_strategies[name] = strategy_class(params)

    def get_strategy(self, name: str, params: Dict[str, Any] = None):
        """获取策略实例"""
        if name in self.active_strategies:
            return self.active_strategies[name]

        if name in self.strategies:
            strategy = self.strategies[name](params)
            self.active_strategies[name] = strategy
            return strategy

        # 提供更详细的错误信息
        available = ", ".join(self.get_strategy_list())
        raise ValueError(
            f"未知策略: '{name}'\n"
            f"可用策略: {available}\n"
            f"提示: 请检查策略名称拼写，或从上述列表中选择"
        )

    def validate_strategies(
        self, strategy_names: List[str]
    ) -> Tuple[List[str], List[str]]:
        """
        验证策略名称列表

        Returns:
            (有效策略列表, 无效策略列表)
        """
        valid = []
        invalid = []

        for name in strategy_names:
            if name in self.strategies:
                valid.append(name)
            else:
                invalid.append(name)

        return valid, invalid

    def analyze(
        self, df: pd.DataFrame, strategy_names: List[str] = None
    ) -> Dict[str, Any]:
        """使用多个策略分析数据"""
        if strategy_names is None:
            strategy_names = list(self.strategies.keys())

        # 验证策略名称
        valid_strategies, invalid_strategies = self.validate_strategies(strategy_names)

        if invalid_strategies:
            available = ", ".join(self.get_strategy_list())
            error_msg = (
                f"发现无效策略: {', '.join(invalid_strategies)}\n可用策略: {available}"
            )
            return {
                "final_signal": "ERROR",
                "confidence": 0,
                "details": {},
                "error": error_msg,
                "buy_signals": [],
                "sell_signals": [],
            }

        results = {}
        buy_signals = []
        sell_signals = []
        hold_signals = []

        for name in valid_strategies:
            try:
                strategy = self.get_strategy(name)
                signal = strategy.get_current_signal(df)
                signal_confidence = self._clamp_confidence(
                    signal.get("confidence", 0.0)
                )
                signal["confidence"] = signal_confidence
                results[name] = signal

                if signal["signal"] == "BUY":
                    buy_signals.append((name, signal_confidence))
                elif signal["signal"] == "SELL":
                    sell_signals.append((name, signal_confidence))
                elif signal["signal"] == "HOLD":
                    hold_signals.append((name, signal_confidence))
            except Exception as e:
                results[name] = {"signal": "ERROR", "reason": str(e)}

        # 综合判断
        total_confidence = 0
        if buy_signals and not sell_signals:
            final_signal = "BUY"
            total_confidence = sum(c for _, c in buy_signals) / len(buy_signals)
        elif sell_signals and not buy_signals:
            final_signal = "SELL"
            total_confidence = sum(c for _, c in sell_signals) / len(sell_signals)
        elif buy_signals and sell_signals:
            # 信号冲突，看哪个更强
            buy_conf = sum(c for _, c in buy_signals) / len(buy_signals)
            sell_conf = sum(c for _, c in sell_signals) / len(sell_signals)
            if buy_conf > sell_conf:
                final_signal = "BUY"
                total_confidence = buy_conf - sell_conf
            else:
                final_signal = "SELL"
                total_confidence = sell_conf - buy_conf
        else:
            final_signal = "HOLD"
            if hold_signals:
                total_confidence = sum(c for _, c in hold_signals) / len(hold_signals)
            else:
                total_confidence = 0.0

        return {
            "final_signal": final_signal,
            "confidence": self._clamp_confidence(total_confidence),
            "details": results,
            "buy_signals": buy_signals,
            "sell_signals": sell_signals,
        }

    def get_strategy_list(self) -> List[str]:
        """获取可用策略列表"""
        return list(self.strategies.keys())

    def get_strategy_info(self, name: str) -> Dict[str, Any]:
        """获取策略信息"""
        strategy_info = {
            "ma_cross": {
                "name": "双均线交叉",
                "description": "短期均线上穿长期均线买入，下穿卖出",
                "category": "趋势跟踪",
                "risk_level": "中",
            },
            "macd": {
                "name": "MACD策略",
                "description": "MACD金叉买入，死叉卖出",
                "category": "趋势跟踪",
                "risk_level": "中",
            },
            "rsi": {
                "name": "RSI超买卖",
                "description": "RSI超卖买入，超买卖出",
                "category": "均值回归",
                "risk_level": "中",
            },
            "bollinger": {
                "name": "布林带突破",
                "description": "价格突破上轨买入，跌破下轨卖出",
                "category": "波动突破",
                "risk_level": "中",
            },
            "momentum": {
                "name": "动量策略",
                "description": "追涨杀跌，基于价格和成交量动量",
                "category": "趋势跟踪",
                "risk_level": "高",
            },
            "mean_reversion": {
                "name": "均值回归",
                "description": "价格偏离均值后回归，适合震荡市场",
                "category": "均值回归",
                "risk_level": "中",
            },
            "breakout": {
                "name": "突破策略",
                "description": "突破近期高低点进行交易",
                "category": "趋势跟踪",
                "risk_level": "高",
            },
            "kdj": {
                "name": "KDJ随机指标",
                "description": "基于KDJ指标的交叉和超买超卖",
                "category": "均值回归",
                "risk_level": "中",
            },
            "volume": {
                "name": "成交量策略",
                "description": "基于成交量变化的量价分析",
                "category": "量价分析",
                "risk_level": "中",
            },
            "multi_factor": {
                "name": "多因子组合",
                "description": "综合MA、MACD、RSI等多个因子",
                "category": "综合策略",
                "risk_level": "低",
            },
            "grid": {
                "name": "网格交易",
                "description": "在价格区间内低买高卖，适合震荡市场",
                "category": "套利策略",
                "risk_level": "低",
            },
            "fractal": {
                "name": "分形交易策略",
                "description": "基于比尔·威廉姆斯的分形指标，识别价格反转点",
                "category": "趋势反转",
                "risk_level": "中",
            },
        }
        return strategy_info.get(name, {})
