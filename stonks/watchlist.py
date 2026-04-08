"""
Persist and load per-exchange watchlists to/from ~/.stonks/watchlists.json.
"""

import json
from pathlib import Path

WATCHLIST_PATH = Path.home() / ".stonks" / "watchlists.json"


def load_watchlist(exchange_key: str) -> tuple[list[str], set[str]] | None:
    """
    Return (tickers, etf_set) for the given exchange if a saved watchlist exists,
    otherwise return None.
    """
    if not WATCHLIST_PATH.exists():
        return None
    try:
        data = json.loads(WATCHLIST_PATH.read_text())
        entry = data.get(exchange_key)
        if not entry:
            return None
        tickers = entry.get("tickers", [])
        etfs    = set(entry.get("etfs", []))
        if not tickers:
            return None
        return tickers, etfs
    except Exception:
        return None


def save_watchlist(exchange_key: str, tickers: list[str], etf_set: set[str]):
    """Upsert the watchlist for the given exchange key."""
    WATCHLIST_PATH.parent.mkdir(parents=True, exist_ok=True)

    data: dict = {}
    if WATCHLIST_PATH.exists():
        try:
            data = json.loads(WATCHLIST_PATH.read_text())
        except Exception:
            data = {}

    data[exchange_key] = {
        "tickers": tickers,
        "etfs":    list(etf_set),
    }
    WATCHLIST_PATH.write_text(json.dumps(data, indent=2))
