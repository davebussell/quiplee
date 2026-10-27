#!/usr/bin/env python3
"""Be The Puck daily drafts: read the signal on your stocks and draft the orders YOUR rules call for.

    python bethepuck_drafts.py --dry-run      drafts only: prints them and saves a CSV, contacts no broker
    python bethepuck_drafts.py                also offers each draft to your Alpaca PAPER account, one at a time,
                                              and sends it only if you type "yes"

What it does, in order:
  1. Reads your rules from bethepuck_rules.json (next to this file, or --rules PATH).
  2. Asks Be The Puck's read API for each ticker's signal (https://bethepuck.com/developers/). With your member key in
     the BETHEPUCK_KEY environment variable it can use your own weights; without one it uses the free sample
     (the standard signal, 30 calls a day).
  3. Works out what you hold: from your Alpaca paper account if ALPACA_KEY_ID and ALPACA_SECRET_KEY are set (paper
     keys), otherwise from "holdings" in the rules file.
  4. Applies your rules (buy sizes are in each stock's own currency: U.S. dollars for U.S. listings, Canadian dollars
     for Toronto) and prints the drafts, and saves them to drafts-YYYY-MM-DD.csv so you can enter them at any
     broker by hand.
  5. Unless --dry-run, offers each draft for a U.S.-listed stock or fund to the Alpaca paper account. Nothing is sent
     unless you type "yes" for that order, at a terminal. Toronto-listed names, coins and indexes are drafts only.

It only ever talks to Alpaca's paper-trading address. It will not send an order to a live account: whether a rule is
ever used with real money is your decision, with your broker, and ideally an advisor.

Be The Puck is not a broker or an adviser and never places trades. This analysis does not constitute trading advice.
Please meet with an advisor or independently review sources before making any decision. You are responsible for every
order you send. Python 3.8 or newer; no packages to install. Keys go in environment variables, never in this file.
"""
import argparse
import csv
import datetime as dt
import json
import math
import os
import re
import sys
import urllib.error
import urllib.parse
import urllib.request

VERSION = "1.0 (Oct 27, 2026)"
SITE = "https://bethepuck.com"
PAPER = "https://paper-api.alpaca.markets"
DISCLAIMER = ("This analysis does not constitute trading advice. Please meet with an advisor or independently review "
              "sources before making any decision.")
DEFAULT_RULES = {
    "tickers": ["SPY", "MU", "NVDA"],
    "buy_when": "Buy",
    "sell_when": "Sell",
    "dollars_per_buy": 1000,
    "max_share_of_account": 0.10,
    "buys_when_market_guard_on": False,
    "account_value": 10000,
    "holdings": {},
    "weights": "",
    "buy_line": 60,
    "sell_line": 40,
}


def say(*a):
    print(*a, flush=True)


def money(x):
    return "–" if x is None else f"{x:,.2f}"


def http_json(url, headers=None, method="GET", body=None):
    """(status, parsed JSON or None, raw text) for one request; network trouble comes back as status 0."""
    data = json.dumps(body).encode() if body is not None else None
    h = {"accept": "application/json", "user-agent": "bethepuck-drafts/" + VERSION.split()[0]}
    h.update(headers or {})
    if data is not None:
        h["content-type"] = "application/json"
    req = urllib.request.Request(url, data=data, headers=h, method=method)
    try:
        with urllib.request.urlopen(req, timeout=30) as r:
            raw = r.read().decode("utf-8", "replace")
            status = r.status
    except urllib.error.HTTPError as err:
        raw, status = err.read().decode("utf-8", "replace"), err.code
    except (urllib.error.URLError, OSError) as err:
        return 0, None, str(err)
    try:
        return status, json.loads(raw), raw
    except ValueError:
        return status, None, raw


# ---------------------------------------------------------------- Be The Puck
def signal(site, ticker, key, rules):
    q = {}
    if key and rules.get("weights"):
        q = {"w": rules["weights"], "buy": rules.get("buy_line", 60), "sell": rules.get("sell_line", 40)}
    url = f"{site}/api/v1/stock/{urllib.parse.quote(ticker)}" + ("?" + urllib.parse.urlencode(q) if q else "")
    status, j, raw = http_json(url, {"authorization": "Bearer " + key} if key else None)
    if status != 200 or not j:
        why = (j or {}).get("error") or (j or {}).get("text") or raw[:200] or "no answer"
        return None, f"Be The Puck didn't answer for {ticker} ({status or 'network'}): {why}"
    return j, None


# ---------------------------------------------------------------- Alpaca (paper only)
def paper_base():
    base = os.environ.get("ALPACA_PAPER_URL", PAPER).rstrip("/")
    if base != PAPER and not re.match(r"^http://(localhost|127\.0\.0\.1)(:\d+)?$", base):
        sys.exit("This script only talks to Alpaca's paper-trading address (" + PAPER + "). It won't send orders anywhere else.")
    return base


class Paper:
    def __init__(self, key_id, secret):
        self.base = paper_base()
        self.h = {"APCA-API-KEY-ID": key_id, "APCA-API-SECRET-KEY": secret}

    def get(self, path):
        status, j, raw = http_json(self.base + path, self.h)
        if status != 200:
            sys.exit(f"Alpaca paper said {status or 'nothing'} for {path}: {raw[:200]}. Check your PAPER keys.")
        return j

    def account_value(self):
        return float(self.get("/v2/account").get("equity") or 0)

    def holdings(self):
        return {p["symbol"]: float(p.get("qty") or 0) for p in self.get("/v2/positions")}

    def open_orders(self):
        return [(o.get("symbol"), o.get("side")) for o in self.get("/v2/orders?status=open&limit=500")]

    def send(self, d):
        body = {"symbol": d["ticker"], "qty": str(d["qty"]), "side": d["side"], "type": "market", "time_in_force": "day",
                "client_order_id": f"btp-{d['ticker']}-{d['side']}-{dt.date.today():%Y%m%d}"}
        return http_json(self.base + "/v2/orders", self.h, "POST", body)


def sendable(j):
    """Alpaca takes U.S.-listed stocks and funds; Toronto names, coins and indexes stay drafts."""
    sym = j.get("symbol") or ""
    return j.get("market") in ("us", "fund") and bool(re.fullmatch(r"[A-Z]{1,5}", sym))


# ---------------------------------------------------------------- your rules
def draft(j, rules, held, value):
    """One draft order (or None) and a line saying why, from your rules alone."""
    t, sig, close, cur = j["symbol"], (j.get("signal") or ""), j.get("close"), j.get("currency") or ""
    have = held.get(t, 0)              # the same ticker as in your list: SHOP.TO, not SHOP
    if sig.lower() == str(rules["buy_when"]).lower() and have <= 0:
        if j.get("guard") and not rules.get("buys_when_market_guard_on"):
            return None, "reads " + sig + ", but the market guard is on and your rules skip buys then"
        size = min(float(rules["dollars_per_buy"]), float(rules["max_share_of_account"]) * value) if value else float(rules["dollars_per_buy"])
        if not close:
            return None, "no close to size the order from"
        qty = math.floor(size / close)
        if qty < 1:
            return None, f"reads {sig}, but one share ({close:,.2f} {cur}) costs more than your buy size ({size:,.0f} {cur})"
        return {"ticker": t, "side": "buy", "qty": qty, "price": close, "cur": cur, "why": f"signal {sig}, you hold none"}, "draft: buy"
    if sig.lower() == str(rules["sell_when"]).lower() and have > 0:
        qty = int(have) if float(have).is_integer() else have
        return {"ticker": t, "side": "sell", "qty": qty, "price": close, "cur": cur, "why": f"signal {sig}, you hold {have:g}"}, "draft: sell all"
    return None, f"reads {sig or 'nothing'}: nothing to do by your rules" + (f" (you hold {have:g})" if have else "")


def main():
    ap = argparse.ArgumentParser(description="Draft the orders your rules call for from Be The Puck's signal. Paper only.")
    ap.add_argument("--rules", default=os.path.join(os.path.dirname(os.path.abspath(__file__)), "bethepuck_rules.json"))
    ap.add_argument("--dry-run", action="store_true", help="print and save drafts only; contact no broker")
    ap.add_argument("--out", default="", help="folder for the drafts CSV (default: next to the rules file)")
    ap.add_argument("--site", default=os.environ.get("BETHEPUCK_SITE", SITE), help=argparse.SUPPRESS)
    a = ap.parse_args()

    say("Be The Puck daily drafts", VERSION)
    say(DISCLAIMER)
    say("Be The Puck is not a broker or an adviser and never places trades. You decide on every order.\n")
    if not os.path.exists(a.rules):
        with open(a.rules, "w", encoding="utf-8") as f:
            json.dump(DEFAULT_RULES, f, indent=2)
        say(f"No rules file yet, so one was written with placeholder numbers: {a.rules}\nSet your own rules in it and run this again.")
        return
    with open(a.rules, encoding="utf-8") as f:
        rules = {**DEFAULT_RULES, **json.load(f)}
    key = os.environ.get("BETHEPUCK_KEY", "").strip()
    site = a.site.rstrip("/")

    kid, sec = os.environ.get("ALPACA_KEY_ID", "").strip(), os.environ.get("ALPACA_SECRET_KEY", "").strip()
    paper = Paper(kid, sec) if (kid and sec and not a.dry_run) else None
    if paper:
        held, value, waiting = paper.holdings(), paper.account_value(), set(paper.open_orders())
        say(f"Alpaca PAPER account: worth {value:,.2f}, {len(held)} positions.")
    else:
        held = {str(k).upper(): float(v) for k, v in (rules.get("holdings") or {}).items()}
        value, waiting = float(rules.get("account_value") or 0), set()
        say("Drafts only: holdings and account value come from your rules file.")
    say(f"Signal from {site}" + (" with your member key" if key else " (free sample, standard signal)") + "\n")

    drafts, asof = [], ""
    for tk in rules["tickers"]:
        j, err = signal(site, str(tk).strip(), key, rules)
        if err:
            say("  " + err)
            continue
        asof = j.get("as_of") or asof
        d, why = draft(j, rules, held, value)
        extra = " · ".join(x for x in [j.get("held_words"), j.get("guard_words")] if x)
        say(f"{j['symbol']:<9} {j.get('signal', '?'):<5} score {j.get('score', '?')!s:<4} {why}")
        if extra:
            say("          " + extra)
        if d:
            d["sendable"] = bool(paper) and sendable(j)
            d["note"] = "" if sendable(j) else "not a U.S. listing: enter it at your broker"
            drafts.append(d)

    say("")
    if not drafts:
        say(f"No drafts: your rules call for nothing at the {asof} close.")
        return
    out = a.out or os.path.dirname(os.path.abspath(a.rules))
    path = os.path.join(out, f"drafts-{dt.date.today():%Y-%m-%d}.csv")
    with open(path, "w", newline="", encoding="utf-8") as f:
        w = csv.writer(f)
        w.writerow(["ticker", "side", "quantity", "last_close", "currency", "order_type", "why", "note", "signal_close_date"])
        for d in drafts:
            w.writerow([d["ticker"], d["side"], d["qty"], d["price"], d["cur"], "market, day", d["why"], d["note"], asof])
    say(f"{len(drafts)} draft(s) saved to {path}")

    if not paper:
        say("Nothing was sent anywhere. Enter any order you decide on at your broker yourself.")
        return
    if not sys.stdin.isatty():
        say("No terminal to confirm at, so nothing was sent. Run it yourself to approve orders one by one.")
        return
    for d in drafts:
        if not d["sendable"]:
            say(f"  {d['ticker']}: draft only ({d['note']}).")
            continue
        if (d["ticker"], d["side"]) in waiting:
            say(f"  {d['ticker']}: an open {d['side']} order is already waiting in the paper account; skipped.")
            continue
        ans = input(f"Send to your Alpaca PAPER account: {d['side'].upper()} {d['qty']} {d['ticker']} at market (last close "
                    f"{money(d['price'])})? Type yes to send: ").strip()
        if ans != "yes":
            say("  Not sent.")
            continue
        status, j, raw = paper.send(d)
        if status in (200, 201) and j:
            say(f"  Sent to paper: order {j.get('id', '?')}, status {j.get('status', '?')}.")
        else:
            say(f"  Alpaca paper refused it ({status}): {raw[:200]}")
    say("\nDone. Check the paper account in Alpaca's dashboard. " + DISCLAIMER)


if __name__ == "__main__":
    main()
