#!/usr/bin/env python3
"""Download company fundamentals for every stock in the universe into
data/fundamentals/<slug>.json (Yahoo Finance via yfinance).

Used by the stock pages (valuation, balance sheet, analyst targets), the crash
exposure read (debt, interest cover, cash) and the Learn widgets. ETFs, indexes
and crypto are skipped. A ticker that fails keeps its previous file.

    python tools/fetch_fundamentals.py            # all stocks
    python tools/fetch_fundamentals.py HTZ NVDA   # just these
"""
import datetime as dt
import json
import math
import os
import sys
import time

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from qstrat.content import TICKERS  # noqa: E402

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
OUT = os.path.join(ROOT, "data", "fundamentals")
INFO = ["shortName", "longName", "sector", "industry", "country", "currency", "financialCurrency", "quoteType", "exchange",
        "marketCap", "enterpriseValue", "sharesOutstanding", "trailingPE", "forwardPE", "priceToBook", "priceToSalesTrailing12Months",
        "pegRatio", "trailingPegRatio", "trailingEps", "forwardEps", "totalRevenue", "revenueGrowth", "earningsGrowth",
        "grossMargins", "operatingMargins", "profitMargins", "returnOnEquity", "returnOnAssets", "ebitda", "freeCashflow",
        "operatingCashflow", "totalDebt", "totalCash", "debtToEquity", "currentRatio", "quickRatio", "bookValue", "beta",
        "dividendYield", "payoutRatio", "fiftyTwoWeekHigh", "fiftyTwoWeekLow", "targetMeanPrice", "targetLowPrice",
        "targetHighPrice", "numberOfAnalystOpinions", "recommendationMean", "recommendationKey", "heldPercentInsiders",
        "shortPercentOfFloat", "fullTimeEmployees", "longBusinessSummary", "website"]


def clean(v):
    if v is None:
        return None
    if isinstance(v, float) and (math.isnan(v) or math.isinf(v)):
        return None
    if hasattr(v, "item"):
        v = v.item()
    return v


def latest(df, names):
    """Most recent annual value of the first matching row."""
    if df is None or getattr(df, "empty", True):
        return None, None
    for n in names:
        if n in df.index:
            row = df.loc[n].dropna()
            if len(row):
                return clean(float(row.iloc[0])), str(row.index[0])[:10]
    return None, None


def fetch(sym):
    import yfinance as yf
    tk = yf.Ticker(sym)
    info = tk.info or {}
    if info.get("quoteType") not in (None, "EQUITY"):
        return None
    out = {k: clean(info.get(k)) for k in INFO}
    if out.get("longBusinessSummary"):
        out["longBusinessSummary"] = out["longBusinessSummary"][:900]
    try:
        bs, inc = tk.balance_sheet, tk.income_stmt
    except Exception:
        bs = inc = None
    out["equity"], out["equity_date"] = latest(bs, ["Stockholders Equity", "Common Stock Equity", "Total Equity Gross Minority Interest"])
    out["total_debt_bs"], _ = latest(bs, ["Total Debt"])
    out["cash_bs"], _ = latest(bs, ["Cash And Cash Equivalents", "Cash Cash Equivalents And Short Term Investments"])
    out["ebit"], _ = latest(inc, ["EBIT", "Operating Income"])
    out["interest_expense"], _ = latest(inc, ["Interest Expense", "Interest Expense Non Operating"])
    ie = out["interest_expense"]
    out["interest_cover"] = (out["ebit"] / abs(ie)) if out["ebit"] is not None and ie else None
    out["fetched"] = dt.date.today().isoformat()
    return out


def main(argv):
    os.makedirs(OUT, exist_ok=True)
    pool = [t for t in TICKERS if not (t.get("index") or t.get("crypto") or t.get("group") in ("Indexes & ETFs", "Sectors"))]
    if argv:
        pool = [t for t in TICKERS if t["sym"] in argv]
    failed = []
    for t in pool:
        for i in range(3):
            try:
                d = fetch(t["sym"])
                if d is not None:
                    with open(os.path.join(OUT, t["slug"] + ".json"), "w") as f:
                        json.dump(d, f, indent=1, sort_keys=True)
                print(f"ok   {t['sym']:9s} cap={d and d.get('marketCap')} pe={d and d.get('trailingPE')}")
                break
            except Exception as ex:
                if i == 2:
                    failed.append(t["sym"])
                    print(f"FAIL {t['sym']}: {ex}", file=sys.stderr)
                time.sleep(2 * (i + 1))
    print(f"{len(pool) - len(failed)} ok, {len(failed)} failed")
    return 1 if failed and len(failed) > len(pool) // 2 else 0


if __name__ == "__main__":
    sys.exit(main(sys.argv[1:]))
