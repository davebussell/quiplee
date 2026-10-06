"""/articles/: three shelves of reading, all tied to the live numbers.

  Stocks              a brief for every covered name (generated nightly), the
                      names most plays agree on, the debt lens on crashes
  Strategies & sectors the 20 plays to learn first, trend vs mean reversion by regime,
                      what thousands of backtests say, a brief per sector
  Macro               bubbles and crashes, is this a bubble, cash vs invested

Written pieces carry their own date and sources. Generated pieces say which
close they were built from. Nothing here is advice; every piece says so.
"""
import html
import json
import math

import numpy as np
import pandas as pd

from . import macro
from . import stockview as sv
from .content import TICKERS, TIMED, PLAY, FAMILIES, FAMILY, GROUP_ORDER, credit
from .members import locked_page, member_tag, PRICE

e = html.escape
WRITTEN = pd.Timestamp("2026-10-03")
BUCKETS = [("stocks", "Stocks", "A brief on every covered name, rebuilt each night, plus the names the plays agree on and the ones a crash would hit hardest."),
           ("strategies", "Strategies & sectors", "What the plays are, when each family works, what the backtests really say, and a brief on each sector."),
           ("macro", "Macro", "Bubbles, crashes and the gauges that came before them, and how to think about cash versus staying invested.")]
SECTOR_ETF = {"Semiconductors": "SMH", "Big tech": "XLK", "Software & devices": "XLK", "Healthcare": "XLV", "Financials": "XLF",
              "Industrials & rentals": "XLI", "Energy & power": "XLE", "Metals & mining": "XLB", "Crypto miners": "BTC-USD",
              "Consumer & retail": "XLY", "Media & telecom": "XLC", "Industrials & materials": "XLI", "Real estate": "XLRE"}


def _js(obj):
    return json.dumps(obj, separators=(",", ":"), allow_nan=False).replace("</", "<\\/")


def slugify(s):
    return "".join(c if c.isalnum() else "-" for c in s.lower()).strip("-").replace("--", "-").replace("--", "-")


def P(*paras):
    return "".join(f"<p>{x}</p>" for x in paras)


def pc(v, d=0, sign=True):
    if v is None or (isinstance(v, float) and (math.isnan(v) or math.isinf(v))):
        return "–"
    s = f"{abs(v) * 100:.{d}f}%"
    return ("−" + s) if v < 0 and round(abs(v) * 100, d) else (("+" + s) if sign and v > 0 else s)


class Articles:
    def __init__(self, site):
        self.s = site
        self.list = []      # (bucket, slug_path, title, dek, kind, date)

    # ------------------------------------------------------------- helpers
    def h(self, depth):
        return lambda x: self.s.href(depth, x)

    def core(self):
        """Every play (all of them are core); the starter 20 are self.starter()."""
        return [p for p in TIMED if p.get("core")]

    def starter(self):
        return [p for p in TIMED if p.get("starter")]

    def equities(self, univ=True):
        base = self.s.universe if univ else TICKERS
        return [t for t in base if not t.get("index") and not t["crypto"] and t["group"] not in ("Indexes & ETFs", "Sectors")]

    def risk(self, t):
        return (self.s.meta.get(t["sym"]) or {}).get("risk") or {}

    def share(self, t, plays=None):
        k, n = self.s.consensus(t, plays)
        return (k / n if n else 0), k, n

    def shell(self, path, bucket, title, dek, body, sources=(), live=False, related="", desc=None, date=None):
        depth = path.count("/")
        h = self.h(depth)
        bname = dict((k, n) for k, n, _ in BUCKETS)[bucket]
        when = (f"Rebuilt with the {self.s.asof.strftime('%b %-d, %Y')} close" if live else f"Be The Puck · {(date or WRITTEN).strftime('%b %-d, %Y')}")
        src = ""
        if sources:
            src = ('<section class="card prose art-sources"><p class="eyebrow">Sources</p><ol>'
                   + "".join(f'<li><a href="{e(u)}" rel="noopener" target="_blank">{e(lab)}</a></li>' for lab, u in sources) + "</ol></section>")
        page = f"""
<nav class="crumbs"><a href="{h('articles/')}">Articles</a><span>/</span><a href="{h('articles/')}#{bucket}">{e(bname)}</a></nav>
<article class="article">
<header class="pair-head"><p class="eyebrow">{e(bname)} · {e(when)}</p><h1 class="h1">{title}</h1><p class="lede">{dek}</p></header>
<div class="art-body">{body}</div>
<p class="note-line">This analysis does not constitute trading advice. Please meet with an advisor or independently review sources before making any decision. Be The Puck reports what published rules and public data say; it doesn't know your goals, taxes or timeline.</p>
{src}
{related}
</article>"""
        plain = html.unescape(title.replace("<em>", "").replace("</em>", ""))
        self.s.add(path, self.s.shell(path, plain, desc or html.unescape(dek), page,
                                      active="articles/", scripts=("assets/widgets.js",)))
        crumbs = f'<nav class="crumbs"><a href="{h("articles/")}">Articles</a><span>/</span><a href="{h("articles/")}#{bucket}">{e(bname)}</a></nav>'
        head = f'<header class="pair-head"><p class="eyebrow">{e(bname)} · {e(when)}</p><h1 class="h1">{title}</h1><p class="lede">{dek}</p></header>'
        locked_page(self.s, path, plain, desc or html.unescape(dek), head, what="report", active="articles/", crumbs=crumbs)

    def gauge_table(self, depth):
        M = self.s.macro
        if not M:
            return ""
        from .markets import fmt_val, STATUS_WORD
        h = self.h(depth)
        rows = "".join(f'<tr><td><a href="{h("markets/")}#g-{g["key"]}">{e(g["name"])}</a></td><td class="c"><span class="st-cell st-{g["status"]}">{fmt_val(g, g["value"])}</span></td>'
                       f'<td><span class="g-status {g["status"]}">{STATUS_WORD[g["status"]]}</span></td><td class="small muted">{e(g["reading"])}</td></tr>' for g in M["gauges"])
        return (f'<div class="tbl-wrap"><table class="tbl" data-nosort><thead><tr><th>Gauge</th><th class="c">Now</th><th>Status</th><th>Reading</th></tr></thead>'
                f'<tbody>{rows}</tbody></table></div><p class="small muted">Live from the <a href="{h("markets/")}">Markets page</a>, as of the {self.s.asof.strftime("%b %-d")} close. '
                f'Market weather: <b>{e(M["weather"])}</b>.</p>')

    def related(self, depth, slugs):
        h = self.h(depth)
        cards = ""
        for b, sp, title, dek, kind, _ in self.list:
            if sp in slugs:
                cards += f'<a class="card art-card" href="{h(sp)}"><span class="eyebrow">{e(dict((k, n) for k, n, _ in BUCKETS)[b])}</span><span class="name">{title}</span><span class="muted small">{dek}</span>{member_tag()}</a>'
        return f'<section><h2 class="h2">Keep reading</h2><div class="grid grid-3">{cards}</div></section>' if cards else ""

    # ------------------------------------------------------------- registry
    def plan(self):
        """Register every piece first so the hub and 'keep reading' can link them all."""
        L = self.list
        L.append(("macro", "articles/is-this-a-bubble/", "Is this a bubble? The gauges in October 2026",
                  "Valuations and concentration rival 2000. Credit, jobs and volatility are calm. Rates are the highest since 2007 and the Fed is raising again. What history says to make of that.", "written", WRITTEN))
        L.append(("macro", "articles/bubbles-and-crashes/", "A century of bubbles and crashes, and the signs that came first",
                  "From 1929 to 2022: what fell, how far, what set it off, and which warning signs had a real track record.", "written", WRITTEN))
        L.append(("macro", "articles/cash-or-invested/", "Cash, stay invested, or buckets?",
                  "What selling, holding, rebalancing and a simple trend rule would have done through 2008, 2020 and 2022, and why the bucket approach exists.", "written", WRITTEN))
        L.append(("stocks", "articles/debt-and-crashes/", "Debt decides who survives a crash",
                  "The storm test on every covered stock: which balance sheets would struggle if credit tightened, and how to check one yourself.", "live", None))
        L.append(("stocks", "articles/green-across-the-board/", "Green across the board, with room to run",
                  "The stocks scored half on how many plays hold them and half on analysts' upside: where the room is, what the backdrop says, and where the rules would get out.", "live", None))
        L.append(("strategies", "articles/the-core-20/", "The 20 plays to learn first, and why these 20",
                  f"Out of {len(TIMED)} plays, these 20 are the rules traders actually follow, across the main families. One page on each, with how it has scored.", "live", None))
        L.append(("strategies", "articles/trend-vs-reversion/", "Trend or mean reversion? It depends on the market",
                  "How each family of plays did through the 2008 crash, the COVID drop, the 2022 bear market and the long bull markets in between.", "live", None))
        L.append(("strategies", "articles/what-backtests-say/", "What thousands of backtests say about timing the market",
                  "Every play on every stock against buying and holding: where timing earned its keep, where it didn't, and how not to fool yourself.", "live", None))
        for g in self.sector_groups():
            L.append(("strategies", f"articles/sectors/{slugify(g)}/", f"{e(g)}: what the plays say",
                      f"Every covered {e(g.lower())} name through the same lenses: plays, trend, run-up and crash exposure.", "live", None))

    def sector_groups(self):
        return [g for g in GROUP_ORDER if len([t for t in self.equities() if t["group"] == g]) >= 3]

    def build(self):
        self.plan()
        self.bubble()
        self.history()
        self.cash()
        self.debt()
        self.green()
        self.core20()
        self.regimes()
        self.backtests()
        for g in self.sector_groups():
            self.sector(g)
        for t in TICKERS:
            if (t["sym"], "buy-and-hold") in self.s.R:
                self.stock_brief(t)
        self.hub()

    # ================================================================ hub
    def hub(self):
        path, depth = "articles/", 1
        h = self.h(depth)
        secs = ""
        for key, name, desc in BUCKETS:
            cards = ""
            for b, sp, title, dek, kind, _ in self.list:
                if b != key or "/sectors/" in sp:
                    continue
                tag = '<span class="art-tags">' + ('<span class="tag live">Live</span>' if kind == "live" else "") + member_tag() + '</span>'
                cards += f'<a class="card art-card" href="{h(sp)}">{tag}<span class="name">{title}</span><span class="muted small">{dek}</span></a>'
            extra = ""
            if key == "stocks":
                cards += (f'<a class="card art-card" href="{h("stories/the-hertz-lesson.html")}"><span class="tag">Story</span><span class="name">The Hertz lesson: why a crash doesn\'t care about your revenue</span>'
                          f'<span class="muted small">How a car-rental giant fell 85% in a housing crash, and the five checks that sort survivors from casualties.</span></a>')
                opts = "".join(f'<optgroup label="{e(g)}">' + "".join(f'<option value="{e(t["slug"])}">{e(t["short"])} · {e(t["name"])}</option>' for t in TICKERS if t["group"] == g and (t["sym"], "buy-and-hold") in self.s.R) + "</optgroup>"
                               for g in GROUP_ORDER if any(t["group"] == g for t in TICKERS))
                extra = (f'<div class="card art-lookup"><label for="brief-pick" class="h3">Look up a stock brief</label>'
                         f'<p class="muted small">Every covered name gets a plain-English brief each night: what the plays say, the levels where they would act, the business and the crash risk.</p>'
                         f'<select id="brief-pick" data-nav data-tmpl="{e(h("articles/stocks/{v}/"))}"><option value="">Choose a stock…</option>{opts}</select></div>')
            if key == "strategies":
                chips = "".join(f'<a href="{h("articles/sectors/" + slugify(g) + "/")}">{e(g)}</a>' for g in self.sector_groups())
                extra = f'<div class="card"><p class="h3">Sector briefs</p><div class="chips" style="margin-top:10px">{chips}</div></div>'
            secs += f'<section id="{key}"><div class="sec-head"><h2 class="h2">{e(name)}</h2><p>{e(desc)}</p></div>{extra}<div class="grid grid-3">{cards}</div></section>'
        feat = ""
        for sp in ["articles/is-this-a-bubble/", "articles/bubbles-and-crashes/", "articles/cash-or-invested/",
                   "articles/debt-and-crashes/", "articles/green-across-the-board/"]:
            b, _, title, dek, kind, date = next(x for x in self.list if x[1] == sp)
            when = f"Updated with the {self.s.asof.strftime('%b %-d')} close" if kind == "live" else (date or WRITTEN).strftime("%b %-d, %Y")
            feat += (f'<a class="card art-card feat" href="{h(sp)}"><span class="eyebrow">{e(dict((k, n) for k, n, _ in BUCKETS)[b])} · {e(when)}</span>'
                     f'<span class="name">{title}</span><span class="muted small">{dek}</span>{member_tag()}</a>')
        feat += (f'<a class="card art-card feat" href="{h("stories/the-hertz-lesson.html")}"><span class="eyebrow">Story · Sep 30, 2026</span>'
                 f'<span class="name">The Hertz lesson: why a crash doesn\'t care about your revenue</span>'
                 f'<span class="muted small">How a car-rental giant fell 85% in a housing crash, and the five checks that sort survivors from casualties.</span></a>')
        body = f"""<section class="pair-head"><p class="eyebrow">Articles and stories</p><h1 class="h1">Read the market, then the stock</h1>
<p class="lede">Plain-English pieces built on the same numbers as the rest of Be The Puck. The live ones rebuild every night with the latest close, so they never go stale.</p>
<p class="mem-note">{member_tag()} <span>The reports are for <a href="{h('members/')}">Be The Puck Members</a>: {PRICE} a month, with the top-picks tracker and alerts on your stocks. The Hertz story stays free.</span></p>
<div class="chips fam-chips">{''.join(f'<a href="#{k}">{e(n)}</a>' for k, n, _ in BUCKETS)}</div></section>
<section aria-labelledby="new-h"><div class="sec-head"><h2 class="h2" id="new-h">Start with these</h2><p>The long reads: bubbles, crashes, debt, positioning and the names the plays agree on.</p></div>
<div class="grid grid-3">{feat}</div></section>
{secs}"""
        self.s.add(path, self.s.shell(path, "Articles and stories", "Long reads on bubbles, crashes, debt and positioning, stock briefs for every covered name, and strategy and sector pieces, rebuilt nightly.",
                                      body, active="articles/"))

    # ================================================================ macro
    def bubble(self):
        path, depth = "articles/is-this-a-bubble/", 2
        h = self.h(depth)
        M = self.s.macro or {}
        by = {g["key"]: g for g in M.get("gauges", [])}
        ndx = by.get("runup", {}).get("value")
        spy = self.s.R.get(("SPY", "ten-month-sma"))
        rule_now = ("in" if spy and spy["state"] == 1 else "out") if spy else None
        hot = sorted([t for t in self.s.universe if t["group"] == "Sectors"], key=lambda t: -(self.risk(t).get("runup2y") or -9))[:3]
        hot_txt = ", ".join(f'{e(t.get("sector") or t["short"])} ({pc(self.risk(t).get("runup2y"))})' for t in hot)
        body = f"""
<div class="prose">
<h2 class="h2">The short answer</h2>
{P("Parts of today's market look like past bubbles and parts don't. Stocks are as expensive as they have been outside 1999–2000, and the index leans on a handful of giants. But credit is calm, unemployment is low and volatility is ordinary, which is not how the run-up to most crashes looked. What changed in the last few months is the thing that has ended many booms: money got more expensive.",
   "Bubbles are easy to describe and hard to time. The useful question is not whether this is a bubble, but how exposed you are if it is.")}

<h2 class="h2">The case that it is</h2>
<ul>
<li><b>Valuation.</b> The Shiller CAPE, price against ten years of inflation-adjusted earnings, was 41.4 on October 2. The only higher months since 1871 were April 1999 to September 2000, when it peaked at 44.2. Its long-run average is about 17.</li>
<li><b>Concentration.</b> The ten biggest stocks were 37.9% of the S&amp;P 500 in June, down from a record of about 41% at the end of 2025 but far above the roughly 27% at the 2000 peak. Nvidia alone was 7.5%.</li>
<li><b>Spending.</b> Amazon, Alphabet, Meta and Microsoft guided to roughly $735–750 billion of capital spending in 2026, up from about $416 billion in 2025, much of it on AI data centres. Their combined free cash flow fell 24% in the year to the second quarter.</li>
<li><b>Borrowing.</b> Margin debt, money borrowed against stock, hit a record $1.50 trillion in June.</li>
<li><b>New shares.</b> The second quarter raised a record $104.8 billion in U.S. IPOs, including SpaceX's $75 billion listing, the largest ever. Heavy share issuance is one of the traits that separated run-ups that crashed from those that didn't.</li>
<li><b>Voices.</b> GMO's Jeremy Grantham called it "the largest investment bubble in American history" in September; Ray Dalio said he sees classic signs.</li>
</ul>

<h2 class="h2">The case that it isn't, or not yet</h2>
<ul>
<li><b>Earnings are real.</b> On next year's expected profits the S&amp;P 500 trades at about 19 times, close to its five- and ten-year averages, because estimates have surged: analysts expect 32% earnings growth in 2026. CAPE is high because it averages ten years of smaller earnings. The two measures disagree, and the argument is about whether today's profits last.</li>
<li><b>Not 1999 prices.</b> Evercore's Julian Emanuel put AI stocks at about 39 times earnings against 152 times in 1999. Goldman Sachs strategists found no valuation bubble in technology, though they warned of a possible <em>earnings</em> bubble. Ed Yardeni calls the rally earnings momentum, not 1999-style fear of missing out.</li>
<li><b>Breadth improved.</b> The equal-weight S&amp;P 500 beat the cap-weighted index this year, up about 16% to late August against about 12%: more of the market is joining in.</li>
<li><b>No credit stress.</b> Corporate bond spreads are near their tightest in decades and the Sahm rule, which tracks rising unemployment, reads about zero.</li>
</ul>

<h2 class="h2">What changed recently</h2>
{P("On September 16 the Federal Reserve raised its target rate to 3.75–4.00%, its first increase since July 2023, saying inflation remains elevated. The 10-year Treasury yield rose above 5% for the first time since 2007. Margin debt fell $84.8 billion in July, the largest dollar drop on record, before edging back up. IPOs cooled: almost a third of third-quarter deals priced below their range and the Renaissance IPO index fell 11.5%.",
   "Rising rates and a turn in borrowing are on the list of things that preceded the 1929, 2000 and 2007 tops. They are also common in markets that kept going. Charles Schwab's Henry Hoenig put it plainly: bubbles are identified after the fact, so manage the risk rather than the forecast.")}

<h2 class="h2">What the gauges say tonight</h2>
</div>
{self.gauge_table(depth)}
<div class="prose">
<h2 class="h2">What history says about timing</h2>
{P(f"Greenwood, Shleifer and You studied every U.S. industry that rose 100% or more in two years between 1928 and 2014. About half (21 of 40) then fell 40% or more within two years; at a 150% run-up, 80% did. At a 50% run-up the rate was about one in five, against 14% for any random two-year stretch. The Nasdaq-100's two-year gain is {pc(ndx)} tonight; the hottest sector funds are {hot_txt}.",
   "But timing was hard even with hindsight. In the episodes that did crash, prices peaked about six months after first crossing the line, and rose another 30% or so in between. Robert Shiller warned of irrational exuberance in December 1996; prices doubled before they fell, and at the 2003 low they were still above where he spoke.",
   "Traits that raised the odds of a crash: accelerating prices, rising volatility, lots of new shares and outperformance by young firms.")}

<h2 class="h2">What to do with this</h2>
<ul>
<li><b>Know your exposure.</b> Put your holdings in the <a href="{h('watchlist/')}">watchlist</a> and look at the crash column. Stocks with heavy debt and big run-ups fall furthest when credit tightens (<a href="{h('articles/debt-and-crashes/')}">the storm test</a>).</li>
<li><b>Plan for a 30–50% fall before it happens.</b> Money you need in the next few years shouldn't depend on stocks. <a href="{h('articles/cash-or-invested/')}">Cash, stay invested, or buckets</a> runs the numbers.</li>
<li><b>Use rules, not moods.</b> Trend rules don't predict tops, but they step aside once a fall is under way. Meb Faber's 10-month rule on the S&amp;P 500 ETF is <b>{rule_now or '–'}</b> tonight. <a href="{h('stocks/spy/ten-month-sma/')}">See its record</a>.</li>
<li><b>Rebalance.</b> If a few winners have grown into most of your portfolio, trimming them back to a target is the simplest bubble insurance there is.</li>
</ul>
</div>"""
        src = [("multpl.com: Shiller PE by month", "https://www.multpl.com/shiller-pe/table/by-month"),
               ("FactSet Earnings Insight, Sep 25, 2026", "https://advantage.factset.com/hubfs/Website/Resources%20Section/Research%20Desk/Earnings%20Insight/EarningsInsight_092526.pdf"),
               ("chartrow: S&P 500 concentration", "https://chartrow.com/sp500/concentration"),
               ("RBC Wealth Management: The great narrowing (Jan 2026)", "https://www.rbcwealthmanagement.com/en-us/insights/the-great-narrowing-sp-500-concentration"),
               ("Platformonomics: Q2 2026 capex scoreboard", "https://platformonomics.com/?p=41900"),
               ("Platformonomics: Follow the capex, 2025 retrospective", "https://platformonomics.com/2026/02/follow-the-capex-2025-retrospective/"),
               ("FINRA margin statistics", "https://www.finra.org/rules-guidance/key-topics/margin-accounts/margin-statistics"),
               ("Renaissance Capital: Q2 2026 U.S. IPO review", "https://www.renaissancecapital.com/review/2Q26USReview_Public.pdf"),
               ("Renaissance Capital: Q3 2026 U.S. IPO review", "https://www.renaissancecapital.com/review/3Q26USReview_Press.pdf"),
               ("GMO: Jeremy Grantham on The Diary of a CEO (Sep 2026)", "https://www.gmo.com/americas/research-library/jeremy-grantham-joins-the-diary-of-a-ceo-the-biggest-bubble-in-american-history_inthenews/"),
               ("Fortune: Ray Dalio on AI bubble signs (Aug 2026)", "https://fortune.com/2026/08/04/ray-dalio-ai-bubble-1929-2000-ipos-wealth-is-not-money/"),
               ("Investing.com: Goldman on an earnings bubble (Aug 2026)", "https://www.investing.com/news/stock-market-news/goldman-the-real-ai-risk-is-an-earnings-bubble-not-valuations-4830442"),
               ("Yahoo Finance: echoes of 1999 (May 2026)", "https://finance.yahoo.com/markets/article/wall-street-says-stock-market-euphoria-has-echoes-of-1999-but-a-firmer-foundation-180757836.html"),
               ("Stocktwits: Ed Yardeni on FEMO (Aug 2026)", "https://stocktwits.com/news-articles/markets/equity/ed-yardeni-downplays-ai-bubble-concerns-market-rally-femo-not-fomo-1999/cZYcBWaRJjT"),
               ("Fortune: equal-weight funds in 2026", "https://fortune.com/2026/08/28/why-equal-weight-sp-500-funds-having-moment-up-almost-16-this-year-alone/"),
               ("Federal Reserve statement, Sep 16, 2026", "https://www.federalreserve.gov/newsevents/pressreleases/monetary20260916a.htm"),
               ("Advisor Perspectives: Schwab, What market bubble? (Sep 2026)", "https://www.advisorperspectives.com/commentaries/2026/09/04/what-market-bubble"),
               ("Greenwood, Shleifer & You, Bubbles for Fama (NBER w23191)", "https://www.nber.org/system/files/working_papers/w23191/w23191.pdf")]
        self.shell(path, "macro", "Is this a bubble? The gauges in October 2026",
                   "Valuations and concentration rival 2000. Credit, jobs and volatility are calm. Rates are the highest since 2007 and the Fed is raising again. What history says to make of that.",
                   body, src, related=self.related(depth, ["articles/bubbles-and-crashes/", "articles/cash-or-invested/", "articles/debt-and-crashes/"]))

    def history(self):
        path, depth = "articles/bubbles-and-crashes/", 2
        h = self.h(depth)
        rows = [
            ("1929", "Dow", "Sep 1929 – Jul 1932", "−89%", "Stocks bought with 10% down and the rest borrowed; the Fed raised rates to 6% to cool speculation.", "CAPE 32.6; record margin borrowing; the economy had already peaked in August."),
            ("1973–74", "S&amp;P 500", "Jan 1973 – Oct 1974", "−48%", "Inflation after the end of the gold standard, then the oil embargo quadrupled oil prices.", "'Nifty Fifty' growth stocks at 42× earnings, though the index CAPE was only 18.7."),
            ("1987", "S&amp;P 500", "Aug – Dec 1987", "−34%", "Portfolio-insurance selling fed on itself; the Dow fell 22.6% in a single day.", "Up 44% in seven months. CAPE only 18.3. No recession followed."),
            ("Japan 1990", "Nikkei 225", "Dec 1989 – 2009", "−82%", "The Bank of Japan raised rates from 2.5% to 6% into a property and stock bubble.", "Stock P/E above 50; land valued above all of California. Took until 2024 to recover."),
            ("2000–02", "Nasdaq", "Mar 2000 – Oct 2002", "−78%", "Internet stocks with no profits; the Fed raised rates from 4.75% to 6.5%.", "Record CAPE of 44.2; 476 IPOs in 1999, three in four unprofitable; margin debt peaked the same month."),
            ("2007–09", "S&amp;P 500", "Oct 2007 – Mar 2009", "−57%", "Bad mortgages packaged into securities; Lehman failed; credit froze.", "Yield curve inverted from Aug 2006; credit was cheap, not stressed, beforehand; margin debt peaked Jul 2007."),
            ("2020", "S&amp;P 500", "Feb – Mar 2020", "−34%", "A pandemic: an outside shock, over in 33 days.", "Few useful signs. The VIX hit a record 82.7 during the fall, not before."),
            ("2022", "S&amp;P 500", "Jan – Oct 2022", "−25%", "Inflation hit 9.1%; the Fed raised rates from zero to 4.25–4.5% in nine months.", "CAPE 38.6; record margin debt; 613 SPAC listings in 2021."),
        ]
        trs = "".join(f"<tr><td><b>{a}</b><span class='sym-sub'>{b}</span></td><td class='nowrap'>{c}</td><td class='r'><b>{d}</b></td><td class='small'>{x}</td><td class='small muted'>{y}</td></tr>" for a, b, c, d, x, y in rows)
        ind = [
            ("Valuation (CAPE)", "Returns over the next ten years", "High readings came before poor decades.", "Useless for timing: high for years before 2000; ordinary before 1973 and 1987."),
            ("Inverted yield curve", "Recessions, 5–16 months ahead", "Came before every U.S. recession since 1969.", "The 2022–24 inversion has not been followed by one so far. Not a crash timer: none before 1987."),
            ("Credit spreads", "Economic slowdowns and falling stocks", "Widening spreads led downturns (Gilchrist & Zakrajšek).", "Often tightest just before trouble, as in early 2007; they widen mostly during the fall."),
            ("Sahm rule", "Recessions as they start", "Triggered early in every recession since 1960.", "Fired in 2024 with no recession, when immigration was swelling the workforce."),
            ("Two-year run-ups", "Crash odds", "100%+ run-ups crashed about half the time.", "Prices kept rising for about six months after the signal, on average."),
            ("Long calm (low VIX)", "Build-ups of risk", "Long low-volatility stretches came before banking crises (Danielsson et al.).", "The VIX itself spikes during crashes, not before."),
            ("Margin debt", "Leverage turning", "Peaked near the 2000, 2007 and 2021 tops.", "New records happen in most bull markets; the turn matters more than the level."),
            ("IPO frenzy", "Lower returns ahead", "Heavy equity issuance came before weak markets (Baker & Wurgler).", "Hard to measure in real time; busy years can run on."),
        ]
        irs = "".join(f"<tr><td><b>{a}</b></td><td class='small'>{b}</td><td class='small'>{c}</td><td class='small muted'>{d}</td></tr>" for a, b, c, d in ind)
        body = f"""
<div class="prose">{P("Every crash looks obvious afterwards. In real time each one had a different trigger, and the warning signs that worked once often failed the next time. What they shared was a market stretched by optimism or borrowing, and then something that made money tighter or scarcer.")}</div>
<h2 class="h2">Eight big falls</h2>
<div class="tbl-wrap"><table class="tbl" data-nosort><thead><tr><th>Crash</th><th>Peak to low</th><th class="r">Fall</th><th>What set it off</th><th>Signs beforehand</th></tr></thead><tbody>{trs}</tbody></table></div>
<div class="prose">
<h2 class="h2">How manias run</h2>
{P("Charles Kindleberger, building on Hyman Minsky, described the same five stages in centuries of manias. A <b>displacement</b>, a new technology or policy, creates real opportunity. A <b>boom</b> follows, fed by cheap credit. Then <b>euphoria</b>: rising prices become the reason to buy and borrowing grows riskier. In <b>distress</b>, insiders sell and money gets tighter. Finally <b>revulsion</b>: everyone wants out at once.",
   "Minsky's point was that stability breeds instability. Long calm periods encourage more borrowing against higher prices, so the system grows fragile precisely when it looks safest.")}
<h2 class="h2">Which warning signs have a record</h2>
</div>
<div class="tbl-wrap"><table class="tbl" data-nosort><thead><tr><th>Sign</th><th>What it predicts</th><th>Record</th><th>Blind spots</th></tr></thead><tbody>{irs}</tbody></table></div>
<div class="prose">
<h2 class="h2">Three lessons</h2>
<ol>
<li><b>Valuation sets the size of the fall, not the date.</b> The most expensive markets (1929, 2000) fell furthest, but they stayed expensive for years first.</li>
<li><b>Tight money is usually the trigger.</b> Rate rises came before 1929, Japan, 2000, 2007 and 2022. The exceptions, 1987 and 2020, were shocks that recovered fast.</li>
<li><b>Debt decides who survives.</b> Companies and investors who had to sell at the bottom are the ones the crash destroyed. <a href="{h('articles/debt-and-crashes/')}">The storm test</a> applies this to every stock Be The Puck covers.</li>
</ol>
<p>All nine of Be The Puck's gauges, with their history and readings at the last four tops, are on the <a href="{h('markets/')}">Markets page</a>.</p>
</div>"""
        src = [("Federal Reserve History: Stock market crash of 1929", "https://www.federalreservehistory.org/essays/stock-market-crash-of-1929"),
               ("Yardeni Research: S&P 500 bear market tables", "https://archive.yardeni.com/pub/sp500corrbeartables.pdf"),
               ("Federal Reserve History: Oil shock of 1973–74", "https://www.federalreservehistory.org/essays/oil-shock-of-1973-74"),
               ("AAII: Siegel, Valuing growth stocks: the Nifty Fifty", "https://www.aaii.com/journal/article/valuing-growth-stocks-revisiting-the-nifty-fifty"),
               ("Federal Reserve History: Stock market crash of 1987", "https://www.federalreservehistory.org/essays/stock-market-crash-of-1987"),
               ("Nippon.com: Nikkei sets first record since 1989", "https://www.nippon.com/en/japan-data/h01927/nikkei-index-sets-first-record-high-since-1989.html"),
               ("French & Poterba, Were Japanese stock prices too high? (NBER)", "https://ideas.repec.org/p/nbr/nberwo/3290.html"),
               ("Fortune: Nasdaq passes its 2000 peak (2015)", "https://fortune.com/2015/04/23/nasdaq-supasses-internet-bubble-peak-to-set-new-record/"),
               ("Jay Ritter: IPO statistics", "https://site.warrington.ufl.edu/ritter/files/IPO-Statistics.pdf"),
               ("Federal Reserve History: Subprime mortgage crisis", "https://www.federalreservehistory.org/essays/subprime-mortgage-crisis"),
               ("NBER business cycle dates", "https://www.nber.org/research/data/us-business-cycle-expansions-and-contractions"),
               ("BLS: CPI up 9.1% in the year to June 2022", "https://www.bls.gov/opub/ted/2022/consumer-prices-up-9-1-percent-over-the-year-ended-june-2022-largest-increase-in-40-years.htm"),
               ("Campbell & Shiller, Valuation ratios and the long-run outlook (NBER w8221)", "https://www.nber.org/papers/w8221"),
               ("Estrella & Mishkin, The yield curve as a predictor of recessions (NY Fed)", "https://www.newyorkfed.org/research/current_issues/ci2-7.pdf"),
               ("Gilchrist & Zakrajšek, Credit spreads and business cycle fluctuations (AER 2012)", "https://www.aeaweb.org/articles?id=10.1257/aer.102.4.1692"),
               ("CRS: The Sahm rule", "https://www.everycrsreport.com/reports/IN12410.html"),
               ("Greenwood, Shleifer & You, Bubbles for Fama (NBER w23191)", "https://www.nber.org/system/files/working_papers/w23191/w23191.pdf"),
               ("Danielsson, Valenzuela & Zer, Learning from history: volatility and financial crises", "https://www.riskresearch.org/papers/DanielssonValenzuelaZer2015/"),
               ("Baker & Wurgler, The equity share in new issues (Journal of Finance 2000)", "https://ideas.repec.org/a/bla/jfinan/v55y2000i5p2219-2257.html"),
               ("Loomis Sayles: the Kindleberger-Minsky liquidity cycle", "https://www.loomissayles.com/internet/InternetData.nsf/0/B1F8BC5B2A8A05A285257AC6004AFE01/$FILE/Liquidity-Cycle.pdf"),
               ("FINRA margin statistics", "https://www.finra.org/rules-guidance/key-topics/margin-accounts/margin-statistics")]
        self.shell(path, "macro", "A century of bubbles and crashes, and the signs that came first",
                   "From 1929 to 2022: what fell, how far, what set it off, and which warning signs had a real track record.",
                   body, src, related=self.related(depth, ["articles/is-this-a-bubble/", "articles/cash-or-invested/", "articles/debt-and-crashes/"]))

    def cash(self):
        path, depth = "articles/cash-or-invested/", 2
        h = self.h(depth)
        Pd = macro.positioning_data()
        B = macro.best_days()
        from .markets import SCENARIOS
        plans = [("All stocks, held", {"stocks": 1, "bonds": 0, "gold": 0, "cash": 0}, "hold"),
                 ("Sold everything, back in 12 months later", {"stocks": 1, "bonds": 0, "gold": 0, "cash": 0}, "cash"),
                 ("60/40, rebalanced yearly", {"stocks": .6, "bonds": .4, "gold": 0, "cash": 0}, "rebal"),
                 ("Three buckets (60/25/15), rebalanced", {"stocks": .6, "bonds": .25, "gold": 0, "cash": .15}, "rebal"),
                 ("Stocks on the 10-month rule", {"stocks": 1, "bonds": 0, "gold": 0, "cash": 0}, "rule")]
        heads, rows = [], {p[0]: [] for p in plans}
        for sc in SCENARIOS[:3]:
            heads.append(sc["label"].split(":")[0])
            for name, mix, plan in plans:
                r = sim(Pd, sc["from"], sc["to"], mix, plan)
                rows[name].append(r)
        trs = ""
        for name, _, _ in plans:
            cells = "".join(f'<td class="r">{pc(r["dd"])}<span class="sym-sub">{("back in " + str(r["rec"]) + " mo") if r["rec"] is not None else "not back"}</span></td>' for r in rows[name])
            trs += f"<tr><td>{e(name)}</td>{cells}</tr>"
        table = (f'<div class="tbl-wrap"><table class="tbl" data-nosort><thead><tr><th>Plan</th>{"".join(f"<th class=r>{x}</th>" for x in heads)}</tr></thead><tbody>{trs}</tbody></table></div>'
                 f'<p class="small muted">Worst fall of $10,000 invested at each peak, and months until it was back to $10,000. SPY, TLT and T-bills, monthly, before tax.</p>')
        bd = "".join(f"<tr><td>{e(l)}</td><td class='r mono'>${v:,.0f}</td></tr>" for l, v in B["rows"])
        body = f"""
<div class="prose">
{P("When markets look stretched, the question people actually ask is simple: should I get out? The honest answer is that getting out is two decisions, not one. You have to sell before the fall and buy back before the recovery, and the recovery tends to start when the news is worst.")}
<h2 class="h2">The cost of missing the best days</h2>
{P(f"$10,000 in the S&amp;P 500 ETF from January 2005 grew to about ${B['rows'][0][1]:,.0f}. Miss just the ten best days and it was about ${B['rows'][1][1]:,.0f}. Of the 20 best days, {B['best20_in_bear']} came during bear markets, and {B['best20_near_worst']} came within two weeks of one of the 20 worst. Anyone who sold to avoid the worst days very likely missed the best ones too.")}
</div>
<div class="tbl-wrap"><table class="tbl" data-nosort><thead><tr><th>$10,000 in SPY, Jan 2005 to {B['end'].strftime('%b %Y')}</th><th class="r">Ending value</th></tr></thead><tbody>{bd}</tbody></table></div>
<div class="prose">
<h2 class="h2">Five plans through three crashes</h2>
{P("Here is what each approach did to $10,000 invested at the top before 2008, 2020 and 2022.")}
</div>
{table}
<div class="prose">
{P("A few things stand out. Selling at the top and waiting a year sounds safe, but in 2020 it locked in a loss while the market raced back. A 60/40 mix fell roughly half as far as stocks in 2008, but in 2022 bonds fell with stocks, because rising rates hit both. The 10-month rule cut the 2008 loss sharply, but sold late and bought back late in the fast COVID drop. No plan wins every time; each trades one risk for another.")}
<h2 class="h2">Why buckets exist</h2>
{P("The bucket approach, popularised by planner Harold Evensky, doesn't try to dodge crashes. It sorts money by when you'll need it: one to two years of spending in cash, the next several years in bonds, and only long-term money in stocks. A crash then never forces you to sell stocks at the bottom to pay bills, and you refill the cash bucket from whichever bucket did well.",
   "The size of each bucket is a personal decision about your income, spending and timeline, which is why Be The Puck shows the trade-offs rather than a recommendation.")}
<h2 class="h2">Try it yourself</h2>
<p>The <a href="{h('markets/')}#positioning">simulator on the Markets page</a> lets you set your own mix, pick a crash and compare plans month by month.</p>
<h2 class="h2">Questions worth answering before the next fall</h2>
<ul>
<li>How much of this money will I need in the next three years?</li>
<li>If my stocks fell 40%, would I sell? If yes, I own more stocks than I can hold.</li>
<li>What would make me buy back in? Write it down now; a rule such as the <a href="{h('strategies/ten-month-sma/')}">10-month rule</a> is one way.</li>
<li>Have a few winners grown into most of my portfolio? Rebalancing back to a target is the cheapest protection there is.</li>
</ul>
</div>"""
        src = [("Be The Puck calculation from SPY, TLT and ^IRX prices (Yahoo Finance)", "https://finance.yahoo.com/quote/SPY/"),
               ("Meb Faber, A Quantitative Approach to Tactical Asset Allocation", "https://papers.ssrn.com/abstract=962461")]
        self.shell(path, "macro", "Cash, stay invested, or buckets?",
                   "What selling, holding, rebalancing and a simple trend rule would have done through 2008, 2020 and 2022, and why the bucket approach exists.",
                   body, src, related=self.related(depth, ["articles/is-this-a-bubble/", "articles/bubbles-and-crashes/", "articles/debt-and-crashes/"]))

    # ================================================================ stocks
    def debt(self):
        path, depth = "articles/debt-and-crashes/", 2
        h = self.h(depth)
        names = [t for t in self.equities() if self.risk(t) and self.risk(t).get("has_fund")]
        names.sort(key=lambda t: (-self.risk(t)["points"].get("balance", 0), -self.risk(t)["score"], t["short"]))
        heavy = [t for t in names if self.risk(t)["points"].get("balance", 0) >= 2]
        light = [t for t in names if self.risk(t)["points"].get("balance", 0) == 0 and (self.risk(t).get("nd_ebitda") is None or self.risk(t)["nd_ebitda"] <= 0)]
        rows = ""
        for t in names:
            rk = self.risk(t)
            nd, de, cover = rk.get("nd_ebitda"), rk.get("de"), rk.get("cover")
            de_txt = "negative equity" if rk.get("neg_equity") else (f"{de:.2f}×" if de is not None else "–")
            de_v = 99 if rk.get("neg_equity") else (de if de is not None else "")
            nd_txt = "net cash" if nd is not None and nd <= 0 else (f"{nd:.1f}×" if nd is not None else "–")
            cv_txt = f"{cover:.1f}×" if cover is not None else "–"
            bal = rk["points"].get("balance", 0)
            rows += (f'<tr><td><a class="sym" href="{h("stocks/" + t["slug"] + "/")}#crash">{e(t["short"])}</a><span class="sym-sub">{e(t["name"])}</span></td>'
                     f'<td class="r" data-v="{bal}">{bal}/3</td><td class="r" data-v="{de_v}">{de_txt}</td>'
                     f'<td class="r" data-v="{nd if nd is not None else ""}">{nd_txt}</td><td class="r" data-v="{cover if cover is not None else ""}">{cv_txt}</td>'
                     f'<td data-v="{rk["score"]}"><span class="lvl lvl-{sv.LEVEL_CLASS[rk["level"]]}">{e(rk["level"])}</span></td></tr>')
        heavy_txt = ", ".join(f'<a href="{h("stocks/" + t["slug"] + "/")}#crash">{e(t["short"])}</a>' for t in heavy[:10]) or "none"
        intro = P("A crash marks every stock down. What decides which companies come through it is mostly debt. A business that runs on borrowed money has to keep paying interest and refinancing loans whether sales hold up or not, so when a shock hits and lenders pull back, the debt comes due anyway. Revenue doesn't pay a bill that lenders won't roll over.",
                  "Be The Puck's <b>storm test</b> scores every covered stock on that question, alongside how hard it swings with the market, how it fared in past crashes and how far it has run up. The result is its crash exposure: Low, Moderate, High or Very high.")
        light_txt = ", ".join(f'<a href="{h("stocks/" + t["slug"] + "/")}#crash">{e(t["short"])}</a>' for t in light[:10]) or "none"
        body = f"""
<div class="prose">
{intro}
<h2 class="h2">Four numbers that tell you most of it</h2>
<ul>
<li><b>Debt to equity:</b> borrowing against what shareholders own. Above about 1.5× is heavy; above 3×, or negative equity, is fragile.</li>
<li><b>Net debt to EBITDA:</b> how many years of operating cash earnings it would take to pay off the debt after using the cash on hand. Above 4× leaves little room for a bad year.</li>
<li><b>Interest cover:</b> operating profit divided by interest. Under 2× means a modest drop in profit makes the interest hard to pay.</li>
<li><b>When it's due:</b> debt that must be refinanced in the next two years is the real danger, because that's when lenders can say no. Company reports list it; Be The Puck doesn't track it yet.</li>
</ul>
<h2 class="h2">Every covered stock, by balance sheet</h2>
{P(f"Heaviest balance-sheet scores tonight: {heavy_txt}. Net cash and no debt flags: {light_txt}.")}
</div>
<div class="tbl-wrap"><table class="tbl"><thead><tr><th>Stock</th><th class="r" data-sort-first="desc">Debt points</th><th class="r">Debt / equity</th><th class="r">Net debt / EBITDA</th><th class="r">Interest cover</th><th>Crash exposure</th></tr></thead><tbody>{rows}</tbody></table></div>
<div class="prose">
<p class="small muted">Debt points are one part of the 10-point storm test, which also weighs how hard a stock swings with the market, how it fared in past crashes and the size of its run-up. Company figures from Yahoo Finance; banks such as JPMorgan and RBC borrow as their business, so their ratios read high by design.</p>
<h2 class="h2">What to do with it</h2>
<ul>
<li>Check the crash card on any <a href="{h('stocks/')}">stock page</a> before adding to a position, especially after a big run-up.</li>
<li>Size positions so that a heavily borrowed company falling 80% wouldn't change your plans. That is what leverage can do to a stock in a credit crunch.</li>
<li>In a downturn, money tends to move to cash, Treasuries and companies with net cash: the opposite of a heavily borrowed business.</li>
</ul>
<p>Learn to read a balance sheet in the <a href="{h('learn/balance-sheet/')}">balance-sheet lesson</a>, with a stress test you can run yourself. For a worked example of a revenue-rich company undone by its debt, read <a href="{h('stories/the-hertz-lesson.html')}">the Hertz story</a>.</p>
</div>"""
        self.shell(path, "stocks", "Debt decides who survives a crash",
                   "The storm test on every covered stock: which balance sheets would struggle if credit tightened, and how to check one yourself.",
                   body, [("Yahoo Finance company fundamentals", "https://finance.yahoo.com/")], live=True,
                   related=self.related(depth, ["articles/green-across-the-board/", "articles/bubbles-and-crashes/", "articles/is-this-a-bubble/"]))

    def green(self):
        path, depth = "articles/green-across-the-board/", 2
        h = self.h(depth)
        cands = [t for t in self.s.universe if not t.get("index") and t["group"] != "Sectors"]
        outl = {t["sym"]: sv.outlook(self.s, t) for t in cands}
        # green across the board first: at least half the plays in, then ranked on the combined score
        ranked = sorted([t for t in cands if outl[t["sym"]]["ok"] and outl[t["sym"]]["trend"] >= 0.5], key=lambda t: (-outl[t["sym"]]["score"], t["short"]))
        top = ranked[:8]
        M = self.s.macro or {}
        # the scoring table: every name at least half the plays hold, best score first
        tbl = ""
        for t in sorted([t for t in cands if outl[t["sym"]]["trend"] >= 0.5],
                        key=lambda t: (-(outl[t["sym"]]["score"] if outl[t["sym"]]["ok"] else -1), -outl[t["sym"]]["trend"])):
            o = outl[t["sym"]]
            sc = f'<b>{round(o["score"] * 100)}</b>' if o["ok"] else f'<span class="muted small">{e(o["why"])}</span>'
            u = o["upside"]
            tbl += (f'<tr><td><a class="sym" href="{h("stocks/" + t["slug"] + "/")}">{e(t["short"])}</a><span class="sym-sub">{e(t["name"])}</span></td>'
                    f'<td class="r" data-v="{o["trend"]:.4f}">{o["k"]}/{o["n"]}</td>'
                    f'<td class="r {"up" if (u or 0) > 0.02 else "down" if u is not None and u < 0 else ""}" data-v="{"" if u is None else f"{u:.4f}"}">{pc(u) if u is not None else "–"}</td>'
                    f'<td class="r" data-v="{o["n_an"]}">{o["n_an"] or "–"}</td>'
                    f'<td class="r" data-v="{o["score"] if o["ok"] else ""}">{sc}</td></tr>')
        score_tbl = (f'<div class="tbl-wrap"><table class="tbl"><thead><tr><th>Stock</th><th class="r">Plays in</th><th class="r">To analysts\' target</th>'
                     f'<th class="r">Analysts</th><th class="r" data-sort-first="desc">Score</th></tr></thead><tbody>{tbl}</tbody></table></div>')
        stretched = [t for t in cands if outl[t["sym"]]["ok"] and outl[t["sym"]]["trend"] >= 0.6 and outl[t["sym"]]["upside"] <= 0.02]
        stretched_txt = ", ".join(f'<a href="{h("stocks/" + t["slug"] + "/")}">{e(t["short"])}</a> ({outl[t["sym"]]["k"]} of {outl[t["sym"]]["n"]} plays in, target {pc(outl[t["sym"]]["upside"])})'
                                  for t in sorted(stretched, key=lambda t: -outl[t["sym"]]["trend"]))
        cards = ""
        for t in top:
            sh, k, n = self.share(t)
            kc, nc = self.s.consensus(t, self.core())
            rk = self.risk(t)
            fund = self.s.fund.get(t["sym"]) or {}
            x = self.s.R[(t["sym"], "buy-and-hold")]
            price = x["price"]
            exits = self.exit_levels(t)
            ex_txt = ""
            if exits:
                near = exits[:3]
                ex_txt = "Nearest exits: " + "; ".join(f'{e(p["name"])} below {t["cur"]}{lvl:,.2f} ({pc(d, 1)})' for p, lvl, d in near) + "."
                n10 = sum(1 for _, _, d in exits if d >= -0.10)
                ex_txt += f" A close 10% lower would trip {n10} of the {len(exits)} plays that are in."
            val = []
            pe, fpe = sv.num(fund.get("trailingPE")), sv.num(fund.get("forwardPE"))
            if pe and pe > 0:
                val.append(f"{pe:.0f}× last year's earnings")
            if fpe and fpe > 0:
                val.append(f"{fpe:.0f}× next year's")
            tgt, na = sv.num(fund.get("targetMeanPrice")), sv.num(fund.get("numberOfAnalystOpinions"))
            room = []
            if tgt and na and na >= 3:
                room.append(f"analysts' average target is {pc(tgt / price - 1)} from here ({int(na)} analysts)")
            if rk.get("runup2y") is not None:
                room.append(f"{'up' if rk['runup2y'] >= 0 else 'down'} {pc(abs(rk['runup2y']), sign=False)} in two years")
            if rk.get("off_high") is not None:
                room.append("at its 52-week high" if rk["off_high"] > -0.01 else f"{pc(rk['off_high'])} from its 52-week high")
            cards += f"""<article class="card green-card"><div class="g-top"><div><p class="eyebrow">{e(t['group'])}</p>
<h3 class="h3"><a href="{h('stocks/' + t['slug'] + '/')}">{e(t['name'])} ({e(t['short'])})</a></h3></div>
<div class="g-val"><b>{round(outl[t['sym']]['score'] * 100)}</b><span class="small muted">score · {k}/{n} plays in · target {pc(outl[t['sym']]['upside'])}</span></div></div>
<ul class="green-facts">
<li><b>Room to grow?</b> {e(("; ".join(room))[:1].upper() + ("; ".join(room))[1:] + ".") if room else "No analyst coverage or valuation data."}{(" Valued at " + e(" and ".join(val)) + ".") if val else ""}</li>
<li><b>Crash exposure:</b> <span class="lvl lvl-{sv.LEVEL_CLASS[rk['level']] if rk.get('level') else 'calm'}">{e(rk.get('level', '–'))}</span>{(". It " + e(rk['why'][0]) + ".") if rk.get('why') else "."}</li>
<li><b>Where the rules get out:</b> {ex_txt or "No price-based exit level among the plays right now."}</li>
</ul>
<p class="small"><a href="{h('articles/stocks/' + t['slug'] + '/')}">Full brief</a> · <a href="{h('stocks/' + t['slug'] + '/')}">Every play</a></p></article>"""
        wx = M.get("weather", "–")
        wx_par = P(f"Be The Puck's market weather is <b>{e(wx)}</b> tonight. Strong stocks tend to fall hardest when a broad market fall comes, because they are where the crowd is. "
                   f"See all nine gauges on the <a href='{h('markets/')}'>Markets page</a> and the longer argument in <a href='{h('articles/is-this-a-bubble/')}'>Is this a bubble?</a>")
        body = f"""
<div class="prose">
{P(f"A strong trend and room to run are two different things. A stock can have almost every play in and already sit above where analysts think it's worth. So this list ranks each name half on how many of the {len(TIMED)} plays hold it after the {self.s.asof.strftime('%B %-d')} close, and half on how far analysts' average 12-month price target sits above the price.")}
<h2 class="h2">How the score works</h2>
<ul>
<li><b>Half: the plays.</b> The share of all {len(TIMED)} plays holding the stock. 78 of 100 in gives 78% of this half.</li>
<li><b>Half: analysts' upside.</b> The gap to the average 12-month target, scored in a straight line from 20% below the price (nothing) to 50% above it (full marks). A price sitting right on the target earns 29% of this half.</li>
<li><b>Guards.</b> Only names at least half the plays hold make the list. At least {sv.MIN_ANALYSTS} analysts must cover the stock, and a target more than double the price is ignored as stale, which usually happens after a share consolidation. ETFs, indexes and coins have no targets, so they aren't scored.</li>
</ul>
{P("Analyst targets are opinions, they lean optimistic, and they tend to follow the price rather than lead it. They are useful here as a rough check on how much good news is already in the price, not as a forecast.")}
</div>
<div class="green-grid">{cards}</div>
<div class="prose">
<h2 class="h2">Strong trend, little room on the targets</h2>
<p>{("Most plays are in on these, but the price already sits at or above analysts' average target: " + stretched_txt + ". The trend is real; the upside analysts see has mostly been used up, so a pullback or a cut in targets matters more.") if stretched_txt else "No name with most plays in is trading at or above its analysts' average target tonight."}</p>
<h2 class="h2">Every name at least half the plays hold</h2>
</div>
{score_tbl}
<div class="prose">
<h2 class="h2">Is there room to grow?</h2>
{P("Momentum research is on the side of strong stocks: winners over the past three to twelve months have tended to keep outperforming for a while (Jegadeesh and Titman, 1993), which is why so many plays here buy strength. The same research shows momentum can reverse violently, especially after a market fall. Run-ups matter too: in Greenwood, Shleifer and You's work, two-year gains of 100% or more crashed about half the time, though usually after rising further first.",
   "So a strong consensus says the trend is healthy now. It says nothing about how long it lasts. Valuation and analyst targets give a rough sense of how much good news is already in the price.")}
<h2 class="h2">Is now a good time, given the market?</h2>
{wx_par}
<h2 class="h2">Managing the risk</h2>
<ul>
<li><b>Know your exit before you enter.</b> Each card lists where the plays would sell. Decide in advance which rule you'd follow.</li>
<li><b>Size by the exit, not the excitement.</b> If the exit is 15% below and you're willing to lose 1% of your account on one idea, the position can be at most about 7% of the account.</li>
<li><b>Mind the theme.</b> Several of these names may ride the same story. Five stocks on one theme behave like one big position in a sell-off.</li>
<li><b>Stage in.</b> Buying in two or three steps reduces the cost of being wrong about timing.</li>
</ul>
</div>"""
        self.shell(path, "stocks", "Green across the board, with room to run",
                   "The stocks scored half on how many plays hold them and half on analysts' upside: where the room is, what the backdrop says, and where the rules would get out.",
                   body, [("Jegadeesh & Titman, Returns to buying winners and selling losers (Journal of Finance, 1993)", "https://doi.org/10.1111/j.1540-6261.1993.tb04702.x"),
                          ("Greenwood, Shleifer & You, Bubbles for Fama (NBER w23191)", "https://www.nber.org/system/files/working_papers/w23191/w23191.pdf")],
                   live=True, related=self.related(depth, ["articles/debt-and-crashes/", "articles/is-this-a-bubble/", "articles/the-core-20/"]))

    def exit_levels(self, t):
        """(play, level, distance) for plays that are in and have a price exit, nearest first."""
        from .render import next_move
        out = []
        for p in self.core():
            x = self.s.R.get((t["sym"], p["slug"]))
            if not x or x["state"] != 1:
                continue
            nm = next_move(x, p, t)
            if nm["level"] is not None and nm["dist"] is not None and nm["dist"] < 0:
                out.append((p, nm["level"], nm["dist"]))
        out.sort(key=lambda z: -z[2])
        return out

    def entry_levels(self, t):
        from .render import next_move
        out = []
        for p in self.core():
            x = self.s.R.get((t["sym"], p["slug"]))
            if not x or x["state"] != 0:
                continue
            nm = next_move(x, p, t)
            if nm["level"] is not None and nm["dist"] is not None and nm["dist"] > 0:
                out.append((p, nm["level"], nm["dist"]))
        out.sort(key=lambda z: z[2])
        return out

    def stock_brief(self, t):
        path, depth = f"articles/stocks/{t['slug']}/", 3
        h = self.h(depth)
        s = self.s
        sym = t["sym"]
        meta = s.meta.get(sym) or {}
        fund = s.fund.get(sym)
        x = s.R[(sym, "buy-and-hold")]
        kc, nc = s.consensus(t, self.core())
        k, n = s.consensus(t)
        lines = sv.read_lines(s, t, meta, fund) if meta else []
        read = "".join(f"<li>{e(l)}</li>" for l in lines)
        # recent changes
        flips = []
        for p in TIMED:
            r = s.R.get((sym, p["slug"]))
            c = r["last_call"] if r else None
            if c and c["date"] >= s.asof - pd.Timedelta(days=30):
                flips.append((c["date"], p, c))
        flips.sort(key=lambda z: z[0], reverse=True)
        from .render import plays_for
        own = {p["slug"] for p in plays_for(t)}
        def flip_li(d, p, c):
            name = f'<a href="{h(s.pair_path(t, p))}">{e(p["name"])}</a>' if p["slug"] in own else e(p["name"])
            word, cls = ("in", "up") if c["state"] == 1 else ("out", "down")
            return f'<li><span class="mono small">{d.strftime("%b %-d")}</span> {name} went <b class="{cls}">{word}</b> at {t["cur"]}{c["price"]:,.2f}</li>'
        fl = "".join(flip_li(d, p, c) for d, p, c in flips[:8])
        flip_html = f"<ul class='flip-list'>{fl}</ul>" if fl else "<p>No play changed its call on it in the last 30 days.</p>"
        exits, entries = self.exit_levels(t), self.entry_levels(t)

        def lvl_list(items, word):
            return "".join(f'<li><a href="{h(s.pair_path(t, p) if p["slug"] in own else "strategies/" + p["slug"] + "/")}">{e(p["name"])}</a>: {word} {t["cur"]}{lvl:,.2f} <span class="muted">({pc(d, 1)})</span></li>'
                           for p, lvl, d in items[:6])
        levels = ""
        if exits:
            n10 = sum(1 for _, _, d in exits if d >= -0.10)
            levels += f"<p>Of the {len(exits)} plays holding {e(t['short'])} with a price exit, {n10} would sell on a close 10% or less below tonight's. The nearest:</p><ul>{lvl_list(exits, 'sells below')}</ul>"
        if entries:
            n10 = sum(1 for _, _, d in entries if d <= 0.10)
            levels += f"<p>Of the {len(entries)} plays out with a price entry, {n10} would buy on a close up to 10% higher. The nearest:</p><ul>{lvl_list(entries, 'buys above')}</ul>"
        if not levels:
            levels = "<p>None of the plays has a single-close trigger level right now.</p>"
        rk = meta.get("risk") or {}
        crash = ""
        if rk:
            why = "; ".join(rk.get("why") or []) or "nothing on the checklist stands out"
            crash = f"<p>Crash exposure reads <b class='lvl-{sv.LEVEL_CLASS[rk['level']]}'>{e(rk['level'].lower())}</b> ({rk['score']} of 10): {e(why)}. <a href=\"{h('stocks/' + t['slug'] + '/')}#crash\">The full crash card</a>.</p>"
        biz = ""
        if fund and sv.is_equity(t, fund):
            pe, fpe = sv.num(fund.get("trailingPE")), sv.num(fund.get("forwardPE"))
            mcap = sv.num(fund.get("marketCap"))
            margin, rg = sv.num(fund.get("profitMargins")), sv.num(fund.get("revenueGrowth"))
            bits = []
            if mcap:
                bits.append(f"is worth {sv.big_money(mcap, sv.CUR_SIGN.get(fund.get('currency'), t['cur'] or '$'))}")
            if pe and pe > 0:
                bits.append(f"trades at {pe:.0f}× last year's earnings" + (f" and {fpe:.0f}× next year's" if fpe and fpe > 0 else ""))
            elif sv.num(fund.get("trailingEps")) is not None and sv.num(fund.get("trailingEps")) < 0:
                bits.append("lost money over the last year")
            if margin is not None:
                bits.append(f"keeps {pc(margin, 0, sign=False)} of sales as profit" if margin > 0 else "spends more than it earns")
            if rg is not None:
                bits.append(f"grew sales {pc(rg, sign=False)} on a year earlier" if rg >= 0 else f"saw sales shrink {pc(abs(rg), sign=False)} on a year earlier")
            if bits:
                biz = f"<p>{e(t['name'])} " + e(", ".join(bits[:-1]) + (" and " if len(bits) > 1 else "") + bits[-1]) + ".</p>"
        M = s.macro or {}
        wx = M.get("weather")
        y1 = s.one_year(t)
        trend_word = "uptrend" if kc / nc >= 0.6 else "downtrend" if kc / nc <= 0.3 else "mixed picture"
        title = f"{e(t['name'])} ({e(t['short'])}): {kc} of {nc} plays in"
        dek = f"What the plays, the trend and the business say about {e(t['short'])} after the {s.asof.strftime('%b %-d')} close: a {trend_word}, {pc(y1)} over a year."
        body = f"""
<div class="prose">
<ul class="read">{read}</ul>
<h2 class="h2">What changed lately</h2>{flip_html}
<h2 class="h2">Levels that matter</h2>{levels}
{"<h2 class='h2'>The business</h2>" + biz if biz else ""}
{"<h2 class='h2'>If the market cracks</h2>" + crash if crash else ""}
<h2 class="h2">The backdrop</h2>
<p>Be The Puck's market weather is <b>{e(wx or '–')}</b>. When the whole market falls, most stocks fall with it, whatever their own trend. <a href="{h('markets/')}">See the gauges</a>.</p>
<p><a class="btn" href="{h('stocks/' + t['slug'] + '/')}">Chart, every play and the record</a></p>
</div>"""
        self.shell(path, "stocks", title, dek, body, live=True,
                   desc=f"{t['name']} ({t['short']}) brief: {kc} of {nc} plays in, the levels where plays would buy or sell, the business and crash exposure. Updated nightly.",
                   related=self.related(depth, ["articles/green-across-the-board/", "articles/debt-and-crashes/", "articles/is-this-a-bubble/"]))

    # ================================================================ strategies
    def core20(self):
        path, depth = "articles/the-core-20/", 2
        h = self.h(depth)
        guides_link = f'<a href="{h("guides/")}">guides</a>'
        rows = ""
        for fk, fname, _ in FAMILIES:
            ps = [p for p in self.starter() if p["family"] == fk]
            if not ps:
                continue
            rows += f'<tr class="grp"><td colspan="5">{e(fname)}</td></tr>'
            for p in ps:
                sm = self.s.strat_summary(p)
                rows += (f'<tr><td><a href="{h("strategies/" + p["slug"] + "/")}"><b>{e(p["name"])}</b></a><span class="sym-sub">{e(credit(p))}</span></td>'
                         f'<td class="small">{e(p["short"])}</td><td class="r">{sm["in_now"]}/{sm["n"]}</td>'
                         f'<td class="r">{sm["beat_sharpe"]}/{sm["graded"]}</td><td class="r">{sm["cut_dd"]}/{sm["graded"]}</td></tr>')
        body = f"""
<div class="prose">
{P(f"Be The Puck tests {len(TIMED)} plays, and every one runs on every stock it covers, with a page of its own. That is more than anyone needs to follow. These 20 are the ones a newcomer should learn first: the most widely published and followed rule from each corner of technical trading, from Meb Faber's 10-month average to Larry Connors' two-day RSI.",
   'Three tests picked them: the rule is published by a named practitioner or researcher, it is still widely used, and together the 20 cover the main families without repeating the same idea. Once these make sense, the ' + guides_link + ' show which kinds of prediction have worked best.')}
</div>
<div class="tbl-wrap"><table class="tbl" data-nosort><thead><tr><th>Play</th><th>In one line</th><th class="r">In now</th><th class="r">Beat buy &amp; hold (Sharpe)</th><th class="r">Cut drawdown</th></tr></thead><tbody>{rows}</tbody></table></div>
<div class="prose">
<p class="small muted">Counts are across the {len(self.s.universe)} names in Be The Puck's main universe, graded against buying and holding each one over the same dates, after costs.</p>
<h2 class="h2">How to use them</h2>
<ul>
<li><b>As a census, not a signal.</b> When most of the 20 agree, the trend is broad. When they split, the market is undecided.</li>
<li><b>One rule, followed consistently,</b> beats switching rules after every loss. Pick one that fits how often you want to act: monthly rules like the 10-month SMA trade a few times a year; daily rules like RSI(2) trade often.</li>
<li><b>Learn them by doing:</b> the <a href="{h('learn/')}">Learn track</a> covers every family, and <a href="{h('learn/call-it/')}">Call it</a> lets you practise reading them on real charts.</li>
</ul>
</div>"""
        self.shell(path, "strategies", "The 20 plays to learn first, and why these 20",
                   f"Out of {len(TIMED)} plays, these 20 are the rules traders actually follow, across the main families. One page on each, with how it has scored.",
                   body, live=True, related=self.related(depth, ["articles/trend-vs-reversion/", "articles/what-backtests-say/", "articles/green-across-the-board/"]))

    def regime_table(self):
        windows = [("2008 crash", "2007-10-09", "2009-03-09"), ("Recovery 2009–19", "2009-03-09", "2020-02-19"), ("COVID drop", "2020-02-19", "2020-03-23"),
                   ("2020–21 rally", "2020-03-23", "2022-01-03"), ("2022 bear", "2022-01-03", "2022-10-12"), ("Since Oct 2022", "2022-10-12", None)]
        univ = [t for t in self.s.universe if not t["crypto"]]
        out = {}
        for fk, fname, _ in FAMILIES:
            ps = [p for p in TIMED if p["family"] == fk]
            row = []
            for lab, a, b in windows:
                gaps = []
                for t in univ:
                    for p in ps:
                        x = self.s.R.get((t["sym"], p["slug"]))
                        if not x:
                            continue
                        eq = x["equity"]
                        d = pd.DatetimeIndex(eq["dates"])
                        if not len(d) or d[0] > pd.Timestamp(a) + pd.Timedelta(days=10):
                            continue
                        i0 = int(d.searchsorted(pd.Timestamp(a)))
                        i1 = len(d) - 1 if b is None else int(min(len(d) - 1, d.searchsorted(pd.Timestamp(b))))
                        if i1 <= i0:
                            continue
                        rs = float(eq["strat"][i1] / eq["strat"][i0] - 1)
                        rb = float(eq["bh"][i1] / eq["bh"][i0] - 1)
                        gaps.append(rs - rb)
                row.append((float(np.median(gaps)) if gaps else None, len(gaps)))
            out[fk] = (fname, row)
        return windows, out

    def regimes(self):
        path, depth = "articles/trend-vs-reversion/", 2
        h = self.h(depth)
        windows, tab = self.regime_table()
        head = "".join(f"<th class='c'>{e(lab)}</th>" for lab, _, _ in windows)
        rows = ""
        for fk, (fname, row) in tab.items():
            cells = ""
            for v, nn in row:
                cls = "" if v is None else ("st-calm" if v > 0.02 else "st-warning" if v < -0.02 else "")
                cells += f'<td class="c"><span class="st-cell {cls}">{pc(v)}</span></td>'
            rows += f"<tr><td><a href='{h('strategies/')}#fam-{fk}'>{e(fname)}</a></td>{cells}</tr>"
        fam = {fk: self.fam_summary(fk) for fk, _, _ in FAMILIES}
        sum_rows = "".join(f"<tr><td>{e(FAMILY[fk][0])}</td><td class='r'>{v['plays']}</td><td class='r'>{pc(v['bat'], 0, sign=False)}</td><td class='r'>{v['beat_sharpe']}/{v['graded']}</td><td class='r'>{v['cut_dd']}/{v['graded']}</td><td class='r'>{v['switches']:.1f}</td></tr>" for fk, v in fam.items())
        body = f"""
<div class="prose">
{P("Trend plays and mean-reversion plays make opposite bets. Trend plays buy strength and sell weakness, expecting moves to continue. Mean-reversion plays buy weakness and sell strength, expecting moves to snap back. Each is right in a different kind of market, so the useful question isn't which is better, but when each one works.")}
<h2 class="h2">How each family did, market by market</h2>
{P("Median gap between each play and simply holding the same stock over each period, across every stock and ETF in Be The Puck's main universe (crypto excluded). Positive means the play did better than holding.")}
</div>
<div class="tbl-wrap"><table class="tbl tops" data-nosort><thead><tr><th>Family</th>{head}</tr></thead><tbody>{rows}</tbody></table></div>
<div class="prose">
{P("The pattern is the one the research predicts. In sharp, sustained falls like 2008 and 2022, trend and momentum plays stepped aside and beat holding by a wide margin. In long rallies they trailed, because every false alarm costs a little. Mean-reversion plays were the opposite: they lost less ground in choppy markets and missed less of a rally, but bought too early in a real crash. The COVID drop was too fast for most rules to react to at all.")}
<h2 class="h2">The full-history scorecard by family</h2>
</div>
<div class="tbl-wrap"><table class="tbl" data-nosort><thead><tr><th>Family</th><th class="r">Plays</th><th class="r">Calls right</th><th class="r">Beat B&amp;H (Sharpe)</th><th class="r">Cut drawdown</th><th class="r">Switches / yr</th></tr></thead><tbody>{sum_rows}</tbody></table></div>
<div class="prose">
<h2 class="h2">What it means</h2>
<ul>
<li><b>Trend rules are insurance.</b> They cost a little most years and pay out in the rare bad ones. Judge them over a full cycle, not a calm year.</li>
<li><b>Mean reversion wins often, but small.</b> Its high hit rate feels good; its risk is the dip that keeps dipping. Most published versions only buy dips inside a long uptrend for that reason.</li>
<li><b>Combining them</b> is common practice: a slow trend rule decides whether to be in at all, and a faster reversion rule decides when to add.</li>
</ul>
<p>Learn the families in the <a href="{h('learn/trend-following/')}">trend</a> and <a href="{h('learn/oscillators/')}">mean-reversion</a> lessons.</p>
</div>"""
        self.shell(path, "strategies", "Trend or mean reversion? It depends on the market",
                   "How each family of plays did through the 2008 crash, the COVID drop, the 2022 bear market and the long bull markets in between.",
                   body, live=True, related=self.related(depth, ["articles/what-backtests-say/", "articles/the-core-20/", "articles/cash-or-invested/"]))

    def fam_summary(self, fk):
        sms = [self.s.strat_summary(p) for p in TIMED if p["family"] == fk]
        g = sum(m["graded"] for m in sms)
        calls = sum(m["calls"] for m in sms)
        right = sum((m["bat"] or 0) * m["calls"] for m in sms)
        sw = [m["switches"] for m in sms if m["switches"] is not None]
        return {"plays": len(sms), "graded": g, "beat_sharpe": sum(m["beat_sharpe"] for m in sms), "beat_cagr": sum(m["beat_cagr"] for m in sms),
                "cut_dd": sum(m["cut_dd"] for m in sms), "bat": right / calls if calls else None, "switches": float(np.median(sw)) if sw else 0.0}

    def backtests(self):
        path, depth = "articles/what-backtests-say/", 2
        h = self.h(depth)
        groups = {}
        tot = {"n": 0, "sh": 0, "cg": 0, "dd": 0}
        for t in self.s.universe:
            gkey = "Crypto" if t["crypto"] else ("Indexes, sectors & ETFs" if t.get("index") or t["group"] in ("Sectors", "Indexes & ETFs") else
                                                 "Micro caps" if t.get("micro") else "Stocks")
            gg = groups.setdefault(gkey, {"n": 0, "sh": 0, "cg": 0, "dd": 0})
            for p in TIMED:
                x = self.s.R.get((t["sym"], p["slug"]))
                if not x:
                    continue
                a, b = x["stats"]["full"]["strat"], x["stats"]["full"]["bh"]
                if not a or not b:
                    continue
                for d in (gg, tot):
                    d["n"] += 1
                    d["sh"] += (a["sharpe"] or -9) > (b["sharpe"] or -9)
                    d["cg"] += a["cagr"] > b["cagr"]
                    d["dd"] += a["maxdd"] > b["maxdd"]
        grows = "".join(f"<tr><td>{e(k)}</td><td class='r'>{v['n']:,}</td><td class='r'>{pc(v['cg'] / v['n'], 0, sign=False)}</td><td class='r'>{pc(v['sh'] / v['n'], 0, sign=False)}</td><td class='r'>{pc(v['dd'] / v['n'], 0, sign=False)}</td></tr>"
                        for k, v in groups.items() if v["n"])
        best = sorted(TIMED, key=lambda p: -(self.s.strat_summary(p)["beat_sharpe"] / max(1, self.s.strat_summary(p)["graded"])))[:5]
        worst = sorted(TIMED, key=lambda p: (self.s.strat_summary(p)["beat_sharpe"] / max(1, self.s.strat_summary(p)["graded"])))[:5]
        bl = ", ".join(f'<a href="{h("strategies/" + p["slug"] + "/")}">{e(p["name"])}</a>' for p in best)
        wl = ", ".join(f'<a href="{h("strategies/" + p["slug"] + "/")}">{e(p["name"])}</a>' for p in worst)
        n = tot["n"]
        body = f"""
<div class="prose">
{P(f"Be The Puck runs {len(TIMED)} published plays on {len(self.s.universe)} stocks, ETFs, indexes and coins, from 2005 or each one's first year of trading, after costs, earning T-bill interest while out. That is {n:,} backtests, each graded against buying and holding the same thing over the same dates.")}
<h2 class="h2">The headline</h2>
<ul>
<li><b>Higher return than buy and hold:</b> {tot['cg']:,} of {n:,} ({pc(tot['cg'] / n, 0, sign=False)}).</li>
<li><b>Better risk-adjusted return (Sharpe):</b> {tot['sh']:,} of {n:,} ({pc(tot['sh'] / n, 0, sign=False)}).</li>
<li><b>Smaller worst drawdown:</b> {tot['dd']:,} of {n:,} ({pc(tot['dd'] / n, 0, sign=False)}).</li>
</ul>
{P("Read together, that is the honest case for market timing: most rules don't make you richer than holding, but most do make the ride smoother, cutting the deepest losses. Whether that trade is worth it depends on whether a smaller loss would keep you from selling in a panic.")}
<h2 class="h2">By kind of asset</h2>
</div>
<div class="tbl-wrap"><table class="tbl" data-nosort><thead><tr><th>Asset</th><th class="r">Backtests</th><th class="r">Beat on return</th><th class="r">Beat on Sharpe</th><th class="r">Cut drawdown</th></tr></thead><tbody>{grows}</tbody></table></div>
<div class="prose">
{P(f"Plays that beat holding most often on a risk-adjusted basis: {bl}. Least often: {wl}.")}
<h2 class="h2">How not to fool yourself</h2>
<ul>
<li><b>Luck looks like skill.</b> With {n:,} combinations, some will look brilliant by chance. Trust a play that does reasonably well across many stocks over one that did spectacularly on one.</li>
<li><b>Survivors only.</b> Every stock here still trades today. Companies that went to zero aren't in the test, which flatters buy and hold and every play alike.</li>
<li><b>The skeptic's view.</b> Valeriy Zakamulin found moving-average timing showed no reliable edge in the second half of 155 years of U.S. data; the rules earned their keep in a few severe bear markets. <a href="{h('thinkers/valeriy-zakamulin/')}">His scoreboard</a>.</li>
<li><b>Costs and taxes.</b> Be The Puck's backtests deduct trading costs but not taxes. In a taxable account, frequent switching can cost more than any edge.</li>
</ul>
<p>The <a href="{h('learn/reading-a-backtest/')}">backtest lesson</a> explains every column, and the <a href="{h('method/')}">method page</a> lists every assumption.</p>
</div>"""
        self.shell(path, "strategies", "What thousands of backtests say about timing the market",
                   "Every play on every stock against buying and holding: where timing earned its keep, where it didn't, and how not to fool yourself.",
                   body, [("Zakamulin, Market Timing with Moving Averages (Palgrave, 2017)", "https://link.springer.com/book/10.1007/978-3-319-60970-6")],
                   live=True, related=self.related(depth, ["articles/trend-vs-reversion/", "articles/the-core-20/", "articles/cash-or-invested/"]))

    def sector(self, g):
        path, depth = f"articles/sectors/{slugify(g)}/", 3
        h = self.h(depth)
        names = [t for t in self.equities() if t["group"] == g]
        core = self.core()
        rows = ""
        shares, runs, levels = [], [], []
        for t in sorted(names, key=lambda t: -self.share(t, core)[0]):
            sh, kc, nc = self.share(t, core)
            rk = self.risk(t)
            y1 = self.s.one_year(t)
            shares.append(sh)
            if rk.get("runup2y") is not None:
                runs.append((t, rk["runup2y"]))
            if rk.get("level"):
                levels.append(rk["level"])
            from .render import count_in, pct, dir_cls, sortv
            rows += (f'<tr><td><a class="sym" href="{h("stocks/" + t["slug"] + "/")}">{e(t["short"])}</a><span class="sym-sub">{e(t["name"])}</span></td>'
                     f'<td data-v="{sh}">{count_in(kc, nc)}</td><td class="r {dir_cls(y1)}" data-v="{sortv(y1)}">{pct(y1, d=0)}</td>'
                     f'<td class="r" data-v="{sortv(rk.get("runup2y"))}">{pct(rk.get("runup2y"), d=0)}</td>'
                     f'<td data-v="{rk.get("score", "")}">' + (f'<span class="lvl lvl-{sv.LEVEL_CLASS[rk["level"]]}">{e(rk["level"])}</span>' if rk.get("level") else "–")
                     + f'</td><td><a class="small" href="{h("articles/stocks/" + t["slug"] + "/")}">Brief</a></td></tr>')
        avg = float(np.mean(shares)) if shares else 0
        mood = "mostly in" if avg >= 0.6 else "mostly out" if avg <= 0.35 else "split"
        etf = SECTOR_ETF.get(g)
        etf_t = next((t for t in TICKERS if t["sym"] == etf), None)
        etf_txt = ""
        if etf_t and (etf, "buy-and-hold") in self.s.R:
            sh, kc, nc = self.share(etf_t, core)
            rk = self.risk(etf_t)
            etf_txt = (f"<p>The broader fund, <a href=\"{h('stocks/' + etf_t['slug'] + '/')}\">{e(etf_t['short'])}</a>, has {kc} of {nc} plays in"
                       + (f" and is {pc(rk.get('runup2y'))} over two years" if rk.get("runup2y") is not None else "") + ".</p>")
        hot = sorted(runs, key=lambda z: -z[1])
        hot_txt = ""
        if hot:
            big = [f"{e(t['short'])} ({pc(r)})" for t, r in hot if r >= 1.0]
            hot_txt = (f"<p>Two-year run-ups of 100% or more, the line where Greenwood, Shleifer and You found crash odds near one in two: {', '.join(big)}.</p>" if big
                       else f"<p>No name here is up 100% or more over two years; the biggest gain is {e(hot[0][0]['short'])} at {pc(hot[0][1])}.</p>")
        hi = sum(1 for l in levels if l in ("High", "Very high"))
        body = f"""
<div class="prose">
<p>Across the {len(names)} {e(g.lower())} names Be The Puck covers, the plays are <b>{mood}</b>: on average {pc(avg, 0, sign=False)} of them hold each name tonight. {hi} of {len(levels)} names carry high crash exposure.</p>
{etf_txt}{hot_txt}
</div>
<div class="tbl-wrap"><table class="tbl"><thead><tr><th>Stock</th><th>Plays in</th><th class="r">1 year</th><th class="r">2-yr run-up</th><th>Crash exposure</th><th></th></tr></thead><tbody>{rows}</tbody></table></div>
<div class="prose"><p class="small muted">A sector is only as diversified as its holdings: names in one industry tend to fall together in a sell-off. Be The Puck covers a sample of each sector, not all of it.</p></div>"""
        self.shell(path, "strategies", f"{e(g)}: what the plays say", f"Every covered {e(g.lower())} name through the same lenses: plays, trend, run-up and crash exposure.",
                   body, live=True, related=self.related(depth, ["articles/green-across-the-board/", "articles/debt-and-crashes/", "articles/trend-vs-reversion/"]))


def sim(Pd, frm, to, mix, plan):
    """Python twin of the Markets simulator: worst fall and months to get back to the start."""
    dates = Pd["dates"]
    i0 = dates.index(frm) if frm in dates else 0
    i1 = dates.index(to) if to and to in dates else len(dates) - 1
    val = dict(mix)
    port = [1.0]
    for i in range(i0, i1 + 1):
        r = {k: (Pd[k][i] or 0.0) for k in ("stocks", "bonds", "gold", "cash")}
        k = i - i0
        sr = r["stocks"]
        if plan == "cash" and k < 12:
            sr = r["cash"]
        if plan == "rule" and Pd["rule"][i] == 0:
            sr = r["cash"]
        val["stocks"] *= 1 + sr
        for a in ("bonds", "gold", "cash"):
            val[a] *= 1 + r[a]
        tot = sum(val.values())
        if plan == "rebal" and (k + 1) % 12 == 0:
            val = {a: tot * mix[a] for a in mix}
        port.append(tot)
    pk, dd = port[0], 0.0
    for v in port:
        pk = max(pk, v)
        dd = min(dd, v / pk - 1)
    low_i = int(np.argmin(port))
    rec = next((i for i in range(low_i, len(port)) if port[i] >= port[0]), None)
    return {"dd": dd, "rec": rec, "end": port[-1]}
