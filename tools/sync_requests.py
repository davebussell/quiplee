#!/usr/bin/env python3
"""Turn readers' watchlist requests into covered stocks (runs nightly in CI).

1. Read the queue from https://quiplee.com/api/watch (Netlify Function + Blobs).
2. For each symbol not already covered or rejected, check it has a real price
   history on Yahoo Finance (at least 60 sessions) and look up its name and
   currency.
3. Add good ones to data/universe/requested.json and bad ones to
   data/universe/rejected.json. fetch_prices.py then downloads their history and
   the next site build publishes their analysis.

Limits keep the nightly build quick: at most 25 new tickers a night and 300 in
total. Anything over the limit stays queued for the next night.
"""
import datetime as dt
import json
import os
import sys
import urllib.request

HERE = os.path.dirname(os.path.abspath(__file__))
ROOT = os.path.dirname(HERE)
sys.path.insert(0, HERE)
from qstrat.content import TICKERS, EXCLUDED  # noqa: E402

QUEUE = os.environ.get("QUIPLEE_QUEUE_URL", "https://quiplee.com/api/watch")
REQ = os.path.join(ROOT, "data", "universe", "requested.json")
REJ = os.path.join(ROOT, "data", "universe", "rejected.json")
PER_NIGHT, MAX_TOTAL = 25, 300
CUR = {"USD": "$", "CAD": "C$", "EUR": "€", "GBP": "£", "GBp": "GBp ", "JPY": "¥"}


def load(path, key):
    return json.load(open(path)) if os.path.exists(path) else {key: []}


def tidy(name):
    """'Coca-Cola Company (The)' -> 'Coca-Cola Company'; drop legal suffixes."""
    import re
    n = (name or "").strip()
    n = re.sub(r"\s*\(The\)$", "", n)
    n = re.sub(r",?\s+(Inc\.?|Incorporated|Corporation|Corp\.?|Ltd\.?|Limited|plc|PLC|S\.A\.|N\.V\.|Co\.)$", "", n)
    return n.strip() or name


def check(sym):
    import yfinance as yf
    d = yf.download(sym, period="2y", progress=False, auto_adjust=True, threads=False)
    if d is None or len(d) < 60:
        return None, "no price history found on Yahoo Finance"
    info = {}
    try:
        info = yf.Ticker(sym).info or {}
    except Exception:
        pass
    cur = info.get("currency") or "USD"
    return {"sym": sym, "name": tidy(info.get("shortName") or info.get("longName") or sym), "cur": CUR.get(cur, cur + " "),
            "currency": cur, "type": info.get("quoteType"), "exchange": info.get("exchange")}, None


def main():
    req, rej = load(REQ, "tickers"), load(REJ, "tickers")
    covered = {t["sym"] for t in TICKERS} | {r["sym"] for r in req["tickers"]}
    rejected = {r["sym"] for r in rej["tickers"]}
    try:
        with urllib.request.urlopen(urllib.request.Request(QUEUE, headers={"User-Agent": "quiplee-sync"}), timeout=60) as r:
            queue = json.load(r).get("requests", [])
    except Exception as ex:
        print(f"queue unavailable: {ex}")
        return 0
    todo = [q for q in queue if q["sym"] not in covered and q["sym"] not in rejected and q["sym"] not in EXCLUDED]
    room = max(0, min(PER_NIGHT, MAX_TOTAL - len(req["tickers"])))
    today = dt.date.today().isoformat()
    added = 0
    for q in todo[:room]:
        try:
            ok, why = check(q["sym"])
        except Exception as ex:
            print(f"skip {q['sym']} for now: {ex}")
            continue
        if ok:
            ok.update(status="ok", added=today, requested=q.get("first", "")[:10], count=q.get("count", 1))
            req["tickers"].append(ok)
            added += 1
            print(f"add  {q['sym']}: {ok['name']}")
        else:
            rej["tickers"].append({"sym": q["sym"], "reason": why, "date": today})
            print(f"skip {q['sym']}: {why}")
    os.makedirs(os.path.dirname(REQ), exist_ok=True)
    for path, data in ((REQ, req), (REJ, rej)):
        data["updated"] = today
        with open(path, "w") as f:
            json.dump(data, f, indent=1)
    print(f"{len(queue)} in queue, {len(todo)} new, {added} added, {max(0, len(todo) - room)} left for later")
    return 0


if __name__ == "__main__":
    sys.exit(main())
