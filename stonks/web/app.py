"""
Flask web dashboard for Stonks.ca.
Routes:
  GET  /          — main dashboard page
  POST /scan      — run a scan, return HTML table partial
  GET  /status    — market status HTML partial (for HTMX polling)
"""

import os
from datetime import datetime

from flask import Flask, render_template, request

from ..exchanges import EXCHANGES, get_market_status
from ..fetcher import scan_tickers
from ..signals import THRESHOLDS, evaluate_alerts, generate_suggestion
from ..export import export_both

app = Flask(__name__, template_folder="templates", static_folder="static")


# ── Helpers ───────────────────────────────────────────────────────────────────

def _fmt_pct(value):
    if value is None:
        return '<span class="na">N/A</span>'
    css = "pos" if value > 0 else ("neg" if value < 0 else "")
    sign = "+" if value > 0 else ""
    return f'<span class="{css}">{sign}{value:.2f}%</span>'


def _fmt_vol(ratio):
    if ratio is None:
        return '<span class="na">N/A</span>'
    if ratio >= THRESHOLDS["volume_spike_x"]:
        return f'<span class="spike">{ratio:.2f}×</span>'
    return f'<span class="na">{ratio:.2f}×</span>'


def _fmt_pe(pe, is_etf):
    if is_etf:
        return '<span class="etf-label">fund</span>'
    if pe is None:
        return '<span class="na">N/A</span>'
    if pe < THRESHOLDS["pe_max"]:
        return f'<span class="pos">{pe:.1f}</span>'
    if pe > 35:
        return f'<span class="neg">{pe:.1f}</span>'
    return f'{pe:.1f}'


def _fmt_rsi(rsi):
    if rsi is None:
        return '<span class="na">N/A</span>'
    if rsi < THRESHOLDS["rsi_oversold"]:
        return f'<span class="pos bold">{rsi:.0f}</span>'
    if rsi > THRESHOLDS["rsi_overbought"]:
        return f'<span class="neg bold">{rsi:.0f}</span>'
    return f'{rsi:.0f}'


def _fmt_ma(row):
    price, ma50, ma200 = row.get("price"), row.get("ma50"), row.get("ma200")
    if not (price and ma50 and ma200):
        return '<span class="na">N/A</span>'
    if price > ma50 > ma200:
        return '<span class="pos bold">▲ Golden</span>'
    if price < ma50 < ma200:
        return '<span class="neg bold">▼ Death</span>'
    if price > ma200:
        return '<span class="pos">Above 200d</span>'
    return '<span class="neg">Below 200d</span>'


def _fmt_52w(row):
    th = THRESHOLDS["week52_pct"]
    pfh = row.get("pct_from_high")
    pfl = row.get("pct_from_low")
    if pfh is not None and pfh <= th:
        return f'<span class="pos bold">▲ {pfh:.1f}% fr high</span>'
    if pfl is not None and pfl <= th:
        return f'<span class="neg bold">▼ {pfl:.1f}% fr low</span>'
    hi = f"{pfh:.1f}%" if pfh is not None else "?"
    lo = f"{pfl:.1f}%" if pfl is not None else "?"
    return f'<span class="na">H-{hi} / L+{lo}</span>'


def _fmt_cap(cap):
    if cap is None:
        return '<span class="na">N/A</span>'
    if cap >= 1e12:
        return f'{cap / 1e12:.1f}T'
    if cap >= 1e9:
        return f'{cap / 1e9:.1f}B'
    if cap >= 1e6:
        return f'<span class="na">{cap / 1e6:.0f}M</span>'
    return f'{cap:,}'


def _fmt_alerts(alerts):
    if not alerts:
        return '<span class="na">—</span>'
    parts = []
    for a in alerts:
        if "HIGH" in a or "UP" in a or "GOLDEN" in a or "OVERSOLD" in a:
            parts.append(f'<span class="pos bold">{a}</span>')
        elif "LOW" in a or "DOWN" in a or "DEATH" in a or "OVERBOUGHT" in a:
            parts.append(f'<span class="neg bold">{a}</span>')
        elif "VOL" in a:
            parts.append(f'<span class="spike bold">{a}</span>')
        elif "P/E" in a or "RSI" in a:
            parts.append(f'<span class="cyan">{a}</span>')
        else:
            parts.append(a)
    return "  ".join(parts)


def _sug_class(style):
    if "bold green" in style:
        return "sug-strong-pos"
    if "green" in style:
        return "sug-pos"
    if "bold red" in style:
        return "sug-strong-neg"
    if "red" in style:
        return "sug-neg"
    if "yellow" in style:
        return "sug-warn"
    if "cyan" in style:
        return "sug-cyan"
    return "na"


SORT_KEYS = {
    "ticker":    lambda r: r["ticker"],
    "pct_change": lambda r: (r.get("pct_change") is None, -(r.get("pct_change") or 0)),
    "volume":    lambda r: (r.get("volume_ratio") is None, -(r.get("volume_ratio") or 0)),
    "rsi":       lambda r: (r.get("rsi") is None, r.get("rsi") or 50),
    "pe":        lambda r: (r.get("pe_ratio") is None, r.get("pe_ratio") or 9999),
}


def build_html_table(results, currency, sort_by="ticker", flagged_only=False):
    sort_fn = SORT_KEYS.get(sort_by, SORT_KEYS["ticker"])
    rows_html = []
    alert_count = 0
    notable = []

    for row in sorted(results, key=sort_fn):
        alerts = evaluate_alerts(row)
        suggestion, sug_style = generate_suggestion(alerts, row)

        if flagged_only and not alerts:
            continue

        if alerts:
            alert_count += 1
            if suggestion != "—":
                notable.append((row["ticker"], suggestion, sug_style))

        ticker_html = f'<span class="ticker-name">{row["ticker"]}</span>'
        if row.get("is_etf"):
            ticker_html += ' <span class="etf-label">[ETF]</span>'

        price_str = f"{row['price']:.2f}" if row.get("price") else "N/A"
        row_class = "flagged" if alerts else ""

        rows_html.append(f"""
<tr class="{row_class}">
  <td>{ticker_html}</td>
  <td class="num">{price_str}</td>
  <td class="num">{_fmt_pct(row.get("pct_change"))}</td>
  <td class="num">{_fmt_vol(row.get("volume_ratio"))}</td>
  <td class="num">{_fmt_pe(row.get("pe_ratio"), row.get("is_etf"))}</td>
  <td>{_fmt_52w(row)}</td>
  <td class="num">{_fmt_rsi(row.get("rsi"))}</td>
  <td>{_fmt_ma(row)}</td>
  <td class="num">{_fmt_cap(row.get("market_cap"))}</td>
  <td class="sector">{row.get("sector") or "—"}</td>
  <td class="alerts-cell">{_fmt_alerts(alerts)}</td>
  <td class="{_sug_class(sug_style)}">{suggestion}</td>
</tr>""")

    currency_label = f"Price ({currency})"
    header = f"""
<thead>
  <tr>
    <th>Ticker</th><th>{currency_label}</th><th>% Change</th>
    <th>Vol Spike</th><th>P/E</th><th>52W Position</th>
    <th>RSI</th><th>MA Trend</th><th>Mkt Cap</th>
    <th>Sector</th><th>Alerts</th><th>Suggestion</th>
  </tr>
</thead>"""

    table_html = f'<table id="results-table">{header}<tbody>{"".join(rows_html)}</tbody></table>'

    scan_time = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
    meta_html = (
        f'<p class="scan-meta">Scanned {len(results)} tickers &nbsp;|&nbsp; '
        f'{alert_count} alerts &nbsp;|&nbsp; Last scan: {scan_time}</p>'
    )

    notable_html = ""
    if notable:
        items = "".join(
            f'<li><span class="ticker-name">{t}</span> '
            f'<span class="{_sug_class(s)}">{sug}</span></li>'
            for t, sug, s in notable
        )
        notable_html = f'<div class="notable-panel"><h3>Notable Signals</h3><ul>{items}</ul></div>'

    return meta_html + notable_html + table_html, alert_count


# ── Routes ────────────────────────────────────────────────────────────────────

@app.route("/")
def index():
    exchanges = {k: {"key": v["key"], "name": v["name"]} for k, v in EXCHANGES.items()}
    return render_template("index.html", exchanges=exchanges)


@app.route("/scan", methods=["POST"])
def scan():
    exchange_num   = request.form.get("exchange", "1")
    custom_stocks  = request.form.get("custom_stocks", "").strip()
    custom_etfs    = request.form.get("custom_etfs", "").strip()
    flagged_only   = request.form.get("flagged_only") == "true"
    sort_by        = request.form.get("sort_by", "ticker")
    export_results = request.form.get("export") == "true"

    exchange = EXCHANGES.get(exchange_num, EXCHANGES["1"])
    suffix   = exchange["suffix"]

    def parse(raw):
        return [t.strip().upper() for t in raw.split(",") if t.strip()]

    stocks = parse(custom_stocks) if custom_stocks else []
    etfs   = parse(custom_etfs)   if custom_etfs   else []

    all_tickers = list(dict.fromkeys(exchange["watchlist"] + stocks + etfs))
    etf_set     = set(etfs)

    results = scan_tickers(all_tickers, etf_set)
    if not results:
        return '<p class="error">No data retrieved. Check ticker symbols or connection.</p>'

    table_html, _ = build_html_table(results, exchange["currency"], sort_by, flagged_only)

    if export_results:
        try:
            export_both(results, exchange["key"])
        except Exception:
            pass

    return table_html


@app.route("/status")
def status():
    exchange_num = request.args.get("exchange", "1")
    exchange     = EXCHANGES.get(exchange_num, EXCHANGES["1"])
    st, label, _ = get_market_status(exchange)

    icons = {
        "open":        ("● LIVE", "status-open"),
        "pre_market":  ("◐ PRE-MARKET", "status-warn"),
        "after_hours": ("◑ AFTER HOURS", "status-warn"),
        "weekend":     ("○ CLOSED", "status-closed"),
        "holiday":     ("○ CLOSED", "status-closed"),
    }
    icon, css = icons[st]
    return f'<span class="{css}">{icon}</span> <span class="status-label">{label}</span>'
