#!/usr/bin/env python3
"""Claude reads each earnings press release (8-K Exhibit 99.1) into structured fields.

The SEC's XBRL numbers (tools/fetch_sec.py) don't say what a company expects next. The
press release does: guidance raised, kept, cut, started or withdrawn, and one-off items.
For every covered company with a new earnings 8-K (Item 2.02, listed in data/sec/<slug>.json),
this downloads the press release, asks Claude to record what it says with a fixed schema,
and keeps the answer in data/earnings/<slug>.json, keyed by the filing's accession number:

    {"<accession>": {"filed", "at", "doc", "model", "read", "period", "revenue_m", "eps", "eps_adj",
                     "guidance": [{"metric", "period", "low", "high", "unit", "said"}],
                     "dir": "raised"|"cut"|"kept"|"started"|"withdrawn"|"mixed"|"none",
                     "one_offs": [...], "tone", "headline"}}

"dir" is the release's overall guidance direction: what the company says it did ("said"),
or, when it gives a range without saying, the change from the same metric and period in its
previous release. News that moves stocks measures how stocks moved on each kind
(tools/qstrat/newsevents.py), and the stock page shows the latest headline.

Needs ANTHROPIC_API_KEY (a GitHub Actions secret); without it, it does nothing.

    python tools/fetch_earnings.py               # the newest unread release of each company
    python tools/fetch_earnings.py --backfill 8  # up to the last 8 releases each (a one-off history)
    python tools/fetch_earnings.py MU NVDA
"""
import datetime as dt
import html as htmlmod
import json
import os
import re
import sys
import time
import urllib.error
import urllib.request

HERE = os.path.dirname(os.path.abspath(__file__))
ROOT = os.path.dirname(HERE)
sys.path.insert(0, HERE)
from qstrat.content import TICKERS  # noqa: E402
from fetch_sec import UA  # noqa: E402

SEC_DIR = os.path.join(ROOT, "data", "sec")
OUT = os.path.join(ROOT, "data", "earnings")
MODEL = os.environ.get("EARNINGS_MODEL", "claude-sonnet-5-5")
MAX_PER_RUN = int(os.environ.get("EARNINGS_MAX", "60"))   # bounds the cost of one run
MAX_CHARS = 120_000

TOOL = {
    "name": "record_results",
    "description": "Record what this earnings press release says. Use only facts stated in the release; never estimate or infer numbers.",
    "input_schema": {
        "type": "object",
        "properties": {
            "period": {"type": "string", "description": "The period reported, e.g. 'Q3 FY2026 (quarter ended Sep 28, 2026)'."},
            "revenue_m": {"type": ["number", "null"], "description": "Revenue for the period in millions of the reporting currency, or null."},
            "eps": {"type": ["number", "null"], "description": "GAAP diluted EPS for the period, or null."},
            "eps_adj": {"type": ["number", "null"], "description": "Adjusted (non-GAAP) diluted EPS for the period if given, else null."},
            "guidance": {
                "type": "array",
                "description": "Every forward-looking range or figure the company gives for a future period (revenue, EPS, margin, capex...). Empty if none.",
                "items": {
                    "type": "object",
                    "properties": {
                        "metric": {"type": "string", "description": "revenue, eps, eps_adj, gross_margin, operating_margin, capex, other: <name>"},
                        "period": {"type": "string", "description": "The future period, normalised like 'Q4 FY2026' or 'FY2026'."},
                        "low": {"type": ["number", "null"]}, "high": {"type": ["number", "null"]},
                        "unit": {"type": "string", "description": "millions, per share, percent, ..."},
                        "said": {"type": "string", "enum": ["raised", "lowered", "reaffirmed", "new", "withdrawn", "unspecified"],
                                 "description": "What the release itself says about this outlook versus the previous one. 'unspecified' if it doesn't say."},
                    },
                    "required": ["metric", "period", "said"],
                },
            },
            "withdrew_guidance": {"type": "boolean", "description": "True if the company withdrew or suspended its outlook."},
            "one_offs": {"type": "array", "items": {"type": "string"}, "description": "Unusual items the release names (impairments, gains, charges), each under 15 words."},
            "tone": {"type": "string", "enum": ["positive", "neutral", "negative"], "description": "The release's overall message about the business, not the stock."},
            "headline": {"type": "string", "description": "One plain sentence under 22 words: what the company reported and what it expects. No adjectives like 'strong' unless the release's numbers show it."},
        },
        "required": ["period", "guidance", "withdrew_guidance", "one_offs", "tone", "headline"],
    },
}
SYSTEM = ("You read company earnings press releases and record what they say, accurately and literally. "
          "Numbers must appear in the release. If something isn't stated, use null or 'unspecified'. Never give investment opinions.")


def get(url, binary=False):
    for i in range(4):
        try:
            req = urllib.request.Request(url, headers={"User-Agent": UA})
            with urllib.request.urlopen(req, timeout=60) as r:
                data = r.read()
            time.sleep(0.15)
            return data if binary else data.decode("utf-8", "replace")
        except urllib.error.HTTPError as ex:
            if ex.code == 404:
                return None
            time.sleep(2 + 3 * i)
        except Exception:
            time.sleep(2 + 3 * i)
    return None


def press_release(cik, acc, primary):
    """The text of the filing's Exhibit 99.1 (the press release), found from the filing index's document types."""
    base = f"https://www.sec.gov/Archives/edgar/data/{cik}/{acc.replace('-', '')}/"
    doc = None
    page = get(base + f"{acc}-index.htm")
    if page:
        for row in re.findall(r"(?is)<tr[^>]*>(.*?)</tr>", page):
            href = re.search(r'href="[^"]*/([^"/]+\.html?)"', row)
            if href and re.search(r">\s*EX-99\.?0?1\s*<", row):
                doc = href.group(1)
                break
    if not doc:      # no typed index: guess from the file names
        idx = get(base + "index.json")
        names = [i["name"] for i in json.loads(idx)["directory"]["item"]] if idx else []
        pick = [n for n in names if re.search(r"ex[-_ ]?99[-_.]?0?1|ex991", n, re.I)]
        doc = pick[0] if pick else None
    if not doc:
        return None, None
    raw = get(base + doc)
    return (to_text(raw) if raw else None), doc


def to_text(raw):
    s = re.sub(r"(?is)<(script|style)\b.*?</\1>", " ", raw)
    s = re.sub(r"(?i)</t[dh]>", " | ", s)
    s = re.sub(r"(?i)<br\s*/?>|</(p|div|tr|li|h\d)>", "\n", s)
    s = re.sub(r"<[^>]+>", " ", s)
    s = htmlmod.unescape(s).replace("\xa0", " ")
    s = re.sub(r"[ \t]+", " ", s)
    s = re.sub(r"( ?\| ?)+\n", "\n", s)
    s = re.sub(r"\n\s*\n+", "\n", s)
    return s.strip()[:MAX_CHARS]


def ask_claude(text, company):
    body = {"model": MODEL, "max_tokens": 2000, "system": SYSTEM, "tools": [TOOL],
            "tool_choice": {"type": "tool", "name": TOOL["name"]},
            "messages": [{"role": "user", "content": f"Company: {company}\n\nEarnings press release:\n\n{text}"}]}
    req = urllib.request.Request("https://api.anthropic.com/v1/messages", data=json.dumps(body).encode(), method="POST",
                                 headers={"x-api-key": os.environ["ANTHROPIC_API_KEY"], "anthropic-version": "2023-06-01",
                                          "content-type": "application/json"})
    for i in range(3):
        try:
            with urllib.request.urlopen(req, timeout=180) as r:
                d = json.loads(r.read().decode())
            for c in d.get("content", []):
                if c.get("type") == "tool_use":
                    return c["input"]
            return None
        except urllib.error.HTTPError as ex:
            msg = ex.read().decode()[:300]
            if ex.code in (429, 500, 529):
                time.sleep(10 * (i + 1))
                continue
            print(f"  Claude API {ex.code}: {msg}")
            return None
        except Exception as ex:
            print("  Claude API:", ex)
            time.sleep(5)
    return None


def direction(rec, earlier):
    """The release's overall guidance direction: what it says, else the change in the same metric and period."""
    if rec.get("withdrew_guidance"):
        return "withdrawn"
    said = set()
    for g in rec.get("guidance") or []:
        s = g.get("said")
        if s in ("unspecified", None):
            prev = next((p for e in earlier for p in (e.get("guidance") or [])
                         if p.get("metric") == g.get("metric") and p.get("period") == g.get("period")), None)
            mid = lambda x: ((x.get("low") or x.get("high") or 0) + (x.get("high") or x.get("low") or 0)) / 2
            if prev and mid(prev):
                ch = mid(g) / mid(prev) - 1
                s = "raised" if ch > 0.01 else "lowered" if ch < -0.01 else "reaffirmed"
            else:
                s = "new"
        said.add(s)
    if not said:
        return "none"
    if "withdrawn" in said:
        return "withdrawn"
    if "raised" in said and "lowered" in said:
        return "mixed"
    if "raised" in said:
        return "raised"
    if "lowered" in said:
        return "cut"
    if "reaffirmed" in said:
        return "kept"
    return "started"


def main(argv):
    if not os.environ.get("ANTHROPIC_API_KEY"):
        print("earnings: ANTHROPIC_API_KEY not set, nothing read")
        return
    os.makedirs(OUT, exist_ok=True)
    back = 1
    if "--backfill" in argv:
        back = int(argv[argv.index("--backfill") + 1])
    want = [a.upper() for a in argv if not a.startswith("--") and not a.isdigit()]
    done = 0
    t0 = time.time()
    for t in TICKERS:
        if want and t["sym"].upper() not in want:
            continue
        sp = os.path.join(SEC_DIR, t["slug"] + ".json")
        if not os.path.exists(sp):
            continue
        sec = json.load(open(sp))
        path = os.path.join(OUT, t["slug"] + ".json")
        have = json.load(open(path)) if os.path.exists(path) else {}
        todo = [e for e in (sec.get("earn") or [])[:back] if e[1] not in have]
        for e in reversed(todo):              # oldest first, so "said: unspecified" can compare with the release before
            if done >= MAX_PER_RUN:
                break
            filed, acc, primary = e[0], e[1], e[2]
            text, doc = press_release(sec["cik"], acc, primary)
            if not text or len(text) < 500:
                have[acc] = {"filed": filed, "at": e[3] if len(e) > 3 else None, "doc": doc, "skip": "no press release text"}
                continue
            rec = ask_claude(text, t["name"])
            if not rec:
                continue
            earlier = [v for k, v in sorted(have.items(), key=lambda kv: kv[1].get("filed", "")) if v.get("filed", "") < filed and not v.get("skip")]
            rec["dir"] = direction(rec, earlier[::-1])
            rec.update({"filed": filed, "at": e[3] if len(e) > 3 else None, "doc": doc, "model": MODEL, "read": dt.date.today().isoformat(),
                        "url": f"https://www.sec.gov/Archives/edgar/data/{sec['cik']}/{acc.replace('-', '')}/{doc}"})
            have[acc] = rec
            done += 1
            print(f"  {t['sym']} {filed}: {rec['dir']} · {rec.get('headline', '')[:90]}")
        if have:
            with open(path, "w") as f:
                json.dump(have, f, indent=1, ensure_ascii=False)
    print(f"earnings: read {done} press releases with {MODEL} in {time.time() - t0:.0f}s")


if __name__ == "__main__":
    main(sys.argv[1:])
