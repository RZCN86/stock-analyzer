import streamlit as st
import pandas as pd
from datetime import datetime

from utils import supabase_store
from utils.stock_name import get_stock_name, get_stock_info
from web.constants import MARKET_LABELS
from web.web_utils import currency
from database.db_manager import db


def page_watchlist():
    st.title("👀 自选股观察列表")

    if not supabase_store.is_available():
        st.warning(
            "自选股功能需要 Supabase 配置。请在 `.streamlit/secrets.toml` 中配置 `[supabase]` 后刷新。"
        )
        return

    with st.sidebar.expander("➕ 添加自选股", expanded=True):
        symbol = st.text_input("股票代码", key="wl_symbol")
        market = st.selectbox("市场", ["A", "US", "ETF"], key="wl_market")
        notes = st.text_input("备注 (可选)", key="wl_notes")
        if st.button("添加", key="wl_add_btn", use_container_width=True):
            if symbol.strip():
                ok = supabase_store.add_to_watchlist(symbol.strip(), market, notes)
                if ok:
                    st.sidebar.success(f"✅ 已添加 {symbol.strip()}")
                    st.rerun()
                else:
                    st.sidebar.error("添加失败")

    items = supabase_store.load_watchlist()

    if not items:
        st.info("📭 自选股列表为空，请在左侧添加关注的股票代码")
        return

    st.markdown(
        f"关注数量: **{len(items)}** 只 | 更新时间: **{datetime.now().strftime('%H:%M')}**"
    )

    watch_data = []
    for item in items:
        sym = item.get("symbol", "")
        mkt = item.get("market", "A")
        note = item.get("notes", "")

        name = get_stock_name(sym, mkt) or sym
        mkt_label = MARKET_LABELS.get(mkt, mkt)

        try:
            df = db.get_daily_data(sym)
            if not df.empty:
                latest = df.iloc[-1]
                curr_price = latest.get("close", 0)
                prev_price = (
                    df.iloc[-2].get("close", curr_price) if len(df) > 1 else curr_price
                )
                change = (
                    ((curr_price - prev_price) / prev_price * 100) if prev_price else 0
                )
                volume = latest.get("volume", 0)
            else:
                curr_price = 0
                change = 0
                volume = 0
        except Exception:
            curr_price = 0
            change = 0
            volume = 0

        watch_data.append(
            {
                "symbol": sym,
                "market": mkt,
                "name": name,
                "market_label": mkt_label,
                "price": curr_price,
                "change": change,
                "volume": volume,
                "notes": note,
            }
        )

    for i, row in enumerate(watch_data):
        with st.container():
            col_sym, col_price, col_change, col_note, col_del = st.columns(
                [2, 1.5, 1.5, 2, 0.5]
            )

            with col_sym:
                st.markdown(
                    f"**{row['name']}** `{row['symbol']}` "
                    f'<span style="background:#e3f2fd;padding:2px 6px;border-radius:4px;font-size:0.8rem">{row["market_label"]}</span>',
                    unsafe_allow_html=True,
                )

            with col_price:
                curr = currency(row["market"])
                st.markdown(f"**{curr}{row['price']:.2f}**")

            with col_change:
                color = "#c62828" if row["change"] < 0 else "#2e7d32"
                arrow = "↓" if row["change"] < 0 else "↑"
                st.markdown(
                    f'<span style="color:{color}">{arrow} {row["change"]:+.2f}%</span>',
                    unsafe_allow_html=True,
                )

            with col_note:
                if row["notes"]:
                    st.caption(f"📝 {row['notes']}")

            with col_del:
                if st.button("🗑️", key=f"wl_del_{row['symbol']}_{row['market']}_{i}"):
                    supabase_store.remove_from_watchlist(row["symbol"], row["market"])
                    st.rerun()

            st.divider()
