"""
Exchange configurations, market-status helpers, and exchange selection.
"""

from datetime import date, datetime, time, timedelta
from zoneinfo import ZoneInfo

from rich.console import Console
from rich.panel import Panel

console = Console()

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
    date(2025, 1, 1),
    date(2025, 2, 17),
    date(2025, 4, 18),
    date(2025, 5, 19),
    date(2025, 7, 1),
    date(2025, 8, 4),
    date(2025, 9, 1),
    date(2025, 10, 13),
    date(2025, 12, 25),
    date(2025, 12, 26),
    date(2026, 1, 1),
    date(2026, 2, 16),
    date(2026, 4, 3),
    date(2026, 5, 18),
    date(2026, 7, 1),
    date(2026, 8, 3),
    date(2026, 9, 7),
    date(2026, 10, 12),
    date(2026, 12, 25),
    date(2026, 12, 28),
}

# BSE / NSE shared holidays 2025–2026
_INDIA_HOLIDAYS = {
    date(2025, 1, 26),
    date(2025, 2, 19),
    date(2025, 3, 14),
    date(2025, 4, 14),
    date(2025, 4, 18),
    date(2025, 5, 1),
    date(2025, 8, 15),
    date(2025, 10, 2),
    date(2025, 10, 24),
    date(2025, 10, 25),
    date(2025, 11, 5),
    date(2025, 12, 25),
    date(2026, 1, 26),
    date(2026, 3, 3),
    date(2026, 4, 3),
    date(2026, 4, 14),
    date(2026, 5, 1),
    date(2026, 8, 15),
    date(2026, 10, 2),
    date(2026, 10, 17),
    date(2026, 11, 25),
    date(2026, 12, 25),
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


def get_market_status(exchange: dict) -> tuple[str, str, str]:
    """
    Return (status, label, style) for the current market state.
    status: 'open' | 'pre_market' | 'after_hours' | 'weekend' | 'holiday'
    """
    now   = datetime.now(exchange["tz"])
    today = now.date()
    now_t = now.time()
    name  = exchange["name"]

    if today in exchange["holidays"]:
        return "holiday", f"{name} Closed — Market Holiday  (data reflects last close)", "red"

    weekday = today.weekday()
    if weekday >= 5:
        days_until_open = 7 - weekday
        next_open = today + timedelta(days=days_until_open)
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
    """Print a compact market-status banner."""
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
