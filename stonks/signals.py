"""
Signal evaluation: evaluate_alerts() and generate_suggestion().
Includes RSI, moving-average cross, 52W proximity, volume spike, and price-move signals.
"""

THRESHOLDS = {
    "pe_max":          20,    # flag P/E below this (value territory)
    "volume_spike_x":  1.5,   # flag volume > N × 20-day average
    "week52_pct":      5.0,   # flag within X% of 52W high or low
    "price_change_pct": 2.0,  # flag |% change today| above this
    "rsi_oversold":    30,    # flag RSI below this
    "rsi_overbought":  70,    # flag RSI above this
}


def evaluate_alerts(row: dict) -> list[str]:
    """Apply all filter thresholds and return a list of alert strings."""
    alerts = []
    th = THRESHOLDS

    # P/E value signal (not for ETFs)
    if not row.get("is_etf") and row.get("pe_ratio") and row["pe_ratio"] < th["pe_max"]:
        alerts.append(f"P/E<{th['pe_max']}")

    # Volume spike
    if row.get("volume_ratio") and row["volume_ratio"] >= th["volume_spike_x"]:
        alerts.append(f"VOL×{row['volume_ratio']:.1f}")

    # Near 52-week extremes
    if row.get("pct_from_high") is not None and row["pct_from_high"] <= th["week52_pct"]:
        alerts.append("NEAR 52W-HIGH")
    if row.get("pct_from_low") is not None and row["pct_from_low"] <= th["week52_pct"]:
        alerts.append("NEAR 52W-LOW")

    # Big price move
    if row.get("pct_change") is not None and abs(row["pct_change"]) >= th["price_change_pct"]:
        direction = "UP" if row["pct_change"] > 0 else "DOWN"
        alerts.append(f"MOVE {direction} {abs(row['pct_change']):.1f}%")

    # RSI extremes
    if row.get("rsi") is not None:
        if row["rsi"] < th["rsi_oversold"]:
            alerts.append(f"RSI {row['rsi']:.0f} OVERSOLD")
        elif row["rsi"] > th["rsi_overbought"]:
            alerts.append(f"RSI {row['rsi']:.0f} OVERBOUGHT")

    # Moving average cross alignment
    price = row.get("price")
    ma50  = row.get("ma50")
    ma200 = row.get("ma200")
    if price and ma50 and ma200:
        if price > ma50 > ma200:
            alerts.append("GOLDEN CROSS")
        elif price < ma50 < ma200:
            alerts.append("DEATH CROSS")

    return alerts


def generate_suggestion(alerts: list[str], row: dict) -> tuple[str, str]:
    """
    Interpret the combination of active alerts.
    Returns (suggestion_text, rich_style).
    """
    if not alerts:
        return "—", "dim"

    has = lambda keyword: any(keyword in a for a in alerts)

    is_etf       = row.get("is_etf", False)
    low_pe       = has("P/E") and not is_etf
    vol_spike    = has("VOL")
    near_high    = has("52W-HIGH")
    near_low     = has("52W-LOW")
    move_up      = has("MOVE UP")
    move_down    = has("MOVE DOWN")
    rsi_over     = has("OVERSOLD")
    rsi_under    = has("OVERBOUGHT")
    golden       = has("GOLDEN CROSS")
    death        = has("DEATH CROSS")

    # Highest-conviction combos first
    if rsi_over and near_low and low_pe:
        return "Deep value + oversold — strong reversal watch", "bold green"
    if rsi_over and near_low:
        return "Deep oversold near 52W low — high-risk reversal watch", "bold green"
    if rsi_under and near_high:
        return "Overbought at 52W high — pullback risk", "bold red"
    if low_pe and near_low:
        return "Value opportunity — research further", "bold green"
    if vol_spike and move_up and near_high:
        return "Momentum breakout — watch for continuation", "bold green"
    if vol_spike and move_up and golden:
        return "Strong buying with bullish MA alignment", "bold green"
    if vol_spike and move_up:
        return "Unusual buying interest", "green"
    if vol_spike and move_down and near_low:
        return "Heavy selling near 52W low — high risk", "bold red"
    if vol_spike and move_down and death:
        return "Heavy selling with bearish MA alignment — avoid", "bold red"
    if vol_spike and move_down:
        return "Unusual selling — investigate catalyst", "red"
    if golden:
        return "Bullish MA alignment — price above 50d & 200d MA", "green"
    if death:
        return "Bearish MA alignment — avoid new longs", "red"
    if near_low and move_down:
        return "Selling pressure — use caution", "red"
    if near_high and move_up:
        return "Testing resistance — monitor closely", "yellow"
    if near_high:
        return "Near 52W high — watch for breakout or reversal", "yellow"
    if near_low:
        return "Oversold territory — watch for reversal", "yellow"
    if rsi_over:
        return "RSI oversold — potential bounce candidate", "cyan"
    if rsi_under:
        return "RSI overbought — monitor for pullback", "yellow"
    if low_pe:
        return "Potentially undervalued", "cyan"
    if move_up:
        return "Strong positive move today", "green"
    if move_down:
        return "Notable decline today", "red"

    return "Flagged — review signals", "dim"
