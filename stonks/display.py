"""
Rich terminal display: formatting helpers, table builder, and panel printers.
"""

from datetime import datetime

from rich import box
from rich.console import Console
from rich.panel import Panel
from rich.table import Table
from rich.text import Text

from .signals import THRESHOLDS, evaluate_alerts, generate_suggestion

console = Console()

# ── Formatting helpers ────────────────────────────────────────────────────────

def fmt_pct(value: float | None, decimals: int = 2) -> Text:
    if value is None:
        return Text("N/A", style="dim")
    colour = "green" if value > 0 else ("red" if value < 0 else "white")
    sign = "+" if value > 0 else ""
    return Text(f"{sign}{value:.{decimals}f}%", style=colour)


def fmt_volume_ratio(ratio: float | None) -> Text:
    if ratio is None:
        return Text("N/A", style="dim")
    if ratio >= THRESHOLDS["volume_spike_x"]:
        return Text(f"{ratio:.2f}×", style="bold yellow")
    return Text(f"{ratio:.2f}×", style="dim")


def fmt_pe(pe: float | None) -> Text:
    if pe is None:
        return Text("N/A", style="dim")
    if pe < THRESHOLDS["pe_max"]:
        return Text(f"{pe:.1f}", style="green")
    if pe > 35:
        return Text(f"{pe:.1f}", style="red")
    return Text(f"{pe:.1f}", style="white")


def fmt_week52_position(row: dict) -> Text:
    th = THRESHOLDS["week52_pct"]
    if row.get("pct_from_high") is not None and row["pct_from_high"] <= th:
        return Text(f"▲ {row['pct_from_high']:.1f}% fr high", style="bold green")
    if row.get("pct_from_low") is not None and row["pct_from_low"] <= th:
        return Text(f"▼ {row['pct_from_low']:.1f}% fr low", style="bold red")
    hi = f"{row['pct_from_high']:.1f}%" if row.get("pct_from_high") is not None else "?"
    lo = f"{row['pct_from_low']:.1f}%"  if row.get("pct_from_low")  is not None else "?"
    return Text(f"H-{hi} / L+{lo}", style="dim")


def fmt_rsi(rsi: float | None) -> Text:
    if rsi is None:
        return Text("N/A", style="dim")
    if rsi < THRESHOLDS["rsi_oversold"]:
        return Text(f"{rsi:.0f}", style="bold green")
    if rsi > THRESHOLDS["rsi_overbought"]:
        return Text(f"{rsi:.0f}", style="bold red")
    return Text(f"{rsi:.0f}", style="white")


def fmt_ma_trend(row: dict) -> Text:
    price = row.get("price")
    ma50  = row.get("ma50")
    ma200 = row.get("ma200")
    if not (price and ma50 and ma200):
        return Text("N/A", style="dim")
    if price > ma50 > ma200:
        return Text("▲ Golden", style="bold green")
    if price < ma50 < ma200:
        return Text("▼ Death", style="bold red")
    if price > ma200:
        return Text("Above 200d", style="green")
    return Text("Below 200d", style="red")


def fmt_market_cap(cap: int | None) -> Text:
    if cap is None:
        return Text("N/A", style="dim")
    if cap >= 1_000_000_000_000:
        return Text(f"{cap / 1e12:.1f}T", style="white")
    if cap >= 1_000_000_000:
        return Text(f"{cap / 1e9:.1f}B", style="white")
    if cap >= 1_000_000:
        return Text(f"{cap / 1e6:.0f}M", style="dim white")
    return Text(f"{cap:,}", style="dim")


def fmt_alerts(alerts: list[str]) -> Text:
    if not alerts:
        return Text("—", style="dim")
    t = Text()
    for i, alert in enumerate(alerts):
        if "HIGH" in alert or "UP" in alert or "GOLDEN" in alert or "OVERSOLD" in alert:
            t.append(alert, style="bold green")
        elif "LOW" in alert or "DOWN" in alert or "DEATH" in alert or "OVERBOUGHT" in alert:
            t.append(alert, style="bold red")
        elif "VOL" in alert:
            t.append(alert, style="bold yellow")
        elif "P/E" in alert or "RSI" in alert:
            t.append(alert, style="cyan")
        else:
            t.append(alert)
        if i < len(alerts) - 1:
            t.append("  ")
    return t


# ── Table builder ─────────────────────────────────────────────────────────────

SORT_KEYS = {
    "ticker":    lambda r: r["ticker"],
    "pct_change": lambda r: (r["pct_change"] is None, -(r["pct_change"] or 0)),
    "volume":    lambda r: (r["volume_ratio"] is None, -(r["volume_ratio"] or 0)),
    "rsi":       lambda r: (r["rsi"] is None, r["rsi"] or 50),
    "pe":        lambda r: (r["pe_ratio"] is None, r["pe_ratio"] or 9999),
}


def build_table(
    results: list[dict],
    currency: str,
    sort_by: str = "ticker",
    flagged_only: bool = False,
) -> tuple[Table, int, list]:
    """
    Build the Rich results table.
    Returns (table, alert_count, notable_list).
    notable_list = [(ticker, suggestion, style), ...]
    """
    table = Table(
        title=None,
        box=box.ROUNDED,
        header_style="bold magenta",
        show_lines=True,
        expand=False,
    )

    table.add_column("Ticker",             style="bold white",  justify="left",  min_width=14)
    table.add_column(f"Price ({currency})", style="white",      justify="right", min_width=10)
    table.add_column("% Change",           justify="right",     min_width=9)
    table.add_column("Vol Spike",          justify="right",     min_width=9)
    table.add_column("P/E",                justify="right",     min_width=6)
    table.add_column("52W Position",       justify="left",      min_width=18)
    table.add_column("RSI",                justify="right",     min_width=5)
    table.add_column("MA Trend",           justify="left",      min_width=11)
    table.add_column("Mkt Cap",            justify="right",     min_width=8)
    table.add_column("Sector",             justify="left",      min_width=14)
    table.add_column("Alerts",             justify="left",      min_width=24)
    table.add_column("Suggestion",         justify="left",      min_width=38)

    sort_fn = SORT_KEYS.get(sort_by, SORT_KEYS["ticker"])
    sorted_results = sorted(results, key=sort_fn)

    alert_count = 0
    notable: list[tuple[str, str, str]] = []

    for row in sorted_results:
        alerts = evaluate_alerts(row)
        suggestion, sug_style = generate_suggestion(alerts, row)

        if flagged_only and not alerts:
            continue

        if alerts:
            alert_count += 1
            if suggestion != "—":
                notable.append((row["ticker"], suggestion, sug_style))

        price_str = f"{row['price']:.2f}" if row.get("price") else "N/A"

        ticker_cell = Text()
        ticker_cell.append(row["ticker"], style="bold white")
        if row.get("is_etf"):
            ticker_cell.append(" [ETF]", style="dim cyan")

        pe_cell = Text("fund", style="dim cyan") if row.get("is_etf") else fmt_pe(row.get("pe_ratio"))

        table.add_row(
            ticker_cell,
            price_str,
            fmt_pct(row.get("pct_change")),
            fmt_volume_ratio(row.get("volume_ratio")),
            pe_cell,
            fmt_week52_position(row),
            fmt_rsi(row.get("rsi")),
            fmt_ma_trend(row),
            fmt_market_cap(row.get("market_cap")),
            row.get("sector") or "—",
            fmt_alerts(alerts),
            Text(suggestion, style=sug_style),
        )

    return table, alert_count, notable


# ── Panels ────────────────────────────────────────────────────────────────────

def print_header(exchange: dict):
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


def print_summary(total: int, alert_count: int, csv_path: str, json_path: str):
    console.print(
        Panel(
            f"[white]Tickers scanned:[/white]  [bold cyan]{total}[/bold cyan]\n"
            f"[white]Alerts triggered:[/white] [bold yellow]{alert_count}[/bold yellow]\n"
            f"[white]CSV saved to:[/white]     [bold green]{csv_path}[/bold green]\n"
            f"[white]JSON saved to:[/white]    [bold green]{json_path}[/bold green]",
            title="[bold]Scan Summary[/bold]",
            border_style="blue",
            expand=False,
        )
    )
