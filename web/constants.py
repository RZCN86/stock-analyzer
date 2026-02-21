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
