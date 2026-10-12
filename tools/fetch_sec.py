#!/usr/bin/env python3
"""Company fundamentals from SEC filings (XBRL), dated by when each number was filed.

For every covered stock that files 10-Qs and 10-Ks with the SEC (U.S. companies, and
Canadian ones such as Shopify that file as U.S. domestic filers), this keeps one compact
file, data/sec/<slug>.json:

    {"cik", "name", "ccy", "fetched", "last_filed",
     "q": [[end, filed, revenue, net income, diluted EPS, operating cash flow, capex,
            gross profit, operating income, dividends per share, diluted shares], ...],   # one row per quarter
     "b": [[end, filed, equity, debt, cash, shares outstanding], ...],     # balance sheet dates
     "earn": [[filed, accession, primary document], ...]}                  # 8-Ks with Item 2.02

Every value is the one first reported for that quarter (later restatements are ignored),
with the date it was filed, so a backtest only ever sees what was public at the time.
Quarters missing from the filings (Q4 is usually only in the 10-K) are derived: Q4 =
full year less the first nine months. tools/qstrat/secfund.py turns these into P/E,
growth, margins and the rest.

Nightly (in .github/workflows/refresh-prices.yml) it reads each company's filing list
(data.sec.gov/submissions) and downloads the full facts again only when a new 10-Q, 10-K
or amendment has been filed since the last run, so most nights it fetches ~250 small files.

    python tools/fetch_sec.py              # every covered stock
    python tools/fetch_sec.py MU SHOP.TO   # just these
    python tools/fetch_sec.py --all        # ignore the cache and refetch every company's facts

SEC asks for a descriptive User-Agent with a contact address and at most 10 requests a second.
"""
import datetime as dt
import json
import os
import re
import sys
import time
import urllib.error
import urllib.request

HERE = os.path.dirname(os.path.abspath(__file__))
ROOT = os.path.dirname(HERE)
sys.path.insert(0, HERE)
from qstrat.content import TICKERS  # noqa: E402

OUT = os.path.join(ROOT, "data", "sec")
UA = "Be The Puck news archive (bethepuck.com; dave@clickshift.ca)"   # same contact as tools/fetch_news.py
GAP = 0.13            # seconds between requests (under SEC's 10 a second)
PERIODIC = ("10-K", "10-Q", "10-K/A", "10-Q/A", "10-KT")

# concept -> the us-gaap tags that carry it, in order of preference
DURATION = {
    "rev": ["RevenueFromContractWithCustomerExcludingAssessedTax", "Revenues", "SalesRevenueNet",
            "RevenueFromContractWithCustomerIncludingAssessedTax", "RevenuesNetOfInterestExpense", "SalesRevenueGoodsNet"],
    "ni": ["NetIncomeLoss", "NetIncomeLossAvailableToCommonStockholdersBasic", "ProfitLoss"],
    "eps": ["EarningsPerShareDiluted", "EarningsPerShareBasicAndDiluted", "EarningsPerShareBasic"],
    "ocf": ["NetCashProvidedByUsedInOperatingActivities", "NetCashProvidedByUsedInOperatingActivitiesContinuingOperations"],
    "capex": ["PaymentsToAcquirePropertyPlantAndEquipment", "PaymentsToAcquireProductiveAssets"],
    "gp": ["GrossProfit"],
    "opi": ["OperatingIncomeLoss"],
    "dps": ["CommonStockDividendsPerShareDeclared", "CommonStockDividendsPerShareCashPaid"],
    # diluted share count for the quarter (an average, so never derived from year-to-date figures);
    # the fallback when the cover page has no single share count (several share classes)
    "wsh": ["WeightedAverageNumberOfDilutedSharesOutstanding", "WeightedAverageNumberOfSharesOutstandingBasicAndDiluted"],
}
NO_DERIVE = {"wsh"}
Q_KEYS = list(DURATION)
INSTANT = {
    "equity": ["StockholdersEquity", "StockholdersEquityIncludingPortionAttributableToNoncontrollingInterest"],
    "cash": ["CashAndCashEquivalentsAtCarryingValue", "CashCashEquivalentsRestrictedCashAndRestrictedCashEquivalents", "Cash"],
}
DEBT_PARTS = [["LongTermDebt"], ["LongTermDebtNoncurrent", "LongTermDebtAndCapitalLeaseObligations"],
              ["LongTermDebtCurrent", "DebtCurrent", "LongTermDebtAndCapitalLeaseObligationsCurrent"],
              ["ShortTermBorrowings", "CommercialPaper"]]
B_KEYS = ["equity", "debt", "cash", "shares"]


def get(url, tries=4):
    for i in range(tries):
        try:
            req = urllib.request.Request(url, headers={"User-Agent": UA, "Accept-Encoding": "identity"})
            with urllib.request.urlopen(req, timeout=60) as r:
                data = r.read()
            time.sleep(GAP)
            return json.loads(data.decode())
        except urllib.error.HTTPError as ex:
            if ex.code == 404:
                return None
            time.sleep(2 + 3 * i)
        except Exception:
            time.sleep(2 + 3 * i)
    return None


def norm_name(s):
    s = re.sub(r"[^a-z0-9 ]", " ", (s or "").lower())
    drop = {"inc", "corp", "corporation", "co", "company", "ltd", "limited", "plc", "the", "holdings", "group", "sa", "nv", "ag", "lp", "llc", "class", "a", "b"}
    return [w for w in s.split() if w not in drop]


def same_company(ours, theirs):
    """Loose check that two company names are the same business (guards against ticker clashes like L / L.TO)."""
    a, b = norm_name(ours), norm_name(theirs)
    return bool(a and b and a[0] == b[0])


def cik_map(names):
    """{sym: (cik, SEC name)} for covered stocks: U.S. tickers by ticker (name-checked), TSX ones only by an exact name match on a U.S. exchange."""
    d = get("https://www.sec.gov/files/company_tickers_exchange.json")
    if not d:
        return {}
    rows = [dict(zip(d["fields"], r)) for r in d["data"]]
    by_ticker = {r["ticker"].upper(): r for r in rows}
    by_name = {}
    for r in rows:
        if r.get("exchange") in ("NYSE", "Nasdaq", "CBOE", "NYSE MKT", "NYSE American"):
            by_name.setdefault(" ".join(norm_name(r["name"])), r)
    out = {}
    for t in names:
        sym = t["sym"]
        if sym.endswith((".TO", ".V", ".NE", ".CN")):
            r = by_name.get(" ".join(norm_name(t["name"])))
        else:
            r = by_ticker.get(sym.replace(".", "-").upper()) or by_ticker.get(sym.upper())
            if r and not same_company(t["name"], r["name"]):
                r = None
        if r:
            out[sym] = (int(r["cik"]), r["name"])
    return out


def _days(a, b):
    return (dt.date.fromisoformat(b) - dt.date.fromisoformat(a)).days


def first_reported(facts):
    """{(start or None, end): (val, filed)} keeping the earliest filing of each period from 10-K/10-Q forms."""
    out = {}
    for f in facts:
        if f.get("form") not in PERIODIC:
            continue
        k = (f.get("start"), f["end"])
        if k not in out or f["filed"] < out[k][1]:
            out[k] = (f["val"], f["filed"])
    return out


def pick_units(concept):
    units = concept.get("units", {})
    for u in ("USD", "USD/shares", "CAD", "CAD/shares", "shares", "pure"):
        if u in units:
            return u, units[u]
    return (next(iter(units.items())) if units else (None, []))


def _quarters_one(facts, derive=True):
    """{end: (val, filed, start)} for one tag: its quarterly facts plus quarters derived from year-to-date figures."""
    q, ytd = {}, []
    for (start, end), (val, filed) in first_reported(facts).items():
        if not start:
            continue
        n = _days(start, end)
        if 80 <= n <= 120:          # 12- to 17-week quarters (retailers' 52/53-week years)
            q[end] = (val, filed, start)
        elif 120 < n <= 380:
            ytd.append((start, end, val, filed, n))
    # Q2 = H1 - Q1, Q3 = 9M - H1, Q4 = FY - 9M: any year-to-date figure whose earlier quarters are known
    for _ in range(3 if derive else 0):
        added = False
        for start, end, val, filed, n in sorted(ytd, key=lambda x: x[4]):
            if end in q:
                continue
            inside = sorted([(e, v) for e, v in q.items() if v[2] >= start and e < end], key=lambda x: x[0])
            want = round(n / 91.3) - 1
            if want < 1 or len(inside) != want or abs(_days(inside[0][1][2], start)) > 6:
                continue
            last_end = inside[-1][0]
            if not 80 <= _days(last_end, end) <= 120:
                continue
            q[end] = (val - sum(v[0] for _, v in inside), filed, (dt.date.fromisoformat(last_end) + dt.timedelta(days=1)).isoformat())
            added = True
        if not added:
            break
    return q


def quarters(gaap, tags, derive=True):
    """{end: (val, filed, start)} for every quarter. Each quarter comes from the first tag in
    `tags` that has it, since companies switch tags over the years (Revenues, then
    RevenueFromContractWithCustomer...)."""
    out = {}
    for tag in tags:
        c = gaap.get(tag)
        if not c:
            continue
        _, facts = pick_units(c)
        for end, v in _quarters_one(facts, derive).items():
            out.setdefault(end, v)
    return out


def instants(gaap, tags):
    """{end: (val, filed)} for balance-sheet values, each date from the first tag in `tags` that has it."""
    out = {}
    for tag in tags:
        c = gaap.get(tag)
        if not c:
            continue
        _, facts = pick_units(c)
        for (start, end), (val, filed) in first_reported(facts).items():
            if start is None:
                out.setdefault(end, (val, filed))
    return out


def extract(facts):
    gaap = facts.get("facts", {}).get("us-gaap", {})
    dei = facts.get("facts", {}).get("dei", {})
    if not gaap:
        return None
    ccy, _ = pick_units(gaap.get("NetIncomeLoss") or gaap.get("Revenues") or gaap.get("StockholdersEquity") or {})
    Q = {k: quarters(gaap, tags, k not in NO_DERIVE) for k, tags in DURATION.items()}
    ends = sorted(set().union(*[set(v) for v in Q.values()]))
    qrows = []
    for end in ends:
        filed = min(Q[k][end][1] for k in Q_KEYS if end in Q[k])
        qrows.append([end, filed] + [(round(Q[k][end][0], 6) if end in Q[k] else None) for k in Q_KEYS])
    B = {k: instants(gaap, tags) for k, tags in INSTANT.items()}
    parts = [instants(gaap, tags) for tags in DEBT_PARTS]
    debt = {}
    for end in set().union(*[set(p) for p in parts]):
        lt = parts[0].get(end)
        if lt:
            v, f = lt[0], lt[1]
        else:
            got = [p[end] for p in parts[1:3] if end in p]
            if not got:
                continue
            v, f = sum(g[0] for g in got), min(g[1] for g in got)
        if end in parts[3]:
            v += parts[3][end][0]
        debt[end] = (v, f)
    B["debt"] = debt
    # shares outstanding: the cover page count; a company with several share classes reports one
    # number per class on the same date and filing, so distinct values are summed
    per = {}
    so = dei.get("EntityCommonStockSharesOutstanding")
    if so:
        _, facts_ = pick_units(so)
        for f in facts_:
            if f.get("form") in PERIODIC:
                per.setdefault((f["end"], f["accn"]), [f["filed"], set()])[1].add(f["val"])
    sh = {}
    for (end, _), (filed, vals) in sorted(per.items(), key=lambda kv: kv[1][0]):
        if end not in sh:
            sh[end] = (sum(vals), filed)
    B["shares"] = sh
    bends = sorted(set().union(*[set(v) for v in B.values()]))
    brows = []
    for end in bends:
        got = [B[k][end] for k in B_KEYS if end in B[k]]
        brows.append([end, min(g[1] for g in got)] + [(B[k][end][0] if end in B[k] else None) for k in B_KEYS])
    return {"ccy": ccy, "q": qrows, "b": brows}


def submissions(cik):
    d = get(f"https://data.sec.gov/submissions/CIK{cik:010d}.json")
    if not d:
        return None
    r = d["filings"]["recent"]
    rows = list(zip(r["form"], r["filingDate"], r["accessionNumber"], r.get("items", [""] * len(r["form"])), r["primaryDocument"]))
    last = max((f for form, f, *_ in rows if form in PERIODIC), default=None)
    earn = [[f, a, doc] for form, f, a, items, doc in rows if form in ("8-K", "8-K/A") and "2.02" in (items or "")][:12]
    return {"name": d.get("name"), "last_filed": last, "earn": earn}


def main(argv):
    os.makedirs(OUT, exist_ok=True)
    force = "--all" in argv
    want = [a.upper() for a in argv if not a.startswith("--")]
    names = [t for t in TICKERS if not t.get("index") and not t.get("crypto") and t.get("group") not in ("Indexes & ETFs", "Sectors")
             and (not want or t["sym"].upper() in want)]
    idx_path = os.path.join(OUT, "_index.json")
    idx = json.load(open(idx_path)) if os.path.exists(idx_path) else {}
    ciks = idx.get("ciks") or {}
    stale = (idx.get("map_date") or "") < (dt.date.today() - dt.timedelta(days=7)).isoformat()
    if stale or not ciks or any(t["sym"] not in ciks and t["sym"] not in idx.get("no_cik", []) for t in names):
        got = cik_map(names)
        if got:
            ciks.update({s: list(v) for s, v in got.items()})
            idx["no_cik"] = sorted(set(idx.get("no_cik", [])) | {t["sym"] for t in names if t["sym"] not in got})
            idx["map_date"] = dt.date.today().isoformat()
    idx["ciks"] = ciks
    t0, n_full, n_new, skipped = time.time(), 0, 0, []
    for t in names:
        sym = t["sym"]
        if sym not in ciks:
            continue
        cik = ciks[sym][0]
        path = os.path.join(OUT, t["slug"] + ".json")
        old = json.load(open(path)) if os.path.exists(path) else None
        sub = submissions(cik)
        if sub is None:
            skipped.append(sym)
            continue
        if not sub["last_filed"]:
            skipped.append(sym)       # no 10-K/10-Q: a 40-F or 20-F filer, left to Yahoo's numbers
            continue
        if old and not force and old.get("last_filed") == sub["last_filed"]:
            if old.get("earn") != sub["earn"]:
                old["earn"] = sub["earn"]
                json.dump(old, open(path, "w"), separators=(",", ":"))
                n_new += 1
            continue
        facts = get(f"https://data.sec.gov/api/xbrl/companyfacts/CIK{cik:010d}.json")
        x = extract(facts) if facts else None
        if not x or not x["q"]:
            skipped.append(sym)
            continue
        x.update({"cik": cik, "name": sub["name"], "fetched": dt.date.today().isoformat(), "last_filed": sub["last_filed"], "earn": sub["earn"]})
        with open(path, "w") as f:
            json.dump(x, f, separators=(",", ":"))
        n_full += 1
    idx["run"] = dt.datetime.now(dt.timezone.utc).strftime("%Y-%m-%dT%H:%MZ")
    with open(idx_path, "w") as f:
        json.dump(idx, f, indent=0, sort_keys=True)
    print(f"sec: {len(ciks)} mapped, {n_full} refetched, {n_new} with new earnings 8-Ks, {len(skipped)} without 10-K/10-Q data "
          f"({', '.join(skipped[:12])}{'…' if len(skipped) > 12 else ''}) in {time.time() - t0:.0f}s")


if __name__ == "__main__":
    main(sys.argv[1:])
