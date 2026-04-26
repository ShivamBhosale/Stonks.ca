# Stonks.ca

A TSX Stock Screener CLI tool that scans equities and ETFs for notable market signals in real time — right from your terminal.

![Python](https://img.shields.io/badge/Python-3.10%2B-blue)
![License](https://img.shields.io/badge/License-MIT-green)

---

## Features

- **Real market data** via `yfinance` — no API key required
- **Four configurable signal filters:**
  - P/E ratio below a value threshold
  - Volume spike vs 20-day average
  - Proximity to 52-week high or low
  - Significant % price move today
- **Plain-English suggestions** based on signal combinations (e.g. *"Momentum breakout — watch for continuation"*)
- **ETF support** — enter ETF tickers separately; P/E signals are suppressed for funds
- **Rich terminal UI** — colour-coded table, Notable Signals panel, progress bar
- **CSV export** to Desktop after every scan (`tsx_screener_report_YYYYMMDD_HHMMSS.csv`)
- **Rescan loop** — re-fetch fresh data without restarting

---

## Installation

```bash
pip install yfinance rich pandas
```

Requires Python 3.10+.

---

## Usage

```bash
python3 tsx_screener.py
```

At startup you will be prompted twice:

```
Add custom stock tickers? (comma-separated with .TO suffix, or Enter to skip):
Add ETF tickers?          (comma-separated with .TO suffix, or Enter to skip):
```

After results are shown:

```
Run again? (y to rescan / q to quit):
```

---

## Default Watchlist

20 TSX blue-chips and growth names scanned on every run:

| Banks | Rails & Energy | Mining | Tech & Ins | Telecom & Other |
|---|---|---|---|---|
| RY.TO | CNR.TO | ABX.TO | SHOP.TO | BCE.TO |
| TD.TO | CP.TO  | AEM.TO | CSU.TO  | T.TO   |
| BNS.TO | SU.TO | | MFC.TO  | WCN.TO |
| BMO.TO | ENB.TO | | SLF.TO  | ATD.TO |
| CM.TO  | TRP.TO | | | |

---

## Signal Logic

| Combination | Suggestion |
|---|---|
| Low P/E + near 52W low | Value opportunity — research further |
| Volume spike + move up + near 52W high | Momentum breakout — watch for continuation |
| Volume spike + move up | Unusual buying interest |
| Volume spike + move down + near 52W low | Heavy selling near 52W low — high risk |
| Volume spike + move down | Unusual selling — investigate catalyst |
| Near 52W low + move down | Selling pressure — use caution |
| Near 52W high + move up | Testing resistance — monitor closely |
| Near 52W high | Near 52W high — watch for breakout or reversal |
| Near 52W low | Oversold territory — watch for reversal |
| Low P/E only | Potentially undervalued |

---

## Configurable Thresholds

Edit the `THRESHOLDS` dict at the top of `tsx_screener.py`:

```python
THRESHOLDS = {
    "pe_max": 20,            # flag P/E below this value
    "volume_spike_x": 1.5,   # flag volume > N × 20-day average
    "week52_pct": 5.0,       # flag within X% of 52W high or low
    "price_change_pct": 2.0, # flag |% change today| above this
}
```

---

## Output

**Terminal:**

```
╭─────────────────── Stonks.ca ────────────────────╮
│  TSX STOCK SCREENER                               │
│  Tuesday, March 31 2026  14:23:01                 │
╰──────────────── Powered by yfinance ─────────────╯

┌──────────────┬─────────────┬──────────┬───────────┬──────┬──────────────────────┬──────────────────────┬────────────────────────────────────────┐
│ Ticker       │ Price (CAD) │ % Change │ Vol Spike │  P/E │ 52W Position         │ Alerts               │ Suggestion                             │
...

╭──────────── Notable Signals ─────────────╮
│  XIU.TO    Near 52W high — monitor       │
│  SU.TO     Unusual buying interest       │
╰── Review before acting — not fin. advice ╯
```

**CSV** (`~/Desktop/tsx_screener_report_YYYYMMDD_HHMMSS.csv`):

| ticker | type | price | pct_change | volume | avg_volume | volume_ratio | pe_ratio | week52_high | week52_low | pct_from_high | pct_from_low | alerts | suggestion |
|---|---|---|---|---|---|---|---|---|---|---|---|---|---|

---

## Disclaimer

This tool is for informational purposes only. Nothing here constitutes financial advice. Always do your own research before making investment decisions.

---

## License

MIT
