import streamlit as st
import sys
import os
from datetime import datetime, timedelta
import pandas as pd
import plotly.graph_objects as go
from plotly.subplots import make_subplots

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

# 设置页面配置（必须在其他streamlit命令之前）
st.set_page_config(
    page_title="股票分析系统",
    page_icon="📈",
    layout="wide",
    initial_sidebar_state="expanded",
)

from main import StockAnalyzer
from database.db_manager import db
from analysis.indicators import TechnicalIndicators
from utils.stock_name import get_stock_name, get_stock_info
from utils.history import add_to_history, get_history, clear_history

# ─── 常量定义 ───────────────────────────────────────────────────────────────

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

STRATEGY_CATEGORIES = {
    "趋势跟踪": ["ma_cross", "macd", "momentum", "breakout"],
    "均值回归": ["rsi", "bollinger", "mean_reversion", "kdj"],
    "量价分析": ["volume"],
    "综合策略": ["multi_factor"],
    "套利策略": ["grid"],
    "趋势反转": ["fractal"],
}

MARKET_LABELS = {"A": "A股", "US": "美股", "ETF": "ETF"}

# ─── 自定义 CSS ─────────────────────────────────────────────────────────────

CUSTOM_CSS = """
<style>
/* 信号卡片 */
.signal-card {
    padding: 1.2rem; border-radius: 0.75rem; text-align: center;
    box-shadow: 0 2px 8px rgba(0,0,0,0.08); margin-bottom: 0.5rem;
}
.signal-buy  { background: linear-gradient(135deg, #e8f5e9 0%, #c8e6c9 100%); border-left: 4px solid #2e7d32; }
.signal-sell { background: linear-gradient(135deg, #ffebee 0%, #ffcdd2 100%); border-left: 4px solid #c62828; }
.signal-hold { background: linear-gradient(135deg, #f5f5f5 0%, #eeeeee 100%); border-left: 4px solid #757575; }
.signal-card h2 { margin: 0 0 0.3rem 0; font-size: 2rem; }
.signal-card p  { margin: 0; font-size: 0.9rem; color: #555; }

/* 策略标签 */
.strategy-tag {
    display: inline-block; padding: 0.15rem 0.5rem; border-radius: 0.25rem;
    font-size: 0.75rem; font-weight: 600; margin-right: 0.3rem;
}
.tag-buy  { background: #e8f5e9; color: #2e7d32; }
.tag-sell { background: #ffebee; color: #c62828; }
.tag-hold { background: #f5f5f5; color: #757575; }

/* 市场标签 */
.market-badge {
    display: inline-block; padding: 0.1rem 0.4rem; border-radius: 0.2rem;
    font-size: 0.7rem; font-weight: 700; margin-left: 0.3rem;
}
.badge-a   { background: #fff3e0; color: #e65100; }
.badge-us  { background: #e3f2fd; color: #1565c0; }
.badge-etf { background: #f3e5f5; color: #7b1fa2; }

/* 数据新鲜度 */
.freshness { font-size: 0.78rem; color: #888; margin-top: 0.2rem; }
.freshness-stale { color: #e65100; font-weight: 600; }

/* 免责声明 */
.disclaimer {
    background: #fffde7; border-left: 3px solid #f9a825; padding: 0.6rem 1rem;
    border-radius: 0 0.4rem 0.4rem 0; font-size: 0.82rem; color: #5d4037;
}
</style>
"""

# ─── 工具函数 ───────────────────────────────────────────────────────────────


def currency(market: str) -> str:
    return "$" if market == "US" else "¥"


def fmt_price(value: float, market: str) -> str:
    return f"{currency(market)}{value:.2f}"


def fmt_volume(vol: float) -> str:
    if vol >= 1e8:
        return f"{vol / 1e8:.2f}亿"
    return f"{vol / 1e4:.0f}万"


def market_badge_html(market: str) -> str:
    cls = {"A": "badge-a", "US": "badge-us", "ETF": "badge-etf"}.get(market, "badge-a")
    label = MARKET_LABELS.get(market, market)
    return f'<span class="market-badge {cls}">{label}</span>'


def data_freshness(df: pd.DataFrame) -> str:
    """返回数据新鲜度 HTML 标签"""
    if df.empty:
        return ""
    last_date = pd.to_datetime(df["date"].iloc[-1])
    delta = (datetime.now() - last_date).days
    if delta <= 1:
        return '<span class="freshness">📡 数据已是最新</span>'
    cls = "freshness-stale" if delta > 5 else "freshness"
    return f'<span class="{cls}">⏱️ 最新数据: {last_date.strftime("%Y-%m-%d")}（{delta}天前）</span>'


# ─── Plotly 图表 ────────────────────────────────────────────────────────────

PLOTLY_LAYOUT = dict(
    template="plotly_white",
    hovermode="x unified",
    legend=dict(orientation="h", yanchor="bottom", y=1.02, xanchor="right", x=1),
    margin=dict(l=0, r=0, t=30, b=0),
    xaxis_rangeslider_visible=False,
)

UP_COLOR = "#ef5350"  # 红涨
DOWN_COLOR = "#26a69a"  # 绿跌


def chart_candlestick(df: pd.DataFrame, symbol: str, stock_name: str) -> go.Figure:
    """K线 + 成交量 + 均线"""
    fig = make_subplots(
        rows=2,
        cols=1,
        shared_xaxes=True,
        vertical_spacing=0.03,
        row_heights=[0.75, 0.25],
    )

    # K线
    fig.add_trace(
        go.Candlestick(
            x=df["date"],
            open=df["open"],
            high=df["high"],
            low=df["low"],
            close=df["close"],
            name="K线",
            increasing_line_color=UP_COLOR,
            decreasing_line_color=DOWN_COLOR,
        ),
        row=1,
        col=1,
    )

    # 均线
    for col, color, label in [
        ("ma5", "#ff9800", "MA5"),
        ("ma20", "#2196f3", "MA20"),
        ("ma60", "#9c27b0", "MA60"),
    ]:
        if col in df.columns:
            fig.add_trace(
                go.Scatter(
                    x=df["date"],
                    y=df[col],
                    name=label,
                    line=dict(width=1, color=color),
                ),
                row=1,
                col=1,
            )

    # 成交量（涨红跌绿）
    colors = [
        UP_COLOR if c >= o else DOWN_COLOR for c, o in zip(df["close"], df["open"])
    ]
    fig.add_trace(
        go.Bar(
            x=df["date"],
            y=df["volume"],
            name="成交量",
            marker_color=colors,
            opacity=0.6,
            showlegend=False,
        ),
        row=2,
        col=1,
    )

    fig.update_layout(
        **PLOTLY_LAYOUT,
        height=520,
        title_text=f"{stock_name} ({symbol})",
        yaxis_title="价格",
        yaxis2_title="成交量",
    )
    fig.update_xaxes(type="category", nticks=12)
    return fig


def chart_macd(df: pd.DataFrame) -> go.Figure:
    """MACD 图"""
    if "macd_dif" not in df.columns:
        return None

    fig = make_subplots(
        rows=2,
        cols=1,
        shared_xaxes=True,
        vertical_spacing=0.03,
        row_heights=[0.6, 0.4],
    )

    fig.add_trace(
        go.Scatter(
            x=df["date"],
            y=df["close"],
            name="收盘价",
            line=dict(width=1.5, color="#1976d2"),
        ),
        row=1,
        col=1,
    )

    fig.add_trace(
        go.Scatter(
            x=df["date"],
            y=df["macd_dif"],
            name="DIF",
            line=dict(width=1.2, color="#2196f3"),
        ),
        row=2,
        col=1,
    )
    fig.add_trace(
        go.Scatter(
            x=df["date"],
            y=df["macd_dea"],
            name="DEA",
            line=dict(width=1.2, color="#ff9800"),
        ),
        row=2,
        col=1,
    )

    colors = [UP_COLOR if h >= 0 else DOWN_COLOR for h in df["macd_histogram"]]
    fig.add_trace(
        go.Bar(
            x=df["date"],
            y=df["macd_histogram"],
            name="MACD柱",
            marker_color=colors,
            opacity=0.7,
            showlegend=False,
        ),
        row=2,
        col=1,
    )
    fig.add_hline(y=0, line_dash="dot", line_color="grey", row=2, col=1)

    fig.update_layout(
        **PLOTLY_LAYOUT, height=480, yaxis_title="价格", yaxis2_title="MACD"
    )
    fig.update_xaxes(type="category", nticks=12)
    return fig


def chart_rsi(df: pd.DataFrame) -> go.Figure:
    """RSI 图"""
    if "rsi" not in df.columns:
        return None

    fig = go.Figure()
    fig.add_trace(
        go.Scatter(
            x=df["date"],
            y=df["rsi"],
            name="RSI",
            line=dict(width=1.5, color="#7b1fa2"),
        )
    )
    fig.add_hline(
        y=70, line_dash="dash", line_color="#ef5350", annotation_text="超买 70"
    )
    fig.add_hline(
        y=30, line_dash="dash", line_color="#26a69a", annotation_text="超卖 30"
    )
    fig.add_hrect(y0=30, y1=70, fillcolor="gray", opacity=0.06, line_width=0)

    fig.update_layout(
        **PLOTLY_LAYOUT, height=280, yaxis_title="RSI", yaxis=dict(range=[0, 100])
    )
    fig.update_xaxes(type="category", nticks=12)
    return fig


def chart_bollinger(df: pd.DataFrame) -> go.Figure:
    """布林带"""
    if "boll_mid" not in df.columns:
        return None

    fig = go.Figure()
    fig.add_trace(
        go.Scatter(
            x=df["date"],
            y=df["boll_upper"],
            name="上轨",
            line=dict(width=1, color="#ef5350", dash="dot"),
        )
    )
    fig.add_trace(
        go.Scatter(
            x=df["date"],
            y=df["boll_lower"],
            name="下轨",
            line=dict(width=1, color="#26a69a", dash="dot"),
            fill="tonexty",
            fillcolor="rgba(33,150,243,0.06)",
        )
    )
    fig.add_trace(
        go.Scatter(
            x=df["date"],
            y=df["boll_mid"],
            name="中轨",
            line=dict(width=1, color="#1976d2"),
        )
    )
    fig.add_trace(
        go.Scatter(
            x=df["date"],
            y=df["close"],
            name="收盘价",
            line=dict(width=1.5, color="#333"),
        )
    )

    fig.update_layout(**PLOTLY_LAYOUT, height=400, yaxis_title="价格")
    fig.update_xaxes(type="category", nticks=12)
    return fig


def chart_kdj(df: pd.DataFrame) -> go.Figure:
    """KDJ 图"""
    if "kdj_k" not in df.columns:
        return None

    fig = go.Figure()
    fig.add_trace(
        go.Scatter(
            x=df["date"],
            y=df["kdj_k"],
            name="K",
            line=dict(width=1.2, color="#2196f3"),
        )
    )
    fig.add_trace(
        go.Scatter(
            x=df["date"],
            y=df["kdj_d"],
            name="D",
            line=dict(width=1.2, color="#ff9800"),
        )
    )
    fig.add_trace(
        go.Scatter(
            x=df["date"],
            y=df["kdj_j"],
            name="J",
            line=dict(width=1, color="#9c27b0", dash="dot"),
        )
    )
    fig.add_hline(
        y=80, line_dash="dash", line_color="#ef5350", annotation_text="超买 80"
    )
    fig.add_hline(
        y=20, line_dash="dash", line_color="#26a69a", annotation_text="超卖 20"
    )

    fig.update_layout(**PLOTLY_LAYOUT, height=300, yaxis_title="KDJ")
    fig.update_xaxes(type="category", nticks=12)
    return fig


def chart_equity(
    equity_curve: list,
    trades: list,
    initial_cash: float,
    stock_name: str,
    symbol: str,
) -> go.Figure:
    """资金曲线 + 回撤"""
    eq = pd.Series(equity_curve, dtype=float)
    peak = eq.cummax()
    drawdown = (eq - peak) / peak * 100

    fig = make_subplots(
        rows=2,
        cols=1,
        shared_xaxes=True,
        vertical_spacing=0.05,
        row_heights=[0.7, 0.3],
    )

    fig.add_trace(
        go.Scatter(
            x=list(range(len(eq))),
            y=eq,
            name="资金曲线",
            line=dict(width=1.8, color="#1976d2"),
            fill="tozeroy",
            fillcolor="rgba(25,118,210,0.06)",
        ),
        row=1,
        col=1,
    )
    fig.add_hline(
        y=initial_cash,
        line_dash="dash",
        line_color="#ef5350",
        annotation_text="初始资金",
        row=1,
        col=1,
    )

    fig.add_trace(
        go.Scatter(
            x=list(range(len(drawdown))),
            y=drawdown,
            name="回撤%",
            line=dict(width=1, color="#ef5350"),
            fill="tozeroy",
            fillcolor="rgba(239,83,80,0.1)",
        ),
        row=2,
        col=1,
    )

    fig.update_layout(
        **PLOTLY_LAYOUT,
        height=420,
        title_text=f"{stock_name} ({symbol}) 资金曲线",
        yaxis_title="资金 (元)",
        yaxis2_title="回撤 %",
    )
    return fig


def chart_win_loss_pie(trades: list) -> go.Figure:
    """胜负饼图"""
    sells = [t for t in trades if t.get("type") == "SELL"]
    wins = sum(1 for t in sells if t.get("pnl", t.get("revenue", 0)) > 0)
    losses = len(sells) - wins

    if not sells:
        return None

    fig = go.Figure(
        data=[
            go.Pie(
                labels=["盈利", "亏损"],
                values=[wins, losses],
                marker_colors=[DOWN_COLOR, UP_COLOR],  # 绿盈红亏
                hole=0.45,
                textinfo="label+value+percent",
            )
        ]
    )
    fig.update_layout(
        height=280,
        margin=dict(l=0, r=0, t=30, b=0),
        title_text="交易胜负分布",
    )
    return fig


# ─── 显示模块 ───────────────────────────────────────────────────────────────


def show_signal_card(result: dict, market: str):
    """信号卡片 + 置信度进度条"""
    final_signal = result.get("final_signal", "HOLD")
    confidence = result.get("confidence", 0)
    buy_signals = result.get("buy_signals", [])
    sell_signals = result.get("sell_signals", [])

    signal_map = {
        "BUY": ("🟢 买入", "signal-buy", "做多信号"),
        "SELL": ("🔴 卖出", "signal-sell", "做空信号"),
        "HOLD": ("⚪ 观望", "signal-hold", "持仓等待"),
    }
    label, cls, desc = signal_map.get(final_signal, signal_map["HOLD"])

    col1, col2, col3 = st.columns([1, 1, 2])

    with col1:
        st.markdown(
            f'<div class="signal-card {cls}"><h2>{label}</h2><p>{desc}</p></div>',
            unsafe_allow_html=True,
        )

    with col2:
        st.markdown("**综合置信度**")
        st.progress(min(confidence, 1.0))
        st.caption(f"{confidence:.1%}")

        if buy_signals:
            avg = sum(c for _, c in buy_signals) / len(buy_signals)
            st.markdown(f"🟢 **{len(buy_signals)}个买入** (平均 {avg:.0%})")
        if sell_signals:
            avg = sum(c for _, c in sell_signals) / len(sell_signals)
            st.markdown(f"🔴 **{len(sell_signals)}个卖出** (平均 {avg:.0%})")
        if not buy_signals and not sell_signals:
            st.markdown("⚪ 所有策略均为观望")

    with col3:
        show_strategy_details(result)


def show_strategy_details(result: dict):
    """按类别分组的策略详情"""
    details = result.get("details", {})
    if not details:
        return

    # 按类别分组
    grouped = {}
    for name, detail in details.items():
        cat = "其他"
        for category, members in STRATEGY_CATEGORIES.items():
            if name in members:
                cat = category
                break
        grouped.setdefault(cat, []).append((name, detail))

    for category, items in grouped.items():
        with st.expander(f"📂 {category} ({len(items)}个策略)", expanded=False):
            for name, detail in items:
                signal = detail.get("signal", "HOLD")
                reason = detail.get("reason", "")
                conf = detail.get("confidence", 0)
                icon = {"BUY": "🟢", "SELL": "🔴", "HOLD": "⚪"}.get(signal, "⚪")
                tag_cls = {
                    "BUY": "tag-buy",
                    "SELL": "tag-sell",
                    "HOLD": "tag-hold",
                }.get(signal, "tag-hold")

                st.markdown(
                    f"{icon} **{STRATEGY_NAMES.get(name, name)}** "
                    f'<span class="strategy-tag {tag_cls}">{signal} {conf:.0%}</span> '
                    f'<span style="color:#666;font-size:0.85rem">{reason}</span>',
                    unsafe_allow_html=True,
                )


def show_backtest_single(
    backtest_result: dict, stock_name: str, symbol: str, market: str
):
    """单策略回测结果展示"""
    if "error" in backtest_result:
        st.error(f"回测失败: {backtest_result.get('error', '未知错误')}")
        return

    col1, col2, col3, col4 = st.columns(4)
    with col1:
        st.metric("总收益率", backtest_result.get("total_return_pct", "N/A"))
    with col2:
        st.metric("最大回撤", backtest_result.get("max_drawdown_pct", "N/A"))
    with col3:
        st.metric("交易次数", str(backtest_result.get("total_trades", 0)))
    with col4:
        st.metric("胜率", backtest_result.get("win_rate", "N/A"))

    # 资金曲线 + 回撤
    equity_curve = backtest_result.get("equity_curve", [])
    trades = backtest_result.get("trades", [])
    initial_cash = backtest_result.get("initial_cash", 100000)

    tab_eq, tab_trades, tab_pie = st.tabs(["📈 资金曲线", "📋 交易记录", "🎯 胜负分布"])

    with tab_eq:
        if equity_curve:
            fig = chart_equity(equity_curve, trades, initial_cash, stock_name, symbol)
            st.plotly_chart(fig, use_container_width=True)

    with tab_trades:
        if trades:
            df_trades = pd.DataFrame(trades)
            if "date" in df_trades.columns:
                df_trades["date"] = pd.to_datetime(df_trades["date"]).dt.strftime(
                    "%Y-%m-%d"
                )
            display_cols = [
                c
                for c in ["type", "date", "price", "shares", "pnl"]
                if c in df_trades.columns
            ]
            df_show = df_trades[display_cols].copy()
            col_map = {
                "type": "类型",
                "date": "日期",
                "price": "价格",
                "shares": "数量",
                "pnl": "盈亏",
            }
            df_show.columns = [col_map.get(c, c) for c in display_cols]
            st.dataframe(df_show, use_container_width=True, hide_index=True)
        else:
            st.info("无交易记录")

    with tab_pie:
        if trades:
            fig = chart_win_loss_pie(trades)
            if fig:
                st.plotly_chart(fig, use_container_width=True)
        else:
            st.info("无交易记录")


def show_backtest_multiple(comparison_result: dict, market: str):
    """多策略对比回测"""
    if "error" in comparison_result:
        st.error(f"回测对比失败: {comparison_result.get('error', '未知错误')}")
        return

    best = comparison_result.get("best_strategy", {})
    st.markdown(f"### 🏆 最佳策略: **{best.get('name', 'N/A')}**")

    col1, col2, col3, col4 = st.columns(4)
    with col1:
        st.metric("总收益率", best.get("total_return_pct", "N/A"))
    with col2:
        st.metric("最大回撤", best.get("max_drawdown_pct", "N/A"))
    with col3:
        st.metric("胜率", best.get("win_rate", "N/A"))
    with col4:
        st.metric("综合得分", f"{best.get('score', 0):.2f}")

    st.markdown("---")

    # 对比表格
    comparison_data = comparison_result.get("comparison", [])
    if comparison_data:
        df_cmp = pd.DataFrame(comparison_data)
        display_columns = [
            "strategy_name",
            "category",
            "risk_level",
            "total_return_pct",
            "max_drawdown_pct",
            "win_rate",
            "total_trades",
        ]
        available = [c for c in display_columns if c in df_cmp.columns]
        df_show = df_cmp[available].copy()
        col_map = {
            "strategy_name": "策略名称",
            "category": "分类",
            "risk_level": "风险等级",
            "total_return_pct": "总收益率",
            "max_drawdown_pct": "最大回撤",
            "win_rate": "胜率",
            "total_trades": "交易次数",
        }
        df_show.columns = [col_map.get(c, c) for c in available]

        def highlight_best(row):
            if row.iloc[0] == best.get("name"):
                return ["background-color: rgba(0,200,83,0.12)"] * len(row)
            return [""] * len(row)

        st.dataframe(
            df_show.style.apply(highlight_best, axis=1),
            use_container_width=True,
            hide_index=True,
        )

    # 排名
    ranking = comparison_result.get("ranking", [])
    if ranking:
        st.subheader("🏆 策略排名（按综合得分）")
        for i, item in enumerate(ranking[:5], 1):
            medal = {1: "🥇", 2: "🥈", 3: "🥉"}.get(i, f"{i}.")
            st.markdown(
                f"{medal} **{item['strategy_name']}** — "
                f"收益: {item['total_return_pct']} | 回撤: {item['max_drawdown_pct']} | "
                f"胜率: {item['win_rate']} | 得分: {item['score']:.2f}"
            )


# ─── 初始化 ─────────────────────────────────────────────────────────────────


@st.cache_resource
def get_analyzer():
    return StockAnalyzer()


analyzer = get_analyzer()


# ─── 侧边栏 ─────────────────────────────────────────────────────────────────


def sidebar():
    st.sidebar.title("📊 股票分析系统")
    st.sidebar.markdown("---")

    current_symbol = st.session_state.get("selected_symbol", "000001")
    current_market = st.session_state.get("selected_market", "A")
    if current_market not in ["A", "US", "ETF"]:
        current_market = "A"

    # ── 股票代码输入
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

    # ── 最近查询历史（带市场标签）
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

    # ── 数据管理
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

    # ── 策略配置（按类别分组）
    st.sidebar.subheader("🎯 策略配置")

    # 初始化 select_all 历史状态
    if "prev_select_all" not in st.session_state:
        st.session_state.prev_select_all = False

    select_all = st.sidebar.checkbox(
        "✅ 全选所有策略", value=False, key="select_all_cb"
    )

    # 检测全选状态变化，同步各策略复选框
    if select_all != st.session_state.prev_select_all:
        for s in ALL_STRATEGIES:
            st.session_state[f"strat_{s}"] = select_all
        st.session_state.prev_select_all = select_all

    # 分类展示策略
    default_strategies = ["ma_cross", "macd", "rsi", "multi_factor"]
    selected_strategies = []
    for cat, members in STRATEGY_CATEGORIES.items():
        with st.sidebar.expander(
            f"{cat} ({len(members)})", expanded=(cat == "趋势跟踪")
        ):
            for s in members:
                checked = st.checkbox(
                    STRATEGY_NAMES[s],
                    value=(s in default_strategies),
                    key=f"strat_{s}",
                )
                if checked:
                    selected_strategies.append(s)

    if not selected_strategies:
        selected_strategies = ["ma_cross", "macd", "rsi", "multi_factor"]

    st.sidebar.markdown("---")

    # ── 回测配置
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


# ─── 主页面 ─────────────────────────────────────────────────────────────────


def main():
    # 注入 CSS
    st.markdown(CUSTOM_CSS, unsafe_allow_html=True)

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

    # 获取股票名称
    stock_name = get_stock_name(symbol, market)

    # 页面标题
    if stock_name != symbol:
        st.title(f"📈 {stock_name} ({symbol})")
    else:
        st.title(f"📈 股票分析 — {symbol}")

    # ── 数据获取
    if fetch_data:
        with st.spinner("正在获取数据..."):
            if is_etf:
                df = analyzer.ak_fetcher.fetch_etf_data(symbol)
                if not df.empty:
                    db.save_daily_data(symbol, df)
            else:
                df = analyzer.fetch_and_store(symbol, market, force_update=True)
        st.success(f"✅ {symbol} ({stock_name}) 数据更新完成！")

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

    add_to_history(symbol, stock_name, market)

    # ── 数据概览卡片
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

    # 数据新鲜度
    st.markdown(data_freshness(df), unsafe_allow_html=True)

    st.markdown("---")

    # ── 计算指标 & 策略分析
    df_with_indicators = TechnicalIndicators.calculate_all(df)

    with st.spinner("正在进行技术分析..."):
        result = analyzer.strategy_engine.analyze(df_with_indicators, strategies)

    # ── 交易信号
    st.subheader("🎯 交易信号")
    show_signal_card(result, market)

    st.markdown("---")

    # ── 图表
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
        # 数据表格（条件格式化）
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

        # CSV 下载
        csv = df_display.to_csv(index=False).encode("utf-8-sig")
        st.download_button(
            label="📥 下载数据 (CSV)",
            data=csv,
            file_name=f"{symbol}_{datetime.now().strftime('%Y%m%d')}.csv",
            mime="text/csv",
        )

    st.markdown("---")

    # ── 回测
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


if __name__ == "__main__":
    main()
