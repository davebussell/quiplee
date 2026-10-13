"""The October 2026 model update, tested: the old and new standard signals side by side, and the
next refinements we tried (articles/old-vs-new-signal/, riskpieces.py).

    python tools/model_compare.py        # from the dev cache -> data/modelcompare.json (a few minutes)

The study is a snapshot: it is rerun by hand when the model changes, and the article reads the
JSON, so the nightly build doesn't redo it.

At every month-end since 2011, each covered stock gets its points on every factor exactly as Your
signal would have scored it then, from numbers public at the time (as in factorgrade.py), and each
model's Buy (60+), Hold or Sell (40 or less) is checked against what the stock did next against its
market (the S&P 500, or the TSX): over a month, three months and a year, and how far it fell in the
following year.

The old standard was half analysts' upside, which has no stored history. Rating changes with price
targets are on file from late 2023 (data/events/, tools/fetch_events.py), so from July 2024 the old
signal is rebuilt from them: each firm's latest target in the past year, averaged over three or more
firms, ignoring any target more than double or less than half the price on the day it was set
(targets aren't split-adjusted). That window is short and mostly a rising market; the article says so.
"""
import datetime as dt
import glob
import json
import os

import numpy as np
import pandas as pd

from .content import TIMED
from . import secfund
from .quality import BOUNDS

ROOT = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
OUT = os.path.join(ROOT, "data", "modelcompare.json")
START = pd.Timestamp("2006-01-01")
AN_START = pd.Timestamp("2024-07-01")     # enough target history (12 months back) for most names
BUY, SELL = 60, 40
H1, H3, H12 = 21, 63, 252


def _rank(s):
    """Points 0-100 by rank among the names that have a value (factors.py / factorgrade.py)."""
    s = s.dropna()
    if len(s) < 2:
        return pd.Series(50.0, index=s.index)
    return (100 * (s.rank(method="average") - 1) / (len(s) - 1)).round()


def _targets(t, c):
    """[(day, firm, target)] from the stored rating changes, keeping only targets within half to
    double the price on the day they were set."""
    path = os.path.join(ROOT, "data", "events", t["slug"] + ".json")
    if not os.path.exists(path):
        return []
    try:
        rs = json.load(open(path)).get("ratings") or []
    except Exception:
        return []
    out = []
    for r in rs:
        if len(r) < 7 or not r[6]:
            continue
        d = pd.Timestamp(r[0][:10])
        i = c.index.searchsorted(d, side="right") - 1
        if i < 0:
            continue
        p = float(c.iloc[i])
        if p > 0 and 0.5 <= float(r[6]) / p <= 2.0:
            out.append((d, r[1], float(r[6]), r[5] or ""))
    return sorted(out)


def _consensus(tg, d):
    """(average target, firms, share of last-90-day actions that raised a target) at d."""
    last, acts = {}, []
    for day, firm, tgt, act in tg:
        if day > d:
            break
        if day >= d - pd.Timedelta(days=365):
            last[firm] = tgt
        if day >= d - pd.Timedelta(days=90) and act in ("Raises", "Lowers"):
            acts.append(1 if act == "Raises" else 0)
    tgt = float(np.mean(list(last.values()))) if len(last) >= 3 else None
    rev = (float(np.mean(acts)) if len(acts) >= 3 else None)
    return tgt, len(last), rev


def panel(site):
    """One row per stock and month-end: each factor's raw value or points, and what came next."""
    from .factorgrade import _stocks, _plays_share
    from .factors import offhigh_points
    from .engine import _read, PRICE_DIR
    stocks = _stocks(site)
    spx = site.prices["^GSPC"]["close"]
    cal = spx.index
    last = len(cal) - 1 - H1
    months = pd.Series(cal[:last + 1], index=cal[:last + 1]).groupby(cal[:last + 1].to_period("M")).last()
    dates = pd.DatetimeIndex([d for d in months.values if d >= START])
    spx_ma = spx.rolling(200).mean()
    spx_up = {d: bool(spx.loc[:d].iloc[-1] > spx_ma.loc[:d].iloc[-1]) for d in dates}
    try:
        fx = _read("CAD=X", PRICE_DIR)["close"]
    except Exception:
        fx = None
    rows = []
    for t in stocks:
        c = site.prices[t["sym"]]["close"]
        b = site.prices[t["bench"]]["close"]
        cv, bv = c.values.astype(float), b.values.astype(float)
        bhi = b.rolling(252, min_periods=120).max().values
        ma = c.rolling(200).mean().values
        hi = c.rolling(252, min_periods=120).max().values
        vol = (c.pct_change().rolling(252, min_periods=120).std() * np.sqrt(252)).values
        pos = c.index.searchsorted(dates, side="right") - 1
        bpos = b.index.searchsorted(dates, side="right") - 1
        k, n = _plays_share(site, t, dates)
        tg = _targets(t, c)
        for di, d in enumerate(dates):
            i, j = pos[di], bpos[di]
            if i < 252 or j < 0 or cv[i] <= 0 or bv[j] <= 0 or i + H1 >= len(cv) or j + H1 >= len(bv):
                continue
            p0 = cv[i]
            r = {"d": d, "sym": t["sym"], "plays": (100 * k[di] / n[di]) if n[di] >= 20 else np.nan,
                 "dd": p0 / hi[i] - 1 if hi[i] > 0 else np.nan, "vol": vol[i],
                 "gap": p0 / ma[i] - 1 if ma[i] > 0 else np.nan,
                 "mom": p0 / cv[i - 252] - 1 if cv[i - 252] > 0 else np.nan,
                 "mom121": cv[i - 21] / cv[i - 252] - 1 if cv[i - 252] > 0 else np.nan,
                 "spx_up": spx_up[d], "bdd": bv[j] / bhi[j] - 1 if bhi[j] > 0 else np.nan}
            for h, key in ((H1, "1"), (H3, "3"), (H12, "12")):
                if i + h < len(cv) and j + h < len(bv):
                    r["ex" + key] = (cv[i + h] / p0 - 1) - (bv[j + h] / bv[j] - 1)
                    r["ab" + key] = cv[i + h] / p0 - 1
            if i + H12 < len(cv):
                r["fdd"] = float(cv[i:i + H12 + 1].min() / p0 - 1)
            if tg and d >= AN_START:
                tgt, nf, rev = _consensus(tg, d)
                if tgt:
                    u = tgt / p0 - 1
                    r["up"] = u if -0.6 <= u <= 1.0 else np.nan
                r["rev"] = rev
            if secfund.has(t):
                fxd = float(fx.iloc[fx.index.searchsorted(d, side="right") - 1]) if fx is not None and len(fx) else None
                rr = secfund.ratios(t, p0, d, fxd)
                for key in ("roe", "de"):
                    v = rr.get(key)
                    if isinstance(v, str):
                        r[key + "_fix"] = 0
                    elif v is not None and BOUNDS.get(key, (-1e18, 1e18))[0] <= v <= BOUNDS.get(key, (-1e18, 1e18))[1]:
                        r[key] = v
            rows.append(r)
    df = pd.DataFrame(rows)
    # points, as Your signal scores them
    df["p_offhigh"] = df.dd.map(lambda v: offhigh_points(v) if pd.notna(v) else np.nan)
    for fl in (0.20, 0.40):
        df[f"p_off{int(fl * 100)}"] = df.dd.map(lambda v, fl=fl: round(100 * min(max(1 + v / fl, 0), 1)) if pd.notna(v) else np.nan)
    df["p_offrel"] = (100 * (1 + (df.dd - df.bdd) / 0.30).clip(0, 1)).round()
    floor = (1.5 * df.vol).clip(0.15, 0.60)
    df["p_offvol"] = (100 * (1 + df.dd / floor).clip(0, 1)).round()
    for raw, col in (("gap", "p_trend"), ("mom", "p_mom"), ("mom121", "p_mom121"), ("rev", "p_rev"), ("roe", "p_roe")):
        df[col] = df.groupby("d")[raw].transform(_rank) if raw in df else np.nan
    if "de" in df:
        df["p_de"] = 100 - df.groupby("d")["de"].transform(_rank)
        if "de_fix" in df:
            df.loc[df.de_fix.eq(0), "p_de"] = 0
    if "roe_fix" in df:
        df.loc[df.roe_fix.eq(0), "p_roe"] = 0
    from .stockview import upside_points
    df["p_up"] = df.get("up", pd.Series(np.nan, index=df.index)).map(lambda u: 100 * upside_points(u) if pd.notna(u) else np.nan)
    df["p_upcap"] = np.where(df.gap < 0, np.minimum(df.p_up, 50), df.p_up)
    df["p_plays"] = df.plays.round()
    return df


MODELS = {
    # key: (label, {points column: weight}, needs analyst history)
    "new": ("Now: plays 40, off the high 30, trend 30", {"p_plays": 40, "p_offhigh": 30, "p_trend": 30}, False),
    "plays": ("Plays only", {"p_plays": 100}, False),
    "old": ("Before: plays 50, analysts' upside 50", {"p_plays": 50, "p_up": 50}, True),
    "oldcap": ("Before, with the upside cap", {"p_plays": 50, "p_upcap": 50}, True),
    # refinements tried
    "off20": ("Exit rule at 20% off the high", {"p_plays": 40, "p_off20": 30, "p_trend": 30}, False),
    "off40": ("Exit rule at 40% off the high", {"p_plays": 40, "p_off40": 30, "p_trend": 30}, False),
    "offvol": ("Exit rule scaled to each stock's volatility", {"p_plays": 40, "p_offvol": 30, "p_trend": 30}, False),
    "mom121": ("12-month momentum (skipping the last month) for trend", {"p_plays": 40, "p_offhigh": 30, "p_mom121": 30}, False),
    "offrel": ("Exit rule measured against the market's own fall", {"p_plays": 40, "p_offrel": 30, "p_trend": 30}, False),
    "quality": ("Plus quality: return on equity and debt", {"p_plays": 30, "p_offhigh": 25, "p_trend": 25, "p_roe": 10, "p_de": 10}, False),
    "upside15": ("Plus capped analysts' upside at 15%", {"p_plays": 35, "p_offhigh": 25, "p_trend": 25, "p_upcap": 15}, True),
    "rev15": ("Plus analysts' target revisions at 15%", {"p_plays": 35, "p_offhigh": 25, "p_trend": 25, "p_rev": 15}, True),
}


def score(df, w):
    """Weighted average of the factors a stock has, if they carry at least half the weight (factors.score)."""
    num = pd.Series(0.0, index=df.index)
    have = pd.Series(0.0, index=df.index)
    for col, wt in w.items():
        v = df[col]
        ok = v.notna()
        num += np.where(ok, v * wt, 0)
        have += np.where(ok, wt, 0)
    s = num / have.replace(0, np.nan)
    s[have < sum(w.values()) / 2] = np.nan
    return s.round()


def calls(s, buy=BUY, sell=SELL):
    return pd.Series(np.select([s >= buy, s <= sell], [1, -1], 0), index=s.index).where(s.notna())


def sticky(df, s, out=50):
    """Hysteresis: a Buy stays a Buy until the score falls below `out`; a Sell stays until it rises above it."""
    g = calls(s)
    res = pd.Series(np.nan, index=df.index)
    for _, idx in df.groupby("sym").groups.items():
        idx = df.loc[idx].sort_values("d").index
        prev = None
        for ix in idx:
            sc, c = s[ix], g[ix]
            if pd.isna(sc):
                prev = None
                continue
            if prev == 1 and c != 1 and sc >= out:
                c = 1
            elif prev == -1 and c != -1 and sc <= out:
                c = -1
            res[ix] = c
            prev = c
    return res


def record(df, g, mask=None):
    """How a set of calls did: Buys and Sells against the market, and what came after."""
    m = g.notna() if mask is None else (g.notna() & mask)
    x = df[m]
    gg = g[m]
    out = {"n": int(m.sum())}
    for key, sub in (("buy", x[gg == 1]), ("hold", x[gg == 0]), ("sell", x[gg == -1])):
        e12, e3 = sub.ex12.dropna(), sub.ex3.dropna()
        out[key] = {"n": len(sub), "share": round(len(sub) / max(len(x), 1), 4),
                    "beat12": round(float((e12 > 0).mean()), 4) if len(e12) else None,
                    "beat3": round(float((e3 > 0).mean()), 4) if len(e3) else None,
                    "med12": round(float(e12.median()), 4) if len(e12) else None,
                    "fell30": round(float((sub.fdd.dropna() <= -0.30).mean()), 4) if sub.fdd.notna().any() else None,
                    "fdd": round(float(sub.fdd.dropna().median()), 4) if sub.fdd.notna().any() else None,
                    "p10": round(float(e12.quantile(0.10)), 4) if len(e12) else None,
                    "lag30": round(float((e12 <= -0.30).mean()), 4) if len(e12) else None,
                    "n12": len(e12), "n3": len(e3)}
    b, s_ = out["buy"], out["sell"]
    out["edge12"] = round(b["beat12"] - s_["beat12"], 4) if b["beat12"] is not None and s_["beat12"] is not None else None
    out["edge3"] = round(b["beat3"] - s_["beat3"], 4) if b["beat3"] is not None and s_["beat3"] is not None else None
    # a basket of the Buys, rebalanced monthly, against each stock's market
    mb = x[gg == 1].groupby("d").ex1.mean()
    ms = x[gg == -1].groupby("d").ex1.mean()
    out["buy_basket"] = round(float(mb.mean() * 12), 4) if len(mb) else None
    out["sell_basket"] = round(float(ms.mean() * 12), 4) if len(ms) else None
    return out


def flips(df, g):
    """Signal changes per stock per year, month-end to month-end."""
    x = pd.DataFrame({"sym": df.sym, "d": df.d, "g": g}).dropna().sort_values(["sym", "d"])
    ch = (x.groupby("sym").g.diff().fillna(0) != 0).sum()
    yrs = len(x) / 12
    return round(float(ch / yrs), 3) if yrs else None


def study(site):
    df = panel(site)
    era = {"e1": df.d < pd.Timestamp("2011-01-01"), "e2": (df.d >= pd.Timestamp("2011-01-01")) & (df.d < pd.Timestamp("2019-01-01")),
           "e3": df.d >= pd.Timestamp("2019-01-01")}
    an = df.d >= AN_START
    out = {"built": dt.date.today().isoformat(), "since": df.d.min().strftime("%Y-%m-%d"), "to": df.d.max().strftime("%Y-%m-%d"),
           "to12": df[df.ex12.notna()].d.max().strftime("%Y-%m-%d"), "stocks": int(df.sym.nunique()),
           "an_since": AN_START.strftime("%Y-%m-%d"), "an_stocks": int(df[an & df.get("up", pd.Series(np.nan, index=df.index)).notna()].sym.nunique()),
           "models": {}}
    S = {k: score(df, w) for k, (_, w, _) in MODELS.items()}
    G = {k: calls(s) for k, s in S.items()}
    G["sticky"] = sticky(df, S["new"])
    guard = lambda sc, lvl=-0.15: sc.where(~(df.bdd <= lvl), S["plays"])  # in a market down 15%+ from its high, the plays alone
    G["guard"] = calls(guard(S["new"]))
    G["guard10"] = calls(guard(S["new"], -0.10))
    G["guard20"] = calls(guard(S["new"], -0.20))
    G["guardsticky"] = sticky(df, guard(S["new"]))
    G["guardup"] = calls(guard(S["upside15"]))
    G["relsticky"] = sticky(df, S["offrel"])
    G["mktfilter"] = calls(S["new"], buy=BUY).where(df.spx_up | (S["new"] >= 70) | (S["new"] < BUY), 0)   # Buy needs 70 when the S&P 500 is below its 200-day
    labels = {k: v[0] for k, v in MODELS.items()} | {"sticky": "A Buy or Sell holds until the score crosses 50", "mktfilter": "Buy needs 70 while the S&P 500 is below its 200-day",
                                                 "guard": "Plays alone while the market is 15% or more below its high",
                                                 "relsticky": "Exit rule against the market, and sticky calls",
                                                 "guard10": "Plays alone while the market is 10% or more below its high",
                                                 "guard20": "Plays alone while the market is 20% or more below its high",
                                                 "guardsticky": "Market guard and sticky calls together",
                                                 "guardup": "Market guard plus capped analysts' upside at 15%"}
    fall = df.dd <= -0.20
    for k, g in G.items():
        need_an = MODELS.get(k, (None, None, False))[2] or k == "guardup"
        rec = {"label": labels[k], "an_only": need_an}
        if not need_an:
            rec["all"] = record(df, g)
            for ek, em in era.items():
                rec[ek] = record(df, g, em)
            rec["fall"] = record(df, g, fall)
            rec["flips"] = flips(df, g)
            rec["years"] = {str(y): record(df, g, df.d.dt.year == y)["edge12"] for y in sorted(df.d.dt.year.unique())}
        rec["an"] = record(df, g, an)
        rec["an_fall"] = record(df, g, an & fall)
        rec["an_flips"] = flips(df[an], g[an])
        out["models"][k] = rec
    # old vs new, call by call, in the window where both can be scored
    both = an & G["old"].notna() & G["new"].notna()
    ct = pd.crosstab(G["old"][both], G["new"][both])
    out["cross_an"] = {f"{int(a)}|{int(b)}": int(ct.loc[a, b]) for a in ct.index for b in ct.columns}
    # where they disagreed: old Buy / new Sell and the reverse
    dis = {}
    for name, (a, b) in {"oldbuy_newsell": (1, -1), "oldsell_newbuy": (-1, 1), "oldbuy_newbuy": (1, 1), "oldbuy_newhold": (1, 0)}.items():
        x = df[both & (G["old"] == a) & (G["new"] == b)]
        dis[name] = {"n": len(x), "beat3": round(float((x.ex3.dropna() > 0).mean()), 4) if x.ex3.notna().any() else None,
                     "med3": round(float(x.ex3.dropna().median()), 4) if x.ex3.notna().any() else None,
                     "beat12": round(float((x.ex12.dropna() > 0).mean()), 4) if x.ex12.notna().any() else None,
                     "med12": round(float(x.ex12.dropna().median()), 4) if x.ex12.notna().any() else None,
                     "n12": int(x.ex12.notna().sum()), "dd": round(float(x.dd.median()), 4) if len(x) else None}
    out["disagree"] = dis
    # how the rebuilt targets compare with today's published consensus
    out["upside_check"] = upside_check(site, df)
    return out


def upside_check(site, df):
    from .stockview import outlook
    from .content import TICKERS
    by = {t["sym"]: t for t in TICKERS}
    last = df[df.d == df.d.max()].dropna(subset=["up"])
    pairs = []
    for _, r in last.iterrows():
        ol = outlook(site, by[r.sym]) if r.sym in by else None
        if ol and ol.get("upside") is not None and ol.get("ok"):
            pairs.append((r.up, ol["upside"]))
    if len(pairs) < 10:
        return None
    a = np.array(pairs)
    return {"n": len(a), "corr": round(float(np.corrcoef(a[:, 0], a[:, 1])[0, 1]), 3),
            "med_gap": round(float(np.median(np.abs(a[:, 0] - a[:, 1]))), 4)}


def load():
    try:
        return json.load(open(OUT))
    except Exception:
        return {}
