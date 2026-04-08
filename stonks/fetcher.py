"""
Data fetching: fetch_ticker_data() and scan_tickers().
Includes RSI (14-day), MA50/200, market cap, sector, and industry.
"""

import warnings

import yfinance as yf
from rich.console import Console
from rich.progress import BarColumn, Progress, SpinnerColumn, TextColumn

warnings.filterwarnings("ignore")

console = Console()


def _calc_rsi(closes: list[float], period: int = 14) -> float | None:
    """Simple 14-period RSI from a list of closing prices."""
    if len(closes) < period + 1:
        return None
    deltas = [closes[i] - closes[i - 1] for i in range(1, len(closes))]
    gains  = [d if d > 0 else 0.0 for d in deltas[-period:]]
    losses = [-d if d < 0 else 0.0 for d in deltas[-period:]]
    avg_gain = sum(gains) / period
    avg_loss = sum(losses) / period
    if avg_loss == 0:
        return 100.0
    rs = avg_gain / avg_loss
    return 100.0 - (100.0 / (1.0 + rs))


def fetch_ticker_data(ticker: str, is_etf: bool = False) -> dict | None:
    """
    Fetch all required fields for a single ticker via yfinance.
    Returns a data dict, or None if the ticker is invalid / data missing.
    """
    try:
        t    = yf.Ticker(ticker)
        info = t.info

        price = info.get("currentPrice") or info.get("regularMarketPrice")
        if not price:
            console.print(f"  [yellow]⚠ {ticker}: no price data — skipping[/yellow]")
            return None

        prev_close = info.get("previousClose") or info.get("regularMarketPreviousClose")
        pct_change = ((price - prev_close) / prev_close * 100) if prev_close else None

        volume     = info.get("volume") or info.get("regularMarketVolume")
        avg_volume = info.get("averageVolume") or info.get("averageDailyVolume10Day")
        volume_ratio = (volume / avg_volume) if (volume and avg_volume and avg_volume > 0) else None

        week52_high = info.get("fiftyTwoWeekHigh")
        week52_low  = info.get("fiftyTwoWeekLow")
        pct_from_high = ((week52_high - price) / week52_high * 100) if week52_high else None
        pct_from_low  = ((price - week52_low)  / week52_low  * 100) if week52_low  else None

        pe_ratio = None if is_etf else (info.get("trailingPE") or info.get("forwardPE"))

        # Moving averages (already in info, no extra call)
        ma50  = info.get("fiftyDayAverage")
        ma200 = info.get("twoHundredDayAverage")

        # RSI — requires a short history fetch
        rsi = None
        try:
            hist   = t.history(period="1mo")
            closes = hist["Close"].tolist()
            rsi    = _calc_rsi(closes)
        except Exception:
            pass

        # Fundamentals
        market_cap = info.get("marketCap")
        sector     = info.get("sector") or ""
        industry   = info.get("industry") or ""

        return {
            "ticker":       ticker,
            "is_etf":       is_etf,
            "price":        price,
            "pct_change":   pct_change,
            "volume":       volume,
            "avg_volume":   avg_volume,
            "volume_ratio": volume_ratio,
            "pe_ratio":     pe_ratio,
            "week52_high":  week52_high,
            "week52_low":   week52_low,
            "pct_from_high": pct_from_high,
            "pct_from_low":  pct_from_low,
            "rsi":          rsi,
            "ma50":         ma50,
            "ma200":        ma200,
            "market_cap":   market_cap,
            "sector":       sector,
            "industry":     industry,
        }

    except Exception as e:
        console.print(f"  [yellow]⚠ {ticker}: fetch error ({e}) — skipping[/yellow]")
        return None


def scan_tickers(tickers: list[str], etf_set: set[str]) -> list[dict]:
    """
    Fetch data for all tickers with a progress bar.
    Returns a list of result dicts (failed tickers omitted).
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
