"""
Signal evaluation and conviction scoring.

Public API:
  - THRESHOLDS         : tunable filter constants
  - evaluate_alerts()  : returns list[str] of alert labels (unchanged shape)
  - score_row()        : returns (score_int, direction, bull_pts, bear_pts)
  - generate_suggestion(): returns (text, rich_style) — uses score_row() internally
  - compute_signals()  : one-shot wrapper returning alerts + score + suggestion
"""

THRESHOLDS = {
    "pe_max":           20,    # flag P/E below this (value territory)
    "volume_spike_x":   1.5,   # flag volume > N × 20-day average
    "week52_pct":       5.0,   # flag within X% of 52W high or low
    "price_change_pct": 2.0,   # flag |% change today| above this
    "rsi_oversold":     30,    # flag RSI below this
    "rsi_overbought":   70,    # flag RSI above this
}


# ── Alerts (binary labels for display) ────────────────────────────────────────

def evaluate_alerts(row: dict) -> list[str]:
    """Apply all filter thresholds and return a list of alert strings."""
    alerts: list[str] = []
    th = THRESHOLDS

    if not row.get("is_etf") and row.get("pe_ratio") and row["pe_ratio"] < th["pe_max"]:
        alerts.append(f"P/E<{th['pe_max']}")

    if row.get("volume_ratio") and row["volume_ratio"] >= th["volume_spike_x"]:
        alerts.append(f"VOL×{row['volume_ratio']:.1f}")

    if row.get("pct_from_high") is not None and row["pct_from_high"] <= th["week52_pct"]:
        alerts.append("NEAR 52W-HIGH")
    if row.get("pct_from_low") is not None and row["pct_from_low"] <= th["week52_pct"]:
        alerts.append("NEAR 52W-LOW")

    if row.get("pct_change") is not None and abs(row["pct_change"]) >= th["price_change_pct"]:
        direction = "UP" if row["pct_change"] > 0 else "DOWN"
        alerts.append(f"MOVE {direction} {abs(row['pct_change']):.1f}%")

    if row.get("rsi") is not None:
        if row["rsi"] < th["rsi_oversold"]:
            alerts.append(f"RSI {row['rsi']:.0f} OVERSOLD")
        elif row["rsi"] > th["rsi_overbought"]:
            alerts.append(f"RSI {row['rsi']:.0f} OVERBOUGHT")

    price = row.get("price")
    ma50  = row.get("ma50")
    ma200 = row.get("ma200")
    if price and ma50 and ma200:
        if price > ma50 > ma200:
            alerts.append("GOLDEN CROSS")
        elif price < ma50 < ma200:
            alerts.append("DEATH CROSS")

    return alerts


# ── Conviction score (0–100) ──────────────────────────────────────────────────

def score_row(row: dict) -> tuple[int, str, float, float]:
    """
    Compute a weighted conviction score in [0, 100] and a directional bias.

    Every filter that `evaluate_alerts()` fires on contributes points to a
    bullish or bearish bucket. The total magnitude (bull + bear, capped at
    100) becomes the score; relative balance determines direction.

    Returns (score, direction, bull_pts, bear_pts), where
    direction ∈ {"bullish", "bearish", "mixed", "neutral"}.
    """
    th = THRESHOLDS
    bull = 0.0
    bear = 0.0
    is_etf = bool(row.get("is_etf"))

    # Today's price move — carries direction
    pc = row.get("pct_change")
    if pc is not None and abs(pc) >= th["price_change_pct"]:
        mag = min(abs(pc) * 2.5, 20.0)          # 2% → 5 pts, 8% → 20 pts (cap)
        if pc > 0:
            bull += mag
        else:
            bear += mag

    # Volume spike — amplifier, inherits the direction of today's move.
    vr = row.get("volume_ratio")
    if vr and vr >= th["volume_spike_x"]:
        vol_pts = min((vr - th["volume_spike_x"]) * 10.0, 15.0)  # 1.5×→0, 3×→15
        if pc and pc > 0:
            bull += vol_pts
        elif pc and pc < 0:
            bear += vol_pts
        else:
            # Unusual activity with no clear move — split evenly
            bull += vol_pts * 0.5
            bear += vol_pts * 0.5

    # 52-week position
    pfl = row.get("pct_from_low")
    pfh = row.get("pct_from_high")
    if pfl is not None and pfl <= th["week52_pct"]:
        # Closer to 52W low = stronger reversal/value watch
        bull += (th["week52_pct"] - pfl) / th["week52_pct"] * 15.0
    if pfh is not None and pfh <= th["week52_pct"]:
        mag = (th["week52_pct"] - pfh) / th["week52_pct"] * 15.0
        if pc and pc > 0:
            # Breakout continuation
            bull += mag
        else:
            # At 52W high without buying = distribution risk
            bull += mag * 0.5
            bear += mag * 0.5

    # RSI extremes
    rsi = row.get("rsi")
    if rsi is not None:
        if rsi < th["rsi_oversold"]:
            bull += (th["rsi_oversold"] - rsi) * 0.8   # rsi 10 → 16 pts
        elif rsi > th["rsi_overbought"]:
            bear += (rsi - th["rsi_overbought"]) * 0.8

    # Moving-average alignment
    price = row.get("price")
    ma50  = row.get("ma50")
    ma200 = row.get("ma200")
    if price and ma50 and ma200:
        if price > ma50 > ma200:
            bull += 10.0
        elif price < ma50 < ma200:
            bear += 10.0
        elif price > ma200:
            bull += 3.0
        else:
            bear += 3.0

    # Low P/E — value signal (stocks only)
    pe = row.get("pe_ratio")
    if not is_etf and pe and 0 < pe < th["pe_max"]:
        bull += (th["pe_max"] - pe) / th["pe_max"] * 10.0

    total = int(min(round(bull + bear), 100))

    if total < 8:
        direction = "neutral"
    elif bull >= bear * 2.0:
        direction = "bullish"
    elif bear >= bull * 2.0:
        direction = "bearish"
    else:
        direction = "mixed"

    return total, direction, bull, bear


# ── Suggestion text (score-gated, combo-aware) ────────────────────────────────

def generate_suggestion(alerts: list[str], row: dict) -> tuple[str, str]:
    """
    Interpret the row's signals. Returns (text, rich_style).

    The score determines the tier (strong / medium / lean); a combo matcher
    supplies specific descriptive text when signals align on a known pattern.
    Falls back to a generic per-tier phrase when no combo matches.
    """
    if not alerts:
        return "—", "dim"

    score, direction, _, _ = score_row(row)
    tier  = _tier(score, direction)
    style = _STYLE_FOR[tier]

    combo = _combo_text(alerts, bool(row.get("is_etf")))
    return (combo or _GENERIC_TEXT[tier]), style


def compute_signals(row: dict) -> dict:
    """
    One-shot evaluator for callers that need alerts + score + suggestion.
    Computes everything in a single pass so display/export/web don't have
    to call evaluate_alerts and generate_suggestion separately.
    """
    alerts = evaluate_alerts(row)
    score, direction, bull, bear = score_row(row)

    if alerts:
        tier  = _tier(score, direction)
        style = _STYLE_FOR[tier]
        combo = _combo_text(alerts, bool(row.get("is_etf")))
        suggestion = combo or _GENERIC_TEXT[tier]
    else:
        suggestion, style = "—", "dim"

    return {
        "alerts":     alerts,
        "score":      score,
        "direction":  direction,
        "bull_pts":   bull,
        "bear_pts":   bear,
        "suggestion": suggestion,
        "style":      style,
    }


# ── Internal helpers ──────────────────────────────────────────────────────────

def _combo_text(alerts: list[str], is_etf: bool) -> str | None:
    """Return descriptive text for well-known signal combinations, or None."""
    has = lambda kw: any(kw in a for a in alerts)

    low_pe     = has("P/E") and not is_etf
    vol_spike  = has("VOL")
    near_high  = has("52W-HIGH")
    near_low   = has("52W-LOW")
    move_up    = has("MOVE UP")
    move_down  = has("MOVE DOWN")
    oversold   = has("OVERSOLD")
    overbought = has("OVERBOUGHT")
    golden     = has("GOLDEN CROSS")
    death      = has("DEATH CROSS")

    # Multi-signal combos first
    if oversold and near_low and low_pe:
        return "Deep value + oversold — strong reversal watch"
    if oversold and near_low:
        return "Deep oversold near 52W low — reversal watch"
    if overbought and near_high:
        return "Overbought at 52W high — pullback risk"
    if low_pe and near_low:
        return "Value opportunity — research further"
    if vol_spike and move_up and near_high:
        return "Momentum breakout — watch continuation"
    if vol_spike and move_up and golden:
        return "Strong buying with bullish MA alignment"
    if vol_spike and move_up:
        return "Unusual buying interest"
    if vol_spike and move_down and near_low:
        return "Heavy selling near 52W low — high risk"
    if vol_spike and move_down and death:
        return "Heavy selling with bearish MA alignment"
    if vol_spike and move_down:
        return "Unusual selling — investigate catalyst"

    # Single-signal hints
    if golden:     return "Bullish MA alignment"
    if death:      return "Bearish MA alignment"
    if near_low:   return "Oversold territory — reversal watch"
    if near_high:  return "Near 52W high — breakout watch"
    if oversold:   return "RSI oversold — potential bounce"
    if overbought: return "RSI overbought — monitor pullback"
    if low_pe:     return "Potentially undervalued"
    if move_up:    return "Strong positive move today"
    if move_down:  return "Notable decline today"
    return None


def _tier(score: int, direction: str) -> str:
    """Map (score, direction) → styling bucket."""
    if score >= 60:
        if direction == "bullish": return "strong_pos"
        if direction == "bearish": return "strong_neg"
        if direction == "mixed":   return "warn"
        return "neutral"
    if score >= 30:
        if direction == "bullish": return "pos"
        if direction == "bearish": return "neg"
        if direction == "mixed":   return "warn"
        return "neutral"
    if direction == "bullish": return "lean_pos"
    if direction == "bearish": return "lean_neg"
    return "neutral"


_STYLE_FOR = {
    "strong_pos": "bold green",
    "pos":        "green",
    "lean_pos":   "cyan",
    "strong_neg": "bold red",
    "neg":        "red",
    "lean_neg":   "yellow",
    "warn":       "yellow",
    "neutral":    "dim",
}

_GENERIC_TEXT = {
    "strong_pos": "High-conviction bullish setup",
    "pos":        "Bullish signals — review further",
    "lean_pos":   "Early bullish lean",
    "strong_neg": "High-conviction bearish signals",
    "neg":        "Bearish signals — caution",
    "lean_neg":   "Early bearish lean",
    "warn":       "Mixed signals — uncertain",
    "neutral":    "Flagged — review",
}
