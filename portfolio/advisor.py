import os
import yaml
import numpy as np
import pandas as pd
from datetime import datetime
from typing import List, Dict, Any, Optional

from main import StockAnalyzer
from database.db_manager import db
from analysis.indicators import TechnicalIndicators
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

    def _calculate_smart_levels(
        self,
        df: "pd.DataFrame",
        current_price: float,
        cost_price: float,
        signal: str,
        confidence: float,
    ) -> Dict[str, Any]:
        """基于技术指标计算智能止盈止损价位

        综合使用布林带、均线、ATR、近期高低点和RSI等技术指标，
        结合策略信号方向和置信度，给出有技术依据的止盈止损建议。
        """
        if df.empty or current_price <= 0:
            return {}

        latest = df.iloc[-1]
        lookback = min(20, len(df))
        recent = df.tail(lookback)

        # ── 提取技术指标 ──
        boll_lower = latest.get("boll_lower")
        boll_upper = latest.get("boll_upper")
        boll_mid = latest.get("boll_mid")
        ma20 = latest.get("ma20")
        ma60 = latest.get("ma60")
        atr = latest.get("atr")
        rsi = latest.get("rsi")

        # 近期高低点
        recent_low = recent["low"].min() if "low" in recent.columns else None
        recent_high = recent["high"].max() if "high" in recent.columns else None

        # 检查关键指标可用性
        has_boll = boll_lower is not None and not np.isnan(boll_lower)
        has_ma20 = ma20 is not None and not np.isnan(ma20)
        has_ma60 = ma60 is not None and not np.isnan(ma60)
        has_atr = atr is not None and not np.isnan(atr) and atr > 0
        has_rsi = rsi is not None and not np.isnan(rsi)
        has_recent_low = recent_low is not None and not np.isnan(recent_low)
        has_recent_high = recent_high is not None and not np.isnan(recent_high)
        has_boll_upper = boll_upper is not None and not np.isnan(boll_upper)
        has_boll_mid = boll_mid is not None and not np.isnan(boll_mid)

        # ── 信号方向的ATR系数 ──
        # BUY → 看多 → 止损紧、止盈宽; SELL → 看空 → 止损宽、止盈紧
        if signal == "BUY":
            sl_atr_k = 0.5 if confidence >= 0.65 else 0.8
            tp_atr_k = 1.5 if confidence >= 0.65 else 1.0
        elif signal == "SELL":
            sl_atr_k = 1.5 if confidence >= 0.65 else 1.2
            tp_atr_k = 0.5 if confidence >= 0.65 else 0.8
        else:  # HOLD
            sl_atr_k = 1.0
            tp_atr_k = 1.0

        # ══════════════════════════════════════════
        # 止损价计算: 选择最佳支撑位 - ATR缓冲
        # ══════════════════════════════════════════
        support_candidates = []
        if has_boll and boll_lower < current_price:
            support_candidates.append(("布林带下轨", float(boll_lower)))
        if has_ma20 and ma20 < current_price:
            support_candidates.append(("MA20均线", float(ma20)))
        if has_recent_low and recent_low < current_price:
            support_candidates.append(("近20日最低", float(recent_low)))

        sl_basis = ""
        sl_level = 0.0
        sl_atr_buffer = 0.0

        if support_candidates:
            # 选取最接近现价的支撑位（最高的支撑 = 最近的）
            support_candidates.sort(key=lambda x: x[1], reverse=True)
            sl_basis, sl_level = support_candidates[0]
        elif has_boll:
            # 所有支撑都在现价之上（罕见），用布林下轨兜底
            sl_basis, sl_level = "布林带下轨", float(boll_lower)
        else:
            # 无技术指标可用，回退：现价 × (1 - 8%)
            sl_basis = "默认百分比"
            sl_level = current_price * 0.92

        # 应用ATR缓冲
        if has_atr:
            sl_atr_buffer = float(atr) * sl_atr_k
            stop_loss_price = sl_level - sl_atr_buffer
        else:
            stop_loss_price = sl_level * 0.98  # 无ATR时下移2%
            sl_atr_buffer = 0.0

        # 约束：止损不能为负，且不应高于现价的95%
        stop_loss_price = max(stop_loss_price, 0.01)
        stop_loss_price = min(stop_loss_price, current_price * 0.95)

        # ══════════════════════════════════════════
        # 止盈价计算: 选择最佳阻力位 + ATR延伸
        # ══════════════════════════════════════════
        resistance_candidates = []
        if has_boll_upper and boll_upper > current_price:
            resistance_candidates.append(("布林带上轨", float(boll_upper)))
        if has_recent_high and recent_high > current_price:
            resistance_candidates.append(("近20日最高", float(recent_high)))
        if has_ma60 and ma60 > current_price:
            resistance_candidates.append(("MA60均线", float(ma60)))

        tp_basis = ""
        tp_level = 0.0
        tp_atr_extension = 0.0

        if resistance_candidates:
            # 选取最接近现价的阻力位（最低的阻力 = 最近的）
            resistance_candidates.sort(key=lambda x: x[1])
            tp_basis, tp_level = resistance_candidates[0]

            # 如果强看多信号，目标可以突破第一阻力
            if (
                signal == "BUY"
                and confidence >= 0.65
                and len(resistance_candidates) > 1
            ):
                tp_basis, tp_level = resistance_candidates[1]
                tp_basis = f"{tp_basis}(强势突破)"
        elif has_boll_upper:
            tp_basis, tp_level = "布林带上轨", float(boll_upper)
        else:
            tp_basis = "默认百分比"
            tp_level = current_price * 1.15

        # 应用ATR延伸
        if has_atr:
            tp_atr_extension = float(atr) * tp_atr_k
            take_profit_price = tp_level + tp_atr_extension
        else:
            take_profit_price = tp_level * 1.02
            tp_atr_extension = 0.0

        # RSI修正：超买时收紧止盈目标
        rsi_note = ""
        if has_rsi:
            if rsi > 75:
                take_profit_price = min(take_profit_price, tp_level)
                rsi_note = "RSI超买，止盈目标收紧"
            elif rsi < 25:
                stop_loss_price = min(stop_loss_price, sl_level)
                rsi_note = "RSI超卖，止损位收紧保护"

        # 约束：止盈至少高于现价1%
        take_profit_price = max(take_profit_price, current_price * 1.01)

        # ── 组装结果 ──
        indicators_used = []
        if has_boll:
            indicators_used.append("布林带")
        if has_ma20:
            indicators_used.append("MA20")
        if has_ma60:
            indicators_used.append("MA60")
        if has_atr:
            indicators_used.append("ATR")
        if has_rsi:
            indicators_used.append("RSI")
        if has_recent_low or has_recent_high:
            indicators_used.append("近期高低点")

        return {
            "stop_loss_price": round(stop_loss_price, 4),
            "take_profit_price": round(take_profit_price, 4),
            "calc_method": {
                "sl_basis": sl_basis,
                "sl_level": round(sl_level, 4),
                "sl_atr_buffer": round(sl_atr_buffer, 4),
                "tp_basis": tp_basis,
                "tp_level": round(tp_level, 4),
                "tp_atr_extension": round(tp_atr_extension, 4),
                "atr": round(float(atr), 4) if has_atr else None,
                "rsi": round(float(rsi), 2) if has_rsi else None,
                "rsi_note": rsi_note,
                "signal_effect": {
                    "BUY": "止损收紧、止盈放宽",
                    "SELL": "止损放宽、止盈收紧",
                    "HOLD": "标准区间",
                }.get(signal, "标准区间"),
                "indicators_used": indicators_used,
            },
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

        try:
            df_raw = db.get_daily_data(symbol)
            if not df_raw.empty:
                df_ind = TechnicalIndicators.calculate_all(df_raw)
                smart_levels = self._calculate_smart_levels(
                    df_ind, current_price, cost_price, final_signal, confidence
                )
                if smart_levels:
                    advice["stop_loss_price"] = smart_levels["stop_loss_price"]
                    advice["take_profit_price"] = smart_levels["take_profit_price"]
                    advice["price_calc"] = smart_levels["calc_method"]
        except Exception as e:
            logger.warning(f"智能止盈止损计算失败 {symbol}: {e}")

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

    def get_portfolio_correlation(self, days: int = 90) -> pd.DataFrame:
        """计算持仓相关性矩阵"""
        if not self.holdings:
            return pd.DataFrame()

        price_data = {}
        for holding in self.holdings:
            symbol = holding["symbol"]
            # 尝试获取最近N天的数据
            try:
                # 确保有数据 (fetch if needed logic is inside analyze_holding usually,
                # but here we just read DB to be fast. If empty, skip)
                df = db.get_daily_data(symbol)
                if not df.empty:
                    # 截取最近N天
                    df = df.tail(days).copy()
                    df["date"] = pd.to_datetime(df["date"])
                    df = df.set_index("date")
                    price_data[f"{symbol}"] = df["close"]
            except Exception as e:
                logger.warning(f"获取 {symbol} 相关性数据失败: {e}")

        if not price_data:
            return pd.DataFrame()

        # 合并数据
        df_prices = pd.DataFrame(price_data)
        # 计算相关性
        if df_prices.empty:
            return pd.DataFrame()

        return df_prices.corr()

    def calculate_position_size(
        self,
        atr: float,
        current_price: float,
        total_capital: float = 100000,
        risk_per_trade: float = 0.01,
        stop_loss_atr_multiple: float = 2.0,
    ) -> Dict[str, Any]:
        """基于ATR计算建议仓位 (波动率资金管理)"""
        if atr <= 0 or current_price <= 0:
            return {}

        # 止损距离
        stop_loss_dist = atr * stop_loss_atr_multiple
        # 单笔交易最大允许亏损额
        max_risk_amt = total_capital * risk_per_trade

        # 建议股数 = 最大亏损额 / 每股止损距离
        suggested_shares = int(max_risk_amt / stop_loss_dist)
        # 向下取整到100倍数 (A股)
        suggested_shares = (suggested_shares // 100) * 100

        # 建议金额
        suggested_value = suggested_shares * current_price
        # 仓位占比
        position_pct = suggested_value / total_capital

        return {
            "atr": atr,
            "stop_loss_distance": stop_loss_dist,
            "stop_loss_price": current_price - stop_loss_dist,
            "max_risk_amount": max_risk_amt,
            "suggested_shares": suggested_shares,
            "suggested_value": suggested_value,
            "position_pct": position_pct,
            "risk_per_trade_pct": risk_per_trade,
        }

    def calculate_grid_strategy(
        self,
        current_price: float,
        volatility_atr: float,
        grid_count: int = 5,
        grid_width_atr: float = 1.0,
    ) -> List[Dict[str, Any]]:
        """生成网格交易策略表"""
        if current_price <= 0 or volatility_atr <= 0:
            return []

        step = volatility_atr * grid_width_atr
        grids = []

        # 生成买入网格 (当前价下方)
        for i in range(1, grid_count + 1):
            price = current_price - (step * i)
            grids.append(
                {
                    "type": "BUY",
                    "level": i,
                    "price": round(price, 3),
                    "diff_pct": -round((step * i) / current_price * 100, 2),
                    "action": f"买入第{i}档",
                }
            )

        # 生成卖出网格 (当前价上方)
        for i in range(1, grid_count + 1):
            price = current_price + (step * i)
            grids.append(
                {
                    "type": "SELL",
                    "level": i,
                    "price": round(price, 3),
                    "diff_pct": round((step * i) / current_price * 100, 2),
                    "action": f"卖出第{i}档",
                }
            )

        # 按价格降序排列
        grids.sort(key=lambda x: x["price"], reverse=True)
        return grids

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
