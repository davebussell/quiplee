"""/guides/: which kinds of prediction work, family by family and play by play.

Free and rebuilt every night from the backtests:
  /guides/                 what kinds of prediction work (the seven bets compared)
  /guides/<family>/        one family: the bet, the evidence, when and where it worked
  /guides/<play>/          one play: does it work, when, on what, and how to use it

Narrative about each family's idea and the research behind it is written by
hand below; every number, ranking and verdict comes from tonight's results.
"""
import html

import numpy as np
import pandas as pd

from .content import TICKERS, TIMED, PLAY, FAMILIES, FAMILY, THINKER, GROUP_ORDER, credit
from .render import universe, pct, fill_bar, dlong, DISCLAIMER
from .media import page_art, PAGE_ART
from .icons import icon

e = html.escape

WINDOWS = [("2008 crash", "2007-10-09", "2009-03-09"), ("Recovery 2009–19", "2009-03-09", "2020-02-19"), ("COVID drop", "2020-02-19", "2020-03-23"),
           ("2020–21 rally", "2020-03-23", "2022-01-03"), ("2022 bear", "2022-01-03", "2022-10-12"), ("Since Oct 2022", "2022-10-12", None)]

LESSON = {"trend": "trend-following", "breakout": "breakouts", "momentum": "momentum", "reversion": "oscillators",
          "volume": "volume", "pattern": "candlesticks", "calendar": "calendar"}

# ---------------------------------------------------------------------------
# The idea behind each family, and what research has found (written by hand).
# ---------------------------------------------------------------------------
FAMILY_GUIDE = {
    "trend": {
        "bet": "Prices that have been rising tend to keep rising for a while, and falls tend to keep falling. A trend play doesn't try to call tops or bottoms: it holds while price stays on the right side of an average or trend line and steps aside when it breaks.",
        "why": "News spreads slowly, investors anchor to old prices and then chase, and big holders build and unwind positions over months. Each of these makes moves last longer than a random walk would.",
        "evidence": [
            "Brock, Lakonishok and LeBaron (1992) found simple moving-average and range-break rules had real predictive power on the Dow from 1897 to 1986.",
            "Sullivan, Timmermann and White (1999) showed the best of those rules stopped beating the market after 1986 once data-snooping was accounted for: rules that look best in hindsight often fade.",
            "Meb Faber (2007) showed a 10-month moving average kept most of the market's return with much smaller drawdowns across asset classes.",
            "Hurst, Ooi and Pedersen (2017) found trend following worked across a century of futures and bond and currency markets, with its best years in the worst bear markets.",
        ],
        "fails": "In choppy, sideways markets a trend rule is whipsawed: it buys after a rise, sells after a dip and pays a little each time. It also gives back part of every move, because it waits for the turn to show before acting, and it can't dodge a crash that happens in a day or two.",
        "use": ["Treat it as insurance: it costs a little most years and pays out in the rare bad ones, so judge it over a full cycle.",
                "Slower rules (weekly or monthly) whipsaw less but react later. Faster ones react sooner and trade more.",
                "Many traders use a slow trend rule only to decide whether to be in the market at all."],
    },
    "breakout": {
        "bet": "When price escapes the range it has held for weeks, the move that follows tends to run. A breakout play buys new highs (or a close above a band) and sells on a break the other way or a trailing stop.",
        "why": "A range is where buyers and sellers have agreed on value. A break means the balance has shifted, often on news, and the stops and orders sitting just beyond the range push it further.",
        "evidence": [
            "Richard Donchian's four-week rule of the 1960s and the Turtle traders of the 1980s (Curtis Faith's Way of the Turtle, 2007) made channel breakouts the backbone of trend-following funds.",
            "Brock, Lakonishok and LeBaron (1992) found trading-range breaks had predictive power on the Dow, alongside moving averages.",
            "Breakout systems win well under half their trades. Their edge, where it exists, comes from a few long runs paying for many small failed breakouts.",
        ],
        "fails": "Most breakouts fail. In quiet, range-bound markets a breakout play buys the top of the range again and again, and each failure costs the gap to the stop.",
        "use": ["Expect to be wrong more often than right; the size of the wins is what matters.",
                "A trailing stop that widens with volatility (ATR) keeps a breakout trade alive through normal noise.",
                "Breakouts on single stocks are noisier than on indexes or commodities, where the systems were built."],
    },
    "momentum": {
        "bet": "What has risen most over the past months tends to keep outperforming for a while. Momentum plays measure the rate of change, or strength against the market, and hold only while it is positive.",
        "why": "Investors under-react to news at first and over-react later, and money keeps flowing into last year's winners. Both stretch good runs out.",
        "evidence": [
            "Jegadeesh and Titman (1993) found stocks that rose most over 3 to 12 months kept beating the losers over the following months.",
            "Moskowitz, Ooi and Pedersen (2012) found 'time-series momentum', an asset's own past 12-month return, predicted its next month across 58 futures markets.",
            "George and Hwang (2004) found nearness to the 52-week high explained much of momentum's profit.",
            "Daniel and Moskowitz (2016) documented 'momentum crashes': after a market bottom, last year's losers can rebound violently and momentum suffers its worst months.",
            "Cooper, Gutierrez and Hameed (2004) found momentum paid only after the market had risen over the previous three years, and lost money after it had fallen.",
            "Da, Gurun and Warachka (2014) found momentum built from many small gains lasted longer than momentum from a few big jumps: the 'frog in the pan'.",
        ],
        "fails": "At sharp turning points. When a falling market reverses, momentum is still positioned for the old trend and misses the start of the rebound, or is caught holding last year's leaders as they reverse.",
        "use": ["Momentum is about relative strength: a stock can show momentum against the market while both fall.",
                "Monthly momentum rules trade little; daily oscillator versions trade much more.",
                "Pairing momentum with a trend filter (only buy strength in an uptrend) is the classic way to soften momentum crashes."],
    },
    "reversion": {
        "bet": "Short, sharp moves tend to snap back. Mean-reversion plays buy a stock after a quick drop or an oversold reading and sell into the bounce, often only when the longer trend is still up.",
        "why": "Over days, prices overshoot on forced selling, liquidity gaps and emotional trading, then market makers and bargain hunters pull them back. The effect is strongest for liquid, stable stocks and indexes.",
        "evidence": [
            "Jegadeesh (1990) and Lehmann (1990) found that stocks that fell most over the last week or month tended to rebound the next one: short-term reversal.",
            "De Bondt and Thaler (1985) found the same over 3 to 5 years: long-term losers beat long-term winners.",
            "Larry Connors and Cesar Alvarez (2009) popularised short-term rules like the 2-period RSI, which buy pullbacks only above the 200-day average.",
        ],
        "fails": "When the dip keeps dipping. Mean reversion buys falling prices, so in a real crash it buys too early and holds a loser. It also sits in cash much of the time, missing steady rallies.",
        "use": ["High hit rate, small wins: most trades work, a few big losses decide the result.",
                "The trend filter matters: buying dips in a long uptrend is a different bet from buying dips in a downtrend.",
                "Costs bite, because these rules trade often."],
    },
    "volume": {
        "bet": "Volume shows conviction. Money-flow plays read whether shares change hands more on up days or down days, betting that heavy buying shows up in volume before it shows up in price.",
        "why": "Large investors can't hide their size: buying a big position takes days of above-normal volume. Volume rising with price confirms a move; falling volume warns it is running out of buyers.",
        "evidence": [
            "Joseph Granville's On-Balance Volume (1963) made the idea popular: a running total of volume on up days minus down days.",
            "Blume, Easley and O'Hara (1994) showed volume carries information about the quality of price signals that price alone doesn't.",
            "Gervais, Kaniel and Mingelgrin (2001) found stocks with unusually high trading volume tend to rise over the following month.",
        ],
        "fails": "Volume is noisy for single stocks, swings around earnings, index rebalances and option expiry, and differs between exchanges. Many money-flow signals end up tracking price anyway.",
        "use": ["Use volume to confirm a price signal rather than on its own.",
                "Index and ETF volume is often distorted by fund flows; it reads best on actively traded single stocks."],
    },
    "pattern": {
        "bet": "A short pattern of bars can show a move running out of steam. Pattern plays look for a turn in the last day or few days, like a candle that swallows the one before it or a breakout that fails and snaps back, and trade the reversal.",
        "why": "A failed move traps the traders who bet on it. When a break below an old low reverses the next day, or a big up candle erases a down day, those traders rush to get out and add fuel to the turn.",
        "evidence": [
            "Steve Nison's Japanese Candlestick Charting Techniques (1991) brought candle patterns, used in Japanese rice trading since the 1700s, to Western traders.",
            "Caginalp and Laurent (1998) found some three-day candlestick reversal patterns predicted S&P 500 stocks over 1992 to 1996.",
            "Marshall, Young and Rose (2006) tested candlestick rules on the Dow stocks from 1992 to 2002 and found they added no value after accounting for chance.",
            "Lo, Mamaysky and Wang (2000) measured classic chart patterns with statistics and found they carried some information about the next few days' returns, mostly small.",
        ],
        "fails": "Patterns are common and most of them mean nothing: the same candle shape appears in random data. In a strong trend, a reversal pattern is usually just a pause before the trend carries on.",
        "use": ["Treat a pattern as a reason to look, not a reason to trade: the evidence that patterns alone pay is thin.",
                "Pattern plays hold for days, not months, so trading costs and slippage matter a lot.",
                "A pattern that agrees with the longer trend (a bullish turn inside an uptrend) has a better record than one that fights it."],
    },
    "calendar": {
        "bet": "Some parts of the year and month have been reliably stronger than others. Calendar plays hold only through those windows and sit in cash the rest of the time.",
        "why": "Pay-day and pension flows arrive at month ends, holidays lift mood and thin selling, and fund managers dress up portfolios at year end. Whether those causes still hold is part of the debate.",
        "evidence": [
            "Bouman and Jacobsen (2002) found returns from November to April beat May to October in 36 of 37 countries: the Halloween indicator, or 'sell in May'.",
            "Ariel (1987) and Lakonishok and Smidt (1988) found most of the market's gains came around the turn of the month and before holidays.",
            "French (1980) found the S&P 500 fell on average from Friday's close to Monday's close from 1953 to 1977: the weekend effect.",
            "Lucca and Moench (2015) found that from 1994 the S&P 500 made a large share of its excess return in the 24 hours before scheduled Fed announcements.",
            "McLean and Pontiff (2016) found published market anomalies lose much of their edge after publication, which matters most for well-known calendar effects.",
        ],
        "fails": "A calendar play can't see the market. It holds through a crash that happens inside its window and misses a rally outside it, and well-known effects get traded away.",
        "use": ["Calendar plays are in cash much of the year, so judge them on risk-adjusted return, not raw return.",
                "They work best on whole markets (indexes); single stocks add their own news on top."],
    },
}

BOOKS = [
    ("Brock, Lakonishok & LeBaron (1992)", "Simple technical trading rules and the stochastic properties of stock returns", "Journal of Finance"),
    ("Sullivan, Timmermann & White (1999)", "Data-snooping, technical trading rule performance, and the bootstrap", "Journal of Finance"),
    ("Jegadeesh & Titman (1993)", "Returns to buying winners and selling losers", "Journal of Finance"),
    ("Moskowitz, Ooi & Pedersen (2012)", "Time series momentum", "Journal of Financial Economics"),
    ("Faber (2007)", "A quantitative approach to tactical asset allocation", "Journal of Wealth Management"),
    ("Bouman & Jacobsen (2002)", "The Halloween indicator, 'Sell in May and go away': another puzzle", "American Economic Review"),
    ("McLean & Pontiff (2016)", "Does academic research destroy stock return predictability?", "Journal of Finance"),
    ("Lo, Mamaysky & Wang (2000)", "Foundations of technical analysis", "Journal of Finance"),
    ("Marshall, Young & Rose (2006)", "Candlestick technical trading strategies: can they create value for investors?", "Journal of Banking & Finance"),
    ("Lucca & Moench (2015)", "The pre-FOMC announcement drift", "Journal of Finance"),
]


def _rate(a, b):
    return a / b if b else None


class Guides:
    def __init__(self, site):
        self.s = site
        self.univ = [t for t in universe() if (t["sym"], "buy-and-hold") in site.R]
        self._m = {}

    def h(self, depth):
        return lambda x: self.s.href(depth, x)

    # ------------------------------------------------------------ numbers
    def play_metrics(self, p):
        """Per-stock results and summaries for one play (cached)."""
        if p["slug"] in self._m:
            return self._m[p["slug"]]
        rows = []
        for t in self.univ:
            x = self.s.R.get((t["sym"], p["slug"]))
            if not x:
                continue
            a, b = x["stats"]["full"]["strat"], x["stats"]["full"]["bh"]
            if not a or not b:
                continue
            sa, sb = a.get("sharpe"), b.get("sharpe")
            rows.append({"t": t, "x": x, "sh_gap": (sa - sb) if sa is not None and sb is not None else None,
                         "beat_sh": sa is not None and sb is not None and sa > sb, "beat_cg": a["cagr"] > b["cagr"], "cut": a["maxdd"] > b["maxdd"],
                         "cg_gap": a["cagr"] - b["cagr"], "dd_gap": a["maxdd"] - b["maxdd"],
                         "sw": x["stats"]["switches_per_year"], "inv": x["stats"]["invested"],
                         "bn": x["batting"]["n"], "br": x["batting"]["right"]})
        n = len(rows)
        calls = sum(r["bn"] for r in rows)
        m = {
            "rows": rows, "n": n,
            "beat_sh": sum(r["beat_sh"] for r in rows), "beat_cg": sum(r["beat_cg"] for r in rows), "cut": sum(r["cut"] for r in rows),
            "bat": _rate(sum(r["br"] for r in rows), calls), "calls": calls,
            "sw": float(np.median([r["sw"] for r in rows])) if rows else None,
            "inv": float(np.median([r["inv"] for r in rows if r["inv"] is not None])) if rows else None,
            "cg_gap": float(np.median([r["cg_gap"] for r in rows])) if rows else None,
            "dd_gap": float(np.median([r["dd_gap"] for r in rows])) if rows else None,
            "in_now": sum(1 for t in self.univ if (self.s.R.get((t["sym"], p["slug"])) or {}).get("state") == 1),
            "regimes": self.regimes([p]),
        }
        groups = {}
        for r in rows:
            groups.setdefault(r["t"]["group"], []).append(r)
        m["groups"] = [(g, len(groups[g]), sum(r["beat_sh"] for r in groups[g]), float(np.median([r["sh_gap"] for r in groups[g] if r["sh_gap"] is not None] or [0])))
                       for g in GROUP_ORDER if len(groups.get(g, [])) >= 6]
        self._m[p["slug"]] = m
        return m

    def _gaps(self, p):
        """Per window, every stock's gap against holding for one play (cached)."""
        cache = self.__dict__.setdefault("_gap_cache", {})
        if p["slug"] in cache:
            return cache[p["slug"]]
        out = [[] for _ in WINDOWS]
        bounds = [(pd.Timestamp(a), pd.Timestamp(b) if b else None) for _, a, b in WINDOWS]
        for t in self.univ:
            if t["crypto"]:
                continue
            x = self.s.R.get((t["sym"], p["slug"]))
            if not x:
                continue
            eq = x["equity"]
            d = pd.DatetimeIndex(eq["dates"])
            if not len(d):
                continue
            for w, (ta, tb) in enumerate(bounds):
                if d[0] > ta + pd.Timedelta(days=10):
                    continue
                i0 = int(d.searchsorted(ta))
                i1 = len(d) - 1 if tb is None else int(min(len(d) - 1, d.searchsorted(tb)))
                if i1 <= i0:
                    continue
                rs, rb = float(eq["strat"][i1] / eq["strat"][i0]), float(eq["bh"][i1] / eq["bh"][i0])
                yrs = (d[i1] - d[i0]).days / 365.25
                # long stretches compare yearly returns; short ones the whole move
                out[w].append(rs ** (1 / yrs) - rb ** (1 / yrs) if yrs > 1.5 and rs > 0 and rb > 0 else rs - rb)
        cache[p["slug"]] = out
        return out

    def regimes(self, plays):
        out = []
        for w, (lab, _, _) in enumerate(WINDOWS):
            gaps = [g for p in plays for g in self._gaps(p)[w]]
            out.append((lab, float(np.median(gaps)) if gaps else None, len(gaps)))
        return out

    def family_metrics(self, fk):
        ps = [p for p in TIMED if p["family"] == fk]
        ms = [self.play_metrics(p) for p in ps]
        g = sum(m["n"] for m in ms)
        calls = sum(m["calls"] for m in ms)
        right = sum((m["bat"] or 0) * m["calls"] for m in ms)
        groups = {}
        for m in ms:
            for r in m["rows"]:
                groups.setdefault(r["t"]["group"], []).append(r)
        return {"plays": ps, "ms": ms, "n": g, "beat_sh": sum(m["beat_sh"] for m in ms), "beat_cg": sum(m["beat_cg"] for m in ms),
                "cut": sum(m["cut"] for m in ms), "bat": _rate(right, calls), "calls": calls,
                "sw": float(np.median([m["sw"] for m in ms if m["sw"] is not None])) if ms else None,
                "inv": float(np.median([m["inv"] for m in ms if m["inv"] is not None])) if ms else None,
                "in_now": sum(m["in_now"] for m in ms), "slots": len(ps) * len(self.univ),
                "regimes": self.regimes(ps),
                "groups": [(gname, len(groups[gname]), sum(r["beat_sh"] for r in groups[gname]),
                            float(np.median([r["sh_gap"] for r in groups[gname] if r["sh_gap"] is not None] or [0])))
                           for gname in GROUP_ORDER if len(groups.get(gname, [])) >= 6 * len(ps)]}

    # ------------------------------------------------------------ pieces
    @staticmethod
    def share(k, n, word=""):
        if not n:
            return '<span class="muted">–</span>'
        return f'<span class="g-share">{fill_bar(k, n)}<b>{round(100 * k / n)}%</b>{(" " + word) if word else ""}</span>'

    def tiles(self, m):
        n = m["n"]
        items = [("Cut the worst fall", self.share(m["cut"], n), f"{m['cut']:,} of {n:,} stock tests: a smaller peak-to-trough loss than holding."),
                 ("Beat holding, risk-adjusted", self.share(m["beat_sh"], n), f"{m['beat_sh']:,} of {n:,}: a higher Sharpe ratio than buy and hold."),
                 ("Beat holding on return", self.share(m["beat_cg"], n), f"{m['beat_cg']:,} of {n:,}: more money than buy and hold, after costs."),
                 ("Calls right", f'<b class="g-big">{pct(m["bat"], sign=False, d=0)}</b>', f"Of {m['calls']:,} finished calls, in before a rise or out before a fall."),
                 ("Switches a year", f'<b class="g-big">{m["sw"]:.1f}</b>' if m.get("sw") is not None else "–", "Median trades per stock per year. More switching, more cost."),
                 ("Time in the market", f'<b class="g-big">{pct(m["inv"], sign=False, d=0)}</b>' if m.get("inv") is not None else "–", "Median share of days holding rather than in cash.")]
        return '<div class="grid g-tiles">' + "".join(
            f'<div class="card tile"><span class="tile-label">{a}</span><span class="tile-value g-val">{b}</span><span class="tile-note">{c}</span></div>' for a, b, c in items) + "</div>"

    @staticmethod
    def regime_cells(reg):
        out = ""
        for lab, v, nn in reg:
            cls = "" if v is None else ("st-calm" if v > 0.02 else "st-warning" if v < -0.02 else "")
            out += f'<td class="c" data-v="{"" if v is None else round(v, 4)}"><span class="st-cell {cls}">{pct(v, d=0)}</span></td>'
        return out

    @staticmethod
    def regime_sentence(reg, who):
        vals = [(lab, v) for lab, v, nn in reg if v is not None and nn >= 20]
        if len(vals) < 3:
            return ""
        best = max(vals, key=lambda z: z[1])
        worst = min(vals, key=lambda z: z[1])
        return (f"{who} did best against holding in the <b>{e(best[0])}</b> ({pct(best[1], d=0)} median gap) and worst in the "
                f"<b>{e(worst[0])}</b> ({pct(worst[1], d=0)}).")

    def verdict(self, m, name):
        n = m["n"] or 1
        cut, sh, cg = m["cut"] / n, m["beat_sh"] / n, m["beat_cg"] / n
        head = (f"Across {m['n']} stocks, {name} cut the worst fall on {round(cut * 100)}%, beat buying and holding on risk-adjusted return "
                f"on {round(sh * 100)}% and on raw return on {round(cg * 100)}%.")
        if sh >= 0.55:
            tag = "One of the stronger plays: on most stocks it earned more per unit of risk than simply holding."
        elif cut >= 0.7 and cg < 0.35:
            tag = "Mainly a seatbelt: it softened the big falls on most stocks, but usually gave up return to do it."
        elif cut >= 0.5 and sh >= 0.35:
            tag = "A fair trade: smaller falls on most stocks, with risk-adjusted results close to holding."
        elif sh < 0.25 and cut < 0.5:
            tag = "Hard to justify on its own: it rarely beat holding on risk-adjusted terms and didn't cut the worst fall on most stocks."
        else:
            tag = "Mixed: it helped on some kinds of stock and cost money on others, so where you use it matters."
        return head, tag

    def tips(self, p, m):
        out = []
        if m.get("sw") is not None:
            if m["sw"] >= 8:
                out.append(f"It trades often (about {m['sw']:.0f} switches a year per stock), so costs, spreads and taxes eat into it more than the backtest's 0.05% per switch suggests.")
            elif m["sw"] <= 2:
                out.append(f"It trades rarely (about {m['sw']:.1f} switches a year), so it suits someone who checks in occasionally, and a single bad call can last months.")
        if m.get("bat") is not None:
            if m["bat"] < 0.45:
                out.append(f"Expect to be wrong more often than right: only {pct(m['bat'], sign=False, d=0)} of its calls worked. Its results come from the size of the winners, so following it means sitting through strings of small losses.")
            elif m["bat"] > 0.6:
                out.append(f"It's right often ({pct(m['bat'], sign=False, d=0)} of calls), but check the size of the misses: a high hit rate can hide a few large losses.")
        if m.get("inv") is not None and m["inv"] < 0.45:
            out.append(f"It sits in cash much of the time (holding on about {pct(m['inv'], sign=False, d=0)} of days), so judge it on risk-adjusted return rather than on matching a rising market.")
        good = sorted([g for g in m["groups"] if g[1]], key=lambda g: -(g[2] / g[1]))
        if len(good) >= 3:
            b, w = good[0], good[-1]
            out.append(f"It worked best on <b>{e(b[0])}</b> ({round(100 * b[2] / b[1])}% beat holding on risk-adjusted return) and worst on <b>{e(w[0])}</b> ({round(100 * w[2] / w[1])}%).")
        out.append("Use it as one input. The <a href=\"{light}\">Start/Stop light</a> combines every play on a stock into one call.")
        return out

    # ------------------------------------------------------------ pages
    def build(self):
        for fk, _, _ in FAMILIES:
            if any(p["family"] == fk for p in TIMED):
                self.family_page(fk)
        for p in TIMED:
            self.play_page(p)
        self.hub()

    def hub(self):
        path, depth = "guides/", 1
        h = self.h(depth)
        fams = [(fk, name, desc, self.family_metrics(fk)) for fk, name, desc in FAMILIES if any(p["family"] == fk for p in TIMED)]
        allm = {"n": sum(f[3]["n"] for f in fams), "cut": sum(f[3]["cut"] for f in fams), "beat_sh": sum(f[3]["beat_sh"] for f in fams),
                "beat_cg": sum(f[3]["beat_cg"] for f in fams)}
        cards = ""
        for fk, name, desc, fm in fams:
            g = FAMILY_GUIDE.get(fk, {})
            cards += (f'<a class="card g-fam" href="{h("guides/" + fk + "/")}"><span class="fam-ic">{icon(fk)}</span><span class="eyebrow">{len(fm["plays"])} plays</span><span class="name">{e(name)}</span>'
                      f'<span class="small muted">{e(g.get("bet", desc))}</span>'
                      f'<span class="g-mini"><span>Cut the worst fall {self.share(fm["cut"], fm["n"])}</span><span>Beat holding, risk-adjusted {self.share(fm["beat_sh"], fm["n"])}</span>'
                      f'<span>Calls right <b>{pct(fm["bat"], sign=False, d=0)}</b></span></span></a>')
        rows = "".join(f'<tr><td><a href="{h("guides/" + fk + "/")}">{e(name)}</a></td><td class="r">{len(fm["plays"])}</td>'
                       f'<td data-v="{fm["cut"] / fm["n"]:.4f}">{self.share(fm["cut"], fm["n"])}</td><td data-v="{fm["beat_sh"] / fm["n"]:.4f}">{self.share(fm["beat_sh"], fm["n"])}</td>'
                       f'<td data-v="{fm["beat_cg"] / fm["n"]:.4f}">{self.share(fm["beat_cg"], fm["n"])}</td><td class="r">{pct(fm["bat"], sign=False, d=0)}</td>'
                       f'<td class="r">{fm["sw"]:.1f}</td></tr>' for fk, name, desc, fm in fams)
        reg_head = "".join(f"<th class='c'>{e(lab)}</th>" for lab, _, _ in WINDOWS)
        reg_rows = "".join(f'<tr><td><a href="{h("guides/" + fk + "/")}">{e(name)}</a></td>{self.regime_cells(fm["regimes"])}</tr>' for fk, name, desc, fm in fams)
        # findings
        by_cut = max(fams, key=lambda f: f[3]["cut"] / f[3]["n"])
        by_sh = max(fams, key=lambda f: f[3]["beat_sh"] / f[3]["n"])
        low_sh = min(fams, key=lambda f: f[3]["beat_sh"] / f[3]["n"])
        by_bat = max(fams, key=lambda f: f[3]["bat"] or 0)
        allp = [(p, self.play_metrics(p)) for p in TIMED]
        allp = [(p, m) for p, m in allp if m["n"]]
        sws = [m["sw"] for p, m in allp]
        shs = [m["beat_sh"] / m["n"] for p, m in allp]
        rho = float(pd.Series(sws).rank().corr(pd.Series(shs).rank())) if len(allp) > 5 else 0.0
        crash = [(name, dict((lab, v) for lab, v, nn in fm["regimes"])) for fk, name, desc, fm in fams]
        c08 = max(crash, key=lambda z: z[1].get("2008 crash") or -9)
        rally = min(crash, key=lambda z: z[1].get("Recovery 2009–19") or 9)
        findings = [
            f"<b>Protection is common; beating the market isn't.</b> Across {allm['n']:,} play-and-stock tests, {round(100 * allm['cut'] / allm['n'])}% cut the worst fall, "
            f"{round(100 * allm['beat_sh'] / allm['n'])}% beat holding on risk-adjusted return, and only {round(100 * allm['beat_cg'] / allm['n'])}% made more money than holding.",
            (f"<b>{e(by_cut[1])}</b> plays both cut the worst fall most often ({round(100 * by_cut[3]['cut'] / by_cut[3]['n'])}% of tests) and beat holding on risk-adjusted return most often "
             f"({round(100 * by_sh[3]['beat_sh'] / by_sh[3]['n'])}%), mostly by sitting in cash through the weak months. <b>{e(low_sh[1])}</b> plays beat holding least often ({round(100 * low_sh[3]['beat_sh'] / low_sh[3]['n'])}%)."
             if by_cut[0] == by_sh[0] else
             f"<b>{e(by_cut[1])}</b> cut the worst fall most often ({round(100 * by_cut[3]['cut'] / by_cut[3]['n'])}% of tests); <b>{e(by_sh[1])}</b> beat holding on risk-adjusted return most often "
             f"({round(100 * by_sh[3]['beat_sh'] / by_sh[3]['n'])}%), and <b>{e(low_sh[1])}</b> least often ({round(100 * low_sh[3]['beat_sh'] / low_sh[3]['n'])}%)."),
            f"<b>Being right often isn't the same as making money.</b> {e(by_bat[1])} plays were right on {pct(by_bat[3]['bat'], sign=False, d=0)} of calls, the highest hit rate of any family, "
            f"yet beat holding on risk-adjusted return on {round(100 * by_bat[3]['beat_sh'] / by_bat[3]['n'])}% of tests.",
            ("<b>Trading more didn't help.</b> Plays that switch more often tended to beat holding less often." if rho < -0.15 else
             "<b>Trading more helped a little.</b> Plays that switch more often tended to beat holding slightly more often, before real-world costs beyond the backtest's." if rho > 0.15 else
             "<b>How often a play trades said little about how well it did.</b> Fast and slow plays both appear among the best and the worst."),
            (f"<b>The market decides which bet pays.</b> {e(c08[0])} plays did best in the 2008 crash and lagged most in the long 2009–19 recovery: the caution that protects in a crash costs in a long rally."
             if c08[0] == rally[0] else
             f"<b>The market decides which bet pays.</b> {e(c08[0])} plays did best in the 2008 crash; {e(rally[0])} plays lagged most in the long 2009–19 recovery. No family won every kind of market."),
        ]
        top_sh = sorted(allp, key=lambda z: -(z[1]["beat_sh"] / z[1]["n"]))[:10]
        top_cut = sorted(allp, key=lambda z: -(z[1]["cut"] / z[1]["n"]))[:10]

        def plist(lst, key):
            return "".join(f'<li><a href="{h("guides/" + p["slug"] + "/")}">{e(p["name"])}</a> <span class="muted small">· {e(FAMILY[p["family"]][0])}</span>'
                           f'<span class="g-li">{self.share(m[key], m["n"])}</span></li>' for p, m in lst)
        refs = "".join(f"<li><b>{e(a)}</b>, {e(b)}. <i>{e(c)}</i>.</li>" for a, b, c in BOOKS)
        body = f"""
<section class="pair-head has-art">{page_art(h, PAGE_ART["guides/"], "50% 62%")}<p class="eyebrow">Guides</p><h1 class="h1">Which predictions actually work?</h1>
<p class="lede">Every trading play is a prediction about what a price will do next. They come in seven kinds: trends continue, breakouts run, strength persists, dips snap back, volume leads price, patterns warn of a turn, and the calendar matters. Be The Puck runs all {len(TIMED)} plays on {len(self.univ)} stocks, funds and coins every night. Here is what the record says about each kind of bet, with a guide to every family and every play.</p></section>

<section><div class="sec-head"><h2 class="h2">Five things {allm['n']:,} backtests say</h2><p>Each play against simply holding the same stock over the same dates since 2005, after costs, as of the {dlong(self.s.asof)} close.</p></div>
<ol class="g-findings">{"".join(f"<li>{x}</li>" for x in findings)}</ol></section>

<section><div class="sec-head"><h2 class="h2">The seven bets</h2><p>Open a family for what it predicts, the research behind it, when it works and when it fails.</p></div>
<div class="grid grid-3">{cards}</div></section>

<section><div class="sec-head"><h2 class="h2">The scorecard</h2><p>Share of play-and-stock tests where the family's plays did better than holding. Click a column to sort.</p></div>
<div class="tbl-wrap"><table class="tbl"><thead><tr><th>Family</th><th class="r">Plays</th><th data-sort-first="desc">Cut the worst fall</th><th data-sort-first="desc">Beat holding, risk-adjusted</th><th data-sort-first="desc">Beat holding on return</th><th class="r">Calls right</th><th class="r">Switches / yr</th></tr></thead><tbody>{rows}</tbody></table></div></section>

<section><div class="sec-head"><h2 class="h2">Market by market</h2><p>Median gap in return between each family's plays and holding the same stock through each stretch (crypto excluded): per year over stretches longer than 18 months, for the whole stretch otherwise. Positive means the play did better.</p></div>
<div class="tbl-wrap"><table class="tbl tops" data-nosort><thead><tr><th>Family</th>{reg_head}</tr></thead><tbody>{reg_rows}</tbody></table></div></section>

<section class="split"><div class="card"><h2 class="h3">Most often beat holding, risk-adjusted</h2><ol class="g-list">{plist(top_sh, "beat_sh")}</ol></div>
<div class="card"><h2 class="h3">Most often cut the worst fall</h2><ol class="g-list">{plist(top_cut, "cut")}</ol></div></section>

<section class="card prose"><h2 class="h3">Putting them together</h2>
<p>No single kind of prediction wins in every market, which is why Be The Puck sums every play on a stock into one <a href="{h('method/')}#light">Start/Stop light</a>: Start when most of the plays hold it, Stop when most don't. You can <a href="{h('alerts/')}">get an email</a> when it flips on your stocks, and members can choose which plays count. Every play also has a guide: <a href="{h('strategies/')}">browse all {len(TIMED)}</a>.</p></section>

<section class="card prose"><h2 class="h3">Further reading</h2><ul class="g-refs">{refs}</ul>
<p class="small muted">Backtests flatter: they use stocks still listed today, can't feel fear, and with {len(TIMED)} plays some will look good by luck. {DISCLAIMER}</p></section>
"""
        self.s.add(path, self.s.shell(path, "Which trading predictions actually work?",
                                      f"Trend, breakout, momentum, mean reversion, volume and calendar plays compared on {len(self.univ)} stocks: what each predicts and how often it beat simply holding.",
                                      body, active="strategies/"))

    def family_page(self, fk):
        path, depth = f"guides/{fk}/", 2
        h = self.h(depth)
        name, desc = FAMILY[fk]
        g = FAMILY_GUIDE.get(fk, {"bet": desc, "why": "", "evidence": [], "fails": "", "use": []})
        fm = self.family_metrics(fk)
        rows = ""
        for p, m in sorted(zip(fm["plays"], fm["ms"]), key=lambda z: -((z[1]["beat_sh"] / z[1]["n"]) if z[1]["n"] else 0)):
            if not m["n"]:
                continue
            rows += (f'<tr><td><a href="{h("guides/" + p["slug"] + "/")}">{e(p["name"])}</a><span class="sym-sub">{e(credit(p))}</span></td>'
                     f'<td data-v="{m["beat_sh"] / m["n"]:.4f}">{self.share(m["beat_sh"], m["n"])}</td><td data-v="{m["cut"] / m["n"]:.4f}">{self.share(m["cut"], m["n"])}</td>'
                     f'<td data-v="{m["beat_cg"] / m["n"]:.4f}">{self.share(m["beat_cg"], m["n"])}</td><td class="r">{pct(m["bat"], sign=False, d=0)}</td>'
                     f'<td class="r">{m["sw"]:.1f}</td><td class="r">{pct(m["inv"], sign=False, d=0)}</td><td class="r">{m["in_now"]}/{len(self.univ)}</td></tr>')
        reg_head = "".join(f"<th class='c'>{e(lab)}</th>" for lab, _, _ in WINDOWS)
        grp = sorted(fm["groups"], key=lambda z: -(z[2] / z[1]))
        grows = "".join(f'<tr><td>{e(gname)}</td><td data-v="{k / n:.4f}">{self.share(k, n)}</td><td class="r" data-v="{gap:.4f}">{gap:+.2f}</td></tr>' for gname, n, k, gap in grp)
        ev = "".join(f"<li>{e(x)}</li>" for x in g["evidence"])
        use = "".join(f"<li>{e(x)}</li>" for x in g["use"])
        share_now = fm["in_now"] / fm["slots"] if fm["slots"] else 0
        lesson = LESSON.get(fk)
        body = f"""
<nav class="crumbs"><a href="{h('guides/')}">Guides</a><span>/</span><span>{e(name)}</span></nav>
<section class="pair-head"><p class="eyebrow">Guide · {len(fm['plays'])} plays</p><h1 class="h1">{e(name)}: what it predicts, and when it works</h1>
<p class="lede">{e(g['bet'])}</p></section>
{self.tiles(fm)}
<section class="split"><div class="card prose"><h2 class="h3">Why it might work</h2><p>{e(g['why'])}</p><h2 class="h3">When it fails</h2><p>{e(g['fails'])}</p></div>
<div class="card prose"><h2 class="h3">What the research says</h2><ul>{ev}</ul></div></section>

<section><div class="sec-head"><h2 class="h2">Every {e(name.lower())} play, ranked</h2><p>Share of stocks where each play did better than holding, since 2005 or as long as the stock has traded, after costs. Click a column to sort.</p></div>
<div class="tbl-wrap"><table class="tbl"><thead><tr><th>Play</th><th data-sort-first="desc">Beat holding, risk-adjusted</th><th data-sort-first="desc">Cut the worst fall</th><th data-sort-first="desc">Beat holding on return</th><th class="r">Calls right</th><th class="r">Switches / yr</th><th class="r">Time in</th><th class="r">In now</th></tr></thead><tbody>{rows}</tbody></table></div></section>

<section><div class="sec-head"><h2 class="h2">When it worked</h2><p>{self.regime_sentence(fm['regimes'], 'The family')} Median gap in return against holding (per year over stretches longer than 18 months; crypto excluded).</p></div>
<div class="tbl-wrap"><table class="tbl tops" data-nosort><thead><tr><th></th>{reg_head}</tr></thead><tbody><tr><td>{e(name)}</td>{self.regime_cells(fm['regimes'])}</tr></tbody></table></div></section>

<section><div class="sec-head"><h2 class="h2">Where it worked</h2><p>By kind of stock: how often the family's plays beat holding on risk-adjusted return, and the median Sharpe ratio gap.</p></div>
<div class="tbl-wrap"><table class="tbl"><thead><tr><th>Group</th><th data-sort-first="desc">Beat holding, risk-adjusted</th><th class="r" data-sort-first="desc">Sharpe gap</th></tr></thead><tbody>{grows}</tbody></table></div></section>

<section class="split"><div class="card prose"><h2 class="h3">How traders use it</h2><ul>{use}</ul>{f'<p><a href="{h("learn/" + lesson + "/")}">Learn it step by step</a></p>' if lesson else ''}</div>
<div class="card prose"><h2 class="h3">Right now</h2><p>The {e(name.lower())} plays hold {round(100 * share_now)}% of the stock-and-play combinations Be The Puck tracks ({fm['in_now']:,} of {fm['slots']:,}) as of the {dlong(self.s.asof)} close.</p>
<p><a href="{h('stocks/?view=families')}">See which stocks each family holds</a> · <a href="{h('strategies/')}#fam-{fk}">The plays and their rules</a></p></div></section>
<p class="small muted">{DISCLAIMER}</p>
"""
        self.s.add(path, self.s.shell(path, f"{name}: what it predicts and when it works",
                                      f"{name} plays tested on {len(self.univ)} stocks: the bet they make, the research behind it, and how often each one beat simply holding.",
                                      body, active="strategies/"))

    def play_page(self, p):
        path, depth = f"guides/{p['slug']}/", 2
        h = self.h(depth)
        m = self.play_metrics(p)
        fname = FAMILY[p["family"]][0]
        g = FAMILY_GUIDE.get(p["family"], {})
        if not m["n"]:
            return
        head, tag = self.verdict(m, p["name"])
        by = " &amp; ".join(f'<a href="{h("thinkers/" + a + "/")}">{e(THINKER[a]["name"])}</a>' for a in p["analysts"])
        rules = "".join(f"<li>{e(r)}</li>" for r in p["rules"])
        reg_head = "".join(f"<th class='c'>{e(lab)}</th>" for lab, _, _ in WINDOWS)
        grp = sorted(m["groups"], key=lambda z: -(z[2] / z[1]))
        grows = "".join(f'<tr><td>{e(gname)}</td><td data-v="{k / n:.4f}">{self.share(k, n)}</td><td class="r" data-v="{gap:.4f}">{gap:+.2f}</td></tr>' for gname, n, k, gap in grp)
        # best and worst lists only use stocks with three years or more of graded history
        ranked = sorted([r for r in m["rows"] if r["sh_gap"] is not None and (r["x"]["stats"]["full"]["strat"] or {}).get("years", 0) >= 3],
                        key=lambda r: -r["sh_gap"])

        def stock_li(r):
            t = r["t"]
            return (f'<li><a href="{h("stocks/" + t["slug"] + "/" + p["slug"] + "/")}">{e(t["short"])}</a> <span class="muted small">{e(t["name"])}</span>'
                    f'<span class="g-li {"up" if r["sh_gap"] > 0 else "down"}">{r["sh_gap"]:+.2f}</span></li>')
        best = "".join(stock_li(r) for r in ranked[:6])
        worst = "".join(stock_li(r) for r in ranked[-6:][::-1])
        tips = "".join(f"<li>{x.replace('{light}', h('method/') + '#light')}</li>" for x in self.tips(p, m))
        recent = []
        for t in self.univ:
            x = self.s.R.get((t["sym"], p["slug"]))
            c = (x or {}).get("last_call")
            if c and c["date"] >= self.s.asof - pd.Timedelta(days=10):
                recent.append((c["date"], t, c))
        recent.sort(key=lambda z: z[0], reverse=True)
        rec_html = "".join(f'<li><a href="{h("stocks/" + t["slug"] + "/" + p["slug"] + "/")}">{e(t["short"])}</a> <span class="muted small">{"went in" if c["state"] == 1 else "went out"} {e(dlong(d))}</span></li>'
                           for d, t, c in recent[:8])
        body = f"""
<nav class="crumbs"><a href="{h('guides/')}">Guides</a><span>/</span><a href="{h('guides/' + p['family'] + '/')}">{e(fname)}</a><span>/</span><span>{e(p['name'])}</span></nav>
<section class="pair-head"><p class="eyebrow">Guide · {e(fname)}</p><h1 class="h1">Does {e(p['name'])} work?</h1>
<p class="lede">{e(head)} <b>{e(tag)}</b></p>
<div class="byline"><span>Play from {by}</span><span>·</span><a href="{h('strategies/' + p['slug'] + '/')}">The rule and every stock</a></div></section>
{self.tiles(m)}
<section class="split"><div class="card prose"><h2 class="h3">What it predicts</h2><p>{e(p['short'])}</p><ul>{rules}</ul>
<p class="small muted">{e(fname)} plays bet that {e((g.get('bet') or '').split('.')[0].lower())}. <a href="{h('guides/' + p['family'] + '/')}">The family guide</a></p></div>
<div class="card prose"><h2 class="h3">How to use it</h2><ul>{tips}</ul></div></section>

<section><div class="sec-head"><h2 class="h2">When it worked</h2><p>{self.regime_sentence(m['regimes'], p['name'])} Median gap in return against holding the same stock (per year over stretches longer than 18 months; crypto excluded).</p></div>
<div class="tbl-wrap"><table class="tbl tops" data-nosort><thead><tr><th></th>{reg_head}</tr></thead><tbody><tr><td>{e(p['name'])}</td>{self.regime_cells(m['regimes'])}</tr></tbody></table></div></section>

<section><div class="sec-head"><h2 class="h2">Where it worked</h2><p>By kind of stock: how often it beat holding on risk-adjusted return, and the median Sharpe ratio gap.</p></div>
<div class="tbl-wrap"><table class="tbl"><thead><tr><th>Group</th><th data-sort-first="desc">Beat holding, risk-adjusted</th><th class="r" data-sort-first="desc">Sharpe gap</th></tr></thead><tbody>{grows}</tbody></table></div></section>

<section class="split"><div class="card"><h2 class="h3">Where it helped most</h2><p class="small muted">Sharpe ratio gap against holding, stocks with 3+ years of history</p><ol class="g-list">{best}</ol></div>
<div class="card"><h2 class="h3">Where it hurt most</h2><p class="small muted">Sharpe ratio gap against holding, stocks with 3+ years of history</p><ol class="g-list">{worst}</ol></div></section>

<section class="card prose"><h2 class="h3">Right now</h2><p>{e(p['name'])} holds {m['in_now']} of {len(self.univ)} names as of the {dlong(self.s.asof)} close.</p>
{f'<p>Changed its call in the last two weeks:</p><ul class="g-recent">{rec_html}</ul>' if rec_html else '<p>No changes of call in the last two weeks.</p>'}
<p><a href="{h('strategies/' + p['slug'] + '/')}">What it says on every stock</a></p></section>
<p class="small muted">Backtest results since 2005 (or as long as each stock has traded), against holding the same stock over the same dates, after 0.05% per switch. Past results don't promise future ones. {DISCLAIMER}</p>
"""
        self.s.add(path, self.s.shell(path, f"Does {p['name']} work? A guide from {m['n']} backtests",
                                      f"{p['name']} ({fname.lower()}) tested on {m['n']} stocks: how often it cut the worst fall and beat holding, when and where it worked, and how to use it.",
                                      body, active="strategies/"))
