# Stonks.ca — CLAUDE.md

## Project Overview
`tsx_screener.py` is a single-file CLI tool that scans TSX-listed equities and ETFs for notable market signals using real-time data from `yfinance`. Output is rendered in the terminal via `rich` and exported to a timestamped CSV on the Desktop after each scan.

## Architecture
Entirely functional Python — no classes. The flow is:

```
main()
 └── get_ticker_list()          # prompt user for custom stocks + ETFs
 └── run_scan() [loop]
      └── scan_tickers()        # fetch data with progress bar
           └── fetch_ticker_data()   # one ticker at a time via yfinance
      └── build_table()         # rich table + evaluate all alerts + suggestions
           └── evaluate_alerts()
           └── generate_suggestion()
      └── print_notable_signals()   # summary panel of flagged tickers
      └── export_csv()              # write to ~/Desktop/tsx_screener_report_*.csv
      └── print_summary()
```

## Key Files
- `tsx_screener.py` — the entire application (single file, ~500 lines)

## Configuration
All filter thresholds live in the `THRESHOLDS` dict near the top of the file:

```python
THRESHOLDS = {
    "pe_max": 20,            # flag P/E below this (value territory)
    "volume_spike_x": 1.5,   # flag volume > N × 20-day average
    "week52_pct": 5.0,       # flag within X% of 52W high or low
    "price_change_pct": 2.0, # flag |% change today| above this
}
```

## TSX Ticker Convention
All tickers must carry the `.TO` suffix (e.g. `RY.TO`, `XIU.TO`). The app warns at runtime if a user-entered ticker is missing the suffix.

## ETF Handling
ETFs entered at the custom ETF prompt are tagged `is_etf=True` in their data dict. This suppresses P/E-based signals (P/E is not meaningful for funds) and renders a `[ETF]` badge in the Ticker column and `fund` in the P/E column.

## Dependencies
```
yfinance   — market data
rich       — terminal UI (table, panels, progress bar)
pandas     — imported but used implicitly by yfinance
```
Install: `pip install yfinance rich pandas`

## Running
```bash
python3 tsx_screener.py
```

## Output
- Terminal: styled `rich` table + Notable Signals panel + Scan Summary panel
- CSV: `~/Desktop/tsx_screener_report_YYYYMMDD_HHMMSS.csv` (includes `type` column: Stock or ETF)

## Do Not
- Add classes — the functional style is intentional
- Change the CSV save location away from `~/Desktop`
- Add features beyond the four core filters without updating `THRESHOLDS`
- Remove the dependency check at the top of the file
