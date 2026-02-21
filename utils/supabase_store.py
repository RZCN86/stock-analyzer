from __future__ import annotations

from datetime import datetime
from typing import Any

from utils.helpers import logger

_client = None


def _get_client():
    global _client
    if _client is not None:
        return _client

    try:
        url = ""
        key = ""

        # Try Streamlit secrets first
        try:
            import streamlit as st

            cfg = st.secrets.get("supabase", {})
            url = cfg.get("url", "")
            key = cfg.get("key", "")
        except Exception:
            pass

        # Fallback: read from environment variables
        if not (url and key):
            import os

            url = os.environ.get("SUPABASE_URL", "")
            key = os.environ.get("SUPABASE_KEY", "")

        if not (url and key):
            return None

        from supabase import create_client

        _client = create_client(url, key)
        return _client
    except Exception as e:
        logger.debug(f"Supabase not available: {e}")
        return None


def is_available() -> bool:
    return _get_client() is not None


def load_holdings() -> list[dict[str, Any]]:
    client = _get_client()
    if client is None:
        return []
    try:
        resp = client.table("holdings").select("*").order("created_at").execute()
        rows = resp.data or []
        return [
            {
                "symbol": r["symbol"],
                "market": r["market"],
                "shares": r["shares"],
                "cost_price": r["cost_price"],
                "buy_date": r.get("buy_date", ""),
            }
            for r in rows
        ]
    except Exception as e:
        logger.error(f"Supabase load_holdings failed: {e}")
        return []


def save_holding(
    symbol: str, market: str, shares: int, cost_price: float, buy_date: str = ""
) -> bool:
    client = _get_client()
    if client is None:
        return False
    try:
        if not buy_date:
            buy_date = datetime.now().strftime("%Y-%m-%d")
        client.table("holdings").insert(
            {
                "symbol": symbol,
                "market": market.upper(),
                "shares": shares,
                "cost_price": cost_price,
                "buy_date": buy_date,
            }
        ).execute()
        return True
    except Exception as e:
        logger.error(f"Supabase save_holding failed: {e}")
        return False


def delete_holding(symbol: str, market: str) -> bool:
    client = _get_client()
    if client is None:
        return False
    try:
        client.table("holdings").delete().eq("symbol", symbol).eq(
            "market", market.upper()
        ).execute()
        return True
    except Exception as e:
        logger.error(f"Supabase delete_holding failed: {e}")
        return False


def add_trade_record(
    symbol: str,
    market: str,
    action: str,
    shares: int,
    price: float,
    trade_date: str = "",
    notes: str = "",
) -> bool:
    client = _get_client()
    if client is None:
        return False
    try:
        if not trade_date:
            trade_date = datetime.now().strftime("%Y-%m-%d")
        client.table("trade_history").insert(
            {
                "symbol": symbol,
                "market": market.upper(),
                "action": action,
                "shares": shares,
                "price": price,
                "trade_date": trade_date,
                "notes": notes,
            }
        ).execute()
        return True
    except Exception as e:
        logger.error(f"Supabase add_trade_record failed: {e}")
        return False


def load_trade_history(symbol: str | None = None) -> list[dict[str, Any]]:
    client = _get_client()
    if client is None:
        return []
    try:
        query = client.table("trade_history").select("*").order("trade_date", desc=True)
        if symbol:
            query = query.eq("symbol", symbol)
        resp = query.limit(200).execute()
        return resp.data or []
    except Exception as e:
        logger.error(f"Supabase load_trade_history failed: {e}")
        return []


def load_watchlist() -> list[dict[str, Any]]:
    client = _get_client()
    if client is None:
        return []
    try:
        resp = (
            client.table("watchlist").select("*").order("added_at", desc=True).execute()
        )
        return resp.data or []
    except Exception as e:
        logger.error(f"Supabase load_watchlist failed: {e}")
        return []


def add_to_watchlist(symbol: str, market: str, notes: str = "") -> bool:
    client = _get_client()
    if client is None:
        return False
    try:
        existing = (
            client.table("watchlist")
            .select("id")
            .eq("symbol", symbol)
            .eq("market", market.upper())
            .execute()
        )
        if existing.data:
            return True
        client.table("watchlist").insert(
            {
                "symbol": symbol,
                "market": market.upper(),
                "notes": notes,
            }
        ).execute()
        return True
    except Exception as e:
        logger.error(f"Supabase add_to_watchlist failed: {e}")
        return False


def remove_from_watchlist(symbol: str, market: str) -> bool:
    client = _get_client()
    if client is None:
        return False
    try:
        client.table("watchlist").delete().eq("symbol", symbol).eq(
            "market", market.upper()
        ).execute()
        return True
    except Exception as e:
        logger.error(f"Supabase remove_from_watchlist failed: {e}")
        return False
