"""Point-in-time company numbers from SEC filings (data/sec/<slug>.json, tools/fetch_sec.py).

    snap(t, when)                 the last four quarters and the balance sheet as filed by `when`
    ratios(t, price, when, fx)    P/E, P/S, P/B, dividend yield, growth, margin, ROE, debt to equity

Only numbers filed on or before `when` are used, so the same functions serve tonight's
signal and the backtests that grade each factor (tools/qstrat/factorgrade.py). Prices are
converted to the filing currency with the CAD/USD rate when the two differ (Shopify trades
in Canadian dollars on the TSX and reports in U.S. dollars).
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


def load(slug):
    if slug not in _CACHE:
        p = os.path.join(DIR, slug + ".json")
        try:
            _CACHE[slug] = json.load(open(p)) if os.path.exists(p) else None
        except Exception:
            _CACHE[slug] = None
    return _CACHE[slug]


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
