import streamlit as st
import sys
import os
from datetime import datetime, timedelta
import pandas as pd
import matplotlib.pyplot as plt

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

# 设置页面配置（必须在其他streamlit命令之前）
st.set_page_config(
    page_title="股票分析系统",
    page_icon="📈",
    layout="wide",
    initial_sidebar_state="expanded",
)

# 配置中文字体
from utils.font_config import setup_chinese_font, font_prop

setup_chinese_font()

from main import StockAnalyzer
from database.db_manager import db
from analysis.indicators import TechnicalIndicators
from visualization.charts import ChartVisualizer
from utils.stock_name import get_stock_name, get_stock_info
from utils.history import add_to_history, get_history, clear_history

ALL_STRATEGIES = [
    "ma_cross",
    "macd",
    "rsi",
    "bollinger",
    "momentum",
    "mean_reversion",
    "breakout",
    "kdj",
    "volume",
    "multi_factor",
    "grid",
    "fractal",
]

STRATEGY_NAMES = {
    "ma_cross": "双均线交叉",
    "macd": "MACD策略",
    "rsi": "RSI超买卖",
    "bollinger": "布林带突破",
    "momentum": "动量策略",
    "mean_reversion": "均值回归",
    "breakout": "突破策略",
    "kdj": "KDJ随机指标",
    "volume": "成交量策略",
    "multi_factor": "多因子组合",
    "grid": "网格交易",
    "fractal": "分形交易",
}


# 初始化分析器
@st.cache_resource
def get_analyzer():
    return StockAnalyzer()


analyzer = get_analyzer()


# 侧边栏
def sidebar():
    st.sidebar.title("📊 股票分析系统")
    st.sidebar.markdown("---")

    current_symbol = st.session_state.get("selected_symbol", "000001")
    current_market = st.session_state.get("selected_market", "A")
    if current_market not in ["A", "US", "ETF"]:
        current_market = "A"

    # 股票代码输入
    symbol = st.sidebar.text_input(
        "股票代码",
        value=current_symbol,
        help="A股请输入6位数字代码，美股请输入字母代码",
    )

    # 市场选择
    market_options = ["A", "US", "ETF"]
    market = st.sidebar.selectbox(
        "市场",
        options=market_options,
        index=market_options.index(current_market),
        format_func=lambda x: {"A": "A股", "US": "美股", "ETF": "ETF"}[x],
        help="选择股票市场",
    )

    # 自动调整ETF市场
    if market == "ETF":
        market = "A"
        is_etf = True
    else:
        is_etf = False

    st.sidebar.markdown("---")

    # 最近查询历史
    st.sidebar.subheader("🕐 最近查询")
    history = get_history(limit=10)

    if history:
        for item in history:
            col1, col2 = st.sidebar.columns([3, 1])
            with col1:
                # 显示按钮让用户快速选择
                if st.button(
                    f"{item['name']} ({item['symbol']})",
                    key=f"hist_{item['symbol']}_{item['market']}",
                    use_container_width=True,
                ):
                    # 使用session_state来传递值
                    st.session_state.selected_symbol = item["symbol"].strip()
                    st.session_state.selected_market = item["market"]
                    st.rerun()

        # 清空历史按钮
        if st.sidebar.button("🗑️ 清空历史", use_container_width=True):
            clear_history()
            st.sidebar.success("历史记录已清空！")
            st.rerun()
    else:
        st.sidebar.info("暂无查询记录")

    st.sidebar.markdown("---")

    # 数据操作
    st.sidebar.subheader("📥 数据管理")
    col1, col2 = st.sidebar.columns(2)

    with col1:
        fetch_data = st.button("🔄 更新数据", use_container_width=True)

    with col2:
        clear_cache = st.button("🗑️ 清除缓存", use_container_width=True)

    if clear_cache:
        st.cache_data.clear()
        st.sidebar.success("缓存已清除！")

    st.sidebar.markdown("---")

    # 策略选择
    st.sidebar.subheader("🎯 策略配置")

    select_all = st.sidebar.checkbox("✅ 全选所有策略", value=False)

    if select_all:
        default_strategies = ALL_STRATEGIES
    else:
        default_strategies = ["ma_cross", "macd", "rsi", "multi_factor"]

    strategies = st.sidebar.multiselect(
        "选择策略",
        options=ALL_STRATEGIES,
        default=default_strategies,
        format_func=lambda x: STRATEGY_NAMES[x],
    )

    st.sidebar.markdown("---")

    # 回测配置
    st.sidebar.subheader("📈 回测设置")

    # 回测模式选择
    backtest_mode = st.sidebar.radio(
        "回测模式",
        options=["single", "multiple"],
        format_func=lambda x: "单策略回测" if x == "single" else "多策略对比",
    )

    enable_backtest = st.sidebar.checkbox("启用回测", value=False)

    backtest_strategy = None
    backtest_strategies = []
    start_date = datetime.now() - timedelta(days=365)
    end_date = datetime.now()

    if enable_backtest:
        if backtest_mode == "single":
            backtest_strategy = st.sidebar.selectbox(
                "选择策略",
                options=ALL_STRATEGIES,
                format_func=lambda x: STRATEGY_NAMES[x],
            )
        else:
            backtest_strategies = st.sidebar.multiselect(
                "选择对比策略（建议2-5个）",
                options=ALL_STRATEGIES,
                default=["ma_cross", "macd", "rsi"],
                format_func=lambda x: STRATEGY_NAMES[x],
            )

        # 回测时间区间
        st.sidebar.subheader("⏱️ 回测区间")
        col1, col2 = st.sidebar.columns(2)
        with col1:
            start_date = st.sidebar.date_input(
                "开始日期",
                value=datetime.now() - timedelta(days=365),
                max_value=datetime.now(),
            )
        with col2:
            end_date = st.sidebar.date_input(
                "结束日期",
                value=datetime.now(),
                max_value=datetime.now(),
            )

    st.sidebar.markdown("---")
    st.sidebar.info("💡 提示：输入股票代码后，点击'分析'按钮开始分析")

    return (
        symbol,
        market,
        is_etf,
        strategies,
        enable_backtest,
        backtest_strategy,
        backtest_strategies,
        backtest_mode,
        start_date,
        end_date,
        fetch_data,
    )


# 主页面
def main():
    # 初始化session_state
    if "selected_symbol" not in st.session_state:
        st.session_state.selected_symbol = "000001"
    if "selected_market" not in st.session_state:
        st.session_state.selected_market = "A"

    (
        symbol,
        market,
        is_etf,
        strategies,
        enable_backtest,
        backtest_strategy,
        backtest_strategies,
        backtest_mode,
        start_date,
        end_date,
        fetch_data,
    ) = sidebar()

    symbol = symbol.strip()
    if market == "US":
        symbol = symbol.upper()

    # 将当前输入同步回session_state，避免历史值覆盖用户输入
    st.session_state.selected_symbol = symbol
    st.session_state.selected_market = "ETF" if is_etf else market

    # 获取股票名称
    stock_name = get_stock_name(symbol, market)

    # 页面标题（显示股票名称）
    if stock_name != symbol:
        st.title(f"📈 {stock_name} ({symbol})")
    else:
        st.title(f"📈 股票分析 - {symbol}")

    # 获取数据
    if fetch_data:
        with st.spinner("正在获取数据..."):
            if is_etf:
                df = analyzer.ak_fetcher.fetch_etf_data(symbol)
                if not df.empty:
                    db.save_daily_data(symbol, df)
            else:
                df = analyzer.fetch_and_store(symbol, market, force_update=True)
        st.success(f"✅ {symbol} ({stock_name}) 数据更新完成！")

    # 检查本地数据
    df = db.get_daily_data(symbol)

    if df.empty:
        st.warning(f"⚠️ 本地无 {symbol} 的数据，正在自动获取...")
        with st.spinner("获取数据中..."):
            if is_etf:
                df = analyzer.ak_fetcher.fetch_etf_data(symbol)
                if not df.empty:
                    db.save_daily_data(symbol, df)
            else:
                df = analyzer.fetch_and_store(symbol, market)

    if df.empty:
        st.error(f"❌ 无法获取 {symbol} 的数据，请检查代码是否正确")
        return

    # 成功获取数据，添加到历史记录
    add_to_history(symbol, stock_name, market)

    # 显示数据概览（包含股票名称）
    latest = df.iloc[-1]
    prev = df.iloc[-2] if len(df) > 1 else latest

    # 显示股票信息卡片
    info_col1, info_col2, info_col3, info_col4 = st.columns(4)

    with info_col1:
        st.metric(
            label=f"{stock_name}",
            value=f"¥{latest['close']:.2f}",
            delta=f"{latest.get('pct_change', 0):.2f}%",
        )

    with info_col2:
        st.metric(label="今日最高", value=f"¥{latest['high']:.2f}")

    with info_col3:
        st.metric(label="今日最低", value=f"¥{latest['low']:.2f}")

    with info_col4:
        st.metric(label="成交量", value=f"{latest.get('volume', 0) / 10000:.0f}万")

    st.markdown("---")

    # 计算技术指标
    df_with_indicators = TechnicalIndicators.calculate_all(df)

    # 运行策略分析
    with st.spinner("正在进行技术分析..."):
        result = analyzer.strategy_engine.analyze(df_with_indicators, strategies)

    # 显示分析结果
    st.subheader("🎯 交易信号")

    signal_col1, signal_col2, signal_col3 = st.columns([1, 1, 2])

    with signal_col1:
        final_signal = result.get("final_signal", "HOLD")
        signal_color = {"BUY": "🟢", "SELL": "🔴", "HOLD": "⚪"}.get(final_signal, "⚪")

        st.markdown(f"### {signal_color} {final_signal}")

    with signal_col2:
        confidence = result.get("confidence", 0)
        buy_signals = result.get("buy_signals", [])
        sell_signals = result.get("sell_signals", [])

        st.markdown(f"### 置信度: {confidence:.2%}")

        if buy_signals:
            buy_conf = sum(c for _, c in buy_signals) / len(buy_signals)
            st.markdown(f"🟢 **{len(buy_signals)}个买入** (平均{buy_conf:.0%})")
        if sell_signals:
            sell_conf = sum(c for _, c in sell_signals) / len(sell_signals)
            st.markdown(f"🔴 **{len(sell_signals)}个卖出** (平均{sell_conf:.0%})")
        if not buy_signals and not sell_signals:
            st.markdown(f"⚪ **{len(strategies)}个观望**")

    with signal_col3:
        # 显示各策略详情
        details = result.get("details", {})
        for name, detail in details.items():
            signal = detail.get("signal", "HOLD")
            reason = detail.get("reason", "")
            conf = detail.get("confidence", 0)
            icon = {"BUY": "🟢", "SELL": "🔴", "HOLD": "⚪"}.get(signal, "⚪")
            st.markdown(f"{icon} **{name}**: {signal} (置信度:{conf:.0%}) - {reason}")

    st.markdown("---")

    # 绘制图表
    st.subheader("📊 技术分析图表")

    # 限制显示天数
    days_to_show = st.slider(
        "显示天数", min_value=30, max_value=min(500, len(df)), value=120
    )
    df_display = df_with_indicators.tail(days_to_show).reset_index(drop=True)

    # 创建图表标签页
    tab1, tab2, tab3 = st.tabs(["K线图", "技术指标", "原始数据"])

    with tab1:
        st.markdown("**K线图与均线**")
        fig, ax = plt.subplots(figsize=(12, 6))

        # 绘制收盘价和均线
        ax.plot(df_display["date"], df_display["close"], label="收盘价", linewidth=2)
        if "ma5" in df_display.columns:
            ax.plot(df_display["date"], df_display["ma5"], label="MA5", alpha=0.7)
        if "ma20" in df_display.columns:
            ax.plot(df_display["date"], df_display["ma20"], label="MA20", alpha=0.7)
        if "ma60" in df_display.columns:
            ax.plot(df_display["date"], df_display["ma60"], label="MA60", alpha=0.7)

        ax.set_xlabel("日期")
        ax.set_ylabel("价格")
        ax.set_title(f"{symbol} 价格走势")
        ax.legend()
        ax.grid(True, alpha=0.3)
        plt.xticks(rotation=45)
        plt.tight_layout()

        st.pyplot(fig)
        plt.close()

    with tab2:
        st.markdown("**MACD指标**")
        if "macd_dif" in df_display.columns:
            fig, (ax1, ax2) = plt.subplots(
                2, 1, figsize=(12, 8), gridspec_kw={"height_ratios": [2, 1]}
            )

            # 价格
            ax1.plot(df_display["date"], df_display["close"], label="收盘价")
            ax1.set_ylabel("价格")
            ax1.legend()
            ax1.grid(True, alpha=0.3)

            # MACD
            ax2.plot(
                df_display["date"], df_display["macd_dif"], label="DIF", color="blue"
            )
            ax2.plot(
                df_display["date"], df_display["macd_dea"], label="DEA", color="orange"
            )

            colors = ["red" if h > 0 else "green" for h in df_display["macd_histogram"]]
            ax2.bar(
                df_display["date"],
                df_display["macd_histogram"],
                color=colors,
                alpha=0.5,
            )
            ax2.axhline(y=0, color="black", linestyle="-", linewidth=0.5)
            ax2.set_ylabel("MACD")
            ax2.legend()
            ax2.grid(True, alpha=0.3)

            plt.tight_layout()
            st.pyplot(fig)
            plt.close()

        st.markdown("**RSI指标**")
        if "rsi" in df_display.columns:
            fig, ax = plt.subplots(figsize=(12, 4))
            ax.plot(df_display["date"], df_display["rsi"], label="RSI", color="purple")
            ax.axhline(y=70, color="red", linestyle="--", label="超买(70)")
            ax.axhline(y=30, color="green", linestyle="--", label="超卖(30)")
            ax.fill_between(df_display["date"], 30, 70, alpha=0.1, color="gray")
            ax.set_ylabel("RSI")
            ax.set_ylim(0, 100)
            ax.legend()
            ax.grid(True, alpha=0.3)
            plt.tight_layout()
            st.pyplot(fig)
            plt.close()

    with tab3:
        st.dataframe(df_display.tail(50), use_container_width=True)

    st.markdown("---")

    # 回测部分
    if enable_backtest:
        if backtest_mode == "single" and backtest_strategy:
            # 单策略回测
            st.subheader(
                f"📈 单策略回测 - {STRATEGY_NAMES.get(backtest_strategy, backtest_strategy)}"
            )

            with st.spinner("正在进行回测..."):
                backtest_result = analyzer.backtest(symbol, backtest_strategy, market)

            if "error" not in backtest_result:
                col1, col2, col3, col4 = st.columns(4)

                with col1:
                    st.metric(
                        label="总收益率",
                        value=backtest_result.get("total_return_pct", "N/A"),
                    )

                with col2:
                    st.metric(
                        label="最大回撤",
                        value=backtest_result.get("max_drawdown_pct", "N/A"),
                    )

                with col3:
                    st.metric(
                        label="交易次数",
                        value=str(backtest_result.get("total_trades", 0)),
                    )

                with col4:
                    st.metric(
                        label="胜率",
                        value=backtest_result.get("win_rate", "N/A"),
                    )

                # 绘制资金曲线
                equity_curve = backtest_result.get("equity_curve", [])
                if equity_curve:
                    fig, ax = plt.subplots(figsize=(12, 4))
                    ax.plot(equity_curve, label="资金曲线", color="blue")
                    ax.axhline(
                        y=backtest_result.get("initial_cash", 100000),
                        color="red",
                        linestyle="--",
                        alpha=0.5,
                        label="初始资金",
                    )
                    ax.set_xlabel("交易日")
                    ax.set_ylabel("资金")
                    ax.set_title(f"{stock_name} ({symbol}) 资金曲线")
                    ax.legend()
                    ax.grid(True, alpha=0.3)
                    plt.tight_layout()
                    st.pyplot(fig)
                    plt.close()
            else:
                st.error(f"回测失败: {backtest_result.get('error', '未知错误')}")

        elif backtest_mode == "multiple" and backtest_strategies:
            # 多策略对比回测
            st.subheader("📊 多策略回测对比")

            with st.spinner("正在进行多策略回测对比..."):
                # 格式化日期
                start_date_str = start_date.strftime("%Y-%m-%d")
                end_date_str = end_date.strftime("%Y-%m-%d")

                comparison_result = analyzer.backtest_multiple(
                    symbol=symbol,
                    strategy_names=backtest_strategies,
                    market=market,
                    start_date=start_date_str,
                    end_date=end_date_str,
                )

            if "error" not in comparison_result:
                # 显示最佳策略
                best = comparison_result.get("best_strategy", {})
                st.markdown(f"### 🏆 最佳策略: **{best.get('name', 'N/A')}**")

                best_col1, best_col2, best_col3, best_col4 = st.columns(4)
                with best_col1:
                    st.metric("总收益率", best.get("total_return_pct", "N/A"))
                with best_col2:
                    st.metric("最大回撤", best.get("max_drawdown_pct", "N/A"))
                with best_col3:
                    st.metric("胜率", best.get("win_rate", "N/A"))
                with best_col4:
                    st.metric("综合得分", f"{best.get('score', 0):.2f}")

                st.markdown("---")

                # 显示对比表格
                st.subheader("📈 策略对比详情")

                comparison_data = comparison_result.get("comparison", [])
                if comparison_data:
                    df_comparison = pd.DataFrame(comparison_data)
                    # 选择要显示的列
                    display_columns = [
                        "strategy_name",
                        "category",
                        "risk_level",
                        "total_return_pct",
                        "max_drawdown_pct",
                        "win_rate",
                        "total_trades",
                    ]
                    df_display = df_comparison[display_columns].copy()
                    df_display.columns = [
                        "策略名称",
                        "分类",
                        "风险等级",
                        "总收益率",
                        "最大回撤",
                        "胜率",
                        "交易次数",
                    ]

                    # 高亮最佳策略
                    def highlight_best(row):
                        if row["策略名称"] == best.get("name"):
                            return ["background-color: rgba(0, 255, 0, 0.2)"] * len(row)
                        return [""] * len(row)

                    st.dataframe(
                        df_display.style.apply(highlight_best, axis=1),
                        use_container_width=True,
                    )

                # 显示排名
                st.subheader("🏆 策略排名（按综合得分）")
                ranking = comparison_result.get("ranking", [])
                if ranking:
                    for i, item in enumerate(ranking[:5], 1):  # 只显示前5
                        medal = {1: "🥇", 2: "🥈", 3: "🥉"}.get(i, f"{i}.")
                        st.markdown(
                            f"{medal} **{item['strategy_name']}** - "
                            f"收益: {item['total_return_pct']} | "
                            f"回撤: {item['max_drawdown_pct']} | "
                            f"胜率: {item['win_rate']} | "
                            f"得分: {item['score']:.2f}"
                        )
            else:
                st.error(f"回测对比失败: {comparison_result.get('error', '未知错误')}")

    st.markdown("---")
    st.caption(
        "⚠️ 免责声明：本系统仅供学习研究使用，不构成投资建议。股市有风险，投资需谨慎。"
    )


if __name__ == "__main__":
    main()
