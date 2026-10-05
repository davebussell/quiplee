#!/usr/bin/env python3
"""Download adjusted daily prices for every ticker into data/prices/.

One CSV per ticker (date,open,high,low,close,volume), split- and
dividend-adjusted, from 2004 on, plus ^IRX (13-week T-bill yield, in percent).
The site build reads only these files, so it never touches the network.

A ticker that fails to download keeps its previous file, so one bad night at
Yahoo never empties a page. Run nightly by .github/workflows/refresh-prices.yml.

    python tools/fetch_prices.py            # all tickers
    python tools/fetch_prices.py NVDA SPY   # just these
"""
import datetime as dt
import json
import os
import sys
import time

import pandas as pd
from zoneinfo import ZoneInfo

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from qstrat.content import TICKERS  # noqa: E402

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
OUT = os.path.join(ROOT, "data", "prices")
START = "2004-01-01"
EXTRA = ["^IRX", "^VIX", "^TNX", "RSP", "HYG", "IEF", "CAD=X"]   # cash rate, macro gauges, USD/CAD (paper trading)
ET = ZoneInfo("America/New_York")


def file_for(sym):
    return os.path.join(OUT, sym.replace("^", "_").replace(".", "-").lower() + ".csv")


def start_for(sym):
    """Indexes get long history (1985) for the macro charts; everything else from 2004."""
    return "1985-01-01" if sym.startswith("^") and sym != "^IRX" else START


def download(sym, tries=3, start=None):
    import yfinance as yf
    last = None
    for i in range(tries):
        try:
            d = yf.download(sym, start=start or start_for(sym), progress=False, auto_adjust=True, threads=False)
            if d is not None and not d.empty:
                if isinstance(d.columns, pd.MultiIndex):
                    d.columns = d.columns.get_level_values(0)
                d = d.rename(columns=str.lower)[["open", "high", "low", "close", "volume"]]
                d.index = pd.to_datetime(d.index).tz_localize(None).normalize()
                d = d[~d.index.duplicated(keep="last")]
                d = d.dropna(subset=["close"])
                return d
            last = "empty frame"
        except Exception as ex:   # network hiccup, rate limit
            last = repr(ex)
        time.sleep(2 * (i + 1))
    raise RuntimeError(f"{sym}: {last}")


def finished(sym, d, now_et):
    """Keep only finished bars: drop today's row for stocks before 16:30 New York
    time, and today's UTC row for crypto (it is still forming)."""
    if d.empty:
        return d
    last = d.index[-1].date()
    if sym.endswith("-USD"):
        if last >= dt.datetime.now(dt.timezone.utc).date():
            return d.iloc[:-1]
    elif last >= now_et.date() and (now_et.hour, now_et.minute) < (16, 30):
        return d.iloc[:-1]
    return d


def write(sym, d):
    d = d.copy()
    for c in ["open", "high", "low", "close"]:
        d[c] = d[c].fillna(d["close"])
    d["volume"] = d["volume"].fillna(0).round().astype("int64")
    d.index.name = "date"
    path = file_for(sym)
    txt = d.to_csv(float_format="%.6g", date_format="%Y-%m-%d")
    old = open(path).read() if os.path.exists(path) else None
    if txt != old:
        with open(path, "w") as f:
            f.write(txt)
        return True
    return False


def main(argv):
    os.makedirs(OUT, exist_ok=True)
    syms = argv or ([t["sym"] for t in TICKERS] + EXTRA)
    meta_path = os.path.join(OUT, "_meta.json")
    meta = json.load(open(meta_path)) if os.path.exists(meta_path) else {"tickers": {}}
    failed, changed = [], 0
    for sym in syms:
        try:
            d = finished(sym, download(sym), dt.datetime.now(ET))
            changed += write(sym, d)
            meta["tickers"][sym] = {"first": d.index[0].strftime("%Y-%m-%d"), "last": d.index[-1].strftime("%Y-%m-%d"), "rows": len(d)}
            print(f"ok   {sym:10s} {d.index[0].date()} → {d.index[-1].date()} ({len(d)} rows)")
        except Exception as ex:
            failed.append(sym)
            print(f"FAIL {sym}: {ex}", file=sys.stderr)
    meta["fetched_at"] = dt.datetime.now(dt.timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")
    meta["failed"] = failed
    with open(meta_path, "w") as f:
        json.dump(meta, f, indent=1, sort_keys=True)
    print(f"{len(syms) - len(failed)} fetched, {changed} files changed, {len(failed)} failed")
    # Fail the job only if most downloads failed (Yahoo outage); a few misses keep old files.
    return 1 if len(failed) > len(syms) // 2 else 0


if __name__ == "__main__":
    sys.exit(main(sys.argv[1:]))
