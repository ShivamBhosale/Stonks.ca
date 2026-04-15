"""
Export scan results to CSV and JSON on the Desktop.
"""

import csv
import json
import os
from datetime import datetime

from .signals import compute_signals

_FIELDNAMES = [
    "ticker", "type", "price", "pct_change", "volume", "avg_volume",
    "volume_ratio", "pe_ratio", "week52_high", "week52_low",
    "pct_from_high", "pct_from_low", "rsi", "ma50", "ma200",
    "market_cap", "sector", "industry",
    "score", "direction", "alerts", "suggestion",
]


def _desktop_path(exchange_key: str, ext: str) -> str:
    ts = datetime.now().strftime("%Y%m%d_%H%M%S")
    filename = f"{exchange_key}_screener_report_{ts}.{ext}"
    return os.path.join(os.path.expanduser("~/Desktop"), filename)


def export_csv(results: list[dict], path: str):
    """Write scan results to a CSV file."""
    with open(path, "w", newline="") as f:
        writer = csv.DictWriter(f, fieldnames=_FIELDNAMES)
        writer.writeheader()
        for row in sorted(results, key=lambda r: r["ticker"]):
            sig = compute_signals(row)
            writer.writerow({
                "ticker":        row["ticker"],
                "type":          "ETF" if row.get("is_etf") else "Stock",
                "price":         f"{row['price']:.2f}" if row.get("price") else "",
                "pct_change":    f"{row['pct_change']:.2f}" if row.get("pct_change") is not None else "",
                "volume":        row.get("volume") or "",
                "avg_volume":    row.get("avg_volume") or "",
                "volume_ratio":  f"{row['volume_ratio']:.2f}" if row.get("volume_ratio") is not None else "",
                "pe_ratio":      f"{row['pe_ratio']:.2f}" if row.get("pe_ratio") is not None else "",
                "week52_high":   f"{row['week52_high']:.2f}" if row.get("week52_high") else "",
                "week52_low":    f"{row['week52_low']:.2f}" if row.get("week52_low") else "",
                "pct_from_high": f"{row['pct_from_high']:.2f}" if row.get("pct_from_high") is not None else "",
                "pct_from_low":  f"{row['pct_from_low']:.2f}" if row.get("pct_from_low") is not None else "",
                "rsi":           f"{row['rsi']:.1f}" if row.get("rsi") is not None else "",
                "ma50":          f"{row['ma50']:.2f}" if row.get("ma50") else "",
                "ma200":         f"{row['ma200']:.2f}" if row.get("ma200") else "",
                "market_cap":    row.get("market_cap") or "",
                "sector":        row.get("sector") or "",
                "industry":      row.get("industry") or "",
                "score":         sig["score"],
                "direction":     sig["direction"],
                "alerts":        " | ".join(sig["alerts"]),
                "suggestion":    sig["suggestion"] if sig["suggestion"] != "—" else "",
            })


def export_json(results: list[dict], path: str):
    """Write scan results (with evaluated alerts) to a JSON file."""
    output = []
    for row in sorted(results, key=lambda r: r["ticker"]):
        sig = compute_signals(row)
        output.append({
            "ticker":        row["ticker"],
            "type":          "ETF" if row.get("is_etf") else "Stock",
            "price":         round(row["price"], 2) if row.get("price") else None,
            "pct_change":    round(row["pct_change"], 2) if row.get("pct_change") is not None else None,
            "volume":        row.get("volume"),
            "avg_volume":    row.get("avg_volume"),
            "volume_ratio":  round(row["volume_ratio"], 2) if row.get("volume_ratio") is not None else None,
            "pe_ratio":      round(row["pe_ratio"], 2) if row.get("pe_ratio") is not None else None,
            "week52_high":   round(row["week52_high"], 2) if row.get("week52_high") else None,
            "week52_low":    round(row["week52_low"], 2) if row.get("week52_low") else None,
            "pct_from_high": round(row["pct_from_high"], 2) if row.get("pct_from_high") is not None else None,
            "pct_from_low":  round(row["pct_from_low"], 2) if row.get("pct_from_low") is not None else None,
            "rsi":           round(row["rsi"], 1) if row.get("rsi") is not None else None,
            "ma50":          round(row["ma50"], 2) if row.get("ma50") else None,
            "ma200":         round(row["ma200"], 2) if row.get("ma200") else None,
            "market_cap":    row.get("market_cap"),
            "sector":        row.get("sector") or None,
            "industry":      row.get("industry") or None,
            "score":         sig["score"],
            "direction":     sig["direction"],
            "bull_pts":      round(sig["bull_pts"], 1),
            "bear_pts":      round(sig["bear_pts"], 1),
            "alerts":        sig["alerts"],
            "suggestion":    sig["suggestion"] if sig["suggestion"] != "—" else None,
        })
    with open(path, "w") as f:
        json.dump(output, f, indent=2)


def export_both(results: list[dict], exchange_key: str) -> tuple[str, str]:
    """Export CSV + JSON and return (csv_path, json_path)."""
    csv_path  = _desktop_path(exchange_key, "csv")
    json_path = _desktop_path(exchange_key, "json")
    export_csv(results, csv_path)
    export_json(results, json_path)
    return csv_path, json_path
