import streamlit as st
import pandas as pd

from web.constants import STRATEGY_NAMES, STRATEGY_CATEGORIES
from web.charts import (
    chart_equity,
    chart_win_loss_pie,
    chart_trade_pnl,
    chart_strategies_overlay,
)


def show_signal_card(result: dict, market: str):
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
    details = result.get("details", {})
    if not details:
        return

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

    equity_curve = backtest_result.get("equity_curve", [])
    trades = backtest_result.get("trades", [])
    initial_cash = backtest_result.get("initial_cash", 100000)
    prices = backtest_result.get("prices", [])
    dates = backtest_result.get("dates", [])

    tab_eq, tab_pnl, tab_trades, tab_pie = st.tabs(
        ["📈 资金曲线", "📊 逐笔盈亏", "📋 交易记录", "🎯 胜负分布"]
    )

    with tab_eq:
        if equity_curve:
            fig = chart_equity(
                equity_curve,
                trades,
                initial_cash,
                stock_name,
                symbol,
                prices=prices,
                dates=dates,
            )
            st.plotly_chart(fig, use_container_width=True)

    with tab_pnl:
        if trades:
            fig = chart_trade_pnl(trades)
            if fig:
                st.plotly_chart(fig, use_container_width=True)
            else:
                st.info("无卖出交易记录")
        else:
            st.info("无交易记录")

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

    comparison_data = comparison_result.get("comparison", [])

    tab_overlay, tab_table, tab_rank = st.tabs(
        ["📈 资金曲线对比", "📊 策略数据", "🏆 策略排名"]
    )

    with tab_overlay:
        if comparison_data:
            fig = chart_strategies_overlay(comparison_data)
            if fig:
                st.plotly_chart(fig, use_container_width=True)
            else:
                st.info("无资金曲线数据")

    with tab_table:
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

    with tab_rank:
        ranking = comparison_result.get("ranking", [])
        if ranking:
            for i, item in enumerate(ranking[:5], 1):
                medal = {1: "🥇", 2: "🥈", 3: "🥉"}.get(i, f"{i}.")
                st.markdown(
                    f"{medal} **{item['strategy_name']}** — "
                    f"收益: {item['total_return_pct']} | 回撤: {item['max_drawdown_pct']} | "
                    f"胜率: {item['win_rate']} | 得分: {item['score']:.2f}"
                )
