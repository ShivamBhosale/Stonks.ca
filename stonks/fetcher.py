"""
Data fetching: scan_tickers() and helpers.

Strategy (fast path):
  1. One batched yf.download() call pulls 3-month OHLCV history for every
     ticker at once — used to derive fresh price, volume, % change, 20-day
     avg volume, and RSI locally.
  2. A ThreadPoolExecutor fans out yfinance .info calls in parallel for
     fundamentals that don't change intraday (PE, sector, 52W, MAs, etc.).
  3. A module-level TTL cache avoids refetching .info on quick auto-refresh
     cycles — live price/volume still come from the batched history.

A 20-ticker scan drops from ~30s to ~3s and degrades gracefully on batch
failure (falls back to info-only fields).
"""

import time
import warnings
from concurrent.futures import ThreadPoolExecutor

import yfinance as yf
from rich.console import Console
from rich.progress import BarColumn, Progress, SpinnerColumn, TextColumn

warnings.filterwarnings("ignore")

console = Console()

# ── Info TTL cache ────────────────────────────────────────────────────────────

_INFO_CACHE: dict[str, tuple[float, dict]] = {}
_INFO_TTL_SECS = 300  # fundamentals rarely shift within 5 minutes


def _get_info_cached(ticker: str) -> dict:
    """Fetch yfinance .info for a ticker, cached for _INFO_TTL_SECS."""
    now = time.time()
    cached = _INFO_CACHE.get(ticker)
    if cached and now - cached[0] < _INFO_TTL_SECS:
        return cached[1]
    try:
        info = yf.Ticker(ticker).info or {}
    except Exception:
        info = {}
    _INFO_CACHE[ticker] = (now, info)
    return info


def clear_info_cache() -> None:
    """Drop cached fundamentals — useful before a forced full refresh."""
    _INFO_CACHE.clear()


# ── RSI (Wilder's smoothed method) ────────────────────────────────────────────

def _calc_rsi(closes: list[float], period: int = 14) -> float | None:
    """
    Wilder's 14-period RSI. Seeds with a simple mean of the first `period`
    gains/losses, then applies Wilder's exponential smoothing
    (α = 1/period) across the remainder of the series. This is the
    standard RSI that 30/70 thresholds are calibrated against.
    """
    if len(closes) < period + 1:
        return None
    deltas = [closes[i] - closes[i - 1] for i in range(1, len(closes))]
    gains  = [d if d > 0 else 0.0 for d in deltas]
    losses = [-d if d < 0 else 0.0 for d in deltas]

    # Seed from the first `period` bars
    avg_gain = sum(gains[:period]) / period
    avg_loss = sum(losses[:period]) / period

    # Wilder smoothing over remaining bars
    for i in range(period, len(gains)):
        avg_gain = (avg_gain * (period - 1) + gains[i]) / period
        avg_loss = (avg_loss * (period - 1) + losses[i]) / period

    if avg_loss == 0:
        return 100.0
    rs = avg_gain / avg_loss
    return 100.0 - (100.0 / (1.0 + rs))


# ── History frame helpers ─────────────────────────────────────────────────────

def _series_for(hist, ticker: str, field: str) -> list[float]:
    """
    Extract one column (Close / Volume / …) for `ticker` from a batched
    yf.download frame. Handles both multi-ticker (MultiIndex columns) and
    single-ticker (flat columns) shapes, plus empty/missing frames.
    """
    if hist is None or getattr(hist, "empty", True):
        return []
    try:
        series = hist[ticker][field]
    except (KeyError, TypeError, ValueError):
        try:
            series = hist[field]
        except (KeyError, TypeError, ValueError):
            return []
    try:
        return [float(x) for x in series.dropna().tolist()]
    except Exception:
        return []


# ── Row assembly ──────────────────────────────────────────────────────────────

def _build_row(ticker: str, hist, info: dict, is_etf: bool) -> dict | None:
    """Merge batched history and cached info into a single result row."""
    closes  = _series_for(hist, ticker, "Close")
    volumes = _series_for(hist, ticker, "Volume")

    # Price — prefer fresh history, fall back to info
    price = closes[-1] if closes else (
        info.get("currentPrice") or info.get("regularMarketPrice")
    )
    if not price:
        console.print(f"  [yellow]⚠ {ticker}: no price data — skipping[/yellow]")
        return None

    prev_close = closes[-2] if len(closes) >= 2 else (
        info.get("previousClose") or info.get("regularMarketPreviousClose")
    )
    pct_change = ((price - prev_close) / prev_close * 100) if prev_close else None

    # Volume — prefer fresh history
    volume = int(volumes[-1]) if volumes else (
        info.get("volume") or info.get("regularMarketVolume")
    )
    if len(volumes) >= 20:
        avg_volume = sum(volumes[-20:]) / 20
    else:
        avg_volume = info.get("averageVolume") or info.get("averageDailyVolume10Day")
    volume_ratio = (
        (volume / avg_volume) if (volume and avg_volume and avg_volume > 0) else None
    )

    # 52-week band
    week52_high = info.get("fiftyTwoWeekHigh")
    week52_low  = info.get("fiftyTwoWeekLow")
    pct_from_high = ((week52_high - price) / week52_high * 100) if week52_high else None
    pct_from_low  = ((price - week52_low) / week52_low * 100) if week52_low else None

    # Fundamentals (none of these for ETFs where PE is meaningless)
    pe_ratio = None if is_etf else (info.get("trailingPE") or info.get("forwardPE"))

    ma50  = info.get("fiftyDayAverage")
    ma200 = info.get("twoHundredDayAverage")

    rsi = _calc_rsi(closes) if closes else None

    return {
        "ticker":        ticker,
        "is_etf":        is_etf,
        "price":         price,
        "pct_change":    pct_change,
        "volume":        volume,
        "avg_volume":    avg_volume,
        "volume_ratio":  volume_ratio,
        "pe_ratio":      pe_ratio,
        "week52_high":   week52_high,
        "week52_low":    week52_low,
        "pct_from_high": pct_from_high,
        "pct_from_low":  pct_from_low,
        "rsi":           rsi,
        "ma50":          ma50,
        "ma200":         ma200,
        "market_cap":    info.get("marketCap"),
        "sector":        info.get("sector") or "",
        "industry":      info.get("industry") or "",
    }


# ── Public API ────────────────────────────────────────────────────────────────

def scan_tickers(tickers: list[str], etf_set: set[str]) -> list[dict]:
    """
    Fetch market data for all tickers in two parallel phases:
      1. one batched history download
      2. thread-pooled .info calls (cached)

    Returns a list of result dicts; failed tickers are omitted.
    """
    if not tickers:
        return []

    results: list[dict] = []

    with Progress(
        SpinnerColumn(),
        TextColumn("[bold cyan]{task.description}[/bold cyan]"),
        BarColumn(bar_width=40),
        TextColumn("[progress.percentage]{task.percentage:>3.0f}%"),
        console=console,
        transient=True,
    ) as progress:
        # Phase 1 — batched OHLCV history
        hist_task = progress.add_task("Downloading price history…", total=1)
        try:
            hist = yf.download(
                tickers=tickers,
                period="3mo",
                interval="1d",
                group_by="ticker",
                threads=True,
                progress=False,
                auto_adjust=False,
            )
        except Exception as e:
            console.print(
                f"  [yellow]⚠ Batch history download failed ({e}) — "
                f"falling back to info-only fields[/yellow]"
            )
            hist = None
        progress.advance(hist_task)

        # Phase 2 — parallel fundamentals
        info_task = progress.add_task("Fetching fundamentals…", total=len(tickers))
        infos: dict[str, dict] = {}

        def _fetch_one(tkr: str) -> None:
            infos[tkr] = _get_info_cached(tkr)
            progress.advance(info_task)

        with ThreadPoolExecutor(max_workers=8) as ex:
            list(ex.map(_fetch_one, tickers))

        # Phase 3 — assemble rows
        for ticker in tickers:
            try:
                row = _build_row(
                    ticker, hist, infos.get(ticker, {}), is_etf=(ticker in etf_set)
                )
                if row:
                    results.append(row)
            except Exception as e:
                console.print(
                    f"  [yellow]⚠ {ticker}: row build error ({e}) — skipping[/yellow]"
                )

    return results
