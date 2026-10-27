"""The data-quality gate: checks every company number before it reaches Your signal.

factors.compute() sends each fundamental through check(); a number that fails is held back
(the stock is scored on its other factors, as if the number were missing), and a number
with a known fault is corrected. Everything held back or corrected is listed in
data/quality.json and in the build log, so a bad number is seen instead of shipped.

The checks:
  - bounds: values no real company has (a P/E over 1,000, a dividend yield over 25%, debt over
    50 times equity...). These are almost always a units change or a near-zero denominator.
  - currency: Yahoo divides a TSX company's market value in Canadian dollars by revenue in the
    currency it reports in (often U.S. dollars), so its price-to-sales is off by the exchange
    rate. Corrected with the night's CAD/USD rate; other currency pairs are held back.
  - staleness: Yahoo numbers fetched more than STALE_DAYS ago are held back (the nightly fetch
    has been failing for that stock); SEC numbers carry their own filing dates (secfund.STALE_DAYS).
"""
import datetime as dt
import json

STALE_DAYS = 10
# key: (lowest believable, highest believable), in the units factors.py ranks
BOUNDS = {
    "pe": (0, 1000), "fpe": (0, 1000), "peg": (-50, 50), "ps": (0, 500), "pb": (0, 500),
    "dy": (0, 0.25), "eg": (-50, 100), "rg": (-1, 50), "pm": (-100, 5), "roe": (-20, 20), "de": (0, 50),
}
NAMES = {"pe": "P/E", "fpe": "forward P/E", "peg": "PEG", "ps": "price to sales", "pb": "price to book", "dy": "dividend yield",
         "eg": "earnings growth", "rg": "revenue growth", "pm": "profit margin", "roe": "return on equity", "de": "debt to equity"}


class Gate:
    def __init__(self, asof, fx):
        self.asof = asof
        self.fx = fx
        self.items = []

    def note(self, t, key, value, why, action):
        self.items.append({"sym": t["sym"], "factor": NAMES.get(key, key), "value": value if not isinstance(value, float) else round(value, 4),
                           "why": why, "action": action})

    def stale(self, t, fund):
        """True when this stock's Yahoo numbers are too old to use."""
        got = (fund or {}).get("fetched")
        if not got:
            return False
        try:
            age = (self.asof.date() - dt.date.fromisoformat(got)).days
        except Exception:
            return False
        if age > STALE_DAYS:
            self.note(t, "all", got, f"Yahoo numbers fetched {age} days ago", "held back")
            return True
        return False

    def ps_currency(self, t, fund, ps):
        """Yahoo's price to sales for a stock that trades in one currency and reports in another."""
        trade = "CAD" if t.get("cur") == "C$" else "USD"
        rep = (fund or {}).get("financialCurrency") or trade
        if rep == trade or ps is None:
            return ps
        if trade == "CAD" and rep == "USD" and self.fx:
            fixed = ps / self.fx
            self.note(t, "ps", ps, f"market value in CAD over revenue in USD; divided by {self.fx:.4f}", f"corrected to {fixed:.2f}")
            return fixed
        self.note(t, "ps", ps, f"trades in {trade}, reports in {rep}", "held back")
        return None

    def check(self, t, key, value, src):
        """The value if it's believable, else None (and a note)."""
        if value is None or isinstance(value, str):
            return value
        lo, hi = BOUNDS.get(key, (None, None))
        if lo is not None and not (lo <= value <= hi):
            shown = f"{value * 100:,.1f}%" if key in ("dy", "eg", "rg", "pm", "roe") else f"{value:,.2f}"
            self.note(t, key, value, f"{NAMES.get(key, key)} of {shown} from {src} is outside {lo:g} to {hi:g}", "held back")
            return None
        return value

    def report(self):
        return {"asof": self.asof.strftime("%Y-%m-%d"), "n": len(self.items), "items": self.items}

    def json(self):
        return json.dumps(self.report(), ensure_ascii=False, indent=1)

    def summary(self):
        held = sum(1 for x in self.items if x["action"] == "held back")
        fixed = len(self.items) - held
        return f"data quality: {held} numbers held back, {fixed} corrected (data/quality.json)"


# --------------------------------------------------------------------------
# Price files (AUD-46): checked once, as they're read (engine.load_all), so every
# play, factor and test sees the same cleaned history.
# --------------------------------------------------------------------------
JUMP = 5            # a one-day rise of 5x or more...
JUMP_LEVEL = 0.6    # ...that holds (the next month's median is at least 60% of the jump over the last month's)...
JUMP_CALM = 0.2     # ...with a quiet next day (within 20%)...
JUMP_VOL = 10       # ...and no burst of trading (median volume up less than 10x) is a reverse split Yahoo left unadjusted
TICK = 2            # a close at least double, or at most half, the sessions either side...
TICK_BACK = 1.25    # ...that is back within 25% the next day is a bad tick
TICK_FLOOR = 0.5    # under 50 cents, a cent's tick can be a real halving
PENNY = 0.01        # last close under a cent: too thin to test
DEAD_SHARE = 0.25   # more than a quarter of the last two years' sessions with no trades: too thin to test


def price_check(sym, d, crypto=False, index=False):
    """Clean one price history. Returns (d, notes, unreliable): the history with bad
    ticks flattened and anything before an unadjusted reverse split left out, a
    plain-words line per change, and a reason when the stock is too thin to test
    (it keeps its page but stays out of every graded record)."""
    import numpy as np
    notes = []
    if len(d) < 3:
        return d, notes, None
    c = d["close"].to_numpy()
    v = d["volume"].to_numpy()
    # one-day bad ticks: put the session back at the previous close
    bad = []
    for i in range(1, len(c) - 1):
        a, b = c[i] / c[i - 1], c[i + 1] / c[i]
        back = c[i + 1] / c[i - 1]
        if c[i - 1] >= TICK_FLOOR and ((a >= TICK and b <= 1 / TICK) or (a <= 1 / TICK and b >= TICK)) and 1 / TICK_BACK <= back <= TICK_BACK:
            bad.append(i)
    if bad:
        d = d.copy()
        for i in bad:
            prev = d["close"].iat[i - 1]
            for col in ("open", "high", "low", "close"):
                d.iat[i, d.columns.get_loc(col)] = prev
        days = ", ".join(d.index[i].strftime("%b %-d, %Y") for i in bad[:3]) + (" and others" if len(bad) > 3 else "")
        notes.append(f"{len(bad)} one-day bad price{'s' if len(bad) > 1 else ''} ({days}) replaced with the previous session's close")
        c = d["close"].to_numpy()
    # an unadjusted reverse split: keep the history from the jump on
    cut = None
    for i in range(1, len(c)):
        r = c[i] / c[i - 1]
        if r < JUMP:
            continue
        pre = np.median(c[max(0, i - 20):i])
        post = np.median(c[i:i + 20])
        nxt = c[i + 1] / c[i] if i + 1 < len(c) else 1.0
        pv = np.median(v[max(0, i - 20):i])
        qv = np.median(v[i:i + 20])
        burst = pv > 0 and qv / pv >= JUMP_VOL
        if post / pre >= JUMP_LEVEL * r and abs(nxt - 1) <= JUMP_CALM and not burst:
            cut = i
    if cut is not None:
        notes.append(f"history before {d.index[cut].strftime('%b %-d, %Y')} left out: prices jumped {c[cut] / c[cut - 1]:,.0f}x overnight and stayed there "
                     "without a rush of trading, usually a reverse split the price feed didn't adjust")
        d = d.iloc[cut:]
    why = None
    if not crypto and not index:
        last = float(d["close"].iat[-1])
        tail = d["volume"].iloc[-504:]
        dead = float((tail == 0).mean()) if len(tail) else 0.0
        if last < PENNY:
            why = f"last close under a cent (${last:.4f})"
        elif dead > DEAD_SHARE:
            why = f"no trades on {dead:.0%} of the last two years' sessions"
    return d, notes, why
