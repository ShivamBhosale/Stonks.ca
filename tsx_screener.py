"""
Stonks.ca — Multi-Exchange Stock Screener CLI
Scans equities on TSX, NYSE/NASDAQ, BSE, and NSE for notable signals
using real market data from yfinance.
"""

# ── Dependency check ────────────────────────────────────────────────────────
import sys
import importlib
import importlib.util

_REQUIRED = ["yfinance", "rich", "pandas"]
_MISSING = [pkg for pkg in _REQUIRED if importlib.util.find_spec(pkg) is None]
if _MISSING:
    print(f"Missing dependencies: {', '.join(_MISSING)}")
    print("Run:  pip install yfinance rich pandas")
    sys.exit(1)

# ── Imports ──────────────────────────────────────────────────────────────────
import csv
import os
import warnings
from datetime import date, datetime, time
from zoneinfo import ZoneInfo

import pandas as pd
import yfinance as yf
from rich import box
from rich.console import Console
from rich.panel import Panel
from rich.progress import BarColumn, Progress, SpinnerColumn, TextColumn
from rich.table import Table
from rich.text import Text

warnings.filterwarnings("ignore")  # suppress yfinance noise

# ── Configuration ────────────────────────────────────────────────────────────

# Filter thresholds (all configurable here)
THRESHOLDS = {
    "pe_max": 20,            # flag if P/E is below this value (value stock territory)
    "volume_spike_x": 1.5,  # flag if today's volume > N × 20-day average
    "week52_pct": 5.0,       # flag if within X% of 52-week high or low
    "price_change_pct": 2.0, # flag if |% change today| exceeds this
}

console = Console()

# ── Exchange definitions ──────────────────────────────────────────────────────

_ET  = ZoneInfo("America/New_York")
_IST = ZoneInfo("Asia/Kolkata")

# NYSE/NASDAQ statutory holidays 2025–2026
_NYSE_HOLIDAYS = {
    date(2025, 1, 1),   # New Year's Day
    date(2025, 1, 20),  # MLK Day
    date(2025, 2, 17),  # Presidents' Day
    date(2025, 4, 18),  # Good Friday
    date(2025, 5, 26),  # Memorial Day
    date(2025, 6, 19),  # Juneteenth
    date(2025, 7, 4),   # Independence Day
    date(2025, 9, 1),   # Labor Day
    date(2025, 11, 27), # Thanksgiving
    date(2025, 12, 25), # Christmas
    date(2026, 1, 1),   # New Year's Day
    date(2026, 1, 19),  # MLK Day
    date(2026, 2, 16),  # Presidents' Day
    date(2026, 4, 3),   # Good Friday
    date(2026, 5, 25),  # Memorial Day
    date(2026, 6, 19),  # Juneteenth
    date(2026, 7, 3),   # Independence Day (observed)
    date(2026, 9, 7),   # Labor Day
    date(2026, 11, 26), # Thanksgiving
    date(2026, 12, 25), # Christmas
}

# TSX statutory holidays 2025–2026
_TSX_HOLIDAYS = {
    date(2025, 1, 1),   # New Year's Day
    date(2025, 2, 17),  # Family Day (Ontario)
    date(2025, 4, 18),  # Good Friday
    date(2025, 5, 19),  # Victoria Day
    date(2025, 7, 1),   # Canada Day
    date(2025, 8, 4),   # Civic Holiday
    date(2025, 9, 1),   # Labour Day
    date(2025, 10, 13), # Thanksgiving
    date(2025, 12, 25), # Christmas Day
    date(2025, 12, 26), # Boxing Day
    date(2026, 1, 1),   # New Year's Day
    date(2026, 2, 16),  # Family Day (Ontario)
    date(2026, 4, 3),   # Good Friday
    date(2026, 5, 18),  # Victoria Day
    date(2026, 7, 1),   # Canada Day
    date(2026, 8, 3),   # Civic Holiday
    date(2026, 9, 7),   # Labour Day
    date(2026, 10, 12), # Thanksgiving
    date(2026, 12, 25), # Christmas Day
    date(2026, 12, 28), # Boxing Day (observed)
}

# BSE / NSE shared holidays 2025–2026
_INDIA_HOLIDAYS = {
    date(2025, 1, 26),  # Republic Day
    date(2025, 2, 19),  # Chhatrapati Shivaji Maharaj Jayanti
    date(2025, 3, 14),  # Holi
    date(2025, 4, 14),  # Dr. Ambedkar Jayanti
    date(2025, 4, 18),  # Good Friday
    date(2025, 5, 1),   # Maharashtra Day
    date(2025, 8, 15),  # Independence Day
    date(2025, 10, 2),  # Gandhi Jayanti
    date(2025, 10, 24), # Diwali — Laxmi Pujan
    date(2025, 10, 25), # Diwali — Balipratipada
    date(2025, 11, 5),  # Guru Nanak Jayanti
    date(2025, 12, 25), # Christmas
    date(2026, 1, 26),  # Republic Day
    date(2026, 3, 3),   # Holi
    date(2026, 4, 3),   # Good Friday
    date(2026, 4, 14),  # Dr. Ambedkar Jayanti
    date(2026, 5, 1),   # Maharashtra Day
    date(2026, 8, 15),  # Independence Day
    date(2026, 10, 2),  # Gandhi Jayanti
    date(2026, 10, 17), # Diwali
    date(2026, 11, 25), # Guru Nanak Jayanti
    date(2026, 12, 25), # Christmas
}

EXCHANGES = {
    "1": {
        "key":       "tsx",
        "name":      "TSX (Toronto Stock Exchange)",
        "suffix":    ".TO",
        "currency":  "CAD",
        "tz":        _ET,
        "open":      time(9, 30),
        "close":     time(16, 0),
        "open_label":  "9:30 AM ET",
        "close_label": "4:00 PM ET",
        "holidays":  _TSX_HOLIDAYS,
        "watchlist": [
            "RY.TO", "TD.TO", "BNS.TO", "BMO.TO", "CM.TO",
            "CNR.TO", "CP.TO", "SU.TO", "ENB.TO", "TRP.TO",
            "ABX.TO", "AEM.TO", "SHOP.TO", "CSU.TO", "MFC.TO",
            "SLF.TO", "BCE.TO", "T.TO", "WCN.TO", "ATD.TO",
        ],
        "etf_examples": "XIU.TO  XIC.TO  ZEB.TO  XEI.TO  VCN.TO  HXT.TO  ZAG.TO",
    },
    "2": {
        "key":       "nyse",
        "name":      "NYSE / NASDAQ (United States)",
        "suffix":    "",
        "currency":  "USD",
        "tz":        _ET,
        "open":      time(9, 30),
        "close":     time(16, 0),
        "open_label":  "9:30 AM ET",
        "close_label": "4:00 PM ET",
        "holidays":  _NYSE_HOLIDAYS,
        "watchlist": [
            "AAPL", "MSFT", "AMZN", "GOOGL", "META",
            "NVDA", "TSLA", "JPM", "JNJ", "V",
            "WMT", "UNH", "BAC", "XOM", "PG",
            "MA", "HD", "CVX", "LLY", "ABBV",
        ],
        "etf_examples": "SPY  QQQ  IWM  VTI  VOO  GLD  TLT  XLF  XLE",
    },
    "3": {
        "key":       "bse",
        "name":      "BSE (Bombay Stock Exchange)",
        "suffix":    ".BO",
        "currency":  "INR",
        "tz":        _IST,
        "open":      time(9, 15),
        "close":     time(15, 30),
        "open_label":  "9:15 AM IST",
        "close_label": "3:30 PM IST",
        "holidays":  _INDIA_HOLIDAYS,
        "watchlist": [
            "RELIANCE.BO", "TCS.BO", "INFY.BO", "HDFCBANK.BO", "ICICIBANK.BO",
            "HINDUNILVR.BO", "SBIN.BO", "BHARTIARTL.BO", "WIPRO.BO", "BAJFINANCE.BO",
            "KOTAKBANK.BO", "LT.BO", "AXISBANK.BO", "ASIANPAINT.BO", "MARUTI.BO",
            "SUNPHARMA.BO", "TITAN.BO", "ULTRACEMCO.BO", "NESTLEIND.BO", "POWERGRID.BO",
        ],
        "etf_examples": "NIFTYBEES.BO  BANKBEES.BO  JUNIORBEES.BO  GOLDBEES.BO",
    },
    "4": {
        "key":       "nse",
        "name":      "NSE (National Stock Exchange, India)",
        "suffix":    ".NS",
        "currency":  "INR",
        "tz":        _IST,
        "open":      time(9, 15),
        "close":     time(15, 30),
        "open_label":  "9:15 AM IST",
        "close_label": "3:30 PM IST",
        "holidays":  _INDIA_HOLIDAYS,
        "watchlist": [
            "RELIANCE.NS", "TCS.NS", "INFY.NS", "HDFCBANK.NS", "ICICIBANK.NS",
            "HINDUNILVR.NS", "SBIN.NS", "BHARTIARTL.NS", "WIPRO.NS", "BAJFINANCE.NS",
            "KOTAKBANK.NS", "LT.NS", "AXISBANK.NS", "ASIANPAINT.NS", "MARUTI.NS",
            "SUNPHARMA.NS", "TITAN.NS", "ULTRACEMCO.NS", "NESTLEIND.NS", "POWERGRID.NS",
        ],
        "etf_examples": "NIFTYBEES.NS  BANKBEES.NS  JUNIORBEES.NS  GOLDBEES.NS",
    },
}


# ── Exchange selection ────────────────────────────────────────────────────────

def select_exchange() -> dict:
    """Prompt the user to choose an exchange and return its config dict."""
    console.print("\n[bold cyan]Select Exchange[/bold cyan]")
    for key, ex in EXCHANGES.items():
        console.print(f"  [bold white]{key}[/bold white]  {ex['name']}")
    console.print()

    while True:
        choice = console.input(
            "[bold]Enter exchange number[/bold] ([dim]1–4, default 1[/dim]): "
        ).strip()
        if not choice:
            choice = "1"
        if choice in EXCHANGES:
            exchange = EXCHANGES[choice]
            console.print(f"\n  [green]✓[/green] Selected: [bold]{exchange['name']}[/bold]\n")
            return exchange
        console.print("  [red]Invalid choice — enter 1, 2, 3, or 4.[/red]")


# ── Market status ─────────────────────────────────────────────────────────────

def get_market_status(exchange: dict) -> tuple[str, str, str]:
    """
    Return (status, label, style) for the current market state of the given exchange.

    status values: 'open' | 'pre_market' | 'after_hours' | 'weekend' | 'holiday'
    label  : human-readable description shown in the banner
    style  : Rich colour string
    """
    now   = datetime.now(exchange["tz"])
    today = now.date()
    now_t = now.time()
    name  = exchange["name"]

    if today in exchange["holidays"]:
        return "holiday", f"{name} Closed — Market Holiday  (data reflects last close)", "red"

    weekday = today.weekday()  # 0=Mon … 6=Sun
    if weekday >= 5:
        days_until_open = 7 - weekday
        next_open = today.replace(day=today.day + days_until_open)
        return (
            "weekend",
            f"{name} Closed — Weekend  (reopens Monday {next_open.strftime('%b %d')} at {exchange['open_label']})",
            "red",
        )

    if now_t < exchange["open"]:
        opens_in = datetime.combine(today, exchange["open"], tzinfo=exchange["tz"]) - now
        mins = int(opens_in.total_seconds() // 60)
        return (
            "pre_market",
            f"Pre-Market  —  {name} opens in {mins} min ({exchange['open_label']})  |  Prices reflect yesterday's close",
            "yellow",
        )

    if now_t >= exchange["close"]:
        return (
            "after_hours",
            f"After Hours  —  {name} closed at {exchange['close_label']}  |  Prices reflect today's close",
            "yellow",
        )

    closes_in = datetime.combine(today, exchange["close"], tzinfo=exchange["tz"]) - now
    mins = int(closes_in.total_seconds() // 60)
    h, m = divmod(mins, 60)
    time_left = f"{h}h {m}m" if h else f"{m}m"
    return (
        "open",
        f"Market Open  —  {name} closes in {time_left} ({exchange['close_label']})",
        "green",
    )


def print_market_status(exchange: dict):
    """Print a compact market-status banner below the header."""
    status, label, style = get_market_status(exchange)

    icon = {
        "open":        "● LIVE",
        "pre_market":  "◐ PRE-MARKET",
        "after_hours": "◑ AFTER HOURS",
        "weekend":     "○ CLOSED",
        "holiday":     "○ CLOSED",
    }[status]

    console.print(
        Panel(
            f"[{style}]{icon}[/{style}]  [white]{label}[/white]",
            border_style=style,
            expand=False,
            padding=(0, 2),
        )
    )


# ── Data fetching ─────────────────────────────────────────────────────────────

def fetch_ticker_data(ticker: str, is_etf: bool = False) -> dict | None:
    """
    Fetch all required fields for a single ticker via yfinance.
    Returns a dict of data, or None if the ticker is invalid / data is missing.
    is_etf=True suppresses P/E fetching (ETFs don't carry a meaningful P/E).
    """
    try:
        t = yf.Ticker(ticker)
        info = t.info

        # Require at minimum a current price to consider the ticker valid
        price = info.get("currentPrice") or info.get("regularMarketPrice")
        if not price:
            console.print(f"  [yellow]⚠ {ticker}: no price data — skipping[/yellow]")
            return None

        # Previous close for % change calculation
        prev_close = info.get("previousClose") or info.get("regularMarketPreviousClose")
        pct_change = ((price - prev_close) / prev_close * 100) if prev_close else None

        # Volume: today vs 20-day average
        volume = info.get("volume") or info.get("regularMarketVolume")
        avg_volume = info.get("averageVolume") or info.get("averageDailyVolume10Day")
        volume_ratio = (volume / avg_volume) if (volume and avg_volume and avg_volume > 0) else None

        # 52-week range
        week52_high = info.get("fiftyTwoWeekHigh")
        week52_low = info.get("fiftyTwoWeekLow")

        # Distance from 52w high/low as percentage
        pct_from_high = ((week52_high - price) / week52_high * 100) if week52_high else None
        pct_from_low = ((price - week52_low) / week52_low * 100) if week52_low else None

        # P/E ratio — not meaningful for ETFs, skip intentionally
        pe_ratio = None if is_etf else (info.get("trailingPE") or info.get("forwardPE"))

        return {
            "ticker": ticker,
            "is_etf": is_etf,
            "price": price,
            "pct_change": pct_change,
            "volume": volume,
            "avg_volume": avg_volume,
            "volume_ratio": volume_ratio,
            "pe_ratio": pe_ratio,
            "week52_high": week52_high,
            "week52_low": week52_low,
            "pct_from_high": pct_from_high,
            "pct_from_low": pct_from_low,
        }

    except Exception as e:
        console.print(f"  [yellow]⚠ {ticker}: fetch error ({e}) — skipping[/yellow]")
        return None


def scan_tickers(tickers: list[str], etf_set: set[str]) -> list[dict]:
    """
    Fetch data for all tickers with a progress bar.
    etf_set contains uppercase ticker symbols that should be treated as ETFs.
    Returns a list of result dicts (failed tickers are omitted).
    """
    results = []
    with Progress(
        SpinnerColumn(),
        TextColumn("[bold cyan]Fetching[/bold cyan] {task.description}"),
        BarColumn(bar_width=40),
        TextColumn("[progress.percentage]{task.percentage:>3.0f}%"),
        console=console,
        transient=True,
    ) as progress:
        task = progress.add_task("market data…", total=len(tickers))
        for ticker in tickers:
            progress.update(task, description=f"[white]{ticker}[/white]")
            data = fetch_ticker_data(ticker, is_etf=(ticker in etf_set))
            if data:
                results.append(data)
            progress.advance(task)

    return results


# ── Signal evaluation ─────────────────────────────────────────────────────────

def generate_suggestion(alerts: list[str], row: dict) -> tuple[str, str]:
    """
    Interpret the combination of active alerts and return a (suggestion, style) tuple.
    Style is a Rich colour string used to highlight the suggestion in the table.
    ETFs skip P/E-based signals since P/E is not meaningful for funds.
    """
    has = lambda keyword: any(keyword in a for a in alerts)

    is_etf    = row.get("is_etf", False)
    low_pe    = has("P/E") and not is_etf   # never true for ETFs
    vol_spike = has("VOL")
    near_high = has("52W-HIGH")
    near_low  = has("52W-LOW")
    move_up   = has("MOVE UP")
    move_down = has("MOVE DOWN")

    if not alerts:
        return "—", "dim"

    # Strongest combos first
    if low_pe and near_low:
        return "Value opportunity — research further", "bold green"
    if vol_spike and move_up and near_high:
        return "Momentum breakout — watch for continuation", "bold green"
    if vol_spike and move_up:
        return "Unusual buying interest", "green"
    if vol_spike and move_down and near_low:
        return "Heavy selling near 52W low — high risk", "bold red"
    if vol_spike and move_down:
        return "Unusual selling — investigate catalyst", "red"
    if near_low and move_down:
        return "Selling pressure — use caution", "red"
    if near_high and move_up:
        return "Testing resistance — monitor closely", "yellow"
    if near_high:
        return "Near 52W high — watch for breakout or reversal", "yellow"
    if near_low:
        return "Oversold territory — watch for reversal", "yellow"
    if low_pe:
        return "Potentially undervalued", "cyan"
    if move_up:
        return "Strong positive move today", "green"
    if move_down:
        return "Notable decline today", "red"

    return "Flagged — review signals", "dim"


def evaluate_alerts(row: dict) -> list[str]:
    """
    Apply all filter thresholds to a data row and return a list of alert strings.
    """
    alerts = []
    th = THRESHOLDS

    # P/E below threshold → potential value
    if row["pe_ratio"] and row["pe_ratio"] < th["pe_max"]:
        alerts.append(f"P/E<{th['pe_max']}")

    # Volume spike
    if row["volume_ratio"] and row["volume_ratio"] >= th["volume_spike_x"]:
        alerts.append(f"VOL×{row['volume_ratio']:.1f}")

    # Near 52-week high
    if row["pct_from_high"] is not None and row["pct_from_high"] <= th["week52_pct"]:
        alerts.append(f"NEAR 52W-HIGH")

    # Near 52-week low
    if row["pct_from_low"] is not None and row["pct_from_low"] <= th["week52_pct"]:
        alerts.append(f"NEAR 52W-LOW")

    # Big price move today
    if row["pct_change"] is not None and abs(row["pct_change"]) >= th["price_change_pct"]:
        direction = "UP" if row["pct_change"] > 0 else "DOWN"
        alerts.append(f"MOVE {direction} {abs(row['pct_change']):.1f}%")

    return alerts


# ── Formatting helpers ────────────────────────────────────────────────────────

def fmt_pct(value: float | None, decimals: int = 2) -> Text:
    """Return a colour-coded Rich Text for a percentage value."""
    if value is None:
        return Text("N/A", style="dim")
    colour = "green" if value > 0 else ("red" if value < 0 else "white")
    sign = "+" if value > 0 else ""
    return Text(f"{sign}{value:.{decimals}f}%", style=colour)


def fmt_volume_ratio(ratio: float | None) -> Text:
    """Return a colour-coded Rich Text for the volume spike ratio."""
    if ratio is None:
        return Text("N/A", style="dim")
    if ratio >= THRESHOLDS["volume_spike_x"]:
        return Text(f"{ratio:.2f}×", style="bold yellow")
    return Text(f"{ratio:.2f}×", style="dim")


def fmt_pe(pe: float | None) -> Text:
    """Return a colour-coded Rich Text for P/E ratio."""
    if pe is None:
        return Text("N/A", style="dim")
    if pe < THRESHOLDS["pe_max"]:
        return Text(f"{pe:.1f}", style="green")
    if pe > 35:
        return Text(f"{pe:.1f}", style="red")
    return Text(f"{pe:.1f}", style="white")


def fmt_week52_position(row: dict) -> Text:
    """
    Summarise 52-week position as e.g. '▲ 3.2% from high' or '▼ 8.1% from low'.
    Highlight if near extremes.
    """
    th = THRESHOLDS["week52_pct"]
    if row["pct_from_high"] is not None and row["pct_from_high"] <= th:
        return Text(f"▲ {row['pct_from_high']:.1f}% fr high", style="bold green")
    if row["pct_from_low"] is not None and row["pct_from_low"] <= th:
        return Text(f"▼ {row['pct_from_low']:.1f}% fr low", style="bold red")
    # Normal range — show both distances concisely
    hi = f"{row['pct_from_high']:.1f}%" if row["pct_from_high"] is not None else "?"
    lo = f"{row['pct_from_low']:.1f}%" if row["pct_from_low"] is not None else "?"
    return Text(f"H-{hi} / L+{lo}", style="dim")


def fmt_alerts(alerts: list[str]) -> Text:
    """Render the alerts list as a single Rich Text cell."""
    if not alerts:
        return Text("—", style="dim")
    # Colour individual alerts
    t = Text()
    for i, alert in enumerate(alerts):
        if "HIGH" in alert or "UP" in alert:
            t.append(alert, style="bold green")
        elif "LOW" in alert or "DOWN" in alert:
            t.append(alert, style="bold red")
        elif "VOL" in alert:
            t.append(alert, style="bold yellow")
        elif "P/E" in alert:
            t.append(alert, style="cyan")
        else:
            t.append(alert)
        if i < len(alerts) - 1:
            t.append("  ")
    return t


# ── Display ───────────────────────────────────────────────────────────────────

def build_table(results: list[dict], currency: str) -> tuple[Table, int, list]:
    """
    Build the Rich results table. Returns (table, alert_count, notable).
    """
    table = Table(
        title=None,
        box=box.ROUNDED,
        header_style="bold magenta",
        show_lines=True,
        expand=False,
    )

    table.add_column("Ticker",                  style="bold white",  justify="left",  min_width=14)
    table.add_column(f"Price ({currency})",     style="white",       justify="right", min_width=13)
    table.add_column("% Change",                justify="right",     min_width=9)
    table.add_column("Vol Spike",               justify="right",     min_width=9)
    table.add_column("P/E",                     justify="right",     min_width=6)
    table.add_column("52W Position",            justify="left",      min_width=18)
    table.add_column("Alerts",                  justify="left",      min_width=20)
    table.add_column("Suggestion",              justify="left",      min_width=38)

    alert_count = 0
    notable: list[tuple[str, str, str]] = []  # (ticker, suggestion, style) for summary panel

    for row in sorted(results, key=lambda r: r["ticker"]):
        alerts = evaluate_alerts(row)
        suggestion, sug_style = generate_suggestion(alerts, row)

        if alerts:
            alert_count += 1
            if suggestion != "—":
                notable.append((row["ticker"], suggestion, sug_style))

        price_str = f"{row['price']:.2f}" if row["price"] else "N/A"

        # Badge ETF tickers with a dim label so they stand out from equities
        ticker_cell = Text()
        ticker_cell.append(row["ticker"], style="bold white")
        if row.get("is_etf"):
            ticker_cell.append(" [ETF]", style="dim cyan")

        # P/E column shows a distinct label for ETFs instead of N/A
        pe_cell = Text("fund", style="dim cyan") if row.get("is_etf") else fmt_pe(row["pe_ratio"])

        table.add_row(
            ticker_cell,
            price_str,
            fmt_pct(row["pct_change"]),
            fmt_volume_ratio(row["volume_ratio"]),
            pe_cell,
            fmt_week52_position(row),
            fmt_alerts(alerts),
            Text(suggestion, style=sug_style),
        )

    return table, alert_count, notable


def print_header(exchange: dict):
    """Print the branded application header."""
    ts = datetime.now().strftime("%A, %B %d %Y  %H:%M:%S")
    console.print(
        Panel(
            f"[bold white]STOCK SCREENER — {exchange['name'].upper()}[/bold white]\n"
            f"[dim]{ts}[/dim]",
            title="[bold green]Stonks.ca[/bold green]",
            subtitle="[dim]Powered by yfinance[/dim]",
            border_style="green",
            expand=False,
        )
    )


def print_notable_signals(notable: list[tuple[str, str, str]]):
    """Print a Notable Signals panel summarising the most actionable tickers."""
    if not notable:
        return
    lines = Text()
    for ticker, suggestion, style in notable:
        lines.append(f"  {ticker:<14}", style="bold white")
        lines.append(f"{suggestion}\n", style=style)
    console.print(
        Panel(
            lines,
            title="[bold yellow]Notable Signals[/bold yellow]",
            subtitle="[dim]Review before acting — not financial advice[/dim]",
            border_style="yellow",
            expand=False,
        )
    )


def print_summary(total: int, alert_count: int, csv_path: str):
    """Print the scan summary panel below the table."""
    console.print(
        Panel(
            f"[white]Tickers scanned:[/white]  [bold cyan]{total}[/bold cyan]\n"
            f"[white]Alerts triggered:[/white] [bold yellow]{alert_count}[/bold yellow]\n"
            f"[white]Report saved to:[/white]  [bold green]{csv_path}[/bold green]",
            title="[bold]Scan Summary[/bold]",
            border_style="blue",
            expand=False,
        )
    )


# ── CSV export ────────────────────────────────────────────────────────────────

def export_csv(results: list[dict], path: str):
    """Write scan results (including evaluated alerts) to a CSV file."""
    fieldnames = [
        "ticker", "type", "price", "pct_change", "volume", "avg_volume",
        "volume_ratio", "pe_ratio", "week52_high", "week52_low",
        "pct_from_high", "pct_from_low", "alerts", "suggestion",
    ]
    with open(path, "w", newline="") as f:
        writer = csv.DictWriter(f, fieldnames=fieldnames)
        writer.writeheader()
        for row in sorted(results, key=lambda r: r["ticker"]):
            alerts = evaluate_alerts(row)
            suggestion, _ = generate_suggestion(alerts, row)
            writer.writerow({
                "ticker":        row["ticker"],
                "type":          "ETF" if row.get("is_etf") else "Stock",
                "price":         f"{row['price']:.2f}" if row["price"] else "",
                "pct_change":    f"{row['pct_change']:.2f}" if row["pct_change"] is not None else "",
                "volume":        row["volume"] or "",
                "avg_volume":    row["avg_volume"] or "",
                "volume_ratio":  f"{row['volume_ratio']:.2f}" if row["volume_ratio"] is not None else "",
                "pe_ratio":      f"{row['pe_ratio']:.2f}" if row["pe_ratio"] is not None else "",
                "week52_high":   f"{row['week52_high']:.2f}" if row["week52_high"] else "",
                "week52_low":    f"{row['week52_low']:.2f}" if row["week52_low"] else "",
                "pct_from_high": f"{row['pct_from_high']:.2f}" if row["pct_from_high"] is not None else "",
                "pct_from_low":  f"{row['pct_from_low']:.2f}" if row["pct_from_low"] is not None else "",
                "alerts":        " | ".join(alerts),
                "suggestion":    suggestion if suggestion != "—" else "",
            })


# ── Main loop ─────────────────────────────────────────────────────────────────

def _parse_tickers(raw: str, label: str, exchange: dict) -> list[str]:
    """
    Parse a comma-separated ticker string.
    For exchanges that require a suffix, warn if it's missing.
    For NYSE/NASDAQ (no suffix), warn if a foreign suffix is present.
    """
    suffix = exchange["suffix"]
    tickers = [t.strip().upper() for t in raw.split(",") if t.strip()]
    for t in tickers:
        if suffix:
            # Suffix-based exchanges (TSX, BSE, NSE)
            if not t.endswith(suffix):
                console.print(
                    f"  [yellow]⚠ '{t}' does not end with {suffix} — "
                    f"{exchange['name']} tickers require the {suffix} suffix ({label})[/yellow]"
                )
        else:
            # NYSE/NASDAQ: warn if ticker carries any known exchange suffix
            for known_suffix in (".TO", ".NS", ".BO", ".L", ".AX", ".DE"):
                if t.endswith(known_suffix):
                    console.print(
                        f"  [yellow]⚠ '{t}' has suffix {known_suffix} — "
                        f"NYSE/NASDAQ tickers have no suffix ({label})[/yellow]"
                    )
                    break
    return tickers


def get_ticker_list(exchange: dict) -> tuple[list[str], set[str]]:
    """
    Prompt the user for optional custom stock tickers and ETF tickers.
    Returns (all_tickers, etf_set) where etf_set is the subset that are ETFs.
    """
    suffix = exchange["suffix"]
    suffix_hint = f" with {suffix} suffix" if suffix else " (no suffix needed)"

    console.print("\n[bold cyan]Stock Universe[/bold cyan]")
    console.print(f"  Default watchlist: [dim]{', '.join(exchange['watchlist'])}[/dim]\n")

    # ── Custom stocks ──────────────────────────────────────────────────────
    raw_stocks = console.input(
        f"[bold]Add custom stock tickers?[/bold] (comma-separated{suffix_hint}, or [dim]Enter[/dim] to skip): "
    ).strip()
    custom_stocks = _parse_tickers(raw_stocks, "stock", exchange) if raw_stocks else []

    # ── ETFs ───────────────────────────────────────────────────────────────
    console.print(
        f"\n  [dim]Common ETFs: {exchange['etf_examples']}[/dim]"
    )
    raw_etfs = console.input(
        f"[bold]Add ETF tickers?[/bold]        (comma-separated{suffix_hint}, or [dim]Enter[/dim] to skip): "
    ).strip()
    custom_etfs = _parse_tickers(raw_etfs, "ETF", exchange) if raw_etfs else []

    # Merge everything, deduplicate, preserve order
    all_tickers = list(dict.fromkeys(exchange["watchlist"] + custom_stocks + custom_etfs))
    etf_set = set(custom_etfs)

    stock_count = len(all_tickers) - len(etf_set)
    etf_count   = len(etf_set)
    console.print(
        f"\n  [green]✓[/green] Scanning [bold]{len(all_tickers)}[/bold] ticker(s) "
        f"([white]{stock_count}[/white] stocks + [cyan]{etf_count}[/cyan] ETFs).\n"
    )
    return all_tickers, etf_set


def run_scan(tickers: list[str], etf_set: set[str], exchange: dict):
    """Execute a full scan: fetch → display → export."""
    results = scan_tickers(tickers, etf_set)

    if not results:
        console.print("[red]No data retrieved. Check your connection or ticker symbols.[/red]")
        return

    table, alert_count, notable = build_table(results, exchange["currency"])
    console.print(table)
    print_notable_signals(notable)

    # CSV export with timestamped filename — saved to Desktop
    ts = datetime.now().strftime("%Y%m%d_%H%M%S")
    csv_path = os.path.join(
        os.path.expanduser("~/Desktop"),
        f"{exchange['key']}_screener_report_{ts}.csv",
    )
    export_csv(results, csv_path)

    print_summary(len(results), alert_count, csv_path)


def main():
    console.clear()

    exchange = select_exchange()

    print_header(exchange)
    print_market_status(exchange)

    tickers, etf_set = get_ticker_list(exchange)

    while True:
        run_scan(tickers, etf_set, exchange)

        console.print()
        choice = console.input(
            "[bold]Run again?[/bold] ([green]y[/green] to rescan / [red]q[/red] to quit): "
        ).strip().lower()

        if choice == "y":
            console.print()
            print_market_status(exchange)
            console.print("[dim]Re-fetching fresh data…[/dim]\n")
            continue
        else:
            console.print(
                Panel(
                    "[bold green]Thanks for using Stonks.ca![/bold green]\n"
                    "[dim]Good luck out there, trader.[/dim]",
                    border_style="green",
                    expand=False,
                )
            )
            break


if __name__ == "__main__":
    main()
