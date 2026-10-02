"""Learn section: the training hub, seven lessons and the glossary page.

Lessons quote live numbers from the backtests (via the Site object), so the
examples stay current every time the site rebuilds.
"""
import math

import numpy as np
import pandas as pd

from .content import TICKERS, STRATEGIES, STRATEGY, THINKER, TIMED, BAR_WORD
from .glossary import GLOSSARY, TOPICS, BY_SLUG

LESSONS = [
    dict(slug="reading-a-page", title="How to read a Quiplee page", minutes=5,
         summary="What the IN/OUT call, the next move, the charts and the record on every page mean, using a live example."),
    dict(slug="moving-averages", title="Moving averages, explained", minutes=6,
         summary="The building block of every rule here: what a moving average is, simple versus exponential, and why they lag."),
    dict(slug="trend-following", title="Trend following: why it works and when it doesn't", minutes=6,
         summary="The idea behind every rule on the site, the research that supports it, and the price you pay for using it."),
    dict(slug="reading-a-backtest", title="How to read a backtest", minutes=8,
         summary="Annual return, drawdown, volatility, Sharpe ratio and calls right, in plain English, plus the traps that make backtests look better than they are."),
    dict(slug="the-seven-rules", title="The seven rules in plain English", minutes=7,
         summary="Each rule on Quiplee in two or three sentences: who it comes from, how fast it is, and what it's good for."),
    dict(slug="signal-to-plan", title="From signal to plan", minutes=6,
         summary="How people actually use rules like these with real money: core and satellite, position sizing, and taxes in Canada."),
    dict(slug="common-mistakes", title="Seven common mistakes", minutes=5,
         summary="The errors that turn a sensible rule into a losing habit, and how to avoid them."),
]
LESSON = {l["slug"]: l for l in LESSONS}


def fmt_pct(v, d=1):
    if v is None or (isinstance(v, float) and math.isnan(v)):
        return "–"
    s = f"{abs(v) * 100:,.{d}f}%"
    return ("−" + s) if v < 0 and round(abs(v) * 100, d) else (("+" + s) if v > 0 else s)


class Learn:
    def __init__(self, site):
        self.s = site
        self.R = site.R

    # ------------------------------------------------------------- helpers
    def r(self, sym, slug):
        return self.R[(sym, slug)]

    def full(self, sym, slug, side="strat"):
        return self.r(sym, slug)["stats"]["full"][side] or {}

    def lesson_href(self, depth, slug, anchor=""):
        return self.s.href(depth, f"learn/{slug}/") + (f"#{anchor}" if anchor else "")

    def nav_box(self, slug, depth):
        i = [l["slug"] for l in LESSONS].index(slug)
        prev_l = LESSONS[i - 1] if i > 0 else None
        next_l = LESSONS[i + 1] if i + 1 < len(LESSONS) else None
        parts = []
        if prev_l:
            parts.append(f'<a class="card lesson-nav" href="{self.lesson_href(depth, prev_l["slug"])}"><span class="muted small">Previous</span><b>{prev_l["title"]}</b></a>')
        else:
            parts.append('<span></span>')
        if next_l:
            parts.append(f'<a class="card lesson-nav next" href="{self.lesson_href(depth, next_l["slug"])}"><span class="muted small">Next lesson</span><b>{next_l["title"]}</b></a>')
        else:
            parts.append(f'<a class="card lesson-nav next" href="{self.s.href(depth, "learn/glossary/")}"><span class="muted small">Keep this handy</span><b>The glossary</b></a>')
        return f'<nav class="lesson-pager" aria-label="Lessons">{"".join(parts)}</nav>'

    def lesson_shell(self, slug, body_html):
        l = LESSON[slug]
        path, depth = f"learn/{slug}/", 2
        i = [x["slug"] for x in LESSONS].index(slug) + 1
        h = lambda x: self.s.href(depth, x)
        body = f"""
<nav class="crumbs"><a href="{h('learn/')}">Learn</a><span>/</span><span>Lesson {i} of {len(LESSONS)}</span></nav>
<article class="lesson">
<header class="pair-head"><p class="eyebrow">Lesson {i} · {l['minutes']} min read</p><h1 class="h1">{l['title']}</h1><p class="lede">{l['summary']}</p></header>
{body_html}
</article>
{self.nav_box(slug, depth)}
"""
        self.s.add(path, self.s.shell(path, l["title"], l["summary"], body, active="learn/", lesson=slug))

    # ------------------------------------------------------------- hub
    def hub(self):
        path, depth = "learn/", 1
        h = lambda x: self.s.href(depth, x)
        items = "".join(
            f'<li><a class="card lesson-card" href="{h("learn/" + l["slug"] + "/")}"><span class="lesson-n">{i}</span>'
            f'<span class="lesson-txt"><b>{l["title"]}</b><span class="muted small">{l["summary"]}</span></span>'
            f'<span class="muted small nowrap">{l["minutes"]} min</span></a></li>'
            for i, l in enumerate(LESSONS, 1))
        common = ["moving-average", "ema", "sma", "band", "next-move", "drawdown", "sharpe-ratio", "annual-return",
                  "buy-and-hold", "backtest", "whipsaw", "t-bills", "calls-right", "trend-following", "tfsa"]
        chips = "".join(f'<a href="{h("learn/glossary/")}#{c}">{BY_SLUG[c]["term"]}</a>' for c in common)
        total = sum(l["minutes"] for l in LESSONS)
        body = f"""
<section class="pair-head"><p class="eyebrow">Learn</p><h1 class="h1">Trading rules, without the jargon</h1>
<p class="lede">Seven short lessons that take you from "what is a moving average?" to reading any page on Quiplee with confidence. About {total} minutes in total. Every technical word on the site links back to a plain-English definition, so you can also dip in whenever something isn't clear.</p></section>
<section><div class="sec-head"><h2 class="h2">The course</h2><p>Read them in order the first time. Each one builds on the last.</p></div>
<ol class="lesson-list">{items}</ol></section>
<section class="split">
<div class="card prose"><p class="eyebrow">The glossary</p><p class="h3">{len(GLOSSARY)} terms, each in a sentence or two</p>
<p>From "adjusted price" to "whipsaw". Hover over any underlined word on the site to see its definition without leaving the page; tap it on a phone.</p>
<p><a class="btn" href="{h('learn/glossary/')}">Open the glossary</a></p></div>
<div class="card prose"><p class="eyebrow">Words you'll see most</p><div class="chips">{chips}</div></div>
</section>
<section class="card prose"><p class="eyebrow">A note before you start</p>
<p>Quiplee teaches how published trading rules work and how they have behaved. It doesn't know your goals, your taxes or what else you own, so nothing here is advice to buy or sell anything.</p></section>
"""
        self.s.add(path, self.s.shell(path, "Learn", "Seven short lessons and a plain-English glossary for moving averages, trend rules and backtests.", body, active="learn/"))

    # ------------------------------------------------------------- glossary
    def glossary(self):
        path, depth = "learn/glossary/", 2
        h = lambda x: self.s.href(depth, x)
        nav = "".join(f'<a href="#topic-{k}">{lab}</a>' for k, lab in TOPICS)
        secs = ""
        for key, label in TOPICS:
            entries = ""
            for g in [x for x in GLOSSARY if x["topic"] == key]:
                more = ""
                if g.get("lesson"):
                    ls, _, anc = g["lesson"].partition("#")
                    more = f'<p class="gl-more">Explained in depth: <a href="{self.lesson_href(depth, ls, anc)}">{LESSON[ls]["title"]}</a></p>'
                entries += (f'<div class="gl-entry" id="{g["slug"]}" data-search="{(g["term"] + " " + " ".join(g["aliases"])).lower()}">'
                            f'<h3 class="h3">{g["term"]}</h3><p>{g["body"]}</p>{more}</div>')
            secs += f'<section class="gl-topic" id="topic-{key}"><h2 class="h2">{label}</h2><div class="gl-list">{entries}</div></section>'
        body = f"""
<nav class="crumbs"><a href="{h('learn/')}">Learn</a><span>/</span><span>Glossary</span></nav>
<section class="pair-head"><p class="eyebrow">Glossary</p><h1 class="h1">Every term, in plain English</h1>
<p class="lede">{len(GLOSSARY)} words and phrases you'll meet on Quiplee, grouped by topic. Where a term gets a fuller explanation in a lesson, the entry links to it.</p></section>
<section class="gl-tools"><label for="gl-search" class="small muted">Find a term</label>
<input id="gl-search" type="search" placeholder="Try drawdown, EMA, TFSA…" autocomplete="off">
<div class="chips gl-topics">{nav}</div><p id="gl-empty" class="muted" hidden>No terms match. Try a shorter word.</p></section>
{secs}
"""
        self.s.add(path, self.s.shell(path, "Glossary", "Plain-English definitions of every trading, backtest and investing term used on Quiplee.", body, active="learn/", glossary=True))

    # ------------------------------------------------------------- lessons
    def build(self):
        self.hub()
        self.glossary()
        self.reading_a_page()
        self.moving_averages()
        self.trend_following()
        self.reading_a_backtest()
        self.seven_rules()
        self.signal_to_plan()
        self.common_mistakes()

    # 1 ---------------------------------------------------------------------
    def reading_a_page(self):
        depth = 2
        h = lambda x: self.s.href(depth, x)
        sym, slug = "SPY", "ten-month-sma"
        t = next(x for x in TICKERS if x["sym"] == sym)
        x = self.r(sym, slug)
        from .render import next_move, money, dlong
        nm = next_move(x, STRATEGY[slug], t)
        a, b = self.full(sym, slug), self.full(sym, slug, "bh")
        page = h(f"stocks/{t['slug']}/{slug}/")
        state = "IN" if x["state"] == 1 else "OUT"
        body = f"""
<section class="prose">
<p>Every page on Quiplee that pairs a rule with a stock answers three questions: what does the rule say right now, what would make it change its mind, and how has it done in the past? This lesson walks through a real one: <a href="{page}">Meb Faber's 10-month moving average on the S&amp;P 500 ETF (SPY)</a>. Open it in another tab and follow along.</p>
</section>
<section class="prose" id="call">
<h2 class="h2">1. The call: IN or OUT</h2>
<p>The first box tells you the rule's current position. <b>IN</b> means the rule holds the stock. <b>OUT</b> means it has sold and is sitting in cash, which Quiplee assumes earns the interest rate on US Treasury bills.</p>
<p>Right now the 10-month rule on SPY is <b>{state}</b>, and has been since {dlong(x['since'])}. The line underneath shows how much SPY has moved since that call, so you can see whether the call has been working.</p>
</section>
<section class="prose" id="next-move">
<h2 class="h2">2. The next move</h2>
<p>The second box is the most useful thing on the page. It gives the exact closing price that would flip the rule's call at its next check. For SPY it currently reads: <i>"{nm['headline']}"</i></p>
<p>That number comes straight from the rule's formula. If SPY closes beyond it on the check date, the rule changes its call; if not, nothing happens. The percentage beside it tells you how far the price would have to move from the latest close. A level 1% away means the call is fragile; one 15% away means it would take a big move.</p>
<p>The box also tells you <b>when</b> the rule next looks. This rule only checks once a month, on the last trading day, so a dip below the line in the middle of the month doesn't count.</p>
</section>
<section class="prose" id="close">
<h2 class="h2">Why only closing prices count</h2>
<p>Prices jump around all day. A stock can dip below a moving average at 11 am and be back above it by 4 pm. If rules reacted to every intraday wiggle they would trade constantly and lose money on each round trip. So every rule here waits for a <b>finished close</b>: the daily close at 4 pm New York time, Friday's close for weekly rules, or the last close of the month for monthly ones.</p>
</section>
<section class="prose">
<h2 class="h2">3. The price chart</h2>
<p>The first chart shows the last three years of prices with the rule's lines drawn on top. The background is shaded green while the rule was IN and red while it was OUT. Hover over the chart (or tap it on a phone) to see the price, the lines and the call on any day.</p>
<h2 class="h2">4. Growth of 10,000</h2>
<p>The second chart starts both the rule and buy-and-hold with 10,000 and shows how each would have grown since 2005, after trading costs. It uses a log scale so a 10% move looks the same size in 2008 as it does today. Here, the rule turned out <b>{fmt_pct(a.get('total'), 0)}</b> overall, versus <b>{fmt_pct(b.get('total'), 0)}</b> for simply holding.</p>
<h2 class="h2">5. The record</h2>
<p>The table compares the rule with buy-and-hold on the same dates, over the full test and the last five years: annual return, total return, worst drawdown, volatility and Sharpe ratio, plus how often the rule was invested and how often it switched. For SPY the 10-month rule's worst fall was <b>{fmt_pct(a.get('maxdd'))}</b> against <b>{fmt_pct(b.get('maxdd'))}</b> for holding. That trade-off, smaller losses for less growth, is typical. The next lessons explain each number.</p>
<h2 class="h2">6. Every call, graded</h2>
<p>The last table lists the rule's recent calls and marks each one right or wrong. An IN call is right if the price was higher by the time of the next call; an OUT call is right if it was lower. Don't be surprised by a low score. Trend rules are often wrong more than half the time and still do well, because their right calls tend to be much bigger than their wrong ones.</p>
</section>
<section class="card prose"><p class="eyebrow">Try it</p><p>Open <a href="{page}">the SPY page</a> and find the next-move level. Then open <a href="{h('stocks/' + t['slug'] + '/')}">SPY's stock page</a>, which shows every rule's call on SPY side by side, and check how many rules are IN.</p></section>
"""
        self.lesson_shell("reading-a-page", body)

    # 2 ---------------------------------------------------------------------
    def moving_averages(self):
        depth = 2
        h = lambda x: self.s.href(depth, x)
        win = self.r("SPY", "buy-and-hold")["window"]["price"]
        sma = win.rolling(50).mean()
        ema = win.ewm(span=50, adjust=False).mean()
        keep = win.index[60:]
        from .render import sig5, chart_block, key_line
        t0 = keep[0]
        spec = {"t0": t0.strftime("%Y-%m-%d"), "d": [int((d - t0).days) for d in keep], "cur": "$", "fmt": "price",
                "label": "SPY with its 50-day simple and exponential moving averages",
                "series": [{"name": "SPY", "role": "price", "v": [sig5(v) for v in win.loc[keep].values]},
                           {"name": "50-day EMA", "role": "s1", "v": [sig5(v) for v in ema.loc[keep].values]},
                           {"name": "50-day SMA", "role": "s2", "v": [sig5(v) for v in sma.loc[keep].values]}]}
        chart = chart_block("ma-demo", spec, key_line("--s-price", "SPY") + key_line("--s1", "50-day EMA") + key_line("--s2", "50-day SMA"),
                            "SPY with its 50-day averages", "Both lines lag the price. The exponential one (violet) hugs it more closely and turns sooner.")
        body = f"""
<section class="prose" id="what">
<h2 class="h2">What a moving average is</h2>
<p>A moving average is the average of the last few closing prices, recalculated every day. A 5-day moving average adds up the last five closes and divides by five. Tomorrow it drops the oldest day and adds the newest, so the average "moves" along with the price.</p>
<p>Say a stock closed at 10, 11, 12, 11 and 13 over five days. The 5-day average is (10 + 11 + 12 + 11 + 13) ÷ 5 = <b>11.4</b>. If it closes at 14 the next day, the 10 drops out and the 14 comes in: (11 + 12 + 11 + 13 + 14) ÷ 5 = <b>12.2</b>.</p>
<p>The point is to smooth out the noise. Daily prices zig-zag; the average shows which way they're heading underneath. When the price is above a rising average, the trend is up. When it's below a falling one, the trend is down.</p>
</section>
<section class="prose" id="sma-ema">
<h2 class="h2">Simple versus exponential</h2>
<p>A <b>simple moving average</b> (SMA) treats every day equally. In a 21-day SMA, each close counts for 1/21, about 4.8%.</p>
<p>An <b>exponential moving average</b> (EMA) gives the most recent days more weight. In a 21-day EMA, today's close counts for about 9%, yesterday's a little less, and so on back in time. That makes an EMA react faster when the price turns.</p>
<p>Neither is better. Faster averages give earlier signals and more false alarms. Slower ones give fewer, later signals. Most of the rules on Quiplee are really a choice about where to sit on that trade-off.</p>
</section>
{chart}
<section class="prose" id="lag">
<h2 class="h2">Why they always lag</h2>
<p>An average is built from past prices, so it can only confirm a turn after it has happened. A 200-day average might take weeks to turn down after a peak. That lag is the cost of filtering out noise, and it's why trend rules never sell at the top or buy at the bottom. They aim to catch the middle of big moves.</p>
<p>Longer averages lag more. Some common lengths, roughly translated: a 10-month average is about the same as a 200-day one; a 30-week average is about 150 days; a 20-week average is about 100 days.</p>
</section>
<section class="prose" id="bands">
<h2 class="h2">Bands and clouds</h2>
<p>Some rules use two averages and shade the space between them, called a band or a cloud. The PB EMA uses two EMAs; Ben Cowen's bull market support band pairs a 20-week SMA with a 21-week EMA; Ripster's cloud uses the 34- and 50-day EMAs.</p>
<p>The band works like a buffer. Price above the whole band reads as an uptrend, below it as a downtrend. Price inside the band is undecided, so Quiplee's band rules hold their last call until price closes clearly on one side. That one choice cuts out a lot of false signals.</p>
</section>
<section class="prose" id="crossovers">
<h2 class="h2">Crossovers</h2>
<p>A crossover is the moment one line crosses another: the price crossing above its average, or a faster average crossing a slower one. The best-known is the golden cross, when the 50-day average rises above the 200-day, and its opposite, the death cross. Every rule on Quiplee is ultimately a crossover rule with some filter added on top.</p>
</section>
<section class="card prose"><p class="eyebrow">Try it</p><p>Open any <a href="{h('strategies/pb-ema/')}">PB EMA</a> page and find the two EMA lines on the price chart. Then compare it with the slower <a href="{h('strategies/ten-month-sma/')}">10-month SMA</a> on the same stock and notice how many fewer times the shading changes colour.</p></section>
"""
        self.lesson_shell("moving-averages", body)

    # 3 ---------------------------------------------------------------------
    def trend_following(self):
        depth = 2
        h = lambda x: self.s.href(depth, x)
        rows = ""
        for s in STRATEGIES:
            x = self.r("SPY", s["slug"])
            a = x["stats"]["full"]["strat"] or {}
            rows += (f'<tr><td><a href="{h("stocks/spy/" + s["slug"] + "/") if not s.get("benchmark") else h("strategies/buy-and-hold/")}">{s["name"]}</a></td>'
                     f'<td>{BAR_WORD[s["bar"]].capitalize() if not s.get("benchmark") else "Never"}</td>'
                     f'<td class="r">{x["stats"]["switches_per_year"]:.1f}</td><td class="r">{fmt_pct(a.get("cagr"))}</td><td class="r">{fmt_pct(a.get("maxdd"))}</td></tr>')
        n_pairs = len(TICKERS) * len(TIMED)
        cut = beat = 0
        for t in TICKERS:
            for s in TIMED:
                st = self.r(t["sym"], s["slug"])["stats"]["full"]
                if st["strat"] and st["bh"]:
                    cut += st["strat"]["maxdd"] > st["bh"]["maxdd"]
                    beat += st["strat"]["cagr"] > st["bh"]["cagr"]
        body = f"""
<section class="prose" id="idea">
<h2 class="h2">The idea</h2>
<p>Trend following means owning something while its price is rising and stepping aside once it starts falling. It doesn't try to predict anything. It reacts. A trend follower doesn't ask "is this stock cheap?" or "will the economy slow down?" It asks one question: is the price above or below its trend line?</p>
<p>Every rule on Quiplee is a version of this idea. They differ in which line they use, how often they check, and what extra conditions they add.</p>
</section>
<section class="prose" id="why">
<h2 class="h2">Why it can work</h2>
<p>Prices tend to keep going in the direction they've been going, for a while. Researchers call this momentum. In 2012, Tobias Moskowitz, Yao Hua Ooi and Lasse Pedersen showed that an asset's return over the past year helped predict its return over the next month, across stocks, bonds, currencies and commodities, going back decades.</p>
<p>The usual explanations are human. News sinks in slowly, so prices adjust in steps rather than all at once. People pile into what's working and dump what isn't. And big investors take weeks to move money, which keeps a trend going.</p>
</section>
<section class="prose" id="fails">
<h2 class="h2">When it doesn't</h2>
<p>Trend following has two built-in weaknesses.</p>
<p><b>Whipsaws.</b> In a choppy, sideways market the price keeps crossing back and forth over the line. The rule buys, sells a little lower, buys again a little higher, and loses a bit each time. Faster rules suffer most: on SPY, the daily PB EMA band switches about {self.r('SPY', 'pb-ema')['stats']['switches_per_year']:.0f} times a year, while the monthly 10-month rule switches about {self.r('SPY', 'ten-month-sma')['stats']['switches_per_year']:.1f} times.</p>
<p><b>Lag.</b> The rule always gets out after the top and back in after the bottom. When a market drops sharply and recovers quickly, as in early 2020, the rule can sell near the low and buy back higher, missing both sides.</p>
<p>The result is that timing rules spend long stretches trailing buy-and-hold. Meb Faber's own ten-year review of his 10-month rule found it shone in the 2008 crash, then lagged stocks in six of the next eight years. Professor Valeriy Zakamulin, testing 155 years of US data, found the rules' advantage came mainly from a handful of severe bear markets.</p>
</section>
<section>
<div class="sec-head"><h2 class="h2">Speed versus results on the S&amp;P 500</h2><p>Every rule on SPY since 2005, after trading costs. Click a column to sort.</p></div>
<div class="tbl-wrap"><table class="tbl"><thead><tr><th>Rule</th><th>Checks</th><th class="r">Switches / yr</th><th class="r">Annual return</th><th class="r">Worst drawdown</th></tr></thead><tbody>{rows}</tbody></table></div>
</section>
<section class="prose">
<h2 class="h2">What it's really for</h2>
<p>Across all {n_pairs} rule-and-stock pairs on Quiplee, the rule cut the worst drawdown in <b>{cut}</b> cases but beat buy-and-hold's annual return in only <b>{beat}</b>. That's the honest summary: trend rules are mainly a way to limit how much you can lose in a crash, and you usually pay for it with lower growth in good years. If you expect a rule to make you more money than holding, you'll probably be disappointed. If you want it to keep you out of the worst of a collapse, the history is more encouraging.</p>
</section>
<section class="card prose"><p class="eyebrow">Try it</p><p>Sort the table above by "Switches / yr", then by "Worst drawdown". Then read the <a href="{h('thinkers/valeriy-zakamulin/')}">skeptic's scoreboard</a> to see the same pattern across every stock.</p></section>
"""
        self.lesson_shell("trend-following", body)

    # 4 ---------------------------------------------------------------------
    def reading_a_backtest(self):
        depth = 2
        h = lambda x: self.s.href(depth, x)
        from .render import sig5, chart_block, key_line
        x = self.r("SPY", "ten-month-sma")
        eq = x["equity"]
        s_ = pd.Series(eq["strat"], index=pd.DatetimeIndex(eq["dates"]))
        b_ = pd.Series(eq["bh"], index=pd.DatetimeIndex(eq["dates"]))
        dd_s, dd_b = s_ / s_.cummax() - 1, b_ / b_.cummax() - 1
        t0 = s_.index[0]
        spec = {"t0": t0.strftime("%Y-%m-%d"), "d": [int((d - t0).days) for d in s_.index], "cur": "", "fmt": "pct",
                "label": "Drawdowns of SPY: 10-month rule versus buy and hold",
                "series": [{"name": "10-month rule", "role": "s1", "v": [sig5(v) for v in dd_s.values]},
                           {"name": "Buy & hold", "role": "bench", "v": [sig5(v) for v in dd_b.values]}]}
        chart = chart_block("dd-demo", spec, key_line("--s1", "10-month rule") + key_line("--s-bench", "Buy & hold"),
                            "How far below its last peak, week by week (SPY)", "0% means at a new high. The lowest point of each line is its worst drawdown.")
        a, b = self.full("SPY", "ten-month-sma"), self.full("SPY", "ten-month-sma", "bh")
        bat = x["batting"]
        yrs = a.get("years") or 0
        grow = 10000 * (1 + (b.get("cagr") or 0)) ** 20
        body = f"""
<section class="prose" id="what">
<h2 class="h2">What a backtest is</h2>
<p>A backtest runs a rule on past prices to see what it would have done. Quiplee runs every rule on every stock from January 2005 (or the stock's first trading day), and plays fair: it only uses closing prices that were already known, acts on the next trading day, charges a cost on every switch, and pays T-bill interest while the rule is out.</p>
<p>A backtest tells you how a rule behaved, not what it will do next. Treat it like a car's crash-test rating. It's useful, but the road ahead will be different.</p>
</section>
<section class="prose" id="benchmark">
<h2 class="h2">Always compare with doing nothing</h2>
<p>A rule that made 9% a year sounds good until you learn the stock itself made 11%. That's why every number on Quiplee sits next to buy-and-hold on the same stock over the same dates. A rule has to beat simply owning the thing to be worth the effort.</p>
</section>
<section class="prose" id="return">
<h2 class="h2">Annual return and total return</h2>
<p><b>Total return</b> is the whole gain over the period, dividends included: +300% means 10,000 became 40,000. <b>Annual return</b> is the steady yearly rate that would produce the same result. It compounds, so small differences add up: at {fmt_pct(b.get('cagr'))} a year, buy-and-hold SPY's pace, 10,000 grows to about {grow:,.0f} over 20 years.</p>
</section>
<section class="prose" id="drawdown">
<h2 class="h2">Drawdown: the number that tells you how it felt</h2>
<p>A drawdown is how far an investment has fallen from its last high. The <b>worst drawdown</b> is the deepest one in the whole test. It's the number most people underestimate. Buy-and-hold SPY's worst was <b>{fmt_pct(b.get('maxdd'))}</b>, in 2008–09. The 10-month rule's worst was <b>{fmt_pct(a.get('maxdd'))}</b>.</p>
<p>Losses and gains aren't symmetrical. After a 50% fall you need a 100% gain just to get back to even. That's why limiting drawdowns matters more than it first appears.</p>
</section>
{chart}
<section class="prose" id="risk">
<h2 class="h2">Volatility and the Sharpe ratio</h2>
<p><b>Volatility</b> measures how much returns swing around from day to day, scaled to a year. SPY has run at about {fmt_pct(b.get('vol'), 0).lstrip('+')} a year since 2005; the 10-month rule at about {fmt_pct(a.get('vol'), 0).lstrip('+')}, because it spends part of its time in cash.</p>
<p>The <b>Sharpe ratio</b> puts return and risk together: the return earned above cash, divided by volatility. It answers "how much did I get paid for each unit of bumpiness?" Higher is better. A broad stock index usually scores around 0.4 to 0.6 over long periods, and anything consistently above 1 is rare. Here, buy-and-hold SPY scored {b.get('sharpe') or 0:.2f} and the 10-month rule {a.get('sharpe') or 0:.2f}.</p>
</section>
<section class="prose" id="calls">
<h2 class="h2">Calls right</h2>
<p>Calls right is the share of finished calls that went the right way. The 10-month rule on SPY was right on {bat['right']} of {bat['n']} calls ({fmt_pct(bat['avg'], 0).lstrip('+') if bat['avg'] is not None else '–'}). That can look poor, but trend rules are built to take many small losses and a few big wins. One correct call that sidesteps a 40% crash can pay for a dozen small whipsaws.</p>
</section>
<section class="prose">
<h2 class="h2">Switches, time invested and costs</h2>
<p><b>Switches per year</b> counts how often the rule changes its mind; every switch costs money and, in a taxable account, can create a tax bill. <b>Time invested</b> is the share of days the rule held the stock. Quiplee charges 0.05% per switch for stocks and ETFs, 0.10% for crypto and 0.30% for micro caps, whose buying and selling prices are far apart.</p>
</section>
<section class="prose" id="traps">
<h2 class="h2">Three traps that flatter backtests</h2>
<p><b>Overfitting.</b> Try enough settings and one will look brilliant by luck. That's why Quiplee uses each thinker's published settings rather than picking the best-looking ones, and why it shows results for every stock, not just the winners.</p>
<p><b>In-sample results.</b> A rule tuned on the same data it's tested on will look better than it really is. The fair test is out-of-sample: data the designer never saw. The "last 5 years" column on each page is a rough check.</p>
<p><b>Survivorship bias.</b> Quiplee tests stocks that still trade today. Companies that went bust aren't in the data, which makes every strategy, including buy-and-hold, look better than real life would have been.</p>
</section>
<section class="card prose"><p class="eyebrow">Try it</p><p>On <a href="{h('stocks/spy/ten-month-sma/')}">the SPY 10-month page</a>, compare the full-period and 5-year columns. Then try a fast rule on a volatile stock, such as the <a href="{h('stocks/tsla/pb-ema/')}">PB EMA on Tesla</a>, and look at the switches and calls right.</p></section>
"""
        self.lesson_shell("reading-a-backtest", body)

    # 5 ---------------------------------------------------------------------
    def seven_rules(self):
        depth = 2
        h = lambda x: self.s.href(depth, x)
        plain = {
            "pb-ema": ("Fast", "Two short exponential averages make a band. A daily close above the whole band means in; below it means out. Inside the band, it keeps its last call.",
                       "Quick reactions on volatile assets like crypto. On index funds it switches so often that costs and whipsaws eat most of the benefit."),
            "bull-market-support-band": ("Medium", "Ben Cowen's band of a 20-week simple and a 21-week exponential average, checked every Friday. Above the band means a healthy bull market; below it means caution.",
                                         "Bitcoin and broad indexes, where it has historically marked the big regime changes with few trades."),
            "ripster-ema-clouds": ("Fast", "Ripster's cloud between the 34- and 50-day exponential averages, used to decide whether to lean bullish or bearish.",
                                   "Short-term traders who want a simple daily bias. Slower and steadier than the PB EMA."),
            "trend-template": ("Medium", "Mark Minervini's seven-point checklist: price above rising 50, 150 and 200-day averages, near its yearly high and well off its low. All seven must pass to get in.",
                               "Picking strong individual stocks. It's strict, so it spends a lot of time out, and Quiplee's exit rule (a close below the 50-day) is an assumption."),
            "stage-analysis": ("Slow", "Stan Weinstein's rule: own a stock only when its weekly close is above a 30-week average that is itself rising.",
                               "Spotting the long 'Stage 2' advances in individual stocks and avoiding long declines."),
            "ten-month-sma": ("Slowest", "Meb Faber's rule: on the last day of each month, hold if the price is above its 10-month average; otherwise sit in T-bills.",
                              "Limiting crash damage on whole markets with only one or two trades a year."),
            "time-series-momentum": ("Slowest", "From Moskowitz, Ooi and Pedersen: hold if the past 12 months' return beats cash; otherwise sit in T-bills. Checked monthly.",
                                     "Broad markets and asset classes. Very few trades, but slow to get back in after a sharp recovery."),
        }
        cards = ""
        rows = ""
        for s in TIMED:
            speed, what, good = plain[s["slug"]]
            th = THINKER[s["thinker"]]
            sw = [self.r(t["sym"], s["slug"])["stats"]["switches_per_year"] for t in TICKERS]
            sm = self.s.strat_summary(s)
            cards += (f'<div class="card prose rule-plain"><p class="eyebrow">{BAR_WORD[s["bar"]]} · {speed.lower()}</p>'
                      f'<h3 class="h3"><a href="{h("strategies/" + s["slug"] + "/")}">{s["long"]}</a></h3>'
                      f'<p class="muted small">From <a href="{h("thinkers/" + th["slug"] + "/")}">{th["name"]}</a></p>'
                      f'<p>{what}</p><p><b>Good for:</b> {good}</p></div>')
            rows += (f'<tr><td><a href="{h("strategies/" + s["slug"] + "/")}">{s["name"]}</a></td><td>{speed}</td>'
                     f'<td class="r">{np.median(sw):.1f}</td><td class="r">{sm["cut_dd"]} of {sm["n"]}</td><td class="r">{sm["beat_sharpe"]} of {sm["n"]}</td></tr>')
        body = f"""
<section class="prose">
<p>The seven rules fall into three families. <b>Band rules</b> (PB EMA, Bull Market Support Band, Ripster cloud) watch the space between two moving averages. <b>Checklist rules</b> (Trend Template, Stage Analysis) add conditions, such as the average itself rising. <b>Monthly rules</b> (10-month SMA, 12-month momentum) look only once a month, which makes them slow but cheap to run.</p>
</section>
<section><div class="sec-head"><h2 class="h2">At a glance</h2><p>Typical switches per year is the median across all {len(TICKERS)} stocks.</p></div>
<div class="tbl-wrap"><table class="tbl"><thead><tr><th>Rule</th><th>Speed</th><th class="r">Typical switches / yr</th><th class="r">Cut drawdown</th><th class="r">Beat B&amp;H on Sharpe</th></tr></thead><tbody>{rows}</tbody></table></div></section>
<section class="grid grid-3">{cards}</section>
<section class="card prose"><p class="eyebrow">Plus one benchmark</p><p><a href="{h('strategies/buy-and-hold/')}">Buy and hold</a>, the approach John Bogle championed: own the market and never sell. It's the yardstick every rule above is measured against.</p></section>
"""
        self.lesson_shell("the-seven-rules", body)

    # 6 ---------------------------------------------------------------------
    def signal_to_plan(self):
        depth = 2
        h = lambda x: self.s.href(depth, x)
        body = f"""
<section class="prose">
<p>Knowing what a rule says is one thing. Using it without hurting yourself is another. This lesson covers how people who use rules like these tend to set things up. It's general education, not advice for your situation.</p>
<h2 class="h2">Decide what the rule is for</h2>
<p>The history on Quiplee says trend rules are mainly a seatbelt: they tend to limit losses in big crashes and give up some growth the rest of the time. If that's the job you want done, a slow rule on a broad index fund fits. If you expect a rule to beat the market every year, the evidence says it won't.</p>
</section>
<section class="prose" id="core">
<h2 class="h2">Core and satellite</h2>
<p>Many investors split their money in two. A large <b>core</b> is simply held for the long run. A smaller <b>satellite</b>, say 20 to 40%, follows a rule. If the rule goes through a bad stretch of whipsaws, most of the money is unaffected; if a crash comes, the satellite steps aside.</p>
</section>
<section class="prose">
<h2 class="h2">Check on the close, act once</h2>
<p>Pick a rule and check it only when it checks: after the daily close, on Friday, or at month-end. Ignore intraday moves. Quiplee's next-move level tells you in advance what close would change the call, so you can set a price alert and stop watching the screen.</p>
</section>
<section class="prose" id="size">
<h2 class="h2">Position sizing</h2>
<p>How much goes into each holding matters more than which rule you use. A common habit is to cap any single stock at a small share of the portfolio, and to keep speculative names, like the micro caps on Quiplee, smaller still. A rule can't protect you from a company that drops 80% overnight on bad news.</p>
</section>
<section class="prose" id="tax">
<h2 class="h2">Taxes in Canada</h2>
<p>In a regular, non-registered account, every sale is a taxable event: a gain creates a capital gains bill, and a rule that switches ten times a year creates ten of them. Two Canadian accounts avoid this:</p>
<ul><li>A <b>TFSA</b> (Tax-Free Savings Account): growth and withdrawals are tax-free, so switching in and out has no tax cost.</li>
<li>An <b>RRSP</b> (Registered Retirement Savings Plan): contributions are deductible and growth isn't taxed until you withdraw, so trades inside it don't create a bill along the way.</li></ul>
<p>Watch the <b>superficial loss rule</b> in a regular account: if you sell at a loss and buy the same stock back within 30 days, before or after, the Canada Revenue Agency won't let you claim the loss yet. Fast rules that sell and re-buy can run into it. Check the details with an accountant.</p>
</section>
<section class="prose">
<h2 class="h2">Write it down</h2>
<p>Before you start, write the rule, the stock, the account and the amount on one line. Each time the call changes, note the date and price. A short log is what keeps you following the rule during the long stretches when it lags, which is exactly when most people give up.</p>
</section>
<section class="card prose"><p class="eyebrow">Try it</p><p>Pick one stock you follow. Open its <a href="{h('stocks/')}">stock page</a>, choose the slowest rule that's currently IN, and note its next-move level and check date. That's a complete plan in two numbers.</p></section>
"""
        self.lesson_shell("signal-to-plan", body)

    # 7 ---------------------------------------------------------------------
    def common_mistakes(self):
        depth = 2
        h = lambda x: self.s.href(depth, x)
        body = f"""
<section class="prose">
<ol class="mistakes">
<li><b>Picking the best-looking backtest.</b> With seven rules and {len(TICKERS)} stocks, some combinations will look amazing by luck. Look for rules that do reasonably well across many stocks, not one that did brilliantly on one.</li>
<li><b>Acting on intraday moves.</b> A stock dipping below its average at noon isn't a signal. Wait for the close the rule actually uses.</li>
<li><b>Forgetting costs and taxes.</b> A fast rule that switches 30 times a year can lose its whole edge to trading costs, and in a regular account it can create a pile of tax bills.</li>
<li><b>Quitting after a run of whipsaws.</b> Every trend rule has stretches of small losses. Dropping it then usually means missing the one big call that pays for them.</li>
<li><b>Treating a micro cap like an index.</b> Rules behave very differently on tiny companies: prices jump, trading is thin, and a single news story can wipe out half the value before any rule can react.</li>
<li><b>Confusing a good company with a good trend.</b> A rule doesn't know whether a business is good. It only knows whether the price is rising. Both can be true at once, or neither.</li>
<li><b>Expecting timing to beat buy-and-hold.</b> Across Quiplee's tests, most rules earned less than simply holding but lost less in crashes. Judge a rule by the job you hired it for.</li>
</ol>
</section>
<section class="card prose"><p class="eyebrow">Where next</p><p>Head back to the <a href="{h('')}">signal board</a> and sort it by "Rules in" to see which stocks most rules currently agree on. Keep <a href="{h('learn/glossary/')}">the glossary</a> open in another tab.</p></section>
"""
        self.lesson_shell("common-mistakes", body)

    # ------------------------------------------------------------- linking
    def href_for(self, depth, current):
        """Returns slug -> URL for a page at `depth`, `current` = lesson slug, 'glossary' or None."""
        def f(slug):
            g = BY_SLUG[slug]
            if g.get("lesson"):
                ls, _, anc = g["lesson"].partition("#")
                if ls == current:
                    return f"#{anc}"
                if current != "glossary":
                    return self.lesson_href(depth, ls, anc)
            if current == "glossary":
                return f"#{slug}"
            return self.s.href(depth, "learn/glossary/") + f"#{slug}"
        return f
