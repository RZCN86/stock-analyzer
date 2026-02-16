import pandas as pd
import numpy as np
from typing import Dict, Any, List, Tuple
from scipy import stats


class ConfidenceCalculator:
    """置信度计算器 - 提供标准化的置信度计算方法"""

    @staticmethod
    def clamp_confidence(confidence: float) -> float:
        """统一裁剪置信度到[0,1]。"""
        if pd.isna(confidence):
            return 0.0
        return float(min(1.0, max(0.0, confidence)))

    @staticmethod
    def _safe_relative_diff(a: float, b: float) -> float:
        """安全相对差，避免除零放大。"""
        denom = max(abs(b), abs(a), 1e-9)
        return abs(a - b) / denom

    @staticmethod
    def calculate_trend_confidence(
        current_value: float,
        benchmark: float,
        recent_values: pd.Series = None,
        direction: str = "above",
    ) -> float:
        """
        计算趋势置信度

        Args:
            current_value: 当前值
            benchmark: 基准值（如均线）
            recent_values: 近期值序列，用于计算趋势强度
            direction: 'above' 或 'below'

        Returns:
            置信度 (0-1)
        """
        # 基础偏离度
        deviation = ConfidenceCalculator._safe_relative_diff(current_value, benchmark)

        # 基础置信度
        base_confidence = min(0.95, 0.5 + deviation * 5)

        # 如果有历史数据，计算趋势一致性
        if recent_values is not None and len(recent_values) >= 3:
            # 计算趋势方向一致性
            diffs = recent_values.diff().dropna()
            if len(diffs) > 0:
                # 上涨/下跌的一致性
                if direction == "above":
                    consistency = (diffs > 0).sum() / len(diffs)
                else:
                    consistency = (diffs < 0).sum() / len(diffs)

                # 趋势一致性加成
                trend_bonus = consistency * 0.2
                base_confidence = min(0.95, base_confidence + trend_bonus)

        return ConfidenceCalculator.clamp_confidence(base_confidence)

    @staticmethod
    def calculate_crossover_confidence(
        fast_value: float,
        slow_value: float,
        prev_fast: float,
        prev_slow: float,
        fast_series: pd.Series = None,
        slow_series: pd.Series = None,
    ) -> Tuple[str, float]:
        """
        计算交叉信号置信度

        Returns:
            (信号类型, 置信度)
        """
        # 判断是否发生交叉
        was_above = prev_fast > prev_slow
        is_above = fast_value > slow_value

        if was_above == is_above:
            # 没有交叉
            if is_above:
                hold_strength = min(
                    1.0,
                    ConfidenceCalculator._safe_relative_diff(fast_value, slow_value)
                    * 3,
                )
                return "HOLD", ConfidenceCalculator.clamp_confidence(
                    0.35 + hold_strength * 0.3
                )
            else:
                hold_strength = min(
                    1.0,
                    ConfidenceCalculator._safe_relative_diff(slow_value, fast_value)
                    * 3,
                )
                return "HOLD", ConfidenceCalculator.clamp_confidence(
                    0.35 + hold_strength * 0.3
                )

        # 发生交叉，计算交叉强度
        cross_strength = ConfidenceCalculator._safe_relative_diff(fast_value, slow_value)

        # 基础置信度
        base_conf = 0.7 + min(0.25, cross_strength * 10)

        # 趋势确认加成
        if fast_series is not None and slow_series is not None:
            # 检查交叉前的趋势
            if len(fast_series) >= 5:
                fast_trend = (
                    fast_series.iloc[-1] - fast_series.iloc[-5]
                ) / fast_series.iloc[-5]
                slow_trend = (
                    slow_series.iloc[-1] - slow_series.iloc[-5]
                ) / slow_series.iloc[-5]

                # 快速线趋势更强，确认交叉
                if is_above and fast_trend > slow_trend:
                    base_conf = min(0.95, base_conf + 0.1)
                elif not is_above and fast_trend < slow_trend:
                    base_conf = min(0.95, base_conf + 0.1)

        signal = "BUY" if is_above else "SELL"
        return signal, ConfidenceCalculator.clamp_confidence(base_conf)

    @staticmethod
    def calculate_extreme_confidence(
        value: float,
        lower_bound: float,
        upper_bound: float,
        recent_values: pd.Series = None,
        mean_reversion: bool = True,
    ) -> Tuple[str, float]:
        """
        计算极端值置信度（用于RSI、KDJ等）

        Args:
            value: 当前值
            lower_bound: 下轨/超卖线
            upper_bound: 上轨/超买线
            recent_values: 近期值
            mean_reversion: 是否均值回归（True=超卖买入，False=超买买入）
        """
        range_size = upper_bound - lower_bound

        # 计算偏离程度
        if value < lower_bound:
            # 低于下轨
            oversold_degree = (lower_bound - value) / range_size
            if mean_reversion:
                signal = "BUY"
                confidence = min(0.95, 0.6 + oversold_degree * 2)
            else:
                signal = "SELL"
                confidence = min(0.95, 0.6 + oversold_degree * 1.5)
        elif value > upper_bound:
            # 高于上轨
            overbought_degree = (value - upper_bound) / range_size
            if mean_reversion:
                signal = "SELL"
                confidence = min(0.95, 0.6 + overbought_degree * 2)
            else:
                signal = "BUY"
                confidence = min(0.95, 0.6 + overbought_degree * 1.5)
        else:
            # 在区间内
            position = (value - lower_bound) / range_size

            # 接近边界增加置信度
            if position < 0.3:
                signal = "BUY" if mean_reversion else "SELL"
                confidence = 0.45 + (0.3 - position) * 0.4
            elif position > 0.7:
                signal = "SELL" if mean_reversion else "BUY"
                confidence = 0.45 + (position - 0.7) * 0.4
            else:
                signal = "HOLD"
                center_bias = abs(position - 0.5) * 2
                confidence = 0.3 + center_bias * 0.3

        # 如果有历史数据，考虑背离
        if recent_values is not None and len(recent_values) >= 10:
            # 简单背离检测
            recent_mean = recent_values.tail(5).mean()
            older_mean = recent_values.head(5).mean()

            # 如果指标在改善，增加置信度
            if signal == "BUY" and recent_mean > older_mean:
                confidence = min(0.95, confidence + 0.05)
            elif signal == "SELL" and recent_mean < older_mean:
                confidence = min(0.95, confidence + 0.05)

        return signal, ConfidenceCalculator.clamp_confidence(confidence)

    @staticmethod
    def calculate_breakout_confidence(
        price: float,
        resistance: float,
        support: float,
        volume_ratio: float = 1.0,
        lookback: int = 20,
    ) -> Tuple[str, float]:
        """
        计算突破置信度
        """
        # 突破阻力
        if price > resistance:
            breakout_strength = (price - resistance) / resistance
            base_conf = 0.65 + min(0.3, breakout_strength * 10)

            # 成交量确认
            if volume_ratio > 1.5:
                base_conf = min(0.95, base_conf + 0.1)
            elif volume_ratio < 1.0:
                base_conf = max(0.5, base_conf - 0.1)

            return "BUY", ConfidenceCalculator.clamp_confidence(base_conf)

        # 跌破支撑
        elif price < support:
            breakdown_strength = (support - price) / support
            base_conf = 0.65 + min(0.3, breakdown_strength * 10)

            # 成交量确认
            if volume_ratio > 1.5:
                base_conf = min(0.95, base_conf + 0.1)

            return "SELL", ConfidenceCalculator.clamp_confidence(base_conf)

        # 在区间内
        mid = (resistance + support) / 2
        if price > mid:
            position = (price - mid) / (resistance - mid)
            return "HOLD", ConfidenceCalculator.clamp_confidence(0.35 + position * 0.3)
        else:
            position = (mid - price) / (mid - support)
            return "HOLD", ConfidenceCalculator.clamp_confidence(0.35 + position * 0.3)

    @staticmethod
    def calculate_multi_factor_confidence(
        factor_scores: List[float],
        factor_weights: List[float] = None,
        threshold_buy: float = 0.6,
        threshold_sell: float = 0.4,
    ) -> Tuple[str, float, Dict[str, float]]:
        """
        计算多因子综合置信度

        Args:
            factor_scores: 各因子得分 (0-1)
            factor_weights: 各因子权重
            threshold_buy: 买入阈值
            threshold_sell: 卖出阈值

        Returns:
            (信号, 综合置信度, 各因子详情)
        """
        if factor_weights is None:
            factor_weights = [1.0 / len(factor_scores)] * len(factor_scores)

        # 计算加权得分
        weighted_score = sum(s * w for s, w in zip(factor_scores, factor_weights))

        # 计算因子一致性（标准差越小，一致性越高）
        consistency = 1 - np.std(factor_scores)

        # 基础信号判断
        if weighted_score >= threshold_buy:
            signal = "BUY"
            base_conf = weighted_score
        elif weighted_score <= threshold_sell:
            signal = "SELL"
            base_conf = 1 - weighted_score
        else:
            signal = "HOLD"
            base_conf = 0.35 + min(0.3, abs(weighted_score - 0.5) * 0.8)

        # 一致性加成
        final_conf = min(0.95, base_conf * (0.8 + 0.2 * consistency))

        details = {
            "weighted_score": weighted_score,
            "consistency": consistency,
            "factor_scores": dict(enumerate(factor_scores)),
        }

        return signal, ConfidenceCalculator.clamp_confidence(final_conf), details

    @staticmethod
    def calculate_divergence_confidence(
        price_series: pd.Series, indicator_series: pd.Series, lookback: int = 20
    ) -> Tuple[str, float]:
        """
        计算背离信号置信度

        顶背离: 价格新高，指标未新高 -> 卖出信号
        底背离: 价格新低，指标未新低 -> 买入信号
        """
        if len(price_series) < lookback or len(indicator_series) < lookback:
            return "HOLD", 0.0

        # 获取近期数据
        price_recent = price_series.tail(lookback)
        indicator_recent = indicator_series.tail(lookback)

        # 找出极值点
        price_max_idx = price_recent.idxmax()
        price_min_idx = price_recent.idxmin()
        indicator_max_idx = indicator_recent.idxmax()
        indicator_min_idx = indicator_recent.idxmin()

        # 检查顶背离
        if price_max_idx > indicator_max_idx:
            # 价格继续创新高，但指标没有
            price_divergence = (
                price_recent.iloc[-1] - price_recent.loc[indicator_max_idx]
            ) / price_recent.loc[indicator_max_idx]
            if price_divergence > 0.05:  # 价格偏离超过5%
                return "SELL", ConfidenceCalculator.clamp_confidence(
                    min(0.85, 0.65 + price_divergence * 2)
                )

        # 检查底背离
        if price_min_idx > indicator_min_idx:
            # 价格继续创新低，但指标没有
            price_divergence = (
                price_recent.loc[indicator_min_idx] - price_recent.iloc[-1]
            ) / price_recent.loc[indicator_min_idx]
            if price_divergence > 0.05:
                return "BUY", ConfidenceCalculator.clamp_confidence(
                    min(0.85, 0.65 + price_divergence * 2)
                )
        price_std = price_recent.std()
        indicator_std = indicator_recent.std()
        if price_std > 0 and indicator_std > 0:
            norm_price = abs(price_recent.iloc[-1] - price_recent.mean()) / (
                price_std + 1e-9
            )
            norm_indicator = abs(
                indicator_recent.iloc[-1] - indicator_recent.mean()
            ) / (indicator_std + 1e-9)
            divergence_intensity = min(1.0, abs(norm_price - norm_indicator) / 3)
        else:
            divergence_intensity = 0.0

        return "HOLD", ConfidenceCalculator.clamp_confidence(
            0.3 + divergence_intensity * 0.3
        )

    @staticmethod
    def adjust_confidence_by_volatility(
        base_confidence: float,
        price_series: pd.Series,
        lookback: int = 20,
        high_volatility_penalty: float = 0.1,
    ) -> float:
        """
        根据波动性调整置信度

        高波动性市场降低置信度
        """
        if len(price_series) < lookback:
            return base_confidence

        # 计算近期波动率
        returns = price_series.pct_change().dropna().tail(lookback)
        volatility = returns.std()

        # 根据波动率调整
        if volatility > 0.03:  # 日波动率超过3%视为高波动
            adjustment = -high_volatility_penalty * (volatility / 0.03)
            return ConfidenceCalculator.clamp_confidence(
                max(0.3, min(0.95, base_confidence + adjustment))
            )

        return ConfidenceCalculator.clamp_confidence(base_confidence)

    @staticmethod
    def calculate_volume_confidence(
        current_volume: float,
        avg_volume: float,
        price_change: float,
        direction: str = "up",
    ) -> float:
        """
        计算成交量确认置信度

        量价配合良好 -> 高置信度
        量价背离 -> 低置信度
        """
        if avg_volume == 0:
            return 0.0

        volume_ratio = current_volume / avg_volume

        # 基础置信度
        if direction == "up":
            # 上涨需要放量
            if price_change > 0:
                if volume_ratio > 1.5:
                    return ConfidenceCalculator.clamp_confidence(
                        min(0.9, 0.6 + (volume_ratio - 1.5) * 0.2)
                    )
                elif volume_ratio > 1.0:
                    return ConfidenceCalculator.clamp_confidence(
                        0.55 + (volume_ratio - 1.0) * 0.2
                    )
                else:
                    anomaly = min(1.0, abs(volume_ratio - 1.0))
                    return ConfidenceCalculator.clamp_confidence(0.3 + anomaly * 0.2)
            else:
                drift = min(1.0, abs(price_change))
                return ConfidenceCalculator.clamp_confidence(0.25 + drift * 0.2)
        else:
            # 下跌放量通常不好，但如果是洗盘则另说
            if price_change < 0:
                if volume_ratio > 2.0:
                    return 0.6  # 恐慌性下跌
                elif volume_ratio < 0.8:
                    return 0.6  # 缩量下跌，可能止跌
                else:
                    anomaly = min(1.0, abs(volume_ratio - 1.0))
                    return ConfidenceCalculator.clamp_confidence(0.3 + anomaly * 0.2)
            else:
                drift = min(1.0, abs(price_change))
                return ConfidenceCalculator.clamp_confidence(0.25 + drift * 0.2)
