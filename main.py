import pandas as pd
from datetime import datetime, timedelta
from typing import Optional, List, Dict, Any
import os
import sys

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

from utils.config import config
from utils.helpers import setup_logging, logger, format_date
from utils.stock_name import get_stock_name, get_stock_info
from database.db_manager import db
from fetcher.akshare_fetcher import AKShareFetcher
from fetcher.yfinance_fetcher import YFinanceFetcher
from analysis.indicators import TechnicalIndicators
from strategy.engine import StrategyEngine
from backtest.engine import BacktestEngine
from visualization.charts import ChartVisualizer


class StockAnalyzer:
    """股票分析系统主类"""

    def __init__(self):
        self.ak_fetcher = AKShareFetcher()
        self.us_fetcher = YFinanceFetcher()
        self.strategy_engine = StrategyEngine()
        self.backtest_engine = BacktestEngine()
        self.visualizer = ChartVisualizer()

        setup_logging(
            level=config.get("logging.level", "INFO"),
            log_file=config.get("logging.file"),
        )

    @staticmethod
    def _normalize_symbol(symbol: str, market: Optional[str] = None) -> str:
        symbol = (symbol or "").strip()
        if (market or "").upper() == "US":
            symbol = symbol.upper()
        return symbol

    def fetch_and_store(
        self,
        symbol: str,
        market: str = "A",
        start_date: Optional[str] = None,
        end_date: Optional[str] = None,
        force_update: bool = False,
    ) -> pd.DataFrame:
        """获取并存储数据"""
        market = (market or "").upper()
        symbol = self._normalize_symbol(symbol, market)
        local_data = db.get_daily_data(symbol)

        # 检查本地数据
        if not force_update and not start_date:
            if not local_data.empty:
                last_date = db.get_last_update_date(symbol)
                if last_date:
                    parsed_last_date = pd.to_datetime(last_date, errors="coerce", utc=True)
                    if pd.notna(parsed_last_date):
                        start_date = (parsed_last_date + timedelta(days=1)).strftime(
                            "%Y-%m-%d"
                        )

        # 如果没有指定日期，使用默认
        if not start_date:
            start_date = config.get("update.start_date", "2020-01-01")
        if not end_date:
            end_date = datetime.now().strftime("%Y-%m-%d")

        # 获取数据
        if market == "A":
            df = self.ak_fetcher.fetch_daily_data(symbol, start_date, end_date)
        elif market == "US":
            df = self.us_fetcher.fetch_daily_data(symbol, start_date, end_date)
        elif market == "ETF":
            df = self.ak_fetcher.fetch_etf_data(symbol, start_date, end_date)
        else:
            logger.error(f"不支持的市场类型: {market}")
            return pd.DataFrame()

        # 存储到数据库
        if not df.empty:
            db.save_daily_data(symbol, df)
            logger.info(f"成功保存 {symbol} 的 {len(df)} 条数据")
            return df

        # 增量更新无新数据时，回退本地数据保证功能可用
        if not local_data.empty:
            logger.info(f"{symbol} 暂无增量数据，使用本地缓存 {len(local_data)} 条")
            return local_data

        return df

    def analyze(
        self, symbol: str, market: str = "A", strategies: Optional[List[str]] = None
    ) -> Dict[str, Any]:
        """分析股票"""
        market = (market or "").upper()
        symbol = self._normalize_symbol(symbol, market)
        # 获取数据
        df = db.get_daily_data(symbol)

        if df.empty:
            logger.info(f"本地无数据，尝试获取 {symbol}")
            df = self.fetch_and_store(symbol, market)

        if df.empty:
            return {"error": f"无法获取 {symbol} 的数据"}

        # 计算技术指标
        df_with_indicators = TechnicalIndicators.calculate_all(df)

        # 运行策略分析
        result = self.strategy_engine.analyze(df_with_indicators, strategies)

        # 添加数据摘要
        latest = df_with_indicators.iloc[-1]
        result["data_summary"] = {
            "symbol": symbol,
            "date": latest["date"],
            "close": latest["close"],
            "change_pct": latest.get("pct_change", 0),
            "volume": latest.get("volume", 0),
            "ma20": latest.get("ma20", None),
            "rsi": latest.get("rsi", None),
        }

        return result

    def backtest(
        self,
        symbol: str,
        strategy_name: str,
        market: str = "A",
        start_date: Optional[str] = None,
        end_date: Optional[str] = None,
    ) -> Dict[str, Any]:
        """回测单个策略"""
        market = (market or "").upper()
        symbol = self._normalize_symbol(symbol, market)
        # 获取数据
        df = db.get_daily_data(symbol, start_date, end_date)

        if df.empty:
            df = self.fetch_and_store(symbol, market, start_date, end_date)

        if df.empty or len(df) < 60:
            return {"error": "数据不足，无法进行回测"}

        # 获取策略
        strategy = self.strategy_engine.get_strategy(strategy_name)

        # 运行回测
        result = self.backtest_engine.run_strategy_backtest(df, strategy, symbol)

        return result

    def backtest_multiple(
        self,
        symbol: str,
        strategy_names: List[str],
        market: str = "A",
        start_date: Optional[str] = None,
        end_date: Optional[str] = None,
    ) -> Dict[str, Any]:
        """
        多策略对比回测

        Args:
            symbol: 股票代码
            strategy_names: 策略名称列表
            market: 市场类型
            start_date: 开始日期
            end_date: 结束日期

        Returns:
            {
                'symbol': 股票代码,
                'name': 股票名称,
                'period': 回测区间,
                'best_strategy': 最佳策略,
                'comparison': 各策略对比结果,
                'ranking': 策略排名,
            }
        """
        market = (market or "").upper()
        symbol = self._normalize_symbol(symbol, market)
        from utils.stock_name import get_stock_name

        # 获取数据
        df = db.get_daily_data(symbol, start_date, end_date)

        if df.empty:
            df = self.fetch_and_store(symbol, market, start_date, end_date)

        if df.empty or len(df) < 60:
            return {"error": "数据不足，无法进行回测"}

        # 获取股票名称
        stock_name = get_stock_name(symbol, market)

        # 运行多策略回测
        comparison_results = []

        for strategy_name in strategy_names:
            try:
                strategy = self.strategy_engine.get_strategy(strategy_name)
                result = self.backtest_engine.run_strategy_backtest(
                    df, strategy, symbol
                )

                if "error" not in result:
                    # 获取策略信息
                    strategy_info = self.strategy_engine.get_strategy_info(
                        strategy_name
                    )

                    comparison_results.append(
                        {
                            "strategy_id": strategy_name,
                            "strategy_name": strategy_info.get("name", strategy_name),
                            "category": strategy_info.get("category", "未知"),
                            "risk_level": strategy_info.get("risk_level", "中"),
                            "total_return": result.get("total_return", 0),
                            "total_return_pct": result.get("total_return_pct", "0%"),
                            "max_drawdown": result.get("max_drawdown", 0),
                            "max_drawdown_pct": result.get("max_drawdown_pct", "0%"),
                            "total_trades": result.get("total_trades", 0),
                            "win_rate": result.get("win_rate", "0%"),
                            "sharpe_ratio": result.get("sharpe_ratio", 0),
                            "final_equity": result.get("final_equity", 0),
                            "initial_cash": result.get("initial_cash", 100000),
                        }
                    )
            except Exception as e:
                logger.error(f"回测策略 {strategy_name} 失败: {e}")

        if not comparison_results:
            return {"error": "所有策略回测失败"}

        # 转换为DataFrame便于分析
        comparison_df = pd.DataFrame(comparison_results)

        # 计算综合得分（收益率权重40%，最大回撤权重30%，胜率权重20%，夏普比率权重10%）
        comparison_df["score"] = (
            comparison_df["total_return"] * 0.4
            - comparison_df["max_drawdown"] * 0.3
            + (comparison_df["win_rate"].str.rstrip("%").astype(float) / 100) * 0.2
            + comparison_df["sharpe_ratio"] * 0.1
        )

        # 排序
        comparison_df = comparison_df.sort_values("score", ascending=False)

        # 找出最佳策略
        best_strategy = comparison_df.iloc[0]

        return {
            "symbol": symbol,
            "name": stock_name,
            "market": market,
            "period": {
                "start": df["date"].iloc[0],
                "end": df["date"].iloc[-1],
                "days": len(df),
            },
            "best_strategy": {
                "id": best_strategy["strategy_id"],
                "name": best_strategy["strategy_name"],
                "category": best_strategy["category"],
                "risk_level": best_strategy["risk_level"],
                "total_return_pct": best_strategy["total_return_pct"],
                "max_drawdown_pct": best_strategy["max_drawdown_pct"],
                "win_rate": best_strategy["win_rate"],
                "score": round(best_strategy["score"], 4),
            },
            "comparison": comparison_results,
            "ranking": comparison_df[
                [
                    "strategy_name",
                    "total_return_pct",
                    "max_drawdown_pct",
                    "win_rate",
                    "score",
                ]
            ].to_dict("records"),
        }

    def plot_analysis(
        self, symbol: str, save_dir: str = "output/charts", days: int = 120
    ):
        """绘制分析图表"""
        # 获取数据
        df = db.get_daily_data(symbol)

        if df.empty:
            logger.error(f"无数据可绘图: {symbol}")
            return

        # 计算指标
        df = TechnicalIndicators.calculate_all(df)

        # 限制显示天数
        if len(df) > days:
            df = df.tail(days).reset_index(drop=True)

        # 创建输出目录
        os.makedirs(save_dir, exist_ok=True)

        # 绘制K线图
        self.visualizer.plot_candlestick(
            df,
            title=f"{symbol} K线图",
            save_path=f"{save_dir}/{symbol}_candlestick.png",
        )

        # 绘制技术指标
        self.visualizer.plot_with_indicators(
            df,
            indicators=["macd", "rsi", "bollinger"],
            title=f"{symbol} 技术分析",
            save_path=f"{save_dir}/{symbol}_indicators.png",
        )

        logger.info(f"图表已保存到 {save_dir}")

    def get_watchlist_signals(
        self,
        symbols: List[tuple],  # [(symbol, market), ...]
        strategies: Optional[List[str]] = None,
    ) -> pd.DataFrame:
        """获取关注列表的信号"""
        results = []

        for symbol, market in symbols:
            try:
                result = self.analyze(symbol, market, strategies)

                if "error" in result:
                    continue

                summary = result.get("data_summary", {})
                results.append(
                    {
                        "symbol": symbol,
                        "market": market,
                        "price": summary.get("close", 0),
                        "change_pct": summary.get("change_pct", 0),
                        "signal": result.get("final_signal", "HOLD"),
                        "confidence": result.get("confidence", 0),
                        "rsi": summary.get("rsi", None),
                    }
                )
            except Exception as e:
                logger.error(f"分析 {symbol} 失败: {e}")

        return pd.DataFrame(results)


def main():
    """主函数 - 示例用法"""
    analyzer = StockAnalyzer()

    print("=" * 60)
    print("股票分析系统")
    print("=" * 60)

    # 示例1: 分析A股
    symbol = "000001"  # 平安银行
    print(f"\n正在分析股票: {symbol}")
    result = analyzer.analyze(symbol, market="A")

    if "error" not in result:
        print(f"\n分析结果:")
        print(f"  当前价格: {result['data_summary']['close']}")
        print(f"  综合信号: {result['final_signal']}")
        print(f"  置信度: {result['confidence']:.2f}")
        print(f"\n各策略详情:")
        for name, detail in result["details"].items():
            print(f"  {name}: {detail['signal']} - {detail.get('reason', '')}")

    # 示例2: 回测
    print(f"\n正在回测 {symbol} 的MACD策略...")
    backtest_result = analyzer.backtest(symbol, "macd", market="A")

    if "error" not in backtest_result:
        print(f"\n回测结果:")
        print(f"  初始资金: {backtest_result['initial_cash']}")
        print(f"  最终权益: {backtest_result['final_equity']:.2f}")
        print(f"  总收益率: {backtest_result['total_return_pct']}")
        print(f"  最大回撤: {backtest_result['max_drawdown_pct']}")
        print(f"  交易次数: {backtest_result['total_trades']}")

    # 示例3: 绘制图表
    print(f"\n正在生成图表...")
    analyzer.plot_analysis(symbol)

    print("\n分析完成!")


if __name__ == "__main__":
    main()
