"""Build the 'Call it' practice set and the play-quiz bank.

Call it: real charts cut off at a real close. The learner reads the play's
lines and says IN or OUT; then the rest of the chart and what happened next
are revealed. Scenarios are drawn reproducibly (fixed seed) from well-known
names so the set only changes when prices do.
"""
import json

import numpy as np
import pandas as pd

from .content import TICKERS, TIMED, THINKER, FAMILY, BAR_WORD, credit
from .engine import to_bars, make_ctx, BENCH
from .cal import future_sessions
from .render import money

POOL = ["SPY", "QQQ", "IWM", "GLD", "TLT", "BTC-USD", "AAPL", "MSFT", "NVDA", "AMZN", "META", "TSLA", "AMD",
        "LLY", "JPM", "XOM", "SHOP.TO", "RY.TO", "URI", "MARA"]
BEFORE, AFTER = 110, 40


def _sig(v, n=4):
    if v is None or (isinstance(v, float) and (np.isnan(v) or np.isinf(v))):
        return None
    return float(f"{float(v):.{n}g}")


def build_practice(prices, irx, now, per_play=2, seed=11):
    rng = np.random.default_rng(seed)
    tk = {t["sym"]: t for t in TICKERS}
    bench = prices[BENCH]["close"]
    out = []
    plays = [p for p in TIMED if not p.get("calendar")]
    for p in plays:
        syms = list(rng.permutation([s for s in POOL if s in prices]))
        made, tries = 0, 0
        for sym in syms:
            if made >= per_play or tries > 8:
                break
            tries += 1
            t = tk[sym]
            d = prices[sym]
            bars, complete, _ = to_bars(d, p["bar"], t["crypto"], now)
            done = bars if complete else bars.iloc[:-1]
            if len(done) < BEFORE + AFTER + 60:
                continue
            fut = future_sessions(done.index[-1], t["crypto"]) if p["bar"] == "D" else None
            res = p["fn"](done, make_ctx(t, done.index, bench, irx, fut))
            st = res["state"]
            v = st.to_numpy()
            n = len(v)
            lo = max(BEFORE + 1, int(n * 0.25))
            hi = n - AFTER - 1
            idx = np.arange(lo, hi)
            idx = idx[~np.isnan(v[idx]) & ~np.isnan(v[idx - 1])]
            if not len(idx):
                continue
            flips = idx[v[idx] != v[idx - 1]]
            want_flip = (made % 2 == 0)
            cand = flips if (want_flip and len(flips)) else idx
            i = int(rng.choice(cand))
            ans = int(v[i])
            # what happened next: until the next change of call (or the end of the window)
            j = i + 1
            while j < n and v[j] == ans:
                j += 1
            j = min(j, n - 1)
            c = done["close"].to_numpy()
            move = c[j] / c[i] - 1
            w0, w1 = i - BEFORE, min(n, i + AFTER + 1)
            win = done.iloc[w0:w1]
            t0 = win.index[0]
            series = [{"name": t["short"], "role": "price", "v": [_sig(x, 5) for x in win["close"]]}]
            for lab, ser, role in res["lines"]:
                series.append({"name": lab, "role": role, "v": [_sig(x, 5) for x in ser.iloc[w0:w1]]})
            spec = {"t0": t0.strftime("%Y-%m-%d"), "d": [int((x - t0).days) for x in win.index], "cur": t["cur"], "fmt": "price",
                    "series": series, "label": f"{t['short']} with the {p['name']} play"}
            panel = None
            if res.get("panel"):
                pn = res["panel"]
                panel = {"t0": spec["t0"], "d": spec["d"], "cur": "", "fmt": "pct" if pn["fmt"] == "pct" else "num", "label": pn["label"],
                         "series": [{"name": lab, "role": role, "v": [_sig(x) for x in ser.iloc[w0:w1]]} for lab, ser, role in pn["series"]],
                         "levels": pn["levels"]}
                if pn.get("min") is not None:
                    panel["ymin"] = pn["min"]
                if pn.get("max") is not None:
                    panel["ymax"] = pn["max"]
            sv = st.iloc[w0:w1].to_numpy()
            runs, start, prev = [], None, None
            for k, x in enumerate(sv):
                x = None if np.isnan(x) else int(x)
                if x != prev:
                    if prev is not None:
                        runs.append([start, k - 1, prev])
                    start, prev = k, x
            if prev is not None:
                runs.append([start, len(sv) - 1, prev])
            out.append({
                "id": f"{p['slug']}~{t['slug']}~{done.index[i].strftime('%Y%m%d')}",
                "play": p["slug"], "name": p["name"], "family": p["family"], "by": credit(p), "bar": BAR_WORD[p["bar"]],
                "rules": p["rules"], "sym": t["short"], "stock": t["name"], "cur": t["cur"],
                "date": done.index[i].strftime("%b %-d, %Y"), "price": money(float(c[i]), t["cur"]), "cut": BEFORE,
                "answer": ans, "flip": bool(v[i] != v[i - 1]), "move": round(float(move), 4),
                "until": done.index[j].strftime("%b %-d, %Y"), "bars": int(j - i),
                "right": bool(move > 0) if ans == 1 else bool(move < 0),
                "chart": spec, "panel": panel, "runs": runs,
            })
            made += 1
    return out


def play_bank():
    return [{"slug": p["slug"], "name": p["name"], "by": credit(p), "analysts": p["analysts"], "family": p["family"],
             "familyName": FAMILY[p["family"]][0], "bar": BAR_WORD[p["bar"]], "short": p["short"], "rule": p["rules"][0]}
            for p in TIMED]


def practice_json(items):
    return json.dumps({"items": items}, separators=(",", ":"), ensure_ascii=False)
