#!/usr/bin/env python3
"""Keep a running archive of the news on every covered stock, for the markers on
each stock page's chart: data/news/<slug>.json.

Two sources, both free and public:
  - SEC EDGAR: every 8-K a U.S. company files (earnings releases, deals, executive
    changes...), from data.sec.gov's submissions API. Goes back two years, so the
    chart has history from the first run.
  - Google News RSS: the last week's headlines per stock (the same feed the live
    desk reads). Each nightly run adds the new ones, so the archive grows.

Each file is {"items": [{t, h, s, u, k, ty}]}: t = when it was published (ISO, UTC),
h = headline, s = source, u = link, k = "sec" or "news", ty = story type. Items
older than two years are dropped; a stock keeps its 40 latest filings and 60
latest headlines. A source that fails leaves the old items in place.

    python tools/fetch_news.py               # every stock, both sources
    python tools/fetch_news.py --no-google   # filings only
    python tools/fetch_news.py NVDA AAPL     # just these
"""
import datetime as dt
import email.utils
import html
import json
import os
import re
import sys
import time
import urllib.parse
import urllib.request

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from qstrat.content import TICKERS  # noqa: E402

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
OUT = os.path.join(ROOT, "data", "news")
UA = "Be The Puck news archive (bethepuck.com; dave@clickshift.ca)"
KEEP_DAYS = 730
MAX_SEC, MAX_NEWS = 40, 60

# 8-K items, most telling first. The lead item names the filing; filings with only
# boilerplate items (exhibits, shareholder votes, bylaw changes) are skipped.
ITEMS = [
    ("2.02", "reports quarterly results", "Earnings"),
    ("1.01", "signs a material agreement", "M&A"),
    ("2.01", "completes an acquisition or sale", "M&A"),
    ("1.02", "ends a material agreement", "M&A"),
    ("2.05", "announces restructuring costs", "Restructuring"),
    ("2.06", "reports a material impairment", "Legal"),
    ("4.02", "says past financials can't be relied on", "Legal"),
    ("3.01", "gets a listing-standards notice", "Regulatory"),
    ("5.02", "reports an executive or board change", "Leadership"),
    ("2.03", "takes on a new financial obligation", "Financing"),
    ("3.02", "sells unregistered shares", "Financing"),
    ("8.01", "reports another material event", "Company news"),
    ("7.01", "makes a public disclosure (Reg FD)", "Company news"),
]
ITEM = {c: (lab, ty) for c, lab, ty in ITEMS}
RANK = {c: i for i, (c, _, _) in enumerate(ITEMS)}


def get(url, accept="*/*", tries=3):
    for k in range(tries):
        try:
            req = urllib.request.Request(url, headers={"User-Agent": UA, "Accept": accept})
            with urllib.request.urlopen(req, timeout=20) as r:
                return r.read().decode("utf-8", "replace")
        except Exception as ex:  # noqa: BLE001
            code = getattr(ex, "code", None)
            if code in (404, 400):
                return None
            if k == tries - 1:
                raise
            time.sleep(2 + 3 * k)


def iso(d):
    return d.astimezone(dt.timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")


# ------------------------------------------------------------------ SEC EDGAR
_CIKS = None


def ciks():
    global _CIKS
    if _CIKS is None:
        j = json.loads(get("https://www.sec.gov/files/company_tickers.json", "application/json") or "{}")
        _CIKS = {v["ticker"].upper(): int(v["cik_str"]) for v in j.values()}
    return _CIKS


def sec_items(t, since):
    cik = ciks().get(t["sym"].upper().replace(".", "-")) or ciks().get(t["sym"].upper())
    if not cik:
        return None
    txt = get(f"https://data.sec.gov/submissions/CIK{cik:010d}.json", "application/json")
    if not txt:
        return None
    r = json.loads(txt)["filings"]["recent"]
    out = []
    for i, form in enumerate(r["form"]):
        if form != "8-K":
            continue
        when = dt.datetime.fromisoformat(r["acceptanceDateTime"][i].replace("Z", "+00:00"))
        if when < since:
            break                      # newest first
        codes = [c.strip() for c in (r["items"][i] or "").split(",") if c.strip() in ITEM]
        if not codes:
            continue
        lead = min(codes, key=lambda c: RANK[c])
        acc = r["accessionNumber"][i]
        url = f"https://www.sec.gov/Archives/edgar/data/{cik}/{acc.replace('-', '')}/{r['primaryDocument'][i] or acc + '-index.htm'}"
        out.append({"t": iso(when), "h": f"{t['short_name']} {ITEM[lead][0]}", "s": "SEC filing (8-K)",
                    "u": url, "k": "sec", "ty": ITEM[lead][1], "it": ",".join(sorted(codes, key=lambda c: RANK[c]))})
    return out


# ------------------------------------------------------------------ Google News
def field(block, tag):
    m = re.search(rf"<{tag}[^>]*>([\s\S]*?)</{tag}>", block)
    return html.unescape(re.sub(r"<[^>]+>", "", m.group(1))).strip() if m else ""


def google_items(t):
    q = f'"{t["query"]}" stock when:7d'
    url = "https://news.google.com/rss/search?" + urllib.parse.urlencode({"q": q, "hl": "en-US", "gl": "US", "ceid": "US:en"})
    xml = get(url, "application/rss+xml")
    if not xml:
        return None
    out = []
    for b in re.findall(r"<item\b[\s\S]*?</item>", xml)[:10]:
        title, src, link, pub = field(b, "title"), field(b, "source"), field(b, "link"), field(b, "pubDate")
        if src and title.endswith(" - " + src):
            title = title[: -len(src) - 3]
        elif not src and " - " in title:
            title, src = title.rsplit(" - ", 1)
        try:
            when = email.utils.parsedate_to_datetime(pub)
        except (TypeError, ValueError):
            continue
        if len(title) < 12:
            continue
        out.append({"t": iso(when), "h": title, "s": src or "Google News", "u": link, "k": "news", "ty": "News"})
    return out


# ------------------------------------------------------------------ merge
def key(it):
    return it["k"] + "|" + (it["u"] if it["k"] == "sec" else re.sub(r"[^a-z0-9]+", " ", it["h"].lower()).strip()[:100])


def merge(old, new, since):
    seen, out = set(), []
    for it in sorted(new + old, key=lambda x: x["t"], reverse=True):
        k = key(it)
        if k in seen or it["t"] < iso(since):
            continue
        seen.add(k)
        out.append(it)
    sec = [x for x in out if x["k"] == "sec"][:MAX_SEC]
    news = [x for x in out if x["k"] == "news"][:MAX_NEWS]
    return sorted(sec + news, key=lambda x: x["t"], reverse=True)


def short_name(t):
    n = re.sub(r",? (Inc\.?|Corp\.?|Corporation|Co\.|Company|Ltd\.?|Limited|plc|N\.V\.|S\.A\.|Holdings?|Group)$", "", t["name"]).strip()
    return n or t["short"]


def main():
    args = [a for a in sys.argv[1:] if not a.startswith("--")]
    use_google = "--no-google" not in sys.argv
    os.makedirs(OUT, exist_ok=True)
    since = dt.datetime.now(dt.timezone.utc) - dt.timedelta(days=KEEP_DAYS)
    todo = [t for t in TICKERS if not t.get("index") and (not args or t["sym"] in args or t["slug"] in args)]
    n_sec = n_news = fails = 0
    for i, t in enumerate(todo):
        t = dict(t, short_name=short_name(t), query=short_name(t))
        path = os.path.join(OUT, t["slug"] + ".json")
        try:
            old = json.load(open(path))["items"]
        except (OSError, ValueError, KeyError):
            old = []
        new = []
        if not t.get("crypto") and not t["sym"].endswith((".TO", ".V", ".NE", ".CN")):
            try:
                got = sec_items(t, since)
                if got:
                    new += got
                    n_sec += len(got)
            except Exception as ex:  # noqa: BLE001
                fails += 1
                print(f"  {t['sym']}: SEC failed ({ex.__class__.__name__})")
            time.sleep(0.15)           # SEC asks for no more than 10 requests a second
        if use_google:
            try:
                got = google_items(t)
                if got:
                    new += got
                    n_news += len(got)
            except Exception as ex:  # noqa: BLE001
                fails += 1
                print(f"  {t['sym']}: Google News failed ({ex.__class__.__name__})")
            time.sleep(0.6)
        items = merge(old, new, since)
        if items != old:
            with open(path, "w") as f:
                json.dump({"items": items}, f, separators=(",", ":"), ensure_ascii=False)
        if (i + 1) % 50 == 0:
            print(f"{i + 1}/{len(todo)} stocks")
    print(f"news archive: {len(todo)} stocks, {n_sec} filings and {n_news} headlines read, {fails} source failures")


if __name__ == "__main__":
    main()
