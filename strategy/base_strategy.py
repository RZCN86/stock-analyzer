from abc import ABC, abstractmethod
from typing import Dict, Any, Optional
import pandas as pd


class BaseStrategy(ABC):
    """策略基类"""

    def __init__(self, name: str, params: Dict[str, Any] = None):
        self.name = name
        self.params = params or {}
        self.signals = []

    @abstractmethod
    def generate_signals(self, df: pd.DataFrame) -> pd.DataFrame:
        """生成交易信号"""
        pass

    @abstractmethod
    def get_current_signal(self, df: pd.DataFrame) -> Dict[str, Any]:
        """获取当前交易信号"""
        pass

    def get_params(self) -> Dict[str, Any]:
        """获取策略参数"""
        return self.params

    def set_params(self, params: Dict[str, Any]):
        """设置策略参数"""
        self.params.update(params)

    def calculate_position_size(
        self, capital: float, price: float, risk_per_trade: float = 0.02
    ) -> int:
        """计算仓位大小"""
        max_position_value = capital * self.params.get("max_position", 0.3)
        risk_amount = capital * risk_per_trade

        # 基于风险计算股数
        stop_loss = self.params.get("stop_loss", 0.05)
        if stop_loss > 0:
            shares_by_risk = risk_amount / (price * stop_loss)
        else:
            shares_by_risk = 0

        # 基于最大仓位计算股数
        shares_by_position = max_position_value / price

        # 取较小值
        shares = int(min(shares_by_risk, shares_by_position))
        return max(shares, 0)

    @staticmethod
    def clamp_confidence(confidence: float) -> float:
        """统一裁剪置信度到[0,1]。"""
        if pd.isna(confidence):
            return 0.0
        return float(min(1.0, max(0.0, confidence)))

    @staticmethod
    def scale_confidence(
        strength: float, lower: float = 0.35, upper: float = 0.95
    ) -> float:
        """
        将强度(0-1)线性映射到置信度区间，再统一裁剪。
        strength 越大，返回值越接近 upper。
        """
        safe_strength = min(1.0, max(0.0, strength))
        mapped = lower + (upper - lower) * safe_strength
        return BaseStrategy.clamp_confidence(mapped)
