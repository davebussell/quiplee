"""Learn section: the course (13 lessons with quizzes), the glossary, and the
interactive practice pages (Call it, flashcards, play quiz) plus a reading list.

Lessons quote live numbers from the backtests (via the Site object), so the
examples stay current every time the site rebuilds. Interactive pages are
rendered by assets/learn.js from JSON embedded in each page; progress is kept
in the visitor's own browser.
"""
import json
import math

import numpy as np
import pandas as pd

from .content import (TICKERS, THINKERS, THINKER, PLAYS, PLAY, TIMED, BAR_WORD, FAMILIES, FAMILY, credit)
from .glossary import GLOSSARY, TOPICS, BY_SLUG
from . import ind

BASICS = [
    dict(slug="what-is-a-stock", title="What a stock is, and what sets its price", minutes=5, track="basics",
         summary="Shares, market cap and why a $2 stock can be a bigger company than a $400 one. Buy a slice of a real company."),
    dict(slug="how-prices-move", title="Bids, asks and why prices move", minutes=5, track="basics",
         summary="The order book behind every price. Place trades in a live book and watch the price move."),
    dict(slug="candlesticks", title="Reading candlesticks", minutes=6, track="basics",
         summary="Open, high, low and close in one shape. Build candles yourself, then read a real chart."),
    dict(slug="trends-tops-bottoms", title="Trends, tops and bottoms", minutes=7, track="basics",
         summary="Higher highs, lower lows, support, resistance and moving averages, on real charts you control."),
    dict(slug="valuation", title="What a stock is worth: earnings and P/E", minutes=7, track="basics",
         summary="Earnings per share, P/E, forward P/E and the other yardsticks, with real companies' numbers."),
    dict(slug="balance-sheet", title="Equity, debt and staying power", minutes=7, track="basics",
         summary="What a company owns and owes, and why debt decides who survives a downturn. Stress-test real companies."),
    dict(slug="evaluating-a-stock", title="A ten-minute check on any stock", minutes=6, track="basics",
         summary="Business, price, growth, debt, trend and crash risk in order, run live on any covered stock."),
    dict(slug="risk-and-sizing", title="Risk, volatility and position size", minutes=6, track="basics",
         summary="Volatility, beta, the maths of losses, and how to size a position from its exit."),
]
MARKETS_TRACK = [
    dict(slug="indexes", title="Indexes and the whole market", minutes=5, track="markets",
         summary="What the S&P 500, Nasdaq-100, Dow and TSX are, why the giants move them, and what concentration means."),
    dict(slug="bubbles", title="Bubbles, crashes and the warning signs", minutes=6, track="markets",
         summary="How manias run, which warning signs have a record, and why timing a top is so hard."),
    dict(slug="positioning", title="Staying invested, cash and buckets", minutes=7, track="markets",
         summary="What selling, holding and rebalancing did through real crashes, and how to build buckets."),
]
TRACKS = [("basics", "Stock basics", "Start here if you're new. What a stock is, how prices move, candlesticks, trends, valuation, balance sheets and risk."),
          ("plays", "The plays", "How the published trading rules work, family by family, and how to read their record."),
          ("markets", "Markets and risk", "Indexes, bubbles and crashes, and how to position for a fall you can't time.")]

PLAYS_TRACK = [
    dict(slug="reading-a-page", title="How to read a Be The Puck page", minutes=5,
         summary="What the IN/OUT call, the next move, the charts and the record on every page mean, using a live example."),
    dict(slug="moving-averages", title="Moving averages, explained", minutes=6,
         summary="The building block of most plays here: what a moving average is, simple versus exponential, and why they lag."),
    dict(slug="trend-following", title="Trend following: why it works and when it doesn't", minutes=6,
         summary="The idea behind the biggest family of plays, the research that supports it, and the price you pay for using it."),
    dict(slug="breakouts", title="Breakouts and channels", minutes=6,
         summary="Buying new highs: Donchian's four-week rule, the Turtles, Darvas boxes and the 52-week high."),
    dict(slug="volatility-and-stops", title="Volatility, ATR and trailing stops", minutes=6,
         summary="How plays measure a stock's normal wiggle, and how stops built on it decide when a trend is over."),
    dict(slug="momentum", title="Momentum: own what's rising", minutes=7,
         summary="Time-series versus cross-sectional momentum, relative strength, dual momentum, and the indicators built on rate of change."),
    dict(slug="oscillators", title="Oscillators and mean reversion", minutes=7,
         summary="RSI, stochastics and friends: what overbought and oversold really mean, and why dip-buying plays win often but small."),
    dict(slug="volume", title="Reading volume", minutes=4,
         summary="On-balance volume, Chaikin money flow and the Money Flow Index: using how much traded, not just the price."),
    dict(slug="calendar", title="Calendar effects", minutes=5,
         summary="Sell in May, the turn of the month and the Santa Claus rally: what the research found, and how to judge a pattern that might be luck."),
    dict(slug="reading-a-backtest", title="How to read a backtest", minutes=8,
         summary="Annual return, drawdown, volatility, Sharpe ratio and calls right, in plain English, plus the traps that make backtests look better than they are."),
    dict(slug="the-play-families", title="All the plays at a glance", minutes=6,
         summary="Every play on Be The Puck in one table: family, speed, and how often each one beat simply holding."),
    dict(slug="signal-to-plan", title="From signal to plan", minutes=6,
         summary="How people actually use plays like these with real money: core and satellite, position sizing, and taxes in Canada."),
    dict(slug="common-mistakes", title="Seven common mistakes", minutes=5,
         summary="The errors that turn a sensible play into a losing habit, and how to avoid them."),
]
for _l in PLAYS_TRACK:
    _l["track"] = "plays"
LESSONS = BASICS + PLAYS_TRACK + MARKETS_TRACK
LESSON = {l["slug"]: l for l in LESSONS}
TRACK_NAME = {k: n for k, n, _ in TRACKS}


def Q(q, a, c, why):
    return {"q": q, "a": a, "c": c, "why": why}


QUIZZES = {
    "reading-a-page": [
        Q("A play page says OUT. What is the play doing?", ["Holding the stock", "Sitting in cash earning T-bill interest", "Selling the stock short", "Waiting for the market to open"], 1,
          "OUT means the play has sold and holds cash, which Be The Puck credits with the T-bill rate. No play on Be The Puck ever sells short."),
        Q("The next-move box says 'Stays in unless a daily close lands below $100.' The stock dips to $98 at noon and closes at $101. What happens?", ["The play sells at noon", "Nothing: only the close counts, and it closed above $100", "The play sells the next morning", "The level resets"], 1,
          "Every play here only reads finished closes. An intraday dip below the level doesn't count."),
        Q("What does the green shading on a play's price chart show?", ["Days the stock went up", "Days the play was IN", "Days with high volume", "The play's profit"], 1,
          "Green shading marks the periods the play held the stock; red marks the periods it sat in T-bills."),
        Q("A trend play is right on only 38% of its calls. What's the most likely explanation if it still beat buy and hold?", ["The data is wrong", "Its right calls were much bigger than its wrong ones", "It traded less than buy and hold", "Calls right doesn't include costs"], 1,
          "Trend plays take many small losses and catch a few big moves. A low hit rate is normal for them."),
    ],
    "moving-averages": [
        Q("A stock closed at 10, 11, 12, 11 and 13. What is its 5-day simple moving average?", ["11.0", "11.4", "12.0", "13.0"], 1, "(10 + 11 + 12 + 11 + 13) ÷ 5 = 57 ÷ 5 = 11.4."),
        Q("How is an exponential moving average different from a simple one?", ["It uses more days", "It gives recent closes more weight, so it turns sooner", "It only uses weekly closes", "It ignores dividends"], 1,
          "An EMA weights recent prices more heavily, so it reacts faster than an SMA of the same length."),
        Q("Why do moving-average plays never sell at the exact top?", ["Because of trading costs", "Because averages are built from past prices and lag", "Because they only check monthly", "Because they use adjusted prices"], 1,
          "An average can only confirm a turn after it has happened. That lag is the price of filtering out noise."),
        Q("What happens in a band play when the price closes inside the band?", ["It sells", "It buys", "It keeps its last call", "It switches to a weekly check"], 2,
          "The band is a buffer. Inside it the play holds whatever it said last, which cuts out many false signals."),
    ],
    "trend-following": [
        Q("What single question does a trend follower ask?", ["Is the stock cheap?", "Is the price above or below its trend line?", "Will earnings beat estimates?", "Is the economy growing?"], 1,
          "Trend following reacts to price. It doesn't forecast or value anything."),
        Q("What is a whipsaw?", ["A sharp one-day crash", "Buying and selling repeatedly as price chops back and forth across the line, losing a little each time", "A very profitable trend", "A type of moving average"], 1,
          "In sideways markets, trend plays get whipsawed: in, out, in, out, each round trip costing a little."),
        Q("Across Be The Puck's tests, what do trend plays most often deliver compared with buy and hold?", ["Higher returns and lower drawdowns", "Smaller worst drawdowns but lower returns", "Higher returns and bigger drawdowns", "About the same on everything"], 1,
          "The typical pattern is crash protection paid for with lower growth in good years."),
        Q("Which researchers showed in 2012 that an asset's past 12-month return helped predict its next month across many markets?", ["Bouman and Jacobsen", "Moskowitz, Ooi and Pedersen", "George and Hwang", "Lakonishok and Smidt"], 1,
          "Their Time Series Momentum paper appeared in the Journal of Financial Economics in 2012."),
    ],
    "breakouts": [
        Q("Donchian's four-week rule buys when…", ["A close is above the highest high of the prior four weeks (20 trading days)", "The price rises 4% in a week", "The stock has four up weeks in a row", "The RSI rises above 70"], 0,
          "It's a channel breakout: a close above the prior 20-day high. A 4% rise off the low is Zweig's model, a different play."),
        Q("Turtle System 1 skips a 20-day breakout when…", ["Volume is light", "The previous breakout would have been a winning trade", "The stock is below its 200-day average", "It's the first breakout of the year"], 1,
          "The original rules ignore the next 20-day breakout after a would-be winner, and fall back to a 55-day breakout instead."),
        Q("What builds a Keltner channel in its modern form?", ["A 20-day EMA plus and minus a multiple of ATR", "A 20-day SMA plus and minus two standard deviations", "The highest high and lowest low of 20 days", "The 52-week high and low"], 0,
          "Keltner uses an average and ATR. The standard-deviation version is Bollinger Bands; the high/low version is a Donchian channel."),
        Q("George and Hwang (2004) found that stocks trading near their 52-week high…", ["Tended to fall back", "Tended to keep outperforming", "Had no pattern", "Only rose in January"], 1,
          "They argue traders anchor on the old high and under-react to good news, so prices near it keep catching up."),
        Q("Breakout plays often win under half their calls. How can they still make money?", ["Most failed breakouts are cut quickly for small losses, while a few run a long way", "They use leverage", "They buy only at the bottom", "They avoid all trading costs"], 0,
          "Small, quick losses plus occasional big trends is the classic breakout profile."),
    ],
    "volatility-and-stops": [
        Q("What does ATR measure?", ["The stock's average daily range, including gaps", "Its average return", "Its average volume", "How often it closes up"], 0,
          "Average True Range is a ruler for how much a stock normally moves in a day."),
        Q("Why set a stop in ATRs rather than a fixed dollar amount?", ["It's required by law", "So the stop adapts to how much each stock normally moves", "Because ATR never changes", "To trade more often"], 1,
          "A $2 move is noise for a $500 stock and a crash for a $5 stock. ATR scales the stop to each stock's normal movement."),
        Q("The Chandelier Exit hangs a stop…", ["3 ATRs below the highest high of the last 22 days", "2% below the entry", "At the 200-day average", "At yesterday's low"], 0,
          "Like a chandelier from the ceiling: it hangs a set number of ATRs below the recent high and rises as the high rises."),
        Q("What is the trade-off with a tight stop?", ["It lets trends run longer", "It cuts losses fast but gets shaken out by normal wiggles more often", "It removes all risk", "It only works on crypto"], 1,
          "Tight stops limit each loss but trigger more often; loose stops sit through noise but give back more."),
        Q("Bollinger Bands sit how far from their 20-day average?", ["Two ATRs", "Two standard deviations", "2%", "Two days"], 1,
          "John Bollinger's bands are two standard deviations above and below a 20-day simple average."),
    ],
    "momentum": [
        Q("Which question does time-series momentum ask?", ["Is this stock rising faster than other stocks?", "Has this asset's own recent return been positive or beaten cash?", "Is the stock cheap?", "Is volume rising?"], 1,
          "Time-series momentum compares an asset with its own past. Cross-sectional momentum compares stocks with each other."),
        Q("Jegadeesh and Titman's 1993 study bought…", ["Stocks that had done best over the previous 3 to 12 months", "The cheapest stocks", "Stocks with the highest dividends", "Stocks below their 200-day average"], 0,
          "They ranked stocks by past return and found recent winners kept outperforming recent losers in 1965–1989 U.S. data."),
        Q("Gary Antonacci's dual momentum combines…", ["Two moving averages", "Absolute momentum (beat T-bills) and relative momentum (beat the alternatives)", "Price and volume", "Two time frames of RSI"], 1,
          "Absolute momentum asks if the asset beat cash; relative momentum picks the stronger of the options."),
        Q("A stock's relative-strength line is rising. What does that tell you?", ["Its RSI is above 70", "It is beating the market", "Its volume is rising", "It pays a dividend"], 1,
          "Relative strength compares a stock with the market. It is not the RSI, despite the similar name."),
        Q("MACD above zero means…", ["The stock is up today", "The 12-day EMA is above the 26-day EMA", "RSI is above 50", "The stock beat SPY"], 1,
          "The MACD line is the 12-day EMA minus the 26-day EMA, so above zero means the fast average is on top."),
    ],
    "oscillators": [
        Q("An RSI reading of 75 means…", ["The stock must fall tomorrow", "Recent gains have been large relative to losses; the move looks stretched", "The stock is 75% above its average", "75% of days were up"], 1,
          "Overbought describes a stretched move, not a forecast. Strong trends can stay overbought for weeks."),
        Q("Why do Connors' dip-buying plays require price above the 200-day average?", ["To trade more often", "To buy dips only inside a longer uptrend, where they're more likely to bounce", "Because RSI only works above it", "To avoid dividends"], 1,
          "The trend filter keeps the play from buying dips in stocks that are breaking down."),
        Q("Compared with trend plays, mean-reversion plays usually have…", ["A lower hit rate and bigger wins", "A higher hit rate and smaller wins", "No losing trades", "Fewer trades"], 1,
          "Buying dips is right often but each gain is small, and an occasional loss can be large."),
        Q("What did Wilder, Lane and Appel each treat as a stronger signal than a simple threshold?", ["Divergence between price and the indicator", "Volume spikes", "Moving-average crossovers", "Calendar dates"], 0,
          "Each of them pointed to divergences, which are hard to test mechanically."),
        Q("A DeMark buy setup completes after…", ["Nine closes in a row below the close four days earlier", "Nine up days", "A 9% drop", "RSI below 9"], 0,
          "Nine consecutive closes below the close four bars earlier signal that the selling streak may be exhausted."),
    ],
    "volume": [
        Q("How is on-balance volume calculated?", ["Add the day's volume on up days and subtract it on down days, as a running total", "Average volume over 20 days", "Volume times price", "The highest volume of the year"], 0,
          "Granville's OBV is a running total that rises when volume comes on up days."),
        Q("Chaikin Money Flow counts a day as buying pressure when…", ["The close is near the day's high on heavy volume", "The stock gaps up", "Volume is below average", "The close is near the low"], 0,
          "Chaikin weights volume by where the close lands in the day's range."),
        Q("The Money Flow Index is best described as…", ["A volume-weighted RSI", "A moving average of volume", "A breakout channel", "A calendar effect"], 0,
          "Quong and Soudack built it in 1989 by adding volume to the RSI idea."),
        Q("Which of these is Be The Puck's own choice rather than Granville's?", ["Adding volume on up days", "Using a 20-day average of OBV as the signal line", "Subtracting volume on down days", "Calling it on-balance volume"], 1,
          "Granville read OBV's trend by eye. The 20-day signal line is Be The Puck's mechanical stand-in."),
    ],
    "calendar": [
        Q("The Halloween indicator holds stocks during which months?", ["May to October", "November to April", "January only", "The last week of each month"], 1,
          "Own stocks November through April, sit in T-bills May through October."),
        Q("The turn-of-the-month window studied by Lakonishok and Smidt covers…", ["The last trading day of a month and the first three of the next", "The whole first half of the month", "The 15th of each month", "The last week of the quarter"], 0,
          "Their 90-year study of the Dow pointed to a four-day window around the turn of each month."),
        Q("Why should you be wary of a calendar pattern found by testing many date windows?", ["Calendars change", "Search enough windows and some will look good by chance alone", "Holidays move", "It's illegal"], 1,
          "That's data mining. Patterns that held across many markets and long periods, before and after they were published, deserve more trust."),
        Q("What does Sy Harding's Seasonal Timing Strategy add to the best six months?", ["A volume filter", "MACD signals that can move the entry and exit dates", "A 200-day average", "Leverage"], 1,
          "He waited for MACD to confirm around October 16 and April 20 rather than switching on fixed dates."),
    ],
    "reading-a-backtest": [
        Q("A play made 9% a year. Buy and hold on the same stock made 11%. What's the fair conclusion?", ["The play is good", "The play lagged simply owning the stock", "Both are equal", "Need more data on costs"], 1,
          "Always compare with doing nothing. A play has to beat holding the same thing to be worth the effort."),
        Q("After a 50% loss, what gain do you need to get back to even?", ["50%", "75%", "100%", "150%"], 2, "Half of 10,000 is 5,000; doubling 5,000 (+100%) gets back to 10,000."),
        Q("What does the Sharpe ratio measure?", ["Return per unit of volatility, above cash", "The worst loss", "How often the play is right", "Trading costs"], 0,
          "It divides the return above T-bills by volatility: how much you were paid for each unit of bumpiness."),
        Q("Which trap comes from testing only stocks that still trade today?", ["Overfitting", "Survivorship bias", "Look-ahead bias", "Leverage"], 1,
          "Companies that went bust are missing from the data, which flatters every strategy, buy and hold included."),
    ],
    "the-play-families": [
        Q("Which family typically has the highest share of right calls but the smallest average win?", ["Trend following", "Breakouts", "Mean reversion", "Calendar"], 2,
          "Dip-buying plays are right often and take small profits."),
        Q("Which family ignores price entirely when deciding to be in or out?", ["Momentum", "Calendar", "Volume", "Breakouts"], 1,
          "Pure calendar plays like the Halloween indicator and the turn of the month only look at the date."),
        Q("Why are some plays labelled 'Be The Puck's choice' on parts of their rules?", ["To make them look better", "Their authors never specified that part, such as an exit for a buy-only signal", "Because the originals were illegal", "To speed up the site"], 1,
          "Where an author left a gap, Be The Puck fills it with a stated assumption so the play can be tested mechanically."),
    ],
    "signal-to-plan": [
        Q("In a core-and-satellite setup, which part follows a play?", ["The core", "The satellite", "Both equally", "Neither"], 1,
          "A smaller satellite follows the play; the larger core is simply held."),
        Q("In which Canadian account does switching in and out create no tax bill along the way?", ["A regular non-registered account", "A TFSA", "A margin account", "A joint account"], 1,
          "Growth and withdrawals in a TFSA are tax-free. An RRSP also defers tax until withdrawal."),
        Q("What does the superficial loss rule stop you doing?", ["Selling at a gain", "Claiming a loss if you buy the same stock back within 30 days before or after the sale", "Buying ETFs", "Using stop-losses"], 1,
          "Fast plays that sell and re-buy can run into it in a regular account."),
    ],
    "common-mistakes": [
        Q("With 100 plays and hundreds of stocks, why shouldn't you pick the single best-looking backtest?", ["It's too slow", "With thousands of combinations, some look great by luck", "The best one is always wrong", "Costs aren't included"], 1,
          "Look for plays that do reasonably well across many stocks rather than brilliantly on one."),
        Q("A play has had six small losing trades in a row. What does the history suggest about quitting now?", ["Quit immediately", "It often means missing the big call that pays for the small losses", "Double the position", "Switch to a faster play"], 1,
          "Every trend play has whipsaw stretches. Dropping it then usually means missing the trend that pays for them."),
        Q("Does a play's IN call say the company is a good business?", ["Yes", "No, it only says the price is behaving a certain way", "Only for big companies", "Only on monthly plays"], 1,
          "Plays read prices, not businesses."),
    ],
}


def fmt_pct(v, d=1):
    if v is None or (isinstance(v, float) and math.isnan(v)):
        return "–"
    s = f"{abs(v) * 100:,.{d}f}%"
    return ("−" + s) if v < 0 and round(abs(v) * 100, d) else (("+" + s) if v > 0 else s)


def jdump(x):
    return json.dumps(x, separators=(",", ":"), ensure_ascii=False).replace("</", "<\\/")


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
            parts.append(f'<a class="card lesson-nav next" href="{self.s.href(depth, "learn/call-it/")}"><span class="muted small">Now practise</span><b>Call it on real charts</b></a>')
        return f'<nav class="lesson-pager" aria-label="Lessons" data-lesson-end="{slug}">{"".join(parts)}</nav>'

    def quiz_block(self, slug):
        qs = QUIZZES.get(slug)
        if not qs:
            return ""
        return (f'<section class="card quiz" data-quiz="{slug}" aria-labelledby="quiz-{slug}"><p class="eyebrow">Check yourself</p>'
                f'<h2 class="h3" id="quiz-{slug}">{len(qs)} quick questions</h2>'
                f'<script type="application/json">{jdump(qs)}</script>'
                f'<noscript><p class="muted">Turn on JavaScript to take the quiz.</p></noscript><div class="quiz-body"></div></section>')

    def lesson_shell(self, slug, body_html, scripts=None):
        l = LESSON[slug]
        path, depth = f"learn/{slug}/", 2
        tr = [x for x in LESSONS if x["track"] == l["track"]]
        i = [x["slug"] for x in tr].index(slug) + 1
        tn = [k for k, _, _ in TRACKS].index(l["track"]) + 1
        h = lambda x: self.s.href(depth, x)
        body = f"""
<nav class="crumbs"><a href="{h('learn/')}">Learn</a><span>/</span><a href="{h('learn/')}#track-{l['track']}">Track {tn}: {TRACK_NAME[l['track']]}</a><span>/</span><span>Lesson {i} of {len(tr)}</span></nav>
<article class="lesson" data-lesson="{slug}">
<header class="pair-head"><p class="eyebrow">Track {tn} · Lesson {i} · {l['minutes']} min</p><h1 class="h1">{l['title']}</h1><p class="lede">{l['summary']}</p></header>
{body_html}
{self.quiz_block(slug)}
</article>
{self.nav_box(slug, depth)}
"""
        self.s.add(path, self.s.shell(path, l["title"], l["summary"], body, active="learn/", lesson=slug, scripts=scripts or ["assets/learn.js"]))

    def spy_table(self, family, cols="std"):
        depth = 2
        h = lambda x: self.s.href(depth, x)
        rows = ""
        for s in [p for p in TIMED if p["family"] == family]:
            x = self.r("SPY", s["slug"])
            a = x["stats"]["full"]["strat"] or {}
            rows += (f'<tr><td><a href="{h("stocks/spy/" + s["slug"] + "/")}">{s["name"]}</a><span class="sym-sub">{credit(s)}</span></td>'
                     f'<td>{BAR_WORD[s["bar"]].capitalize()}</td>'
                     f'<td class="r">{x["stats"]["switches_per_year"]:.1f}</td><td class="r">{fmt_pct(x["stats"]["invested"], 0).lstrip("+")}</td>'
                     f'<td class="r">{fmt_pct(a.get("cagr"))}</td><td class="r">{fmt_pct(a.get("maxdd"))}</td>'
                     f'<td class="r">{fmt_pct(x["batting"]["avg"], 0).lstrip("+") if x["batting"]["avg"] is not None else "–"}</td></tr>')
        b = self.full("SPY", "buy-and-hold", "bh")
        rows += (f'<tr><td><a href="{h("strategies/buy-and-hold/")}"><b>Buy &amp; hold</b></a><span class="sym-sub">benchmark</span></td><td>Never</td><td class="r">0</td><td class="r">100%</td>'
                 f'<td class="r">{fmt_pct(b.get("cagr"))}</td><td class="r">{fmt_pct(b.get("maxdd"))}</td><td class="r">–</td></tr>')
        return (f'<div class="tbl-wrap"><table class="tbl"><thead><tr><th>Play</th><th>Checks</th><th class="r">Switches / yr</th><th class="r">Time in</th>'
                f'<th class="r">Annual return</th><th class="r">Worst drawdown</th><th class="r">Calls right</th></tr></thead><tbody>{rows}</tbody></table></div>')

    def fam_stats(self, family):
        sms = [self.s.strat_summary(p) for p in TIMED if p["family"] == family]
        g = sum(m["graded"] for m in sms)
        calls = sum(m["calls"] for m in sms)
        right = sum((m["bat"] or 0) * m["calls"] for m in sms)
        return {"plays": len(sms), "graded": g, "beat_sharpe": sum(m["beat_sharpe"] for m in sms), "beat_cagr": sum(m["beat_cagr"] for m in sms),
                "cut_dd": sum(m["cut_dd"] for m in sms), "bat": right / calls if calls else None,
                "switches": float(np.median([m["switches"] for m in sms if m["switches"] is not None]))}

    def pair_chart(self, cid, sym, slug, title, note=None, panel=True):
        from .render import price_spec, panel_spec, chart_block, key_line, key_wash, ROLE_VAR
        t = next(x for x in TICKERS if x["sym"] == sym)
        x = self.r(sym, slug)
        s = PLAY[slug]
        keys = [key_line("--s-price", t["short"])] + [key_line(ROLE_VAR.get(role, "--s1"), lab) for lab, _, role in x["window"]["lines"]]
        keys += [key_wash("in", "Play in"), key_wash("out", "Play out")]
        out = chart_block(cid, price_spec(x, s, t), "".join(keys), title, note)
        ps = panel_spec(x, s, t) if panel else None
        if ps:
            pk = "".join(key_line(ROLE_VAR.get(sr["role"], "--s1"), sr["name"]) for sr in ps["series"])
            out += chart_block(cid + "-ind", ps, pk, ps["label"], small=True)
        return out

    # ------------------------------------------------------------- hub
    def hub(self):
        path, depth = "learn/", 1
        h = lambda x: self.s.href(depth, x)
        tracks = ""
        for tn, (tk, tname, tdesc) in enumerate(TRACKS, 1):
            ls = [l for l in LESSONS if l["track"] == tk]
            items = "".join(
                f'<li><a class="card lesson-card" data-lesson-link="{l["slug"]}" href="{h("learn/" + l["slug"] + "/")}"><span class="lesson-n">{i}</span>'
                f'<span class="lesson-txt"><b>{l["title"]}</b><span class="muted small">{l["summary"]}</span></span>'
                f'<span class="lesson-meta muted small nowrap"><span class="lesson-done" hidden>✓ Read</span><span class="lesson-score"></span><span>{l["minutes"]} min</span></span></a></li>'
                for i, l in enumerate(ls, 1))
            tracks += (f'<section class="track" id="track-{tk}"><div class="sec-head"><div><p class="eyebrow">Track {tn} · {len(ls)} lessons · about {sum(l["minutes"] for l in ls)} min</p>'
                       f'<h2 class="h2">{tname}</h2></div><p>{tdesc}</p></div><ol class="lesson-list">{items}</ol></section>')
        common = ["moving-average", "ema", "rsi", "atr", "breakout", "mean-reversion", "drawdown", "sharpe-ratio",
                  "buy-and-hold", "whipsaw", "relative-strength", "trailing-stop", "t-bills", "tfsa"]
        chips = "".join(f'<a href="{h("learn/glossary/")}#{c}">{BY_SLUG[c]["term"]}</a>' for c in common)
        total = sum(l["minutes"] for l in LESSONS)
        nq = sum(len(v) for v in QUIZZES.values())
        body = f"""
<section class="pair-head"><p class="eyebrow">Learn</p><h1 class="h1">From "what is a stock?" to reading the market</h1>
<p class="lede">{len(LESSONS)} short, hands-on lessons in three tracks, about {total} minutes in all. Start with how stocks work, move on to the {len(TIMED)} trading plays, then learn to read the whole market and plan for a crash. Every lesson uses real prices and real companies, and every technical word on the site links back to a plain-English definition.</p>
<div class="track-pills">{''.join(f'<a class="card track-pill" href="#track-{k}"><span class="eyebrow">Track {i}</span><b>{n}</b></a>' for i, (k, n, _) in enumerate(TRACKS, 1))}</div></section>
<section class="card progress" id="progress" hidden aria-live="polite"><p class="eyebrow">Your progress</p><div class="progress-grid"></div>
<p class="muted small">Saved in this browser only. <button type="button" class="linkish" id="progress-reset">Reset</button></p></section>
{tracks}
<p class="muted small">Each lesson ends with a short quiz ({nq} questions in all). Read them in order the first time.</p>
<section aria-labelledby="practice-h"><div class="sec-head"><h2 class="h2" id="practice-h">Practise</h2><p>Interactive, built from real prices, new questions every round.</p></div>
<div class="grid grid-3">
  <a class="card practice-card" href="{h('learn/call-it/')}"><span class="eyebrow">Practice</span><span class="name">Call it</span><span class="muted small">A real chart and a play's rule, stopped on a real day. Is the play IN or OUT? Then see what happened next.</span></a>
  <a class="card practice-card" href="{h('learn/flashcards/')}"><span class="eyebrow">Flashcards</span><span class="name">Plays, terms, analysts</span><span class="muted small">{len(TIMED)} plays, {len(GLOSSARY)} terms and every analyst. Mark what you know; the rest comes back.</span></a>
  <a class="card practice-card" href="{h('learn/play-quiz/')}"><span class="eyebrow">Quiz</span><span class="name">Who, what and how often?</span><span class="muted small">Ten questions a round on who's behind each play, what gets it in, and how often it checks.</span></a>
</div></section>

<section class="split">
<div class="card prose"><p class="eyebrow">The glossary</p><p class="h3">{len(GLOSSARY)} terms, each in a sentence or two</p>
<p>From "adjusted price" to "whipsaw". Hover over any underlined word on the site to see its definition without leaving the page; tap it on a phone.</p>
<p><a class="btn" href="{h('learn/glossary/')}">Open the glossary</a></p></div>
<div class="card prose"><p class="eyebrow">Reading list</p><p class="h3">The analysts' own books and papers</p>
<p>From Wilder's New Concepts (1978) to Clenow's Stocks on the Move (2015), with where to start.</p>
<p><a class="btn" href="{h('learn/reading-list/')}">See the reading list</a></p></div>
</section>
<section class="card prose"><p class="eyebrow">Words you'll see most</p><div class="chips">{chips}</div></section>
<section class="card prose"><p class="eyebrow">A note before you start</p>
<p>Be The Puck teaches how published trading plays work and how they have behaved. It doesn't know your goals, your taxes or what else you own, so nothing here is advice to buy or sell anything.</p></section>
"""
        self.s.add(path, self.s.shell(path, "Learn", f"{len(LESSONS)} short lessons, interactive practice on real charts, flashcards and a plain-English glossary for {len(TIMED)} trading plays.", body, active="learn/", scripts=["assets/learn.js"]))

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
<p class="lede">{len(GLOSSARY)} words and phrases you'll meet on Be The Puck, grouped by topic. Where a term gets a fuller explanation in a lesson, the entry links to it. Want to drill them? <a href="{h('learn/flashcards/')}?deck=terms">Flashcards</a>.</p></section>
<section class="gl-tools"><label for="gl-search" class="small muted">Find a term</label>
<input id="gl-search" type="search" placeholder="Try drawdown, RSI, TFSA…" autocomplete="off">
<div class="chips gl-topics">{nav}</div><p id="gl-empty" class="muted" hidden>No terms match. Try a shorter word.</p></section>
{secs}
"""
        self.s.add(path, self.s.shell(path, "Glossary", "Plain-English definitions of every trading, indicator, backtest and investing term used on Be The Puck.", body, active="learn/", glossary=True))

    # ------------------------------------------------------------- practice pages
    def call_it(self):
        path, depth = "learn/call-it/", 2
        h = lambda x: self.s.href(depth, x)
        fam_opts = "".join(f'<option value="{k}">{name}</option>' for k, name, _ in FAMILIES if k != "calendar")
        play_opts = "".join(f'<option value="{p["slug"]}">{p["name"]}</option>' for p in TIMED if not p.get("calendar"))
        body = f"""
<nav class="crumbs"><a href="{h('learn/')}">Learn</a><span>/</span><span>Call it</span></nav>
<section class="pair-head"><p class="eyebrow">Practice</p><h1 class="h1">Call it</h1>
<p class="lede">Each round shows a real chart, stopped on a real day, with one play's lines drawn on it and the play's rule beside it. Decide what the play said at the last close shown: IN or OUT. Then the rest of the chart appears, with what the stock did next.</p></section>
<section class="practice callit" id="callit" data-src="{h('data/practice.json')}" data-learn="{h('learn/')}" data-plays="{h('strategies/')}">
<div class="practice-bar">
<label class="small muted">Family<select id="ci-family"><option value="">All families</option>{fam_opts}</select></label>
<label class="small muted">Play<select id="ci-play"><option value="">Any play</option>{play_opts}</select></label>
<span class="ci-score muted small" aria-live="polite"></span></div>
<div class="ci-stage" aria-live="polite"><p class="muted">Loading charts…</p></div>
<noscript><p class="muted">Call it needs JavaScript.</p></noscript>
</section>
<section class="card prose"><p class="eyebrow">How to read the chart</p>
<p>The grey line is the price; the coloured lines are the play's own lines, such as its moving averages or channel. The dashed violet line marks the last close you're allowed to see. Panels below the price show the play's indicator, with its trigger levels dashed. If a play is holding its last call, look back to the last time the price was clearly on one side.</p>
<p>The answer is what the play's rule said at that close, not whether the stock went up afterwards. "What happened next" shows the outcome, so you can see how often a correct reading still loses money.</p></section>
"""
        self.s.add(path, self.s.shell(path, "Call it: practise reading the plays", "Practise reading trading plays on real charts: decide IN or OUT, then see what happened next.", body, active="learn/", scripts=["assets/learn.js"]))

    def flashcards(self):
        path, depth = "learn/flashcards/", 2
        h = lambda x: self.s.href(depth, x)
        plays = [{"id": p["slug"], "front": p["name"], "sub": f"{credit(p)} · {FAMILY[p['family']][0]} · {BAR_WORD[p['bar']]}",
                  "back": p["short"], "list": p["rules"], "href": h(f"strategies/{p['slug']}/")} for p in TIMED]
        terms = [{"id": g["slug"], "front": g["term"], "sub": dict(TOPICS)[g["topic"]], "back": g["tip"], "list": [],
                  "href": h("learn/glossary/") + "#" + g["slug"]} for g in GLOSSARY]
        analysts = [{"id": a["slug"], "front": a["name"], "sub": a["role"],
                     "back": a["argues"][0] if a["argues"] else a["bio"],
                     "list": [f"Play: {PLAY[x]['name']}" for x in a["strategies"]], "href": h(f"thinkers/{a['slug']}/")}
                    for a in THINKERS if a["strategies"] and not a.get("benchmark")]
        decks = {"plays": {"name": "Plays", "cards": plays}, "terms": {"name": "Terms", "cards": terms}, "analysts": {"name": "Analysts", "cards": analysts}}
        body = f"""
<nav class="crumbs"><a href="{h('learn/')}">Learn</a><span>/</span><span>Flashcards</span></nav>
<section class="pair-head"><p class="eyebrow">Flashcards</p><h1 class="h1">Learn the plays until they stick</h1>
<p class="lede">Read the front, say the answer to yourself, then flip. Mark the card "Got it" or "Still learning". Cards you're still learning come back sooner; known cards drop out of the deck.</p></section>
<section class="practice flash" id="flashcards">
<script type="application/json" id="flash-data">{jdump(decks)}</script>
<div class="practice-bar"><div class="seg" role="tablist" aria-label="Deck">
<button type="button" role="tab" data-deck="plays">Plays <span class="muted">{len(plays)}</span></button>
<button type="button" role="tab" data-deck="terms">Terms <span class="muted">{len(terms)}</span></button>
<button type="button" role="tab" data-deck="analysts">Analysts <span class="muted">{len(analysts)}</span></button></div>
<span class="fc-count muted small" aria-live="polite"></span></div>
<div class="fc-stage"><noscript><p class="muted">Flashcards need JavaScript. The same material is in the <a href="{h('strategies/')}">plays list</a> and the <a href="{h('learn/glossary/')}">glossary</a>.</p></noscript></div>
<p class="muted small">Keys: space or Enter flips, → or K for "Got it", ← or J for "Still learning".</p>
</section>
"""
        self.s.add(path, self.s.shell(path, "Flashcards: plays, terms and analysts", f"Flip through {len(TIMED)} trading plays, {len(GLOSSARY)} terms and the analysts behind them until they stick.", body, active="learn/", scripts=["assets/learn.js"], link=False))

    def play_quiz(self):
        path, depth = "learn/play-quiz/", 2
        h = lambda x: self.s.href(depth, x)
        from .practice import play_bank
        bank = play_bank()
        names = {a["slug"]: a["name"] for a in THINKERS}
        body = f"""
<nav class="crumbs"><a href="{h('learn/')}">Learn</a><span>/</span><span>Play quiz</span></nav>
<section class="pair-head"><p class="eyebrow">Quiz</p><h1 class="h1">Who, what and how often?</h1>
<p class="lede">Ten questions a round, drawn from all {len(TIMED)} plays: who's behind each one, what gets it in, which family it belongs to and how often it checks. Every answer links to the play so you can look closer.</p></section>
<section class="practice pq card" id="playquiz" data-plays="{h('strategies/')}">
<script type="application/json" id="pq-data">{jdump({"plays": bank, "families": [[k, n] for k, n, _ in FAMILIES], "analysts": names})}</script>
<div class="pq-stage" aria-live="polite"><noscript><p class="muted">The quiz needs JavaScript.</p></noscript></div>
</section>
"""
        self.s.add(path, self.s.shell(path, "Play quiz", "A ten-question quiz on the trading plays: who's behind them, what gets them in, their families and how often they check.", body, active="learn/", scripts=["assets/learn.js"], link=False))

    def reading_list(self):
        path, depth = "learn/reading-list/", 2
        h = lambda x: self.s.href(depth, x)
        start = [
            ("j-welles-wilder", "New Concepts in Technical Trading Systems", "The 1978 source of RSI, ATR, ADX and the Parabolic SAR. Dense, but it's where half of modern charting software comes from."),
            ("meb-faber", "The Ivy Portfolio", "A readable case for simple trend rules on whole asset classes, built around the 10-month average."),
            ("richard-dennis-william-eckhardt", "Way of the Turtle", "Curtis Faith's account of the Turtle experiment and its breakout rules, by one of the traders."),
            ("gary-antonacci", "Dual Momentum Investing", "The research behind absolute and relative momentum, written for individual investors."),
            ("stan-weinstein", "Stan Weinstein's Secrets for Profiting in Bull and Bear Markets", "The four stages, the 30-week average and relative strength, with hundreds of charts."),
            ("valeriy-zakamulin", "Market Timing with Moving Averages", "The careful skeptic's view: what moving-average timing has and hasn't done over 155 years."),
        ]
        picks = ""
        for slug, title, why in start:
            a = THINKER.get(slug)
            if not a:
                continue
            yr = next((b.get("year") for b in a.get("books", []) if b["title"].startswith(title.split(" (")[0][:20])), None)
            picks += (f'<div class="card prose book-pick"><p class="eyebrow">{"Start here" if slug == "meb-faber" else "Next"}</p><h3 class="h3">{title}{f" <span class=muted>({yr})</span>" if yr else ""}</h3>'
                      f'<p class="muted small">by <a href="{h("thinkers/" + slug + "/")}">{a["name"]}</a></p><p>{why}</p></div>')
        secs = ""
        for k, name, _ in FAMILIES:
            rows = ""
            for a in THINKERS:
                if not a["strategies"] or PLAY[a["strategies"][0]]["family"] != k or not a.get("books"):
                    continue
                for b in a["books"]:
                    rows += (f'<tr><td><b>{b["title"]}</b></td><td class="nowrap" data-v="{b.get("year") or ""}">{b.get("year") or "–"}</td>'
                             f'<td><a href="{h("thinkers/" + a["slug"] + "/")}">{a["name"]}</a></td>'
                             f'<td>{", ".join(PLAY[x]["name"] for x in a["strategies"])}</td></tr>')
            if rows:
                secs += (f'<section><h2 class="h2">{name}</h2><div class="tbl-wrap"><table class="tbl"><thead><tr><th>Title</th><th>Year</th><th>Author</th><th>Plays on Be The Puck</th></tr></thead>'
                         f'<tbody>{rows}</tbody></table></div></section>')
        other = ""
        for a in THINKERS:
            if (a.get("benchmark") or a.get("skeptic")) and a.get("books"):
                for b in a["books"]:
                    other += f'<tr><td><b>{b["title"]}</b></td><td data-v="{b.get("year") or ""}">{b.get("year") or "–"}</td><td><a href="{h("thinkers/" + a["slug"] + "/")}">{a["name"]}</a></td><td>{"The benchmark" if a.get("benchmark") else "The skeptic"}</td></tr>'
        if other:
            secs += (f'<section><h2 class="h2">The yardsticks</h2><div class="tbl-wrap"><table class="tbl"><thead><tr><th>Title</th><th>Year</th><th>Author</th><th>Role</th></tr></thead>'
                     f'<tbody>{other}</tbody></table></div></section>')
        body = f"""
<nav class="crumbs"><a href="{h('learn/')}">Learn</a><span>/</span><span>Reading list</span></nav>
<section class="pair-head"><p class="eyebrow">Reading list</p><h1 class="h1">Go to the source</h1>
<p class="lede">The books and papers behind the plays, as published by the analysts themselves. Years are first editions where they could be confirmed; a dash means the year couldn't be verified. Be The Puck isn't affiliated with any author or publisher.</p></section>
<section><h2 class="h2">Six to start with</h2><div class="grid grid-3">{picks}</div></section>
{secs}
"""
        self.s.add(path, self.s.shell(path, "Reading list", "The books and papers behind every trading play on Be The Puck, from Wilder and Donchian to Antonacci and Clenow, with six to start with.", body, active="learn/"))

    # ------------------------------------------------------------- lessons
    def build(self):
        self.hub()
        self.glossary()
        self.call_it()
        self.flashcards()
        self.play_quiz()
        self.reading_list()
        from .basics import Basics
        Basics(self).build()
        self.reading_a_page()
        self.moving_averages()
        self.trend_following()
        self.breakouts()
        self.volatility_and_stops()
        self.momentum()
        self.oscillators()
        self.volume()
        self.calendar()
        self.reading_a_backtest()
        self.play_families()
        self.signal_to_plan()
        self.common_mistakes()

    # 1 ---------------------------------------------------------------------
    def reading_a_page(self):
        depth = 2
        h = lambda x: self.s.href(depth, x)
        sym, slug = "SPY", "ten-month-sma"
        t = next(x for x in TICKERS if x["sym"] == sym)
        x = self.r(sym, slug)
        from .render import next_move, dlong
        nm = next_move(x, PLAY[slug], t)
        a, b = self.full(sym, slug), self.full(sym, slug, "bh")
        page = h(f"stocks/{t['slug']}/{slug}/")
        state = "IN" if x["state"] == 1 else "OUT"
        body = f"""
<section class="prose">
<p>Every page on Be The Puck that pairs a play with a stock answers three questions: what does the play say right now, what would make it change its mind, and how has it done in the past? This lesson walks through a real one: <a href="{page}">Meb Faber's 10-month moving average on the S&amp;P 500 ETF (SPY)</a>. Open it in another tab and follow along.</p>
</section>
<section class="prose" id="call">
<h2 class="h2">1. The call: IN or OUT</h2>
<p>The first box tells you the play's current position. <b>IN</b> means the play holds the stock. <b>OUT</b> means it has sold and is sitting in cash, which Be The Puck assumes earns the interest rate on US Treasury bills.</p>
<p>Right now the 10-month play on SPY is <b>{state}</b>, and has been since {dlong(x['since'])}. The line underneath shows how much SPY has moved since that call, so you can see whether the call has been working.</p>
</section>
<section class="prose" id="next-move">
<h2 class="h2">2. The next move</h2>
<p>The second box is the most useful thing on the page. It gives the closing price that would flip the play's call at its next check. For SPY it currently reads: <i>"{nm['headline']}"</i></p>
<p>Be The Puck finds that number by asking the play itself what it would say at a range of possible closes. If SPY closes beyond it on the check date, the play changes its call; if not, nothing happens. The percentage beside it tells you how far the price would have to move. A level 1% away means the call is fragile; one 15% away means it would take a big move.</p>
<p>Some plays can't flip on a single close: an RSI crossover might need the indicator to dip first, and a calendar play only cares about the date. The box says so instead of showing a level.</p>
<p>The box also tells you <b>when</b> the play next looks. This one only checks once a month, on the last trading day, so a dip below the line in the middle of the month doesn't count.</p>
</section>
<section class="prose" id="close">
<h2 class="h2">Why only closing prices count</h2>
<p>Prices jump around all day. A stock can dip below a moving average at 11 am and be back above it by 4 pm. If plays reacted to every intraday wiggle they would trade constantly and lose money on each round trip. So every play here waits for a <b>finished close</b>: the daily close at 4 pm New York time, Friday's close for weekly plays, or the last close of the month for monthly ones.</p>
</section>
<section class="prose">
<h2 class="h2">3. The price chart</h2>
<p>The first chart shows the last two years of prices with the play's lines drawn on top. The background is shaded green while the play was IN and red while it was OUT. Plays that use an indicator, such as the RSI, get a second, smaller chart underneath with the trigger levels dashed. Hover over a chart (or tap it on a phone) to see the values on any day.</p>
<h2 class="h2">4. Growth of 10,000</h2>
<p>The next chart starts both the play and buy-and-hold with 10,000 and shows how each would have grown since 2005, after trading costs. It uses a log scale so a 10% move looks the same size in 2008 as it does today. Here, the play turned out <b>{fmt_pct(a.get('total'), 0)}</b> overall, versus <b>{fmt_pct(b.get('total'), 0)}</b> for simply holding.</p>
<h2 class="h2">5. The record</h2>
<p>The table compares the play with buy-and-hold on the same dates, over the full test and the last five years. For SPY the 10-month play's worst fall was <b>{fmt_pct(a.get('maxdd'))}</b> against <b>{fmt_pct(b.get('maxdd'))}</b> for holding. That trade-off, smaller losses for less growth, is typical. Later lessons explain each number.</p>
<h2 class="h2">6. Every call, graded</h2>
<p>The last table lists the play's recent calls and marks each one right or wrong. An IN call is right if the price was higher by the time of the next call; an OUT call is right if it was lower. Don't be surprised by a low score. Trend plays are often wrong more than half the time and still do well, because their right calls tend to be much bigger than their wrong ones.</p>
</section>
<section class="card prose"><p class="eyebrow">Try it</p><p>Open <a href="{page}">the SPY page</a> and find the next-move level. Then open <a href="{h('stocks/' + t['slug'] + '/')}">SPY's stock page</a>, which shows every play's call on SPY side by side, grouped by family.</p></section>
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
<p>There are more exotic versions too. Alan Hull's average combines weighted averages to cut lag further; Perry Kaufman's adaptive average speeds up when the price moves cleanly and slows down in chop; Patrick Mulloy's triple EMA strips out most of the lag of an ordinary EMA. Each is a different answer to the same trade-off.</p>
<p>Neither is better. Faster averages give earlier signals and more false alarms. Slower ones give fewer, later signals. Many of the plays on Be The Puck are really a choice about where to sit on that trade-off.</p>
</section>
{chart}
<section class="prose" id="lag">
<h2 class="h2">Why they always lag</h2>
<p>An average is built from past prices, so it can only confirm a turn after it has happened. A 200-day average might take weeks to turn down after a peak. That lag is the cost of filtering out noise, and it's why trend plays never sell at the top or buy at the bottom. They aim to catch the middle of big moves.</p>
<p>Longer averages lag more. Some common lengths, roughly translated: a 10-month average is about the same as a 200-day one; a 30-week average is about 150 days; a 20-week average is about 100 days.</p>
</section>
<section class="prose" id="bands">
<h2 class="h2">Bands and clouds</h2>
<p>Some plays use two averages and shade the space between them, called a band or a cloud. The PB EMA uses two EMAs; Ben Cowen's bull market support band pairs a 20-week SMA with a 21-week EMA; Ripster's cloud uses the 34- and 50-day EMAs.</p>
<p>The band works like a buffer. Price above the whole band reads as an uptrend, below it as a downtrend. Price inside the band is undecided, so band plays hold their last call until price closes clearly on one side. That one choice cuts out a lot of false signals.</p>
</section>
<section class="prose" id="crossovers">
<h2 class="h2">Crossovers</h2>
<p>A crossover is the moment one line crosses another: the price crossing above its average, or a faster average crossing a slower one. The best-known is the golden cross, when the 50-day average rises above the 200-day, and its opposite, the death cross. Ed Seykota's teaching system is a crossover of two exponential averages, 15 and 150 days.</p>
</section>
<section class="card prose"><p class="eyebrow">Try it</p><p>Open any <a href="{h('strategies/pb-ema/')}">PB EMA</a> page and find the two EMA lines on the price chart. Then compare it with the slower <a href="{h('strategies/ten-month-sma/')}">10-month SMA</a> on the same stock and notice how many fewer times the shading changes colour.</p></section>
"""
        self.lesson_shell("moving-averages", body)

    # 3 ---------------------------------------------------------------------
    def trend_following(self):
        depth = 2
        h = lambda x: self.s.href(depth, x)
        fs = self.fam_stats("trend")
        body = f"""
<section class="prose" id="idea">
<h2 class="h2">The idea</h2>
<p>Trend following means owning something while its price is rising and stepping aside once it starts falling. It doesn't try to predict anything. It reacts. A trend follower doesn't ask "is this stock cheap?" or "will the economy slow down?" It asks one question: is the price above or below its trend line?</p>
<p>It's the biggest family on Be The Puck: {fs['plays']} plays, from Paul Tudor Jones's 200-day rule to the Ichimoku cloud. Breakout and momentum plays are close cousins. Mean-reversion and calendar plays work differently and get their own lessons.</p>
</section>
<section class="prose" id="why">
<h2 class="h2">Why it can work</h2>
<p>Prices tend to keep going in the direction they've been going, for a while. Researchers call this momentum. In 2012, Tobias Moskowitz, Yao Hua Ooi and Lasse Pedersen showed that an asset's return over the past year helped predict its return over the next month, across stocks, bonds, currencies and commodities, going back decades.</p>
<p>The usual explanations are human. News sinks in slowly, so prices adjust in steps rather than all at once. People pile into what's working and dump what isn't. And big investors take weeks to move money, which keeps a trend going.</p>
</section>
<section class="prose" id="fails">
<h2 class="h2">When it doesn't</h2>
<p>Trend following has two built-in weaknesses.</p>
<p><b>Whipsaws.</b> In a choppy, sideways market the price keeps crossing back and forth over the line. The play buys, sells a little lower, buys again a little higher, and loses a bit each time. Faster plays suffer most: on SPY, the daily PB EMA band switches about {self.r('SPY', 'pb-ema')['stats']['switches_per_year']:.0f} times a year, while the monthly 10-month play switches about {self.r('SPY', 'ten-month-sma')['stats']['switches_per_year']:.1f} times.</p>
<p><b>Lag.</b> The play always gets out after the top and back in after the bottom. When a market drops sharply and recovers quickly, as in early 2020, the play can sell near the low and buy back higher, missing both sides.</p>
<p>The result is that timing plays spend long stretches trailing buy-and-hold. Meb Faber's own ten-year review of his 10-month rule found it shone in the 2008 crash, then lagged stocks in six of the next eight years. Professor Valeriy Zakamulin, testing 155 years of US data, found the rules' advantage came mainly from a handful of severe bear markets.</p>
</section>
<section>
<div class="sec-head"><h2 class="h2">Every trend play on the S&amp;P 500</h2><p>On SPY since 2005, after trading costs. Click a column to sort.</p></div>
{self.spy_table("trend")}
</section>
<section class="prose">
<h2 class="h2">What it's really for</h2>
<p>Across all {fs['graded']:,} trend-play-and-stock pairs on Be The Puck, the play cut the worst drawdown in <b>{fs['cut_dd']:,}</b> cases but beat buy-and-hold's annual return in only <b>{fs['beat_cagr']:,}</b>. That's the honest summary: trend plays are mainly a way to limit how much you can lose in a crash, and you usually pay for it with lower growth in good years.</p>
</section>
<section class="card prose"><p class="eyebrow">Try it</p><p>Sort the table above by "Switches / yr", then by "Worst drawdown". Then read the <a href="{h('thinkers/valeriy-zakamulin/')}">skeptic's scoreboard</a> to see the same pattern across every play.</p></section>
"""
        self.lesson_shell("trend-following", body)

    # 4 ---------------------------------------------------------------------
    def breakouts(self):
        depth = 2
        h = lambda x: self.s.href(depth, x)
        fs = self.fam_stats("breakout")
        tf = self.fam_stats("trend")
        chart = self.pair_chart("bo-demo", "NVDA", "four-week-rule", "Nvidia with the four-week rule, last two years",
                                "The violet line is the highest high of the prior 20 days, the amber line the lowest low. A close above violet buys; a close below amber sells.")
        body = f"""
<section class="prose" id="breakout">
<h2 class="h2">What a breakout is</h2>
<p>A breakout is a close beyond the edge of a recent range: above the highest price of the last 20 days, say, or the last year. The idea is simple. A stock that escapes its range has found buyers willing to pay more than anyone has recently, and that is often how a new trend starts.</p>
<p>Breakout plays buy those new highs and then need a way out, because many breakouts fail and fall back. The exit is usually the opposite edge of a shorter channel, or a trailing stop.</p>
</section>
<section class="prose" id="channels">
<h2 class="h2">Channels</h2>
<p>A <b>channel</b> boxes the price in between two lines. The oldest is the <b>Donchian channel</b>: the highest high and lowest low of the last N days. Richard Donchian, who started one of the first public managed-futures funds in 1949, is credited with the "four-week rule": buy when price beats the highs of the last four weeks, sell when it breaks the lows.</p>
<p>Other channels measure distance from an average instead. A <b>Keltner channel</b> sits a couple of average true ranges (ATRs) above and below a 20-day EMA; Bollinger Bands sit two standard deviations away from a 20-day average. A close above the top line is the breakout.</p>
</section>
{chart}
<section class="prose" id="turtles">
<h2 class="h2">The Turtles</h2>
<p>In 1983, commodity traders Richard Dennis and William Eckhardt settled a bet about whether trading could be taught. They recruited about two dozen novices through newspaper ads, taught them a breakout system in two weeks and gave them money to trade. Their rules, published by former Turtles in 2003, had two versions:</p>
<ul><li><b>System 1:</b> buy a 20-day breakout and sell a 10-day low, but skip the next breakout if the last one would have been a winner (then wait for a 55-day breakout instead).</li>
<li><b>System 2:</b> buy every 55-day breakout and sell a 20-day low.</li></ul>
<p>Both used a stop two ATRs (the Turtles called it 2N) below the entry, sized every position by volatility and also sold short. Be The Puck tests one long position at a time.</p>
</section>
<section class="prose" id="highs">
<h2 class="h2">New highs: Darvas and the 52-week high</h2>
<p>Nicolas Darvas, a professional dancer, described in 1960 how he bought stocks breaking out of "boxes": a top that held for a few days, then a floor that held under it. When price broke the top, he bought; if it fell through the floor, he sold.</p>
<p>Academics found something similar. Thomas George and Chuan-Yang Hwang showed in 2004 that stocks trading close to their 52-week high tended to keep outperforming. Their explanation: traders anchor on the old high and hesitate to bid past it, so good news takes longer to show up in the price.</p>
</section>
<section class="prose" id="failed">
<h2 class="h2">Failed breakouts</h2>
<p>Most breakouts don't run. Across Be The Puck's tests, breakout plays were right on about {fmt_pct(fs['bat'], 0).lstrip('+')} of their calls, against {fmt_pct(tf['bat'], 0).lstrip('+')} for trend plays. They make it back because a failed breakout is usually cut quickly while a real one can run for months. Some traders even trade the failures: Linda Bradford Raschke's "Turtle Soup" setup, from her 1995 book with Larry Connors, bets against breakouts to new 20-day extremes that quickly reverse.</p>
</section>
<section>
<div class="sec-head"><h2 class="h2">Every breakout play on the S&amp;P 500</h2><p>On SPY since 2005, after trading costs.</p></div>
{self.spy_table("breakout")}
</section>
"""
        self.lesson_shell("breakouts", body)

    # 5 ---------------------------------------------------------------------
    def volatility_and_stops(self):
        depth = 2
        h = lambda x: self.s.href(depth, x)
        rows = ""
        if self.s.prices is not None:
            for sym in ["SPY", "AAPL", "NVDA", "TSLA", "BTC-USD", "OPTT"]:
                d = self.s.prices.get(sym)
                if d is None or len(d) < 60:
                    continue
                t = next(x for x in TICKERS if x["sym"] == sym)
                a = float(ind.atr(d, 20).iloc[-1])
                px = float(d["close"].iloc[-1])
                from .render import money
                rows += f'<tr><td><b>{t["short"]}</b><span class="sym-sub">{t["name"]}</span></td><td class="r">{money(px, t["cur"])}</td><td class="r">{money(a, t["cur"])}</td><td class="r">{fmt_pct(a / px).lstrip("+")}</td><td class="r">{fmt_pct(3 * a / px).lstrip("+")}</td></tr>'
        atr_tbl = (f'<div class="tbl-wrap"><table class="tbl"><thead><tr><th>Stock</th><th class="r">Last close</th><th class="r">20-day ATR</th><th class="r">ATR as % of price</th><th class="r">A 3-ATR stop sits</th></tr></thead><tbody>{rows}</tbody></table></div>') if rows else ""
        chart = self.pair_chart("ce-demo", "AAPL", "chandelier-exit", "Apple with the Chandelier Exit, last two years",
                                "The stop hangs three ATRs below the 22-day high. It rises with new highs and falls back only as the old high drops out of the window.")
        body = f"""
<section class="prose" id="atr">
<h2 class="h2">ATR: a ruler for normal movement</h2>
<p>A $5 move means nothing for a $700 index fund and everything for a $10 stock. To set sensible levels, plays need to know how much a stock normally moves. The standard ruler is J. Welles Wilder's <b>Average True Range</b> (ATR), from his 1978 book. The <b>true range</b> is the day's high minus its low, stretched to include any gap from the previous close; the ATR averages it over 14 or 20 days.</p>
</section>
<section><div class="sec-head"><h2 class="h2">How far a normal day goes</h2><p>Live, as of the latest close.</p></div>{atr_tbl}</section>
<section class="prose" id="stdev">
<h2 class="h2">Standard deviation and Bollinger Bands</h2>
<p>The other common ruler is the <b>standard deviation</b> of recent closes: how spread out they've been around their average. John Bollinger's bands sit two standard deviations above and below a 20-day average, so they widen when the market gets jumpy and squeeze together when it goes quiet. Bollinger's own view is that a close outside the bands usually means the move is continuing, and that a squeeze often comes before a big move.</p>
</section>
<section class="prose" id="trailing">
<h2 class="h2">Trailing stops</h2>
<p>A <b>trailing stop</b> is an exit level that follows the price up but never moves down. It turns "when does this trend end?" into a number. Several plays here are built around one:</p>
<ul>
<li><b>Chandelier Exit</b> (Chuck LeBeau): three ATRs below the highest high of the last 22 days, hanging from the top like a chandelier from the ceiling.</li>
<li><b>Supertrend</b>: a line three ATRs from the middle of each day's range that only ratchets in the trend's direction.</li>
<li><b>Parabolic SAR</b> (Wilder): starts loose, then tightens a little faster every time price makes a new high, so it gets out quickly once a trend stalls.</li>
<li><b>Clenow's trend model</b>: exits when the close falls three ATRs below the best close since entry.</li>
</ul>
</section>
{chart}
<section class="prose" id="tradeoff">
<h2 class="h2">Tight or loose?</h2>
<p>Every stop is a trade-off. A tight stop cuts each loss quickly but gets shaken out by ordinary wiggles, so you trade more and pay more costs. A loose stop sits through the noise and rides trends longer, but gives back more of each gain before it triggers. Setting stops in ATRs at least makes the trade-off the same for a quiet utility and a wild micro cap.</p>
</section>
"""
        self.lesson_shell("volatility-and-stops", body)

    # 6 ---------------------------------------------------------------------
    def momentum(self):
        depth = 2
        h = lambda x: self.s.href(depth, x)
        chart = self.pair_chart("dm-demo", "NVDA", "dual-momentum", "Nvidia with Dual Momentum, last two years",
                                "The panel shows the three 12-month returns the play compares each month-end: the stock, SPY and T-bills.")
        body = f"""
<section class="prose" id="time-series">
<h2 class="h2">Time-series momentum</h2>
<p>Momentum is the tendency of rising prices to keep rising for a while. The simplest way to use it is to compare an asset with its own past: has it gone up over the last year, or at least beaten cash? If yes, own it; if not, sit in T-bills. That is <b>time-series momentum</b>, the rule behind Moskowitz, Ooi and Pedersen's 2012 paper and Be The Puck's 12-month momentum play.</p>
</section>
<section class="prose" id="cross-sectional">
<h2 class="h2">Cross-sectional momentum</h2>
<p>The older academic version compares stocks with each other. Robert Levy tested it in 1967 by buying stocks trading well above their 27-week average. Narasimhan Jegadeesh and Sheridan Titman's 1993 paper is the classic: ranking U.S. stocks by their past 3 to 12 months' return, recent winners kept beating recent losers over 1965–1989. Later researchers usually skip the most recent month, because very short-term returns tend to reverse; that's the "12-1" measure.</p>
<p>Be The Puck tests one stock at a time, so it can't rank a whole market. Its versions either ask whether the stock's own momentum is positive, or compare it with SPY as a stand-in for the ranking.</p>
</section>
<section class="prose" id="relative-strength">
<h2 class="h2">Relative strength and dual momentum</h2>
<p><b>Relative strength</b> means beating the market. Divide a stock's price by the S&amp;P 500's and you get a line that rises when the stock is outperforming. Stan Weinstein reads it from Mansfield charts and wants it positive before buying. Robert Levy's 27-week ratio is another version.</p>
<p>Gary Antonacci combined the two kinds into <b>dual momentum</b>: an asset must beat T-bills (absolute momentum) and beat the alternatives (relative momentum). In his book he applies it to whole markets, U.S. versus international stocks, with bonds as the safe asset. Andreas Clenow measures momentum as the slope of a 90-day trend line, multiplied by how well the line fits, so smooth climbers score higher than jumpy ones.</p>
</section>
{chart}
<section class="prose" id="rate-of-change">
<h2 class="h2">Indicators built on rate of change</h2>
<p>A <b>rate of change</b> is just the percentage move over a set period. Several famous indicators smooth and combine them:</p>
<ul>
<li><b>MACD</b> (Gerald Appel): the 12-day EMA minus the 26-day EMA. Above zero, the fast average is on top; crossing its 9-day signal line is the most common signal.</li>
<li><b>KST</b> (Martin Pring): four smoothed rates of change over different look-backs, weighted and added together.</li>
<li><b>Coppock curve</b> (Edwin Coppock): a monthly blend of the 11- and 14-month rates of change, designed to spot the end of bear markets. Coppock reportedly took those periods from how long Episcopal bishops said mourning normally lasts.</li>
<li><b>CCI</b> (Donald Lambert): how far the price has run from its average, scaled so ±100 marks unusual moves.</li>
</ul>
</section>
<section class="prose" id="crashes">
<h2 class="h2">When momentum breaks</h2>
<p>Momentum's worst moments tend to come right after a bear market, when the beaten-down stocks rebound hardest and the recent leaders lag; Kent Daniel and Tobias Moskowitz documented these "momentum crashes" in 2016. Slow, monthly momentum plays are also late to get back in after a sharp V-shaped recovery.</p>
</section>
<section>
<div class="sec-head"><h2 class="h2">Every momentum play on the S&amp;P 500</h2><p>On SPY since 2005, after trading costs. On SPY itself the relative tests compare SPY with itself, so only their absolute parts matter.</p></div>
{self.spy_table("momentum")}
</section>
"""
        self.lesson_shell("momentum", body)

    # 7 ---------------------------------------------------------------------
    def oscillators(self):
        depth = 2
        h = lambda x: self.s.href(depth, x)
        fr = self.fam_stats("reversion")
        ft = self.fam_stats("trend")
        chart = self.pair_chart("rsi-demo", "SPY", "rsi-30-70", "SPY with the RSI 30/70 play, last two years",
                                "The play buys when the RSI climbs back above 30 and sells when it drops back below 70.")
        r2 = self.s.strat_summary(PLAY["rsi-2-pullback"])
        body = f"""
<section class="prose" id="oscillator">
<h2 class="h2">What an oscillator is</h2>
<p>An <b>oscillator</b> is an indicator that swings between fixed limits, usually 0 and 100. Instead of telling you which way the trend points, it tells you how stretched the latest move is. The famous ones:</p>
<ul>
<li><b>RSI</b> (J. Welles Wilder, 1978): compares the size of recent up days with recent down days. The standard look-back is 14 days.</li>
<li><b>Stochastic</b> (popularised by George Lane): where today's close sits in the last 14 days' high-low range. %K is the reading, %D its average.</li>
<li><b>Williams %R</b> (Larry Williams): the stochastic flipped upside down, from 0 at the top of the range to −100 at the bottom.</li>
<li><b>Money Flow Index</b>: an RSI that also weighs volume. More on that in the volume lesson.</li>
</ul>
</section>
<section class="prose" id="overbought">
<h2 class="h2">Overbought, oversold and divergence</h2>
<p>Readings near the top of the range are called <b>overbought</b> (RSI above 70) and near the bottom <b>oversold</b> (below 30). These words describe a stretched move, not a forecast. In a strong trend a stock can stay overbought for weeks while it keeps climbing.</p>
<p>Wilder, Lane and Appel all said their best signal was a <b>divergence</b>: price makes a new high but the indicator doesn't. Divergences are hard to define mechanically, so Be The Puck's versions use the simpler threshold crossings most traders know, and say so on each play page.</p>
</section>
{chart}
<section class="prose" id="mean-reversion">
<h2 class="h2">Mean reversion</h2>
<p>Mean reversion is the opposite bet to trend following: a price that has moved unusually far, unusually fast, tends to snap partway back. Mean-reversion plays buy sharp dips and sell the bounce, often within days.</p>
<p>Larry Connors and Cesar Alvarez added an important filter: only buy dips in stocks above their 200-day average, where the long trend is still up. Their RSI(2) play buys when a 2-day RSI drops below 10 and sells on the first close above the 5-day average; their Double 7s buys a close at a 7-day low and sells a 7-day high. In their tests, stop-losses hurt these short-term strategies, so the published rules don't use them.</p>
<p>The profile is very different from trend following. Across Be The Puck's tests, mean-reversion plays were right on about <b>{fmt_pct(fr['bat'], 0).lstrip('+')}</b> of their calls, against <b>{fmt_pct(ft['bat'], 0).lstrip('+')}</b> for trend plays. But each win is small, the plays sit in cash much of the time, and without a stop an unlucky entry can ride a long decline. The RSI(2) play switched a median of {r2['switches']:.0f} times a year per stock, so trading costs and taxes matter a lot.</p>
</section>
<section class="prose" id="exhaustion">
<h2 class="h2">Counting to exhaustion</h2>
<p>Tom DeMark's approach counts closes. Nine in a row below the close four days earlier completes a "buy setup", a sign the selling may be spent; nine above completes a sell setup. His full TD Sequential method goes on to a 13-bar countdown with more conditions. Be The Puck tests the popular nine-count shortcut and labels it that way.</p>
</section>
<section>
<div class="sec-head"><h2 class="h2">Every mean-reversion play on the S&amp;P 500</h2><p>On SPY since 2005, after trading costs. Look at "Time in" and "Calls right" together.</p></div>
{self.spy_table("reversion")}
</section>
"""
        self.lesson_shell("oscillators", body)

    # 8 ---------------------------------------------------------------------
    def volume(self):
        depth = 2
        h = lambda x: self.s.href(depth, x)
        chart = self.pair_chart("obv-demo", "AMD", "on-balance-volume", "AMD with the on-balance volume play, last two years",
                                "The play is in while on-balance volume (violet, lower panel) is above its 20-day average (amber).")
        body = f"""
<section class="prose" id="obv">
<h2 class="h2">On-balance volume</h2>
<p>Price tells you where a stock traded. <b>Volume</b> tells you how much traded there. Joseph Granville, a market-letter writer, argued in his 1963 book that volume moves before price: big money accumulates quietly before a rally and sells quietly before a fall.</p>
<p>His <b>on-balance volume</b> (OBV) is a running total. On an up day, add that day's volume; on a down day, subtract it. If OBV climbs while the price goes sideways, buyers may be accumulating. Granville read OBV's trend by eye. Be The Puck's mechanical version holds the stock while OBV is above its own 20-day average, and labels that signal line as its own choice.</p>
</section>
{chart}
<section class="prose" id="money-flow">
<h2 class="h2">Money flow</h2>
<p>OBV counts the whole day's volume as buying or selling based only on the close. Marc Chaikin refined that. His <b>Chaikin Money Flow</b> weighs each day's volume by where the close lands in the day's range: a close near the high counts mostly as buying, near the low mostly as selling. Above zero over 21 days means buying pressure; Be The Puck uses ±0.05 as a buffer against whipsaws, as StockCharts suggests.</p>
<p>Gene Quong and Avrum Soudack's <b>Money Flow Index</b> (1989) folds volume into Wilder's RSI, so a rally on heavy volume pushes it higher than the same rally on light volume. It reads like the RSI: 80 and 20 are the usual overbought and oversold lines.</p>
</section>
<section class="prose" id="limits">
<h2 class="h2">The limits of volume</h2>
<p>Volume is messier than price. It spikes on index rebalancing days and option expiries for reasons that have nothing to do with conviction, and crypto volume is spread across many exchanges. Volume plays also need daily data, so they're among the busier ones here.</p>
</section>
<section>
<div class="sec-head"><h2 class="h2">The volume plays on the S&amp;P 500</h2><p>On SPY since 2005, after trading costs.</p></div>
{self.spy_table("volume")}
</section>
"""
        self.lesson_shell("volume", body)

    # 9 ---------------------------------------------------------------------
    def calendar(self):
        depth = 2
        h = lambda x: self.s.href(depth, x)
        tom = self.r("SPY", "turn-of-the-month")["stats"]
        body = f"""
<section class="prose" id="halloween">
<h2 class="h2">Sell in May and go away</h2>
<p>The old saying has real research behind it. In 2002, Sven Bouman and Ben Jacobsen tested it in 37 stock markets and found returns from November to April beat May to October in 36 of them. They called it a puzzle, because no obvious risk explains it. Jacobsen later extended the test to more than a hundred markets and centuries of U.K. data and found the gap persisted.</p>
<p>The <b>Stock Trader's Almanac</b>, founded by Yale Hirsch in 1967, calls the same window the "Best Six Months" and has tracked it since 1986. The Almanac and newsletter writer Sy Harding each refined it with MACD signals, so the switch dates move a few weeks depending on momentum.</p>
</section>
<section class="prose" id="turn-of-month">
<h2 class="h2">The turn of the month</h2>
<p>Robert Ariel found in 1987 that U.S. stock gains were concentrated in the first half of each month, starting on the last trading day of the previous month. A year later, Josef Lakonishok and Seymour Smidt looked at 90 years of the Dow and narrowed it to a four-day window: the last trading day of a month and the first three of the next. One common explanation is money flowing in at month-end from paycheques and pension contributions.</p>
<p>Be The Puck's turn-of-the-month play holds SPY for just those four days a month, about {fmt_pct(tom['invested'], 0).lstrip('+')} of the time, and sits in T-bills otherwise.</p>
</section>
<section class="prose" id="santa">
<h2 class="h2">The Santa Claus rally</h2>
<p>Yale Hirsch defined it in 1972: the last five trading days of December and the first two of January. Seven days a year. It's a fun one to watch, but with so few days in the market it can't compound much.</p>
</section>
<section>
<div class="sec-head"><h2 class="h2">The calendar plays on the S&amp;P 500</h2><p>On SPY since 2005, after trading costs. "Time in" is the share of days in the market.</p></div>
{self.spy_table("calendar")}
</section>
<section class="prose" id="data-mining">
<h2 class="h2">Luck or law?</h2>
<p>Calendar effects are the easiest patterns to find by accident. There are thousands of possible windows (the third Tuesday, the week before a holiday, odd years after an election), and if you test enough of them some will look brilliant by chance. That's <b>data mining</b>.</p>
<p>Three questions help. Was the pattern found before the test period, or after? Does it show up across many markets, not just one? And has it held since it was published, when people could trade on it? The Halloween effect does reasonably well on all three; many newer calendar "rules" don't.</p>
</section>
"""
        self.lesson_shell("calendar", body)

    # 10 --------------------------------------------------------------------
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
                "label": "Drawdowns of SPY: 10-month play versus buy and hold",
                "series": [{"name": "10-month play", "role": "s1", "v": [sig5(v, 4) for v in dd_s.values]},
                           {"name": "Buy & hold", "role": "bench", "v": [sig5(v, 4) for v in dd_b.values]}]}
        chart = chart_block("dd-demo", spec, key_line("--s1", "10-month play") + key_line("--s-bench", "Buy & hold"),
                            "How far below its last peak, week by week (SPY)", "0% means at a new high. The lowest point of each line is its worst drawdown.")
        a, b = self.full("SPY", "ten-month-sma"), self.full("SPY", "ten-month-sma", "bh")
        bat = x["batting"]
        grow = 10000 * (1 + (b.get("cagr") or 0)) ** 20
        body = f"""
<section class="prose" id="what">
<h2 class="h2">What a backtest is</h2>
<p>A backtest runs a play on past prices to see what it would have done. Be The Puck runs every play on every stock from January 2005 (or the stock's first trading day), and plays fair: it only uses closing prices that were already known, acts on the next trading day, deducts a trading cost on every switch, and earns T-bill interest while the play is out.</p>
<p>A backtest tells you how a play behaved, not what it will do next. Treat it like a car's crash-test rating. It's useful, but the road ahead will be different.</p>
</section>
<section class="prose" id="benchmark">
<h2 class="h2">Always compare with doing nothing</h2>
<p>A play that made 9% a year sounds good until you learn the stock itself made 11%. That's why every number on Be The Puck sits next to buy-and-hold on the same stock over the same dates. A play has to beat simply owning the thing to be worth the effort.</p>
</section>
<section class="prose" id="return">
<h2 class="h2">Annual return and total return</h2>
<p><b>Total return</b> is the whole gain over the period, dividends included: +300% means 10,000 became 40,000. <b>Annual return</b> is the steady yearly rate that would produce the same result. It compounds, so small differences add up: at {fmt_pct(b.get('cagr'))} a year, buy-and-hold SPY's pace, 10,000 grows to about {grow:,.0f} over 20 years.</p>
</section>
<section class="prose" id="drawdown">
<h2 class="h2">Drawdown: the number that tells you how it felt</h2>
<p>A drawdown is how far an investment has fallen from its last high. The <b>worst drawdown</b> is the deepest one in the whole test. Buy-and-hold SPY's worst was <b>{fmt_pct(b.get('maxdd'))}</b>, in 2008–09. The 10-month play's worst was <b>{fmt_pct(a.get('maxdd'))}</b>.</p>
<p>Losses and gains aren't symmetrical. After a 50% fall you need a 100% gain just to get back to even. That's why limiting drawdowns matters more than it first appears.</p>
</section>
{chart}
<section class="prose" id="risk">
<h2 class="h2">Volatility and the Sharpe ratio</h2>
<p><b>Volatility</b> measures how much returns swing around from day to day, scaled to a year. SPY has run at about {fmt_pct(b.get('vol'), 0).lstrip('+')} a year since 2005; the 10-month play at about {fmt_pct(a.get('vol'), 0).lstrip('+')}, because it spends part of its time in cash.</p>
<p>The <b>Sharpe ratio</b> puts return and risk together: the return earned above cash, divided by volatility. Higher is better. A broad stock index usually scores around 0.4 to 0.6 over long periods, and anything consistently above 1 is rare. Here, buy-and-hold SPY scored {b.get('sharpe') or 0:.2f} and the 10-month play {a.get('sharpe') or 0:.2f}.</p>
</section>
<section class="prose" id="calls">
<h2 class="h2">Calls right</h2>
<p>Calls right is the share of finished calls that went the right way. The 10-month play on SPY was right on {bat['right']} of {bat['n']} calls ({fmt_pct(bat['avg'], 0).lstrip('+') if bat['avg'] is not None else '–'}). Trend plays are built to take many small losses and a few big wins, so one correct call that sidesteps a 40% crash can pay for a dozen small whipsaws. Mean-reversion plays are the opposite: high hit rates, small wins.</p>
</section>
<section class="prose">
<h2 class="h2">Switches, time invested and costs</h2>
<p><b>Switches per year</b> counts how often the play changes its mind; every switch costs money and, in a taxable account, can create a tax bill. <b>Time invested</b> is the share of days the play held the stock. Be The Puck's backtests deduct 0.05% per switch for stocks and ETFs, 0.10% for crypto and 0.30% for micro caps, whose buying and selling prices are far apart.</p>
</section>
<section class="prose" id="traps">
<h2 class="h2">Three traps that flatter backtests</h2>
<p><b>Overfitting.</b> Try enough settings and one will look brilliant by luck. That's why Be The Puck uses each analyst's published settings rather than picking the best-looking ones, and shows results for every stock, not just the winners.</p>
<p><b>In-sample results.</b> A play tuned on the same data it's tested on will look better than it really is. The fair test is out-of-sample: data the designer never saw. The "last 5 years" column on each page is a rough check, since most of these plays were published long before.</p>
<p><b>Survivorship bias.</b> Be The Puck tests stocks that still trade today. Companies that went bust aren't in the data, which makes every strategy, including buy-and-hold, look better than real life would have been.</p>
</section>
<section class="card prose"><p class="eyebrow">Try it</p><p>On <a href="{h('stocks/spy/ten-month-sma/')}">the SPY 10-month page</a>, compare the full-period and 5-year columns. Then try a fast play on a volatile stock, such as the <a href="{h('stocks/tsla/rsi-2-pullback/')}">RSI(2) pullback on Tesla</a>, and look at the switches and calls right.</p></section>
"""
        self.lesson_shell("reading-a-backtest", body)

    # 11 --------------------------------------------------------------------
    def play_families(self):
        from .render import n_people
        depth = 2
        h = lambda x: self.s.href(depth, x)
        tiles = ""
        for k, name, desc in FAMILIES:
            fs = self.fam_stats(k)
            tiles += (f'<div class="card tile"><span class="tile-label">{name} · {fs["plays"]} plays</span>'
                      f'<span class="tile-value">{fmt_pct(fs["cut_dd"] / fs["graded"] if fs["graded"] else None, 0).lstrip("+")}</span>'
                      f'<span class="tile-note">of pairs cut the worst drawdown; {fmt_pct(fs["beat_sharpe"] / fs["graded"] if fs["graded"] else None, 0).lstrip("+")} beat buy and hold on Sharpe. Calls right {fmt_pct(fs["bat"], 0).lstrip("+")}, median {fs["switches"]:.1f} switches a year.</span></div>')
        rows = ""
        for k, name, _ in FAMILIES:
            rows += f'<tr class="grp"><td colspan="6">{name}</td></tr>'
            for s in [p for p in TIMED if p["family"] == k]:
                sm = self.s.strat_summary(s)
                rows += (f'<tr><td><a href="{h("strategies/" + s["slug"] + "/")}">{s["name"]}</a><span class="sym-sub">{credit(s)}</span></td>'
                         f'<td>{BAR_WORD[s["bar"]].capitalize()}</td><td class="r">{sm["switches"]:.1f}</td>'
                         f'<td class="r">{fmt_pct(sm["bat"], 0).lstrip("+")}</td>'
                         f'<td class="r" data-v="{sm["cut_dd"] / max(1, sm["graded"])}">{sm["cut_dd"]} of {sm["graded"]}</td>'
                         f'<td class="r" data-v="{sm["beat_sharpe"] / max(1, sm["graded"])}">{sm["beat_sharpe"]} of {sm["graded"]}</td></tr>')
        body = f"""
<section class="prose">
<p>Be The Puck tests {len(TIMED)} plays from {n_people()} analysts, plus the golden cross, which has no single author. They fall into seven families that think about the market in different ways. Knowing the family tells you most of what to expect from a play before you look at its record.</p>
<ul>
<li><b>Trend following</b>: hold while price is above a line; sell when it breaks. Many small losses, a few big wins, good crash protection.</li>
<li><b>Breakouts &amp; channels</b>: buy new highs, sell on the opposite edge or a trailing stop. Similar profile, more trading.</li>
<li><b>Momentum</b>: own what has risen most, measured over months. Slow, few trades, late to turn.</li>
<li><b>Mean reversion</b>: buy dips, sell bounces. Right often, small wins, often in cash.</li>
<li><b>Volume &amp; money flow</b>: read buying and selling pressure from volume.</li>
<li><b>Candles &amp; chart patterns</b>: read a turn from a short pattern of bars, like an engulfing candle or a failed breakout. Short holds, often in cash.</li>
<li><b>Calendar</b>: in or out by date alone.</li>
</ul>
</section>
<section><div class="tiles">{tiles}</div></section>
<section><div class="sec-head"><h2 class="h2">Every play</h2><p>Medians and counts across all {len(TICKERS)} stocks, since 2005 or each stock's first full year. Click a column to sort; group headers hide while sorted.</p></div>
<div class="tbl-wrap"><table class="tbl"><thead><tr><th>Play</th><th>Checks</th><th class="r">Switches / yr</th><th class="r">Calls right</th><th class="r">Cut drawdown</th><th class="r">Beat B&amp;H Sharpe</th></tr></thead><tbody>{rows}</tbody></table></div></section>
<section class="prose">
<h2 class="h2">Gaps the authors left</h2>
<p>Many of these plays were published as ideas, screens or buy signals rather than complete systems. Coppock defined a buy but no sell; Minervini's template is a screen, not an exit; Granville read on-balance volume by eye. Where Be The Puck had to fill a gap to test a play mechanically, the play's page lists the choice under "How the play works", and the analyst's page links the original sources.</p>
</section>
"""
        self.lesson_shell("the-play-families", body)

    # 12 --------------------------------------------------------------------
    def signal_to_plan(self):
        depth = 2
        h = lambda x: self.s.href(depth, x)
        body = f"""
<section class="prose">
<p>Knowing what a play says is one thing. Using it without hurting yourself is another. This lesson covers how people who use plays like these tend to set things up. It's general education, not advice for your situation.</p>
<h2 class="h2">Decide what the play is for</h2>
<p>The history on Be The Puck says trend plays are mainly a seatbelt: they tend to limit losses in big crashes and give up some growth the rest of the time. Mean-reversion plays are a different tool: frequent small trades that need low costs and a tax-sheltered account. If you expect any play to beat the market every year, the evidence says it won't.</p>
</section>
<section class="prose" id="core">
<h2 class="h2">Core and satellite</h2>
<p>Many investors split their money in two. A large <b>core</b> is simply held for the long run. A smaller <b>satellite</b>, say 20 to 40%, follows a play. If the play goes through a bad stretch of whipsaws, most of the money is unaffected; if a crash comes, the satellite steps aside.</p>
</section>
<section class="prose">
<h2 class="h2">Check on the close, act once</h2>
<p>Pick a play and check it only when it checks: after the daily close, on Friday, or at month-end. Ignore intraday moves. Be The Puck's next-move level tells you in advance what close would change the call, so you can set a price alert and stop watching the screen.</p>
</section>
<section class="prose" id="size">
<h2 class="h2">Position sizing</h2>
<p>How much goes into each holding matters more than which play you use. A common habit is to cap any single stock at a small share of the portfolio, and to keep speculative names, like the micro caps on Be The Puck, smaller still. The Turtles sized every position by its ATR so that each one risked about the same amount. No play can protect you from a company that drops 80% overnight on bad news.</p>
</section>
<section class="prose" id="tax">
<h2 class="h2">Taxes in Canada</h2>
<p>In a regular, non-registered account, every sale is a taxable event: a gain creates a capital gains bill, and a play that switches ten times a year creates ten of them. Two Canadian accounts avoid this:</p>
<ul><li>A <b>TFSA</b> (Tax-Free Savings Account): growth and withdrawals are tax-free, so switching in and out has no tax cost.</li>
<li>An <b>RRSP</b> (Registered Retirement Savings Plan): contributions are deductible and growth isn't taxed until you withdraw, so trades inside it don't create a bill along the way.</li></ul>
<p>Watch the <b>superficial loss rule</b> in a regular account: if you sell at a loss and buy the same stock back within 30 days, before or after, the Canada Revenue Agency won't let you claim the loss yet. Fast plays that sell and re-buy can run into it. Check the details with an accountant.</p>
</section>
<section class="prose">
<h2 class="h2">Write it down</h2>
<p>Before you start, write the play, the stock, the account and the amount on one line. Each time the call changes, note the date and price. A short log is what keeps you following the play during the long stretches when it lags, which is exactly when most people give up.</p>
</section>
<section class="card prose"><p class="eyebrow">Try it</p><p>Pick one stock you follow. Open its <a href="{h('stocks/')}">stock page</a>, choose the slowest play that's currently IN, and note its next-move level and check date. That's a complete plan in two numbers.</p></section>
"""
        self.lesson_shell("signal-to-plan", body)

    # 13 --------------------------------------------------------------------
    def common_mistakes(self):
        depth = 2
        h = lambda x: self.s.href(depth, x)
        n_pairs = len(TICKERS) * len(TIMED)
        body = f"""
<section class="prose">
<ol class="mistakes">
<li><b>Picking the best-looking backtest.</b> With {len(TIMED)} plays and {len(TICKERS)} stocks there are {n_pairs:,} combinations, and some will look amazing by luck. Look for plays that do reasonably well across many stocks, not one that did brilliantly on one.</li>
<li><b>Acting on intraday moves.</b> A stock dipping below its average at noon isn't a signal. Wait for the close the play actually uses.</li>
<li><b>Forgetting costs and taxes.</b> A fast play that switches 30 times a year can lose its whole edge to trading costs, and in a regular account it can create a pile of tax bills.</li>
<li><b>Quitting after a run of whipsaws.</b> Every trend play has stretches of small losses. Dropping it then usually means missing the one big call that pays for them.</li>
<li><b>Treating a micro cap like an index.</b> Plays behave very differently on tiny companies: prices jump, trading is thin, and a single news story can wipe out half the value before any play can react.</li>
<li><b>Confusing a good company with a good trend.</b> A play doesn't know whether a business is good. It only knows whether the price is behaving a certain way. Both can be true at once, or neither.</li>
<li><b>Expecting timing to beat buy-and-hold.</b> Across Be The Puck's tests, most plays earned less than simply holding but lost less in crashes. Judge a play by the job you hired it for.</li>
</ol>
</section>
<section class="card prose"><p class="eyebrow">Where next</p><p>Put it into practice: <a href="{h('learn/call-it/')}">Call it</a> on real charts, drill the <a href="{h('learn/flashcards/')}">flashcards</a>, or head back to the <a href="{h('')}">signal board</a> and sort it by "All plays" to see which stocks most plays currently agree on.</p></section>
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


from .basics import QUIZZES as _BASIC_QUIZZES  # noqa: E402
QUIZZES.update(_BASIC_QUIZZES)
