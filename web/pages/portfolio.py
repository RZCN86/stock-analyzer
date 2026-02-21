import streamlit as st
import pandas as pd
import plotly.graph_objects as go
import plotly.express as px
from datetime import datetime

from portfolio.advisor import PortfolioAdvisor
from web.constants import MARKET_LABELS
from web.web_utils import currency, market_badge_html
from web.charts import PLOTLY_LAYOUT
from utils.email_alert import is_email_configured, check_and_send_alerts
from utils import supabase_store


# @st.cache_resource
def _get_advisor_instance():
    return PortfolioAdvisor()


def page_portfolio():
    advisor = _get_advisor_instance()
    advisor.reload()

    st.sidebar.subheader("💼 持仓管理")

    with st.sidebar.expander("➕ 添加持仓", expanded=False):
        new_symbol = st.text_input("股票代码", key="pf_new_symbol")
        new_market = st.selectbox("市场", ["A", "US", "ETF"], key="pf_new_market")
        new_shares = st.number_input(
            "持仓数量", min_value=1, value=100, key="pf_new_shares"
        )
        new_cost = st.number_input(
            "买入均价", value=10.0, format="%.2f", key="pf_new_cost"
        )
        new_date = st.date_input("买入日期", key="pf_new_date")
        if st.button("确认添加", key="pf_add_btn", use_container_width=True):
            if new_symbol.strip():
                advisor.add_holding(
                    new_symbol.strip(),
                    new_market,
                    int(new_shares),
                    float(new_cost),
                    new_date.strftime("%Y-%m-%d"),
                )
                supabase_store.add_trade_record(
                    new_symbol.strip(),
                    new_market,
                    "BUY",
                    int(new_shares),
                    float(new_cost),
                    new_date.strftime("%Y-%m-%d"),
                )
                st.sidebar.success(f"✅ 已添加 {new_symbol.strip()}")
                st.rerun()

    if advisor.holdings:
        with st.sidebar.expander("🗑️ 删除持仓", expanded=False):
            for i, h in enumerate(advisor.holdings):
                label = f"{h['symbol']} ({MARKET_LABELS.get(h.get('market', 'A'), h.get('market', 'A'))})"
                if st.button(
                    f"删除 {label}",
                    key=f"pf_del_{h['symbol']}_{h.get('market', 'A')}_{i}",
                ):
                    advisor.remove_holding(h["symbol"], h.get("market", "A"))
                    st.rerun()

    st.sidebar.markdown("---")
    st.sidebar.subheader("⚙️ 风控设置")
    risk = advisor.risk_config
    stop_loss_pct = st.sidebar.slider(
        "止损线 (%)",
        1,
        30,
        int(risk.get("stop_loss", 0.08) * 100),
        1,
        key="pf_sl",
    )
    take_profit_pct = st.sidebar.slider(
        "止盈线 (%)",
        5,
        50,
        int(risk.get("take_profit", 0.20) * 100),
        1,
        key="pf_tp",
    )
    stop_loss = stop_loss_pct / 100.0
    take_profit = take_profit_pct / 100.0

    email_configured = is_email_configured()
    if email_configured:
        st.sidebar.markdown("---")
        st.sidebar.subheader("📧 邮件提醒")
        enable_email = st.sidebar.checkbox(
            "启用止盈止损邮件提醒", value=False, key="pf_email_on"
        )
        alert_email = ""
        if enable_email:
            alert_email = st.sidebar.text_input(
                "接收邮箱",
                key="pf_alert_email",
                placeholder="your@email.com",
            )
    else:
        enable_email = False
        alert_email = ""

    st.title("💼 持仓交易建议")

    if not advisor.holdings:
        st.info("📭 暂无持仓数据，请在左侧添加持仓或编辑 config/portfolio.yaml")
        return

    st.markdown(
        f"持仓数量: **{len(advisor.holdings)}** 只 | 分析时间: **{datetime.now().strftime('%Y-%m-%d %H:%M')}**"
    )

    advisor._config.setdefault("risk", {})
    advisor._config["risk"]["stop_loss"] = stop_loss
    advisor._config["risk"]["take_profit"] = take_profit

    with st.spinner("正在分析所有持仓，请稍候..."):
        analysis = advisor.analyze_all()

    summary = analysis.get("portfolio_summary", {})

    c1, c2, c3, c4 = st.columns(4)
    total_mv = summary.get("total_market_value", 0)
    total_pnl = summary.get("total_pnl", 0)
    total_pnl_pct = summary.get("total_pnl_pct", 0)
    pnl_delta = f"{total_pnl_pct:+.2f}%"

    with c1:
        st.metric("总市值", f"¥{total_mv:,.0f}")
    with c2:
        st.metric("总盈亏", f"¥{total_pnl:,.0f}", delta=pnl_delta)
    with c3:
        st.metric("买入信号", f"{summary.get('buy_signals', 0)} 只", delta="看多")
    with c4:
        st.metric(
            "卖出信号",
            f"{summary.get('sell_signals', 0)} 只",
            delta="看空",
            delta_color="inverse",
        )

    warnings = summary.get("position_warnings", [])
    if warnings:
        for w in warnings:
            st.markdown(f'<div class="risk-warn">⚠️ {w}</div>', unsafe_allow_html=True)

    if enable_email and alert_email:
        triggered = check_and_send_alerts(analysis.get("results", []), alert_email)
        if triggered:
            names = ", ".join(a["name"] for a in triggered)
            st.success(f"📧 已发送预警邮件至 {alert_email}（触发: {names}）")

    with st.expander("📊 组合相关性热力图 (点击展开)", expanded=False):
        try:
            corr_df = advisor.get_portfolio_correlation()
        except AttributeError:
            st.error("组件加载中，请刷新页面...")
            corr_df = pd.DataFrame()

        if not corr_df.empty:
            fig_corr = px.imshow(
                corr_df,
                text_auto=".2f",
                aspect="auto",
                color_continuous_scale="RdBu_r",
                zmin=-1,
                zmax=1,
                title="持仓标的相关性矩阵 (近90日)",
            )
            fig_corr.update_layout(
                xaxis_title="",
                yaxis_title="",
                height=600,
            )
            fig_corr.update_traces(
                hovertemplate="<b>%{x}</b> vs <b>%{y}</b><br>相关系数: %{z:.2f}<extra></extra>"
            )
            st.plotly_chart(fig_corr, use_container_width=True)
            st.caption(
                "💡 说明: 相关系数越接近 1 (红色)，表示涨跌越同步；接近 -1 (蓝色) 表示负相关；"
                "接近 0 表示无相关性。组合中若存在大量高度相关的标的，说明风险分散不足。"
            )
        else:
            st.info("数据不足，无法计算相关性矩阵")

    st.markdown("---")

    signal_order = {"BUY": 0, "SELL": 1, "HOLD": 2, "ERROR": 3}
    results = sorted(
        analysis.get("results", []),
        key=lambda r: (
            signal_order.get(r.get("final_signal", "HOLD"), 9),
            -r.get("confidence", 0),
        ),
    )

    for r in results:
        if "error" in r:
            st.warning(f"⚠️ {r.get('name', r['symbol'])}({r['symbol']}): {r['error']}")
            continue

        signal = r.get("final_signal", "HOLD")
        confidence = r.get("confidence", 0)
        advice = r.get("advice", {})
        sym = currency(r.get("market", "A"))

        css_class = {"BUY": "advice-buy", "SELL": "advice-sell"}.get(
            signal, "advice-hold"
        )
        signal_emoji = {"BUY": "🟢", "SELL": "🔴"}.get(signal, "⚪")

        pnl_pct = r.get("pnl_pct", 0)
        pnl_class = "pnl-pos" if pnl_pct >= 0 else "pnl-neg"
        pnl_val = r.get("pnl", 0)

        badge = market_badge_html(r.get("market", "A"))

        st.markdown(
            f'<div class="advice-card {css_class}">'
            f'<b style="font-size:1.1rem">{signal_emoji} {r.get("name", r["symbol"])}</b> '
            f"<code>{r['symbol']}</code> {badge}"
            f" &nbsp; | &nbsp; 现价: <b>{sym}{r.get('current_price', 0):.2f}</b>"
            f" &nbsp; | &nbsp; 成本: {sym}{r.get('cost_price', 0):.2f}"
            f' &nbsp; | &nbsp; 盈亏: <span class="{pnl_class}">{sym}{pnl_val:+,.0f} ({pnl_pct:+.2f}%)</span>'
            f"</div>",
            unsafe_allow_html=True,
        )

        col_adv, col_detail = st.columns([1, 1])
        with col_adv:
            st.markdown(
                f"**操作建议: {advice.get('action', '持有')}** (置信度: {confidence:.0%})"
            )
            st.markdown(f"📋 {advice.get('advice', '')}")
            st.markdown(f"📊 建议仓位: **{advice.get('suggested_position', '维持')}**")

            sl_price = advice.get("stop_loss_price")
            tp_price = advice.get("take_profit_price")
            calc = advice.get("price_calc")
            if sl_price and tp_price:
                st.markdown(
                    f"🎯 止盈价: **{sym}{tp_price:.2f}** &nbsp;|&nbsp; 🛡️ 止损价: **{sym}{sl_price:.2f}**"
                )
                if calc and "sl_basis" in calc:
                    sl_basis = calc.get("sl_basis", "")
                    sl_level = calc.get("sl_level", 0)
                    sl_atr_buf = calc.get("sl_atr_buffer", 0)
                    tp_basis = calc.get("tp_basis", "")
                    tp_level = calc.get("tp_level", 0)
                    tp_atr_ext = calc.get("tp_atr_extension", 0)
                    atr_val = calc.get("atr")
                    rsi_val = calc.get("rsi")
                    rsi_note = calc.get("rsi_note", "")
                    signal_eff = calc.get("signal_effect", "")
                    indicators = calc.get("indicators_used", [])

                    sl_formula = f"{sl_basis} {sym}{sl_level:.2f}"
                    if sl_atr_buf > 0:
                        sl_formula += f" − ATR缓冲 {sym}{sl_atr_buf:.2f}"
                    sl_formula += f" = **{sym}{sl_price:.2f}**"

                    tp_formula = f"{tp_basis} {sym}{tp_level:.2f}"
                    if tp_atr_ext > 0:
                        tp_formula += f" + ATR延伸 {sym}{tp_atr_ext:.2f}"
                    tp_formula += f" = **{sym}{tp_price:.2f}**"

                    detail_lines = [
                        f"🛡️ 止损: {sl_formula}",
                        f"🎯 止盈: {tp_formula}",
                    ]
                    if atr_val is not None:
                        detail_lines.append(f"📐 ATR(14): {sym}{atr_val:.2f}")
                    if rsi_val is not None:
                        detail_lines.append(f"📊 RSI(14): {rsi_val:.1f}")
                    if rsi_note:
                        detail_lines.append(f"⚡ {rsi_note}")
                    if signal_eff:
                        detail_lines.append(f"📈 信号影响: {signal_eff}")
                    if indicators:
                        detail_lines.append(f"🔧 综合指标: {', '.join(indicators)}")

                    with st.expander("📐 止盈止损计算逻辑", expanded=False):
                        for line in detail_lines:
                            st.markdown(line)
                elif calc:
                    base_label = calc.get("base_label", "")
                    base_price = calc.get("base_price", 0)
                    sl_r = calc.get("sl_rate", 0)
                    tp_r = calc.get("tp_rate", 0)
                    st.caption(
                        f"计算基准: {base_label} {sym}{base_price:.2f} &nbsp;| &nbsp;"
                        f"止盈 = {base_label} × (1 + {tp_r:.0%}) = {sym}{tp_price:.2f} &nbsp;| &nbsp;"
                        f"止损 = {base_label} × (1 − {sl_r:.0%}) = {sym}{sl_price:.2f}"
                    )

            for w in advice.get("risk_warnings", []):
                st.markdown(f'<div class="risk-warn">{w}</div>', unsafe_allow_html=True)

        with col_detail:
            details = r.get("strategy_details", [])
            if details:
                df_strat = pd.DataFrame(details)
                df_strat = df_strat[["name", "signal", "confidence", "reason"]]
                df_strat.columns = ["策略", "信号", "置信度", "依据"]

                def _color_signal(val):
                    if val == "BUY":
                        return "color: #2e7d32; font-weight:700"
                    if val == "SELL":
                        return "color: #c62828; font-weight:700"
                    return "color: #757575"

                styled = df_strat.style.map(_color_signal, subset=["信号"])
                st.dataframe(
                    styled, use_container_width=True, hide_index=True, height=200
                )

        # ─── 扩展工具箱 (仓位 & 网格) ───
        calc_info = advice.get("price_calc", {})
        atr_val = calc_info.get("atr")

        with st.expander("🧮 量化工具箱 (仓位/网格)", expanded=False):
            t_col1, t_col2 = st.columns(2)

            # 1. 仓位管理
            with t_col1:
                st.markdown("##### ⚖️ ATR 波动率仓位建议")
                if atr_val:
                    # 默认总资金 10万，单笔风险 1%
                    total_cap = st.number_input(
                        "账户总资金", value=100000, step=10000, key=f"cap_{r['symbol']}"
                    )
                    risk_pct = st.number_input(
                        "单笔风险 (%)", value=1.0, step=0.1, key=f"risk_{r['symbol']}"
                    )

                    pos_size = advisor.calculate_position_size(
                        atr=float(atr_val),
                        current_price=r.get("current_price", 0),
                        total_capital=total_cap,
                        risk_per_trade=risk_pct / 100,
                    )

                    if pos_size:
                        rec_shares = pos_size.get("suggested_shares", 0)
                        rec_val = pos_size.get("suggested_value", 0)
                        st.info(
                            f"建议买入: **{rec_shares} 股**\n\n"
                            f"对应市值: ¥{rec_val:,.0f} ({pos_size.get('position_pct', 0):.1%})\n\n"
                            f"止损金额: ¥{pos_size.get('max_risk_amount', 0):.0f}"
                        )
                else:
                    st.warning("缺少ATR数据，无法计算建议仓位")

            # 2. 网格策略 (仅ETF或用户启用)
            with t_col2:
                st.markdown("##### 🥅 网格策略生成器")
                if atr_val:
                    grid_mid = st.number_input(
                        "网格中枢价",
                        value=r.get("current_price", 0.0),
                        format="%.3f",
                        key=f"grid_mid_{r['symbol']}",
                    )
                    grid_num = st.number_input(
                        "网格数量 (单边)",
                        value=5,
                        min_value=1,
                        max_value=20,
                        key=f"grid_num_{r['symbol']}",
                    )

                    grid_table = advisor.calculate_grid_strategy(
                        current_price=grid_mid,
                        volatility_atr=float(atr_val),
                        grid_count=grid_num,
                    )

                    if grid_table:
                        df_grid = pd.DataFrame(grid_table)
                        st.dataframe(
                            df_grid[["action", "price", "diff_pct"]],
                            column_config={
                                "action": "操作",
                                "price": st.column_config.NumberColumn(
                                    "挂单价", format="%.3f"
                                ),
                                "diff_pct": st.column_config.NumberColumn(
                                    "偏离%", format="%.2f%%"
                                ),
                            },
                            hide_index=True,
                            use_container_width=True,
                        )
                else:
                    st.warning("缺少波动率数据，无法生成网格")

        st.markdown("---")

    if results:
        pie_data = {
            "买入": summary.get("buy_signals", 0),
            "卖出": summary.get("sell_signals", 0),
            "持有": summary.get("hold_signals", 0),
        }
        pie_data = {k: v for k, v in pie_data.items() if v > 0}
        if pie_data:
            fig = go.Figure(
                data=[
                    go.Pie(
                        labels=list(pie_data.keys()),
                        values=list(pie_data.values()),
                        marker=dict(colors=["#4caf50", "#f44336", "#9e9e9e"]),
                        hole=0.4,
                    )
                ]
            )
            fig.update_layout(
                title="持仓信号分布",
                **{
                    k: v
                    for k, v in PLOTLY_LAYOUT.items()
                    if k != "xaxis_rangeslider_visible"
                },
            )
            st.plotly_chart(fig, use_container_width=True)

    if supabase_store.is_available():
        with st.expander("📋 交易历史记录", expanded=False):
            history = supabase_store.load_trade_history()
            if history:
                df_hist = pd.DataFrame(history)
                display_cols = [
                    c
                    for c in [
                        "trade_date",
                        "symbol",
                        "market",
                        "action",
                        "shares",
                        "price",
                        "notes",
                    ]
                    if c in df_hist.columns
                ]
                df_show = df_hist[display_cols].copy()
                col_map = {
                    "trade_date": "日期",
                    "symbol": "代码",
                    "market": "市场",
                    "action": "操作",
                    "shares": "数量",
                    "price": "价格",
                    "notes": "备注",
                }
                df_show.columns = [col_map.get(c, c) for c in display_cols]

                def _color_action(val):
                    if val == "BUY":
                        return "color: #2e7d32; font-weight:700"
                    if val == "SELL":
                        return "color: #c62828; font-weight:700"
                    return ""

                styled = df_show.style.map(_color_action, subset=["操作"])
                st.dataframe(styled, use_container_width=True, hide_index=True)
            else:
                st.info("暂无交易记录")

    st.markdown(
        '<div class="disclaimer">⚠️ <b>免责声明</b>：本系统仅供学习研究使用，'
        "不构成投资建议。股市有风险，投资需谨慎。</div>",
        unsafe_allow_html=True,
    )
