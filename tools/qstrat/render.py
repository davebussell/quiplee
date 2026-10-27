"""HTML renderer for the plays site. Pure functions over engine results.

Links are relative so the same output works on bethepuck.com and in a static
preview; `preview=True` spells out index.html for hosts without directory
indexes.
"""
import html
import json
import math
import os
import re

import numpy as np
import pandas as pd

from .icons import icon
from .media import pic, page_art, PAGE_ART
from .linker import link_terms
from . import stockview as sv
from .engine import GRADE_START
from .content import (TICKERS, THINKERS, THINKER, PLAYS, PLAY, TIMED, GROUP_ORDER, BAR_WORD,
                      FAMILIES, FAMILY, FAMILY_ORDER, credit)

e = html.escape
TK = {t["sym"]: t for t in TICKERS}


def universe():
    """The curated list. Reader-requested tickers get their own pages but stay out
    of the cross-stock tables and counts, which would otherwise shift as readers add names."""
    return [t for t in TICKERS if not t.get("requested")]


# Reader-requested names are private: analysed every night like any other, but only for the readers who follow
# them (their account page, their watchlist, their emails). They stay out of every list, the screener, the
# sitemap and search engines (noindex), and out of the rankings the public scores use (factors.compute).
PRIVATE_SLUGS = {t["slug"] for t in TICKERS if t.get("requested")}


def play_label(p):
    """A play's everyday name with its technical name in brackets when they differ: "Buy the oversold bounce (RSI 30/70)"."""
    plain, tech = p.get("plain") or p["name"], p["name"]
    return plain if plain.lower() == tech.lower() else f"{plain} ({tech})"


def play_name_html(p, cls="play-tech"):
    """The everyday name in bold, the technical name under it (plain.py)."""
    plain, tech = p.get("plain") or p["name"], p["name"]
    return f'<b>{e(plain)}</b>' + ("" if plain.lower() == tech.lower() else f'<span class="{cls}">{e(tech)}</span>')


def classic_links(h, kind, slug, lead):
    """Links to the classics (classics.py) that mention this play or person: the history behind the rule."""
    from .classics import see_also, links_html
    return links_html(h, see_also(kind, slug), lead)


def private_path(path):
    """True for any page of a private (reader-requested) name: its stock page, its play rows, its brief."""
    parts = path.split("/")
    if parts[0] == "stocks" and len(parts) > 1:
        return parts[1] in PRIVATE_SLUGS
    return path.startswith("articles/stocks/") and len(parts) > 2 and parts[2] in PRIVATE_SLUGS


# "Real stocks" for ranking plays: no indexes, index or sector funds, or crypto.
NON_STOCK_GROUPS = ("Sectors", "Indexes & ETFs", "Market indexes", "Crypto")
GRADE_YEAR = GRADE_START.year   # calls are graded from here on
TOP_MIN_CALLS = 500     # to be ranked, a play needs this many finished calls across the stocks,
                        # on at least half of them (the Mayer Multiple, say, only ever flips on a few)


def is_stock(t):
    return not t.get("crypto") and not t.get("index") and t["group"] not in NON_STOCK_GROUPS


def n_stocks():
    return sum(1 for t in universe() if is_stock(t))


def rankable(a, n=None):
    """Whether a play's accuracy (Site.play_accuracy) rests on enough calls, on enough stocks, to rank."""
    n = n_stocks() if n is None else n
    return a["bat"] is not None and a["calls"] >= TOP_MIN_CALLS and 2 * a["stocks"] >= n


def ps_bar(h, note, cls=""):
    """The play-filter button (assets/plays.js fills in the label and opens the chooser) and a line on what it changes."""
    return (f'<div class="ps-bar{" " + cls if cls else ""}"><span class="ps-chips"><button type="button" class="ps-chip" data-ps-open aria-haspopup="dialog">'
            f'<span class="ps-chip-k">Plays counted</span><b data-ps-label>All {len(TIMED)}</b><span class="ps-caret" aria-hidden="true">▾</span></button>'
            f'<button type="button" class="ps-chip" data-ps-open="weights" aria-haspopup="dialog">'
            f'<span class="ps-chip-k">Weights</span><b data-ps-wlabel>Plays + exit rules</b><span class="ps-caret" aria-hidden="true">▾</span></button></span>'
            f'<p class="small muted">{note} <a href="{h("guides/your-plays/")}">How it works</a></p></div>')


def fx_score(site, t):
    from .factors import score
    return score(site, t)


def sig_pill(sig):
    from .factors import SIG_WORD, SIG_CLS
    return f'<span class="sig-pill {SIG_CLS[sig]}">{SIG_WORD[sig] if sig is not None else "–"}</span>'


def slugify_group(g):
    return "".join(c if c.isalnum() else "-" for c in g.lower()).strip("-").replace("--", "-")


# Stock x play pages exist only for each stock's headline plays: the most accurate play in each
# family (Site.top_plays) plus these. Any other /stocks/<stock>/<play>/ address forwards to that
# play's row on the stock page (netlify.toml), which carries the same call, level and record.
HEADLINE_EXTRA = ("mayer-multiple",)
# Every play keeps one full example page, on SPY, because the Learn lessons walk through them;
# plus the RSI(2) on Tesla example in "Reading a backtest".
EXTRA_PAIRS = {("SPY", s["slug"]) for s in TIMED} | {("TSLA", "rsi-2-pullback")}
BASE = "https://bethepuck.com/"
DISCLAIMER = ("This analysis does not constitute trading advice. Please meet with an advisor or independently review sources "
              "before making any decision.")
# The Click Shift mark (cursor + yellow shift key, as on clickshift.ca) and a gold maple leaf for the footer.
CS_MARK = ('<span class="cs-mark" role="img" aria-label="Click Shift"><span class="cs-click" aria-hidden="true"><svg viewBox="0 0 24 24">'
           '<path fill="#ffffff" d="M4.037 4.688a.495.495 0 0 1 .651-.651l16 6.5a.5.5 0 0 1-.063.947l-6.124 1.58a2 2 0 0 0-1.438 1.435l-1.579 6.126a.5.5 0 0 1-.947.063z"/>'
           '</svg></span><span class="cs-shift" aria-hidden="true">shift</span></span>')
MAPLE = ('<svg class="maple" viewBox="-2015 -2000 4030 4030" aria-hidden="true"><path fill="currentColor" d="m-90 2030 45-863a95 95 0 0 0-111-98l-859 151 116-320a65 65 0 0 0-20-73l-941-762 212-99a65 65 0 0 0 34-79l-186-572 542 115a65 65 0 0 0 73-38l105-247 423 454a65 65 0 0 0 111-57l-204-1052 327 189a65 65 0 0 0 91-27l332-652 332 652a65 65 0 0 0 91 27l327-189-204 1052a65 65 0 0 0 111 57l423-454 105 247a65 65 0 0 0 73 38l542-115-186 572a65 65 0 0 0 34 79l212 99-941 762a65 65 0 0 0-20 73l116 320-859-151a95 95 0 0 0-111 98l45 863z"/></svg>')
FOOT_CREDITS = ('<div class="foot-credits"><a class="cs-credit" href="https://clickshift.ca/" rel="noopener">Created by ' + CS_MARK + '</a>'
                '<a class="ca-credit" href="https://proudtowork.ca/" rel="noopener">Proudly Canadian ' + MAPLE + '</a></div>')
def foot_disclaim(guide_href, broker_href=None):
    """The disclaimer that closes every page, with a link to who can advise, country by country, and the broker directory."""
    broker_href = broker_href or guide_href.replace("ways-to-invest/", "brokers/")
    return (f'<p class="foot-disclaim"><b>Not financial advice.</b> {DISCLAIMER} '
            f'Be The Puck is not a broker or an adviser and never places trades: to buy or sell, use a registered broker '
            f'(<a href="{broker_href}">find one</a>). '
            f'<a href="{guide_href}">Ways to invest in your country, and how to check an advisor</a>.</p>')


FOOT_DISCLAIM = foot_disclaim("/guides/ways-to-invest/")     # the hand-written pages (absolute link)
# The plays-only light (retired as a verdict in October 2026; Your signal replaced it). Only the
# Top 10's published rule and the members' /rules/ page still use it. It turns to Start when this
# share of the plays with a call hold the stock, and back to Stop only when the share falls
# to LIGHT_OFF, so a stock hovering near half doesn't flicker.
LIGHT_ON, LIGHT_OFF = 0.6, 0.4
LIGHT_HOW = (f"Start when {round(LIGHT_ON * 100)}% or more of the plays hold it; it stays Start until that falls to "
             f"{round(LIGHT_OFF * 100)}% or less, then turns Stop (and back again at {round(LIGHT_ON * 100)}%).")


def foot_cta(h, path=""):
    """The closing call to action above the footer (site.js hides it once signed in)."""
    second = (f'<a class="btn" href="{h("")}#screen">Open the screener</a>' if path.startswith("theory/")
              else f'<a class="btn" href="{h("theory/")}">Test a theory</a>')
    return (f'<section class="foot-cta" data-signed-out><div class="wrap foot-cta-in"><div><p class="eyebrow">Free account</p>'
            f'<p class="foot-cta-h">Know the moment the light flips on your stocks.</p>'
            f'<p class="muted">Follow your stocks and get an email with the analysis the evening a light flips. '
            f'Member tools are free until January 1, 2027.</p></div>'
            f'<div class="foot-cta-act"><a class="btn primary glow" href="{h("me/")}">Create your free account</a>'
            f'{second}</div></div></section>')


def light_badge(L, href=None, big=False):
    """The Start/Stop pill for a light dict (see Site.light)."""
    if not L or not L.get("state"):
        return '<span class="light-pill">–</span>'
    word = "Start" if L["state"] == "start" else "Stop"
    inner = f'<i aria-hidden="true"></i>{word}'
    cls = f'light-pill {L["state"]}{" lg" if big else ""}'
    tip = e(f'{L["k"]} of {L["n"]} plays in. {LIGHT_HOW}')
    return f'<a class="{cls}" href="{href}" title="{tip}">{inner}</a>' if href else f'<span class="{cls}" title="{tip}">{inner}</span>'
FONTS = ("https://fonts.googleapis.com/css2?family=Geist:wght@400;500;600;700"
         "&family=Geist+Mono:wght@400;500;600&family=Newsreader:opsz,wght@6..72,400;6..72,500;6..72,600&display=swap")
ICON = ("data:image/svg+xml,%3Csvg xmlns='http://www.w3.org/2000/svg' viewBox='0 0 64 64'%3E%3Crect width='64' height='64' rx='14' fill='%230b0f17'/%3E%3Cellipse cx='27' cy='44' rx='18' ry='7.5' fill='%235d6a82'/%3E%3Crect x='9' y='37' width='36' height='7' fill='%235d6a82'/%3E%3Cellipse cx='27' cy='37' rx='18' ry='7.5' fill='%23e7edf7'/%3E%3Cpath d='M44 27 L51.5 13 L59 27 Z' fill='%231fd093'/%3E%3C/svg%3E")
NAV = [("markets/", "Markets"), ("stocks/", "Stocks"), ("theory/", "Theory tester"), ("watchlist/", "Watchlist"), ("strategies/", "Plays"),
       ("learn/", "Learn"), ("articles/", "Articles"), ("desk/", "Live desk")]
NAV_ACTIVE = {"thinkers/": "strategies/"}   # analyst pages sit under Plays in the menu


def nav_menus():
    """Each top-level section's menu: (href, title, one-line description)."""
    return {
        "markets/": [("markets/", "Market weather", "The nine crash gauges and the overall read"),
                     ("markets/#idx-h", "Indexes and sectors", "The plays on the S&P 500, Nasdaq, Dow, Russell, TSX and sector funds"),
                     ("markets/#tops-h", "Today vs past market tops", "Each gauge at the 2000, 2007, 2020 and 2022 peaks"),
                     ("markets/#ex-h", "Who would feel a crash first", "Covered stocks ranked by crash exposure"),
                     ("markets/#positioning", "Cash, stay in, or buckets?", "Run your mix through real crashes")],
        "stocks/": [("stocks/", "All stocks", "Every name: plays in, analysts' upside, score, crash exposure"),
                    ("stocks/?sort=score", "Strongest setups", "Most plays in, plus room to the analysts' targets"),
                    ("stocks/?sort=crash", "Most crash-exposed", "Market swings, past crashes, debt and run-up"),
                    ("stocks/?view=families", "By play family", "Trend, breakout, momentum, reversion, volume, calendar"),
                    ("stocks/?group=ndx", "Nasdaq-100", "All 100 companies in the index, with the same reads"),
                    ("stocks/?group=tsx", "TSX stocks", f"The {n_tsx()} Toronto-listed companies, in Canadian dollars"),
                    ("watchlist/", "My watchlist", "Check your own stocks, or add ones Be The Puck doesn't cover"),
                    ("alerts/", "Free email alerts", "An email with the analysis when the light flips on your stocks"),
                    ("rules/", "Your own rules (members)", "Pick the plays, set when the light turns, check your portfolio"),
                    ("picks/", "Top picks (members)", "Five rule-based picks, tracked against the S&P 500")],
        "strategies/": [("strategies/", f"All {len(TIMED)} plays", "Seven families, what each says now and its record"),
                        ("guides/", "Which predictions work?", "Guides to every family and every play, from the backtests"),
                        ("articles/the-core-20/", "The 20 to learn first", "Where a newcomer should start"),
                        ("thinkers/", "Analysts", f"The {n_people()} people behind the plays"),
                        ("classics/", "The classics", "Forgotten strategies, the people behind them and the plays they led to"),
                        ("learn/call-it/", "Practise: Call it", "Read the plays on real charts")],
        "learn/": [("guides/", "Guides: which predictions work", "What each kind of play bets on, and how often it paid"),
                   ("guides/plan-an-account/", "Planning an account", "How many stocks, a core and caps: what mixes did since 2006"),
                   ("guides/ways-to-invest/", "Ways to invest, by country", "Who can advise you, what they must promise, how they've done"),
                   ("guides/brokers/", "Brokers and platforms", "Who can place your trades, manage the money, or copy and follow"),
                   ("learn/#track-basics", "Track 1: Stock basics", "Shares, candlesticks, trends, P/E, debt and risk"),
                   ("learn/#track-plays", "Track 2: The plays", "How each family of trading rules works"),
                   ("learn/#track-markets", "Track 3: Markets and risk", "Indexes, bubbles, crashes and positioning"),
                   ("learn/glossary/", "Glossary", "Every term in plain English")],
        "articles/": [("articles/#new-h", "Long reads", "Bubbles, crashes, debt and positioning"),
                      ("articles/#stocks", "Stock briefs", "A plain-English brief on every covered name"),
                      ("articles/#strategies", "Strategies and sectors", "The 20 to learn first, regimes, backtests, sector briefs"),
                      ("articles/#macro", "Macro", "The bubble question, crash history, cash vs invested"),
                      ("articles/#automate", "Automate with Claude", "Claude drafts from your rules; you approve each order"),
                      ("members/", "Members", "The reports, the top picks and alerts on your stocks")],
    }
CORE_ATTR = ' data-core="1"'
CO_ATTR = ' data-co="1"'
ROLE_VAR = {"s1": "--s1", "s2": "--s2", "s3": "--s3", "price": "--s-price", "bench": "--s-bench"}


# --------------------------------------------------------------------------
# formatting
# --------------------------------------------------------------------------
def money(v, cur="$"):
    if v is None or (isinstance(v, float) and math.isnan(v)):
        return "–"
    if abs(v) >= 10000:
        return f"{cur}{v:,.0f}"
    if 0 < abs(v) < 1:            # sub-dollar and penny stocks: keep 3 significant digits
        places = min(6, max(2, -int(math.floor(math.log10(abs(v)))) + 2))
        return f"{cur}{v:.{places}f}"
    return f"{cur}{v:,.2f}"


def pct(v, sign=True, d=1):
    if v is None or (isinstance(v, float) and math.isnan(v)):
        return "–"
    s = f"{abs(v) * 100:,.{d}f}%"
    if v < 0 and round(abs(v) * 100, d) != 0:
        return "−" + s
    return ("+" + s) if (sign and v > 0) else s


def ratio(v):
    return "–" if v is None else f"{v:.2f}".replace("-", "−")


def dlong(ts):
    return "–" if ts is None else pd.Timestamp(ts).strftime("%b %-d, %Y")


def dshort(ts):
    return "–" if ts is None else pd.Timestamp(ts).strftime("%b %-d")


def dir_cls(v):
    return "" if v is None else ("up" if v > 0 else "down" if v < 0 else "")


def pill(state, lg=False):
    if state is None:
        return '<span class="pill">–</span>'
    cls = "in" if state == 1 else "out"
    return f'<span class="pill {cls}{" lg" if lg else ""}">{"IN" if state == 1 else "OUT"}</span>'


def sortv(v):
    """Raw value for a cell's data-v sort attribute; blank sorts last."""
    return "" if v is None or (isinstance(v, float) and math.isnan(v)) else f"{v:.6g}"


BAND_MARK = '<span class="band-mark" title="Inside the band"></span>'


def flag_tag(s):
    return f' <span class="tag warn">{e(s["flag"])}</span>' if s.get("flag") else ""


def sig(v, n=5):
    if v is None:
        return None
    v = float(v)
    if math.isnan(v) or math.isinf(v):
        return None
    return float(f"{v:.{n}g}")


sig5 = sig


def n_people():
    """Analysts behind at least one play (not the benchmark, not 'market tradition')."""
    return len([a for a in THINKERS if a["strategies"] and not a.get("benchmark") and a["slug"] != "market-tradition"])


def n_tsx():
    """Toronto-listed companies covered (the TSX filter on the stock list)."""
    return len([t for t in universe() if t.get("tsx")])


def fill_bar(k, n):
    w = 0 if not n else round(100 * k / n)
    return (f'<span class="fillbar" aria-hidden="true"><i style="width:{w}%"></i></span>')


def count_in(k, n, word="in"):
    return f'<span class="consensus">{fill_bar(k, n)}{k} of {n} {word}</span>'


# --------------------------------------------------------------------------
# the "next move" sentence
# --------------------------------------------------------------------------
BAR_CLOSE = {"D": "a daily close", "W": "a weekly close", "M": "a month-end close"}
BAR_PERIOD = {"W": "week", "M": "month"}
WAIT = {
    "rsi-30-70": "It needs RSI to cross 30 or 70, which takes more than one day from here.",
    "stochastic-20-80": "It needs a %K/%D crossover inside the 20 or 80 zone, which takes more than one day from here.",
    "williams-percent-r": "It needs %R to cross −80 or −20, which takes more than one day from here.",
    "money-flow-index": "It needs the MFI to cross 20 or 80, which takes more than one day from here.",
    "demark-setup-9": "It needs a full nine-day setup to complete.",
    "williams-alligator": "The Alligator's lines are shifted forward in time, so tomorrow's close can't move them.",
    "twelve-one-momentum": "The rule skips the most recent month, so the next close doesn't count. Its next call is already set by closes you can see.",
    "golden-cross": "The 50- and 200-day averages are too far apart for one close to cross them.",
    "seykota-crossover": "The two averages are too far apart for one close to cross them.",
    "on-balance-volume": "On-balance volume moves by one day's volume at most, which isn't enough here.",
    "chaikin-money-flow": "Money flow would need to move past ±0.05, more than one day can do from here.",
    "coppock-curve": "The curve moves slowly; one month-end won't turn it.",
    "rsi-2-pullback": "It needs a dip that drives the 2-day RSI under 10 while the stock holds above its 200-day average.",
    "double-7s": "It needs a close at a 7-day low while the stock holds above its 200-day average.",
    "mayer-multiple": "The price would need to reach 2.4 times its 200-day average.",
    "trend-template": "Several conditions are failing at once, so no single close passes them all.",
    "darvas-box": "It needs a confirmed box first: three days without a new high, then three without a new low.",
    "adx-directional-movement": "It needs +DI above −DI with ADX above 25, and ADX moves slowly.",
    "best-six-months-macd": "The buy window is open, but it needs a fresh MACD crossover, which takes more than one day from here.",
    "seasonal-timing-strategy": "The window is open, but MACD would need to cross its signal line, which takes more than one day from here.",
    "cci-100": "It needs the CCI to cross +100, which takes more than one day from here.",
    "elder-impulse": "It needs the 13-day EMA and the MACD histogram to move together, which takes more than one day from here.",
    # the plays added in October 2026
    "frog-in-the-pan": "It is decided at month-end from returns that stop a month earlier, so the next close can't change it.",
    "january-barometer": "Only SPY's January return decides this call, at the last close of January; a December close puts it back in.",
    "market-state-momentum": "It needs the stock's 12-1 return and SPY's 3-year return both above zero at a month-end.",
    "short-term-reversal": "It is decided at month-end from the month's return against SPY's.",
    "connorsrsi-pullback": "It needs a strong trend, a one-day drop of 4% or more and ConnorsRSI under 10, all on the same day.",
    "connors-percent-b": "It needs %b under 0.2 for three closes in a row while the stock holds above its 200-day average.",
    "negative-volume-index": "The index moves only on days when volume falls, and it sits too far from its average for one day to cross it.",
    "volume-flow-indicator": "One day's volume moves the VFI only a little, not enough to cross zero from here.",
    "engulfing-switch": "It needs an engulfing candle after a decline (to buy) or after a rise (to sell).",
    "hikkake": "It needs an inside day, a false break and a close back through the inside day's range within 3 days.",
    "turtle-soup-plus-one": "It needs a close under an old 20-day low, then a close back above it the next day.",
    "raschke-holy-grail": "It needs a strong trend (ADX above 30) and a pullback to the 20-day EMA first, then a close above the pullback day's high.",
    "elder-triple-screen": "The weekly MACD histogram has to be rising and a daily dip (Force Index below zero) has to set up the buy first.",
    "ttm-squeeze": "It needs the Bollinger Bands to squeeze inside the Keltner Channel and then fire with momentum above zero and rising.",
    "bollinger-squeeze": "It needs the bands at their narrowest in 125 days within the last 5 days, then a close above the upper band.",
    "headley-acceleration-bands": "It needs two closes in a row above the upper acceleration band.",
    "crabel-nr7": "It needs a close beyond the latest narrow-range (NR7) day's high or low.",
    "pf-double-top-breakout": "The point-and-figure chart needs a column that breaks past the last column's top (to buy) or bottom (to sell).",
    "ehlers-zero-lag": "The error-corrected line has to cross its 32-day EMA while sitting more than 0.75% from the close, more than one close can do from here.",
}


def next_move(res, s, t):
    cur, price, trig, bar = t["cur"], res["price"], res["trigger"], res["bar"]
    out = {"headline": "", "short": "", "level": None, "dist": None, "check": "", "alert": None, "notes": [],
           "checks": trig.get("extra", {}).get("checks"), "kind": trig.get("kind")}
    nc = res["next_check"]
    if bar == "D":
        out["check"] = f"Next check: the {dlong(nc)} close"
    elif res["bar_complete"]:
        out["check"] = f"Next check: the {BAR_PERIOD[bar]} ending {dlong(nc)}"
    else:
        out["check"] = f"Next check: this {BAR_PERIOD[bar]}'s close, {dlong(nc)}"
    if s.get("benchmark"):
        out.update(headline="Always in. Nothing in this rule ever sells.", short="Always in", check="No check needed")
        return out
    st = res["state"]
    if st is None:
        out.update(headline="Not enough price history yet for this play to make a call.", short="Not enough history")
        return out
    kind = trig.get("kind")
    if kind == "date":
        d = trig.get("date")
        if d is None:
            out.update(headline="No calendar change in the next year.", short="–")
            return out
        verb = "buys" if trig["to"] == 1 else "sells"
        out.update(headline=f"Stays {'in' if st == 1 else 'out'} until the close on {dlong(d)}, when the calendar says it {verb}. No price can change that.",
                   short=f"{'Buys' if trig['to'] == 1 else 'Sells'} {dshort(d)}", check=f"Next change: the {dlong(d)} close",
                   date=d)
        out["dist_days"] = (pd.Timestamp(d) - res["asof"]).days
        return out
    if kind == "window":
        d, which = trig["date"], trig["which"]
        if which == "buy":
            out.update(headline=f"Stays out until the buy window opens on {dlong(d)}. From then it waits for a MACD buy signal.", short=f"Window opens {dshort(d)}")
        else:
            out.update(headline=f"Stays in until the sell window opens on {dlong(d)}. From then it waits for a MACD sell signal.", short=f"Window opens {dshort(d)}")
        out["dist_days"] = (pd.Timestamp(d) - res["asof"]).days
        return out
    segs = trig.get("segments") or []
    bc = BAR_CLOSE[bar]
    if not segs:
        lo, hi = trig.get("span", (None, None))
        rng = f", not even one as low as {money(lo, cur)} or as high as {money(hi, cur)}" if lo else ""
        out["headline"] = f"No single {bc[2:]} can flip this call{rng}. {WAIT.get(s['slug'], 'It needs a bigger move, or more time, than one close can deliver.')}"
        out["short"] = "Not on one close"
    else:
        def gap(seg):
            a, b = seg
            if a is not None and b is not None and a <= price <= b:
                return 0.0
            return min(abs(np.log(x / price)) for x in (a, b) if x is not None) if (a or b) else 9.0
        seg = min(segs, key=gap)
        a, b = seg
        exit_ = st == 1
        if a is None and b is None:
            out["headline"] = f"The next check flips it whatever the price: the rule will {'sell' if exit_ else 'buy'}."
            out["short"] = "Flips at next check"
        elif a is None:
            lvl = b
            out["headline"] = (f"Stays in unless {bc} lands below {money(b, cur)}." if exit_ else f"Buys on {bc} below {money(b, cur)}.")
            out["short"] = f"{'Exit' if exit_ else 'Buy'} below {money(b, cur)}"
            out["level"] = lvl
        elif b is None:
            lvl = a
            out["headline"] = (f"Sells on {bc} above {money(a, cur)}." if exit_ else f"Stays out until {bc} lands above {money(a, cur)}.")
            out["short"] = f"{'Sell' if exit_ else 'Enter'} above {money(a, cur)}"
            out["level"] = lvl
        else:
            lvl = a if abs(np.log(a / price)) < abs(np.log(b / price)) else b
            out["headline"] = f"{'Sells' if exit_ else 'Buys'} on {bc} between {money(a, cur)} and {money(b, cur)}."
            out["short"] = f"{'Sell' if exit_ else 'Buy'} {money(a, cur)}–{money(b, cur)}"
            out["level"] = lvl
        if out["level"] is not None:
            out["dist"] = out["level"] / price - 1
        for o in segs:
            if o is seg:
                continue
            oa, ob = o
            if oa is None and ob is not None:
                out["notes"].append(f"It would also {'sell' if exit_ else 'buy'} on a close below {money(ob, cur)}.")
            elif ob is None and oa is not None:
                out["notes"].append(f"It would also {'sell' if exit_ else 'buy'} on a close above {money(oa, cur)}.")
            elif oa is not None:
                out["notes"].append(f"It would also {'sell' if exit_ else 'buy'} on a close between {money(oa, cur)} and {money(ob, cur)}.")
        if s["slug"] == "stocks-on-the-move" and exit_ and any(o[1] is None for o in segs):
            out["notes"].append("A one-day jump of more than 15% also breaks this play's rules, which is why a big up day can trigger a sell.")
    now = trig.get("now")
    if bar != "D" and not res["bar_complete"] and now is not None and now != st:
        out["alert"] = (f"At the latest close ({money(price, cur)}) the rule would already {'sell' if st == 1 else 'buy'} "
                        f"if the {BAR_PERIOD[bar]} ended today.")
    zone = trig.get("extra", {}).get("zone")
    if s.get("band") and zone == "between":
        out["notes"].append("Price is inside the band, so the rule is holding its last call.")
    if s["slug"] == "trend-template" and st == 0 and out["level"] is not None:
        out["notes"].append("That is the lowest close that would pass every price condition at once.")
    return out


# --------------------------------------------------------------------------
# chart specs
# --------------------------------------------------------------------------
def _runs(pos):
    runs, start, prev = [], None, None
    vals = pos.values
    for i, v in enumerate(vals):
        v = None if (v is None or (isinstance(v, float) and math.isnan(v))) else int(v)
        if v != prev:
            if prev is not None:
                runs.append([start, i - 1, prev])
            start, prev = i, v
    if prev is not None:
        runs.append([start, len(vals) - 1, prev])
    return runs


def _days(idx):
    t0 = idx[0]
    return t0.strftime("%Y-%m-%d"), [int((d - t0).days) for d in idx]


def price_spec(res, s, t, with_rule=True):
    win = res["window"]["price"]
    t0, d = _days(win.index)
    yrs = "two" if not s.get("benchmark") else "three"
    spec = {"t0": t0, "d": d, "cur": t["cur"], "fmt": "price",
            "label": f"{t['short']} price, last {yrs} years", "series": [{"name": t["short"], "role": "price", "v": [sig(v) for v in win.values]}]}
    if with_rule and not s.get("benchmark"):
        for lab, ser, role in res["window"]["lines"]:
            spec["series"].append({"name": lab, "role": role, "v": [sig(v) for v in ser.values]})
        spec["runs"] = _runs(res["window"]["pos"])
        spec["label"] = f"{t['short']} price with the {s['name']} play, last two years"
    return spec


def panel_spec(res, s, t):
    pn = res["window"].get("panel")
    if not pn:
        return None
    win = res["window"]["price"]
    t0, d = _days(win.index)
    spec = {"t0": t0, "d": d, "cur": "", "fmt": "pct" if pn["fmt"] == "pct" else "num", "label": pn["label"],
            "series": [{"name": lab, "role": role, "v": [sig(v, 4) for v in ser.values]} for lab, ser, role in pn["series"]],
            "levels": pn["levels"], "runs": _runs(res["window"]["pos"]), "small": True}
    if pn.get("min") is not None:
        spec["ymin"] = pn["min"]
    if pn.get("max") is not None:
        spec["ymax"] = pn["max"]
    return spec


def equity_spec(res, s, t):
    eq = res["equity"]
    dates = pd.DatetimeIndex(eq["dates"])
    step = max(1, len(dates) // 320)
    keep = list(range(0, len(dates), step))
    if keep and keep[-1] != len(dates) - 1:
        keep.append(len(dates) - 1)
    idx = dates[keep]
    t0, d = _days(idx)
    return {"t0": t0, "d": d, "cur": t["cur"], "fmt": "money", "log": True, "label": f"Growth of 10,000 in {t['short']}",
            "series": [{"name": s["name"], "role": "s1", "v": [sig(eq["strat"][i] * 10000, 4) for i in keep]},
                       {"name": "Buy & hold", "role": "bench", "v": [sig(eq["bh"][i] * 10000, 4) for i in keep]}]}


def chart_block(cid, spec, keys_html, title, note=None, small=False):
    data = json.dumps(spec, separators=(",", ":")).replace("</", "<\\/")
    return (f'<div class="card chart-card"><div class="chart-top"><h3 class="h3">{title}</h3>'
            f'<div class="legend-row">{keys_html}</div></div>'
            f'<div class="chart{" chart-sm" if small else ""}" data-chart="{cid}" aria-label="{e(spec.get("label", title))}"></div>'
            f'<script type="application/json" id="{cid}">{data}</script>'
            + (f'<p class="chart-note">{note}</p>' if note else "") + "</div>")


def key_line(color_var, label):
    return f'<span class="key"><i style="background:var({color_var})"></i>{e(label)}</span>'


def key_wash(kind, label):
    bg = "var(--in-wash)" if kind == "in" else "var(--out-wash)"
    edge = "var(--in-edge)" if kind == "in" else "var(--out-edge)"
    return f'<span class="key"><s style="background:{bg};box-shadow:inset 0 0 0 1px {edge}"></s>{e(label)}</span>'


# --------------------------------------------------------------------------
# site
# --------------------------------------------------------------------------
class Site:
    def __init__(self, results, preview=False, built=None, prices=None, irx=None, meta=None):
        self.R = results
        self.meta = meta or {}
        self.universe = universe()
        self.macro = None
        from .risk import load_fundamentals
        self.fund = load_fundamentals(TICKERS)
        self.preview = preview
        self.built = built
        self.prices = prices
        self.irx = irx
        self.asof = max(r["asof"] for r in results.values())
        self.pages = {}   # path -> html (or None once written to self.out)
        self.art_links = {}   # article path -> slugs of the stocks it links to (articles.index_json: the hub's "your stocks" view)
        self.on_page = None   # called with (path, html) for every page as it is made
        self.out = None   # set to a folder to write each page as it is made (keeps memory flat)
        self.ver = self.asof.strftime("%Y%m%d")
        self._sum = {}
        self._acc, self._top = {}, None
        from .learn import Learn
        self.learn = Learn(self)

    # ----- helpers -----
    def r(self, sym, slug):
        return self.R[(sym, slug)]

    def href(self, depth, target):
        path = target
        if self.preview and (target == "" or target.endswith("/")):
            path += "index.html"
        elif self.preview and "/#" in target:
            a, _, b = target.partition("#")
            if a.endswith("/"):
                path = a + "index.html#" + b
        return ("../" * depth + path) or "./"

    def pair_path(self, t, s):
        return f"stocks/{t['slug']}/{s['slug']}/"

    def headline_plays(self):
        """The plays that get a page of their own on every stock (see HEADLINE_EXTRA)."""
        if getattr(self, "_headline", None) is None:
            got = [p for _, p, _ in self.top_plays()]
            got += [PLAY[x] for x in HEADLINE_EXTRA if x in PLAY and PLAY[x] not in got]
            self._headline = got
        return self._headline

    def headline_slugs(self):
        return {p["slug"] for p in self.headline_plays()}

    def pair_link(self, t, s):
        """Where a link to play s on stock t goes: its own page for a headline play, else the play's row on the stock page."""
        if s["slug"] in self.headline_slugs() or (t["sym"], s["slug"]) in EXTRA_PAIRS:
            return self.pair_path(t, s)
        return f"stocks/{t['slug']}/#play-{s['slug']}"

    def pair_or_stock(self, t, s):
        return self.pair_link(t, s)

    def shell(self, path, title, desc, body, active=None, charts=False, extra_head="", lesson=None, glossary=False, scripts=(), link=True, og="og-default.png"):
        depth = path.count("/")
        if link:
            body = link_terms(body, self.learn.href_for(depth, "glossary" if glossary else lesson))
        h = lambda target: self.href(depth, target)
        cur_attr = ' aria-current="page"'
        act = NAV_ACTIVE.get(active, active)
        menus = nav_menus()
        nav = ""
        for p, lab in NAV:
            items = menus.get(p)
            cur = cur_attr if p == act else ""
            if items:
                dd = "".join(f'<a href="{h(u)}"><b>{e(t)}</b><span>{e(d)}</span></a>' for u, t, d in items)
                nav += (f'<div class="nav-item has-dd"><a class="nav-top" href="{h(p)}"{cur} aria-haspopup="true" aria-expanded="false">{lab}<i class="caret" aria-hidden="true"></i></a>'
                        f'<div class="dd"><div class="dd-in">{dd}</div></div></div>')
            else:
                nav += f'<div class="nav-item"><a class="nav-top" href="{h(p)}"{cur}>{lab}</a></div>'
        full_title = f"{title} · Be The Puck" if path else title
        more = "".join(f'<script src="{h(sx)}?v={self.ver}" defer></script>\n' for sx in scripts)
        from .members import is_locked, free_bar
        banner = free_bar(self, depth) if is_locked(path) and not path.startswith("locked/") else ""
        cta = "" if (not path or path.startswith(("me/", "locked/"))) else foot_cta(h, path)
        return f"""<!doctype html>
<html lang="en" data-view="simple">
<head>
<meta charset="utf-8">
<script>try{{if(localStorage.getItem('bp.view')==='full')document.documentElement.setAttribute('data-view','full')}}catch(e){{}}</script>
<meta name="viewport" content="width=device-width, initial-scale=1, viewport-fit=cover">
<title>{e(full_title)}</title>
<meta name="description" content="{e(desc)}">
<link rel="canonical" href="{BASE}{path}">
<link rel="alternate" type="text/plain" href="{BASE}llms.txt" title="Be The Puck for AI tools">
<meta property="og:title" content="{e(full_title)}">
<meta property="og:description" content="{e(desc)}">
<meta property="og:url" content="{BASE}{path}">
<meta property="og:type" content="website">
<meta property="og:image" content="{BASE}{og}">
<meta name="twitter:card" content="summary_large_image">
<meta name="theme-color" content="#0b0f17">
<link rel="icon" type="image/svg+xml" href="{ICON}">
<link rel="apple-touch-icon" href="{h('apple-touch-icon.png')}">
<link rel="preconnect" href="https://fonts.googleapis.com">
<link rel="preconnect" href="https://fonts.gstatic.com" crossorigin>
<link rel="stylesheet" href="{FONTS}">
<link rel="stylesheet" href="{h('assets/site.css')}?v={self.ver}">
{extra_head}{'<meta name="robots" content="noindex">' + chr(10) if private_path(path) and 'name="robots"' not in extra_head else ""}</head>
<body>
<a class="skip" href="#main">Skip to content</a>
<header class="site-head"><div class="wrap head-row">
<a class="logo" href="{h('')}">be<span class="logo-the">the</span>puck<span class="logo-tick">▲</span></a>
<nav class="site-nav" id="site-nav" aria-label="Main">{nav}<a class="nav-me" href="{h('me/')}">Login</a></nav>
<span class="head-meta" data-mkt data-asof="{self.asof.strftime('%Y-%m-%d')}"><i aria-hidden="true"></i><span data-mkt-txt>{dshort(self.asof)} close</span></span>
<a class="acct-btn" href="{h('me/')}" data-acct-btn><span class="acct-ava" aria-hidden="true"></span><span data-acct-label>Login</span></a>
<button type="button" class="nav-toggle" aria-controls="site-nav" aria-expanded="false" aria-label="Menu"><span></span><span></span><span></span></button>
</div><div class="scroll-bar" aria-hidden="true"></div></header>
{banner}<main class="wrap" id="main">
{body}
</main>
{cta}<footer class="site-foot"><div class="wrap">
<div class="foot-cols">
<div class="foot-brand"><a class="logo" href="{h('')}">be<span class="logo-the">the</span>puck<span class="logo-tick">▲</span></a>
<p>{len(TIMED)} published trading plays run on real prices after every U.S. close, with the price that would change each one's mind. It takes no positions in the names it covers.</p></div>
<div><p class="foot-h">Stocks</p><a href="{h('stocks/')}">All stocks</a><a href="{h('watchlist/')}">Watchlist</a><a href="{h('markets/')}">Markets</a><a href="{h('desk/')}">Live desk</a></div>
<div><p class="foot-h">Tools</p><a href="{h('theory/')}">Theory tester</a><a href="{h('')}#screen">Stock screener</a><a href="{h('alerts/')}">Free email alerts</a><a href="{h('developers/')}">For AI tools</a><a href="{h('me/')}" data-nav-me>Login</a></div>
<div><p class="foot-h">Learn</p><a href="{h('guides/')}">Which predictions work?</a><a href="{h('guides/your-plays/')}">Pick your plays</a><a href="{h('guides/news-that-moves-stocks/')}">News that moves stocks</a><a href="{h('strategies/')}">All {len(TIMED)} plays</a><a href="{h('learn/')}">Learn</a><a href="{h('method/')}">How we test</a></div>
<div><p class="foot-h">Members</p><a href="{h('members/')}">Membership</a><a href="{h('picks/')}">Top picks</a><a href="{h('rules/')}">Your own rules</a><a href="{h('articles/')}">Reports</a></div>
</div>
{foot_disclaim(h('guides/ways-to-invest/'))}
<p class="foot-view small" role="group" aria-label="How much detail to show">View: <button type="button" class="linkish" data-view-set="simple">Simple</button> · <button type="button" class="linkish" data-view-set="full">Detailed</button> <span class="muted">Simple shows the call and why; Detailed shows every number.</span></p>
<p class="foot-meta">Closes through {dlong(self.asof)} · Prices from Yahoo Finance, macro data from FRED and multpl · Rebuilt after each U.S. close</p>
{FOOT_CREDITS}
</div></footer>
<script src="{h('assets/site.js')}?v={self.ver}" defer></script>
<script src="{h('assets/sortable.js')}?v={self.ver}" defer></script>
<script src="{h('assets/glossary.js')}?v={self.ver}" defer></script>
<script src="{h('assets/account.js')}?v={self.ver}" defer></script>
<script src="{h('assets/mine.js')}?v={self.ver}" defer></script>
<script src="{h('assets/view.js')}?v={self.ver}" defer></script>
{more}</body>
</html>
"""

    def add(self, path, html_):
        from .hints import annotate
        page = annotate(html_, path)
        if self.on_page:                     # the build's per-page check (build_strategies.note_banned)
            self.on_page(path, page)
        if path.startswith("articles/") and not path.startswith("articles/stocks/"):
            self.art_links[path] = set(re.findall(r'href="[^"]*?\bstocks/([a-z0-9][a-z0-9.-]*)/', page))
        if self.out:
            d = os.path.join(self.out, path)
            os.makedirs(d, exist_ok=True)
            with open(os.path.join(d, "index.html"), "w", encoding="utf-8") as f:
                f.write(page)
            page = None
        self.pages[path] = page

    def not_found_html(self):
        """404.html: what Netlify serves for an address that isn't on the site. It can be served at
        any depth, so a <base href="/"> makes its links resolve from the site root."""
        h = lambda x: self.href(0, x)
        links = [("stocks/", "All stocks", f"Your signal on all {len(universe())} stocks and funds"),
                 ("watchlist/", "Watchlist", "The stocks you follow, in one list"),
                 ("strategies/", "Plays", f"All {len(TIMED)} published plays and how often they've been right"),
                 ("articles/", "Reports", "What the numbers say this week"),
                 ("learn/", "Learn", "How to read a play, a backtest and a signal")]
        items = "".join(f'<li><a href="{h(u)}"><b>{e(t)}</b></a> <span class="muted">{e(d)}</span></li>' for u, t, d in links)
        body = f"""
<section class="pair-head"><p class="eyebrow">Page not found</p><h1 class="h1">That page isn't here</h1>
<p class="lede">The address may have changed, or the page was retired. A stock's page is at /stocks/ and its ticker, like <a href="{h('stocks/mu/')}">/stocks/mu/</a>.</p></section>
<section class="card prose"><ul>{items}</ul></section>"""
        page = self.shell("", "Page not found · Be The Puck", "That page isn't on Be The Puck.", body, link=False,
                          extra_head='<meta name="robots" content="noindex">\n')
        # <base> has to come before every relative URL in the head, or the stylesheet loads from the wrong folder
        return page.replace(f'<link rel="canonical" href="{BASE}">\n', "").replace("<head>\n", '<head>\n<base href="/">\n', 1)

    # ----- aggregates -----
    def strat_summary(self, s):
        if s["slug"] in self._sum:
            return self._sum[s["slug"]]
        rows = [self.r(t["sym"], s["slug"]) for t in universe()]
        n = len(rows)
        full = [(x["stats"]["full"]["strat"] or {}, x["stats"]["full"]["bh"] or {}) for x in rows]
        ok = [(a, b) for a, b in full if a and b]
        right = sum(x["batting"]["right"] for x in rows)
        calls = sum(x["batting"]["n"] for x in rows)
        sw = [x["stats"]["switches_per_year"] for x in rows if x["stats"]["start"] is not None]
        out = {
            "n": n, "graded": len(ok),
            "in_now": sum(1 for x in rows if x["state"] == 1),
            "beat_sharpe": sum(1 for a, b in ok if a["sharpe"] is not None and b["sharpe"] is not None and a["sharpe"] > b["sharpe"]),
            "beat_cagr": sum(1 for a, b in ok if a["cagr"] > b["cagr"]),
            "cut_dd": sum(1 for a, b in ok if a["maxdd"] > b["maxdd"]),
            "bat": right / calls if calls else None, "calls": calls,
            "switches": float(np.median(sw)) if sw else None,
            "med_cagr_gap": float(np.median([a["cagr"] - b["cagr"] for a, b in ok])) if ok else None,
            "med_dd_gap": float(np.median([a["maxdd"] - b["maxdd"] for a, b in ok])) if ok else None,
        }
        self._sum[s["slug"]] = out
        return out

    def play_accuracy(self, s):
        """How often a play's finished calls went the right way (an in call followed by a rise,
        an out call by a fall) across the real stocks: {"bat", "right", "calls", "stocks"}."""
        hit = self._acc.get(s["slug"])
        if hit is None:
            right = calls = stocks = 0
            for t in universe():
                if not is_stock(t):
                    continue
                b = self.r(t["sym"], s["slug"])["batting"]
                right, calls, stocks = right + b["right"], calls + b["n"], stocks + (1 if b["n"] else 0)
            hit = self._acc[s["slug"]] = {"bat": right / calls if calls else None, "right": right, "calls": calls, "stocks": stocks}
        return hit

    def timed_family(self, fk):
        return [p for p in TIMED if p["family"] == fk]

    def top_plays(self):
        """The most accurate play in each family, as [(family key, play, accuracy)].
        Plays with too few finished calls, or calls on too few stocks, aren't ranked."""
        if self._top is None:
            out, ns = [], n_stocks()
            for fk in FAMILY_ORDER:
                ok = [(self.play_accuracy(p), p) for p in self.timed_family(fk)]
                ok = [(a, p) for a, p in ok if rankable(a, ns)]
                if ok:
                    a, p = max(ok, key=lambda ap: (ap[0]["bat"], ap[0]["calls"]))
                    out.append((fk, p, a))
            self._top = out
        return self._top

    def top_plays_block(self, t, h):
        """Stock overview: the most accurate play in each family and what it says about this stock now."""
        top = self.top_plays()
        if not top:
            return ""
        cards = ""
        for fk, p, a in top:
            x = self.r(t["sym"], p["slug"])
            b = x["batting"]
            here = (f'On {e(t["short"])}: right {b["right"]} of {b["n"]}' if b["n"] else f'No finished calls on {e(t["short"])} yet')
            since = (f'{"In" if x["state"] == 1 else "Out"} since {dlong(x["since"])}' if x["state"] is not None and x.get("since") is not None else "")
            cards += (f'<a class="card tp" data-fam="{fk}" href="{h(self.pair_path(t, p))}"><span class="tp-fam">{icon(fk)}{e(FAMILY[fk][0])}</span>'
                      f'<span class="tp-name"><span class="tp-nm">{play_name_html(p)}</span>{pill(x["state"])}</span>'
                      f'<span class="tp-line">{e(p.get("oneline") or "")}</span>'
                      f'<span class="tp-acc"><b>{pct(a["bat"], sign=False, d=0)}</b> of {a["calls"]:,} calls right</span>'
                      f'<span class="tp-here">{here}{" · " + since if since else ""}</span></a>')
        return f"""<section class="top-plays" id="top-plays" aria-labelledby="tp-h"><div class="sec-head"><h2 class="h2" id="tp-h">The most accurate play in each family</h2>
<p data-ps-tp-sub>Each family's play whose calls went the right way most often, tested on {n_stocks()} stocks since {GRADE_YEAR}, and what it says about {e(t['short'])} now.</p></div>
<div class="tp-grid">{cards}</div>
<p class="muted small">A call is right when the stock rose after an in call or fell after an out call. Trend plays are built to take many small losses for a few big wins, so their hit rates run lower; being right often isn't the same as making the most money. <a href="{h('method/')}">How we test a play</a>.</p></section>"""

    def mayer_tile(self, t, h):
        """Stock overview: price over its 200-day average, against Mayer's 2.4 line and the stock's own history."""
        d = self.prices.get(t["sym"]) if self.prices else None
        if d is None or len(d) < 220:
            return ""
        cl = d["close"]
        mm = (cl / cl.rolling(200).mean()).dropna()
        m = float(mm.iloc[-1])
        hist = mm[mm.index >= pd.Timestamp(f"{GRADE_YEAR}-01-01")]
        if len(hist) < 20:
            hist = mm
        share = round(100 * float((hist < m).mean()))
        gap = m - 1
        return (f'<a class="card tile tile-link" href="{h(self.pair_path(t, PLAY["mayer-multiple"]))}"><span class="tile-label">Mayer Multiple</span>'
                f'<span class="tile-value {"down" if m >= 2.4 else ""}">{m:.2f}<small>×</small></span>{fill_bar(round(min(m, 2.4) * 100), 240)}'
                f'<span class="tile-note">Price ÷ its 200-day average ({pct(gap, d=0)}). Higher than on {share}% of days since {hist.index[0].year}. '
                f'Above 2.4 is Mayer\'s overheated zone.</span></a>')

    def light(self, t):
        """{"state": "start"|"stop"|None, "share", "k", "n", "since"}: the latched Start/Stop
        for a stock, walked through two years of weekly calls and then today's."""
        sym = t["sym"]
        cache = self.__dict__.setdefault("_lights", {})
        if sym in cache:
            return cache[sym]
        hs = [(self.R.get((sym, p["slug"])) or {}).get("hist") or "" for p in TIMED]
        L = max((len(h) for h in hs), default=0)
        weeks = (self.meta.get(sym) or {}).get("weeks") or []
        state, since = None, None

        def step(k, n, when):
            nonlocal state, since
            if n < 5:
                return
            sh = k / n
            new = state
            if state is None:
                new = "start" if sh >= 0.5 else "stop"
            elif state == "stop" and sh >= LIGHT_ON:
                new = "start"
            elif state == "start" and sh <= LIGHT_OFF:
                new = "stop"
            if new != state:
                state, since = new, when
        for j in range(-L, 0):          # weeks, aligned on the latest
            col = [h[j] for h in hs if len(h) >= -j]
            k, n = sum(1 for c in col if c == "1"), sum(1 for c in col if c in "01")
            step(k, n, weeks[j] if len(weeks) >= -j else None)
        k, n = self.consensus(t)
        step(k, n, self.r(sym, "buy-and-hold")["asof"])
        out = {"state": state, "share": (k / n) if n else None, "k": k, "n": n, "since": since}
        cache[sym] = out
        return out

    def consensus(self, t, plays=None):
        states = [self.r(t["sym"], s["slug"])["state"] for s in (plays or TIMED)]
        return sum(1 for x in states if x == 1), sum(1 for x in states if x is not None)

    def meter(self, k, n):
        return count_in(k, n)

    def play_options(self, selected=None, value=None, core_only=False):
        """core_only: just the core plays (every play is core now, so this keeps them all)."""
        out = ""
        for fk, fname, _ in FAMILIES:
            opts = "".join(f'<option value="{e(value(p) if value else p["slug"])}"{CORE_ATTR if p.get("core") else ""}'
                           f'{" selected" if p["slug"] == selected else ""}>{e(play_label(p))} · {e(credit(p))}</option>'
                           for p in TIMED if p["family"] == fk and (p.get("core") or not core_only))
            if opts:
                out += f'<optgroup label="{e(fname)}">{opts}</optgroup>'
        return out

    def stock_options(self, selected=None, value=None, full_only=False):
        """full_only: leave out names without a page for every play (none, now every play is core)."""
        names = [t for t in universe() if not (full_only and t.get("core_only"))]
        out = ""
        for g in [x for x in GROUP_ORDER if any(t["group"] == x for t in names)]:
            out += f'<optgroup label="{e(g)}">' + "".join(
                f'<option value="{e(value(t) if value else t["slug"])}"{CO_ATTR if t.get("core_only") else ""}'
                f'{" selected" if t["sym"] == selected else ""}>{e(t["short"])} · {e(t["name"])}</option>'
                for t in names if t["group"] == g) + "</optgroup>"
        return out

    def stock_select(self, sel_id, tmpl, t, depth, full_only=False):
        """A jump-to-stock select that ships with just the current name; site.js fills in
        the rest from data/names.json (one cached file instead of ~380 options per page)."""
        src = self.href(depth, "data/names.json") + "?v=" + self.ver
        return (f'<select id="{sel_id}" data-nav data-tmpl="{tmpl}" data-names="{e(src)}"{" data-full-only" if full_only else ""}>'
                f'<option value="{e(t["slug"])}" selected>{e(t["short"])} · {e(t["name"])}</option></select>')

    def plays_json(self):
        """Every play by family for the jump-to-play selects on pair pages, in names.json's shape."""
        groups = [[fname, [[p["slug"], f'{play_label(p)} · {credit(p)}', 0] for p in TIMED if p["family"] == fk]]
                  for fk, fname, _ in FAMILIES if any(p["family"] == fk for p in TIMED)]
        return json.dumps({"groups": groups}, ensure_ascii=False, separators=(",", ":"))

    def names_json(self):
        """Every covered name by group for the jump-to-stock selects: [group, [[slug, label, core_only]]]."""
        names = universe()
        groups = [[g, [[t["slug"], f'{t["short"]} · {t["name"]}', 1 if t.get("core_only") else 0] for t in names if t["group"] == g]]
                  for g in GROUP_ORDER if any(t["group"] == g for t in names)]
        return json.dumps({"groups": groups}, ensure_ascii=False, separators=(",", ":"))

    # ======================================================================
    # pages
    # ======================================================================
    def build(self):
        from .markets import markets_page
        from .watchlist import watchlist_page
        markets_page(self)
        watchlist_page(self)
        from .articles import Articles
        Articles(self).build()
        from .members import members_page
        from . import picks
        members_page(self)
        from .theory import theory_page
        theory_page(self)
        from .alerts import alerts_page
        alerts_page(self)
        from .me import me_page
        me_page(self)
        from .owner import owner_page
        owner_page(self)
        state, info = picks.run(self)
        picks.picks_page(self, state, info)
        self.home()
        self.strategies_index()
        for s in PLAYS:
            self.strategy_page(s)
        self.thinkers_index()
        for th in THINKERS:
            self.thinker_page(th)
        from . import classics
        classics.build(self)
        self.stocks_index()
        for t in TICKERS:
            self.stock_page(t)
        for s in TIMED:            # warm the per-play summaries before forking
            self.strat_summary(s)
        self.render_pairs()
        from .guides import Guides
        self.guides = Guides(self)
        self.guides.build()
        from .playset import guide_page
        guide_page(self)
        from .newsevents import guide_page as news_guide
        news_guide(self)
        from .rules import rules_page
        rules_page(self, self.guides)
        from .waystoinvest import ways_to_invest_page
        ways_to_invest_page(self)
        from .automate import directory as broker_directory     # /guides/brokers/ (the automation articles are articles.py's)
        broker_directory(self)
        from .accountplan import guide_page as plan_page
        plan_page(self)
        from .agents import developers_page     # AI tools: /developers/ (agents.py; llms.txt, openapi.json and data/api.json are build_strategies.write_data)
        developers_page(self)
        self.learn.build()
        self.method_page()
        return self.pages

    # ---------------------------------------------------------------- home
    def home(self):
        """Straight to value: the slogan, step 1 (is the market about to crash?) and the
        screener (steps 2 to 4: which stocks do the plays agree on?). See screen.py."""
        from . import screen
        path, depth = "", 0
        h = lambda x: self.href(depth, x)
        n_an = n_people()
        walk = [("step-1", "Is the market about to crash?", "Nine crash gauges and the plays on the S&amp;P 500"),
                ("step-2", "Buying or selling?", "Tell the screener your play"),
                ("step-3", "Where are you looking?", "Market, sector and crash exposure"),
                ("step-4", "Which plays, and how many must agree?", f"Count all {len(TIMED)} or just the ones you trust")]
        walk_html = "".join(f'<li><a href="#{a}"><span class="step-n">{i}</span><b>{t}</b><span>{d}</span></a></li>' for i, (a, t, d) in enumerate(walk, 1))
        more = [("theory/", "Theory tester", "Test one theory on one stock", "Every play's reason to buy or not, one at a time, with the price that would change its mind."),
                ("markets/", "Market weather", "All nine crash gauges", "Each one's history back to the 1920s, and where it stood at past market tops."),
                ("guides/", "Guides", "Which predictions work?", "Every family and every play, graded against buying and holding since 2005."),
                ("alerts/", "Free email alerts", "Know when a light flips", "An email with the analysis the evening a stock you follow turns Start or Stop.")]
        from .media import WEATHER_IMG
        wx_img = WEATHER_IMG.get((self.macro or {}).get("weather"), "wx-unsettled")
        more_img = {"theory/": "theory-board", "markets/": wx_img, "guides/": "puck-row", "alerts/": "phone-alert"}
        more_html = "".join(f'<a class="card more-card" href="{h(u)}"><span class="more-img">{pic(h, more_img[u], sizes="(max-width: 700px) 100vw, (max-width: 1100px) 50vw, 280px", decorative=True)}</span>'
                            f'<span class="eyebrow">{e(k)}</span><b>{e(t)}</b><span class="muted small">{e(d)}</span></a>' for u, k, t, d in more)
        body = f"""
<section class="hero hero-v3">
  <div class="hero-art" aria-hidden="true">{pic(h, "hero-trail", sizes="100vw", cls="hero-art-img", eager=True, decorative=True)}</div>
  <div class="hero-copy">
    <p class="eyebrow">Published trading rules, run on real prices every night</p>
    <h1 class="hero-h1">Don't chase where the stock is. Chase where it's <em>going</em>.</h1>
    <p class="lede">{len(TIMED)} trading plays from {n_an} named analysts, run after every close on {len(universe())} stocks, funds and coins. Two questions, four steps:</p>
    <ol class="walk">{walk_html}</ol>
  </div>
  {screen.crash_card(self, depth)}
</section>

{screen.screener(self, depth)}

<section class="more-row" aria-label="More from Be The Puck"><div class="grid grid-4">{more_html}</div></section>
"""
        ld = {"@context": "https://schema.org", "@graph": [
            {"@type": "Organization", "@id": BASE + "#organization", "name": "Be The Puck", "url": BASE, "logo": BASE + "og-default.png"},
            {"@type": "WebSite", "@id": BASE + "#website", "name": "Be The Puck", "url": BASE, "inLanguage": "en", "publisher": {"@id": BASE + "#organization"}}]}
        extra = f'<script type="application/ld+json">{json.dumps(ld)}</script>\n'
        self.add(path, self.shell(path, "Be The Puck · Is the market about to crash? Which stocks do the plays agree on?",
                                  f"Nine crash gauges, then a screener of {len(universe())} stocks, funds and coins: pick buying or selling, where to look and how many of {len(TIMED)} published trading plays from {n_an} analysts must agree.",
                                  body, active="", extra_head=extra, scripts=("assets/plays.js", "assets/screen.js")))

    def board_html(self, depth, curated=False, top=None):
        """Stocks x play families: how many plays in each family hold each stock.
        curated=True leaves out the Nasdaq-100 and TSX names added in bulk (the home page);
        top=N keeps only the N names the most plays hold, without group headings."""
        h = lambda x: self.href(depth, x)
        names = [t for t in universe() if not (curated and t.get("bulk"))]
        if top:
            def share(t):
                k, n = self.consensus(t)
                return k / n if n else 0
            names = sorted([t for t in names if not t.get("index")], key=lambda t: (-share(t), t["short"]))[:top]
        fams = [(k, name, [p for p in TIMED if p["family"] == k]) for k, name, _ in FAMILIES]
        head = "".join(f'<th class="c" scope="col"><a href="{h("strategies/")}#fam-{k}">{e(name)}</a><span class="sym-sub">{len(ps)} plays</span></th>' for k, name, ps in fams)
        rows = ""
        groups = [None] if top else [x for x in GROUP_ORDER if any(t["group"] == x for t in names)]
        for g in groups:
            if g is not None:
                rows += f'<tr class="grp"><td class="stick">{e(g)}</td><td colspan="{len(fams) + 1}"></td></tr>'
            for t in (names if g is None else [x for x in names if x["group"] == g]):
                cells = ""
                for k, name, ps in fams:
                    kk, nn = self.consensus(t, ps)
                    cells += (f'<td class="c fam-cell" data-v="{sortv(kk / nn if nn else None)}" data-ps-fam="{k}"><a href="{h("stocks/" + t["slug"] + "/")}#fam-{k}" title="{e(name)} on {e(t["short"])}: {kk} of {nn} in">'
                              f'{fill_bar(kk, nn)}<span>{kk}/{nn}</span></a></td>')
                k_, n_ = self.consensus(t)
                rows += (f'<tr data-ps-row="{e(t["sym"])}" data-sym="{e(t["sym"])}"><td class="stick"><a class="sym" href="{h("stocks/" + t["slug"] + "/")}">{e(t["short"])}</a>'
                         f'<span class="sym-sub">{e(t["name"])}</span></td>{cells}<td class="r" data-v="{sortv(k_ / n_ if n_ else None)}" data-ps-plays>{count_in(k_, n_)}</td></tr>')
        return (f'<div class="tbl-wrap"><table class="tbl board" data-mine><thead><tr><th class="stick" scope="col">Stock</th>{head}<th class="r" scope="col">All plays</th></tr></thead>'
                f'<tbody>{rows}</tbody></table></div>')

    def thinker_card(self, th, depth):
        h = lambda x: self.href(depth, x)
        if th.get("skeptic"):
            rec = '<div class="rec"><span><b>No play</b>audits the others</span></div>'
            strat = "The skeptic"
        elif th.get("benchmark"):
            rec = '<div class="rec"><span><b>Benchmark</b>every play is graded against this</span></div>'
            strat = "Buy & Hold"
        else:
            ss = [PLAY[x] for x in th["strategies"]]
            strat = " · ".join(p["name"] for p in ss)
            sms = [self.strat_summary(p) for p in ss]
            calls = sum(m["calls"] for m in sms)
            right = sum((m["bat"] or 0) * m["calls"] for m in sms)
            n = sum(m["n"] for m in sms)
            rec = (f'<div class="rec"><span><b>{pct(right / calls if calls else None, sign=False, d=0)}</b>calls right</span>'
                   f'<span><b>{sum(m["beat_sharpe"] for m in sms)} of {sum(m["graded"] for m in sms)}</b>beat buy &amp; hold (Sharpe)</span>'
                   f'<span><b>{sum(m["in_now"] for m in sms)} of {n}</b>in now</span></div>')
        return (f'<a class="card thinker-card" href="{h("thinkers/" + th["slug"] + "/")}"><span class="strat">{e(strat)}</span>'
                f'<span class="name">{e(th["name"])}</span><span class="role">{e(th["role"])}</span>{rec}</a>')

    # ------------------------------------------------------- plays
    def strategies_index(self):
        path, depth = "strategies/", 1
        h = lambda x: self.href(depth, x)
        chips = "".join(f'<a href="#fam-{k}">{e(name)} <span class="muted">{len([p for p in TIMED if p["family"] == k])}</span></a>' for k, name, _ in FAMILIES)
        secs = ""
        for k, name, desc in FAMILIES:
            rows = ""
            for s in [p for p in TIMED if p["family"] == k]:
                sm = self.strat_summary(s)
                rows += (f'<tr><td><a class="play-nm" href="{h("strategies/" + s["slug"] + "/")}">{play_name_html(s)}</a>{flag_tag(s)}'
                         f'<span class="play-line">{e(s.get("oneline") or "")}</span><span class="sym-sub">{e(credit(s))}</span></td>'
                         f'<td class="nowrap">{BAR_WORD[s["bar"]].capitalize()}</td>'
                         f'<td class="r" data-v="{sm["in_now"]}">{sm["in_now"]} of {sm["n"]}</td><td class="r">{pct(sm["bat"], sign=False, d=0)}</td>'
                         f'<td class="r" data-v="{sm["beat_sharpe"] / sm["graded"] if sm["graded"] else ""}">{sm["beat_sharpe"]} of {sm["graded"]}</td>'
                         f'<td class="r" data-v="{sm["cut_dd"] / sm["graded"] if sm["graded"] else ""}">{sm["cut_dd"]} of {sm["graded"]}</td>'
                         f'<td class="r">{sm["switches"]:.1f}</td></tr>')
            secs += f"""<section id="fam-{k}" class="fam-sec"><div class="sec-head"><h2 class="h2 fam-h"><span class="fam-ic">{icon(k)}</span>{e(name)}</h2><p>{e(desc)}</p></div>
<div class="tbl-wrap"><table class="tbl"><thead><tr><th>Play</th><th>Checks</th><th class="r">In now</th><th class="r">Calls right</th><th class="r">Beat B&amp;H Sharpe</th><th class="r">Cut drawdown</th><th class="r">Switches / yr</th></tr></thead>
<tbody>{rows}</tbody></table></div></section>"""
        bh = PLAY["buy-and-hold"]
        body = f"""
<section class="pair-head has-art">{page_art(h, PAGE_ART["strategies/"], "60% 60%")}<p class="eyebrow">Plays</p><h1 class="h1">{len(TIMED)} plays, one scorecard</h1>
<p class="lede">Each play is written down exactly as Be The Puck tests it, run on every stock in the universe, and graded against buying and holding the same stock over the same dates. They fall into seven families.</p>
<div class="chips fam-chips">{chips}</div></section>
{secs}
<section class="card teaser"><div class="prose"><p class="eyebrow">The benchmark</p><p class="h3" style="color:var(--ink)">{e(bh['long'])}</p><p>{e(bh['short'])}</p></div>
<a class="btn" href="{h('strategies/buy-and-hold/')}">Buy and hold by stock</a></section>
<p class="muted small">Calls right: the share of closed calls where an in call was followed by a higher price, or an out call by a lower one. Trend plays often win well under half their calls and make it back on a few long trends. Switches per year is the median across stocks.</p>
"""
        self.add(path, self.shell(path, "Plays", f"All {len(TIMED)} trading plays Be The Puck tests, grouped into seven families, with who they come from and how they have scored.", body, active="strategies/"))

    def strategy_page(self, s):
        path, depth = f"strategies/{s['slug']}/", 2
        h = lambda x: self.href(depth, x)
        by = " &amp; ".join(f'<a href="{h("thinkers/" + a + "/")}">{e(THINKER[a]["name"])}</a>' for a in s["analysts"])
        rule_card = self.rule_card(s)
        if s.get("benchmark"):
            rows = ""
            for g in [x for x in GROUP_ORDER if any(t["group"] == x for t in universe())]:
                rows += f'<tr class="grp"><td colspan="5">{e(g)}</td></tr>'
                for t in [x for x in universe() if x["group"] == g]:
                    b = self.r(t["sym"], s["slug"])["stats"]["full"]["bh"] or {}
                    rows += (f'<tr data-sym="{e(t["sym"])}"><td><a class="sym" href="{h("stocks/" + t["slug"] + "/")}">{e(t["short"])}</a><span class="sym-sub">{e(t["name"])}</span></td>'
                             f'<td class="r {dir_cls(b.get("cagr"))}">{pct(b.get("cagr"))}</td><td class="r">{pct(b.get("maxdd"))}</td><td class="r">{ratio(b.get("sharpe"))}</td>'
                             f'<td class="r nowrap">{dlong(self.r(t["sym"], s["slug"])["stats"]["start"])}</td></tr>')
            body = f"""
<nav class="crumbs"><a href="{h('strategies/')}">Plays</a><span>/</span><span>{e(s['name'])}</span></nav>
<section class="pair-head"><p class="eyebrow">The benchmark</p><h1 class="h1">{e(s['long'])}</h1><div class="byline"><span>Championed by {by}</span></div><p class="lede">{e(s['short'])}</p></section>
<section><h2 class="h2">Buy and hold, stock by stock</h2>
<div class="tbl-wrap"><table class="tbl" data-mine><thead><tr><th>Stock</th><th class="r">Annual return</th><th class="r">Worst drawdown</th><th class="r">Sharpe</th><th class="r">Since</th></tr></thead><tbody>{rows}</tbody></table></div></section>
"""
            self.add(path, self.shell(path, s["long"], s["short"], body, active="strategies/"))
            return

        sm = self.strat_summary(s)
        now_rows, rec_rows = "", ""
        for g in [x for x in GROUP_ORDER if any(t["group"] == x for t in universe())]:
            now_rows += f'<tr class="grp"><td colspan="5">{e(g)}</td></tr>'
            rec_rows += f'<tr class="grp"><td colspan="6">{e(g)}</td></tr>'
            for t in [x for x in universe() if x["group"] == g]:
                x = self.r(t["sym"], s["slug"])
                nm = next_move(x, s, t)
                band = BAND_MARK if s.get("band") and x["trigger"].get("extra", {}).get("zone") == "between" else ""
                link = h(self.pair_or_stock(t, s))
                dv = abs(nm["dist"]) if nm["dist"] is not None else (nm.get("dist_days", 0) / 365 if nm.get("dist_days") is not None else None)
                lvl = nm["short"] + (f' <span class="muted">({pct(nm["dist"])})</span>' if nm["dist"] is not None else "")
                now_rows += (f'<tr data-sym="{e(t["sym"])}"><td><a class="sym" href="{link}">{e(t["short"])}</a><span class="sym-sub">{e(t["name"])}</span></td>'
                             f'<td>{pill(x["state"])}{band}</td><td class="nowrap">{dlong(x["since"])}</td>'
                             f'<td class="nowrap" data-v="{sortv(dv)}">{lvl}</td><td class="nowrap muted">{dlong(x["next_check"])}</td></tr>')
                a, b = x["stats"]["full"]["strat"] or {}, x["stats"]["full"]["bh"] or {}
                bat = x["batting"]
                rec_rows += (f'<tr data-sym="{e(t["sym"])}"><td><a class="sym" href="{link}">{e(t["short"])}</a></td>'
                             f'<td class="r nowrap" data-v="{sortv(a.get("cagr"))}">{pct(a.get("cagr"))} <span class="muted">/ {pct(b.get("cagr"))}</span></td>'
                             f'<td class="r nowrap" data-v="{sortv(a.get("maxdd"))}">{pct(a.get("maxdd"))} <span class="muted">/ {pct(b.get("maxdd"))}</span></td>'
                             f'<td class="r nowrap" data-v="{sortv(a.get("sharpe"))}">{ratio(a.get("sharpe"))} <span class="muted">/ {ratio(b.get("sharpe"))}</span></td>'
                             f'<td class="r nowrap" data-v="{sortv(bat["avg"])}">{pct(bat["avg"], sign=False, d=0)} <span class="muted">of {bat["n"]}</span></td>'
                             f'<td class="r">{x["stats"]["switches_per_year"]:.1f}</td></tr>')
        fam = FAMILY[s["family"]][0]
        body = f"""
<nav class="crumbs"><a href="{h('strategies/')}">Plays</a><span>/</span><a href="{h('strategies/')}#fam-{s['family']}">{e(fam)}</a><span>/</span><span>{e(s['name'])}</span></nav>
<section class="pair-head">
  <p class="eyebrow">{e(fam)} · {e(BAR_WORD[s['bar']])} rule{" · " + e(s['flag']) if s.get('flag') else ""}</p>
  <h1 class="h1">{e(s.get('plain') or s['long'])}</h1>
  {"" if (s.get('plain') or s['long']).lower() == s['long'].lower() else f'<p class="h1-tech">Known as {e(s["long"])}</p>'}
  <div class="byline"><span>From {by}</span>{"<span>·</span><span>" + e(s["origin"]) + "</span>" if s.get("origin") else ""}<span>·</span><a href="{h('guides/' + s['slug'] + '/')}">Guide: does it work?</a></div>
  <p class="lede">{e(s.get('oneline') or s['short'])}</p>
  {"" if not s.get('oneline') else f'<p class="muted">{e(s["short"])}</p>'}
  {classic_links(h, "play", s["slug"], "The history behind it")}
</section>
<section><div class="tiles">
  <div class="card tile"><span class="tile-label">In right now</span><span class="tile-value">{sm['in_now']} of {sm['n']}</span><span class="tile-note">As of the {dlong(self.asof)} close.</span></div>
  <div class="card tile"><span class="tile-label">Calls right</span><span class="tile-value">{pct(sm['bat'], sign=False, d=0)}</span><span class="tile-note">Across {sm['calls']:,} closed calls.</span></div>
  <div class="card tile"><span class="tile-label">Beat buy and hold (Sharpe)</span><span class="tile-value">{sm['beat_sharpe']} of {sm['graded']}</span><span class="tile-note">Cut the worst drawdown on {sm['cut_dd']} of {sm['graded']}.</span></div>
</div></section>
<section class="split">{rule_card}{self.against_card(depth)}</section>
<section class="card practice-strip"><p><b>Practise this play.</b> See if you can read its call on real charts, or drill its rule on a flashcard.</p>
<div class="chips"><a href="{h('learn/call-it/')}?play={s['slug']}">Call it: {e(s['name'])}</a><a href="{h('learn/flashcards/')}?deck=plays#{s['slug']}">Flashcard</a></div></section>
<section data-adv="What it says on every stock now, and the price that would flip each call"><div class="sec-head"><h2 class="h2">What it says now</h2><p>The close that would flip each call on its next {BAR_WORD[s['bar']]} check.</p></div>
<div class="tbl-wrap"><table class="tbl" data-mine><thead><tr><th>Stock</th><th>Call</th><th>Since</th><th data-sort-first="asc">Next move</th><th>Next check</th></tr></thead><tbody>{now_rows}</tbody></table></div></section>
<section><div class="sec-head"><h2 class="h2">The record</h2><p>Play / buy and hold over the same dates, since 2005 or the first date with enough history.</p></div>
<div class="tbl-wrap"><table class="tbl" data-mine><thead><tr><th>Stock</th><th class="r">Annual return</th><th class="r">Worst drawdown</th><th class="r">Sharpe</th><th class="r">Calls right</th><th class="r">Switches / yr</th></tr></thead><tbody>{rec_rows}</tbody></table></div></section>
"""
        self.add(path, self.shell(path, s["long"], f"{s['long']} from {credit(s)}: {s['short']} Current calls and full record on {len(universe())} stocks.", body, active="strategies/"))

    def rule_card(self, s):
        rules = "".join(f"<li>{e(x)}</li>" for x in s["rules"])
        ass = "".join(f"<p>{e(x)}</p>" for x in s["assumptions"])
        src = "".join(f'<li><a href="{e(u)}" rel="noopener">{e(t)}</a></li>' for t, u in s.get("sources") or [])
        return (f'<div class="card rule-card prose"><p class="eyebrow">How the play works</p><ol>{rules}</ol>'
                + (f'<div class="assume">{ass}</div>' if ass else "")
                + (f'<p class="small muted rule-src-h">Where the rules come from</p><ul class="small rule-src">{src}</ul>' if src else "") + "</div>")

    def against_card(self, depth):
        h = lambda x: self.href(depth, x)
        return (f'<div class="card prose"><p class="eyebrow">The case against</p><div class="against">'
                f'<p>Valeriy Zakamulin tested moving-average timing on up to 155 years of U.S. stock data and found no statistically significant edge in the second half of that record. The rules earned their keep in a few severe bear markets and lagged buy and hold for long stretches in between.</p>'
                f'<p><a href="{h("thinkers/valeriy-zakamulin/")}">Read the skeptic\'s scoreboard</a></p></div></div>')

    # ---------------------------------------------------------- analysts
    def analyst_family(self, th):
        if not th["strategies"]:
            return None
        return PLAY[th["strategies"][0]]["family"]

    def thinkers_index(self):
        path, depth = "thinkers/", 1
        h = lambda x: self.href(depth, x)
        secs = ""
        chips = ""
        for k, name, desc in FAMILIES:
            group = [th for th in THINKERS if self.analyst_family(th) == k]
            if not group:
                continue
            chips += f'<a href="#fam-{k}">{e(name)} <span class="muted">{len(group)}</span></a>'
            cards = "".join(self.thinker_card(th, depth) for th in group)
            secs += f'<section id="fam-{k}" class="fam-sec"><div class="sec-head"><h2 class="h2 fam-h"><span class="fam-ic">{icon(k)}</span>{e(name)}</h2><p>{e(desc)}</p></div><div class="grid grid-3">{cards}</div></section>'
        extra = "".join(self.thinker_card(th, depth) for th in THINKERS if th.get("benchmark") or th.get("skeptic"))
        n_an = n_people()
        body = f"""
<section class="pair-head"><p class="eyebrow">Analysts</p><h1 class="h1">The people behind the plays</h1>
<p class="lede">{n_an} traders, authors and researchers, from Richard Donchian's 1950s rules to Ben Cowen's crypto band, plus the golden cross, which has no single author. Each bio and rule was checked against their books, papers or interviews, and every play is graded the same way, whoever published it.</p>
<div class="chips fam-chips">{chips}<a href="#yardsticks">Benchmark &amp; skeptic</a><a href="{h('learn/reading-list/')}">Reading list</a></div></section>
{secs}
<section id="yardsticks" class="fam-sec"><div class="sec-head"><h2 class="h2">The yardsticks</h2><p>The benchmark every play is graded against, and the researcher who says timing rarely beats it.</p></div><div class="grid grid-3">{extra}</div></section>
"""
        self.add(path, self.shell(path, "Analysts", f"The {n_an} traders, analysts and academics behind every play Be The Puck tests, with verified bios, books and sources.", body, active="thinkers/"))

    def thinker_page(self, th):
        path, depth = f"thinkers/{th['slug']}/", 2
        h = lambda x: self.href(depth, x)
        argues = "".join(f"<li>{e(x)}</li>" for x in th["argues"])
        srcs = "".join(f'<a href="{e(u)}" rel="noopener" target="_blank">{e(lab)}</a>' for lab, u in th["sources"])
        books = "".join(f'<li><b>{e(b["title"])}</b>{" <span class=muted>(" + str(b["year"]) + ")</span>" if b.get("year") else ""}</li>' for b in th.get("books", []))
        books_card = (f'<div class="card prose"><p class="eyebrow">Books and papers</p><ul class="books">{books}</ul>'
                      f'<p class="muted small"><a href="{h("learn/reading-list/")}">The full reading list</a></p></div>') if books else ""
        extra = ""
        if th.get("skeptic"):
            rows = ""
            for s in TIMED:
                sm = self.strat_summary(s)
                rows += (f'<tr><td><a class="play-nm" href="{h("strategies/" + s["slug"] + "/")}">{play_name_html(s)}</a><span class="sym-sub">{e(credit(s))}</span></td>'
                         f'<td>{e(FAMILY[s["family"]][0])}</td>'
                         f'<td class="r" data-v="{sm["beat_cagr"] / max(1, sm["graded"])}">{sm["beat_cagr"]} of {sm["graded"]}</td>'
                         f'<td class="r" data-v="{sm["beat_sharpe"] / max(1, sm["graded"])}">{sm["beat_sharpe"]} of {sm["graded"]}</td>'
                         f'<td class="r" data-v="{sm["cut_dd"] / max(1, sm["graded"])}">{sm["cut_dd"]} of {sm["graded"]}</td></tr>')
            extra = f"""<section><div class="sec-head"><h2 class="h2">The skeptic's scoreboard</h2><p>How often each play beat simply holding the stock, over the same dates, after costs. <span class="wide-only">Click a column to sort.</span><span class="narrow-only">Sort with the menu above the list.</span></p></div>
<div class="tbl-wrap"><table class="tbl"><thead><tr><th>Play</th><th>Family</th><th class="r">Beat on return</th><th class="r">Beat on Sharpe</th><th class="r">Cut drawdown</th></tr></thead><tbody>{rows}</tbody></table></div>
<p class="muted small">A play that cuts drawdowns but loses on return is doing what Zakamulin's research predicts: paying for crash protection with years of lag.</p></section>"""
        else:
            for slug in th["strategies"]:
                s = PLAY[slug]
                if s.get("benchmark"):
                    extra += f"""<section><div class="card teaser"><div class="prose"><p class="eyebrow">The benchmark</p><p class="h2" style="color:var(--ink)">Every play on Be The Puck is graded against buy and hold.</p></div>
<a class="btn" href="{h('strategies/' + slug + '/')}">See buy and hold by stock</a></div></section>"""
                    continue
                sm = self.strat_summary(s)
                score = lambda t: ((self.r(t["sym"], slug)["stats"]["full"]["strat"] or {}).get("sharpe") or -9) - ((self.r(t["sym"], slug)["stats"]["full"]["bh"] or {}).get("sharpe") or -9)
                best = sorted(universe(), key=score, reverse=True)[:12]
                chips = "".join(f'<a href="{h(self.pair_or_stock(t, s))}">{e(t["short"])}{pill(self.r(t["sym"], slug)["state"])}</a>' for t in best)
                co = [a for a in s["analysts"] if a != th["slug"]]
                with_ = (" · with " + ", ".join(f'<a href="{h("thinkers/" + a + "/")}">{e(THINKER[a]["name"])}</a>' for a in co)) if co else ""
                extra += f"""<section><div class="sec-head"><h2 class="h2">{e(s.get('plain') or s['long'])}</h2><a class="btn" href="{h('strategies/' + slug + '/')}">Rule and full record</a></div>
<p class="muted small">{"" if (s.get('plain') or s['long']).lower() == s['long'].lower() else e(s['long']) + " · "}{e(FAMILY[s['family']][0])} · {e(BAR_WORD[s['bar']])}{with_}</p>
<p><b>{e(s.get('oneline') or '')}</b> {e(s['short'])}</p>
<div class="tiles">
<div class="card tile"><span class="tile-label">Calls right</span><span class="tile-value">{pct(sm['bat'], sign=False, d=0)}</span><span class="tile-note">{sm['calls']:,} closed calls on {sm['n']} stocks.</span></div>
<div class="card tile"><span class="tile-label">Beat buy and hold (Sharpe)</span><span class="tile-value">{sm['beat_sharpe']} of {sm['graded']}</span><span class="tile-note">On raw return: {sm['beat_cagr']} of {sm['graded']}.</span></div>
<div class="card tile"><span class="tile-label">In right now</span><span class="tile-value">{sm['in_now']} of {sm['n']}</span><span class="tile-note">As of the {dlong(self.asof)} close.</span></div>
</div>
<p class="muted small">Best risk-adjusted results against buy and hold:</p><div class="chips">{chips}<a href="{h('strategies/' + slug + '/')}">All {len(universe())} stocks →</a></div></section>"""
        body = f"""
<nav class="crumbs"><a href="{h('thinkers/')}">Analysts</a><span>/</span><span>{e(th['name'])}</span></nav>
<section class="pair-head"><p class="eyebrow">{e(th['role'])}</p><h1 class="h1">{e(th['name'])}</h1><p class="lede">{e(th['bio'])}</p>{classic_links(h, "thinker", th["slug"], "Their story in the Classics")}</section>
<section class="split"><div class="card prose"><p class="eyebrow">What they argue</p><ul>{argues}</ul></div>
<div class="card prose"><p class="eyebrow">Sources</p><div class="sources">{srcs}</div>
<p class="muted small">Summaries are Be The Puck's paraphrase of public material. Be The Puck has no affiliation with the people listed.</p></div></section>
{f'<section class="split">{books_card}</section>' if books_card else ''}
{extra}
"""
        n_plays = len([x for x in th["strategies"] if not PLAY[x].get("benchmark")])
        desc = f"{th['name']}, {th['role']}: " + (f"{n_plays} play{'s' if n_plays != 1 else ''} tested on {len(universe())} stocks, and what they say now." if n_plays else "background, sources and books.")
        self.add(path, self.shell(path, th["name"], desc, body, active="thinkers/"))

    # ------------------------------------------------------------ stocks
    def one_year(self, t):
        x = self.r(t["sym"], "buy-and-hold")
        w = x["window"]["price"]
        past = w[w.index <= x["asof"] - pd.DateOffset(years=1)]
        return (x["price"] / float(past.iloc[-1]) - 1) if len(past) else None

    def stocks_index(self):
        from .factors import default_words
        path, depth = "stocks/", 1
        h = lambda x: self.href(depth, x)
        groups = [g for g in GROUP_ORDER if any(t["group"] == g and not t.get("requested") for t in TICKERS)]
        rows = ""
        for t in TICKERS:
            if (t["sym"], "buy-and-hold") not in self.R or t.get("requested"):     # private names stay off the list
                continue
            x = self.r(t["sym"], "buy-and-hold")
            meta = self.meta.get(t["sym"]) or {}
            c = meta["ohlc"]["close"] if meta.get("ohlc") is not None else None
            day = float(c.iloc[-1] / c.iloc[-2] - 1) if c is not None and len(c) > 1 else None
            gap = float(c.iloc[-1] / c.iloc[-200:].mean() - 1) if c is not None and len(c) >= 200 else None
            y1 = self.one_year(t)
            k, n = self.consensus(t)
            ol = sv.outlook(self, t)
            rk = meta.get("risk") or {}
            lvl = rk.get("level")
            up = ol["upside"] if ol["ok"] else None
            score, sig, _ = fx_score(self, t)
            upp = f'{sv.upside_points(up):.4f}' if ol["ok"] else ""
            gslug = slugify_group(t["group"])
            ndx_attr = (' data-ndx="1"' if t.get("ndx") else "") + (' data-tsx="1"' if t.get("tsx") else "")
            rows += (f'<tr data-group="{gslug}"{ndx_attr} data-sym="{e(t["sym"])}" data-upp="{upp}" data-sig="{"" if sig is None else sig}" data-share="{k / n if n else 0:.3f}" data-q="{e((t["short"] + " " + t["sym"] + " " + t["name"]).lower())}">'
                     f'<td class="stick"><a class="sym" href="{h("stocks/" + t["slug"] + "/")}">{e(t["short"])}</a><span class="sym-sub">{e(t["name"])}</span></td>'
                     f'<td class="nowrap" data-v="{score if score is not None else ""}" data-ps-signal data-with-score>{sig_pill(sig)}{f" <b class=sig-n>{score}</b>" if score is not None else ""}</td>'
                     f'<td class="small muted grp-col adv-col">{e(t["group"])}</td>'
                     f'<td class="r mono">{money(x["price"], t["cur"])}</td>'
                     f'<td class="r {dir_cls(day)}" data-v="{sortv(day)}">{pct(day)}</td>'
                     f'<td class="r {dir_cls(y1)}" data-v="{sortv(y1)}">{pct(y1, d=0)}</td>'
                     f'<td class="r adv-col {dir_cls(gap)}" data-v="{sortv(gap)}">{pct(gap, d=0)}</td>'
                     f'<td class="adv-col" data-v="{sortv(k / n if n else None)}" data-ps-plays>{count_in(k, n)}</td>'
                     f'<td class="r adv-col {dir_cls(up) if up is not None else "muted"}" data-v="{sortv(up)}">{pct(up, d=0) if up is not None else "–"}</td>'
                     f'<td class="adv-col" data-v="{rk.get("score", "")}">' + (f'<span class="lvl lvl-{sv.LEVEL_CLASS[lvl]}">{e(lvl)}</span>' if lvl else '<span class="muted">–</span>') + '</td></tr>')
        chips = ('<button type="button" class="chip-btn" aria-pressed="true" data-group="">All</button>'
                 '<button type="button" class="chip-btn" aria-pressed="false" data-group="ndx">Nasdaq-100</button>'
                 '<button type="button" class="chip-btn" aria-pressed="false" data-group="tsx">TSX</button>') + "".join(
            f'<button type="button" class="chip-btn" aria-pressed="false" data-group="{slugify_group(g)}">{e(g)}</button>' for g in groups)
        presets = "".join(f'<button type="button" class="chip-btn" aria-pressed="false" data-sort="{k}">{e(lab)}</button>'
                          for k, lab in [("signal", "Highest signal"), ("score", "Your Buys only"), ("plays", "Most plays in"), ("upside", "Most analyst upside"),
                                         ("crash", "Most crash-exposed"), ("year", "Biggest 1-year gain")])
        n_names = len([t for t in TICKERS if (t["sym"], "buy-and-hold") in self.R and not t.get("requested")])
        body = f"""
<section class="pair-head has-art">{page_art(h, PAGE_ART["stocks/"], "50% 55%")}<p class="eyebrow">Stocks</p><h1 class="h1">Every stock, and what your signal says</h1>
<p class="lede">All {n_names} stocks, ETFs, indexes and coins Be The Puck covers, in one list. Your signal is the one call: Buy, Hold or Sell from the factors you weight. The other columns are what goes into it: how many of the {len(TIMED)} plays hold each name, analysts' targets and crash exposure. Sort by any column, filter by group, or open a name for its chart and every play.</p>
<div class="seg seg-sm st-views" role="group" aria-label="View"><button type="button" aria-pressed="true" data-view="list">Stock list</button><button type="button" aria-pressed="false" data-view="families">By play family</button></div>
{ps_bar(h, "Set your signal once: the weights and the plays you count. The list, the sorts and the family view all follow.", "st-ps")}</section>

<section class="st-list" id="list">
<div class="st-tools">
<input type="search" id="st-q" placeholder="Find a stock: NVDA, Shopify, gold…" autocomplete="off" aria-label="Find a stock">
<div class="chips st-sorts"><span class="small muted">Sort:</span>{presets}</div>
<div class="chips st-groups">{chips}</div>
</div>
<div class="tbl-wrap"><table class="tbl st-tbl" id="st-tbl" data-mine><thead><tr>
<th class="stick">Stock</th><th data-sort-first="desc">Your signal</th><th class="adv-col">Group</th><th class="r">Price</th><th class="r">Day</th><th class="r">1 year</th><th class="r adv-col">vs 200-day</th>
<th data-sort-first="desc" class="adv-col">Plays in</th><th class="r adv-col" data-sort-first="desc">Analysts' target</th>
<th data-sort-first="desc" class="adv-col">Crash exposure</th></tr></thead><tbody>{rows}</tbody></table></div>
<p class="adv-cols-note small"><button type="button" class="linkish" data-adv-cols>Show the other five columns</button>: group, vs 200-day, plays in, analysts' target and crash exposure.</p>
<p class="muted small" id="st-count"></p>
<p class="muted small">Your signal: a score from 0 to 100 from the factors you weight. The standard weights are {e(default_words())}; change them to bring in P/E, growth, debt, analysts and more. Buy at 60 or more, Sell at 40 or less, unless you move the lines; with the standard weights a Buy or Sell holds until the score crosses 50, and while a stock's market is 15% or more below its 1-year high the price factors stand down (<a href="{h('guides/your-plays/')}#your-signal">how the score works</a>). Analysts' upside (needs 3+ analysts; <a href="{h('articles/green-across-the-board/')}">how it works</a>). Crash exposure comes from the <a href="{h('articles/debt-and-crashes/')}">storm test</a>. Want your own list? <a href="{h('watchlist/')}">Use the watchlist</a>, including names Be The Puck doesn't cover yet.</p>
</section>

<section class="st-fams" id="families" hidden>
<div class="sec-head"><h2 class="h2">By play family</h2><p>How many plays in each family hold each stock. Tap a cell for every call on that stock.</p></div>
{self.board_html(depth)}
</section>"""
        self.add(path, self.shell(path, "Stocks · every stock and what your signal says",
                                  f"Every stock, ETF, index and coin Be The Puck covers with your signal (Buy, Hold or Sell from the factors you weight), how many of {len(TIMED)} plays hold it, analysts' upside and crash exposure.",
                                  body, active="stocks/", scripts=("assets/plays.js", "assets/stocks.js")))

    def stock_page(self, t):
        path, depth = f"stocks/{t['slug']}/", 2
        h = lambda x: self.href(depth, x)
        sym = t["sym"]
        bh = self.r(sym, "buy-and-hold")
        meta = self.meta.get(sym) or {}
        fund = self.fund.get(sym)
        rk = meta.get("risk")
        k, n = self.consensus(t)
        own_pages = self.headline_slugs() | {p for (x, p) in EXTRA_PAIRS if x == sym}
        tiles, rows = "", ""
        for fk, fname, _ in FAMILIES:
            ps = [p for p in TIMED if p["family"] == fk]
            kk, nn = self.consensus(t, ps)
            tiles += (f'<a class="card fam-tile" href="#fam-{fk}" data-ps-ftile="{fk}"><span class="tile-label">{icon(fk)}{e(fname)}</span>'
                      f'<span class="fam-n"><b data-k>{kk}</b> of <span data-n>{nn}</span> in</span>{fill_bar(kk, nn)}</a>')
            rows += f'<tr class="grp" id="fam-{fk}" data-ps-grp="{fk}"><td colspan="7">{icon(fk)} {e(fname)}</td></tr>'
            for s in ps:
                x = self.r(sym, s["slug"])
                bt = x["batting"]
                right_here = (f'<td class="r nowrap" data-v="{bt["avg"]:.4f}">{pct(bt["avg"], sign=False, d=0)} <span class="muted">{bt["right"]}/{bt["n"]}</span></td>'
                              if bt["n"] else '<td class="r muted" data-v="">–</td>')
                nm = next_move(x, s, t)
                since_move = x["price"] / x["since_price"] - 1 if x.get("since_price") else None
                dv = abs(nm["dist"]) if nm["dist"] is not None else (nm.get("dist_days", 0) / 365 if nm.get("dist_days") is not None else None)
                nxt = nm["short"] + (f' <span class="muted">({pct(nm["dist"])})</span>' if nm["dist"] is not None else "")
                a, b = x["stats"]["full"]["strat"] or {}, x["stats"]["full"]["bh"] or {}
                band = BAND_MARK if s.get("band") and x["trigger"].get("extra", {}).get("zone") == "between" else ""
                tip = e(s.get("oneline") or "")
                name = (f'<a class="play-nm" href="{h(self.pair_path(t, s))}" title="{tip}">{play_name_html(s)}</a>' if s["slug"] in own_pages
                        else f'<a class="play-nm" href="{h("strategies/" + s["slug"] + "/")}" title="{tip}">{play_name_html(s)}</a>')
                rows += (f'<tr id="play-{s["slug"]}" data-ps-play="{s["slug"]}" data-fam="{fk}"><td>{name}<span class="sym-sub">{e(credit(s))} · {BAR_WORD[s["bar"]]}</span></td>'
                         f'<td>{pill(x["state"])}{band}</td><td class="nowrap" data-v="{pd.Timestamp(x["since"]).strftime("%Y-%m-%d") if x["since"] is not None else ""}">{dlong(x["since"])} <span class="{dir_cls(since_move)}">{pct(since_move)}</span></td>'
                         f'<td class="nowrap" data-v="{sortv(dv)}">{nxt}</td>{right_here}<td class="r nowrap" data-v="{sortv(a.get("cagr"))}">{pct(a.get("cagr"))} <span class="muted">/ {pct(b.get("cagr"))}</span></td>'
                         f'<td class="r nowrap" data-v="{sortv(a.get("maxdd"))}">{pct(a.get("maxdd"))} <span class="muted">/ {pct(b.get("maxdd"))}</span></td></tr>')
        b = bh["stats"]["full"]["bh"] or {}
        rows += (f'<tr class="grp"><td colspan="7">Benchmark</td></tr><tr><td><a href="{h("strategies/buy-and-hold/")}"><b>Buy &amp; Hold</b></a><span class="sym-sub">John C. Bogle · benchmark</span></td>'
                 f'<td>{pill(1)}</td><td class="nowrap">{dlong(bh["stats"]["start"])}</td><td class="muted">Always in</td><td class="r muted">–</td>'
                 f'<td class="r">{pct(b.get("cagr"))}</td><td class="r">{pct(b.get("maxdd"))}</td></tr>')
        # this stock's record on every play, for the play filter (assets/playview.js): [right, calls, in/out since]
        here = []
        for p_ in TIMED:
            x_ = self.r(sym, p_["slug"])
            here.append([x_["batting"]["right"], x_["batting"]["n"], pd.Timestamp(x_["since"]).strftime("%Y-%m-%d") if x_.get("since") is not None else None])
        others = self.stock_select("jump-stock", e(h("stocks/{v}/")), t, depth)
        start_y = bh['stats']['start'].year if bh['stats']['start'] is not None else ""

        # price facts
        day_ch = None
        if meta.get("ohlc") is not None and len(meta["ohlc"]) > 1:
            cc = meta["ohlc"]["close"]
            day_ch = float(cc.iloc[-1] / cc.iloc[-2] - 1)
        y1 = self.one_year(t)
        if meta.get("ohlc") is not None and len(meta["ohlc"]):
            bench = self.prices[t["bench"]]["close"] if t.get("bench") in self.prices else None
            chart = sv.candles_block(t, meta, learn=h("learn/candlesticks/"), news=None if t.get("index") else sv.news_items(t), bench=bench, live=True)
            heat = sv.heatmap_block(self, t, meta, lambda p: h(self.pair_path(t, p)) if p["slug"] in own_pages else f"#play-{p['slug']}")
        else:
            chart = chart_block("px-" + t["slug"], price_spec(bh, PLAY["buy-and-hold"], t, with_rule=False), "", f"{e(t['short'])} over the last three years")
            heat = ""
        read = sv.read_lines(self, t, meta, fund) if meta else []
        read_html = "".join(f"<li>{e(x)}</li>" for x in read)
        lvl = rk["level"] if rk else None
        trend_tile = self.mayer_tile(t, h)
        crash_tile = (f'<a class="card tile tile-link" href="#crash"><span class="tile-label">Crash exposure</span><span class="tile-value lvl-{sv.LEVEL_CLASS[lvl]}">{e(lvl)}</span>'
                      f'<span class="tile-note">{rk["score"]} of 10 on the storm test</span></a>') if lvl else ""
        ol = sv.outlook(self, t)
        out_tile, upp = "", None
        if ol["ok"]:
            upp = sv.upside_points(ol["upside"])
            out_tile = (f'<a class="card tile tile-link" href="{h("articles/green-across-the-board/")}" data-ps-score="{e(sym)}" data-upp="{upp:.4f}"><span class="tile-label">Plays + analysts\' upside</span>'
                        f'<span class="tile-value"><span data-v>{round(ol["score"] * 100)}</span><small> / 100</small></span>{fill_bar(round(ol["score"] * 100), 100)}'
                        f'<span class="tile-note">Target <b class="{dir_cls(ol["upside"])}">{pct(ol["upside"], d=0)}</b> from {ol["n_an"]} analysts; half the score is the plays.</span></a>')
        summary = f"""<section class="sum-tiles" data-adv="Plays in, crash exposure and trend at a glance">
<div class="card tile" data-ps-tile="{e(sym)}"><span class="tile-label">Plays in</span><span class="tile-value"><span data-k>{k}</span><small> / <span data-n>{n}</span></small></span>{fill_bar(k, n)}<span class="tile-note" data-note>Every play Be The Puck tests, in {len(FAMILIES)} families.</span></div>
{crash_tile}{trend_tile}
</section>"""
        req_note = ""
        if t.get("requested"):
            req_note = (f'<p class="note-line">Added at a reader\'s request{(" on " + dlong(t["since"])) if t.get("since") else ""}. Be The Puck runs every play on it each night '
                        f'for the readers who follow it; it stays out of the site\'s lists and rankings.</p>')
        elif t.get("ndx"):
            req_note = '<p class="note-line">In the Nasdaq-100.</p>'
        elif t.get("tsx"):
            req_note = ('<p class="note-line">Listed on the Toronto Stock Exchange; prices in Canadian dollars. '
                        f'<a href="{h("stocks/?group=tsx")}">All {n_tsx()} TSX stocks</a>.</p>')
        idx_note = ""
        if t.get("index"):
            idx_note = ('<p class="note-line">An index is a scoreboard, not something you can buy directly. Investors hold it through an index fund or ETF, '
                        'which tracks it closely. The plays read the index itself.</p>')
        from .factors import card_numbers
        used, srcs = card_numbers(self, t)
        fund_html = sv.fundamentals_card(t, fund, bh["price"], learn=h("learn/valuation/"), used=used, srcs=srcs)
        crash_html = sv.crash_card(t, rk, h) if rk else ""
        deep = ""
        if fund_html or crash_html:
            deep = f'<section class="deep" id="crash" data-adv="Crash exposure and the company\'s numbers">{crash_html}{fund_html}</section>'
        exposed = self.index_exposed(t, depth) if t.get("index") else ""
        arts = self.articles_for(t, depth)
        watch_btn = (f'<button type="button" class="btn sm" data-watch-add="{e(sym)}" data-watch-href="{e(h("watchlist/"))}">+ Add to my watchlist</button>')
        if not t.get("index"):
            watch_btn = (f'<span class="read-acts">{watch_btn}<a class="btn sm" href="{e(h("theory/"))}?s={e(t["slug"])}">Test a theory on {e(t["short"])}</a></span>')
        # phones: the three things to do with a stock, docked at the bottom of the screen
        act_bar = ""
        if not t.get("index"):
            act_bar = (f'<div class="act-bar" role="region" aria-label="Actions for {e(t["short"])}">'
                       f'<button type="button" class="btn sm" data-watch-add="{e(sym)}" data-watch-href="{e(h("watchlist/"))}">+ Follow</button>'
                       f'<a class="btn sm" href="{e(h("alerts/"))}?t={e(t["slug"])}" data-signed-out>Email me</a>'
                       f'<a class="btn sm" href="{e(h("me/"))}#alerts" data-signed-in hidden>My alerts</a>'
                       f'<a class="btn sm primary" href="{e(h("theory/"))}?s={e(t["slug"])}">Test a theory</a></div>')
        from .factors import signal_card
        from .newsevents import moves_block
        here_json = json.dumps({"sym": sym, "s": t["short"], "cur": t["cur"], "b": here, "upp": None if upp is None else round(upp, 4), "tw": sv.TREND_WEIGHT,
                                "pair": h("stocks/" + t["slug"] + "/{s}/"), "keep": sorted(own_pages)}, separators=(",", ":")).replace("</", "<\\/")
        body = f"""
<nav class="crumbs"><a href="{h('stocks/')}">Stocks</a><span>/</span><span>{e(t['short'])}</span></nav>
<section class="pair-head"><p class="eyebrow">{e(t['group'])}</p><h1 class="h1">{e(t['name'])} <span class="muted">({e(t['short'])})</span></h1>
<div class="byline"><span class="mono" style="color:var(--ink);font-size:18px">{money(bh['price'], t['cur'])}</span>
<span class="{dir_cls(day_ch)}">{pct(day_ch)} on the day</span><span>·</span><span class="{dir_cls(y1)}">{pct(y1)} in a year</span><span>·</span><span>close {dlong(bh['asof'])}</span></div>
{idx_note}{req_note}</section>
{signal_card(self, t, h)}
<section class="card read-card"><div class="read-top"><p class="eyebrow">The read</p>{watch_btn}</div><ul class="read">{read_html}</ul>
<p class="muted small">{DISCLAIMER} <a href="{h('learn/')}">New to this? Start with the basics.</a></p></section>
{summary}
{self.top_plays_block(t, h)}
{chart}
{moves_block(self, t, h)}
{heat}
<section id="every-play" data-adv="Every play on {e(t['short'])}: each call, its record and the price that would flip it"><div class="sec-head"><h2 class="h2">Every play on {e(t['short'])}</h2><p data-ps-all-sub>All {len(TIMED)} plays, by family.</p></div>
<div class="fam-tiles">{tiles}</div>
<p class="muted small">Calls right: how often the play's calls on {e(t['short'])} went the right way since {GRADE_YEAR}. Record columns: play / buy and hold, annual return and worst drawdown since {start_y}. <span class="wide-only">Click a column to sort.</span><span class="narrow-only">Sort with the menu above the list.</span></p>
<div class="tbl-wrap" id="plays-tbl"><table class="tbl"><thead><tr><th>Play</th><th>Call</th><th>Since</th><th data-sort-first="asc">Next move</th><th class="r" data-sort-first="desc">Calls right</th><th class="r">Annual return</th><th class="r">Worst drawdown</th></tr></thead><tbody>{rows}</tbody></table></div></section>
<script type="application/json" id="ps-here">{here_json}</script>
{deep}
{exposed}
{arts}
<section class="jump"><label class="small muted" for="jump-stock">Another stock</label>{others}</section>
{act_bar}
"""
        self.add(path, self.shell(path, f"{t['name']} ({t['short']}) · plays, chart and crash exposure", f"What {len(TIMED)} published trading plays say about {t['name']} ({t['short']}) now, the exact levels that flip them, its candlestick chart, fundamentals and crash exposure.", body, active="stocks/", scripts=("assets/widgets.js", "assets/plays.js", "assets/playview.js")))

    def articles_for(self, t, depth):
        h = lambda x: self.href(depth, x)
        links = [(f"articles/stocks/{t['slug']}/", f"{t['short']}: the brief", "What the plays, the levels and the business say, in plain English. Rebuilt nightly.")]
        eq = [x for x in self.universe if x["group"] == t["group"] and not x.get("index") and not x["crypto"] and x["group"] not in ("Indexes & ETFs", "Sectors")]
        if len(eq) >= 3 and t in eq:
            from .articles import slugify
            links.append((f"articles/sectors/{slugify(t['group'])}/", f"{t['group']}: what the plays say", "Every covered name in the sector, side by side."))
        links.append(("articles/debt-and-crashes/", "Debt decides who survives a crash", "The storm test on every covered stock."))
        links.append(("articles/is-this-a-bubble/", "Is this a bubble?", "The gauges in October 2026, and what history says about timing."))
        from .members import member_tag
        cards = "".join(f'<a class="card art-card" href="{h(u)}"><span class="name">{e(a)}</span><span class="muted small">{e(b)}</span>{member_tag()}</a>' for u, a, b in links)
        return (f'<section><div class="sec-head"><h2 class="h2">Read more</h2><p>Reports for <a href="{h("members/")}">Be The Puck Members</a>.</p></div>'
                f'<div class="grid grid-4">{cards}</div></section>')

    def index_exposed(self, t, depth):
        """On an index page: the covered names that trade on that market, by crash exposure."""
        h = lambda x: self.href(depth, x)
        canada = t["sym"] == "^GSPTSE"
        ndx = t["sym"] == "^NDX"
        names = [x for x in universe() if not x.get("index") and not x["crypto"] and x["group"] not in ("Indexes & ETFs", "Sectors")
                 and (x.get("ndx") if ndx else x["canadian"] == canada) and self.meta.get(x["sym"], {}).get("risk")]
        if not names:
            return ""
        names.sort(key=lambda x: (-self.meta[x["sym"]]["risk"]["score"], x["short"]))
        rows = ""
        for x in names:
            rk = self.meta[x["sym"]]["risk"]
            kc, nc = self.consensus(x)
            rows += (f'<tr><td><a class="sym" href="{h("stocks/" + x["slug"] + "/")}">{e(x["short"])}</a><span class="sym-sub">{e(x["name"])}</span></td>'
                     f'<td data-v="{rk["score"]}"><span class="lvl lvl-{sv.LEVEL_CLASS[rk["level"]]}">{e(rk["level"])}</span> <span class="muted">{rk["score"]}/10</span></td>'
                     f'<td class="r" data-v="{sortv(rk.get("beta"))}">{ratio(rk.get("beta"))}</td>'
                     f'<td class="r" data-v="{sortv(rk.get("runup2y"))}">{pct(rk.get("runup2y"), d=0)}</td>'
                     f'<td data-v="{kc}">{count_in(kc, nc)}</td><td class="small muted why-col">{e("; ".join(rk.get("why") or [])[:140])}</td></tr>')
        market = "Canadian" if canada else "U.S."
        lede = (f"All {len(names)} Nasdaq-100 companies, ranked by crash exposure." if ndx else
                f"All {len(names)} Canadian stocks Be The Puck covers, ranked by crash exposure." if canada else
                f"The {market} stocks Be The Puck covers, ranked by crash exposure. Be The Puck covers a sample of names, not the full index.")
        return f"""<section><div class="sec-head"><h2 class="h2">Who would feel a crash first</h2>
<p>{lede}</p></div>
<div class="tbl-wrap"><table class="tbl"><thead><tr><th>Stock</th><th data-sort-first="desc">Exposure</th><th class="r">Beta</th><th class="r">2-yr change</th><th>Plays in</th><th>Why</th></tr></thead><tbody>{rows}</tbody></table></div></section>"""

    # -------------------------------------------------------------- pair
    def render_pairs(self, workers=None):
        """Each stock's headline-play pages (and its Theory tester data); one worker process per batch of tickers."""
        import os
        workers = workers or min(8, os.cpu_count() or 1)
        self.theory_json = {}
        if workers <= 1:
            global _SITE
            _SITE = self
            for t in TICKERS:
                self._take_pairs(_pairs_for(t["sym"]))
            return
        import multiprocessing as mp
        _SITE = self
        with mp.get_context("fork").Pool(workers) as pool:
            for part in pool.imap_unordered(_pairs_for, [t["sym"] for t in TICKERS]):
                self._take_pairs(part)

    def _take_pairs(self, part):
        """A worker's pages, less the Theory tester's per-stock data, which goes to self.theory_json."""
        for k in [k for k in part if k.startswith(THEORY_KEY)]:
            self.theory_json[k[len(THEORY_KEY):]] = part.pop(k)
        self.pages.update(part)

    def pair_page(self, t, s):
        path, depth = self.pair_path(t, s), 3
        h = lambda x: self.href(depth, x)
        x = self.r(t["sym"], s["slug"])
        nm = next_move(x, s, t)
        cur = t["cur"]
        st = x["stats"]
        since_move = x["price"] / x["since_price"] - 1 if x.get("since_price") else None
        st_word = "in" if x["state"] == 1 else ("out" if x["state"] == 0 else "undecided")
        state_line = (f"holds {t['short']}" if x["state"] == 1 else ("sits in T-bills" if x["state"] == 0 else "has no call yet"))

        level_html = ""
        if nm["level"] is not None:
            level_html = (f'<div><span class="level">{money(nm["level"], cur)}</span></div>'
                          f'<span class="level-sub">{pct(nm["dist"])} from the {dshort(x["asof"])} close of {money(x["price"], cur)}</span>')
        elif nm.get("date") is not None:
            level_html = f'<div><span class="level">{dshort(nm["date"])}</span></div><span class="level-sub">{nm.get("dist_days")} days from the {dshort(x["asof"])} close</span>'
        checks_html = ""
        if nm["checks"]:
            checks_html = '<ul class="checks">' + "".join(
                f'<li><span class="{"ok" if ok_ else "no"}">{"✓" if ok_ else "✕"}</span>{e(lab)}</li>' for lab, ok_ in nm["checks"]) + "</ul>"
        notes = "".join(f'<p class="muted small">{e(n_)}</p>' for n_ in nm["notes"])
        alert = f'<p class="alert-line">{e(nm["alert"])}</p>' if nm["alert"] else ""
        facts = ""
        if x["state"] is not None:
            facts = (f'<div class="facts"><span>{"In" if x["state"] == 1 else "Out"} since <b>{dlong(x["since"])}</b></span>'
                     f'<span>at <b>{money(x["since_price"], cur)}</b></span><span>{t["short"]} since then <b class="{dir_cls(since_move)}">{pct(since_move)}</b></span></div>')
        pn = x["window"].get("panel")
        reading = ""
        if pn:
            parts = []
            for lab, ser, _ in pn["series"]:
                v = ser.dropna()
                if len(v):
                    val = float(v.iloc[-1])
                    parts.append(f"{e(lab)} <b>{pct(val, sign=False) if pn['fmt'] == 'pct' else f'{val:,.2f}'.replace('-', '−')}</b>")
            if parts:
                reading = f'<p class="muted small reading">Latest reading: {" · ".join(parts)}</p>'
        verdict = f"""<section class="verdict">
<div class="card"><p class="eyebrow">What the play says</p>
<div class="byline">{pill(x['state'], lg=True)}<span class="big" style="color:var(--ink)">The play {state_line}.</span></div>
{facts}{checks_html}{reading}</div>
<div class="card next-card"><p class="eyebrow">Next move</p><p class="h3" style="font-size:17px;line-height:1.45">{e(nm['headline'])}</p>
{level_html}{alert}{notes}<p class="muted small">{e(nm['check'])}</p>
<p class="small"><a href="{h('theory/')}?s={e(t['slug'])}&amp;t=play:{e(s['slug'])}">See every reason, for and against, in the Theory tester</a></p></div>
</section>"""

        keys = [key_line("--s-price", t["short"])]
        for lab, _, role in x["window"]["lines"]:
            keys.append(key_line(ROLE_VAR.get(role, "--s1"), lab))
        keys += [key_wash("in", "Play in"), key_wash("out", "Play out")]
        pchart = chart_block("px", price_spec(x, s, t), "".join(keys), f"{e(t['short'])} with the play, last two years",
                             "Shading shows the play's call from the close that triggered it.")
        pspec = panel_spec(x, s, t)
        panel_html = ""
        if pspec:
            pkeys = "".join(key_line(ROLE_VAR.get(sr["role"], "--s1"), sr["name"]) for sr in pspec["series"])
            lv = ", ".join(str(v).replace("-", "−") for v in pspec.get("levels", []))
            panel_html = chart_block("ind", pspec, pkeys, e(pspec["label"]), f"Dashed line{'s' if len(pspec.get('levels', [])) > 1 else ''} at {lv}." if lv else None, small=True)
        echart = ""
        if st["start"] is not None:
            echart = chart_block("eq", equity_spec(x, s, t), key_line("--s1", s["name"]) + key_line("--s-bench", "Buy & hold"),
                                 f"Growth of {cur}10,000 since {st['start'].year}", "Log scale. After trading costs, with T-bill interest while out.")

        def cell(dct, key, fmt):
            v = (dct or {}).get(key)
            return fmt(v) if v is not None else "–"
        rows = ""
        for lab, key, fmt in [("Annual return", "cagr", pct), ("Total return", "total", lambda v: pct(v, d=0)), ("Worst drawdown", "maxdd", pct),
                              ("Volatility", "vol", lambda v: pct(v, sign=False)), ("Sharpe ratio", "sharpe", ratio)]:
            rows += (f'<tr><td>{lab}</td><td class="r">{cell(st["full"]["strat"], key, fmt)}</td><td class="r muted">{cell(st["full"]["bh"], key, fmt)}</td>'
                     f'<td class="r">{cell(st["5y"]["strat"], key, fmt)}</td><td class="r muted">{cell(st["5y"]["bh"], key, fmt)}</td></tr>')
        rows += f'<tr><td>Time invested</td><td class="r">{pct(st["invested"], sign=False, d=0)}</td><td class="r muted">100%</td><td></td><td></td></tr>'
        rows += f'<tr><td>Switches per year</td><td class="r">{st["switches_per_year"]:.1f}</td><td class="r muted">0</td><td></td><td></td></tr>'
        start_y = st["start"].year if st["start"] is not None else "–"
        stats_tbl = (f'<div class="tbl-wrap"><table class="tbl" data-nosort><thead><tr><th></th><th class="r">Play, since {start_y}</th><th class="r">Hold, since {start_y}</th>'
                     f'<th class="r">Play, 5 yrs</th><th class="r">Hold, 5 yrs</th></tr></thead><tbody>{rows}</tbody></table></div>')

        bat = x["batting"]
        shown = 12
        calls = x["calls"][-shown:][::-1]
        crow = ""
        for c in calls:
            res_ = ('<span class="muted">open</span>' if not c["closed"] else
                    ('<span class="up">✓ right</span>' if c["right"] else '<span class="down">✕ wrong</span>'))
            crow += (f'<tr><td class="nowrap">{dlong(c["date"])}</td><td>{pill(c["state"])}</td><td class="r">{money(c["price"], cur)}</td>'
                     f'<td class="nowrap" data-v="{pd.Timestamp(c["end"]).strftime("%Y-%m-%d")}">{dlong(c["end"]) if c["closed"] else "now"}</td>'
                     f'<td class="r {dir_cls(c["move"])}">{pct(c["move"])}</td><td data-v="{(1 if c["right"] else 0) if c["closed"] else ""}">{res_}</td></tr>')
        bat_line = (f'Right on <b>{bat["right"]}</b> of <b>{bat["n"]}</b> closed calls ({pct(bat["avg"], sign=False, d=0)}). '
                    f'In calls averaged {pct(bat["in_avg"])}; out calls saw {t["short"]} move {pct(bat["out_avg"])} on average.') if bat["n"] else "No closed calls yet."
        calls_sec = f"""<section><div class="sec-head"><h2 class="h2">Every call, graded</h2><p>{bat_line}</p></div>
<div class="tbl-wrap"><table class="tbl"><thead><tr><th>Called</th><th>Call</th><th class="r">Price</th><th>Until</th><th class="r">{e(t['short'])} moved</th><th>Result</th></tr></thead><tbody>{crow}</tbody></table></div>
<p class="muted small">An in call is right when the price rose before the next call; an out call is right when it fell. The latest {min(shown, len(x['calls']))} of {len(x['calls'])} calls shown.</p></section>""" if x["calls"] else ""

        by = " &amp; ".join(f'<a href="{h("thinkers/" + a + "/")}">{e(THINKER[a]["name"])}</a>' for a in s["analysts"])
        # ships with the current play only; site.js fills in the rest from data/plays.json
        play_sel = f'<option value="{e(s["slug"])}" selected>{e(play_label(s))} · {e(credit(s))}</option>'
        plays_src = h("data/plays.json") + "?v=" + self.ver
        stock_sel = self.stock_select("jump-stock", e(h("stocks/{v}/" + s["slug"] + "/")), t, depth, full_only=not s.get("core"))
        play_tmpl = e(h("stocks/" + t["slug"] + "/{v}/"))
        body = f"""
<nav class="crumbs"><a href="{h('stocks/')}">Stocks</a><span>/</span><a href="{h('stocks/' + t['slug'] + '/')}">{e(t['short'])}</a><span>/</span><span>{e(s['name'])}</span></nav>
<section class="pair-head"><p class="eyebrow">{e(FAMILY[s['family']][0])} · {e(BAR_WORD[s['bar']])} rule · {e(t['group'])}</p>
<h1 class="h1">{e(s.get('plain') or s['name'])} on {e(t['name'])}</h1>
{"" if (s.get('plain') or s['name']).lower() == s['name'].lower() else f'<p class="h1-tech">{e(s["name"])} · {e(s.get("oneline") or "")}</p>'}
<div class="byline"><span>Play from {by}</span><span>·</span><a href="{h('strategies/' + s['slug'] + '/')}">How it works</a><span>·</span><a href="{h('guides/' + s['slug'] + '/')}">Does it work?</a><span>·</span><a href="{h('learn/reading-a-page/')}">How to read this page</a>{flag_tag(s)}</div></section>
{verdict}
{pchart}
{panel_html}
{echart}
<section><div class="sec-head"><h2 class="h2">The record</h2><p>The play against buying and holding {e(t['short'])} over exactly the same dates, after costs.</p></div>{stats_tbl}</section>
{calls_sec}
<section class="split">{self.rule_card(s)}{self.against_card(depth)}</section>
<section class="jump split"><div><label class="small muted" for="jump-play">Another play on {e(t['short'])}</label><select id="jump-play" data-nav data-tmpl="{play_tmpl}" data-names="{e(plays_src)}">{play_sel}</select></div>
<div><label class="small muted" for="jump-stock">{e(s['name'])} on another stock</label>{stock_sel}</div></section>
"""
        title = f"{s['name']} on {t['short']}: the play says {st_word}"
        desc = f"{credit(s)}'s {s['long']} applied to {t['name']} ({t['short']}) since {start_y}: {st_word} since {dlong(x['since'])}. {nm['headline']}"
        self.add(path, self.shell(path, title, desc, body, active="stocks/"))

    # ------------------------------------------------------------ method
    def method_page(self):
        from .factors import FACTORS as SIG_FACTORS, BUY as SIG_BUY, SELL as SIG_SELL, default_words
        from .factorgrade import cached as fg_cached
        fg_since = (fg_cached(self).get("since") or "2011")[:4]
        path, depth = "method/", 1
        h = lambda x: self.href(depth, x)
        body = f"""
<section class="pair-head"><p class="eyebrow">Method</p><h1 class="h1">How Be The Puck makes its call and tests a play</h1>
<p class="lede">The same test for all {len(TIMED)} plays and all {len(universe())} stocks, written down so anyone can check it.</p></section>
<section class="card prose" id="signal"><span id="light"></span><p class="eyebrow">Your signal: the one call on each stock</p>
<p>Every stock gets one call, <b>Buy</b>, <b>Hold</b> or <b>Sell</b>, and the reader sets it. Each of {len(SIG_FACTORS)} factors turns into points from 0 to 100: the share of the plays you count that hold the stock, analysts' upside and rating, P/E and the other value measures, growth, margins, debt, trend, momentum and crash exposure. Company numbers score by rank among every covered company, so a P/E lower than 80% of them scores 80. Your score is the weighted average of the factors you weight, over the ones the stock has; with less than half your weight available (a fund has no P/E) there's no score. Buy at {SIG_BUY} or more, Sell at {SIG_SELL} or less, unless you move the lines.</p>
<p>The standard weights are {e(default_words())}, chosen in October 2026 because every factor in them has a tested record (below) and the last two are exit rules: a stock that keeps falling, or breaks below its 200-day average, loses its Buy. Before that they were half plays, half analysts' upside, and the targets behind upside can't be tested and look better the further a stock falls. Two rules were added on October 21, 2026 (model version 3), each graded month by month since 2006 first (<a href="{h('articles/old-vs-new-signal/')}">the tests</a>): the <b>market guard</b>, under which Off the high, Trend and 1-year momentum stand down while the stock's own market (the S&amp;P 500, or the TSX) is 15% or more below its 1-year high, so an exit rule doesn't sell a whole market at its bottom; and <b>sticky calls</b> on the standard weights with every play counted, under which a Buy holds until the score drops below 50 and a Sell until it rises above 50, which cuts the flips by about a third. The guard applies to every set of weights; the sticky rule needs the score's day-by-day history, which only the standard setup has. Change the weights, or the plays you count, from any stock page, the stock list, the screener or the watchlist, and every page follows (<a href="{h('guides/your-plays/')}#your-signal">how the score works</a>). Until October 2026 the site also showed a Start/Stop light, which read only the plays; the same reading is your signal with every weight on the plays. Each stock page also shows the closes at which its signal would turn, with the plays and company numbers held where they are. How the calls are doing: <a href="{h('articles/calls-graded/')}">this week's calls, graded</a>, rebuilt nightly. {DISCLAIMER}</p></section>
<section class="card prose" id="factor-grades"><p class="eyebrow">How the factors are graded</p>
<p>Every factor gets a record, like every play. Each month since {fg_since}, every stock got its points on each factor from numbers public at the time: prices to that close, the plays' calls to that close, and company figures from the SEC filings filed by that date (each value dated by the filing that first reported it). A factor's <b>Buys</b> are stocks it scored 60 or more; its <b>Avoids</b>, 40 or less. Each is checked against its market (the S&amp;P 500, or the TSX) over the next three months and the next year. The <b>edge</b> is how much more often the Buys beat the market than the Avoids did; it's shown beside every slider and in <a href="{h('guides/your-plays/')}#your-signal">the guide</a>. Analysts' targets and ratings, forward P/E, PEG and crash exposure have no record of past values and aren't graded. The test uses today's list of covered stocks, which flatters every factor alike.</p></section>
<section class="split">
<div class="card prose"><p class="eyebrow">Data</p><ul>
<li>Daily open, high, low, close and volume, adjusted for splits and dividends, from Yahoo Finance since January 2004. Grading starts in January 2005, or once a stock has enough history for the play.</li>
<li>Company numbers come from SEC filings (XBRL) for companies that file 10-Qs, dated by filing, and from Yahoo Finance for the rest; every one passes a quality check that holds back impossible values and corrects currency mix-ups (data/quality.json).</li>
<li>Cash earns the 13-week U.S. Treasury bill yield (^IRX). Canadian names use the same rate, which slightly flatters or penalises them.</li>
<li>Every signal uses finished bars only. Today's price is ignored until the market has closed, and weekly or monthly plays wait for the week or month to end.</li>
</ul></div>
<div class="card prose"><p class="eyebrow">Execution and costs</p><ul>
<li>A call made on a close is acted on at the next session. Plays that buy on the signal day's close, like Connors' RSI(2), are tested the same way.</li>
<li>Each switch in or out costs 0.05% for stocks and ETFs, 0.10% for crypto and 0.30% for micro caps, whose buying and selling prices are far apart.</li>
<li>No leverage, no shorting, no taxes. Every play is long or in T-bills, even where its author also sold short. Each play page lists where Be The Puck's version differs from the original.</li>
</ul></div>
</section>
<section class="split">
<div class="card prose"><p class="eyebrow">Grading</p><ul>
<li><b>Calls right:</b> an in call is right if the price was higher when the next call came; an out call is right if it was lower. Open calls are not graded.</li>
<li><b>Annual return, worst drawdown, volatility:</b> computed on the play's daily returns, including T-bill interest while out.</li>
<li><b>Sharpe ratio:</b> average return above T-bills divided by volatility, annualised.</li>
<li>Every play is compared with buying and holding the same stock over exactly the same dates.</li>
</ul></div>
<div class="card prose"><p class="eyebrow">The next move</p><ul>
<li>Be The Puck asks each play what it would say after one more bar at a range of hypothetical closes, from about 30% below the latest close to 40% above (wider for crypto, micro caps and monthly plays), then narrows each point where the call flips to a fraction of a cent.</li>
<li>For a daily play the next bar opens at today's close; its high and low are assumed to stretch only as far as the hypothetical close. Plays that use the day's high, low or volume are approximate on that point.</li>
<li>Some plays can't flip on one close, for example when a crossover needs two days or an indicator is shifted forward in time. The page says so instead of showing a level. Calendar plays show the date of their next change.</li>
<li>Daily plays check every close. Weekly plays check the Friday close (Sunday for crypto). Monthly plays check the last close of the month. Future dates use the U.S. market holiday calendar.</li>
</ul></div>
</section>
<section class="split">
<div class="card prose"><p class="eyebrow">Crash exposure</p><ul>
<li>A 10-point checklist per stock: market swings (beta over three years of weekly returns and monthly downside capture against the S&amp;P 500, or the TSX for Canadian names; up to 3 points), past crashes (its fall against its index's in the 2000–02, 2008–09, 2020 and 2022 bear markets; up to 2), debt (negative equity, debt to equity, interest cover and net debt to EBITDA; up to 3) and run-up (two-year gains of 100% or 150%; up to 2).</li>
<li>0–2 is Low, 3–4 Moderate, 5–6 High, 7 or more Very high. It describes fragility, not timing.</li>
<li>Company figures come from Yahoo Finance and are refreshed nightly; banks and insurers borrow as their business, so their debt ratios read high by design.</li>
</ul></div>
<div class="card prose"><p class="eyebrow">Market gauges</p><ul>
<li>Nine monthly series: trend (S&amp;P 500 against its 200-day average, and how many plays hold it), valuation (Shiller CAPE from multpl.com), run-up (Nasdaq-100 two-year return), concentration (equal-weight RSP against SPY over three years), volatility (VIX), the 10-year minus 3-month yield curve, the Baa corporate spread, the Sahm rule and the 10-year Treasury yield, from Yahoo Finance and FRED.</li>
<li>Each gauge is calm, watch or warning on thresholds stated on the Markets page, chosen from the research cited there. The weather word adds them up: two points per warning, one per watch, and "stormy" also needs the trend gauge to have broken.</li>
</ul></div>
</section>
<section class="card prose"><p class="eyebrow">Analysts' upside</p>
<p>One of the factors in your signal (half of it under the standard weights until October 13, 2026; none of it since, because targets have no record that can be graded). It's the gap between the price and analysts' average 12-month target (Yahoo Finance), scored in a straight line from 20% below the price (0) to 50% above it (full marks). A stock needs at least three analysts, and a target more than double the price is ignored as stale. Targets are opinions that lean optimistic, which is why you can weight them down or out.</p></section>
<section class="card prose"><p class="eyebrow">Reader-requested stocks</p>
<p>Tickers added on the watchlist or the account page that Be The Puck doesn't cover go to a queue holding only the symbol and when it was asked for. Each night, after the U.S. close, up to 25 new symbols are checked for at least 60 sessions of price history on Yahoo Finance and analysed in the next build: all {len(TIMED)} plays and your signal, like any other stock. Reader-requested names stay private: they show for the readers who follow them (their account page, watchlist and emails) and nowhere else: not in the stock list, the screener, the scoreboards or search engines. They are ranked against the site's own list without joining it, so adding one never moves another stock's score.</p></section>
<section class="card prose"><p class="eyebrow">Sources and attribution</p>
<p>Every play's origin, parameters and the analyst's bio were checked against books, journal papers, the analyst's own site or reputable references such as StockCharts ChartSchool. Where a source was missing or two sources disagreed, the play or analyst page says so. Where a rule needed a choice its author never made, such as an exit for a buy-only signal, the choice is labelled as Be The Puck's.</p></section>
<section class="card prose"><p class="eyebrow">What this is not</p>
<p>Be The Puck reports what a published rule says. It does not know your goals, taxes or other holdings. {DISCLAIMER} Past results come from a backtest on stocks that are still listed today, which flatters every play and buy and hold alike. With {len(TIMED)} plays and {len(universe())} stocks, some pairs will look excellent by luck alone. Summaries of each analyst's views are Be The Puck's paraphrase of public material, and Be The Puck has no affiliation with them.</p>
<p>Rebuilt automatically after each U.S. market close. <a href="{h('strategies/')}">See every play</a> or <a href="{h('thinkers/valeriy-zakamulin/')}">the case against timing</a>.</p></section>
"""
        self.add(path, self.shell(path, "Method", "How Be The Puck makes its one call on a stock and tests every trading play: data, execution, costs, grading and the next-move math.", body, active="method/"))

    # ------------------------------------------------------------ exports
    def signals_json(self):
        out = []
        for t in TICKERS:
            for s in PLAYS:
                x = self.r(t["sym"], s["slug"])
                nm = next_move(x, s, t)
                out.append({"sym": t["sym"], "play": s["slug"], "family": s["family"], "analysts": s["analysts"], "state": x["state"],
                            "since": x["since"].strftime("%Y-%m-%d") if x["since"] is not None else None,
                            "next": nm["short"], "level": nm["level"],
                            "next_check": x["next_check"].strftime("%Y-%m-%d"), "price": x["price"],
                            "asof": x["asof"].strftime("%Y-%m-%d")})
        return json.dumps({"asof": self.asof.strftime("%Y-%m-%d"), "signals": out}, separators=(",", ":"))

    def sitemap(self):
        urls = "".join(f"  <url><loc>{BASE}{p}</loc><lastmod>{self.asof.strftime('%Y-%m-%d')}</lastmod></url>\n"
                       for p in sorted([k for k in self.pages if not k.startswith(("locked/", "picks/", "rules/", "owner/")) and not private_path(k)] + ["desk/", "stories/the-hertz-lesson.html"]))
        return f'<?xml version="1.0" encoding="UTF-8"?>\n<urlset xmlns="http://www.sitemaps.org/schemas/sitemap/0.9">\n{urls}</urlset>\n'


_SITE = None


THEORY_KEY = "\x00theory:"


def _pairs_for(sym):
    """One ticker's stock x play pages, plus its Theory tester data while its chart windows are loaded."""
    site = _SITE
    t = TK[sym]
    before = set(site.pages)
    for s in site.headline_plays() + [PLAY[p] for (x, p) in sorted(EXTRA_PAIRS) if x == sym and PLAY[p] not in site.headline_plays()]:
        site.pair_page(t, s)
    out = {k: v for k, v in site.pages.items() if k not in before}
    if (sym, "buy-and-hold") in site.R:
        from .theory import stock_data
        out[THEORY_KEY + t["slug"]] = json.dumps(stock_data(site, t), ensure_ascii=False, separators=(",", ":"))
    return out
