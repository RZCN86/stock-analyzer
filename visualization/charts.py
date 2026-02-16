import matplotlib.pyplot as plt
import mplfinance as mpf
import pandas as pd
import numpy as np
from typing import Optional, Dict, Any, List
import os

from utils.helpers import ensure_dir


class ChartVisualizer:
    """图表可视化类"""

    def __init__(self, style: str = "yahoo"):
        self.style = style
        plt.rcParams["font.sans-serif"] = ["SimHei", "Arial Unicode MS", "DejaVu Sans"]
        plt.rcParams["axes.unicode_minus"] = False

    def plot_candlestick(
        self,
        df: pd.DataFrame,
        title: str = "K线图",
        save_path: Optional[str] = None,
        mav: tuple = (5, 20, 60),
    ):
        """绘制K线图"""
        if df.empty:
            print("数据为空，无法绘制图表")
            return

        # 准备数据
        plot_df = df.copy()
        plot_df["date"] = pd.to_datetime(plot_df["date"])
        plot_df.set_index("date", inplace=True)

        # 确保列名正确
        required_cols = ["open", "high", "low", "close", "volume"]
        for col in required_cols:
            if col not in plot_df.columns:
                print(f"缺少必要列: {col}")
                return

        # 重命名列以符合mplfinance要求
        plot_df = plot_df.rename(
            columns={
                "open": "Open",
                "high": "High",
                "low": "Low",
                "close": "Close",
                "volume": "Volume",
            }
        )

        # 设置图形大小
        figsize = (12, 8)

        # 绘制K线图
        mpf.plot(
            plot_df,
            type="candle",
            style=self.style,
            title=title,
            ylabel="价格",
            ylabel_lower="成交量",
            volume=True,
            mav=mav,
            figsize=figsize,
            savefig=save_path,
        )

        if save_path:
            print(f"图表已保存: {save_path}")

    def plot_with_indicators(
        self,
        df: pd.DataFrame,
        indicators: List[str] = ["ma", "macd", "rsi"],
        title: str = "技术分析图表",
        save_path: Optional[str] = None,
    ):
        """绘制带技术指标的图表"""
        if df.empty:
            return

        # 创建子图
        num_panels = 1 + len(indicators)
        fig, axes = plt.subplots(
            num_panels,
            1,
            figsize=(14, 4 * num_panels),
            gridspec_kw={"height_ratios": [3] + [1] * len(indicators)},
        )

        if num_panels == 1:
            axes = [axes]

        plot_df = df.copy()
        plot_df["date"] = pd.to_datetime(plot_df["date"])

        # 绘制价格和均线
        ax_price = axes[0]
        ax_price.plot(plot_df["date"], plot_df["close"], label="收盘价", linewidth=1.5)

        if "ma5" in plot_df.columns:
            ax_price.plot(plot_df["date"], plot_df["ma5"], label="MA5", alpha=0.7)
        if "ma20" in plot_df.columns:
            ax_price.plot(plot_df["date"], plot_df["ma20"], label="MA20", alpha=0.7)
        if "ma60" in plot_df.columns:
            ax_price.plot(plot_df["date"], plot_df["ma60"], label="MA60", alpha=0.7)

        ax_price.set_title(title, fontsize=14)
        ax_price.set_ylabel("价格")
        ax_price.legend(loc="upper left")
        ax_price.grid(True, alpha=0.3)

        # 绘制指标
        panel_idx = 1
        for indicator in indicators:
            ax = axes[panel_idx]

            if indicator == "macd" and "macd_dif" in plot_df.columns:
                ax.plot(plot_df["date"], plot_df["macd_dif"], label="DIF", color="blue")
                ax.plot(
                    plot_df["date"], plot_df["macd_dea"], label="DEA", color="orange"
                )

                # 绘制MACD柱状图
                colors = [
                    "red" if h > 0 else "green" for h in plot_df["macd_histogram"]
                ]
                ax.bar(
                    plot_df["date"],
                    plot_df["macd_histogram"],
                    color=colors,
                    alpha=0.5,
                    label="MACD",
                )
                ax.axhline(y=0, color="black", linestyle="-", linewidth=0.5)
                ax.set_ylabel("MACD")
                ax.legend(loc="upper left")

            elif indicator == "rsi" and "rsi" in plot_df.columns:
                ax.plot(plot_df["date"], plot_df["rsi"], label="RSI", color="purple")
                ax.axhline(y=70, color="red", linestyle="--", label="超买(70)")
                ax.axhline(y=30, color="green", linestyle="--", label="超卖(30)")
                ax.fill_between(plot_df["date"], 30, 70, alpha=0.1, color="gray")
                ax.set_ylabel("RSI")
                ax.set_ylim(0, 100)
                ax.legend(loc="upper left")

            elif indicator == "kdj" and "kdj_k" in plot_df.columns:
                ax.plot(plot_df["date"], plot_df["kdj_k"], label="K", color="blue")
                ax.plot(plot_df["date"], plot_df["kdj_d"], label="D", color="orange")
                ax.plot(plot_df["date"], plot_df["kdj_j"], label="J", color="purple")
                ax.set_ylabel("KDJ")
                ax.legend(loc="upper left")

            elif indicator == "bollinger" and "boll_upper" in plot_df.columns:
                ax.plot(
                    plot_df["date"], plot_df["close"], label="收盘价", color="black"
                )
                ax.plot(
                    plot_df["date"],
                    plot_df["boll_upper"],
                    label="上轨",
                    color="red",
                    alpha=0.7,
                )
                ax.plot(
                    plot_df["date"],
                    plot_df["boll_mid"],
                    label="中轨",
                    color="blue",
                    alpha=0.7,
                )
                ax.plot(
                    plot_df["date"],
                    plot_df["boll_lower"],
                    label="下轨",
                    color="green",
                    alpha=0.7,
                )
                ax.fill_between(
                    plot_df["date"],
                    plot_df["boll_upper"],
                    plot_df["boll_lower"],
                    alpha=0.1,
                )
                ax.set_ylabel("布林带")
                ax.legend(loc="upper left")

            ax.grid(True, alpha=0.3)
            panel_idx += 1

        plt.tight_layout()

        if save_path:
            ensure_dir(os.path.dirname(save_path))
            plt.savefig(save_path, dpi=150, bbox_inches="tight")
            print(f"图表已保存: {save_path}")
        else:
            plt.show()

        plt.close()

    def plot_equity_curve(
        self,
        backtest_result: Dict[str, Any],
        title: str = "资金曲线",
        save_path: Optional[str] = None,
    ):
        """绘制回测资金曲线"""
        equity_curve = backtest_result.get("equity_curve", [])
        if not equity_curve:
            print("没有资金曲线数据")
            return

        fig, (ax1, ax2) = plt.subplots(
            2, 1, figsize=(12, 8), gridspec_kw={"height_ratios": [3, 1]}
        )

        # 资金曲线
        ax1.plot(equity_curve, linewidth=1.5, color="blue")
        ax1.axhline(
            y=backtest_result.get("initial_cash", 100000),
            color="red",
            linestyle="--",
            alpha=0.5,
            label="初始资金",
        )
        ax1.set_title(title, fontsize=14)
        ax1.set_ylabel("资金")
        ax1.legend()
        ax1.grid(True, alpha=0.3)

        # 添加统计信息
        stats_text = f"""
        总收益率: {backtest_result.get("total_return_pct", "N/A")}
        最大回撤: {backtest_result.get("max_drawdown_pct", "N/A")}
        交易次数: {backtest_result.get("total_trades", 0)}
        胜率: {backtest_result.get("win_rate", "N/A")}
        """
        ax1.text(
            0.02,
            0.98,
            stats_text,
            transform=ax1.transAxes,
            verticalalignment="top",
            bbox=dict(boxstyle="round", facecolor="wheat", alpha=0.5),
        )

        # 回撤曲线
        rolling_max = np.maximum.accumulate(equity_curve)
        drawdown = (rolling_max - equity_curve) / rolling_max
        ax2.fill_between(range(len(drawdown)), drawdown, 0, color="red", alpha=0.3)
        ax2.set_ylabel("回撤")
        ax2.set_xlabel("时间")
        ax2.grid(True, alpha=0.3)

        plt.tight_layout()

        if save_path:
            ensure_dir(os.path.dirname(save_path))
            plt.savefig(save_path, dpi=150, bbox_inches="tight")
            print(f"图表已保存: {save_path}")
        else:
            plt.show()

        plt.close()

    def plot_signal_summary(
        self, signal_result: Dict[str, Any], save_path: Optional[str] = None
    ):
        """绘制信号汇总图"""
        details = signal_result.get("details", {})
        if not details:
            return

        # 提取数据
        strategies = []
        signals = []
        confidences = []

        for name, data in details.items():
            strategies.append(name)
            signal = data.get("signal", "HOLD")
            signals.append(1 if signal == "BUY" else (-1 if signal == "SELL" else 0))
            confidences.append(data.get("confidence", 0.5))

        # 创建图表
        fig, (ax1, ax2) = plt.subplots(1, 2, figsize=(12, 5))

        # 信号柱状图
        colors = ["green" if s > 0 else ("red" if s < 0 else "gray") for s in signals]
        ax1.barh(strategies, signals, color=colors, alpha=0.7)
        ax1.axvline(x=0, color="black", linestyle="-", linewidth=0.5)
        ax1.set_xlabel("信号")
        ax1.set_title("各策略信号")
        ax1.set_xlim(-1.5, 1.5)

        # 置信度柱状图
        colors2 = [
            "green" if c > 0.6 else ("red" if c < 0.4 else "gray") for c in confidences
        ]
        ax2.barh(strategies, confidences, color=colors2, alpha=0.7)
        ax2.axvline(x=0.5, color="black", linestyle="--", linewidth=0.5)
        ax2.set_xlabel("置信度")
        ax2.set_title("信号置信度")
        ax2.set_xlim(0, 1)

        # 添加综合信号
        final_signal = signal_result.get("final_signal", "HOLD")
        fig.suptitle(
            f"综合信号: {final_signal} (置信度: {signal_result.get('confidence', 0):.2f})",
            fontsize=14,
            fontweight="bold",
        )

        plt.tight_layout()

        if save_path:
            ensure_dir(os.path.dirname(save_path))
            plt.savefig(save_path, dpi=150, bbox_inches="tight")
            print(f"图表已保存: {save_path}")
        else:
            plt.show()

        plt.close()
