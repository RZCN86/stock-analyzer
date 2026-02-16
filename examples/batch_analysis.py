#!/usr/bin/env python3
"""
示例脚本: 批量分析自选股票
"""

import sys
import os

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from main import StockAnalyzer


def main():
    analyzer = StockAnalyzer()

    # 定义自选股票列表
    watchlist = [
        # A股
        ("000001", "A", "平安银行"),
        ("000002", "A", "万科A"),
        ("600519", "A", "贵州茅台"),
        ("000858", "A", "五粮液"),
        ("002594", "A", "比亚迪"),
        ("300750", "A", "宁德时代"),
        # 美股
        ("AAPL", "US", "苹果"),
        ("MSFT", "US", "微软"),
        ("GOOGL", "US", "谷歌"),
        ("TSLA", "US", "特斯拉"),
        ("NVDA", "US", "英伟达"),
        # ETF
        ("510300", "ETF", "沪深300ETF"),
        ("510500", "ETF", "中证500ETF"),
        ("512000", "ETF", "券商ETF"),
    ]

    print("=" * 80)
    print("股票批量分析报告")
    print("=" * 80)
    print(
        f"{'代码':<12} {'名称':<12} {'市场':<6} {'价格':<10} {'涨跌幅':<10} {'信号':<8} {'置信度':<8}"
    )
    print("-" * 80)

    results = []

    for symbol, market, name in watchlist:
        try:
            # 获取数据（如果不存在则下载）
            df = analyzer.fetch_and_store(symbol, market)

            if df.empty:
                print(f"{symbol:<12} {name:<12} {market:<6} 数据获取失败")
                continue

            # 分析
            result = analyzer.analyze(symbol, market)
            summary = result.get("data_summary", {})

            signal = result.get("final_signal", "HOLD")
            confidence = result.get("confidence", 0)
            price = summary.get("close", 0)
            change = summary.get("change_pct", 0)

            results.append(
                {
                    "symbol": symbol,
                    "name": name,
                    "market": market,
                    "price": price,
                    "change": change,
                    "signal": signal,
                    "confidence": confidence,
                    "details": result.get("details", {}),
                }
            )

            signal_color = {"BUY": "🟢", "SELL": "🔴", "HOLD": "⚪"}.get(signal, "⚪")

            print(
                f"{symbol:<12} {name:<12} {market:<6} {price:<10.2f} {change:<10.2f}% {signal_color} {signal:<6} {confidence:<8.2f}"
            )

        except Exception as e:
            print(f"{symbol:<12} {name:<12} {market:<6} 分析失败: {str(e)[:20]}")

    print("=" * 80)

    # 生成详细报告
    print("\n📊 详细交易建议:")
    print("-" * 80)

    buy_signals = [r for r in results if r["signal"] == "BUY"]
    sell_signals = [r for r in results if r["signal"] == "SELL"]

    if buy_signals:
        print("\n🟢 买入建议:")
        for r in sorted(buy_signals, key=lambda x: x["confidence"], reverse=True):
            print(f"  • {r['symbol']} ({r['name']}): 置信度 {r['confidence']:.2f}")
            for strategy, detail in r["details"].items():
                if detail.get("signal") == "BUY":
                    print(f"    - {strategy}: {detail.get('reason', '')}")

    if sell_signals:
        print("\n🔴 卖出建议:")
        for r in sorted(sell_signals, key=lambda x: x["confidence"], reverse=True):
            print(f"  • {r['symbol']} ({r['name']}): 置信度 {r['confidence']:.2f}")
            for strategy, detail in r["details"].items():
                if detail.get("signal") == "SELL":
                    print(f"    - {strategy}: {detail.get('reason', '')}")

    if not buy_signals and not sell_signals:
        print("\n⚪ 当前无明确交易信号，建议持仓观望。")

    print("\n" + "=" * 80)
    print("免责声明: 以上分析仅供参考，不构成投资建议。股市有风险，投资需谨慎。")
    print("=" * 80)


if __name__ == "__main__":
    main()
