import streamlit as st
import sys
import os

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

st.set_page_config(
    page_title="股票分析系统",
    page_icon="📈",
    layout="wide",
    initial_sidebar_state="expanded",
)

from web.styles import CUSTOM_CSS
from web.pages.portfolio import page_portfolio
from web.pages.analysis import page_stock_analysis
from web.pages.watchlist import page_watchlist


def main():
    st.markdown(CUSTOM_CSS, unsafe_allow_html=True)

    page = st.sidebar.radio(
        "功能导航",
        ["📈 股票分析", "💼 持仓仪表盘", "👀 自选股"],
        key="nav_page",
    )
    st.sidebar.markdown("---")

    if page == "📈 股票分析":
        page_stock_analysis()
    elif page == "💼 持仓仪表盘":
        page_portfolio()
    else:
        page_watchlist()


if __name__ == "__main__":
    main()
