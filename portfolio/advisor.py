import os
import yaml
from datetime import datetime
from typing import List, Dict, Any, Optional

from main import StockAnalyzer
from utils.stock_name import get_stock_name
from utils.helpers import logger


class PortfolioAdvisor:
    SIGNAL_CN = {"BUY": "买入", "SELL": "卖出", "HOLD": "持有", "ERROR": "异常"}
    ACTION_TEMPLATES = {
        "BUY": {
            "high": "强烈建议加仓，多个策略共振看多，可考虑加仓至目标仓位",
            "medium": "建议适量加仓，技术面偏多但信号尚未完全确认",
            "low": "可小幅试探性加仓，信号较弱需密切关注",
        },
        "SELL": {
            "high": "强烈建议减仓，多个策略共振看空，建议分批减仓控制风险",
            "medium": "建议适量减仓，技术面转弱但趋势尚未完全反转",
            "low": "可适当降低仓位，保持观望为主",
        },
        "HOLD": {
            "high": "继续持有，当前趋势稳定无明显转向信号",
            "medium": "维持现有仓位，密切关注后续走势变化",
            "low": "暂时持有，市场方向不明确，做好双向应对准备",
        },
    }

    def __init__(self, config_path: Optional[str] = None):
        self.base_dir = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
        self.config_path = config_path or os.path.join(
            self.base_dir, "config", "portfolio.yaml"
        )
        self.analyzer = StockAnalyzer()
        self._config: Dict[str, Any] = {}
        self._load_config()

    def _load_config(self):
        try:
            with open(self.config_path, "r", encoding="utf-8") as f:
                self._config = yaml.safe_load(f) or {}
        except FileNotFoundError:
            logger.warning(f"持仓配置文件不存在: {self.config_path}")
            self._config = {"holdings": [], "risk": {}, "analysis": {}}
        except yaml.YAMLError as e:
            logger.error(f"持仓配置解析失败: {e}")
            self._config = {"holdings": [], "risk": {}, "analysis": {}}

    def reload(self):
        self._load_config()

    @property
    def holdings(self) -> List[Dict[str, Any]]:
        return self._config.get("holdings", [])

    @property
    def risk_config(self) -> Dict[str, float]:
        defaults = {
            "stop_loss": 0.08,
            "take_profit": 0.20,
            "position_warning": 0.30,
        }
        risk = self._config.get("risk", {})
        defaults.update(risk or {})
        return defaults

    @property
    def default_strategies(self) -> List[str]:
        analysis = self._config.get("analysis", {})
        return analysis.get(
            "default_strategies", ["ma_cross", "macd", "rsi", "multi_factor"]
        )

    def save_config(self, config: Dict[str, Any]):
        self._config = config
        os.makedirs(os.path.dirname(self.config_path), exist_ok=True)
        with open(self.config_path, "w", encoding="utf-8") as f:
            yaml.dump(
                config, f, allow_unicode=True, default_flow_style=False, sort_keys=False
            )

    def add_holding(
        self,
        symbol: str,
        market: str,
        shares: int,
        cost_price: float,
        buy_date: str = "",
    ):
        if not buy_date:
            buy_date = datetime.now().strftime("%Y-%m-%d")
        new_holding = {
            "symbol": symbol,
            "market": market.upper(),
            "shares": shares,
            "cost_price": cost_price,
            "buy_date": buy_date,
        }
        holdings = list(self.holdings)
        holdings.append(new_holding)
        self._config["holdings"] = holdings
        self.save_config(self._config)

    def remove_holding(self, symbol: str, market: str):
        holdings = [
            h
            for h in self.holdings
            if not (
                h["symbol"] == symbol and h.get("market", "A").upper() == market.upper()
            )
        ]
        self._config["holdings"] = holdings
        self.save_config(self._config)

    def _confidence_level(self, confidence: float) -> str:
        if confidence >= 0.65:
            return "high"
        if confidence >= 0.40:
            return "medium"
        return "low"

    def _generate_advice(
        self,
        signal: str,
        confidence: float,
        pnl_pct: float,
        risk_cfg: Dict[str, float],
    ) -> Dict[str, Any]:
        level = self._confidence_level(confidence)
        base_advice = self.ACTION_TEMPLATES.get(signal, self.ACTION_TEMPLATES["HOLD"])
        advice_text = base_advice.get(level, base_advice["medium"])

        risk_warnings = []
        stop_loss = risk_cfg.get("stop_loss", 0.08)
        take_profit = risk_cfg.get("take_profit", 0.20)

        if pnl_pct <= -stop_loss:
            risk_warnings.append(
                f"⚠️ 已触发止损线（亏损 {abs(pnl_pct) * 100:.1f}% ≥ {stop_loss * 100:.0f}%），建议止损离场"
            )
            advice_text = "建议止损离场，亏损已超过预设止损线，控制风险优先"
        elif pnl_pct >= take_profit:
            risk_warnings.append(
                f"🎯 已达止盈目标（盈利 {pnl_pct * 100:.1f}% ≥ {take_profit * 100:.0f}%），可考虑分批止盈"
            )
            if signal != "BUY":
                advice_text = "建议分批止盈，锁定利润后保留底仓观察"
        elif pnl_pct <= -(stop_loss * 0.7):
            risk_warnings.append(
                f"⚡ 接近止损线（亏损 {abs(pnl_pct) * 100:.1f}%），请密切关注"
            )

        suggested_position = "维持"
        if signal == "BUY" and pnl_pct > -stop_loss:
            suggested_position = "加仓" if level == "high" else "小幅加仓"
        elif signal == "SELL" or pnl_pct <= -stop_loss:
            suggested_position = "减仓" if level != "high" else "大幅减仓"

        return {
            "action": self.SIGNAL_CN.get(signal, signal),
            "advice": advice_text,
            "confidence_level": level,
            "suggested_position": suggested_position,
            "risk_warnings": risk_warnings,
            "stop_loss_price": None,
            "take_profit_price": None,
        }

    def analyze_holding(
        self, holding: Dict[str, Any], strategies: Optional[List[str]] = None
    ) -> Dict[str, Any]:
        symbol = holding["symbol"]
        market = holding.get("market", "A").upper()
        shares = holding.get("shares", 0)
        cost_price = holding.get("cost_price", 0)
        buy_date = holding.get("buy_date", "")

        strategies = strategies or self.default_strategies
        stock_name = get_stock_name(symbol, market)

        try:
            self.analyzer.fetch_and_store(symbol, market)
        except Exception as e:
            logger.warning(f"更新 {symbol} 数据失败: {e}")

        try:
            result = self.analyzer.analyze(symbol, market, strategies)
        except Exception as e:
            logger.error(f"分析 {symbol} 失败: {e}")
            return {
                "symbol": symbol,
                "name": stock_name or symbol,
                "market": market,
                "error": str(e),
            }

        if "error" in result:
            return {
                "symbol": symbol,
                "name": stock_name or symbol,
                "market": market,
                "error": result["error"],
            }

        summary = result.get("data_summary", {})
        current_price = summary.get("close", 0)
        final_signal = result.get("final_signal", "HOLD")
        confidence = result.get("confidence", 0)

        market_value = current_price * shares if current_price > 0 else 0
        if cost_price != 0 and current_price > 0:
            pnl = (current_price - cost_price) * shares
            pnl_pct = (current_price - cost_price) / abs(cost_price)
        else:
            pnl = 0
            pnl_pct = 0

        risk_cfg = self.risk_config
        advice = self._generate_advice(final_signal, confidence, pnl_pct, risk_cfg)

        sl_rate = risk_cfg.get("stop_loss", 0.08)
        tp_rate = risk_cfg.get("take_profit", 0.20)

        if cost_price > 0:
            base_price = cost_price
            base_label = "成本价"
        elif current_price > 0:
            base_price = current_price
            base_label = "现价"
        else:
            base_price = 0
            base_label = ""

        if base_price > 0:
            advice["stop_loss_price"] = round(base_price * (1 - sl_rate), 2)
            advice["take_profit_price"] = round(base_price * (1 + tp_rate), 2)
            advice["price_calc"] = {
                "base_price": round(base_price, 2),
                "base_label": base_label,
                "sl_rate": sl_rate,
                "tp_rate": tp_rate,
            }

        strategy_details = []
        for s_name, s_detail in result.get("details", {}).items():
            info = self.analyzer.strategy_engine.get_strategy_info(s_name)
            strategy_details.append(
                {
                    "id": s_name,
                    "name": info.get("name", s_name),
                    "category": info.get("category", ""),
                    "signal": s_detail.get("signal", "HOLD"),
                    "confidence": s_detail.get("confidence", 0),
                    "reason": s_detail.get("reason", ""),
                }
            )

        return {
            "symbol": symbol,
            "name": stock_name or symbol,
            "market": market,
            "shares": shares,
            "cost_price": cost_price,
            "current_price": current_price,
            "market_value": round(market_value, 2),
            "pnl": round(pnl, 2),
            "pnl_pct": round(pnl_pct * 100, 2),
            "buy_date": buy_date,
            "final_signal": final_signal,
            "confidence": round(confidence, 4),
            "advice": advice,
            "strategy_details": strategy_details,
            "data_summary": summary,
        }

    def analyze_all(self, strategies: Optional[List[str]] = None) -> Dict[str, Any]:
        if not self.holdings:
            return {
                "holdings_count": 0,
                "results": [],
                "portfolio_summary": {},
                "analysis_time": datetime.now().strftime("%Y-%m-%d %H:%M:%S"),
            }

        results = []
        for holding in self.holdings:
            result = self.analyze_holding(holding, strategies)
            results.append(result)

        valid_results = [r for r in results if "error" not in r]

        total_market_value = sum(r.get("market_value", 0) for r in valid_results)
        total_cost = sum(
            r.get("cost_price", 0) * r.get("shares", 0) for r in valid_results
        )
        total_pnl = sum(r.get("pnl", 0) for r in valid_results)
        total_pnl_pct = (
            ((total_market_value - total_cost) / total_cost * 100)
            if total_cost > 0
            else 0
        )

        buy_count = sum(1 for r in valid_results if r.get("final_signal") == "BUY")
        sell_count = sum(1 for r in valid_results if r.get("final_signal") == "SELL")
        hold_count = sum(1 for r in valid_results if r.get("final_signal") == "HOLD")

        position_warnings = []
        warn_threshold = self.risk_config.get("position_warning", 0.30)
        if total_market_value > 0:
            for r in valid_results:
                weight = r.get("market_value", 0) / total_market_value
                if weight >= warn_threshold:
                    position_warnings.append(
                        f"{r['name']}({r['symbol']}) 占比 {weight * 100:.1f}%，超过预警线 {warn_threshold * 100:.0f}%"
                    )

        return {
            "holdings_count": len(self.holdings),
            "valid_count": len(valid_results),
            "results": results,
            "portfolio_summary": {
                "total_market_value": round(total_market_value, 2),
                "total_cost": round(total_cost, 2),
                "total_pnl": round(total_pnl, 2),
                "total_pnl_pct": round(total_pnl_pct, 2),
                "buy_signals": buy_count,
                "sell_signals": sell_count,
                "hold_signals": hold_count,
                "position_warnings": position_warnings,
            },
            "analysis_time": datetime.now().strftime("%Y-%m-%d %H:%M:%S"),
        }
