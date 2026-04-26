"""
Stonks.ca — Entry Point
Usage:
  python main.py          # prompt for CLI or Web
  python main.py --cli    # terminal screener
  python main.py --web    # browser dashboard (localhost:5000)
"""

import sys
import importlib.util

# ── Dependency check ──────────────────────────────────────────────────────────
_REQUIRED = ["yfinance", "rich", "pandas", "flask"]
_MISSING  = [pkg for pkg in _REQUIRED if importlib.util.find_spec(pkg) is None]
if _MISSING:
    print(f"Missing dependencies: {', '.join(_MISSING)}")
    print("Run:  pip install yfinance rich pandas flask")
    sys.exit(1)

import time
from datetime import datetime

from rich.console import Console
from rich.panel import Panel

from stonks.exchanges import EXCHANGES, select_exchange, print_market_status
from stonks.fetcher   import scan_tickers
from stonks.display   import (
    build_table, print_header, print_notable_signals, print_summary, console as _c
)
from stonks.export    import export_both
from stonks.watchlist import load_watchlist, save_watchlist

console = Console()


# ── CLI helpers ───────────────────────────────────────────────────────────────

def _parse_tickers(raw: str, label: str, exchange: dict) -> list[str]:
    suffix  = exchange["suffix"]
    tickers = [t.strip().upper() for t in raw.split(",") if t.strip()]
    for t in tickers:
        if suffix:
            if not t.endswith(suffix):
                console.print(
                    f"  [yellow]⚠ '{t}' does not end with {suffix} — "
                    f"{exchange['name']} tickers require the {suffix} suffix ({label})[/yellow]"
                )
        else:
            for known in (".TO", ".NS", ".BO", ".L", ".AX", ".DE"):
                if t.endswith(known):
                    console.print(
                        f"  [yellow]⚠ '{t}' has suffix {known} — "
                        f"NYSE/NASDAQ tickers have no suffix ({label})[/yellow]"
                    )
                    break
    return tickers


def get_ticker_list(exchange: dict) -> tuple[list[str], set[str]]:
    suffix      = exchange["suffix"]
    suffix_hint = f" with {suffix} suffix" if suffix else " (no suffix needed)"

    console.print("\n[bold cyan]Stock Universe[/bold cyan]")

    # Offer to load saved watchlist
    saved = load_watchlist(exchange["key"])
    if saved:
        saved_tickers, saved_etfs = saved
        console.print(
            f"  [dim]Saved watchlist ({len(saved_tickers)} tickers): "
            f"{', '.join(saved_tickers[:6])}{'…' if len(saved_tickers) > 6 else ''}[/dim]"
        )
        use_saved = console.input(
            "[bold]Load saved watchlist?[/bold] ([green]y[/green]/[dim]n[/dim], default y): "
        ).strip().lower()
        if use_saved != "n":
            console.print(f"  [green]✓[/green] Loaded saved watchlist.\n")
            return saved_tickers, saved_etfs

    console.print(f"  Default watchlist: [dim]{', '.join(exchange['watchlist'])}[/dim]\n")

    raw_stocks = console.input(
        f"[bold]Add custom stock tickers?[/bold] (comma-separated{suffix_hint}, or [dim]Enter[/dim] to skip): "
    ).strip()
    custom_stocks = _parse_tickers(raw_stocks, "stock", exchange) if raw_stocks else []

    console.print(f"\n  [dim]Common ETFs: {exchange['etf_examples']}[/dim]")
    raw_etfs = console.input(
        f"[bold]Add ETF tickers?[/bold]        (comma-separated{suffix_hint}, or [dim]Enter[/dim] to skip): "
    ).strip()
    custom_etfs = _parse_tickers(raw_etfs, "ETF", exchange) if raw_etfs else []

    all_tickers = list(dict.fromkeys(exchange["watchlist"] + custom_stocks + custom_etfs))
    etf_set     = set(custom_etfs)

    stock_count = len(all_tickers) - len(etf_set)
    etf_count   = len(etf_set)
    console.print(
        f"\n  [green]✓[/green] Scanning [bold]{len(all_tickers)}[/bold] ticker(s) "
        f"([white]{stock_count}[/white] stocks + [cyan]{etf_count}[/cyan] ETFs).\n"
    )

    # Offer to save
    if custom_stocks or custom_etfs:
        save_q = console.input(
            "[bold]Save this watchlist for next time?[/bold] ([green]y[/green]/[dim]n[/dim]): "
        ).strip().lower()
        if save_q == "y":
            save_watchlist(exchange["key"], all_tickers, etf_set)
            console.print("  [green]✓[/green] Watchlist saved.\n")

    return all_tickers, etf_set


def get_display_options() -> tuple[str, bool]:
    """Ask sort order and flagged-only filter. Returns (sort_by, flagged_only)."""
    console.print(
        "[dim]Sort by:[/dim] [white]1[/white] Score  [white]2[/white] Ticker  "
        "[white]3[/white] % Change  [white]4[/white] Volume  [white]5[/white] RSI  "
        "[white]6[/white] P/E"
    )
    sort_choice = console.input(
        "[bold]Sort?[/bold] ([dim]1–6, default 1 (Score)[/dim]): "
    ).strip()
    sort_map = {
        "1": "score",
        "2": "ticker",
        "3": "pct_change",
        "4": "volume",
        "5": "rsi",
        "6": "pe",
    }
    sort_by = sort_map.get(sort_choice, "score")

    flagged_raw  = console.input(
        "[bold]Show flagged tickers only?[/bold] ([dim]y/n, default n[/dim]): "
    ).strip().lower()
    flagged_only = flagged_raw == "y"

    return sort_by, flagged_only


def run_scan(tickers, etf_set, exchange, sort_by="ticker", flagged_only=False):
    """Execute one full scan cycle."""
    results = scan_tickers(tickers, etf_set)
    if not results:
        console.print("[red]No data retrieved. Check your connection or ticker symbols.[/red]")
        return

    table, alert_count, notable = build_table(
        results, exchange["currency"], sort_by=sort_by, flagged_only=flagged_only
    )
    console.print(table)
    print_notable_signals(notable)

    csv_path, json_path = export_both(results, exchange["key"])
    print_summary(len(results), alert_count, csv_path, json_path)


def _countdown(seconds: int):
    """Show a live countdown banner, then clear it."""
    for remaining in range(seconds, 0, -1):
        mins, secs = divmod(remaining, 60)
        bar  = "▓" * (20 - int(20 * remaining / seconds)) + "░" * int(20 * remaining / seconds)
        line = f"\r  [dim]Next scan in {mins:02d}:{secs:02d}  [{bar}][/dim]  "
        console.print(line, end="", markup=True)
        time.sleep(1)
    console.print()


# ── CLI main ──────────────────────────────────────────────────────────────────

def cli_main():
    console.clear()

    exchange = select_exchange()
    print_header(exchange)
    print_market_status(exchange)

    tickers, etf_set = get_ticker_list(exchange)
    sort_by, flagged_only = get_display_options()

    interval_secs = 0  # 0 = manual only

    while True:
        run_scan(tickers, etf_set, exchange, sort_by=sort_by, flagged_only=flagged_only)

        console.print()
        console.print(
            "[dim]Rescan options:[/dim]  "
            "[green]y[/green] rescan now  "
            "[white]30[/white]/[white]60[/white]/[white]300[/white] auto-refresh interval (secs)  "
            "[red]q[/red] quit"
        )
        choice = console.input("[bold]>[/bold] ").strip().lower()

        if choice == "q" or choice == "":
            break
        elif choice == "y":
            print_market_status(exchange)
            console.print("[dim]Re-fetching fresh data…[/dim]\n")
            continue
        elif choice.isdigit():
            interval_secs = int(choice)
            console.print(
                f"  [green]✓[/green] Auto-refresh every [bold]{interval_secs}s[/bold]. "
                f"Press [red]Ctrl+C[/red] to stop.\n"
            )
            try:
                while True:
                    print_market_status(exchange)
                    console.print("[dim]Re-fetching fresh data…[/dim]\n")
                    run_scan(tickers, etf_set, exchange, sort_by=sort_by, flagged_only=flagged_only)
                    _countdown(interval_secs)
            except KeyboardInterrupt:
                console.print("\n  [yellow]Auto-refresh stopped.[/yellow]")
            break
        else:
            break

    console.print(
        Panel(
            "[green]Thanks for using Stonks.ca![/green]\n"
            "[dim]Reports saved to ~/Desktop[/dim]",
            border_style="green",
            expand=False,
        )
    )


# ── Web main ──────────────────────────────────────────────────────────────────

def web_main():
    import webbrowser
    from stonks.web.app import app

    port = 5002
    console.print(
        Panel(
            f"[bold green]Stonks.ca[/bold green] — Web Dashboard\n"
            f"[white]Starting Flask on[/white] [bold cyan]http://localhost:{port}[/bold cyan]\n"
            f"[dim]Press Ctrl+C to stop.[/dim]",
            border_style="green",
            expand=False,
        )
    )
    webbrowser.open(f"http://localhost:{port}")
    app.run(host="0.0.0.0", port=port, debug=False)


# ── Entry point ───────────────────────────────────────────────────────────────

def main():
    args = sys.argv[1:]

    if "--web" in args:
        web_main()
    elif "--cli" in args:
        cli_main()
    else:
        # Interactive prompt
        console.print("\n[bold cyan]Stonks.ca — Launch Mode[/bold cyan]")
        console.print("  [bold white]1[/bold white]  Terminal (CLI)")
        console.print("  [bold white]2[/bold white]  Web Dashboard  [dim](opens browser)[/dim]\n")
        choice = console.input("[bold]Choice[/bold] ([dim]1/2, default 1[/dim]): ").strip()
        if choice == "2":
            web_main()
        else:
            cli_main()


if __name__ == "__main__":
    main()
