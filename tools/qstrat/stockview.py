"""The visual blocks on a stock page: candlesticks, the plays-over-time heatmap,
the plain-English read, fundamentals and crash exposure (the storm test).

Each function returns an HTML string. Charts carry their data as embedded JSON
for assets/widgets.js to draw.
"""
import html
import json
import math

import pandas as pd

from .content import TIMED, FAMILIES, credit
from .risk import num

e = html.escape
CUR_SIGN = {"USD": "$", "CAD": "C$", "EUR": "€", "GBP": "£", "JPY": "¥", "AUD": "A$", "HKD": "HK$", "CHF": "CHF "}
LEVEL_CLASS = {"Low": "calm", "Moderate": "watch", "High": "warning", "Very high": "warning"}


def _js(obj):
    return json.dumps(obj, separators=(",", ":"), allow_nan=False).replace("</", "<\\/")


def _sig(v, n=6):
    if v is None:
        return None
    v = float(v)
    if math.isnan(v) or math.isinf(v):
        return None
    return float(f"{v:.{n}g}")


def big_money(v, sign="$"):
    v = num(v)
    if v is None:
        return "–"
    a = abs(v)
    neg = "−" if v < 0 else ""
    for div, suf in ((1e12, "T"), (1e9, "B"), (1e6, "M"), (1e3, "K")):
        if a >= div:
            x = a / div
            return f"{neg}{sign}{x:,.{1 if x < 100 else 0}f}{suf}"
    return f"{neg}{sign}{a:,.0f}"


def pc(v, d=1, sign=False):
    v = num(v)
    if v is None:
        return "–"
    s = f"{abs(v) * 100:,.{d}f}%"
    return ("−" + s) if v < 0 else (("+" + s) if sign and v > 0 else s)


def times(v, d=1):
    v = num(v)
    return "–" if v is None else f"{v:,.{d}f}×".replace("-", "−")


def is_equity(t, fund):
    return bool(fund) and not t.get("index") and not t["crypto"] and (fund.get("quoteType") in (None, "EQUITY"))


# --------------------------------------------------------------------------
# candlesticks
# --------------------------------------------------------------------------
def candles_block(t, meta, learn="#", cid="cd", title=None, note=None, rng=126):
    o = meta["ohlc"]
    t0 = o.index[0]
    vol = [int(v) if v == v and v > 0 else 0 for v in o["volume"].values]
    spec = {"t0": t0.strftime("%Y-%m-%d"), "d": [int((x - t0).days) for x in o.index],
            "o": [_sig(v) for v in o["open"].values], "h": [_sig(v) for v in o["high"].values],
            "l": [_sig(v) for v in o["low"].values], "c": [_sig(v) for v in o["close"].values], "v": vol,
            "cur": t["cur"], "range": rng, "overlays": ["sma50", "sma200"],
            "label": f"{t['short']} daily candlesticks with volume"}
    if not any(vol):
        spec["v"] = [0] * len(vol)
    title = title or f"{e(t['short'])}, day by day"
    note = note or ("Each candle is one trading day: the box spans the open and close, the thin line the day's high and low. "
                    "Hollow boxes closed up, filled boxes closed down. Toggle the averages to see the trend the plays read.")
    return (f'<div class="card chart-card"><div class="chart-top"><h3 class="h3">{title}</h3>'
            f'<a class="small" href="{learn}">How to read candlesticks</a></div>'
            f'<div class="candles" data-candles="{cid}"></div><script type="application/json" id="{cid}">{_js(spec)}</script>'
            f'<p class="chart-note">{note}</p></div>')


# --------------------------------------------------------------------------
# plays over time
# --------------------------------------------------------------------------
def heatmap_block(site, t, meta, href, cid="hm"):
    weeks = meta["weeks"]
    W = len(weeks)
    rows = []
    core_slugs = {p["slug"] for p in TIMED if p.get("core")}
    for fk, fname, _ in FAMILIES:
        for p in [x for x in TIMED if x["family"] == fk]:
            x = site.R.get((t["sym"], p["slug"]))
            if x is None:
                continue
            h = x.get("hist") or ""
            h = ("-" * max(0, W - len(h)) + h)[-W:]
            rows.append({"name": p["name"], "fam": fk, "core": p["slug"] in core_slugs, "h": h,
                         "href": href(p) if href(p) else None})
    spec = {"weeks": [w.strftime("%b %-d, %Y") for w in weeks], "rows": rows,
            "label": f"Every play's call on {t['short']}, week by week for two years"}
    return (f'<div class="card chart-card"><div class="chart-top"><h3 class="h3">Two years of calls, week by week</h3>'
            f'<div class="legend-row"><span class="key"><s style="background:var(--in)"></s>In</span>'
            f'<span class="key"><s style="background:var(--out)"></s>Out</span><span class="key"><i style="background:var(--violet-ink)"></i>Share of plays in</span></div></div>'
            f'<div class="heatmap" data-heatmap="{cid}"></div><script type="application/json" id="{cid}">{_js(spec)}</script>'
            f'<p class="chart-note">One row per play, grouped by family. When most rows turn green at once, the trend is broad. '
            f'When they split, the plays disagree and the stock is usually chopping sideways.</p></div>')


# --------------------------------------------------------------------------
# the plain-English read
# --------------------------------------------------------------------------
FAM_WORD = {"trend": "trend-following", "breakout": "breakout", "momentum": "momentum", "reversion": "mean-reversion",
            "volume": "volume", "pattern": "pattern", "calendar": "calendar"}


def _lean(k, n):
    if not n:
        return None
    r = k / n
    return "in" if r >= 0.67 else "out" if r <= 0.33 else "split"


def read_lines(site, t, meta, fund):
    """Two to four short sentences that say what matters on this name now."""
    sym, short = t["sym"], t["short"]
    ka, na = site.consensus(t)
    lines = []
    if na:
        lines.append(f"{ka} of the {na} plays hold {short} right now.")
    # which families agree, which don't
    leans = []
    for fk, fname, _ in FAMILIES:
        ps = [p for p in TIMED if p["family"] == fk]
        k, n = site.consensus(t, ps)
        if n >= 3:
            leans.append((fk, _lean(k, n), k, n))
    ins = [FAM_WORD[f] for f, l, _, _ in leans if l == "in"]
    outs = [FAM_WORD[f] for f, l, _, _ in leans if l == "out"]

    def join(xs):
        return xs[0] if len(xs) == 1 else ", ".join(xs[:-1]) + " and " + xs[-1]
    if ins and outs:
        lines.append(f"The {join(ins)} plays mostly say in; the {join(outs)} plays mostly say out.")
    elif ins:
        lines.append(f"The {join(ins)} plays mostly say in.")
    elif outs:
        lines.append(f"The {join(outs)} plays mostly say out.")
    # trend position
    c = meta["ohlc"]["close"]
    if len(c) >= 200:
        ma = float(c.iloc[-200:].mean())
        hi = float(c.iloc[-252:].max())
        last = float(c.iloc[-1])
        gap = last / ma - 1
        off = last / hi - 1
        where = "above" if gap >= 0 else "below"
        hi_txt = "at a 52-week high" if off > -0.005 else f"{abs(off) * 100:.0f}% below its 52-week high"
        lines.append(f"It closed {abs(gap) * 100:.0f}% {where} its 200-day average and {hi_txt}.")
    rk = meta.get("risk") or {}
    if rk.get("level"):
        why = rk.get("why") or []
        tail = f": it {why[0]}" + (f" and {why[1]}" if len(why) > 1 else "") + "." if why else "."
        lines.append(f"Crash exposure reads {rk['level'].lower()}{tail}")
    if fund and is_equity(t, fund):
        tgt, n_an = num(fund.get("targetMeanPrice")), num(fund.get("numberOfAnalystOpinions"))
        last = float(c.iloc[-1])
        if tgt and n_an and n_an >= 3:
            sign = CUR_SIGN.get(fund.get("currency"), t["cur"])
            lines.append(f"Analysts' average 12-month target is {sign}{tgt:,.2f}, {abs(tgt / last - 1) * 100:.0f}% "
                         f"{'above' if tgt >= last else 'below'} the close ({int(n_an)} analysts).")
    return lines


# --------------------------------------------------------------------------
# fundamentals
# --------------------------------------------------------------------------
REC = {"strong_buy": "Strong buy", "buy": "Buy", "hold": "Hold", "underperform": "Underperform", "sell": "Sell",
       "strong_sell": "Strong sell", "none": None}


def fundamentals_card(t, fund, price, learn="#"):
    if not is_equity(t, fund):
        return ""
    f = fund
    tc = CUR_SIGN.get(f.get("currency"), t["cur"] or "$")
    fc = CUR_SIGN.get(f.get("financialCurrency") or f.get("currency"), tc)
    mcap, rev = num(f.get("marketCap")), num(f.get("totalRevenue"))
    pe, fpe, pb, ps = num(f.get("trailingPE")), num(f.get("forwardPE")), num(f.get("priceToBook")), num(f.get("priceToSalesTrailing12Months"))
    eps = num(f.get("trailingEps"))
    debt, cash, equity = num(f.get("totalDebt")), num(f.get("totalCash")), num(f.get("equity"))
    de = (debt / equity) if (debt is not None and equity and equity > 0) else None
    cover = num(f.get("interest_cover"))
    margin, rg, eg, roe = num(f.get("profitMargins")), num(f.get("revenueGrowth")), num(f.get("earningsGrowth")), num(f.get("returnOnEquity"))
    dy = num(f.get("dividendYield"))
    fcf = num(f.get("freeCashflow"))
    tgt, tlo, thi, n_an = num(f.get("targetMeanPrice")), num(f.get("targetLowPrice")), num(f.get("targetHighPrice")), num(f.get("numberOfAnalystOpinions"))
    rec = REC.get(f.get("recommendationKey") or "none")
    if pe is not None and pe <= 0:
        pe = None

    def row(label, val, read=""):
        return f'<tr><th scope="row">{label}</th><td class="r mono">{val}</td><td class="muted">{read}</td></tr>'

    size = row("Market cap", big_money(mcap, tc), "What the whole company is worth at today's price: share price × shares outstanding.")
    if rev:
        size += row("Revenue (last 12 months)", big_money(rev, fc), "Total sales." + (f" The market values it at {mcap / rev:,.1f}× sales." if mcap and rev and fc == tc else ""))
    val = ""
    if pe:
        val += row("P/E ratio", times(pe), f"Buyers pay {tc}{pe:,.0f} for each {tc}1 of the last year's profit.")
    elif eps is not None and eps < 0:
        val += row("P/E ratio", "n/a", "Lost money over the last year, so there is no profit to divide by.")
    if fpe and fpe > 0:
        val += row("Forward P/E", times(fpe), "Price against analysts' estimate of next year's profit." + (" Lower than the P/E means profit is expected to grow." if pe and fpe < pe * 0.9 else ""))
    if pb and pb > 0:
        val += row("Price to book", times(pb), "Price against the company's net assets (its equity) per share.")
    if ps and ps > 0 and not val:
        val += row("Price to sales", times(ps), "Price against a year of revenue; used when there is no profit.")
    prof = ""
    if margin is not None:
        prof += row("Profit margin", pc(margin), f"Keeps {abs(margin) * 100:.0f}¢ of each dollar of sales as profit." if margin > 0 else "Spends more than it brings in.")
    if rg is not None:
        prof += row("Revenue growth", pc(rg, sign=True), "Last quarter's sales against the same quarter a year earlier.")
    if eg is not None:
        prof += row("Earnings growth", pc(eg, sign=True), "Same comparison for profit.")
    if roe is not None and equity and equity > 0:
        prof += row("Return on equity", pc(roe), "Yearly profit as a share of shareholders' money in the business.")
    if fcf is not None:
        prof += row("Free cash flow", big_money(fcf, fc), "Cash left after running and investing in the business." if fcf > 0 else "Burning cash: needs savings or new money to keep going.")
    bal = ""
    if equity is not None:
        bal += row("Total equity", big_money(equity, fc), "What it owns minus what it owes." if equity > 0 else "Negative: it owes more than it owns.")
    if debt is not None:
        bal += row("Total debt", big_money(debt, fc), "Loans and bonds it has to pay back, with interest.")
    if cash is not None:
        bal += row("Cash", big_money(cash, fc), "Cash and short-term investments on hand.")
    if de is not None:
        bal += row("Debt to equity", times(de, 2), "Above about 1.5× is heavily borrowed; above 3× is fragile in a downturn." if de > 1.5 else "Comfortable." if de < 0.5 else "Moderate.")
    if cover is not None:
        bal += row("Interest cover", times(cover), "Operating profit divided by interest. Under 2× means one bad year could make the interest hard to pay." if cover < 4 else "Interest is easily paid from profit.")
    st = ""
    if tgt and n_an:
        up = tgt / price - 1 if price else None
        st += row("Average analyst target", f"{tc}{tgt:,.2f}", f"{abs(up) * 100:.0f}% {'above' if up >= 0 else 'below'} the close, from {int(n_an)} analysts" + (f" (range {tc}{tlo:,.2f} to {tc}{thi:,.2f})." if tlo and thi else ".") if up is not None else "")
    if rec and n_an:
        st += row("Consensus rating", rec, "Analysts' average recommendation. Ratings lean positive: sell ratings are rare.")
    if dy:
        st += row("Dividend yield", f"{dy:.2f}%", "Yearly dividends as a share of the price.")

    def sec(title, rows):
        return (f'<div class="tbl-wrap flat"><table class="tbl fund-tbl" data-nosort><tbody><tr class="grp"><td colspan="3">{title}</td></tr>{rows}</tbody></table></div>'
                if rows else "")
    body = sec("Size and valuation", size + val) + sec("Profit and growth", prof) + sec("Balance sheet", bal) + sec("Wall Street", st)
    when = f.get("fetched")
    about = ""
    summ = f.get("longBusinessSummary")
    if summ:
        cut = summ if len(summ) < 520 else summ[:summ.rfind(". ", 0, 520) + 1] or summ[:520] + "…"
        about = f'<p class="about-co"><b>{e(f.get("industry") or "Business")}</b> · {e(cut)}</p>'
    return (f'<div class="card fund-card"><div class="chart-top"><h3 class="h3">The business behind the price</h3>'
            f'<a class="small" href="{learn}">How to judge these numbers</a></div>{about}'
            f'<div class="fund-grid">{body}</div>'
            f'<p class="chart-note">Company figures from Yahoo Finance{", fetched " + pd.Timestamp(when).strftime("%b %-d, %Y") if when else ""}. '
            f'Analyst targets are opinions, not forecasts Be The Puck checks.</p></div>')


# --------------------------------------------------------------------------
# crash exposure (the storm test)
# --------------------------------------------------------------------------
PART = [("market", "Market swings", 3, "Beta and downside capture against its index"),
        ("history", "Past crashes", 2, "How far it fell in past crashes, against its index"),
        ("balance", "Debt", 3, "Borrowing, negative equity and interest cover"),
        ("runup", "Run-up", 2, "Two-year gain against bubble thresholds")]


BENCH_SHORT = {"^GSPTSE": "TSX", "^GSPC": "S&P 500"}


def bench_name(t):
    return {"^GSPTSE": "the TSX", "^GSPC": "the S&P 500"}.get(t.get("bench"), "its index")


def crash_card(t, rk, depth_href):
    if not rk:
        return ""
    lvl = rk["level"]
    cls = LEVEL_CLASS[lvl]
    parts = ""
    for key, lab, mx, tip in PART:
        v = rk["points"].get(key, 0)
        cells = "".join(f'<i class="{"on " + cls if j < v else ""}"></i>' for j in range(mx))
        parts += f'<li title="{e(tip)}"><span>{lab}</span><span class="pips">{cells}</span><b>{v}/{mx}</b></li>'
    bn = bench_name(t)
    bars = ""
    for c in rk["crashes"]:
        mine, idx = c["dd"], c["bench_dd"]
        w1 = min(100, abs(mine) * 100)
        rec = c.get("recovered")
        low = pd.Timestamp(c["low_date"])
        rec_txt = (f"back to its old high {pd.Timestamp(rec).strftime('%b %Y')}" if rec is not None else "never got back")
        line2 = ""
        if idx is not None and t.get("bench"):
            w2 = min(100, abs(idx) * 100)
            line2 = f'<div class="cb-row bench"><span class="cb-lab">{e(BENCH_SHORT.get(t.get("bench"), "Index"))}</span><span class="cb-track"><i style="width:{w2:.0f}%"></i></span><b>{pc(idx, 0)}</b></div>'
        bars += (f'<div class="cb"><p class="cb-h"><b>{e(c["label"])}</b> <span class="muted">{pd.Timestamp(c["start"]).strftime("%b %Y")} to {low.strftime("%b %Y")} · {rec_txt}</span></p>'
                 f'<div class="cb-row"><span class="cb-lab">{e(t["short"])}</span><span class="cb-track"><i class="{cls}" style="width:{w1:.0f}%"></i></span><b>{pc(mine, 0)}</b></div>{line2}</div>')
    if not bars:
        bars = '<p class="muted small">Too young to have lived through a market crash, so there is no crash record to read.</p>'
    facts = []
    if rk.get("beta") is not None:
        facts.append(("Beta", f"{rk['beta']:.2f}", f"Moves about {rk['beta']:.1f}× as much as {bn} week to week."))
    if rk.get("capture") is not None:
        facts.append(("Downside capture", pc(rk["capture"], 0), f"In months {bn} fell, this fell {rk['capture'] * 100:.0f}% as much on average" + (" (it often rose anyway)." if rk["capture"] < 0.6 else ".")))
    if rk.get("runup2y") is not None:
        facts.append(("Two-year change", pc(rk["runup2y"], 0, sign=True),
                      "Run-ups of 100%+ crashed 40% or more within two years about half the time (Greenwood, Shleifer & You)." if rk["runup2y"] > 0.5 else ""))
    if rk.get("off_high") is not None:
        facts.append(("From 52-week high", pc(rk["off_high"], 0), ""))
    if rk.get("neg_equity"):
        facts.append(("Equity", "Negative", "Owes more than it owns."))
    elif rk.get("de") is not None:
        facts.append(("Debt to equity", times(rk["de"], 2), ""))
    if rk.get("nd_ebitda") is not None:
        if rk["nd_ebitda"] <= 0:
            facts.append(("Net debt / EBITDA", "Net cash", "Holds more cash than debt."))
        else:
            facts.append(("Net debt / EBITDA", times(rk["nd_ebitda"]), "Years of operating cash earnings it would take to pay off its debt."))
    if rk.get("cover") is not None:
        facts.append(("Interest cover", times(rk["cover"]), ""))
    fl = "".join(f'<li><span>{lab}</span><b>{val}</b>' + (f'<em>{e(note)}</em>' if note else "") + "</li>" for lab, val, note in facts)
    why = rk.get("why") or []
    why_html = ("<ul class='why'>" + "".join(f"<li>It {e(w)}.</li>" for w in why) + "</ul>") if why else '<p class="muted small">Nothing on the checklist stands out.</p>'
    no_fund = "" if rk.get("has_fund") or t.get("index") or t["crypto"] or t["group"] in ("Indexes & ETFs", "Sectors") else '<p class="muted small">No balance-sheet data for this name, so debt is not scored.</p>'
    return f"""<div class="card crash-card">
<div class="chart-top"><h3 class="h3">If the market cracks: the storm test</h3><a class="small" href="{depth_href('articles/debt-and-crashes/')}">How the storm test works</a></div>
<div class="crash-top"><div class="crash-level {cls}"><span class="eyebrow">Exposure</span><b>{e(lvl)}</b><span class="muted small">{rk['score']} of 10 points</span></div>
<ul class="crash-parts">{parts}</ul></div>
{why_html}{no_fund}
<div class="crash-grid"><div class="crash-bars"><p class="eyebrow">Past crashes, peak to low</p>{bars}</div>
<ul class="crash-facts">{fl}</ul></div>
<p class="chart-note">A crash marks every stock down; debt decides which companies come through. The storm test scores both halves: how hard the stock swings with the market, and how much debt it carries into a downturn. It describes fragility; it does not predict a crash.</p>
</div>"""


# --------------------------------------------------------------------------
# outlook: the plays' consensus weighed equally with analysts' upside
# --------------------------------------------------------------------------
UPSIDE_FLOOR, UPSIDE_CAP = -0.20, 0.50     # upside scored linearly from -20% (0) to +50% (full marks)
MIN_ANALYSTS = 3
TREND_WEIGHT = 0.5                        # the other half is analyst upside


def upside_points(u):
    """Analyst upside mapped to 0-1 (the same formula is in assets/watchlist.js)."""
    return (min(max(u, UPSIDE_FLOOR), UPSIDE_CAP) - UPSIDE_FLOOR) / (UPSIDE_CAP - UPSIDE_FLOOR)


def outlook(site, t, plays=None):
    """{'score', 'trend', 'upside', 'n_an', 'ok', 'why'}: half how many plays hold the stock, half how far
    analysts' average 12-month target sits above the price. Needs 3+ analysts; a target more than double
    the price is treated as stale (usually after a share consolidation) and ignored."""
    k, n = site.consensus(t, plays)
    trend = k / n if n else 0.0
    x = site.R.get((t["sym"], "buy-and-hold"))
    f = site.fund.get(t["sym"]) or {}
    tgt, na = num(f.get("targetMeanPrice")), int(num(f.get("numberOfAnalystOpinions")) or 0)
    out = {"trend": trend, "k": k, "n": n, "upside": None, "n_an": na, "ok": False, "score": None, "why": ""}
    if not x or not tgt or not is_equity(t, f):
        out["why"] = "no analyst target"
        return out
    u = tgt / x["price"] - 1
    out["upside"] = u
    if na < MIN_ANALYSTS:
        out["why"] = f"only {na} analyst{'s' if na != 1 else ''}"
        return out
    if u > 1.0:
        out["why"] = "target looks stale"
        return out
    out["ok"] = True
    out["score"] = TREND_WEIGHT * trend + (1 - TREND_WEIGHT) * upside_points(u)
    return out
