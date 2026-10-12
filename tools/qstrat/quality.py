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
