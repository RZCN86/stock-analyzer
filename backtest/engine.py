import pandas as pd
import numpy as np
from typing import Dict, Any, Optional, List
from datetime import datetime

try:
    import vectorbt as vbt

    VECTORBT_AVAILABLE = True
except ImportError:
    VECTORBT_AVAILABLE = False

from utils.config import config
from utils.helpers import logger


class BacktestEngine:
    """回测引擎 - 使用VectorBT"""

    def __init__(self):
        if not VECTORBT_AVAILABLE:
            logger.warning("VectorBT未安装，回测功能将使用简化版本")

        self.initial_cash = config.get("backtest.initial_cash", 100000)
        self.commission = config.get("backtest.commission", 0.0003)
        self.slippage = config.get("backtest.slippage", 0.001)

    def run_simple_backtest(
        self, df: pd.DataFrame, entries: pd.Series, exits: pd.Series, symbol: str = ""
    ) -> Dict[str, Any]:
        """运行简单回测（不依赖VectorBT）"""
        if df.empty or len(df) < 2:
            return {"error": "数据不足"}

        prices = df["close"].values
        dates = df["date"].values if "date" in df.columns else df.index

        # 初始化
        cash = self.initial_cash
        position = 0
        trades = []
        equity_curve = [cash]

        for i in range(1, len(prices)):
            price = prices[i]

            # 买入信号
            if entries.iloc[i] and position == 0:
                shares = int(cash * 0.95 / price)  # 保留5%现金
                if shares > 0:
                    cost = shares * price * (1 + self.commission)
                    if cost <= cash:
                        position = shares
                        cash -= cost
                        trades.append(
                            {
                                "type": "BUY",
                                "date": dates[i],
                                "price": price,
                                "shares": shares,
                                "cost": cost,
                            }
                        )

            # 卖出信号
            elif exits.iloc[i] and position > 0:
                revenue = position * price * (1 - self.commission)
                trades.append(
                    {
                        "type": "SELL",
                        "date": dates[i],
                        "price": price,
                        "shares": position,
                        "revenue": revenue,
                        "pnl": revenue
                        - (position * trades[-1]["price"] if trades else 0),
                    }
                )
                cash += revenue
                position = 0

            # 计算权益
            current_equity = cash + position * price
            equity_curve.append(current_equity)

        # 最终清算
        final_price = prices[-1]
        final_equity = cash + position * final_price

        # 计算指标
        total_return = (final_equity - self.initial_cash) / self.initial_cash

        # 计算最大回撤
        max_drawdown = 0
        peak = equity_curve[0]
        for equity in equity_curve:
            if equity > peak:
                peak = equity
            drawdown = (peak - equity) / peak
            if drawdown > max_drawdown:
                max_drawdown = drawdown

        # 计算胜率
        winning_trades = [t for t in trades if t.get("pnl", 0) > 0]
        win_rate = (
            len(winning_trades) / len([t for t in trades if t["type"] == "SELL"])
            if trades
            else 0
        )

        date_labels = []
        for d in dates:
            try:
                date_labels.append(pd.Timestamp(d).strftime("%Y-%m-%d"))
            except Exception:
                date_labels.append(str(d))

        return {
            "symbol": symbol,
            "initial_cash": self.initial_cash,
            "final_equity": final_equity,
            "total_return": total_return,
            "total_return_pct": f"{total_return * 100:.2f}%",
            "max_drawdown": max_drawdown,
            "max_drawdown_pct": f"{max_drawdown * 100:.2f}%",
            "total_trades": len([t for t in trades if t["type"] == "SELL"]),
            "win_rate": f"{win_rate * 100:.2f}%",
            "trades": trades,
            "equity_curve": equity_curve,
            "prices": prices.tolist(),
            "dates": date_labels,
        }

    def run_vectorbt_backtest(
        self, df: pd.DataFrame, entries: pd.Series, exits: pd.Series, symbol: str = ""
    ) -> Dict[str, Any]:
        """使用VectorBT运行回测"""
        if not VECTORBT_AVAILABLE:
            return self.run_simple_backtest(df, entries, exits, symbol)

        try:
            prices = df["close"]

            # 创建投资组合
            portfolio = vbt.Portfolio.from_signals(
                prices,
                entries=entries,
                exits=exits,
                init_cash=self.initial_cash,
                fees=self.commission,
                slippage=self.slippage,
                freq="1d",
            )

            # 获取回测统计
            stats = portfolio.stats()

            return {
                "symbol": symbol,
                "initial_cash": self.initial_cash,
                "final_equity": portfolio.final_value(),
                "total_return": portfolio.total_return(),
                "total_return_pct": f"{portfolio.total_return() * 100:.2f}%",
                "max_drawdown": portfolio.max_drawdown(),
                "max_drawdown_pct": f"{portfolio.max_drawdown() * 100:.2f}%",
                "sharpe_ratio": stats.get("Sharpe Ratio", 0),
                "total_trades": stats.get("Total Trades", 0),
                "win_rate": f"{stats.get('Win Rate', 0) * 100:.2f}%",
                "avg_winning_trade": stats.get("Avg Winning Trade", 0),
                "avg_losing_trade": stats.get("Avg Losing Trade", 0),
                "portfolio": portfolio,
            }

        except Exception as e:
            logger.error(f"VectorBT回测失败: {e}")
            return self.run_simple_backtest(df, entries, exits, symbol)

    def run_strategy_backtest(
        self, df: pd.DataFrame, strategy, symbol: str = ""
    ) -> Dict[str, Any]:
        """使用策略运行回测"""
        # 生成策略信号
        result = strategy.generate_signals(df)

        # 提取买入卖出信号
        entries = result["signal"] == 1
        exits = result["signal"] == -1

        # 运行回测
        return self.run_vectorbt_backtest(df, entries, exits, symbol)

    def optimize_strategy(
        self,
        df: pd.DataFrame,
        strategy_class,
        param_grid: Dict[str, List],
        symbol: str = "",
    ) -> Dict[str, Any]:
        """优化策略参数"""
        if not VECTORBT_AVAILABLE:
            logger.warning("VectorBT未安装，跳过参数优化")
            return {}

        try:
            from itertools import product

            # 生成参数组合
            param_names = list(param_grid.keys())
            param_values = list(param_grid.values())

            best_return = -np.inf
            best_params = None
            best_stats = None

            for values in product(*param_values):
                params = dict(zip(param_names, values))
                strategy = strategy_class(params)

                result = strategy.generate_signals(df)
                entries = result["signal"] == 1
                exits = result["signal"] == -1

                portfolio = vbt.Portfolio.from_signals(
                    df["close"],
                    entries=entries,
                    exits=exits,
                    init_cash=self.initial_cash,
                    fees=self.commission,
                    freq="1d",
                )

                total_return = portfolio.total_return()
                if total_return > best_return:
                    best_return = total_return
                    best_params = params
                    best_stats = portfolio.stats()

            return {
                "best_params": best_params,
                "best_return": best_return,
                "stats": best_stats,
            }

        except Exception as e:
            logger.error(f"参数优化失败: {e}")
            return {}
