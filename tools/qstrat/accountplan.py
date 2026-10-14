"""Planning an account, not just picking stocks (AUD-38).

Two things, both built on the prices the site already has:

* data/px/<slug>.json: each covered name's weekly closes since 2006 (adjusted for splits and
  dividends), for the watchlist's account check (assets/watchlist.js), which runs a reader's own
  mix through the same history in the browser.
* study(site): what holding 1 to 30 stocks, an index core with a slice of picks, per-stock caps and
  rebalancing did since 2006, from thousands of random portfolios of covered stocks. Run by hand with
  tools/account_study.py into data/accountplan.json; guide_page() reads it for /guides/plan-an-account/.

Everything here is a record of what mixes did, not advice: the site doesn't know anyone's goals,
timeline, taxes or other money, and the stocks are today's survivors, which flatters single stocks.
"""
import datetime as dt
import html
import json
import os

import numpy as np
import pandas as pd

from .content import TICKERS

e = html.escape
ROOT = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
OUT = os.path.join(ROOT, "data", "accountplan.json")
PATH = "guides/plan-an-account/"
START = pd.Timestamp("2006-01-06")          # a Friday: weekly closes run Friday to Friday
CORES = {"SPY": "the S&P 500 (SPY)", "XIU.TO": "the TSX 60 (XIU)"}
CRASHES = [("2008", "2007-10-12", "2009-03-06", "2008–09 financial crisis"),
           ("2020", "2020-02-21", "2020-03-20", "2020 COVID crash"),
           ("2022", "2021-12-31", "2022-10-14", "2022 rate shock")]


def weekly(site, sym):
    d = (site.prices or {}).get(sym)
    if d is None or "close" not in d or not len(d):
        return None
    return d["close"].resample("W-FRI").last()


def _cal(site):
    s = weekly(site, "SPY")
    return s[s.index >= START].index


def px_json(site, t, cal):
    """{"s", "c", "d0", "w": weekly closes on the shared Friday calendar, null before the name traded}."""
    w = weekly(site, t["sym"])
    if w is None:
        return None
    w = w.reindex(cal)
    vals = [None if pd.isna(v) else float(f"{v:.5g}") for v in w.values]
    return json.dumps({"s": t["sym"], "c": t.get("cur", "$"), "d0": cal[0].strftime("%Y-%m-%d"), "w": vals}, separators=(",", ":"))


def write_px(site, out):
    folder = os.path.join(out, "data", "px")
    os.makedirs(folder, exist_ok=True)
    cal = _cal(site)
    n = 0
    for t in TICKERS:
        if (t["sym"], "buy-and-hold") not in site.R or t.get("requested"):
            continue
        j = px_json(site, t, cal)
        if j:
            with open(os.path.join(folder, t["slug"] + ".json"), "w", encoding="utf-8") as f:
                f.write(j)
            n += 1
    return n


# ------------------------------------------------------------------ the study
def _stats(r, weeks):
    """r: (draws, weeks) weekly returns -> CAGR, worst fall, worst week per draw."""
    g = np.cumprod(1 + r, axis=1)
    cagr = g[:, -1] ** (52 / weeks) - 1
    dd = (g / np.maximum.accumulate(g, axis=1) - 1).min(axis=1)
    return cagr, dd, r.min(axis=1), g


def _summary(cagr, dd, wk, spy_cagr, falls=None):
    q = lambda a, p: round(float(np.percentile(a, p)), 4)
    out = {"cagr_med": q(cagr, 50), "cagr_p10": q(cagr, 10), "cagr_p90": q(cagr, 90), "dd_med": q(dd, 50), "dd_p10": q(dd, 10),
           "dd50": round(float((dd <= -0.5).mean()), 4), "wk_med": q(wk, 50), "beat_all": round(float((cagr > spy_cagr).mean()), 4),
           "lost": round(float((cagr < 0).mean()), 4)}
    if falls:
        out["falls"] = {k: {"med": q(v, 50), "p10": q(v, 10)} for k, v in falls.items()}
    return out


def study(site, draws=2000, seed=7):
    from .render import is_stock
    rng = np.random.default_rng(seed)
    cal = _cal(site)
    cols, syms = [], []
    for t in TICKERS:
        if not is_stock(t) or t.get("requested") or (t["sym"], "buy-and-hold") not in site.R:
            continue
        w = weekly(site, t["sym"])
        if w is None:
            continue
        w = w.reindex(cal)
        if w.iloc[:2].isna().any() or w.isna().mean() > 0.01:
            continue                      # full history since 2006 only, so every draw covers the same weeks
        cols.append(w.ffill().values)
        syms.append(t["sym"])
    P = np.array(cols).T                  # weeks x stocks
    R = P[1:] / P[:-1] - 1
    spy = weekly(site, "SPY").reindex(cal).ffill().values
    rs = spy[1:] / spy[:-1] - 1
    weeks = R.shape[0]
    spy_cagr, spy_dd, spy_wk, spy_g = _stats(rs[None, :], weeks)
    # the "index" the picks are measured against is every one of the same stocks in equal amounts, so
    # survivors are compared with survivors (SPY includes the companies that failed; these stocks don't)
    ru = R.mean(axis=1)
    u_cagr, u_dd, u_wk, u_g = _stats(ru[None, :], weeks)
    dates = cal[1:]
    win = {k: (int(np.searchsorted(dates, pd.Timestamp(a))), int(np.searchsorted(dates, pd.Timestamp(b)))) for k, a, b, _ in CRASHES}

    def falls(g):
        return {k: g[:, j] / g[:, i] - 1 for k, (i, j) in win.items()}
    spy_f = {k: round(float(v[0]), 4) for k, v in falls(spy_g).items()}
    out = {"built": dt.date.today().isoformat(), "since": cal[0].strftime("%Y-%m-%d"), "to": cal[-1].strftime("%Y-%m-%d"),
           "stocks": len(syms), "draws": draws, "years": round(weeks / 52, 1),
           "spy": {"cagr": round(float(spy_cagr[0]), 4), "dd": round(float(spy_dd[0]), 4), "wk": round(float(spy_wk[0]), 4), "falls": spy_f},
           "all": {"cagr": round(float(u_cagr[0]), 4), "dd": round(float(u_dd[0]), 4), "wk": round(float(u_wk[0]), 4),
                   "falls": {k: round(float(v[0]), 4) for k, v in falls(u_g).items()}},
           "crashes": [{"k": k, "from": a, "to": b, "name": n} for k, a, b, n in CRASHES]}
    # A. how many stocks
    nstk = {}
    for n in (1, 2, 3, 5, 10, 20, 30):
        idx = np.array([rng.choice(len(syms), n, replace=False) for _ in range(draws)])
        r = np.concatenate([R[:, idx[i:i + 200]].mean(axis=2).T for i in range(0, draws, 200)])   # equal weights, rebalanced weekly
        c, d, wk, g = _stats(r, weeks)
        nstk[str(n)] = _summary(c, d, wk, u_cagr[0], falls(g))
    out["n"] = nstk
    # B. an index core with a slice of picks (three stocks)
    idx3 = np.array([rng.choice(len(syms), 3, replace=False) for _ in range(draws)])
    picks = R[:, idx3].mean(axis=2).T                     # (draws, weeks)
    core = {}
    for s in (1.0, 0.75, 0.5, 0.25, 0.1):
        r = s * picks + (1 - s) * ru[None, :]
        c, d, wk, g = _stats(r, weeks)
        core[str(int(s * 100))] = _summary(c, d, wk, u_cagr[0], falls(g))
    # the same 50/50 never rebalanced: each half grows on its own
    gp = np.cumprod(1 + picks, axis=1)
    gs = np.cumprod(1 + ru)[None, :]
    g = 0.5 * gp + 0.5 * gs
    rr = np.concatenate([g[:, :1] - 1, g[:, 1:] / g[:, :-1] - 1], axis=1)
    c, d, wk, g2 = _stats(rr, weeks)
    core["50_drift"] = _summary(c, d, wk, u_cagr[0], falls(g2))
    core["50_drift"]["end_share"] = round(float(np.median((0.5 * gp[:, -1]) / g[:, -1])), 4)
    out["core"] = core
    # C. one big position: 60% in one stock and 10% in each of four more
    idx5 = np.array([rng.choice(len(syms), 5, replace=False) for _ in range(draws)])
    big, rest = R[:, idx5[:, 0]].T, R[:, idx5[:, 1:]].mean(axis=2).T
    caps = {}
    gb, gr = np.cumprod(1 + big, axis=1), np.cumprod(1 + rest, axis=1)
    g = 0.6 * gb + 0.4 * gr                                # let it ride
    rr = np.concatenate([g[:, :1] - 1, g[:, 1:] / g[:, :-1] - 1], axis=1)
    c, d, wk, g2 = _stats(rr, weeks)
    caps["ride"] = _summary(c, d, wk, u_cagr[0], falls(g2))
    for key, wb, wr, wc in (("hold60", 0.6, 0.4, 0.0), ("cap25", 0.25, 0.4, 0.35), ("cap10", 0.10, 0.4, 0.50)):
        r = wb * big + wr * rest + wc * ru[None, :]
        c, d, wk, g2 = _stats(r, weeks)
        caps[key] = _summary(c, d, wk, u_cagr[0], falls(g2))
    out["caps"] = caps
    return out


def load():
    try:
        return json.load(open(OUT))
    except Exception:
        return {}


# ------------------------------------------------------------------ the guide
def _pct(v, d=0, sign=False):
    if v is None:
        return "–"
    s = f"{abs(v) * 100:.{d}f}%"
    return ("−" + s) if v < 0 and round(abs(v) * 100, d) else (("+" + s) if sign and v > 0 else s)


def guide_page(site):
    from .render import DISCLAIMER
    J = load()
    path, depth = PATH, 2
    h = lambda x: site.href(depth, x)
    if not J:
        body = '<section class="pair-head"><h1 class="h1">Planning an account</h1></section>'
        site.add(path, site.shell(path, "Planning an account", "How mixes of stocks have behaved.", body, active="learn/"))
        return
    S, A, N, C, K = J["spy"], J["all"], J["n"], J["core"], J["caps"]
    yrs, since, ns = J["years"], J["since"][:4], J["stocks"]
    crash = J["crashes"]
    allname = f"All {ns}, equal amounts"

    def fall_cells(x):
        return "".join(f'<td class="r">{_pct(x["falls"][c["k"]]["med"])}</td>' for c in crash)
    nrows = "".join(f'<tr><td>{k} stock{"s" if k != "1" else ""}</td><td class="r">{_pct(v["cagr_med"], 1)}</td><td class="r">{_pct(v["cagr_p10"], 1)} to {_pct(v["cagr_p90"], 1)}</td>'
                    f'<td class="r">{_pct(v["dd_med"])}</td><td class="r">{_pct(v["dd50"])}</td><td class="r">{_pct(v["beat_all"])}</td></tr>' for k, v in N.items())
    all_row = (f'<tr><td><b>{allname}</b></td><td class="r">{_pct(A["cagr"], 1)}</td><td class="r">–</td><td class="r">{_pct(A["dd"])}</td>'
               f'<td class="r">{"Yes" if A["dd"] <= -0.5 else "No"}</td><td class="r">–</td></tr>')
    lab = {"100": "All picks", "75": "75% picks, 25% the rest", "50": "50 / 50", "25": "25% picks, 75% the rest", "10": "10% picks, 90% the rest"}
    crows = "".join(f'<tr><td>{lab[k]}</td><td class="r">{_pct(C[k]["cagr_med"], 1)}</td><td class="r">{_pct(C[k]["cagr_p10"], 1)}</td><td class="r">{_pct(C[k]["dd_med"])}</td>{fall_cells(C[k])}</tr>'
                    for k in ("100", "75", "50", "25", "10"))
    crows += (f'<tr><td><b>{allname}</b></td><td class="r">{_pct(A["cagr"], 1)}</td><td class="r">–</td><td class="r">{_pct(A["dd"])}</td>'
              + "".join(f'<td class="r">{_pct(A["falls"][c["k"]])}</td>' for c in crash) + "</tr>")
    klab = {"ride": "60% in one stock, never trimmed", "hold60": "60% in one stock, trimmed back to 60%", "cap25": "That stock capped at 25%, the rest spread across all",
            "cap10": "Capped at 10%, the rest spread across all"}
    krows = "".join(f'<tr><td>{klab[k]}</td><td class="r">{_pct(K[k]["cagr_med"], 1)}</td><td class="r">{_pct(K[k]["cagr_p10"], 1)}</td><td class="r">{_pct(K[k]["dd_med"])}</td>'
                    f'<td class="r">{_pct(K[k]["dd_p10"])}</td><td class="r">{_pct(K[k]["dd50"])}</td></tr>' for k in ("ride", "hold60", "cap25", "cap10"))
    one, ten, thirty = N["1"], N["10"], N["30"]
    d50 = C["50_drift"]
    body = f"""
<nav class="crumbs"><a href="{h('guides/')}">Guides</a><span>/</span><span>Planning an account</span></nav>
<section class="pair-head"><p class="eyebrow">Guide</p><h1 class="h1">Planning an account, not just picking stocks</h1>
<p class="lede">A signal is about one stock. What happens to your money depends on the mix: how many names, how much in each, how much spread across everything, and whether you trim what grows. Here is what those choices did since {since}, from {J['draws']:,} random portfolios at each setting, built from the {ns} covered stocks that have traded the whole time.</p>
<div class="ps-steps-row"><a class="btn primary" href="{h('watchlist/')}#account">Check your own mix</a><span class="small muted">Load your holdings into the watchlist and its account check runs them through the same history.</span></div></section>

<section class="card prose"><h2 class="h2">1. How many stocks</h2>
<p>Each row is {J['draws']:,} portfolios of that many covered stocks picked at random, equal amounts in each, from {since} to {pd.Timestamp(J['to']).strftime('%B %Y')} ({yrs:.0f} years). The last row is all {ns} together.</p>
<div class="tbl-wrap"><table class="tbl" data-nosort><thead><tr><th>Holding</th><th class="r">Typical yearly return</th><th class="r">Bad luck to good luck (10th–90th)</th><th class="r">Typical worst fall</th><th class="r">Fell 50%+ at some point</th><th class="r">Beat all {ns} together</th></tr></thead>
<tbody>{nrows}{all_row}</tbody></table></div>
<ul>
<li><b>One stock is a lottery ticket.</b> The typical single stock returned {_pct(one['cagr_med'], 1)} a year, against {_pct(A['cagr'], 1)} for all {ns} together. One in ten did {_pct(one['cagr_p10'], 1)} or worse and one in ten {_pct(one['cagr_p90'], 1)} or better, and {_pct(one['dd50'])} fell by half or more at some point. Only {_pct(one['beat_all'])} beat the whole list: a few huge winners carry the average, and most stocks aren't them.</li>
<li><b>The spread closes fast.</b> By 10 stocks the bad-luck case was {_pct(ten['cagr_p10'], 1)} a year; by 30 it was {_pct(thirty['cagr_p10'], 1)}. The typical worst fall went from {_pct(one['dd_med'])} with one stock to {_pct(thirty['dd_med'])} with 30, close to the {_pct(A['dd'])} of all {ns}.</li>
<li><b>Most of the protection comes from the first 10 to 20 names.</b> Past that, more stocks change the result little, and an index fund does the same job in one holding.</li>
</ul>
<p class="small muted">These are today's survivors: stocks that went bankrupt or were bought out aren't in the list, which flatters every row, and single stocks most. That's also why all {ns} together returned {_pct(A['cagr'], 1)} a year against {_pct(S['cagr'], 1)} for the S&amp;P 500 (SPY), which includes the companies that failed. Each stock is in its own currency.</p></section>

<section class="card prose"><h2 class="h2">2. A core with a slice of picks</h2>
<p>Here the picks are three covered stocks chosen at random, the way a short "top picks" list might look, and the core is all {ns} stocks in equal amounts, so picks and core come from the same survivors. Each mix was reset to its split every week.</p>
<div class="tbl-wrap"><table class="tbl" data-nosort><thead><tr><th>Mix</th><th class="r">Typical yearly return</th><th class="r">Bad luck (10th)</th><th class="r">Typical worst fall</th>{"".join(f'<th class="r">{e(c["name"])}</th>' for c in crash)}</tr></thead>
<tbody>{crows}</tbody></table></div>
<ul>
<li><b>Picks didn't add return on average.</b> The typical three-stock slice returned {_pct(C['100']['cagr_med'], 1)} a year against {_pct(A['cagr'], 1)} for the whole list. What picks add is range: the chance of a big winner, and of a big loser.</li>
<li><b>The core lifts the floor.</b> Going from all picks to 25% picks took the typical worst fall from {_pct(C['100']['dd_med'])} to {_pct(C['25']['dd_med'])} and lifted the bad-luck case from {_pct(C['100']['cagr_p10'], 1)} to {_pct(C['25']['cagr_p10'], 1)} a year.</li>
<li><b>In a broad crash, everything falls.</b> In 2008–09 the typical mix fell 40% or more whatever the split; the core shrank the bad-luck cases more than the typical one.</li>
<li><b>Left alone, a split drifts.</b> A 50/50 mix never reset ended with the picks typically at {_pct(d50.get('end_share'))} of the account; when a pick takes off the drift runs the other way, and a balanced plan quietly becomes a concentrated one.</li>
</ul></section>

<section class="card prose"><h2 class="h2">3. One stock that's most of the account</h2>
<p>{J['draws']:,} accounts with 60% in one covered stock and 10% in each of four more, run four ways:</p>
<div class="tbl-wrap"><table class="tbl" data-nosort><thead><tr><th>Approach</th><th class="r">Typical yearly return</th><th class="r">Bad luck (10th)</th><th class="r">Typical worst fall</th><th class="r">Worst fall, bad luck (10th)</th><th class="r">Fell 50%+</th></tr></thead>
<tbody>{krows}</tbody></table></div>
<ul>
<li><b>A cap changed the bad cases most.</b> Capping the big stock at 25% and spreading the rest took the share of accounts that fell by half or more from {_pct(K['ride']['dd50'])} to {_pct(K['cap25']['dd50'])}, and the bad-luck worst fall from {_pct(K['ride']['dd_p10'])} to {_pct(K['cap25']['dd_p10'])}.</li>
<li><b>Letting it ride</b> is how the occasional huge winner happens, and also how most of the 50% falls happened.</li>
<li><b>Trimming back to 60% didn't help:</b> topping a falling stock back up to 60% made the worst cases worse ({_pct(K['hold60']['dd_p10'])}). The size of the position mattered more than the trimming.</li>
</ul></section>

<section class="card prose"><h2 class="h2">4. What the professionals are held to</h2>
<ul>
<li><b>In Canada,</b> a mutual fund generally can't buy a security if that would put more than 10% of its net assets in one issuer (National Instrument 81-102, section 2.1; <a href="https://www.osc.ca/en/securities-law/orders-rulings-decisions/cibc-asset-management-inc-and-cibc-canadian-banks-covered-call-etf" rel="noopener" target="_blank">as the OSC describes it</a>).</li>
<li><b>In the U.S.,</b> a fund that calls itself diversified must have at least 75% of its assets in holdings where no single issuer is more than 5% of the fund (Investment Company Act of 1940, <a href="https://www.law.cornell.edu/uscode/text/15/80a-5" rel="noopener" target="_blank">section 5(b)(1)</a>).</li>
<li>Those rules are for funds holding other people's money. They're a reference point, not a rule for anyone's own account.</li>
</ul></section>

<section class="card prose"><h2 class="h2">5. The same bet twice</h2>
<p>Two stocks in the same business tend to fall together. Over the last three years, covered chip stocks moved together far more than two covered stocks picked at random (<a href="{h('articles/one-stock-too-many/')}">the numbers are in One stock too many</a>), so a list with five semiconductor names behaves more like one or two positions than five. The account check on the watchlist shows how much of your list sits in each sector.</p></section>

<section class="card prose"><h2 class="h2">What this can and can't tell you</h2>
<p>It shows what each choice did in the past, on stocks that survived. It can't say what mix is right for you: that depends on when you need the money, what else you own, your taxes and how you'd handle a 40% fall, which is what an advisor is for (<a href="{h('guides/ways-to-invest/')}">ways to invest, and how to check an advisor, by country</a>). {DISCLAIMER}</p>
<p class="small muted">Study run {J['built']}: weekly closes adjusted for splits and dividends, no trading costs or taxes, {J['draws']:,} random draws per setting.</p></section>
"""
    site.add(path, site.shell(path, "Planning an account, not just picking stocks",
                              "What holding 1 to 30 stocks, an index core with a slice of picks, per-stock caps and rebalancing did since 2006, from thousands of random portfolios.",
                              body, active="learn/"))
