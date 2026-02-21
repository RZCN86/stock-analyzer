import streamlit as st
import pandas as pd
from datetime import datetime, timedelta

from main import StockAnalyzer
from database.db_manager import db
from analysis.indicators import TechnicalIndicators
from utils.stock_name import get_stock_name
from utils.history import add_to_history, get_history, clear_history

from web.constants import (
    ALL_STRATEGIES,
    STRATEGY_NAMES,
    STRATEGY_CATEGORIES,
    MARKET_LABELS,
)
from web.web_utils import currency, fmt_volume, data_freshness
from web.charts import (
    chart_candlestick,
    chart_macd,
    chart_rsi,
    chart_bollinger,
    chart_kdj,
)
from web.components import (
    show_signal_card,
    show_backtest_single,
    show_backtest_multiple,
)


@st.cache_resource
def get_analyzer():
    return StockAnalyzer()


@st.cache_data(ttl=300)
def _cached_get_daily_data(symbol: str):
    return db.get_daily_data(symbol)


@st.cache_data(ttl=3600)
def _cached_get_stock_name(symbol: str, market: str):
    return get_stock_name(symbol, market)


def sidebar():
    st.sidebar.title("📊 股票分析系统")
    st.sidebar.markdown("---")

    current_symbol = st.session_state.get("selected_symbol", "000001")
    current_market = st.session_state.get("selected_market", "A")
    if current_market not in ["A", "US", "ETF"]:
        current_market = "A"

    symbol = st.sidebar.text_input(
        "股票代码",
        value=current_symbol,
        help="A股请输入6位数字代码，美股请输入字母代码",
    )

    market_options = ["A", "US", "ETF"]
    market = st.sidebar.selectbox(
        "市场",
        options=market_options,
        index=market_options.index(current_market),
        format_func=lambda x: MARKET_LABELS[x],
        help="选择股票市场",
    )

    if market == "ETF":
        market = "A"
        is_etf = True
    else:
        is_etf = False

    st.sidebar.markdown("---")

    st.sidebar.subheader("🕐 最近查询")
    history = get_history(limit=10)

    if history:
        for item in history:
            mkt = item.get("market", "A")
            badge = {"A": "[A股]", "US": "[美股]", "ETF": "[ETF]"}.get(mkt, "")
            btn_label = f"{badge} {item['name']} ({item['symbol']})"
            if st.sidebar.button(
                btn_label,
                key=f"hist_{item['symbol']}_{mkt}",
                use_container_width=True,
            ):
                st.session_state.selected_symbol = item["symbol"].strip()
                st.session_state.selected_market = mkt
                st.rerun()

        if st.sidebar.button("🗑️ 清空历史", use_container_width=True):
            clear_history()
            st.sidebar.success("历史记录已清空！")
            st.rerun()
    else:
        st.sidebar.info("暂无查询记录")

    st.sidebar.markdown("---")

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

    st.sidebar.subheader("🎯 策略配置")

    if "strat_rev" not in st.session_state:
        st.session_state.strat_rev = 0

    def _toggle_select_all():
        st.session_state.strat_rev += 1

    select_all = st.sidebar.checkbox(
        "✅ 全选所有策略", key="select_all_cb", on_change=_toggle_select_all
    )

    default_strategies = ["ma_cross", "macd", "rsi", "multi_factor"]
    rev = st.session_state.strat_rev

    selected_strategies = []
    for cat, members in STRATEGY_CATEGORIES.items():
        with st.sidebar.expander(
            f"{cat} ({len(members)})", expanded=(cat == "趋势跟踪")
        ):
            for s in members:
                checked = st.checkbox(
                    STRATEGY_NAMES[s],
                    value=select_all if rev > 0 else (s in default_strategies),
                    key=f"strat_{s}_v{rev}",
                )
                if checked:
                    selected_strategies.append(s)

    if not selected_strategies:
        selected_strategies = ["ma_cross", "macd", "rsi", "multi_factor"]

    st.sidebar.markdown("---")

    st.sidebar.subheader("📈 回测设置")
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
    st.sidebar.info("💡 输入股票代码后，系统自动开始分析")

    return (
        symbol,
        market,
        is_etf,
        selected_strategies,
        enable_backtest,
        backtest_strategy,
        backtest_strategies,
        backtest_mode,
        start_date,
        end_date,
        fetch_data,
    )


def page_stock_analysis():
    analyzer = get_analyzer()

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

    st.session_state.selected_symbol = symbol
    st.session_state.selected_market = "ETF" if is_etf else market

    stock_name = _cached_get_stock_name(symbol, market)

    if stock_name != symbol:
        st.title(f"📈 {stock_name} ({symbol})")
    else:
        st.title(f"📈 股票分析 — {symbol}")

    if fetch_data:
        with st.spinner("正在获取数据..."):
            if is_etf:
                df = analyzer.ak_fetcher.fetch_etf_data(symbol)
                if not df.empty:
                    db.save_daily_data(symbol, df)
            else:
                df = analyzer.fetch_and_store(symbol, market, force_update=True)
        _cached_get_daily_data.clear()
        st.success(f"✅ {symbol} ({stock_name}) 数据更新完成！")

    df = _cached_get_daily_data(symbol)

    if df.empty:
        st.warning(f"⚠️ 本地无 {symbol} 的数据，正在自动获取...")
        with st.spinner("获取数据中..."):
            if is_etf:
                df = analyzer.ak_fetcher.fetch_etf_data(symbol)
                if not df.empty:
                    db.save_daily_data(symbol, df)
            else:
                df = analyzer.fetch_and_store(symbol, market)
        _cached_get_daily_data.clear()
        df = _cached_get_daily_data(symbol)

    if df.empty:
        st.error(f"❌ 无法获取 {symbol} 的数据，请检查代码是否正确")
        return

    add_to_history(symbol, stock_name, market)

    latest = df.iloc[-1]
    prev = df.iloc[-2] if len(df) > 1 else latest
    sym = currency(market)

    c1, c2, c3, c4 = st.columns(4)
    with c1:
        pct = latest.get("pct_change", 0)
        st.metric(
            label=stock_name,
            value=f"{sym}{latest['close']:.2f}",
            delta=f"{pct:.2f}%",
        )
    with c2:
        st.metric(label="今日最高", value=f"{sym}{latest['high']:.2f}")
    with c3:
        st.metric(label="今日最低", value=f"{sym}{latest['low']:.2f}")
    with c4:
        st.metric(label="成交量", value=fmt_volume(latest.get("volume", 0)))

    st.markdown(data_freshness(df), unsafe_allow_html=True)

    st.markdown("---")

    df_with_indicators = TechnicalIndicators.calculate_all(df)

    with st.spinner("正在进行技术分析..."):
        result = analyzer.strategy_engine.analyze(df_with_indicators, strategies)

    st.subheader("🎯 交易信号")
    show_signal_card(result, market)

    st.markdown("---")

    st.subheader("📊 技术分析图表")

    days_to_show = st.slider(
        "显示天数", min_value=30, max_value=min(500, len(df)), value=120
    )
    df_display = df_with_indicators.tail(days_to_show).reset_index(drop=True)

    tab_k, tab_macd, tab_rsi, tab_boll, tab_kdj, tab_data = st.tabs(
        ["🕯️ K线图", "📊 MACD", "📈 RSI", "📉 布林带", "🔀 KDJ", "📋 原始数据"]
    )

    with tab_k:
        fig = chart_candlestick(df_display, symbol, stock_name)
        st.plotly_chart(fig, use_container_width=True)

    with tab_macd:
        fig = chart_macd(df_display)
        if fig:
            st.plotly_chart(fig, use_container_width=True)
        else:
            st.info("MACD 数据不足")

    with tab_rsi:
        fig = chart_rsi(df_display)
        if fig:
            st.plotly_chart(fig, use_container_width=True)
        else:
            st.info("RSI 数据不足")

    with tab_boll:
        fig = chart_bollinger(df_display)
        if fig:
            st.plotly_chart(fig, use_container_width=True)
        else:
            st.info("布林带数据不足")

    with tab_kdj:
        fig = chart_kdj(df_display)
        if fig:
            st.plotly_chart(fig, use_container_width=True)
        else:
            st.info("KDJ 数据不足")

    with tab_data:
        df_table = df_display.tail(50).copy()
        display_cols = ["date", "open", "high", "low", "close", "volume"]
        if "pct_change" in df_table.columns:
            display_cols.append("pct_change")
        available_cols = [c for c in display_cols if c in df_table.columns]
        df_show = df_table[available_cols].copy()
        col_map = {
            "date": "日期",
            "open": "开盘",
            "high": "最高",
            "low": "最低",
            "close": "收盘",
            "volume": "成交量",
            "pct_change": "涨跌幅%",
        }
        df_show.columns = [col_map.get(c, c) for c in available_cols]

        def color_pct(val):
            if not isinstance(val, (int, float)):
                return ""
            if val > 0:
                return "color: #c62828"
            if val < 0:
                return "color: #2e7d32"
            return ""

        if "涨跌幅%" in df_show.columns:
            styled = df_show.style.map(color_pct, subset=["涨跌幅%"])
            st.dataframe(styled, use_container_width=True, hide_index=True)
        else:
            st.dataframe(df_show, use_container_width=True, hide_index=True)

        csv = df_display.to_csv(index=False).encode("utf-8-sig")
        st.download_button(
            label="📥 下载数据 (CSV)",
            data=csv,
            file_name=f"{symbol}_{datetime.now().strftime('%Y%m%d')}.csv",
            mime="text/csv",
        )

    st.markdown("---")

    if enable_backtest:
        if backtest_mode == "single" and backtest_strategy:
            st.subheader(
                f"📈 单策略回测 — {STRATEGY_NAMES.get(backtest_strategy, backtest_strategy)}"
            )
            with st.spinner("正在进行回测..."):
                backtest_result = analyzer.backtest(symbol, backtest_strategy, market)
            show_backtest_single(backtest_result, stock_name, symbol, market)

        elif backtest_mode == "multiple" and backtest_strategies:
            st.subheader("📊 多策略回测对比")
            with st.spinner("正在进行多策略回测对比..."):
                start_str = start_date.strftime("%Y-%m-%d")
                end_str = end_date.strftime("%Y-%m-%d")
                comparison_result = analyzer.backtest_multiple(
                    symbol=symbol,
                    strategy_names=backtest_strategies,
                    market=market,
                    start_date=start_str,
                    end_date=end_str,
                )
            show_backtest_multiple(comparison_result, market)

    st.markdown("---")
    st.markdown(
        '<div class="disclaimer">⚠️ <b>免责声明</b>：本系统仅供学习研究使用，'
        "不构成投资建议。股市有风险，投资需谨慎。</div>",
        unsafe_allow_html=True,
    )
