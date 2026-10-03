"""Learn, Track 1 (stock basics) and Track 3 (markets and risk).

Each lesson is a sequence of short steps with a hands-on widget (assets/lab.js)
and a checkpoint question, then the usual end-of-lesson quiz. Widgets use real
numbers from Quiplee's data: prices, company fundamentals and crash exposure.
"""
import html
import json
import math

import pandas as pd

from .content import TICKERS, TIMED
from . import macro
from . import stockview as sv

e = html.escape


def _js(obj):
    return json.dumps(obj, separators=(",", ":"), allow_nan=False, ensure_ascii=False).replace("</", "<\\/")


def Q(q, a, c, why):
    return {"q": q, "a": a, "c": c, "why": why}


def num(v):
    return sv.num(v)


def check(q, opts, c, why):
    bs = "".join(f'<button type="button" class="quiz-opt ck-opt">{o}</button>' for o in opts)
    return (f'<div class="card check" data-c="{c}"><p class="eyebrow">Checkpoint</p><p class="ck-q">{q}</p>'
            f'<div class="quiz-opts">{bs}</div><p class="ck-why" hidden>{why}</p></div>')


def lab(name, data=None, title=None, note=None):
    sid = f"lab-{name}"
    head = f'<p class="eyebrow">Try it</p><p class="h3">{title}</p>' if title else '<p class="eyebrow">Try it</p>'
    return (f'<div class="card lab-card">{head}<div class="lab" data-lab="{name}"' + (f' data-src="{sid}"' if data is not None else "") + '></div>'
            + (f'<script type="application/json" id="{sid}">{_js(data)}</script>' if data is not None else "")
            + (f'<p class="chart-note">{note}</p>' if note else "") + "</div>")


def step(*parts):
    return '<section class="step">' + "".join(parts) + "</section>"


BLOCK = ("<ol", "<ul", "<p", "<div", "<table", "<h2", "<h3", "<section", "<figure")


def prose(*paras):
    return '<div class="prose">' + "".join(p if p.startswith(BLOCK) else f"<p>{p}</p>" for p in paras) + "</div>"


QUIZZES = {
    "what-is-a-stock": [
        Q("You buy one share of a company that has 2 billion shares. What do you own?", ["One two-billionth of the company", "A loan to the company", "The right to buy more shares later", "Nothing until you sell"], 0,
          "A share is a slice of ownership. One share out of two billion is one two-billionth of the business, its profits and its debts."),
        Q("Stock A is $10 a share, stock B is $400 a share. Which company is bigger?", ["A", "B", "You can't tell without the number of shares", "They are the same size"], 2,
          "Size is market cap: price times shares outstanding. A low share price can belong to a huge company and a high one to a small company."),
        Q("When you buy shares on an exchange, who usually gets your money?", ["The company", "Another investor who sold", "The exchange", "The government"], 1,
          "After the first sale (an IPO), shares trade between investors. The company only gets money when it issues new shares."),
        Q("Over many years, what matters most for a stock's price?", ["How many people talk about it", "What the company earns, and is expected to earn", "Its share price compared with other stocks", "The time of day you buy"], 1,
          "In the short run prices swing on news and mood. Over long periods they follow profits and what investors expect profits to be."),
    ],
    "how-prices-move": [
        Q("The best bid is $49.98 and the best ask is $50.02. You buy with a market order. What price do you pay?", ["$49.98", "$50.00", "$50.02, or more if the order is big", "The closing price"], 2,
          "A market buy takes the cheapest sellers waiting. If your order is bigger than what's offered at $50.02, the rest fills higher."),
        Q("Why can a stock jump on good news before many shares trade?", ["The exchange sets a new price", "Buyers raise their bids and sellers raise their asks at once", "The company buys its own shares", "It can't"], 1,
          "Prices move when people change what they are willing to pay or accept. A big gap can open with very little trading."),
        Q("What is a limit order?", ["An order that fills at any price", "An order that names the worst price you'll accept", "An order to sell everything", "An order limited to 100 shares"], 1,
          "A limit buy won't pay more than your price, and a limit sell won't take less. It may not fill at all."),
        Q("Why does it usually cost more to buy and sell a tiny company's stock than a big one's?", ["Higher taxes", "The gap between the bid and the ask is much wider", "They trade fewer days a year", "Exchange rules"], 1,
          "Few people trade tiny stocks, so the spread is wide and the order book is thin: you pay up to buy and take less to sell. That's why Quiplee's backtests assume 0.30% a trade for micro caps but 0.05% for big stocks."),
    ],
    "candlesticks": [
        Q("A candle's box runs from $10 to $12 and it is hollow (green). Where did the day open and close?", ["Opened $12, closed $10", "Opened $10, closed $12", "High $12, low $10", "You can't tell"], 1,
          "A hollow or green body means it closed above the open: here it opened at $10 and closed at $12."),
        Q("What do the thin lines above and below the box show?", ["Volume", "The day's high and low", "The moving average", "After-hours trading"], 1,
          "The wicks reach the highest and lowest prices of the period."),
        Q("A candle has a tiny body near the top and a long lower wick, after a fall. What is it called?", ["Shooting star", "Doji", "Hammer", "Marubozu"], 2,
          "A hammer: sellers pushed it down but buyers brought it back to close near the high."),
        Q("What does research say about trading candlestick patterns on their own?", ["They reliably predict the next day", "Studies such as one on Dow stocks found they don't make money by themselves", "They work only on crypto", "They only work in bull markets"], 1,
          "A 2006 study of Dow stocks found popular patterns had no value on their own. Candles are a way to read price, not a strategy."),
    ],
    "trends-tops-bottoms": [
        Q("Which pattern defines an uptrend?", ["Lower highs and lower lows", "Higher highs and higher lows", "Prices above $100", "Rising volume"], 1,
          "An uptrend keeps making higher swing highs and higher swing lows."),
        Q("A stock bounced off $80 three times this year. What do traders call $80?", ["Resistance", "Support", "A breakout", "The 200-day average"], 1,
          "Support is a level where buyers have repeatedly stepped in."),
        Q("Why do trend rules wait for confirmation instead of selling at the exact top?", ["They are badly designed", "Tops are only clear afterwards; waiting avoids selling on every dip", "Exchanges forbid it", "To pay less tax"], 1,
          "Nobody can see the top in real time. Waiting for a break costs some profit but avoids being shaken out by normal pullbacks."),
        Q("Making a moving average longer does what?", ["Makes it react faster", "Makes it smoother and slower, with fewer crossings", "Makes it more accurate", "Nothing"], 1,
          "A longer average smooths more noise and crosses less often, but reacts later to real turns."),
    ],
    "valuation": [
        Q("A stock is $60 and earned $3 a share last year. What is its P/E?", ["3", "20", "60", "180"], 1, "P/E = price ÷ earnings per share = 60 ÷ 3 = 20."),
        Q("Profit grows 20% but the P/E falls from 40 to 30. Roughly what happens to the price?", ["Up 20%", "Up 10%", "Down about 10%", "Unchanged"], 2,
          "Price = EPS × P/E. 1.2 × (30/40) = 0.9, so the price falls about 10% despite strong growth."),
        Q("Forward P/E is lower than trailing P/E. What does that usually mean?", ["Profits are expected to rise", "Profits are expected to fall", "The stock is falling", "The data is wrong"], 0,
          "Forward P/E divides by next year's expected profit. If that is bigger than last year's, the forward P/E is lower."),
        Q("Which measure suits a company that doesn't make a profit yet?", ["P/E", "Price to sales", "Dividend yield", "Earnings growth"], 1,
          "With no profit there is no meaningful P/E, so investors compare price with sales instead."),
    ],
    "balance-sheet": [
        Q("A company has $10B of assets and $12B of debts. What is its equity?", ["$22B", "$2B", "Negative $2B", "$10B"], 2,
          "Equity = assets − liabilities = 10 − 12 = −2. Negative equity means it owes more than it owns."),
        Q("Business worth $16B, with $12B of debt. If the business is marked down 20%, what happens to the stock?", ["Falls 20%", "Falls about 80%", "Rises", "Unchanged"], 1,
          "The business falls to $12.8B; debt still ranks first at $12B, leaving $0.8B for shareholders, down from $4B: an 80% fall."),
        Q("Interest cover is 1.5×. What does that mean?", ["Operating profit is 1.5 times the interest bill", "Debt is 1.5 times equity", "It has 1.5 years of cash", "It pays 1.5% interest"], 0,
          "Operating profit covers interest only 1.5 times; a modest fall in profit would make the interest hard to pay."),
        Q("In the Hertz story, what turned a 17% revenue fall into an 85% stock fall?", ["A fraud", "Debt that needed refinancing while lenders pulled back", "A product recall", "A stock split"], 1,
          "A falling business plus $6B of debt coming due when credit froze: debt magnified the hit."),
    ],
    "evaluating-a-stock": [
        Q("Which of these should you decide before buying, not after?", ["Where you would sell if you're wrong", "Whether the stock will go up", "Next quarter's earnings", "The CEO's salary"], 0,
          "Setting an exit in advance turns a hope into a plan. It is the one part you fully control."),
        Q("A stock is cheap on P/E but most trend plays are out and it carries heavy debt. What does that combination suggest?", ["A sure bargain", "Cheap for a reason: check why before buying", "It will double", "Nothing"], 1,
          "Low valuations often reflect real risks. Trend and balance-sheet checks help tell a bargain from a value trap."),
        Q("What does a strong consensus of trend plays tell you?", ["The stock is cheap", "The stock is in a broad uptrend now", "The stock can't fall", "Analysts like it"], 1,
          "It describes the trend today. It says nothing about value or how long the trend lasts."),
    ],
    "risk-and-sizing": [
        Q("You lose 50%. What gain gets you back to where you started?", ["50%", "75%", "100%", "150%"], 2, "Half of $100 is $50, and $50 must double (+100%) to get back to $100."),
        Q("Account $50,000, risking 1% per idea, buy at $40, exit at $36. How many shares?", ["125", "500", "1,250", "12,500"], 0,
          "1% of $50,000 is $500. The exit is $4 below the buy, so $500 ÷ $4 = 125 shares (a $5,000 position)."),
        Q("A stock with a beta of 2 typically…", ["Moves about twice as much as the market", "Pays twice the dividend", "Is twice as profitable", "Has half the risk"], 0, "Beta measures how much a stock tends to move with the market."),
        Q("You own five AI chip stocks. How diversified are you?", ["Very: five companies", "Less than it looks: they tend to fall together", "Fully", "It depends on the share prices"], 1,
          "Stocks tied to one theme are highly correlated. In a sell-off they behave like one big position."),
    ],
    "indexes": [
        Q("In a cap-weighted index like the S&P 500, which stocks move the index most?", ["The cheapest per share", "The biggest by market value", "All equally", "The newest"], 1,
          "Each company counts in proportion to its market value, so the giants dominate."),
        Q("The equal-weight S&P 500 lags the regular one for years. What does that suggest?", ["Most stocks are doing better than the giants", "A few giants are carrying the index", "The index is broken", "Interest rates are low"], 1,
          "When the average stock lags the cap-weighted index, the gains are concentrated in the largest companies."),
        Q("Can you buy the S&P 500 index itself?", ["Yes, directly", "No: you buy a fund or ETF that tracks it", "Only in the U.S.", "Only at month-end"], 1,
          "An index is a measurement. Index funds and ETFs such as SPY hold the stocks to track it."),
    ],
    "bubbles": [
        Q("Which stage of a mania comes right before the panic, in Kindleberger's sequence?", ["Displacement", "Boom", "Distress", "Revulsion"], 2,
          "Displacement, boom, euphoria, distress, then revulsion (the panic)."),
        Q("In Greenwood, Shleifer & You's study, how often did a 100% two-year industry run-up crash 40% or more within two years?", ["Almost never", "About half the time", "Always", "Only in 1929"], 1,
          "About half (21 of 40 U.S. episodes). Even then, prices rose for about six more months on average first."),
        Q("What is the inverted yield curve best at predicting?", ["Tomorrow's stock price", "Recessions, months ahead", "Crypto crashes", "Company earnings"], 1,
          "It came before every U.S. recession since 1969, typically 5 to 16 months ahead. It is not a crash timer."),
    ],
    "positioning": [
        Q("Why does selling to wait out a crash so often backfire?", ["Taxes", "The best days tend to come close to the worst ones", "Brokers charge more", "Prices never recover"], 1,
          "Many of the biggest up days came in bear markets, close to the worst days. Missing a handful cuts long-run returns sharply."),
        Q("What is the main job of the cash bucket?", ["To earn the most", "To pay near-term spending so you never sell stocks at the bottom", "To time the market", "To avoid taxes"], 1,
          "It covers the next year or two of withdrawals, so a crash doesn't force a sale."),
        Q("In 2022, why did a 60/40 portfolio fall more than usual?", ["Bonds fell along with stocks as rates rose", "Gold fell", "Cash lost money", "It didn't"], 0,
          "Rising rates pushed both stock and bond prices down, so bonds didn't cushion the fall as they usually do."),
    ],
}

class Basics:
    def __init__(self, learn):
        self.L = learn
        self.s = learn.s

    def h(self, depth=2):
        return lambda x: self.s.href(depth, x)

    def scripts(self):
        return ["assets/learn.js", "assets/widgets.js", "assets/lab.js"]

    def shell(self, slug, steps):
        body = "".join(steps) if isinstance(steps, (tuple, list)) else steps
        self.L.lesson_shell(slug, f'<div class="stepper" data-stepper="{slug}">{body}</div>', scripts=self.scripts())

    # -------------------------------------------------------------- data helpers
    def price(self, sym):
        x = self.s.R.get((sym, "buy-and-hold"))
        return x["price"] if x else None

    def co(self, sym):
        t = next((x for x in TICKERS if x["sym"] == sym), None)
        f = self.s.fund.get(sym)
        p = self.price(sym)
        if not t or not f or p is None:
            return None
        cur = sv.CUR_SIGN.get(f.get("currency"), t["cur"] or "$")
        return {"s": t["short"], "n": t["name"], "u": t["slug"], "p": round(p, 4), "cur": cur, "f": f, "t": t}

    def cos(self, syms):
        return [c for c in (self.co(s) for s in syms) if c]

    def series(self, syms, years=5):
        out = {}
        for sym in syms:
            d = (self.s.prices or {}).get(sym)
            t = next((x for x in TICKERS if x["sym"] == sym), None)
            if d is None or t is None:
                continue
            c = d["close"]
            c = c[c.index > c.index[-1] - pd.DateOffset(years=years)]
            t0 = c.index[0]
            out[t["short"]] = {"t0": t0.strftime("%Y-%m-%d"), "d": [int((x - t0).days) for x in c.index],
                               "c": [float(f"{v:.6g}") for v in c.values], "cur": t["cur"], "name": f"{t['name']}, {years} years"}
        return out

    # -------------------------------------------------------------- build
    def build(self):
        self.what_is_a_stock()
        self.how_prices_move()
        self.candlesticks()
        self.trends()
        self.valuation()
        self.balance_sheet()
        self.evaluating()
        self.risk_sizing()
        self.indexes()
        self.bubbles()
        self.positioning()

    # 1 --------------------------------------------------------------------------
    def what_is_a_stock(self):
        h = self.h()
        data = {"cos": [{"s": c["s"], "n": c["n"], "p": c["p"], "cur": c["cur"], "sh": num(c["f"].get("sharesOutstanding")), "eps": num(c["f"].get("trailingEps"))}
                        for c in self.cos(["NVDA", "AAPL", "SHOP.TO", "RY.TO", "JPM", "HTZ", "OPTT"]) if num(c["f"].get("sharesOutstanding"))]}
        steps = (
            step(prose("A <b>share</b> (or stock) is a slice of ownership in a company. If a company is cut into a billion shares and you own one, you own a billionth of the business: a billionth of its buildings, its cash, its profits and its debts.",
                       "Companies sell shares to raise money, the first time in an <b>initial public offering</b> (IPO). After that, shares trade between investors on an exchange such as the NYSE, Nasdaq or the Toronto Stock Exchange. When you buy a share, your money almost always goes to another investor, not to the company.")),
            step(prose("<b>Market cap</b> is the price of one share times the number of shares. It is what the market says the whole company is worth, and it is the only fair way to compare sizes. A $2 stock can belong to a bigger company than a $400 stock."),
                 lab("slice", data, "Buy a slice", "Real share prices and share counts from the latest close and company filings. Profit per share is the last 12 months.")),
            step(check("Company A trades at $10 with 1 billion shares. Company B trades at $500 with 10 million shares. Which is bigger?",
                       ["A, worth $10 billion", "B, because its shares cost more", "They are the same size"], 0,
                       "A is worth $10 × 1 billion = $10 billion; B is $500 × 10 million = $5 billion. Share price alone says nothing about size.")),
            step(prose("<b>What sets the price?</b> At any moment, the last trade: the price at which one buyer and one seller agreed. Over months and years, prices follow what the company earns and what investors expect it to earn. Over days, they move on news, mood and money flowing in or out.",
                       "A handy way to hold both ideas: <b>price = earnings per share × what investors will pay for each dollar of earnings</b> (the P/E ratio). Profits grow slowly; the P/E can swing fast. The <a href=\"" + h("learn/valuation/") + "\">valuation lesson</a> picks this up.")),
            step(prose("<b>What you get, and what you risk.</b> Shareholders earn money two ways: the price rising and dividends, the share of profits some companies pay out. They are also paid last. If a company fails, lenders and suppliers are paid first and shareholders often get nothing, so a stock can fall to zero. That is why debt matters so much, the subject of the <a href=\"" + h("learn/balance-sheet/") + "\">balance-sheet lesson</a>.")),
        )
        self.shell("what-is-a-stock", steps)

    # 2 --------------------------------------------------------------------------
    def how_prices_move(self):
        h = self.h()
        steps = (
            step(prose("Every stock exchange keeps an <b>order book</b>: a list of buyers waiting at the prices they will pay (<b>bids</b>) and sellers waiting at the prices they will accept (<b>asks</b>). The gap between the best bid and the best ask is the <b>spread</b>. A trade happens when someone accepts a price on the other side.")),
            step(lab("orderbook", None, "Move a price yourself", "A simplified book. Real ones change thousands of times a second.")),
            step(prose("Buying pushes prices up because a market buy takes the cheapest sellers first; once they're gone, the next seller wants more. Selling does the opposite. News moves prices even faster: everyone changes their bids and asks at once, so the price can gap before many shares trade."),
                 check("The best ask is $50.02 with 200 shares, the next is $50.04 with 500. You buy 400 at market. What happens?",
                       ["All 400 fill at $50.02", "200 fill at $50.02 and 200 at $50.04", "The order is rejected"], 1,
                       "A market order works through the book: 200 at the best ask, then the rest at the next price up.")),
            step(prose("<b>Market or limit?</b> A market order fills now at whatever the book offers. A limit order names your worst price and waits. Limits protect you in thinly traded stocks, where the spread can be wide; that's why Quiplee's backtests assume each trade in a micro cap costs 0.30%, against 0.05% for a big stock.",
                       "<b>Volume</b> is how many shares changed hands. Big moves on heavy volume mean many people acted on new information; the <a href=\"" + h("learn/volume/") + "\">volume lesson</a> covers plays built on it.")),
            step(prose("<b>Why plays read only the close.</b> Prices swing all day. The closing price is the one everybody agrees on, it sets the next day's starting point, and it is what most published rules use. A dip below a level at noon that recovers by 4pm doesn't count.")),
        )
        self.shell("how-prices-move", steps)

    # 3 --------------------------------------------------------------------------
    def candlesticks(self):
        h = self.h()
        meta = self.s.meta.get("NVDA")
        real = ""
        if meta and meta.get("ohlc") is not None:
            t = next(x for x in TICKERS if x["sym"] == "NVDA")
            real = sv.candles_block(t, meta, learn=h("learn/candlesticks/"), cid="cd-learn", title="Nvidia, day by day",
                                    note="Hover or tap any candle to read its open, high, low and close. Switch the range to 3M to see each candle clearly.", rng=63)
        steps = (
            step(prose("A <b>candlestick</b> squeezes a whole day of trading into one shape. It shows four prices: where the day <b>opened</b>, its <b>high</b>, its <b>low</b> and where it <b>closed</b>.",
                       "The thick <b>body</b> spans the open and the close. The thin <b>wicks</b> reach up to the high and down to the low. On Quiplee a hollow body means it closed above the open (an up day) and a filled body means it closed below (a down day). Many sites use green and red instead.")),
            step(lab("candle", None, "Build a candle", "Drag the four prices, or tap a preset. The name updates as you go.")),
            step(check("A candle opens at $20, rises to $25, falls to $19 and closes at $24. What does it look like?",
                       ["A hollow body from $20 to $24, wicks up to $25 and down to $19", "A filled body from $24 to $20", "No body at all"], 0,
                       "It closed above the open, so the body is hollow from $20 to $24; the wicks mark the $25 high and $19 low.")),
            step(prose("<b>Reading a few common shapes.</b> A long hollow body says buyers were in control all day. A <b>doji</b>, where open and close are nearly equal, says the day was a stalemate. A <b>hammer</b>, with a long lower wick, says sellers pushed it down but buyers pushed it back. A <b>shooting star</b> is the mirror image near a high.",
                       "A word of caution: a 2006 study of the 30 Dow stocks (Marshall, Young and Rose) found that popular candlestick patterns didn't make money on their own. Candles are a fast way to see what happened, not a signal by themselves. Context, such as where a candle sits in a trend, matters more.")),
            step(real, prose("Look for the biggest down day in the last three months, then for a doji. Notice how volume, the bars at the bottom, usually jumps on the big days.")),
            step(prose("<b>Timeframes.</b> The same idea works for any period: a weekly candle covers a week, a monthly candle a month. Quiplee's daily plays read daily closes, weekly plays the Friday close and monthly plays the last close of the month. Next: how to read the trend these candles make, in <a href=\"" + h("learn/trends-tops-bottoms/") + "\">trends, tops and bottoms</a>.")),
        )
        self.shell("candlesticks", steps)

    # 4 --------------------------------------------------------------------------
    def trends(self):
        h = self.h()
        ser = self.series(["SPY", "NVDA", "HTZ", "BTC-USD"], 5)
        data = {"series": ser, "def": "SPY"}
        steps = (
            step(prose("Prices zigzag. A <b>trend</b> is the direction of the zigzag. In an <b>uptrend</b> each swing high is higher than the last and each swing low is higher too: higher highs and higher lows. A <b>downtrend</b> makes lower highs and lower lows. When the swings go nowhere, the price is in a <b>range</b>.")),
            step(lab("swings", data, "Find the swings", "Swing points are marked where the price reversed by at least the swing size. HH = higher high, HL = higher low, LH = lower high, LL = lower low.")),
            step(prose("<b>Support and resistance.</b> Old swing lows often act as <b>support</b>, where buyers stepped in before. Old swing highs act as <b>resistance</b>, where sellers did. When price escapes a range, traders call it a <b>breakout</b>; the <a href=\"" + h("learn/breakouts/") + "\">breakouts lesson</a> covers the plays built on it."),
                 check("A stock has made swing highs of $50, $55 and $53, and swing lows of $40, $45 and $42. What is the latest pattern?",
                       ["Higher high and higher low: uptrend", "Lower high and lower low: the uptrend is in doubt", "A breakout"], 1,
                       "$53 is below $55 (a lower high) and $42 below $45 (a lower low). The uptrend has broken.")),
            step(prose("<b>Moving averages</b> smooth the zigzag into one line: the average close of the last N days. Price above a rising average is the simplest definition of an uptrend, and it's the core of many plays."),
                 lab("maplay", data, "Moving-average playground", "Shading marks days a simple rule would be in: in when the close is above the average, out when below. Before costs and with no interest while out.")),
            step(prose("<b>Tops and bottoms are only obvious afterwards.</b> In real time, every dip might be the start of a fall, and every bounce the start of a rally. That's why trend rules wait for confirmation, such as a close below the average, and accept selling below the top. The price of that patience is lag; the reward is not being shaken out by every pullback. Next in the plays track: <a href=\"" + h("learn/moving-averages/") + "\">moving averages, explained</a>.")),
        )
        self.shell("trends-tops-bottoms", steps)

    # 5 --------------------------------------------------------------------------
    def valuation(self):
        h = self.h()
        pool = ["NVDA", "AAPL", "MSFT", "GOOGL", "META", "AMZN", "JPM", "RY.TO", "XOM", "PFE", "LLY", "SHOP.TO", "HTZ", "TSLA"]
        cos = []
        for c in self.cos(pool):
            f = c["f"]
            eps, feps = num(f.get("trailingEps")), num(f.get("forwardEps"))
            if eps is None:
                continue
            pe = c["p"] / eps if eps > 0 else None
            fpe = c["p"] / feps if feps and feps > 0 else None
            cos.append({"s": c["s"], "n": c["n"], "p": c["p"], "cur": c["cur"], "eps": eps, "feps": feps, "pe": pe, "fpe": fpe})
        rows = ""
        for c in self.cos(pool):
            f = c["f"]
            pe, fpe, rg, m = num(f.get("trailingPE")), num(f.get("forwardPE")), num(f.get("revenueGrowth")), num(f.get("profitMargins"))
            rows += (f'<tr><td><a href="{h("stocks/" + c["t"]["slug"] + "/")}" class="sym">{e(c["s"])}</a><span class="sym-sub">{e(c["n"])}</span></td>'
                     f'<td class="r">{f"{pe:.0f}×" if pe and pe > 0 else "–"}</td><td class="r">{f"{fpe:.0f}×" if fpe and fpe > 0 else "–"}</td>'
                     f'<td class="r">{sv.pc(rg, sign=True) if rg is not None else "–"}</td><td class="r">{sv.pc(m) if m is not None else "–"}</td></tr>')
        table = (f'<div class="tbl-wrap"><table class="tbl"><thead><tr><th>Company</th><th class="r">P/E</th><th class="r">Forward P/E</th><th class="r">Sales growth</th><th class="r">Profit margin</th></tr></thead>'
                 f'<tbody>{rows}</tbody></table></div>')
        steps = (
            step(prose("Two numbers do most of the work in valuing a company. <b>Earnings per share</b> (EPS) is the company's profit divided by its number of shares: your share's slice of the profit. The <b>price-to-earnings ratio</b> (P/E) is the share price divided by EPS: how many years of today's profit you are paying for.",
                       "A P/E of 20 means a buyer pays $20 for each $1 of yearly profit. Investors pay more for companies they expect to grow fast or to be steady, and less for slow, risky or cyclical ones.")),
            step(lab("pe", {"cos": cos}, "The P/E explorer", "Starts from each company's real price and earnings. Move the sliders to see where the price could be in a year."),
                 prose("The lesson in that widget: <b>price = EPS × P/E</b>, so your return comes from profit growth plus any change in the P/E. When the P/E is already high, it has further to fall.")),
            step(check("Profit grows 10% and the P/E stays the same. What happens to the price?", ["Up about 10%", "Unchanged", "Up 20%"], 0,
                       "Price = EPS × P/E. If EPS rises 10% and P/E is unchanged, the price rises about 10%.")),
            step(prose("<b>Comparing companies.</b> P/E only makes sense next to growth and profitability. A bank growing slowly at 12× and a chipmaker growing fast at 35× can both be fairly priced. Here are real numbers from covered companies:"), table,
                 prose("<b>Forward P/E</b> uses analysts' estimate of next year's profit. If it's well below the trailing P/E, profits are expected to grow. For the whole market, the <b>CAPE</b> uses ten years of earnings to smooth out booms and busts; it's on the <a href=\"" + h("markets/") + "#g-cape\">Markets page</a>.")),
            step(prose("<b>Other yardsticks.</b> For companies without profits, <b>price to sales</b> compares the price with a year of revenue. For banks, <b>price to book</b> compares it with net assets. <b>Free cash flow</b>, the cash left after running and investing in the business, is harder to dress up than profit. <b>Dividend yield</b> is the yearly dividend as a share of the price.",
                       "<b>Analyst targets</b> are 12-month price forecasts from brokerage analysts. They are useful as a summary of opinion but lean optimistic, and they tend to follow the price rather than lead it. Every stock page shows them alongside these ratios.")),
        )
        self.shell("valuation", steps)

    # 6 --------------------------------------------------------------------------
    def balance_sheet(self):
        h = self.h()
        cos = []
        for c in self.cos(["HTZ", "CAR", "URI", "R", "TSLA", "NVDA", "AAPL", "XOM", "EIX", "PFE", "MSFT"]):
            f = c["f"]
            mcap = num(f.get("marketCap"))
            if not mcap:
                continue
            ie = num(f.get("interest_expense"))
            cos.append({"s": c["s"], "n": c["n"], "cur": c["cur"], "mcap": mcap, "debt": num(f.get("totalDebt")) or 0, "cash": num(f.get("totalCash")) or 0,
                        "ebit": num(f.get("ebit")), "interest": abs(ie) if ie else None, "equity": num(f.get("equity"))})
        steps = (
            step(prose("A <b>balance sheet</b> is a snapshot of what a company owns and owes. It always balances: <b>assets = liabilities + equity</b>. Assets are what it owns (cash, buildings, inventory, the cars in a rental fleet). Liabilities are what it owes (loans, bonds, bills). <b>Equity</b> is what's left for shareholders.",
                       "If debts exceed assets, equity is <b>negative</b>: on paper, shareholders own less than nothing. Hertz had negative equity in its latest filing.")),
            step(prose("<b>Why debt matters.</b> Borrowing lets a company grow faster, but interest must be paid in good years and bad, and loans must be repaid or refinanced when they come due. In a downturn, profits fall but the debt doesn't. Shareholders absorb the whole difference.")),
            step(lab("stress", {"cos": cos}, "Stress-test a company", "Real debt, cash, market value and operating profit from the latest filings. Banks are left out: borrowing is their business."),
                 prose("Try Hertz, then Nvidia. With heavy debt, a modest markdown of the business wipes out most of the stock. With net cash, the stock falls less than the business.")),
            step(check("A business is worth $10B and has $9B of debt. If the business is marked down 10%, roughly what happens to the stock?",
                       ["Falls 10%", "Falls about 100%", "Falls about 50%"], 1,
                       "The business falls to $9B, exactly the debt, leaving shareholders about nothing: from $1B to roughly zero.")),
            step(prose("<b>Four numbers to check.</b> <b>Debt to equity</b>: above about 1.5× is heavy. <b>Net debt to EBITDA</b>: years of operating cash earnings to pay off debt; above 4× is stretched. <b>Interest cover</b>: operating profit ÷ interest; under 2× is fragile. <b>Current ratio</b>: short-term assets ÷ short-term bills; under 1 means it relies on new money.",
                       "Every stock page shows these in its crash card, and <a href=\"" + h("articles/debt-and-crashes/") + "\">Debt decides who survives a crash</a> ranks every covered stock. For the full story of how debt turned a revenue dip into an 85% fall, read <a href=\"" + h("stories/the-hertz-lesson.html") + "\">the Hertz lesson</a>.")),
        )
        self.shell("balance-sheet", steps)

    # 7 --------------------------------------------------------------------------
    def evaluating(self):
        h = self.h()
        core = [p for p in TIMED if p.get("core")]
        cos = []
        for t in self.s.universe:
            if t.get("index") or t["crypto"] or t["group"] in ("Indexes & ETFs", "Sectors"):
                continue
            c = self.co(t["sym"])
            if not c:
                continue
            f = c["f"]
            meta = self.s.meta.get(t["sym"]) or {}
            rk = meta.get("risk") or {}
            cc = meta["ohlc"]["close"] if meta.get("ohlc") is not None else None
            ma = float(cc.iloc[-1] / cc.iloc[-200:].mean() - 1) if cc is not None and len(cc) >= 200 else None
            k, n = self.s.consensus(t, core)
            pe = num(f.get("trailingPE"))
            cos.append({"s": t["short"], "n": t["name"], "u": t["slug"], "p": c["p"], "cur": c["cur"], "mcap": num(f.get("marketCap")) or 0,
                        "ind": f.get("industry"), "pe": pe if pe and pe > 0 else None, "fpe": num(f.get("forwardPE")) if (num(f.get("forwardPE")) or 0) > 0 else None,
                        "rg": num(f.get("revenueGrowth")), "margin": num(f.get("profitMargins")), "de": rk.get("de"), "neg": bool(rk.get("neg_equity")),
                        "cover": rk.get("cover"), "ma": ma, "k": k, "n20": n, "risk": rk.get("level"), "why": (rk.get("why") or [None])[0],
                        "tgt": num(f.get("targetMeanPrice")) if (num(f.get("numberOfAnalystOpinions")) or 0) >= 3 else None,
                        "na": int(num(f.get("numberOfAnalystOpinions")) or 0)})
        data = {"cos": sorted(cos, key=lambda c: c["n"]), "def": "NVDA", "href": h("stocks/{u}/")}
        steps = (
            step(prose("You now have the pieces: what a company is, how its price is set, how to read its chart and trend, what it's worth and whether it can survive a bad year. This lesson puts them in order as a ten-minute check you can run on any stock before buying.")),
            step(prose("<ol><li><b>The business.</b> What does it sell, and how big is it?</li><li><b>The price.</b> P/E, forward P/E or price to sales, next to growth.</li>"
                       "<li><b>The engine.</b> Is revenue growing? Is it profitable?</li><li><b>The cushion.</b> Debt, interest cover and cash.</li>"
                       "<li><b>The trend.</b> Above or below its 200-day average? How many plays are in?</li><li><b>The storm test.</b> Its crash exposure.</li>"
                       "<li><b>Other opinions.</b> Analyst targets, held lightly.</li><li><b>Your plan.</b> Size, exit and what would change your mind.</li></ol>")),
            step(lab("scorecard", data, "Run the check on a real stock", "Every number is live from Quiplee's data. Colours are rough guides, not verdicts.")),
            step(check("A stock has a P/E of 12, falling sales, debt at 4× equity and most trend plays out. What's the most useful conclusion?",
                       ["It's a bargain", "It may be cheap for a reason; the risks need explaining before buying", "It will rebound soon"], 1,
                       "Cheap valuations often come with real problems. The other checks tell you whether the low price is an opportunity or a trap.")),
            step(prose("<b>The plan matters most.</b> Decide how much you'll put in, where you'd sell if you're wrong, and what would make you sell if you're right, before you buy. Every stock page lists the price at which each play would get out, which is one ready-made exit. The <a href=\"" + h("learn/risk-and-sizing/") + "\">next lesson</a> turns that exit into a position size. And when you're ready, put your own list in the <a href=\"" + h("watchlist/") + "\">watchlist</a>.")),
        )
        self.shell("evaluating-a-stock", steps)

    # 8 --------------------------------------------------------------------------
    def risk_sizing(self):
        h = self.h()
        rows = ""
        for sym in ["SPY", "TLT", "GLD", "AAPL", "JPM", "NVDA", "TSLA", "BTC-USD", "HTZ", "OPTT"]:
            t = next((x for x in TICKERS if x["sym"] == sym), None)
            rk = (self.s.meta.get(sym) or {}).get("risk") or {}
            if not t or rk.get("vol") is None:
                continue
            dd = (self.s.R.get((sym, "buy-and-hold")) or {}).get("stats", {}).get("full", {}).get("bh") or {}
            beta_txt = f"{rk['beta']:.2f}" if rk.get("beta") is not None else "–"
            rows += (f'<tr><td><a class="sym" href="{h("stocks/" + t["slug"] + "/")}">{e(t["short"])}</a><span class="sym-sub">{e(t["name"])}</span></td>'
                     f'<td class="r">{sv.pc(rk["vol"], 0)}</td><td class="r">{beta_txt}</td>'
                     f'<td class="r">{sv.pc(dd.get("maxdd"), 0)}</td></tr>')
        table = (f'<div class="tbl-wrap"><table class="tbl"><thead><tr><th>Name</th><th class="r">Volatility (1 yr)</th><th class="r">Beta</th><th class="r">Worst drawdown since 2005</th></tr></thead>'
                 f'<tbody>{rows}</tbody></table></div>')
        steps = (
            step(prose("Risk in investing has a simple meaning: how far and how fast you could lose money. Three numbers describe it. <b>Volatility</b> is how much a price typically swings in a year. <b>Beta</b> is how much it moves with the market. <b>Drawdown</b> is the fall from a peak to a low.")),
            step(table, prose("A stock with 60% volatility can easily halve in a bad year; one with 15% rarely does. Bitcoin and micro caps swing many times more than an index fund.")),
            step(lab("drawdown", None, "The maths of losses", "Losses and gains are not symmetrical."),
                 check("You lose 50%. What gain gets you back to even?", ["50%", "100%", "150%"], 1, "Half your money has to double, a 100% gain, to get back where you started.")),
            step(prose("<b>Position size</b> is how you control risk on any one idea. Start from the exit: decide the price at which you'd admit you're wrong, then choose how much of your account you're willing to lose if it hits. The size follows."),
                 lab("sizer", None, "Size a position", "The classic fixed-risk method: shares = money at risk ÷ distance to the exit.")),
            step(prose("<b>Diversification has limits.</b> Five stocks on the same theme (five chip makers, five banks) tend to fall together in a sell-off. Owning different kinds of businesses, and some bonds or cash, is what actually spreads risk. The <a href=\"" + h("markets/") + "\">Markets page</a> shows how much the whole market is leaning on a few giants right now.")),
        )
        self.shell("risk-and-sizing", steps)

    # 9 --------------------------------------------------------------------------
    def indexes(self):
        h = self.h()
        toy = []
        for sym in ["NVDA", "AAPL", "MSFT", "JPM", "XOM"]:
            f = self.s.fund.get(sym) or {}
            if num(f.get("marketCap")):
                toy.append({"s": sym, "cap": num(f.get("marketCap"))})
        idx = [t for t in TICKERS if t.get("index")]
        chips = "".join(f'<a href="{h("stocks/" + t["slug"] + "/")}">{e(t["short"])}</a>' for t in idx)
        M = self.s.macro or {}
        conc = next((g for g in M.get("gauges", []) if g["key"] == "concentration"), None)
        conc_txt = (f"Tonight the equal-weight S&amp;P 500 has {'lagged' if conc['value'] < 0 else 'beaten'} the regular index by {abs(conc['value']) * 100:.0f}% over three years." if conc else "")
        steps = (
            step(prose("An <b>index</b> is a scoreboard for a group of stocks. The <b>S&amp;P 500</b> tracks 500 large U.S. companies. The <b>Nasdaq-100</b> tracks the 100 largest non-financial companies on the Nasdaq, heavy in technology. The <b>Dow</b> tracks 30 big names, weighted by share price, an old quirk. The <b>Russell 2000</b> tracks small U.S. companies and the <b>TSX</b> Canada's market.",
                       "You can't buy an index directly. Index funds and ETFs, such as SPY or Canada's XIU, hold the stocks to match it closely and cheaply."),
                 f'<div class="chips">{chips}</div>'),
            step(prose("Most indexes are <b>cap-weighted</b>: each company counts in proportion to its market value. So the biggest companies move the index most."),
                 lab("indextoy", {"cos": toy}, "Build a tiny index", "Five real companies at their real market values.")),
            step(check("In a cap-weighted index, the largest company rises 20% and the other four fall 5% each. What can happen?",
                       ["The index can still rise", "The index must fall", "The index is unchanged"], 0,
                       "If the giant's weight is big enough, its 20% rise outweighs the smaller companies' falls.")),
            step(prose("<b>Concentration.</b> When a few giants carry an index, it is less diversified than its name suggests. The top ten stocks were about 38% of the S&amp;P 500 in mid-2026, against about 27% at the 2000 peak. " + conc_txt,
                       "Quiplee runs every play on the indexes too, and tracks concentration, valuation and seven other gauges on the <a href=\"" + h("markets/") + "\">Markets page</a>.")),
        )
        self.shell("indexes", steps)

    # 10 -------------------------------------------------------------------------
    def bubbles(self):
        h = self.h()
        M = self.s.macro or {}
        ndx = next((g for g in M.get("gauges", []) if g["key"] == "runup"), None)
        steps = (
            step(prose("A <b>bubble</b> is when prices rise far beyond what the underlying businesses can justify, driven by the expectation that prices will keep rising. A <b>crash</b> is a sudden, deep fall, often 30% or more. Not every crash follows a bubble (COVID didn't), and not every boom is a bubble.")),
            step(prose("The economist Charles Kindleberger, building on Hyman Minsky, found the same five stages in centuries of manias: <b>displacement</b> (a new technology or policy), <b>boom</b> (prices rise, credit grows), <b>euphoria</b> (rising prices become the reason to buy), <b>distress</b> (insiders sell, money tightens) and <b>revulsion</b> (the panic)."),
                 check("Prices keep rising, new investors pile in because prices are rising, and borrowing to buy hits records. Which stage is that?", ["Displacement", "Euphoria", "Revulsion"], 1,
                       "When rising prices themselves become the reason to buy, and borrowing grows, that's euphoria.")),
            step(prose("<b>Warning signs with a record.</b> High valuations (CAPE) came before poor decades, but not on a schedule. An inverted yield curve came before every U.S. recession since 1969. Widening credit spreads led downturns. Big run-ups raised crash odds: in Greenwood, Shleifer and You's study, industries up 100% in two years crashed about half the time." +
                       (f" The Nasdaq-100's two-year gain is {ndx['value'] * 100:.0f}% tonight." if ndx else ""),
                       "<b>Why timing is still hard:</b> those same run-ups kept rising for about six months on average before they peaked. Robert Shiller warned in 1996; prices doubled first.")),
            step(prose("The full history, from 1929 to 2022, is in <a href=\"" + h("articles/bubbles-and-crashes/") + "\">A century of bubbles and crashes</a>. How today's market reads is in <a href=\"" + h("articles/is-this-a-bubble/") + "\">Is this a bubble?</a> and live on the <a href=\"" + h("markets/") + "\">Markets page</a>.")),
        )
        self.shell("bubbles", steps)

    # 11 -------------------------------------------------------------------------
    def positioning(self):
        h = self.h()
        from .markets import sim_block
        B = macro.best_days()
        sim = sim_block("sim-learn").replace("{rule}", h("strategies/ten-month-sma/"))
        steps = (
            step(prose(f"When markets look stretched, the instinct is to get out. But getting out is two decisions: when to sell and when to buy back. From 2005, $10,000 in the S&amp;P 500 ETF became about ${B['rows'][0][1]:,.0f}; missing just the ten best days left about ${B['rows'][1][1]:,.0f}. Of the 20 best days, {B['best20_in_bear']} came during bear markets, often days after the worst ones.")),
            step(prose("Try different mixes and plans through real crashes:"), f'<div class="sim-embed">{sim}</div>'),
            step(check("In the simulator, what usually happens to a plan that sells everything at the 2020 peak and buys back 12 months later?",
                       ["It avoids the fall and catches the rebound", "It avoids the fall but misses most of the rebound", "It does the same as holding"], 1,
                       "The COVID fall lasted 33 days and the rebound was fast. A year out of the market missed most of it.")),
            step(prose("<b>Buckets</b> are a planning approach, popularised by Harold Evensky, that sorts money by when you'll need it: near-term spending in cash, the next several years in bonds, the long term in stocks. A crash then never forces you to sell stocks at the bottom."),
                 lab("buckets", None, "Build your buckets", "A rough sketch, not a plan. Your income, pensions, taxes and timeline all change the answer.")),
            step(prose("<b>Rules beat moods.</b> Decide now what you'd do in a 40% fall: rebalance back to your mix, follow a trend rule such as the <a href=\"" + h("strategies/ten-month-sma/") + "\">10-month rule</a>, or simply hold. Writing it down is the cheapest protection there is. The longer version is in <a href=\"" + h("articles/cash-or-invested/") + "\">Cash, stay invested, or buckets?</a>")),
        )
        self.shell("positioning", steps)
