import smtplib
from email.mime.text import MIMEText
from email.mime.multipart import MIMEMultipart
from datetime import datetime
from typing import Any

import streamlit as st

from utils.helpers import logger

ALERT_COOLDOWN_SECONDS = 3600


def is_email_configured() -> bool:
    try:
        cfg = st.secrets.get("email", {})
        return bool(
            cfg.get("smtp_server") and cfg.get("username") and cfg.get("password")
        )
    except Exception:
        return False


def _get_email_config() -> dict:
    cfg = st.secrets["email"]
    return {
        "smtp_server": cfg["smtp_server"],
        "smtp_port": int(cfg.get("smtp_port", 587)),
        "username": cfg["username"],
        "password": cfg["password"],
        "sender": cfg.get("sender", cfg["username"]),
    }


def send_alert_email(subject: str, body_html: str, to_email: str) -> bool:
    try:
        cfg = _get_email_config()
        msg = MIMEMultipart("alternative")
        msg["Subject"] = subject
        msg["From"] = cfg["sender"]
        msg["To"] = to_email
        msg.attach(MIMEText(body_html, "html", "utf-8"))

        with smtplib.SMTP(cfg["smtp_server"], cfg["smtp_port"]) as server:
            server.ehlo()
            server.starttls()
            server.login(cfg["username"], cfg["password"])
            server.sendmail(cfg["sender"], [to_email], msg.as_string())

        logger.info(f"Alert email sent to {to_email}: {subject}")
        return True
    except Exception as e:
        logger.error(f"Failed to send alert email: {e}")
        return False


def _should_alert(symbol: str, alert_type: str) -> bool:
    key = f"_alert_sent_{symbol}_{alert_type}"
    last_sent = st.session_state.get(key)
    if last_sent is None:
        return True
    elapsed = (datetime.now() - last_sent).total_seconds()
    return elapsed >= ALERT_COOLDOWN_SECONDS


def _mark_alert_sent(symbol: str, alert_type: str) -> None:
    key = f"_alert_sent_{symbol}_{alert_type}"
    st.session_state[key] = datetime.now()


def _build_alert_body(alerts: list[dict[str, Any]]) -> str:
    rows = []
    for a in alerts:
        color = "#c62828" if a["type"] == "止损" else "#2e7d32"
        rows.append(
            f"<tr>"
            f"<td style='padding:8px;border:1px solid #ddd'>{a['name']} ({a['symbol']})</td>"
            f"<td style='padding:8px;border:1px solid #ddd'>{a['currency']}{a['current_price']:.2f}</td>"
            f"<td style='padding:8px;border:1px solid #ddd;color:{color};font-weight:bold'>{a['type']}</td>"
            f"<td style='padding:8px;border:1px solid #ddd'>{a['currency']}{a['trigger_price']:.2f}</td>"
            f"<td style='padding:8px;border:1px solid #ddd'>{a['pnl_pct']:+.2f}%</td>"
            f"</tr>"
        )

    return f"""
    <div style="font-family:system-ui,sans-serif;max-width:600px;margin:0 auto">
        <h2 style="color:#1976d2">📊 Stock Analyzer 止盈止损提醒</h2>
        <p>以下持仓已触发价格预警（{datetime.now().strftime("%Y-%m-%d %H:%M")}）：</p>
        <table style="border-collapse:collapse;width:100%">
            <thead>
                <tr style="background:#f5f5f5">
                    <th style="padding:8px;border:1px solid #ddd;text-align:left">标的</th>
                    <th style="padding:8px;border:1px solid #ddd;text-align:left">现价</th>
                    <th style="padding:8px;border:1px solid #ddd;text-align:left">触发类型</th>
                    <th style="padding:8px;border:1px solid #ddd;text-align:left">触发价</th>
                    <th style="padding:8px;border:1px solid #ddd;text-align:left">盈亏</th>
                </tr>
            </thead>
            <tbody>{"".join(rows)}</tbody>
        </table>
        <p style="color:#999;font-size:0.85rem;margin-top:16px">
            ⚠️ 本提醒仅供参考，不构成投资建议。
        </p>
    </div>
    """


def check_and_send_alerts(results: list[dict], to_email: str) -> list[dict]:
    triggered: list[dict[str, Any]] = []

    for r in results:
        if "error" in r:
            continue

        symbol = r.get("symbol", "")
        name = r.get("name", symbol)
        current_price = r.get("current_price", 0)
        advice = r.get("advice", {})
        sl_price = advice.get("stop_loss_price")
        tp_price = advice.get("take_profit_price")
        pnl_pct = r.get("pnl_pct", 0)
        market = r.get("market", "A")
        curr = "$" if market == "US" else "¥"

        if not (sl_price and tp_price and current_price > 0):
            continue

        if current_price <= sl_price and _should_alert(symbol, "sl"):
            triggered.append(
                {
                    "symbol": symbol,
                    "name": name,
                    "current_price": current_price,
                    "trigger_price": sl_price,
                    "type": "止损",
                    "pnl_pct": pnl_pct,
                    "currency": curr,
                }
            )
            _mark_alert_sent(symbol, "sl")

        if current_price >= tp_price and _should_alert(symbol, "tp"):
            triggered.append(
                {
                    "symbol": symbol,
                    "name": name,
                    "current_price": current_price,
                    "trigger_price": tp_price,
                    "type": "止盈",
                    "pnl_pct": pnl_pct,
                    "currency": curr,
                }
            )
            _mark_alert_sent(symbol, "tp")

    if triggered:
        subject = f"⚠️ 持仓预警: {len(triggered)}个标的触发止盈止损"
        body = _build_alert_body(triggered)
        send_alert_email(subject, body, to_email)

    return triggered
