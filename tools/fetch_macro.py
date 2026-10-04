#!/usr/bin/env python3
"""Download the macro series behind Be The Puck's Crash Watch into data/macro/.

  - Shiller CAPE, monthly since 1871 (multpl.com table, built on Shiller's data)
  - FRED: UNRATE (Sahm rule), BAA10Y (Baa corporate minus 10-year Treasury),
    T10Y3M (10-year minus 3-month Treasury), USREC (NBER recession months)

Market series used by the gauges (VIX, 10-year yield, RSP, HYG, IEF) come from
fetch_prices.py, which stores them in data/prices/. A series that fails keeps
its previous file.
"""
import csv
import io
import json
import os
import re
import sys
import time
import urllib.request

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
OUT = os.path.join(ROOT, "data", "macro")
UA = "Be The Puck/1.0 (+https://bethepuck.com)"
FRED = ["UNRATE", "BAA10Y", "T10Y3M", "USREC"]
MONTHS = {m: i for i, m in enumerate(["Jan", "Feb", "Mar", "Apr", "May", "Jun", "Jul", "Aug", "Sep", "Oct", "Nov", "Dec"], 1)}


def get(url, tries=3):
    last = None
    for i in range(tries):
        try:
            req = urllib.request.Request(url, headers={"User-Agent": UA})
            with urllib.request.urlopen(req, timeout=60) as r:
                return r.read().decode("utf-8", "replace")
        except Exception as ex:   # network hiccup
            last = ex
            time.sleep(3 * (i + 1))
    raise RuntimeError(f"{url}: {last}")


def save(name, rows, header):
    if len(rows) < 12:
        raise RuntimeError(f"{name}: only {len(rows)} rows")
    path = os.path.join(OUT, name + ".csv")
    buf = io.StringIO()
    w = csv.writer(buf, lineterminator="\n")
    w.writerow(header)
    w.writerows(rows)
    txt = buf.getvalue()
    old = open(path).read() if os.path.exists(path) else None
    if txt != old:
        with open(path, "w") as f:
            f.write(txt)
    return len(rows)


def cape():
    h = get("https://www.multpl.com/shiller-pe/table/by-month")
    rows = re.findall(r"<td>([A-Z][a-z]{2}) (\d{1,2}), (\d{4})</td>\s*<td>\s*(?:&#x2002;)?\s*([\d.]+)", h)
    out = sorted((f"{y}-{MONTHS[m]:02d}-{int(d):02d}", v) for m, d, y, v in rows)
    return save("cape", out, ["date", "cape"])


def fred(sid):
    txt = get(f"https://fred.stlouisfed.org/graph/fredgraph.csv?id={sid}")
    rows = []
    for r in csv.reader(io.StringIO(txt)):
        if len(r) == 2 and re.match(r"\d{4}-\d{2}-\d{2}$", r[0]) and r[1] not in (".", ""):
            rows.append((r[0], r[1]))
    return save("fred_" + sid.lower(), rows, ["date", sid.lower()])


def main():
    os.makedirs(OUT, exist_ok=True)
    failed = []
    jobs = [("cape", cape)] + [(f"fred:{s}", (lambda s=s: fred(s))) for s in FRED]
    for name, fn in jobs:
        try:
            print(f"ok   {name:14s} {fn()} rows")
        except Exception as ex:
            failed.append(name)
            print(f"FAIL {name}: {ex}", file=sys.stderr)
    with open(os.path.join(OUT, "_meta.json"), "w") as f:
        json.dump({"fetched_at": time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime()), "failed": failed}, f, indent=1)
    return 1 if len(failed) == len(jobs) else 0


if __name__ == "__main__":
    sys.exit(main())
