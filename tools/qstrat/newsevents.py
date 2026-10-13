"""News that moves stocks: every dated event on a covered company (earnings reports,
analyst rating changes, 8-K filings, news headlines) sorted into kinds, each one
measured against the stock's market index, and each kind summed up: how often it
moved stocks the way you'd expect, by how much, and whether the move kept going.

Inputs: data/events/<slug>.json (tools/fetch_events.py: earnings and rating changes),
data/news/<slug>.json (tools/fetch_news.py: 8-K filings and headlines) and the
daily prices on the site object.

    moves_block(site, t, h)  the "What moved X lately" section of a stock page ("" when it doesn't apply)
    guide_page(site)         adds guides/news-that-moves-stocks/
    events_json(site)        each chart marker's kind and that kind's record (data/events.json)
    recent_moves(site, t), next_event(site, t), cat_stats(site)   the data behind them
    NEWS_CSS                 styles for both pages, appended to assets/site.css

How a reaction is measured (the same frame as the news markers on the chart,
assets/widgets.js): the reaction session is the first session whose 4 pm New York
close comes after the event, so news after the close or on a weekend is read on
the next session. Day-1 abnormal move = the stock's close-to-close return that
session minus its index's (S&P 500, or the S&P/TSX for Toronto listings). Five-day
= the same from the last close before the event to four sessions after the
reaction. z = the day-1 abnormal move over the standard deviation of the stock's
daily abnormal moves in the 60 sessions before (the chart uses raw daily moves
there, so its "× a normal day" can read a little lower).

Everything is built once per site and kept on it (site._nev).
"""
import datetime as dt
import html
import json
import math
import os
import re
from zoneinfo import ZoneInfo

import numpy as np
import pandas as pd

e = html.escape
ROOT = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
EVENTS_DIR = os.path.join(ROOT, "data", "events")
NEWS_DIR = os.path.join(ROOT, "data", "news")
ET = ZoneInfo("America/New_York")
GUIDE = "guides/news-that-moves-stocks/"

SD_WINDOW, SD_MIN = 60, 20      # sessions behind a "normal day"
BIG_Z = 2.0                     # a big move: twice a normal day or more
NEAR_EARN = 2                   # other news this many sessions from an earnings report is confounded by it
RECENT = 30                     # sessions looked back on a stock page
MAX_MOVES = 5
PEER_MIN = 3
STOCK_MIN = 3                   # events of a kind before a stock's own record is quoted
NON_STOCK_GROUPS = ("Sectors", "Indexes & ETFs", "Market indexes", "Crypto")
BENCH_NAME = {"^GSPC": "the S&P 500", "^GSPTSE": "the S&P/TSX"}

# ------------------------------------------------------------------ the kinds of news
# key: label, source, expected direction (+1 up, -1 down, 0 none), plural noun for sentences, what counts
SRC = {"earn": "Earnings report", "rating": "Analyst rating", "sec": "SEC filing (8-K)", "news": "News headline",
       "release": "Earnings release, read by Claude"}
EARNINGS_DIR = os.path.join(ROOT, "data", "earnings")
CATS = {
    "big-beat": ("Big beat", "earn", 1, "big beats", "Earnings per share 20% or more above analysts' average estimate going in."),
    "beat": ("Earnings beat", "earn", 1, "earnings beats", "Earnings per share 5% to 20% above analysts' average estimate going in."),
    "small-beat": ("Small beat", "earn", 1, "small beats", "Earnings per share matched the estimate or beat it by less than 5%."),
    "miss": ("Earnings miss", "earn", -1, "earnings misses", "Earnings per share below the estimate, by less than 10%."),
    "big-miss": ("Big miss", "earn", -1, "big misses", "Earnings per share 10% or more below the estimate."),
    "upgrade": ("Upgrade", "rating", 1, "upgrades", "A firm raises its rating (say, from Hold to Buy)."),
    "downgrade": ("Downgrade", "rating", -1, "downgrades", "A firm lowers its rating (say, from Buy to Hold)."),
    "init-buy": ("Initiated at Buy", "rating", 1, "new coverage at Buy", "A firm starts covering the stock at Buy, Outperform or Overweight."),
    "init-hold": ("Initiated at Hold or Sell", "rating", -1, "new coverage at Hold or Sell", "A firm starts covering the stock at Hold, Neutral, Sell or the like."),
    "pt-up": ("Price target raised", "rating", 1, "price target raises", "A firm keeps its rating and raises its 12-month price target."),
    "pt-down": ("Price target cut", "rating", -1, "price target cuts", "A firm keeps its rating and cuts its 12-month price target."),
    "leader": ("Leadership change", "sec", 0, "leadership-change filings", "8-K item 5.02: an executive or director arrives or leaves."),
    "deal": ("Deal or material agreement", "sec", 0, "deal filings", "8-K items 1.01, 1.02 and 2.01: a material agreement signed or ended, or an acquisition or sale completed."),
    "financing": ("Financing", "sec", 0, "financing filings", "8-K items 2.03 and 3.02: new debt, or shares sold privately."),
    "restructure": ("Restructuring or write-down", "sec", 0, "restructuring filings", "8-K items 2.05 and 2.06: restructuring costs or a material impairment."),
    "other-8k": ("Other material event", "sec", 0, "other 8-K filings", "8-K items 7.01, 8.01, 3.01 and 4.02: other disclosures the company deems material."),
    "r-raised": ("Outlook raised", "release", 1, "raised outlooks", "The company's earnings release raises its outlook (read from the release by Claude; tools/fetch_earnings.py)."),
    "r-kept": ("Outlook kept", "release", 0, "kept outlooks", "The earnings release repeats the outlook it gave before."),
    "r-cut": ("Outlook cut or withdrawn", "release", -1, "cut or withdrawn outlooks", "The earnings release lowers or withdraws its outlook."),
    "n-guide-up": ("Guidance raised", "news", 1, "guidance-raised headlines", "A headline says the company raised its outlook or forecast."),
    "n-guide-down": ("Guidance cut", "news", -1, "guidance-cut headlines", "A headline says the company cut or withdrew its outlook, or warned."),
    "n-beat": ("Beat, in the headlines", "news", 1, "beat headlines", "A headline says results beat or topped estimates."),
    "n-miss": ("Miss, in the headlines", "news", -1, "miss headlines", "A headline says results missed or fell short of estimates."),
    "n-buyback": ("Buyback", "news", 1, "buyback headlines", "A headline about a share buyback or repurchase plan."),
    "n-div-up": ("Dividend raised", "news", 1, "dividend-raise headlines", "A headline says the dividend was raised, or a special dividend declared."),
    "n-div-down": ("Dividend cut", "news", -1, "dividend-cut headlines", "A headline says the dividend was cut or suspended."),
    "n-offering": ("Share offering", "news", -1, "share-offering headlines", "A headline about selling new shares or convertible notes."),
    "n-legal": ("Lawsuit or investigation", "news", -1, "lawsuit and probe headlines", "A headline about a lawsuit, class action, investigation or probe."),
    "n-approval": ("Regulatory approval", "news", 1, "approval headlines", "A headline about an FDA or other regulator's approval or clearance."),
    "n-contract": ("Contract or partnership", "news", 1, "contract and partnership headlines", "A headline about a contract or order won, or a partnership."),
    "n-layoffs": ("Layoffs", "news", 0, "layoff headlines", "A headline about job cuts or layoffs."),
    "n-ma": ("Acquisition news", "news", 0, "acquisition headlines", "A headline about an acquisition, merger or takeover involving the company."),
}
ORDER = list(CATS)
EARN_KEYS = ("big-beat", "beat", "small-beat", "miss", "big-miss")
BIG_BEAT, BIG_MISS = 20.0, -10.0   # surprise % from which a beat or a miss is big
BIG_MIN = 30                       # a big row needs this many events; otherwise it folds back into beats or misses
FOLD = {"big-beat": "beat", "big-miss": "miss"}

SEC_CAT = {"5.02": "leader", "1.01": "deal", "1.02": "deal", "2.01": "deal", "2.03": "financing", "3.02": "financing",
           "2.05": "restructure", "2.06": "restructure", "7.01": "other-8k", "8.01": "other-8k", "3.01": "other-8k", "4.02": "other-8k"}
SEC_TY = {"Leadership": "leader", "M&A": "deal", "Financing": "financing", "Restructuring": "restructure"}

# headline rules, first match wins. Questions, previews and fund-holding filler are left unsorted.
_V = r"[^.;:|]{0,40}"
NEWS_RULES = [
    ("n-guide-down", rf"\b(cuts?|lowers?|lowered|slash(es|ed)?|trims?|trimmed|reduces?|reduced|withdraws?|withdrew|pulls?|pulled|suspends?)\b{_V}\b(guidance|outlook|forecasts?)\b"
                     r"|\b(guidance|outlook|forecast) (cut|lowered|slashed|trimmed)\b|\b(weak|weaker|soft|softer|disappointing|downbeat|gloomy|bleak)\b[^.]{0,15}\b(guidance|outlook|forecast)\b|\bprofit warning\b"),
    ("n-guide-up", rf"\b(raises?|raised|lifts?|lifted|boosts?|boosted|ups|upped|hikes?|hiked|increases?|increased)\b{_V}\b(guidance|outlook|forecasts?)\b"
                   r"|\b(guidance|outlook|forecast) (raised|lifted|boosted|hiked)\b|\b(strong|stronger|upbeat|bullish|rosy|better-than-expected|record)\b[^.]{0,15}\b(guidance|outlook|forecast)\b"),
    ("n-div-down", rf"\b(cuts?|slash(es|ed)?|suspends?|suspended|eliminates?|halts?|halted|reduces?|reduced)\b{_V}\bdividends?\b|\bdividend (cut|suspension)\b"),
    ("n-offering", r"\b(public offering|stock offering|share offering|equity offering|secondary (share )?offering|direct offering|at-the-market|"
                   r"offering of (common )?(stock|shares)|convertible (senior )?notes|prices? [^.]{0,30}offering|(announces|launches|proposed) [^.]{0,30}offering)\b"),
    ("n-miss", rf"\b(miss(es|ed|ing)?|falls? short|fell short|falling short|below)\b{_V}\b(estimates?|expectations|forecasts?|consensus)\b|\bworse[- ]than[- ]expected\b"),
    ("n-beat", rf"\b(beats?|beating|tops?|topped|topping|exceeds?|exceeded|exceeding|surpass(es|ed|ing)?|crush(es|ed)?|smash(es|ed)?|above)\b{_V}\b(estimates?|expectations|forecasts?|consensus)\b|\bbetter[- ]than[- ]expected\b"),
    ("n-legal", r"\b(lawsuits?|sued|sues|class action|investigation|investigates|investigating|probe[sd]?|subpoena\w*|indict\w*|antitrust|securities fraud|whistleblower)\b"),
    ("n-buyback", r"\b(buy-?backs?|share repurchases?|stock repurchases?|repurchase (program|plan|authori[sz]ation))\b"),
    ("n-div-up", rf"\b(raises?|raised|hikes?|hiked|boosts?|boosted|increases?|increased|lifts?|lifted)\b{_V}\bdividends?\b|\bdividend (hike|increase|raise)\b|\bspecial dividend\b"),
    ("n-approval", r"\b(fda|health canada|ema|european commission)\b[^.]{0,40}\b(approv\w*|clear(s|ed|ance)|authori[sz]\w*|green[- ]?light\w*|nod)\b"
                   r"|\b(approv\w*|clearance|cleared) (by|from) (the )?(fda|ema|health canada|regulators?)\b|\bfda (approval|nod|clearance)\b"),
    ("n-ma", r"\b(to acquire|acquires|acquisition|agrees? to (buy|acquire)|deal to (buy|acquire)|buyout|takeover|merger|to merge|to be acquired|bid for|tender offer)\b"),
    ("n-layoffs", r"\b(layoffs?|lay off|laying off|job cuts|cut(s|ting)? (about |some |nearly |around )?[\d,%]*\s?(jobs|staff|workforce|employees)|workforce reduction)\b"),
    ("n-contract", rf"\b(wins?|won|awarded|secures?|secured|lands?|landed|signs?|signed|inks?|inked)\b{_V}\b(contract|order|deal|award|agreement)\b"
                   r"|\b(partnership|partners with|teams up|team up|collaboration|strategic alliance|supply (deal|agreement))\b"),
]
NEWS_RULES = [(k, re.compile(rx, re.I)) for k, rx in NEWS_RULES]
SPECULATIVE = re.compile(r"\?|\b(preview|what to expect|ahead of|expected to|set to|poised|likely|to report|will|would|could|might|should|can|prediction|is it|time to|reasons? to|"
                         r"here's|here is|how to|why you|best|top \d|\d+ (stocks|reasons))\b", re.I)
FILLER = re.compile(r"\b(shares of|stake in|position in|holdings in|stock position|\d[\d,]* shares|short interest|options? (trading|activity)|unusual options|"
                    r"stock (price|chart|quote)s?|market cap &|price today|news today|live updates?)\b", re.I)
# insiders' trades and analysts' calls: not sorted from headlines (the ratings cover analysts), but still shown as context
ASIDE = re.compile(r"\b(insiders?|officer|director|ceo|cfo|price target|rating|upgrades?|downgrades?|analysts? (says?|sees?|raises?|cuts?|lifts?|lowers?)|"
                   r"valuation forecast|eps forecast|gets (weaker|stronger|lower|higher))\b", re.I)
GUIDE_BEAT = {"n-guide-up", "n-guide-down", "n-beat", "n-miss", "r-raised", "r-kept", "r-cut"}   # headlines about the report itself: not confounded by it


# ------------------------------------------------------------------ small helpers
def _R():
    from . import render
    return render


def pct(v, sign=True, d=1):
    return _R().pct(v, sign=sign, d=d)


def _share(x):
    return "–" if x is None else f"{round(x * 100)}%"


def _secs(iso):
    try:
        return int(dt.datetime.fromisoformat(iso.replace("Z", "+00:00")).timestamp())
    except (AttributeError, ValueError):
        return None


def _et(ts):
    return dt.datetime.fromtimestamp(ts, ET)


def _when(ts):
    """'Sep 30, 4:05 pm ET'."""
    d = _et(ts)
    return d.strftime("%b %-d, %-I:%M %p ET").replace("AM", "am").replace("PM", "pm")


def _day(ts64):
    return pd.Timestamp(ts64).strftime("%a %b %-d")


def is_stock(t):
    return not t.get("crypto") and not t.get("index") and t.get("group") not in NON_STOCK_GROUPS


def binom_sf(k, n):
    """P(X >= k) for X ~ Binomial(n, 1/2): the chance of k or more of n by coin flips."""
    if k <= 0:
        return 1.0
    if k > n:
        return 0.0
    if n <= 1500:
        return sum(math.comb(n, i) for i in range(k, n + 1)) / 2 ** n
    z = (k - 0.5 - n / 2) / math.sqrt(n / 4)
    return 0.5 * math.erfc(z / math.sqrt(2))


def grade_of(share, n, p):
    if share is not None and share >= 0.65 and n >= 50 and p < 0.01:
        return "High"
    if share is not None and share >= 0.57 and n >= 30 and p < 0.05:
        return "Moderate"
    return "Low"


def grade_note(st):
    if st["grade"] != "Low":
        return f"{st['grade']} predictability"
    return "Low predictability: too few events to tell" if st["n"] < 30 else "Low predictability: close to a coin flip"


# ------------------------------------------------------------------ rating words
def _tone(g):
    g = (g or "").lower()
    if any(w in g for w in ("sell", "underperform", "underweight", "reduce", "negative", "avoid")):
        return -1
    if any(w in g for w in ("buy", "outperform", "overweight", "accumulate", "positive", "top pick", "add")):
        return 1
    return 0


def _rating_cat(action, frm, to, pta, cur, prior):
    a = (action or "").lower()
    if a == "up":
        return "upgrade"
    if a == "down":
        return "downgrade"
    if a == "init":
        return "init-buy" if _tone(to) > 0 else "init-hold"
    if a in ("main", "reit", ""):
        p = (pta or "").lower()
        by_num = p in ("", "adjusts") and cur and prior
        if p.startswith("raise") or (by_num and cur > prior):
            return "pt-up"
        if p.startswith("lower") or (by_num and 0 < cur < prior):
            return "pt-down"
    return None


def news_cat(h):
    """The kind of a news headline, or None (questions, previews and fund-holding filler stay unsorted)."""
    if not h or SPECULATIVE.search(h) or FILLER.search(h) or ASIDE.search(h):
        return None
    for k, rx in NEWS_RULES:
        if rx.search(h):
            return k
    return None


def _load(path):
    try:
        with open(path) as f:
            return json.load(f)
    except (OSError, ValueError):
        return {}


# ------------------------------------------------------------------ prices
_DAY0, _DAYS = dt.date(1970, 1, 1), None


def _close_secs(index):
    """Unix seconds of 4 pm New York on each date (the TSX closes then too), from a table built once."""
    global _DAYS
    if _DAYS is None:
        n = (dt.date(2045, 1, 1) - _DAY0).days
        _DAYS = np.array([int(dt.datetime.combine(_DAY0 + dt.timedelta(days=d), dt.time(16), ET).timestamp()) for d in range(n)], dtype=np.int64)
    return _DAYS[np.asarray(index.values).astype("datetime64[D]").astype(np.int64)]


class Series:
    """A stock's closes against its index, on the stock's own sessions."""

    def __init__(self, o, bench):
        self.dates = o.index
        self.c = o["close"].to_numpy(float)
        self.o = o["open"].to_numpy(float)
        self.bc = bench["close"].reindex(o.index).ffill().to_numpy(float)
        bo = bench["open"].reindex(o.index).to_numpy(float)
        with np.errstate(divide="ignore", invalid="ignore"):
            # open to close against the index: the part of the reaction left after the opening price
            self.oc = (self.c / self.o - 1) - (self.bc / bo - 1)
        self.close_s = _close_secs(o.index)
        r = np.full(len(self.c), np.nan)
        m = np.full(len(self.c), np.nan)
        with np.errstate(divide="ignore", invalid="ignore"):
            r[1:] = self.c[1:] / self.c[:-1] - 1
            m[1:] = self.bc[1:] / self.bc[:-1] - 1
        self.raw, self.mkt = r, m
        self.ab = r - m
        # sd[i]: the normal day size over the 60 sessions up to and including i
        self.sd = pd.Series(self.ab).rolling(SD_WINDOW, min_periods=SD_MIN).std(ddof=0).to_numpy()
        self.n = len(self.c)

    def react(self, ts):
        """Index of the reaction session (first close after ts), or None before the data starts; n if still to come."""
        i = int(np.searchsorted(self.close_s, ts, side="right"))
        return None if i < 1 else i

    def measure(self, i):
        """(day-1 abnormal, 5-day abnormal, z) for reaction session i."""
        if i is None or i >= self.n:
            return None, None, None
        d1 = self.ab[i]
        if not np.isfinite(d1):
            return None, None, None
        d5 = None
        if i + 4 < self.n:
            b = i - 1
            x = (self.c[i + 4] / self.c[b]) - (self.bc[i + 4] / self.bc[b])
            d5 = float(x) if np.isfinite(x) else None
        sd = self.sd[i - 1]
        z = float(d1 / sd) if np.isfinite(sd) and sd > 0 else None
        return float(d1), d5, z

    def before(self, i):
        """The abnormal move over the five sessions before the event (last close before it back five sessions)."""
        if i is None or i - 6 < 0 or i > self.n:
            return None
        b = i - 1
        x = (self.c[b] / self.c[b - 5]) - (self.bc[b] / self.bc[b - 5])
        return float(x) if np.isfinite(x) else None


# ------------------------------------------------------------------ events
def _ev(cat, ts, i, h, src, u="", extra=None):
    return {"cat": cat, "ts": ts, "r": i, "h": h, "s": src, "u": u, "x": extra or {}, "near": False}


def build_events(t, S, items=None, ev=None, tally=None):
    """Every event on a stock, measured: earnings, ratings, 8-Ks and headlines (cat None = an unsorted headline).
    tally, if given, counts how often Yahoo's earnings session matched the 8-K's ("checked", "agree")."""
    ev = _load(os.path.join(EVENTS_DIR, t["slug"] + ".json")) if ev is None else ev
    items = (_load(os.path.join(NEWS_DIR, t["slug"] + ".json")).get("items") or []) if items is None else items
    out, earn_r = [], set()
    # 8-K item 2.02 filings: when each report became public, to check Yahoo's times against
    sec_earn = []
    for it in items:
        if it.get("k") == "sec" and ((it.get("it") or "").split(",")[0] == "2.02" or it.get("ty") == "Earnings"):
            ts = _secs(it.get("t"))
            if ts:
                sec_earn.append(ts)
                i = S.react(ts)
                if i is not None and i < S.n:
                    earn_r.add(i)
    # earnings reports. Yahoo's time agrees with the 8-K on about 99% of reports; where both exist the earlier one is
    # used (a late filing or a late calendar entry both happen), and a date-only entry (midnight UTC) takes the 8-K's
    # time or, without one, is left unscored since it can't be placed before the open or after the close.
    seen = set()
    for row in ev.get("earn") or []:
        ts = _secs(row[0])
        if ts is None:
            continue
        dated_only = row[0].endswith("T00:00:00Z")
        near = [x for x in sec_earn if abs(x - ts) < 3 * 86400]
        if near:
            sec_ts = min(near, key=lambda x: abs(x - ts))
            if tally is not None and not dated_only and row[2] is not None:
                tally["checked"] = tally.get("checked", 0) + 1
                tally["agree"] = tally.get("agree", 0) + (S.react(ts) == S.react(sec_ts))
            ts = sec_ts if dated_only else min(ts, sec_ts)
        elif dated_only:
            for j in (S.react(ts - 5 * 3600), S.react(ts + 19 * 3600)):     # the day's session, either side of the open
                if j is not None and j < S.n:
                    earn_r.add(j)
            continue
        i = S.react(ts)
        if i is None:
            continue
        if i < S.n:
            earn_r.add(i)
        est, act, sur = row[1], row[2], row[3]
        if act is None or sur is None or i in seen:
            continue
        seen.add(i)
        cat = ("big-beat" if sur >= BIG_BEAT else "beat" if sur >= 5 else "small-beat" if sur >= 0
               else "big-miss" if sur <= BIG_MISS else "miss")
        out.append(_ev(cat, ts, i, "", "earn", extra={"est": est, "act": act, "sur": sur}))
    # analyst ratings: one event per kind per session, naming every firm
    rk = {}
    for row in ev.get("ratings") or []:
        ts = _secs(row[0])
        cat = _rating_cat(*row[2:8]) if len(row) >= 8 else None
        if ts is None or cat is None:
            continue
        i = S.react(ts)
        if i is None:
            continue
        key = (cat, i)
        x = {"firm": row[1], "frm": row[3], "to": row[4], "pt": row[6], "prior": row[7]}
        if key in rk:
            rk[key]["x"]["firms"].append(x)
            rk[key]["ts"] = min(rk[key]["ts"], ts)
        else:
            rk[key] = _ev(cat, ts, i, "", "rating", extra={"firms": [x]})
    out += list(rk.values())
    # 8-K filings and headlines
    sk, nk, uk = {}, {}, set()
    for it in items:
        ts = _secs(it.get("t"))
        if ts is None:
            continue
        i = S.react(ts)
        if i is None:
            continue
        if it.get("k") == "sec":
            codes = (it.get("it") or "").split(",")
            if codes[0] == "2.02" or it.get("ty") == "Earnings":
                continue
            cat = SEC_CAT.get(codes[0]) or SEC_TY.get(it.get("ty"), "other-8k")
            if (cat, i) not in sk:
                sk[(cat, i)] = _ev(cat, ts, i, it.get("h", ""), "sec", it.get("u", ""), {"src": it.get("s", "")})
            continue
        h = it.get("h", "")
        cat = news_cat(h)
        if cat:
            if (cat, i) in nk:
                nk[(cat, i)]["x"]["more"] += 1
                continue
            nk[(cat, i)] = _ev(cat, ts, i, h, "news", it.get("u", ""), {"src": it.get("s", ""), "more": 0})
        else:
            key = (re.sub(r"[^a-z0-9]+", " ", h.lower()).strip()[:60], i)
            if key in uk:
                continue
            uk.add(key)
            out.append(_ev(None, ts, i, h, "news", it.get("u", ""), {"src": it.get("s", "")}))
    out += list(sk.values()) + list(nk.values())
    # what the earnings release itself said about the outlook (tools/fetch_earnings.py)
    rel = _load(os.path.join(EARNINGS_DIR, t["slug"] + ".json"))
    for acc, r in (rel or {}).items():
        cat = {"raised": "r-raised", "kept": "r-kept", "cut": "r-cut", "withdrawn": "r-cut"}.get(r.get("dir"))
        ts = _secs(r.get("at") or "") or _secs((r.get("filed") or "") + "T21:00:00Z")
        if not cat or ts is None:
            continue
        i = S.react(ts)
        if i is not None:
            out.append(_ev(cat, ts, i, r.get("headline", ""), "release", r.get("url", ""), {"period": r.get("period", ""), "dir": r.get("dir")}))
    for x in out:
        x["d1"], x["d5"], x["z"] = S.measure(x["r"])
        x["pre"] = S.before(x["r"])
        oc = S.oc[x["r"]] if x["d1"] is not None else np.nan
        x["oc"] = float(oc) if np.isfinite(oc) else None
        if x["cat"] and x["cat"] not in EARN_KEYS and x["cat"] not in GUIDE_BEAT:
            x["near"] = any(abs(x["r"] - j) <= NEAR_EARN for j in earn_r)
    out.sort(key=lambda x: x["ts"])
    return out


# ------------------------------------------------------------------ the state kept on the site
class State:
    def __init__(self, site):
        self.site = site
        self.series, self.events = {}, {}
        self.grp = {}
        self.cats = None
        self.folded = set()
        self.news_start = {}
        self.tally, self.tallied = {}, set()

    def relabel(self, evs):
        for x in evs:
            if x["cat"] in self.folded:
                x["cat"] = FOLD[x["cat"]]
        return evs

    def S(self, t):
        sym = t["sym"]
        if sym not in self.series:
            o = (self.site.prices or {}).get(sym)
            b = (self.site.prices or {}).get(t.get("bench"))
            self.series[sym] = Series(o, b) if (o is not None and b is not None and len(o) > SD_MIN + 2) else None
        return self.series[sym]

    def E(self, t):
        sym = t["sym"]
        if sym not in self.events:
            S = self.S(t)
            items = _load(os.path.join(NEWS_DIR, t["slug"] + ".json")).get("items") or []
            ev = _load(os.path.join(EVENTS_DIR, t["slug"] + ".json"))
            self.events[sym] = self.relabel(build_events(t, S, items, ev, self.tally if sym not in self.tallied else None)) if S is not None else []
            self.tallied.add(sym)
            self.news_start[sym] = min((_secs(it.get("t")) or 2 ** 40 for it in items if it.get("k") == "news"), default=None)
        return self.events[sym]


def _state(site):
    st = site.__dict__.get("_nev")
    if st is None:
        st = site.__dict__["_nev"] = State(site)
    return st


def _stats(evs, d):
    xs = [x for x in evs if x["d1"] is not None]
    n = len(xs)
    if not n:
        return None
    ups = sum(1 for x in xs if x["d1"] > 0)
    downs = sum(1 for x in xs if x["d1"] < 0)
    if d > 0:
        k, way = ups, 1
    elif d < 0:
        k, way = downs, -1
    else:
        way = 1 if ups >= downs else -1
        k = max(ups, downs)
    p = binom_sf(k, n)
    if d == 0:
        p = min(1.0, 2 * p)            # no direction was expected, so either way counts
    d1 = np.array([x["d1"] for x in xs])
    d5 = np.array([x["d5"] for x in xs if x["d5"] is not None])
    zz = np.array([abs(x["z"]) for x in xs if x["z"] is not None])
    pre = np.array([x["pre"] for x in xs if x.get("pre") is not None])
    oc = np.array([x["oc"] for x in xs if x.get("oc") is not None])
    oc_k = int((oc * way > 0).sum()) if len(oc) else 0
    share = k / n
    return {"n": n, "k": k, "way": way, "share": share, "p": p, "stocks": len({x.get("sym") for x in xs}),
            "med": float(np.median(d1)), "mean": float(d1.mean()), "mean5": float(d5.mean()) if len(d5) else None,
            "med5": float(np.median(d5)) if len(d5) else None, "big": float((zz >= BIG_Z).mean()) if len(zz) else None,
            "absmed": float(np.median(np.abs(d1))), "pre": float(pre.mean()) if len(pre) else None,
            "oc_share": oc_k / len(oc) if len(oc) else None, "oc_med": float(np.median(oc)) if len(oc) else None, "oc_n": len(oc),
            "grade": grade_of(share, n, p)}


def cat_stats(site):
    """Every kind's record across the curated universe (not reader-requested tickers, so the numbers don't shift
    as readers add names): {'cats': {kind: stats}, 'raw': {kind: count before setting aside news near earnings},
    'stock': {(sym, kind): stats}, 'base': share of ordinary sessions that are big moves, 'all_beat' / 'all_miss':
    beats of 5%+ and misses of any size, 'timing': Yahoo vs 8-K session check, 'folded', 'beat_rate', 'n_reports',
    'n_events', 'n_stocks', 'earn_years'}."""
    st = _state(site)
    if st.cats is not None:
        return st.cats
    R = _R()
    by, raw, stock = {k: [] for k in CATS}, {k: 0 for k in CATS}, {}
    big_n = big_k = 0
    stocks = 0
    for t in R.universe():
        if not is_stock(t):
            continue
        S = st.S(t)
        if S is None:
            continue
        evs = st.E(t)
        if any(x["cat"] for x in evs):
            stocks += 1
        for x in evs:
            if not x["cat"] or x["d1"] is None:
                continue
            x["sym"] = t["sym"]
            raw[x["cat"]] += 1
            if x["near"]:
                continue
            by[x["cat"]].append(x)
        # the baseline: how often an ordinary session is a big move (last three years)
        lo = max(1, S.n - 756)
        z = S.ab[lo:] / S.sd[lo - 1:-1]
        z = np.abs(z[np.isfinite(z)])
        big_n += len(z)
        big_k += int((z >= BIG_Z).sum())
    # big beats and big misses get their own rows only when there are enough of them
    for big, small in FOLD.items():
        if len(by[big]) < BIG_MIN:
            by[small] += by.pop(big)
            raw[small] += raw.pop(big)
            st.folded.add(big)
    for evs in st.events.values():
        st.relabel(evs)
    cats = {}
    for k, evs in by.items():
        s = _stats(evs, CATS[k][2])
        if s:
            cats[k] = s
            per = {}
            for x in evs:
                per.setdefault(x["sym"], []).append(x)
            for sym, xs in per.items():
                if len(xs) >= STOCK_MIN:
                    stock[(sym, k)] = _stats(xs, CATS[k][2])
    allm = by["miss"] + by.get("big-miss", [])
    all_miss = _stats(allm, -1) if allm else None
    allb = by["beat"] + by.get("big-beat", [])
    all_beat = _stats(allb, 1) if allb else None
    n_rep = sum(len(by.get(k, [])) for k in EARN_KEYS)
    n_beat = sum(len(by.get(k, [])) for k in ("big-beat", "beat", "small-beat"))
    st.cats = {"cats": cats, "raw": raw, "stock": stock, "base": big_k / big_n if big_n else None, "folded": set(st.folded),
               "all_miss": all_miss, "all_beat": all_beat, "timing": dict(st.tally),
               "earn_years": sorted(dt.datetime.fromtimestamp(x["ts"], ET).year for k in EARN_KEYS for x in by.get(k, [])), "beat_rate": n_beat / n_rep if n_rep else None, "n_reports": n_rep,
               "n_events": sum(c["n"] for c in cats.values()), "n_stocks": stocks}
    return st.cats


def _stock_stats(site, sym, cat):
    """This stock's own record for a kind, including any requested ticker outside the curated stats."""
    C = cat_stats(site)
    if (sym, cat) in C["stock"]:
        return C["stock"][(sym, cat)]
    st = _state(site)
    t = _R().TK.get(sym)
    if t is None:
        return None
    xs = [x for x in st.E(t) if x["cat"] == cat and not x["near"] and x["d1"] is not None]
    return _stats(xs, CATS[cat][2]) if len(xs) >= STOCK_MIN else None


# ------------------------------------------------------------------ a stock's recent moves
def _peer_move(site, t, date):
    """(average raw move of the other covered stocks in its group that session, how many), or (None, 0)."""
    st = _state(site)
    g = t.get("group")
    if g not in st.grp:
        R = _R()
        cols = {}
        for x in R.universe():
            if x["group"] == g and is_stock(x) and x["sym"] in (site.prices or {}):
                cols[x["sym"]] = site.prices[x["sym"]]["close"].iloc[-(RECENT + 5):]
        st.grp[g] = pd.DataFrame(cols).pct_change(fill_method=None) if cols else None
    df = st.grp[g]
    if df is None or date not in df.index:
        return None, 0
    row = df.loc[date].drop(labels=[t["sym"]], errors="ignore").dropna()
    return (float(row.mean()), len(row)) if len(row) >= PEER_MIN else (None, len(row))


def recent_moves(site, t):
    """The stock's biggest moves against its index in the last 30 sessions, newest first, each with the events
    read on that session and their kinds' records."""
    if not is_stock(t):
        return []
    st = _state(site)
    S = st.S(t)
    if S is None or S.n < SD_MIN + 3:
        return []
    evs = st.E(t)
    C = cat_stats(site)
    lo = max(SD_MIN + 1, S.n - RECENT)
    rows = []
    for i in range(lo, S.n):
        a, sd = S.ab[i], S.sd[i - 1]
        if np.isfinite(a) and np.isfinite(sd) and sd > 0:
            rows.append((i, float(a), float(a / sd)))
    big = [r for r in rows if abs(r[2]) >= BIG_Z]
    if not big:
        big = sorted(rows, key=lambda r: -abs(r[2]))[:3]
    big = sorted(sorted(big, key=lambda r: -abs(r[2]))[:MAX_MOVES], key=lambda r: -r[0])
    by_r = {}
    for x in evs:
        by_r.setdefault(x["r"], []).append(x)
    out = []
    for i, a, z in big:
        date = S.dates[i]
        found = [dict(x, late=False) for x in by_r.get(i, [])]
        # write-ups published that evening, after the close, are read on the next session but are about this one
        found += [dict(x, late=True) for x in by_r.get(i + 1, []) if x["s"] == "news" and _et(x["ts"]).date() == date.date()]
        # unsorted headlines only when they read as news (no questions, previews or holding filler), three at most
        junk = [x for x in found if x["cat"] is None and (SPECULATIVE.search(x["h"]) or FILLER.search(x["h"]))]
        found = [x for x in found if not any(x is j for j in junk)]
        plain = [x for x in found if x["cat"] is None][3:]
        found = [x for x in found if not any(x is j for j in plain)]
        rank = {"earn": 0, "rating": 1, "sec": 2, "news": 3}
        found.sort(key=lambda x: (x["late"], x["cat"] is None, rank[x["s"]], -x["ts"]))
        for x in found:
            x["move"] = a
            x["stats"] = C["cats"].get(x["cat"]) if x["cat"] else None
            x["mine"] = _stock_stats(site, t["sym"], x["cat"]) if x["cat"] else None
        peer, n_peer = (None, 0) if found else _peer_move(site, t, date)
        ns = st.news_start.get(t["sym"])
        out.append({"i": i, "date": date, "raw": float(S.raw[i]), "mkt": float(S.mkt[i]), "ab": a, "z": z,
                    "d5": S.measure(i)[1], "events": found, "peer": peer, "n_peer": n_peer, "junk": len(junk),
                    "before_news": ns if ns and ns > int(S.close_s[i]) else None})
    return out


def next_event(site, t):
    """The next scheduled earnings report and how reports have moved this stock and all stocks, or None."""
    if not is_stock(t):
        return None
    st = _state(site)
    S = st.S(t)
    if S is None:
        return None
    ev = _load(os.path.join(EVENTS_DIR, t["slug"] + ".json"))
    last_close = int(S.close_s[-1])
    fut = sorted((_secs(r[0]), r[1], r[0].endswith("T00:00:00Z")) for r in ev.get("earn") or []
                 if r[2] is None and _secs(r[0]) and _secs(r[0]) > last_close)
    if not fut:
        return None
    ts, est, dated_only = fut[0]
    C = cat_stats(site)
    mine = [x for x in st.E(t) if x["cat"] in EARN_KEYS and x["d1"] is not None]
    recent = mine[-12:]
    return {"ts": ts, "est": est, "n": len(mine), "dated_only": dated_only,
            "absmed": float(np.median([abs(x["d1"]) for x in recent])) if recent else None, "n_recent": len(recent),
            "ups": sum(1 for x in recent if x["d1"] > 0),
            "beat": _either(site, t, ("beat", "big-beat"), 1), "miss": _either(site, t, ("miss", "big-miss"), -1),
            "all_beat": C.get("all_beat"), "all_miss": C.get("all_miss"), "all_small": C["cats"].get("small-beat")}


def _either(site, t, cats, d):
    """This stock's record after beats of 5% or more, or after misses of any size."""
    xs = [x for x in _state(site).E(t) if x["cat"] in cats and x["d1"] is not None]
    return _stats(xs, d) if len(xs) >= STOCK_MIN else None


# ------------------------------------------------------------------ HTML
def _arrow(d):
    return {1: "▲", -1: "▼", 0: "◆"}[d]


def cat_badge(cat):
    lab, d = CATS[cat][0], CATS[cat][2]
    tip = {1: "Expected to lift the stock", -1: "Expected to weigh on the stock", 0: "No expected direction"}[d]
    return f'<span class="nev-cat d{d + 1}" title="{e(tip)}"><i aria-hidden="true">{_arrow(d)}</i>{e(lab)}</span>'


def grade_pill(st):
    cls = {"High": "hi", "Moderate": "mid", "Low": "lo"}[st["grade"]]
    word = {"High": "High", "Moderate": "Moderate", "Low": "Low"}[st["grade"]]
    return f'<span class="nev-grade {cls}" title="{e(grade_note(st))}">{word} predictability</span>'


def _verb(st, d=None):
    return "did better than" if st["way"] > 0 else "did worse than"


def stat_sentence(cat, st):
    """'After earnings beats, stocks did better than their index at the first close after the news 61% of the time (2,191 of 3,587 on 322 stocks; median move +1.1%).'"""
    lab, src, d, noun, _ = CATS[cat]
    s = (f"After {noun}, stocks {_verb(st)} their index at the first close after the news {_share(st['share'])} of the time "
         f"({st['k']:,} of {st['n']:,} on {st['stocks']:,} stocks; median move {pct(st['med'])}).")
    if d == 0:
        s += " No direction was expected."
    return s


def _mine_sentence(short, cat, st):
    lab, src, d, noun, _ = CATS[cat]
    word = "ahead of" if st["way"] > 0 else "behind"
    return f"{short} after {noun}: {word} its index at the first close after the news {st['k']} of {st['n']} times (median {pct(st['med'])})."


def _event_line(x, t):
    """What happened, in a sentence, with a link when there is one."""
    cat, short = x["cat"], t["short"]
    usd = t.get("cur") == "$"

    def px(v):
        if not v:
            return ""
        return (f"${v:,.0f}" if v >= 100 else f"${v:,.2f}") if usd else (f"{v:,.0f}" if v >= 100 else f"{v:,.2f}")
    if x["s"] == "earn":
        xx = x["x"]
        sur = xx["sur"]
        how = f"a {abs(sur):.1f}% {'beat' if sur > 0 else 'miss'}" if sur != 0 else "exactly in line"
        est = f"{xx['est']:,.2f}" if xx["est"] is not None else "–"
        return f"{e(short)} reported earnings per share of {xx['act']:,.2f} against {est} expected: {how}."
    if x["s"] == "rating":
        fs = x["x"]["firms"]
        names = [f["firm"] for f in fs if f["firm"]]
        if len(fs) == 1:
            f = fs[0]
            tgt = f" Target {px(f['pt'])}" + (f", from {px(f['prior'])}." if f["prior"] else ".") if f["pt"] else ""
            if cat == "upgrade":
                return f"{e(f['firm'])} upgraded it to {e(f['to'])}" + (f" from {e(f['frm'])}" if f["frm"] else "") + "." + tgt
            if cat == "downgrade":
                return f"{e(f['firm'])} downgraded it to {e(f['to'])}" + (f" from {e(f['frm'])}" if f["frm"] else "") + "." + tgt
            if cat in ("init-buy", "init-hold"):
                return f"{e(f['firm'])} started coverage at {e(f['to'])}." + tgt
            verb = "raised" if cat == "pt-up" else "cut"
            return f"{e(f['firm'])} {verb} its price target to {px(f['pt'])}" + (f" from {px(f['prior'])}" if f["prior"] else "") + (f", keeping {e(f['to'])}." if f["to"] else ".")
        lst = ", ".join(e(n) for n in names[:4]) + (f" and {len(names) - 4} more" if len(names) > 4 else "")
        verb = {"upgrade": "upgraded it", "downgrade": "downgraded it", "init-buy": "started coverage at Buy or better",
                "init-hold": "started coverage at Hold or below", "pt-up": "raised their price targets", "pt-down": "cut their price targets"}[cat]
        return f"{len(fs)} firms {verb}: {lst}."
    h = e(x["h"])
    link = f'<a href="{e(x["u"])}" rel="noopener nofollow" target="_blank">{h}</a>' if x["u"] else h
    more = x["x"].get("more") or 0
    return link + (f' <span class="muted">(+{more} similar)</span>' if more else "")


def _ev_li(x, t, bench):
    cat = x["cat"]
    when = _when(x["ts"])
    src = (x["x"].get("src") or "News") if x["s"] == "news" else SRC[x["s"]]
    top = (cat_badge(cat) if cat else '<span class="nev-cat none">Headline</span>') + f'<span class="nev-src">{e(src)} · {e(when)}</span>'
    if x.get("late"):
        top += '<span class="nev-src">after that close</span>'
    body = f'<p class="nev-h">{_event_line(x, t)}</p>'
    st, mine = x.get("stats"), x.get("mine")
    if cat and x.get("near"):
        body += '<p class="nev-stat">Came within two sessions of an earnings report, so the report likely drove the move. Kinds of news are scored without these.</p>'
    elif cat and st:
        early = ' <span class="tag">Early read</span>' if CATS[cat][1] == "news" else ""
        d = CATS[cat][2]
        other = (" This time the stock went the other way." if d and x.get("move") is not None and x["move"] * d < 0 and not x.get("late") else "")
        body += f'<p class="nev-stat">{e(stat_sentence(cat, st) + other)} {grade_pill(st)}{early}</p>'
        if mine:
            body += f'<p class="nev-stat mine">{e(_mine_sentence(t["short"], cat, mine))}</p>'
    return f'<li class="nev-ev"><div class="nev-ev-top">{top}</div>{body}</li>'


def zx(z):
    """'2.3×', rounded down so a 1.96 never reads as twice a normal day."""
    return f"{math.floor(abs(z) * 10) / 10:.1f}×"


def _move_card(m, t, bench):
    cls = "up" if m["ab"] > 0 else "down"
    head = (f'<header class="nev-mh"><span class="nev-day">{_day(m["date"])}</span>'
            f'<span class="nev-mv"><b class="{cls}">{pct(m["ab"])}</b> against {e(bench)}</span>'
            f'<span class="nev-z">{zx(m["z"])} a normal day</span></header>'
            f'<p class="nev-sub">{e(t["short"])} {pct(m["raw"])}, {e(bench)} {pct(m["mkt"])} that session'
            + (f'; {pct(m["d5"])} against {e(bench)} over five sessions.' if m["d5"] is not None else ".") + "</p>")
    shown = m["events"][:5]
    if shown:
        lis = "".join(_ev_li(x, t, bench) for x in shown)
        more = len(m["events"]) - len(shown)
        tail = f'<p class="small muted">{more} more item{"s" if more != 1 else ""} from that day {"is" if more == 1 else "are"} on the chart\'s news markers.</p>' if more > 0 else ""
        return f'<article class="card nev-move">{head}<ul class="nev-evs">{lis}</ul>{tail}</article>'
    short = t["short"]
    if m["peer"] is not None:
        same = (m["peer"] > 0) == (m["raw"] > 0) and abs(m["peer"]) >= 0.5 * abs(m["raw"])
        note = (f"The {m['n_peer']} other {t['group']} stocks Be The Puck covers moved {pct(m['peer'])} on average"
                + (": much of the move was shared with its group." if same else ", so most of the move was its own."))
    else:
        note = ""
    gap = ""
    if m["before_news"]:
        gap = f" Be The Puck's headline archive for {short} starts {dt.datetime.fromtimestamp(m['before_news'], ET).strftime('%b %-d')}, so news stories from that day aren't in it."
    elif m["junk"]:
        gap = " Headlines that day were commentary or previews rather than news."
    txt = (f"No earnings report, rating change, 8-K filing or news story on {short} was found for this session.{gap} "
           f"{bench[0].upper() + bench[1:]} moved {pct(m['mkt'])}. {note}").strip()
    return f'<article class="card nev-move">{head}<p class="nev-none">{e(txt)}</p></article>'


def _next_card(nx, t, bench):
    if nx["dated_only"]:          # a date with no time: midnight UTC on the report date
        d = dt.datetime.fromtimestamp(nx["ts"], dt.timezone.utc)
        timing = ""
    else:
        d = _et(nx["ts"])
        hr = d.hour + d.minute / 60
        timing = " after the close" if hr >= 16 else " before the open" if hr < 9.5 else ""
    when = d.strftime("%a %b %-d, %Y")
    lines = []
    if nx["absmed"] is not None and nx["n_recent"] >= 4:
        lines.append(f"Over its last {nx['n_recent']} reports, {t['short']}'s typical move against {bench} at the first close after the report was "
                     f"±{nx['absmed'] * 100:.1f}% (median size, either way); it finished ahead of the index {nx['ups']} times.")
    for key, noun in (("beat", "beats of 5% or more"), ("miss", "misses of any size")):
        s = nx[key]
        if s:
            word = "ahead of" if s["way"] > 0 else "behind"
            lines.append(f"{t['short']} after {noun}: {word} its index at the first close after the report {s['k']} of {s['n']} times (median {pct(s['med'])}).")
    ab = nx["all_beat"]
    am = nx["all_miss"]
    if ab and am:
        lines.append(f"Across all covered stocks, beats of 5% or more were followed by a gain against the index {_share(ab['share'])} of the time "
                     f"and misses by a drop {_share(am['share'])} of the time.")
    lis = "".join(f"<li>{e(x)}</li>" for x in lines)
    est = f" Analysts expect earnings per share of {nx['est']:,.2f}." if nx["est"] is not None else ""
    return (f'<aside class="card nev-next"><p class="eyebrow">Next earnings report</p><p class="nev-next-d">{e(when)}<span>{e(timing)}</span></p>'
            f'<p class="small muted">From Yahoo Finance\'s calendar; dates can move.{e(est)}</p>'
            + (f'<ul class="nev-next-l">{lis}</ul>' if lis else "") +
            '<p class="small muted">Whether a report beats is only known once it is out, so these say how the stock has reacted, not which way it will go.</p></aside>')


def moves_block(site, t, h):
    """The stock-page section 'What moved {short} lately'. Empty for indexes, funds and coins."""
    if not is_stock(t):
        return ""
    moves = recent_moves(site, t)
    if not moves:
        return ""
    bench = BENCH_NAME.get(t.get("bench"), "its index")
    nx = next_event(site, t)
    cards = "".join(_move_card(m, t, bench) for m in moves)
    n_big = sum(1 for m in moves if abs(m["z"]) >= BIG_Z)
    sub = (f"Its {'biggest move' if n_big == 1 else str(n_big) + ' biggest moves'} against {e(bench)} in the last {RECENT} sessions"
           if n_big else f"No session in the last {RECENT} moved it twice a normal day against {e(bench)}; these were its largest")
    side = _next_card(nx, t, bench) if nx else ""
    return (f'<section class="nev" id="what-moved" aria-labelledby="nev-h"><div class="sec-head"><h2 class="h2" id="nev-h">What moved {e(t["short"])} lately</h2>'
            f'<p>{sub}, the news read on each, and how reliably that kind of news has moved stocks before. <a href="{h(GUIDE)}">How it\'s measured</a></p></div>'
            f'<div class="nev-grid{" has-next" if side else ""}"><div class="nev-moves">{cards}</div>{side}</div></section>')


# ------------------------------------------------------------------ the guide
def _row(k, s, C):
    lab, src, d, noun, what = CATS[k]
    what = _what(k, C)
    share_lab = _share(s["share"]) + ("" if d else (" up" if s["way"] > 0 else " down"))
    early = ' <span class="tag">Early read</span>' if src == "news" else ""
    gcls = {"High": "hi", "Moderate": "mid", "Low": "lo"}[s["grade"]]
    why = "" if s["grade"] != "Low" else ('<span class="nev-why">too few events</span>' if s["n"] < 30 else '<span class="nev-why">close to a coin flip</span>')
    med_cls = "up" if s["med"] > 0 else "down" if s["med"] < 0 else ""
    return (f'<tr><td>{cat_badge(k)}{early}<span class="sym-sub">{e(SRC[src])}. {e(what)}</span></td>'
            f'<td class="r" data-v="{s["n"]}">{s["n"]:,} <span class="muted">/ {s["stocks"]}</span></td>'
            f'<td class="r" data-v="{s["share"]:.4f}"><b>{share_lab}</b></td>'
            f'<td class="r {med_cls}" data-v="{s["med"]:.5f}">{pct(s["med"])}</td>'
            f'<td class="r" data-v="{s["mean5"] if s["mean5"] is not None else ""}">{pct(s["mean5"])}</td>'
            f'<td class="r" data-v="{s["big"] if s["big"] is not None else ""}">{_share(s["big"])}</td>'
            f'<td class="r" data-v="{s["oc_share"] if s["oc_share"] is not None else ""}">{_share(s["oc_share"])}</td>'
            f'<td data-v="{ {"High": 3, "Moderate": 2, "Low": 1}[s["grade"]] + s["share"] / 10:.4f}"><span class="nev-grade {gcls}">{s["grade"]}</span>{why}</td></tr>')


def _table(keys, C):
    head = ('<thead><tr><th>Kind of news</th><th class="r" data-sort-first="desc">Events / stocks</th>'
            '<th class="r" data-sort-first="desc">As expected</th><th class="r">Median</th><th class="r">5-day avg</th>'
            '<th class="r" data-sort-first="desc">Big moves</th><th class="r" data-sort-first="desc">From the open</th>'
            '<th data-sort-first="desc">Predictability</th></tr></thead>')
    rank = {"High": 0, "Moderate": 1, "Low": 2}
    keys = sorted([k for k in keys if k in C["cats"]], key=lambda k: (rank[C["cats"][k]["grade"]], -C["cats"][k]["share"]))
    rows = "".join(_row(k, C["cats"][k], C) for k in keys)
    return f'<div class="tbl-wrap"><table class="tbl nev-tbl">{head}<tbody>{rows}</tbody></table></div>'


def _what(k, C):
    """What counts as this kind, allowing for a big row folded back in."""
    if k == "beat" and "big-beat" in C["folded"]:
        return "Earnings per share at least 5% above analysts' average estimate going in."
    if k == "miss" and "big-miss" in C["folded"]:
        return "Earnings per share below the estimate."
    return CATS[k][4]


def _as_expected(k, s):
    """'did better than their index 77% of the time (median +1.4%)'."""
    return f"{_verb(s)} their index {_share(s['share'])} of the time (median {pct(s['med'])})"


def _cap(x):
    return x[:1].upper() + x[1:]


def hi_keys(C):
    """Kinds graded High (or Moderate when none are), most one-sided first, headlines aside."""
    cs = C["cats"]
    ks = [k for k in cs if CATS[k][1] != "news" and cs[k]["grade"] == "High"] or [k for k in cs if CATS[k][1] != "news" and cs[k]["grade"] == "Moderate"]
    return sorted(ks, key=lambda k: -cs[k]["share"])


def _findings(C):
    """Plain-English findings, each one read off the numbers."""
    cs = C["cats"]
    out = []
    hi = [k for k in ORDER if k in cs and cs[k]["grade"] == "High" and CATS[k][1] != "news"]
    if hi:
        words = {1: "One kind", 2: "Two kinds", 3: "Three kinds", 4: "Four kinds", 5: "Five kinds", 6: "Six kinds"}
        out.append(f"<b>{words.get(len(hi), str(len(hi)) + ' kinds')} of news cleared the bar for High predictability.</b> "
                   + _cap("; ".join(f"after {CATS[k][3]}, stocks {_as_expected(k, cs[k])}, on {cs[k]['n']:,} events" for k in hi)) + ".")
    else:
        mid = [k for k in ORDER if k in cs and cs[k]["grade"] == "Moderate" and CATS[k][1] != "news"]
        if mid:
            out.append("<b>No kind of news cleared the bar for High predictability.</b> The most reliable: "
                       + "; ".join(f"{CATS[k][3]} ({_share(cs[k]['share'])} as expected, {cs[k]['n']:,} events)" for k in mid[:3]) + ".")
    ladder = [k for k in ("big-beat", "beat", "small-beat") if k in cs]
    if len(ladder) >= 2:
        span = {"big-beat": "20% or more above the estimate", "beat": "5% or more above" if "big-beat" in C["folded"] else "5% to 20% above",
                "small-beat": "under 5% above, or matched"}
        parts = _cap("; ".join(f"{CATS[k][3]} ({span[k]}): {_share(cs[k]['share'])} did better than their index, median {pct(cs[k]['med'])}" for k in ladder))
        tail = ""
        if C.get("beat_rate") is not None:
            tail = f" {_share(C['beat_rate'])} of the {C['n_reports']:,} reports scored beat or matched the estimate, so a small beat is close to what the market expects."
        out.append(f"<b>With earnings, the size of the surprise matters.</b> {parts}.{tail}")
    am = C.get("all_miss")
    if am:
        sub = [k for k in ("miss", "big-miss") if k in cs]
        split = ""
        if len(sub) == 2:
            split = (f" Misses of 10% or more did no better as a signal ({_share(cs['big-miss']['share'])}) than smaller ones ({_share(cs['miss']['share'])})."
                     if abs(cs["big-miss"]["share"] - cs["miss"]["share"]) < 0.03 else
                     f" Misses of 10% or more: {_share(cs['big-miss']['share'])}; smaller misses: {_share(cs['miss']['share'])}.")
        bb = cs.get("big-beat")
        head = ("Misses lean down, but less reliably than big beats lean up." if bb and am["share"] < bb["share"] - 0.02 else "Misses lean down.")
        out.append(f"<b>{head}</b> After a miss of any size, stocks did worse than their index "
                   f"{_share(am['share'])} of the time (median {pct(am['med'])}, {am['n']:,} reports).{split}")
    pu, pdn = cs.get("pt-up"), cs.get("pt-down")
    if pu and pdn:
        pre = ""
        if pu["pre"] is not None and pdn["pre"] is not None and pu["pre"] > 0 > pdn["pre"]:
            pre = (f" In the five sessions before a raise, the stock had already beaten its index by {pct(pu['pre'])} on average; before a cut it had lagged by "
                   f"{pct(abs(pdn['pre']), sign=False)}. Targets tend to follow the price.")
        out.append(f"<b>Price-target changes are weak signals.</b> A raised target with the rating kept was followed by a gain against the index "
                   f"{_share(pu['share'])} of the time; a cut target by a drop {_share(pdn['share'])} of the time.{pre}")
    secs = [k for k in ("leader", "deal", "financing", "restructure", "other-8k") if k in cs and cs[k]["n"] >= 30]
    if secs and C.get("base") is not None:
        lows = [k for k in secs if cs[k]["grade"] == "Low"]
        if lows:
            out.append("<b>Company filings have no reliable direction.</b> "
                       + _cap("; ".join(f"{CATS[k][3]}: {_share(cs[k]['share'])} went the more common way, {_share(cs[k]['big'])} were big moves" for k in lows))
                       + f". On an ordinary session, {_share(C['base'])} of moves are that big.")
    ok = [k for k in hi_keys(C) if cs[k]["oc_share"] is not None]
    if ok:
        flat = max(cs[k]["oc_share"] for k in ok[:4]) < 0.57
        out.append(("<b>The reliable part is mostly in the opening price.</b> " if flat else "<b>Some of the edge is left after the open.</b> ")
                   + "Counted from the reaction session's opening price to its close instead of from the close before the news, the share going the expected way falls: "
                   + ", ".join(f"{CATS[k][3]} {_share(cs[k]['oc_share'])} (from {_share(cs[k]['share'])})" for k in ok[:4]) + "."
                   + (" Acting at the open, once the news was out, was close to a coin flip." if flat else ""))
    eb = [k for k in EARN_KEYS if k in cs and cs[k]["big"] is not None]
    if eb and C.get("base") is not None:
        lo, hi_ = min(cs[k]["big"] for k in eb), max(cs[k]["big"] for k in eb)
        out.append(f"<b>Earnings move stocks the most.</b> {_share(lo)} to {_share(hi_)} of earnings reactions were big moves (twice a normal day or more), "
                   f"against {_share(C['base'])} of ordinary sessions, whichever way the surprise went.")
    drift = [k for k in ("big-beat", "beat", "miss", "big-miss", "upgrade", "downgrade") if k in cs and cs[k]["mean5"] is not None]
    if drift:
        parts = []
        for k in drift:
            s = cs[k]
            same = (s["mean5"] > 0) == (s["mean"] > 0)
            word = "kept going" if same and abs(s["mean5"]) > abs(s["mean"]) * 1.05 else "held" if same and abs(s["mean5"]) >= abs(s["mean"]) * 0.95 else "gave some back" if same else "reversed"
            parts.append(f"{CATS[k][3]} {pct(s['mean'])} after one session, {pct(s['mean5'])} after five ({word})")
        out.append("<b>Does the move keep going?</b> Average moves against the index: " + "; ".join(parts) + ".")
    return out


def guide_page(site):
    R = _R()
    path, depth = GUIDE, 2
    h = lambda x: site.href(depth, x)
    C = cat_stats(site)
    cs = C["cats"]
    main_keys = [k for k in ORDER if CATS[k][1] != "news"]
    news_keys = [k for k in ORDER if CATS[k][1] == "news"]
    n_main = sum(cs[k]["n"] for k in main_keys if k in cs)
    n_news = sum(cs[k]["n"] for k in news_keys if k in cs)
    ys = C["earn_years"]
    first_y = ys[len(ys) // 20] if ys else None          # 95% of the reports scored are from this year on
    finds = "".join(f"<li>{x}</li>" for x in _findings(C))
    ex = R.TK.get("MU") or next((t for t in R.universe() if is_stock(t)), None)
    hi_def = ("<b>High</b>: moved the expected way at least 65% of the time, on at least 50 events, with less than a 1% chance of a record that lopsided from coin flips. "
              "<b>Moderate</b>: at least 57%, 30 events and under a 5% chance. <b>Low</b>: anything else, either because the split is close to 50/50 or because there are too few events to tell.")
    oc = [cs[k]["oc_share"] for k in hi_keys(C) if cs[k]["oc_share"] is not None]
    open_txt = ""
    if oc:
        lo_, hi_ = _share(min(oc)), _share(max(oc))
        rng = lo_ if lo_ == hi_ else f"{lo_} to {hi_}"
        open_txt = (f"Counted from the opening price instead, the kinds graded {cs[hi_keys(C)[0]]['grade']} went the expected way {rng} of the time"
                    + (": most of the reaction was already in the opening price." if max(oc) < 0.57 else "."))
    n_near = sum(C["raw"].get(k, 0) - cs[k]["n"] for k in cs if k not in EARN_KEYS)
    n_pt = sum(C["raw"].get(k, 0) - cs[k]["n"] for k in ("pt-up", "pt-down") if k in cs)
    pt_txt = f", {n_pt:,} of them price-target changes" if n_near and n_pt / n_near > 0.5 else ""
    tm = C.get("timing") or {}
    timing_txt = (f"Yahoo's earnings time put the report on the same session as the company's 8-K filing for {tm['agree']:,} of {tm['checked']:,} reports "
                  "where both exist; where they differ, the earlier time is used. " if tm.get("checked") else "")
    big_txt = ("The 20% line for a big beat was drawn after seeing that larger beats ran more one-sided, so that row may flatter a little. "
               if "big-beat" in cs else "")
    cat_list = "".join(f"<li>{cat_badge(k)} <span class='muted'>{e(_what(k, C))}</span></li>" for k in main_keys if k in cs)
    news_list = "".join(f"<li>{cat_badge(k)} <span class='muted'>{e(CATS[k][4])}</span></li>" for k in news_keys)
    body = f"""
<nav class="crumbs"><a href="{h('guides/')}">Guides</a><span>/</span><span>News that moves stocks</span></nav>
<section class="pair-head"><p class="eyebrow">Guide</p><h1 class="h1">News that moves stocks</h1>
<p class="lede">Some kinds of news move a stock the same way time after time; most don't. Be The Puck sorted {n_main:,} earnings reports, analyst rating changes and company filings on {C['n_stocks']} covered companies into {len([k for k in main_keys if k in cs])} kinds, and measured how each stock moved against its market index at the first close after the news. Here is which kinds have a reliable direction, how big the move tends to be, and whether it keeps going.</p>
<p class="small muted">Earnings reports{f' mostly from {first_y} on' if first_y else ''}, rating changes from the last three years, company filings from the last two.</p></section>

<section><div class="sec-head"><h2 class="h2">What the record says</h2><p>Every number below comes from the events and prices as of the {R.dlong(site.asof)} close.</p></div>
<ol class="g-findings">{finds}</ol></section>

<section aria-labelledby="nev-tbl-h"><div class="sec-head"><h2 class="h2" id="nev-tbl-h">Every kind of news, most predictable first</h2><p>▲ news expected to lift a stock, ▼ news expected to weigh on it, ◆ no expected direction. As expected: the share of events where the stock beat its index on the reaction session (▲) or lagged it (▼), from the last close before the news; for ◆, the share that went the more common way. Median: the middle day-one move against the index. 5-day avg: the average move against the index over five sessions. Big moves: twice a normal day or more ({_share(C['base'])} of ordinary sessions are that big). From the open: the as-expected share counted from the reaction session's opening price. Click a column to sort.</p></div>
{_table(main_keys, C)}</section>

<section aria-labelledby="nev-news-h"><div class="sec-head"><h2 class="h2" id="nev-news-h">Headlines: an early read</h2><p>The same measure for {n_news:,} news headlines sorted by their wording. The headline archive only started recently, so most rows have too few events to grade; they will firm up as it grows.</p></div>
{_table(news_keys, C)}</section>

<section class="split">
<div class="card prose"><p class="eyebrow">How events are sorted</p>
<p><b>Earnings reports</b> come from Yahoo Finance's earnings calendar: the earnings per share each company reported against analysts' average estimate going in. The surprise sorts the report.</p>
<ul class="nev-deflist">{cat_list}</ul>
<p><b>Rating changes</b> (Yahoo Finance, last three years) are kept to one event per kind per stock per day, however many firms acted. A rating change within {NEAR_EARN} sessions of an earnings report is left out of the scores, since the report, not the analyst, usually moved the stock; the same goes for filings and headlines. That set aside {n_near:,} events{pt_txt}.</p>
<p><b>Company filings</b> are 8-Ks from SEC EDGAR, sorted by their lead item. Toronto listings aren't in the filing archive.</p>
<p><b>Headlines</b> from Google News are sorted by their wording. Questions, previews, lists and fund-holding filler are left unsorted.</p>
<ul class="nev-deflist">{news_list}</ul></div>
<div class="card prose"><p class="eyebrow">How a reaction is measured</p>
<p><b>The reaction session</b> is the first session whose 4 pm New York close comes after the event. A report after the close, or on a weekend, is read on the next session.</p>
<p><b>The move</b> is the stock's close-to-close change that session minus its index's (the S&amp;P 500, or the S&amp;P/TSX for Toronto listings). That strips out the day the whole market had.</p>
<p><b>Five days</b> runs from the last close before the event to four sessions after the reaction, again against the index: did the move keep going or fade?</p>
<p><b>A big move</b> is at least twice a normal day for that stock, where a normal day is the typical size of its moves against the index over the 60 sessions before.</p>
<p><b>The odds</b> are a binomial test against a coin flip: how likely a record this lopsided would be if the news told you nothing about direction.</p></div>
</section>

<section class="card prose" id="predictability"><p class="eyebrow">What High predictability means, and what it doesn't</p>
<p>{hi_def}</p>
<p><b>It describes past reactions, averaged across many stocks.</b> A kind graded High tended to move stocks the expected way; any one stock, on any one day, can go the other way, and the median move is the middle of a wide spread.</p>
<p><b>It is not a forecast.</b> Whether earnings beat or miss is only known once the report is out. The predictable part is the reaction once the surprise is known, and it is measured from the last close before the news, a price no one could trade at once the news was out. {open_txt}</p>
<p><b>Other limits.</b> Events on the same day across many stocks are not independent, which makes the odds look better than they are. Analysts sometimes change a rating on the same day as other company news, which this can't separate. {timing_txt}Companies that were delisted or acquired are not in the sample. {big_txt}Headlines are sorted by wording, which misreads some.</p>
<p>Each stock page shows its own record under <a href="{h('stocks/' + ex['slug'] + '/') + '#what-moved' if ex else h('stocks/')}">What moved it lately</a>: its biggest recent moves, the news on each, and how that kind of news has moved it and every other stock.</p>
<p class="small muted">{R.DISCLAIMER}</p></section>
"""
    site.add(path, site.shell(path, "News that moves stocks: which events have a predictable impact",
                              f"Earnings beats and misses, upgrades, downgrades, price-target changes, 8-K filings and headlines on {C['n_stocks']} companies: "
                              "how often each kind of news moved stocks the expected way, by how much, and whether it lasted.",
                              body, active="guides/"))


# ------------------------------------------------------------------ chart markers
def events_json(site):
    """For the chart's hover cards: {"c": {kind: [label, expected, events, share as expected, median day-1 move, grade]},
    "m": {sym: {item t: kind}}, "e": {sym: [[t, kind, surprise %], ...]}}. "m" covers every archived item in
    data/news that has a kind (keyed by the item's own t, as the markers are); an 8-K earnings filing takes the
    kind of the report it carried. "e" lists earnings reports from the last two years."""
    C = cat_stats(site)
    st = _state(site)
    cats = {k: [CATS[k][0], CATS[k][2], s["n"], round(s["share"], 3), round(s["med"], 4), s["grade"]] for k, s in C["cats"].items()}
    marks, earn = {}, {}
    since = int(dt.datetime.now(dt.timezone.utc).timestamp()) - 730 * 86400
    for t in _R().TICKERS:
        if not is_stock(t):
            continue
        S = st.S(t)
        if S is None:
            continue
        evs = st.E(t)
        rep = {x["r"]: x for x in evs if x["s"] == "earn" and x["cat"]}
        m = {}
        for it in _load(os.path.join(NEWS_DIR, t["slug"] + ".json")).get("items") or []:
            ts = _secs(it.get("t"))
            if ts is None or ts < since:
                continue
            if it.get("k") == "sec":
                codes = (it.get("it") or "").split(",")
                if codes[0] == "2.02" or it.get("ty") == "Earnings":
                    i = S.react(ts)
                    x = rep.get(i) or rep.get(i - 1 if i else None) or rep.get(i + 1 if i else None)
                    cat = x["cat"] if x else None
                else:
                    cat = SEC_CAT.get(codes[0]) or SEC_TY.get(it.get("ty"), "other-8k")
            else:
                cat = news_cat(it.get("h", ""))
            if cat in C["cats"]:
                m[it["t"]] = cat
        ee = [[dt.datetime.fromtimestamp(x["ts"], dt.timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ"), x["cat"], x["x"]["sur"]]
              for x in evs if x["s"] == "earn" and x["cat"] and x["ts"] >= since]
        if m:
            marks[t["sym"]] = m
        if ee:
            earn[t["sym"]] = ee
    return json.dumps({"c": cats, "m": marks, "e": earn}, separators=(",", ":"))


# ------------------------------------------------------------------ styles (appended to assets/site.css)
NEWS_CSS = """
/* ---------- news that moves stocks (tools/qstrat/newsevents.py) ---------- */
.nev { display: flex; flex-direction: column; gap: 14px; }
.nev-grid { display: grid; grid-template-columns: minmax(0, 1fr); gap: 14px; align-items: start; }
.nev-grid.has-next { grid-template-columns: minmax(0, 2fr) minmax(0, 1fr); }
.nev-moves { display: flex; flex-direction: column; gap: 12px; min-width: 0; }
.nev-move { display: flex; flex-direction: column; gap: 10px; padding: 16px 18px; }
.nev-mh { display: flex; flex-wrap: wrap; align-items: baseline; gap: 4px 14px; }
.nev-day { font: 600 12px var(--data); letter-spacing: .06em; text-transform: uppercase; color: var(--muted); }
.nev-mv { color: var(--ink-2); font-size: 14px; }
.nev-mv b { font: 600 20px var(--data); margin-right: 4px; }
.nev-z { font: 500 12px var(--data); color: var(--violet-ink); padding: 3px 8px; border-radius: 999px; background: rgba(124, 108, 245, .10); box-shadow: inset 0 0 0 1px rgba(124, 108, 245, .35); }
.nev-sub { margin: 0; font-size: 12.5px; color: var(--muted); }
.nev-evs { list-style: none; margin: 0; padding: 0; display: flex; flex-direction: column; }
.nev-ev { display: flex; flex-direction: column; gap: 6px; padding: 10px 0; border-top: 1px solid var(--line); min-width: 0; }
.nev-ev-top { display: flex; flex-wrap: wrap; align-items: center; gap: 6px 10px; }
.nev-src { font: 500 11.5px var(--data); color: var(--muted); }
.nev-h { margin: 0; color: var(--ink); font-size: 14.5px; line-height: 1.45; overflow-wrap: anywhere; }
.nev-h a { color: var(--ink); text-decoration: underline; text-decoration-color: var(--line-2); text-underline-offset: 3px; }
.nev-h a:hover { text-decoration-color: var(--violet-ink); }
.nev-stat { margin: 0; font-size: 13px; line-height: 1.5; color: var(--ink-2); }
.nev-stat .nev-grade, .nev-stat .tag { margin-left: 4px; vertical-align: 1px; }
.nev-stat.mine { color: var(--muted); }
.nev-none { margin: 0; font-size: 13.5px; line-height: 1.5; color: var(--ink-2); border-left: 2px solid var(--line-2); padding-left: 10px; }
.nev-cat { display: inline-flex; align-items: center; gap: 6px; font: 600 11.5px var(--data); letter-spacing: .02em; color: var(--ink);
  padding: 4px 9px; border-radius: 6px; background: var(--panel-2); box-shadow: inset 0 0 0 1px var(--line-2); white-space: nowrap; }
.nev-cat i { font-style: normal; font-size: 9px; color: var(--muted); }
.nev-cat.d2 i { color: var(--ink-2); }
.nev-cat.d0 i { color: var(--ink-2); }
.nev-cat.none { color: var(--muted); font-weight: 500; }
.nev-grade { display: inline-block; font: 600 11px var(--data); letter-spacing: .03em; padding: 3px 8px; border-radius: 999px; white-space: nowrap; }
.nev-grade.hi { color: #fff; background: var(--violet); }
.nev-grade.mid { color: var(--band); background: rgba(242, 177, 60, .10); box-shadow: inset 0 0 0 1px rgba(242, 177, 60, .40); }
.nev-grade.lo { color: var(--muted); background: var(--panel-2); box-shadow: inset 0 0 0 1px var(--line-2); }
.nev-next { display: flex; flex-direction: column; gap: 8px; position: sticky; top: 84px;
  background: linear-gradient(180deg, rgba(124, 108, 245, .09), rgba(124, 108, 245, .015)), var(--panel); border-color: rgba(124, 108, 245, .35); }
.nev-next p { margin: 0; }
.nev-next-d { font: 500 22px/1.2 var(--display); color: var(--ink); }
.nev-next-d span { font: 500 13px var(--ui); color: var(--ink-2); margin-left: 6px; }
.nev-next-l { margin: 0; padding-left: 18px; display: flex; flex-direction: column; gap: 6px; font-size: 13px; line-height: 1.5; color: var(--ink-2); }
.nev-tbl th, .nev-tbl td { padding-inline: 10px; }
.nev-tbl th { letter-spacing: .04em; }
.nev-tbl .sym-sub { display: block; font-size: 12px; color: var(--muted); margin-top: 4px; white-space: normal; max-width: 36ch; }
.nev-why { display: block; font-size: 11.5px; color: var(--muted); margin-top: 4px; }
.nev-tbl td .tag { margin-left: 6px; font-size: 10.5px; padding: 3px 6px; }
.nev-deflist { list-style: none; padding: 0 !important; gap: 8px !important; }
.nev-deflist li { display: flex; flex-wrap: wrap; gap: 4px 8px; align-items: baseline; font-size: 13.5px; }
@media (max-width: 860px) {
  .nev-grid.has-next { grid-template-columns: minmax(0, 1fr); }
  .nev-next { position: static; }
}
@media (max-width: 600px) {
  .nev-move { padding: 14px; }
  .nev-mv b { font-size: 18px; }
  .nev-cat { white-space: normal; }
}
"""
