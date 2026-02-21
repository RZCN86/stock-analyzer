import pandas as pd
from datetime import datetime

from web.constants import MARKET_LABELS


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
