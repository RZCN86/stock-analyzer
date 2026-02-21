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

/* 持仓仪表盘 */
.advice-card {
    padding: 1rem 1.2rem; border-radius: 0.6rem; margin-bottom: 0.8rem;
    box-shadow: 0 1px 6px rgba(0,0,0,0.06);
}
.advice-buy  { background: linear-gradient(135deg, #e8f5e9 0%, #c8e6c9 100%); border-left: 4px solid #2e7d32; }
.advice-sell { background: linear-gradient(135deg, #ffebee 0%, #ffcdd2 100%); border-left: 4px solid #c62828; }
.advice-hold { background: linear-gradient(135deg, #f5f5f5 0%, #e8eaf6 100%); border-left: 4px solid #5c6bc0; }
.pnl-pos { color: #c62828; font-weight: 700; }
.pnl-neg { color: #2e7d32; font-weight: 700; }
.risk-warn { background: #fff8e1; border-left: 3px solid #ff8f00; padding: 0.4rem 0.8rem; border-radius: 0.3rem; font-size: 0.82rem; margin: 0.3rem 0; }
</style>
"""
