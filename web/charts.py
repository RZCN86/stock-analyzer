import pandas as pd
import plotly.graph_objects as go
from plotly.subplots import make_subplots

PLOTLY_LAYOUT = dict(
    template="plotly_white",
    hovermode="x unified",
    legend=dict(orientation="h", yanchor="bottom", y=1.02, xanchor="right", x=1),
    margin=dict(l=0, r=0, t=30, b=0),
    xaxis_rangeslider_visible=False,
)

UP_COLOR = "#ef5350"
DOWN_COLOR = "#26a69a"


def chart_candlestick(df: pd.DataFrame, symbol: str, stock_name: str) -> go.Figure:
    fig = make_subplots(
        rows=2,
        cols=1,
        shared_xaxes=True,
        vertical_spacing=0.03,
        row_heights=[0.75, 0.25],
    )

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
    prices: list | None = None,
    dates: list | None = None,
) -> go.Figure:
    eq = pd.Series(equity_curve, dtype=float)
    peak = eq.cummax()
    drawdown = (eq - peak) / peak * 100

    x_axis = (
        dates[: len(eq)] if dates and len(dates) >= len(eq) else list(range(len(eq)))
    )

    fig = make_subplots(
        rows=2,
        cols=1,
        shared_xaxes=True,
        vertical_spacing=0.05,
        row_heights=[0.7, 0.3],
    )

    fig.add_trace(
        go.Scatter(
            x=x_axis,
            y=eq,
            name="策略资金曲线",
            line=dict(width=1.8, color="#1976d2"),
            fill="tozeroy",
            fillcolor="rgba(25,118,210,0.06)",
        ),
        row=1,
        col=1,
    )

    if prices and len(prices) >= len(eq):
        scale = initial_cash / prices[0] if prices[0] else 1
        benchmark = [p * scale for p in prices[: len(eq)]]
        fig.add_trace(
            go.Scatter(
                x=x_axis,
                y=benchmark,
                name="买入持有基准",
                line=dict(width=1.2, color="#ff9800", dash="dash"),
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
            x=x_axis,
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
    if dates:
        fig.update_xaxes(type="category", nticks=12)
    return fig


def chart_win_loss_pie(trades: list) -> go.Figure:
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
                marker_colors=[DOWN_COLOR, UP_COLOR],
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


def chart_trade_pnl(trades: list) -> go.Figure | None:
    sells = [t for t in trades if t.get("type") == "SELL"]
    if not sells:
        return None

    pnl_values = [t.get("pnl", t.get("revenue", 0)) for t in sells]
    dates_list = []
    for t in sells:
        try:
            dates_list.append(pd.Timestamp(t["date"]).strftime("%Y-%m-%d"))
        except Exception:
            dates_list.append(str(t.get("date", "")))

    colors = [DOWN_COLOR if v > 0 else UP_COLOR for v in pnl_values]

    fig = go.Figure(
        data=[
            go.Bar(
                x=dates_list,
                y=pnl_values,
                marker_color=colors,
                text=[f"{v:+,.0f}" for v in pnl_values],
                textposition="outside",
            )
        ]
    )
    fig.add_hline(y=0, line_dash="dot", line_color="grey")
    fig.update_layout(
        **PLOTLY_LAYOUT,
        height=320,
        title_text="逐笔交易盈亏",
        yaxis_title="盈亏 (元)",
    )
    fig.update_xaxes(type="category", nticks=12)
    return fig


STRATEGY_COLORS = [
    "#1976d2",
    "#e53935",
    "#43a047",
    "#fb8c00",
    "#8e24aa",
    "#00acc1",
    "#d81b60",
    "#7cb342",
    "#6d4c41",
    "#546e7a",
]


def chart_strategies_overlay(comparison_data: list) -> go.Figure | None:
    valid = [c for c in comparison_data if c.get("equity_curve")]
    if not valid:
        return None

    fig = go.Figure()

    for i, item in enumerate(valid):
        eq = item["equity_curve"]
        name = item.get("strategy_name", f"策略{i + 1}")
        dates_list = item.get("dates", [])
        x_axis = dates_list[: len(eq)] if dates_list else list(range(len(eq)))
        color = STRATEGY_COLORS[i % len(STRATEGY_COLORS)]

        fig.add_trace(
            go.Scatter(
                x=x_axis,
                y=eq,
                name=name,
                line=dict(width=1.5, color=color),
            )
        )

    initial_cash = valid[0].get("initial_cash", 100000)
    prices = valid[0].get("prices", [])
    if prices:
        scale = initial_cash / prices[0] if prices[0] else 1
        benchmark = [p * scale for p in prices]
        dates_list = valid[0].get("dates", [])
        x_axis = (
            dates_list[: len(benchmark)] if dates_list else list(range(len(benchmark)))
        )
        fig.add_trace(
            go.Scatter(
                x=x_axis,
                y=benchmark,
                name="买入持有基准",
                line=dict(width=1.8, color="#9e9e9e", dash="dash"),
            )
        )

    fig.add_hline(
        y=initial_cash,
        line_dash="dot",
        line_color="#ef5350",
        annotation_text="初始资金",
    )

    fig.update_layout(
        **PLOTLY_LAYOUT,
        height=480,
        title_text="多策略资金曲线对比",
        yaxis_title="资金 (元)",
    )
    if valid[0].get("dates"):
        fig.update_xaxes(type="category", nticks=12)
    return fig
