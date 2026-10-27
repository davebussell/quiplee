"""Point-in-time company numbers from SEC filings (data/sec/<slug>.json, tools/fetch_sec.py).

    snap(t, when)                 the last four quarters and the balance sheet as filed by `when`
    ratios(t, price, when, fx)    P/E, P/S, P/B, dividend yield, growth, margin, ROE, debt to equity

Only numbers filed on or before `when` are used, so the same functions serve tonight's
signal and the backtests that grade each factor (tools/qstrat/factorgrade.py). Prices are
converted to the filing currency with the CAD/USD rate when the two differ (Shopify trades
in Canadian dollars on the TSX and reports in U.S. dollars).

Share basis (AUD-46). Prices are split-adjusted to today's shares, but a filing reports EPS,
dividends per share and share counts on the shares of its day, and fetch_sec keeps each number
as first filed. So every per-share number is put on today's basis first (norm()): EPS and
dividends divided, share counts multiplied, by every split after the filing. The splits come
from Yahoo (data/events/<slug>.json "splits", tools/fetch_events.py) and, for a company without
that list yet, are read from the filings themselves (inferred_splits()): the share count and the
weighted share count both jump by a split ratio between two filings while equity barely moves,
which an acquisition or a share sale doesn't do. Share counts entered a thousand or a million
times off (an XBRL units slip) are rescaled first.
"""
import datetime as dt
import json
import os

DIR = os.path.join(os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__)))), "data", "sec")
Q_KEYS = ["rev", "ni", "eps", "ocf", "capex", "gp", "opi", "dps"]     # summed over four quarters
WSH = 10                                                                # row index of the quarter's diluted share count
B_KEYS = ["equity", "debt", "cash", "shares"]
STALE_DAYS = 200        # a last quarter older than this is stale (a missed filing, a delisting)
_CACHE = {}


EVENTS = os.path.join(os.path.dirname(DIR), "events")
EPS, DPS = 4, 9                                                         # q row indexes of the per-share numbers
SHARES = 5                                                              # b row index of the share count
SPLIT_RATIOS = (2, 3, 4, 5, 6, 7, 8, 10, 12, 15, 20, 25, 30, 40, 50, 1.5)


def load(slug):
    """The filings on today's share basis (norm()), or None."""
    if slug not in _CACHE:
        p = os.path.join(DIR, slug + ".json")
        try:
            raw = json.load(open(p)) if os.path.exists(p) else None
        except Exception:
            raw = None
        _CACHE[slug] = norm(raw, _yahoo_splits(slug)) if raw else None
    return _CACHE[slug]


def _yahoo_splits(slug):
    """[(day, ratio)] from data/events, or None when that file has no split list yet."""
    try:
        sp = json.load(open(os.path.join(EVENTS, slug + ".json"))).get("splits")
    except Exception:
        return None
    if sp is None:
        return None
    return [(d[:10], float(r)) for d, r in sp if r and float(r) > 0 and float(r) != 1]


def _ratio(r, tol):
    """The split ratio r is within tol of (4, or 0.25 for a 1-for-4), else None."""
    for k in SPLIT_RATIOS:
        if abs(r / k - 1) <= tol:
            return k
        if abs(r * k - 1) <= tol:
            return 1 / k
    return None


def _unit_fix(rows, i):
    """Rescale share counts a thousand, million or billion times off (an XBRL units slip), walking
    back from the latest filing, and drop any other jump of 60x or more."""
    later = None
    for r in sorted(rows, key=lambda r: r[1], reverse=True):
        v = r[i] if len(r) > i else None
        if not v:
            continue
        if later:
            q = v / later
            for m in (1e3, 1e6, 1e9):
                if abs(q / m - 1) < 0.08:
                    r[i] = v / m
                    break
                if abs(q * m - 1) < 0.08:
                    r[i] = v * m
                    break
            else:
                if q > 60 or q < 1 / 60:
                    r[i] = None
                    continue
        later = r[i]


def _days(a, b):
    return abs((dt.date.fromisoformat(a) - dt.date.fromisoformat(b)).days)


def inferred_splits(q, b):
    """[(first filing on the new basis, ratio)] read from the filings: the cover-page share count
    jumps by a split ratio (within 2.5%; 2% for a 3-for-2) between two filings, the weighted
    share count jumps by the same ratio within about a quarter (8%; 1% for a 3-for-2) while
    quarterly revenue doesn't (between neighbouring quarters; unless no later quarter is filed yet and the jump is within 0.5%
    of a whole ratio), and equity rises by less than 45% of itself (80% for a split of 3 or
    more). An acquisition paid in shares, a listing or a share sale raises equity with the
    shares; buybacks can shrink it, so a fall doesn't count against a split."""
    qs = sorted([r for r in q if len(r) > WSH and r[WSH]], key=lambda r: r[1])
    bs = sorted([r for r in b if r[SHARES]], key=lambda r: r[1])
    eqs = sorted([r for r in b if r[2] is not None], key=lambda r: r[1])
    out = []
    for A, C in zip(bs, bs[1:]):
        r = C[SHARES] / A[SHARES]
        k = _ratio(r, 0.025)
        three2 = k in (1.5, 1 / 1.5)
        if not k or (three2 and not _ratio(r, 0.02)):
            continue
        ea = [x[2] for x in eqs if x[1] <= A[1]]
        ec = [x[2] for x in eqs if x[1] <= C[1]]
        if not ea or not ec or ea[-1] == ec[-1] or ea[-1] == 0:
            continue
        whole = k >= 3 or k <= 1 / 3
        if ec[-1] - ea[-1] > (0.8 if whole else 0.45) * abs(ea[-1]):
            continue
        # the weighted share count: the transition nearest the cover-page jump whose ratio is closest to k
        best = None
        for X, Y in zip(qs, qs[1:]):
            if min(_days(Y[1], C[1]), _days(X[1], C[1])) > 130 or Y[1] < A[1]:
                continue
            rq = Y[WSH] / X[WSH]
            gap = abs(rq / k - 1)
            if best is None or gap < best[0]:
                adjacent = _days(X[0], Y[0]) <= 120        # quarterly revenue is only compared between neighbouring quarters
                best = (gap, Y[1], (Y[2] / X[2]) if adjacent and X[2] and Y[2] and X[2] > 0 else None)
        tol = 0.01 if three2 else 0.08
        if best and best[0] <= tol and (best[2] is None or 0.6 <= best[2] <= 1.6):
            out.append((min(C[1], best[1]), k))
        elif not any(x[1] >= C[1] for x in qs) and (k >= 2 or k <= 0.5) and _ratio(r, 0.005):
            out.append((C[1], k))
    return out


def norm(d, splits=None):
    """A copy of one company's filings with every per-share number on today's share basis.
    splits: [(day, ratio)] from Yahoo, or None to read them from the filings."""
    q = [list(r) for r in d.get("q", [])]
    b = [list(r) for r in d.get("b", [])]
    _unit_fix(q, WSH)
    _unit_fix(b, SHARES)
    src = "yahoo" if splits is not None else "filings"
    if splits is None:
        splits = inferred_splits(q, b)
    out = dict(d, q=q, b=b, splits=[[day, k] for day, k in splits], split_src=src)
    if not splits:
        return out

    def factor(filed):
        f = 1.0
        for day, k in splits:
            if filed < day:
                f *= k
        return f
    for r in q:
        f = factor(r[1])
        if f != 1:
            for i in (EPS, DPS):
                if r[i] is not None:
                    r[i] = r[i] / f
            if len(r) > WSH and r[WSH]:
                r[WSH] = r[WSH] * f
    for r in b:
        f = factor(r[1])
        if f != 1 and r[SHARES]:
            r[SHARES] = r[SHARES] * f
    # a quarter fetch_sec derived across a split (Q4 = the year less three quarters as first filed)
    # mixes the two bases: near each split, an EPS that disagrees with net income over shares by
    # more than 2x is replaced by that, and a dividend that turned negative by its neighbours'
    qs = sorted(q, key=lambda r: r[0])
    for day, _ in splits:
        for j, r in enumerate(qs):
            if not 0 <= (dt.date.fromisoformat(r[1]) - dt.date.fromisoformat(day)).days <= 400:   # through the next 10-K
                continue
            near = [x[WSH] for x in qs[max(0, j - 1):j + 2] if len(x) > WSH and x[WSH]]
            sh = (r[WSH] if len(r) > WSH and r[WSH] else None) or (near[-1] if near else None)
            if r[EPS] is not None and r[3] is not None and sh:
                implied = r[3] / sh
                if implied and (r[EPS] / implied < 0 or not 0.5 <= abs(r[EPS] / implied) <= 2):
                    r[EPS] = round(implied, 4)
            if r[DPS] is not None and r[DPS] < 0:
                nb = [x[DPS] for x in qs[max(0, j - 2):j + 3] if x is not r and x[DPS] is not None and x[DPS] >= 0]
                r[DPS] = sorted(nb)[len(nb) // 2] if nb else None
    return out


def has(t):
    return load(t["slug"]) is not None


def _iso(d):
    return d if isinstance(d, str) else d.strftime("%Y-%m-%d")


def _sum4(rows, i):
    vals = [r[i] for r in rows]
    return None if any(v is None for v in vals) else sum(vals)


def snap(t, when):
    """{"end", "filed", "ccy", ttm values, prior-year ttm values ("p_rev"...), balance sheet values} as known on `when`, or None."""
    d = load(t["slug"])
    if not d:
        return None
    w = _iso(when)
    qs = [r for r in d["q"] if r[1] <= w]
    if len(qs) < 4:
        return None
    last8 = qs[-8:]
    # the last four quarters must be consecutive (about a year from first start to last end)
    cur = last8[-4:]
    span = (dt.date.fromisoformat(cur[-1][0]) - dt.date.fromisoformat(cur[0][0])).days
    if not 250 <= span <= 310:
        return None
    if (dt.date.fromisoformat(w) - dt.date.fromisoformat(cur[-1][0])).days > STALE_DAYS:
        return None
    out = {"end": cur[-1][0], "filed": max(r[1] for r in cur), "ccy": d.get("ccy") or "USD"}
    for i, k in enumerate(Q_KEYS):
        out[k] = _sum4(cur, i + 2)
    if len(last8) == 8:
        prev = last8[:4]
        pspan = (dt.date.fromisoformat(cur[0][0]) - dt.date.fromisoformat(prev[-1][0])).days
        if 80 <= pspan <= 120:
            for i, k in enumerate(Q_KEYS):
                out["p_" + k] = _sum4(prev, i + 2)
    if out.get("dps") is None and any(r[9] is not None for r in cur):
        out["dps"] = sum(r[9] or 0 for r in cur)       # a quarter with no dividend reported counts as none
    wsh = [r[WSH] for r in cur if len(r) > WSH and r[WSH]]
    out["wsh"] = wsh[-1] if wsh else None
    bs = [r for r in d["b"] if r[1] <= w]
    for i, k in enumerate(B_KEYS):
        got = [r for r in bs if r[i + 2] is not None]
        out[k] = got[-1][i + 2] if got else None
        if got:
            out[k + "_end"] = got[-1][0]
    return out


def _to_ccy(price, cur, ccy, fx):
    """A price in the trading currency (cur "$" or "C$"), in the filing currency, or None when we can't convert."""
    trade = "CAD" if cur == "C$" else "USD"
    if trade == ccy:
        return price
    if not fx:
        return None
    if trade == "CAD" and ccy == "USD":
        return price / fx
    if trade == "USD" and ccy == "CAD":
        return price * fx
    return None


def ratios(t, price, when, fx=None):
    """{"pe", "ps", "pb", "dy", "rg", "eg", "pm", "roe", "de", "src"} from filings known on `when`
    (missing keys mean no number). P/E of a loss-maker is reported as "loss"."""
    s = snap(t, when)
    if not s:
        return {}
    px = _to_ccy(price, t.get("cur", "$"), s["ccy"], fx)
    out = {"src": f"SEC filings to {s['end']}"}
    if px is None or px <= 0:
        return out
    eps, rev, ni, eq, debt = s.get("eps"), s.get("rev"), s.get("ni"), s.get("equity"), s.get("debt")
    sh = s.get("shares") or s.get("wsh")
    if eps is not None:
        out["pe"] = px / eps if eps > 0 else "loss"
    mcap = px * sh if sh else None
    if mcap and rev and rev > 0:
        out["ps"] = mcap / rev
    if mcap and eq is not None:
        out["pb"] = mcap / eq if eq > 0 else "negative"
    if s.get("dps") is not None:
        out["dy"] = s["dps"] / px
    if rev and s.get("p_rev") and s["p_rev"] > 0:
        out["rg"] = rev / s["p_rev"] - 1
    if eps is not None and s.get("p_eps") and s["p_eps"] > 0:
        out["eg"] = eps / s["p_eps"] - 1
    if ni is not None and rev and rev > 0:
        out["pm"] = ni / rev
    if ni is not None and eq and eq > 0:
        out["roe"] = ni / eq
    if eq is not None:
        if eq <= 0:
            out["de"] = "negative"
        elif debt is not None:
            out["de"] = debt / eq
    return out
