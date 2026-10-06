"""Plain-English hints for table column headers.

Every generated page passes through annotate() (from Site.add), which gives
each <th> whose text it recognises a data-hint attribute. assets/site.js shows
the hint in a small bubble on hover, keyboard focus or tap. Headers that
explain themselves (Title, Year, Author...) are left alone.
"""
import html
import re

from .content import FAMILIES

STORM = ("The storm test: how hard a market crash would likely hit it, scored out of 10 from its market swings, "
         "how it fell in past crashes, its debt and its recent run-up.")
SHARPE_BEAT = "On how many stocks the play earned more per unit of risk (a higher Sharpe ratio) than simply buying and holding."

HINTS = {
    # stocks and lists
    "Stock": "The company, fund or index. Click a name for its chart and every play's call.",
    "Group": "The sector or category the name belongs to.",
    "Price": "The latest closing price.",
    "Day": "Change from the previous day's close.",
    "1 year": "Price change over the last 12 months.",
    "vs 200-day": "How far the price sits above (+) or below (−) its average close of the last 200 trading days. Above usually means a long uptrend.",
    "Core plays in": "How many of the 20 core plays hold the stock right now.",
    "Core plays": "How many of the 20 core plays hold it right now.",
    "All plays": "How many of all the plays hold it right now.",
    "Plays in": "How many of the plays hold it right now.",
    "In now": "How many stocks the play holds right now.",
    "Analysts' target": "How far analysts' average 12-month price target sits above (+) or below (−) today's price. Needs 3 or more analysts.",
    "To analysts' target": "How far analysts' average 12-month price target sits above (+) or below (−) today's price.",
    "Average analyst target": "Analysts' average 12-month price target.",
    "Analysts": "How many analysts publish a price target for it.",
    "Light": "Start or Stop, summing up every play: Start when 60% or more hold it, Stop once that falls to 40% or less.",
    "Score": "0 to 100: half how many plays hold it, half how far analysts' target sits above the price. Higher means a stronger setup.",
    "Rank": "Its position on today's score ranking.",
    "Crash exposure": STORM,
    "Exposure": STORM,
    "Crash": STORM,
    "Why": "What drives its crash-exposure score: market swings, past crashes, debt or run-up.",
    "2-yr change": "Price change over the last two years. A big run-up has further to fall in a crash.",
    "2-yr run-up": "Price change over the last two years. A big run-up has further to fall in a crash.",
    "Beta": "How much it tends to move when the market moves 1%. Above 1 swings more than the market; below 1, less.",
    "Market": "The stock market or index.",
    "Level": "The index's latest closing level.",
    "Weight": "Its share of your list by value.",
    # plays
    "Play": "The trading rule. Click it for how it works and its record.",
    "Family": "The kind of rule: trend following, breakouts, momentum, mean reversion, volume or calendar.",
    "Call": "What the play says now: In (hold it) or Out (stay in cash).",
    "Since": "When the play last changed its call.",
    "Next move": "The closing price that would flip the play's call, and how far that is from today's price.",
    "Next check": "When the play next looks at the price: daily plays at every close, weekly and monthly plays at the end of the week or month.",
    "Checks": "How often the rule looks at the price: every close, every week or every month.",
    "Annual return": "Average yearly gain over the test period (compound annual growth rate).",
    "Worst drawdown": "The biggest fall from a high to a later low during the test. Smaller is easier to live with.",
    "Worst drawdown since 2005": "The biggest fall from a high to a later low since 2005.",
    "Sharpe": "Return per unit of risk: yearly return above cash divided by how much it swung. Higher is better; above 1 is strong.",
    "Calls right": "Share of the play's calls that turned out right: in before a rise, or out before a fall.",
    "Switches / yr": "How often the play changes its call in a typical year. More switching means more trading costs.",
    "Cut drawdown": "On how many stocks the play's worst fall was smaller than buying and holding.",
    "Beat B&H Sharpe": SHARPE_BEAT,
    "Beat on Sharpe": SHARPE_BEAT,
    "Beat B&H (Sharpe)": SHARPE_BEAT,
    "Beat buy & hold (Sharpe)": SHARPE_BEAT,
    "Beat on return": "On how many stocks the play made more money than simply buying and holding.",
    "Buy & hold": "Simply owning it the whole time: the benchmark every play is graded against.",
    "Time in": "Share of the time the play was holding the stock rather than sitting in cash.",
    "Plays": "How many plays are in this family.",
    "Backtests": "How many play-and-stock pairs were tested.",
    "Called": "The close where the play changed its call.",
    "Until": "When that call ended: the next time the play changed its mind.",
    "Result": "Whether the call was right: the price rose while the play was in, or fell while it was out.",
    # business numbers
    "Market cap": "What the whole company is worth on the stock market: share price times shares.",
    "Total equity": "What the company owns minus what it owes (its book value).",
    "Total debt": "All its borrowing: loans and bonds.",
    "Cash": "Cash and short-term investments on hand.",
    "P/E ratio": "Price divided by the last 12 months' earnings per share: how many years of today's profit the price pays for.",
    "P/E": "Price divided by earnings per share: how many years of today's profit the price pays for.",
    "Forward P/E": "Price divided by the next 12 months' expected earnings per share.",
    "Revenue (last 12 months)": "Total sales over the last four quarters.",
    "Revenue growth": "Change in sales versus a year earlier.",
    "Sales growth": "Change in sales versus a year earlier.",
    "Earnings growth": "Change in profit versus a year earlier.",
    "Profit margin": "Profit as a share of sales.",
    "Free cash flow": "Cash the business brought in after paying for equipment and upkeep.",
    "Interest cover": "Operating profit divided by interest owed. Below about 2 times, debt payments eat much of the profit.",
    "Return on equity": "Profit as a share of shareholders' equity: how well it earns on the owners' money.",
    "Debt to equity": "Total debt divided by shareholders' equity. Above 1 means more borrowed than owned.",
    "Debt / equity": "Total debt divided by shareholders' equity. Above 1 means more borrowed than owned.",
    "Net debt / EBITDA": "Debt minus cash, divided by a year's operating earnings: roughly how many years of earnings would pay the debt off.",
    "Debt points": "The debt part of the storm test, out of 3.",
    "Price to book": "Share price divided by book value per share.",
    "Consensus rating": "Analysts' average recommendation, from strong buy to sell.",
    "Dividend yield": "A year's dividends as a share of the price.",
    "Volatility (1 yr)": "How much the price swung over the last year, as a yearly standard deviation.",
    "Last close": "The latest closing price.",
    "20-day ATR": "Average true range: the typical daily price swing over the last 20 days.",
    "ATR as % of price": "The typical daily swing as a share of the price.",
    "A 3-ATR stop sits": "Where a stop-loss set three typical daily swings below the close would sit.",
    # market gauges
    "Gauge": "A market measure with a record of flashing before past crashes.",
    "Now": "Its latest reading.",
    "Status": "Calm, watch or warning, against the levels seen before past crashes.",
    "Reading": "What today's number means in plain English.",
    "Peak to low": "How far the market fell from its high to the bottom.",
    "Fall": "How far the market fell from its high to the bottom.",
    "Plays on Be The Puck": "The plays on this site that come from this source.",
}

RULES = [
    (re.compile(r"^(.+) moved$"), lambda m: f"How much {m.group(1)} itself rose or fell while that call stood, which is how the call is judged."),
    (re.compile(r"^Play, (5 yrs|since .+)$"), lambda m: f"The play's results over this period ({m.group(1)}), next to buying and holding."),
    (re.compile(r"^(2000|2007|2020|2022) top$"), lambda m: f"Where this gauge stood at the {m.group(1)} market peak."),
    (re.compile(r"^(2008 crash|Recovery 2009–19|COVID drop|2020–21 rally|2022 bear|Since Oct 2022)$"),
     lambda m: "How each family's plays did over this stretch of the market, against simply buying and holding the same stocks."),
]
FAMILY_DESC = {name: desc for _, name, desc in FAMILIES}
PAIR_PAGE = re.compile(r"^stocks/[^/]+/[^/]+/$")
PAIR_OVERRIDES = {"Price": "The closing price on the day of the call."}

_TH = re.compile(r"<th\b([^>]*)>(.*?)</th>", re.S)
_TAGS = re.compile(r"<[^>]+>")


def hint_for(text, path=""):
    if PAIR_PAGE.match(path) and text in PAIR_OVERRIDES:
        return PAIR_OVERRIDES[text]
    if text in HINTS:
        return HINTS[text]
    for rx, fn in RULES:
        m = rx.match(text)
        if m:
            return fn(m)
    for name, desc in FAMILY_DESC.items():
        if text.startswith(name):
            return desc
    return None


def annotate(page, path=""):
    if "<th" not in page:
        return page

    def sub(m):
        attrs, inner = m.group(1), m.group(2)
        if "data-hint=" in attrs:
            return m.group(0)
        text = re.sub(r"\s+", " ", html.unescape(_TAGS.sub("", inner))).strip()
        hint = hint_for(text, path) if text else None
        if not hint:
            return m.group(0)
        return f'<th{attrs} data-hint="{html.escape(hint, quote=True)}">{inner}</th>'

    return _TH.sub(sub, page)
