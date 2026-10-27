#!/usr/bin/env python3
"""Keep each covered company's dated events, for the "what moved it lately" read on
its stock page and the news-that-moves-stocks guide: data/events/<slug>.json.

Two lists per company, both from Yahoo Finance via yfinance:
  - earn: every quarterly report Yahoo lists (about ten years for most names), with
    analysts' average EPS estimate going in, the EPS reported and the surprise in
    percent, plus the next scheduled report (estimate only, the rest null).
  - ratings: Wall Street rating changes and price-target moves over the last three
    years (upgrades, downgrades, new coverage, targets raised or cut).

A third list, splits, is the company's stock splits since 2004 ([[day, new shares per old share], ...],
oldest first: 4 for a 4-for-1, 0.1 for a 1-for-10), refetched weekly (splits_at). secfund.py uses it to put
the per-share numbers in SEC filings on the same share basis as the split-adjusted prices.

Each file is {"fetched": iso, "earn": [[t, eps_est, eps_actual, surprise_pct], ...],
"ratings": [[t, firm, action, from_grade, to_grade, pt_action, current_pt, prior_pt], ...],
"splits": [[day, ratio], ...], "splits_at": iso}
with t in ISO UTC, newest first. action is Yahoo's code: up, down, init, main
(maintained) or reit (reiterated). Only companies with a fundamentals file are
fetched (no funds, indexes or coins). A file is rewritten only when its lists
change ("fetched" is then the time of that fetch), and a company whose file was
written in the last 20 hours is skipped, so a run that Yahoo throttles can be run
again to resume. A list that fails keeps its old contents.

    python tools/fetch_events.py              # every company, skipping fresh files
    python tools/fetch_events.py --force      # refetch everything
    python tools/fetch_events.py MU NVDA      # just these (always refetched)
"""
import datetime as dt
import json
import math
import os
import sys
import time

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from qstrat.content import TICKERS  # noqa: E402

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
OUT = os.path.join(ROOT, "data", "events")
FUND = os.path.join(ROOT, "data", "fundamentals")
EARN_LIMIT = 40           # quarters asked for; Yahoo's earnings calendar often returns a few more
RATING_DAYS = 3 * 365
SPLIT_DAYS = 7            # splits are refetched once a week
FRESH_HOURS = 20
PAUSE = 0.8               # seconds between companies
BACKOFF = (60, 180, 600)  # waits after Yahoo throttles us, in turn; then the run stops


class Throttled(Exception):
    pass


def iso(ts):
    import pandas as pd
    ts = pd.Timestamp(ts)
    ts = ts.tz_localize("UTC") if ts.tzinfo is None else ts.tz_convert("UTC")
    return ts.strftime("%Y-%m-%dT%H:%M:%SZ")


def num(v, d=4):
    try:
        v = float(v)
    except (TypeError, ValueError):
        return None
    return None if math.isnan(v) or math.isinf(v) else round(v, d)


def text(v):
    if v is None or (isinstance(v, float) and math.isnan(v)):
        return ""
    return str(v).strip()


def is_throttle(ex):
    s = f"{ex.__class__.__name__} {ex}".lower()
    return "ratelimit" in s or "too many requests" in s or "429" in s


def earnings(tk, now):
    """[[t, est, actual, surprise%], ...] newest first: every past report and the next scheduled one."""
    df = tk.get_earnings_dates(limit=EARN_LIMIT)
    if df is None:
        raise ValueError("no earnings calendar")
    if df.empty:
        return []
    cols = {c.lower(): c for c in df.columns}
    est_c, act_c = cols.get("eps estimate"), cols.get("reported eps")
    sur_c = next((c for k, c in cols.items() if k.startswith("surprise")), None)
    past, future, seen = [], [], set()
    for ts, row in df.iterrows():
        t = iso(ts)
        if t[:10] in seen:
            continue
        seen.add(t[:10])
        est = num(row[est_c]) if est_c else None
        act = num(row[act_c]) if act_c else None
        sur = num(row[sur_c], 2) if sur_c else None
        if sur is None and est is not None and act is not None and est != 0:
            sur = round((act - est) / abs(est) * 100, 2)
        if t > now:
            future.append([t, est, None, None])
        else:
            past.append([t, est, act, sur if act is not None else None])
    future.sort()
    return sorted(future[:1] + past, reverse=True)


def ratings(tk, now):
    """[[t, firm, action, from, to, pt_action, pt_now, pt_before], ...] newest first, last three years."""
    try:
        df = tk.upgrades_downgrades
    except Exception as ex:  # noqa: BLE001
        if "no upgrade" in str(ex).lower():
            return []
        raise
    if df is None or df.empty:
        return []
    since = iso(dt.datetime.now(dt.timezone.utc) - dt.timedelta(days=RATING_DAYS))
    out = []
    for ts, row in df.iterrows():
        t = iso(ts)                     # Yahoo gives epoch seconds; yfinance leaves them as naive UTC
        if t < since or t > now:
            continue
        out.append([t, text(row.get("Firm")), text(row.get("Action")).lower(), text(row.get("FromGrade")), text(row.get("ToGrade")),
                    text(row.get("priceTargetAction")), num(row.get("currentPriceTarget"), 2), num(row.get("priorPriceTarget"), 2)])
    return sorted(out, key=lambda r: r[0], reverse=True)


def splits(tk, now):
    """[[day, ratio], ...] oldest first, since 2004."""
    sp = tk.splits
    if sp is None:
        return []
    out = []
    for ts, r in sp.items():
        r = num(r, 6)
        if r and r > 0 and r != 1 and str(ts)[:4] >= "2004":
            out.append([iso(ts)[:10], r])
    return sorted(out)


def splits_due(old, now):
    got = old.get("splits_at")
    if not got or "splits" not in old:
        return True
    try:
        age = dt.datetime.fromisoformat(now.replace("Z", "+00:00")) - dt.datetime.fromisoformat(got.replace("Z", "+00:00"))
    except ValueError:
        return True
    return age.days >= SPLIT_DAYS


def attempt(fn, *args):
    """One try and one retry; a throttle is passed up so the run can back off."""
    for k in range(2):
        try:
            return fn(*args)
        except Exception as ex:  # noqa: BLE001
            if is_throttle(ex):
                raise Throttled(str(ex)) from ex
            if k == 1:
                raise
            time.sleep(2)


def fresh(path, hours=FRESH_HOURS):
    try:
        with open(path) as f:
            got = json.load(f).get("fetched")
        return got and (dt.datetime.now(dt.timezone.utc) - dt.datetime.fromisoformat(got.replace("Z", "+00:00"))).total_seconds() < hours * 3600
    except (OSError, ValueError, TypeError):
        return False


def main():
    import yfinance as yf
    args = [a for a in sys.argv[1:] if not a.startswith("--")]
    force = "--force" in sys.argv or bool(args)
    os.makedirs(OUT, exist_ok=True)
    todo = [t for t in TICKERS if not t.get("index") and not t.get("crypto") and os.path.exists(os.path.join(FUND, t["slug"] + ".json"))
            and (not args or t["sym"] in args or t["slug"] in args)]
    done = skipped = fails = n_earn = n_rate = changed = 0
    strikes = 0
    i = 0
    while i < len(todo):
        t = todo[i]
        path = os.path.join(OUT, t["slug"] + ".json")
        if not force and fresh(path):
            skipped += 1
            i += 1
            continue
        try:
            with open(path) as f:
                old = json.load(f)
        except (OSError, ValueError):
            old = {}
        now = iso(dt.datetime.now(dt.timezone.utc))
        tk = yf.Ticker(t["sym"])
        new = {"fetched": now, "earn": old.get("earn") or [], "ratings": old.get("ratings") or []}
        if "splits" in old:
            new["splits"], new["splits_at"] = old["splits"], old.get("splits_at")
        jobs = [("earn", earnings), ("ratings", ratings)] + ([("splits", splits)] if splits_due(old, now) else [])
        ok = 0
        try:
            for key, fn in jobs:
                try:
                    new[key] = attempt(fn, tk, now)
                    if key == "splits":
                        new["splits_at"] = now
                    ok += 1
                except Throttled:
                    raise
                except Exception as ex:  # noqa: BLE001
                    fails += 1
                    print(f"  {t['sym']}: {key} failed ({ex.__class__.__name__}: {str(ex)[:80]})")
                time.sleep(0.3)
        except Throttled as ex:
            if strikes >= len(BACKOFF):
                print(f"Yahoo is still throttling after {sum(BACKOFF)}s of waiting; stopping at {t['sym']}. Run again later to resume.")
                break
            wait = BACKOFF[strikes]
            strikes += 1
            print(f"  throttled at {t['sym']} ({str(ex)[:60]}); waiting {wait}s")
            time.sleep(wait)
            continue                    # same company again
        strikes = 0
        if ok:
            # rewrite only when something changed, so the nightly commit stays small
            if new["earn"] != old.get("earn") or new["ratings"] != old.get("ratings") or new.get("splits") != old.get("splits") or new.get("splits_at") != old.get("splits_at") or not old:
                with open(path, "w") as f:
                    json.dump(new, f, separators=(",", ":"), ensure_ascii=False)
                changed += 1
            done += 1
            n_earn += len(new["earn"])
            n_rate += len(new["ratings"])
        i += 1
        if i % 25 == 0:
            print(f"{i}/{len(todo)} companies", flush=True)
        time.sleep(PAUSE)
    print(f"events: {done} companies fetched ({changed} changed), {skipped} still fresh, {n_earn} earnings dates and {n_rate} rating changes, {fails} failures")


if __name__ == "__main__":
    main()
