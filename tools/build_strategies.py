"""Build Be The Puck's plays site from the cached prices.

    pip install -r requirements.txt
    python tools/fetch_prices.py                 # refresh data/prices/ (network; nightly in CI)
    python tools/build_strategies.py             # build the whole site into _site/ (no network)
    python tools/build_strategies.py --out DIR --preview   # local preview with explicit index.html links

Netlify runs the second command on every push (see netlify.toml) and publishes
_site/. The build copies the hand-written parts of the site (live desk,
stories, assets, js) unchanged apart from glossary links, then generates the
home page, /markets/ (crash gauges and the plays on indexes), /watchlist/,
/articles/, /strategies/ (plays), /thinkers/ (analysts), /stocks/ (every stock x
play page), /learn/ (three tracks), /method/, data/*.json and sitemap.xml.
Edit tools/qstrat/plays.py for plays, analysts.json for analysts, content.py
for tickers.
"""
import argparse
import json
import os
import shutil
import sys
import tempfile
import time

HERE = os.path.dirname(os.path.abspath(__file__))
ROOT = os.path.dirname(HERE)
sys.path.insert(0, HERE)

from qstrat import engine  # noqa: E402
from qstrat.render import Site  # noqa: E402
from qstrat.glossary import GLOSSARY, BY_SLUG  # noqa: E402
from qstrat.linker import link_terms  # noqa: E402
from qstrat.practice import build_practice, practice_json  # noqa: E402

# Hand-written pages that also get glossary links (in the output copy only).
STATIC_LINKED = {"stories": "/assets/glossary.js", "desk": "../assets/glossary.js"}
GENERATED = {"index.html", "sitemap.xml", "strategies", "thinkers", "stocks", "method", "learn", "markets", "watchlist", "articles",
             "picks", "members", "locked", "theory", "alerts", "rules", "guides", "me"}
GENERATED_DATA = {"signals.json", "glossary.json", "practice.json", "watch.json", "names.json", "plays.json", "tickers.json", "screen.json", "reads.json", "theory", "hist"}
NOT_PUBLISHED = {".git", ".github", ".ship", ".netlify", "netlify", "tools", "node_modules", "_site", "__pycache__",
                 "netlify.toml", "requirements.txt", "README.md", "BRAND.md", ".gitignore", "SHIP-QUIPLEE.cmd",
                 "package.json", "package-lock.json"}


def root_href(slug):
    g = BY_SLUG[slug]
    if g.get("lesson"):
        lesson, _, anchor = g["lesson"].partition("#")
        return f"/learn/{lesson}/#{anchor}"
    return f"/learn/glossary/#{slug}"


def glossary_json():
    # On the live desk, news headlines use some words in their everyday sense ("suppliers signal...",
    # "a breakout quarter"), so site-mechanics and pattern terms are left out of the desk's in-browser linking.
    not_on_desk = {"signal", "in-out", "band", "next-move", "next-check", "closing-price", "breakout", "pullback",
                   "channel", "indicator", "seasonality", "exhaustion", "trailing-stop", "trading-volume"}
    terms = [{"slug": g["slug"], "term": g["term"], "tip": g["tip"], "href": root_href(g["slug"]), "aliases": g["aliases"]}
             for g in GLOSSARY if g["slug"] not in not_on_desk]
    return json.dumps({"terms": terms}, ensure_ascii=False, indent=1)


def copy_static(out):
    """Copy every hand-written file the site serves into the output folder."""
    for name in os.listdir(ROOT):
        if name in NOT_PUBLISHED or name in GENERATED or name.startswith("."):
            continue
        src, dst = os.path.join(ROOT, name), os.path.join(out, name)
        if os.path.isdir(src):
            if name == "data":
                os.makedirs(dst, exist_ok=True)
                for f in os.listdir(src):
                    if f == "prices" or f in GENERATED_DATA:
                        continue
                    s2 = os.path.join(src, f)
                    (shutil.copytree if os.path.isdir(s2) else shutil.copy2)(s2, os.path.join(dst, f))
                continue
            shutil.copytree(src, dst, ignore=shutil.ignore_patterns("__pycache__", ".DS_Store"))
        else:
            shutil.copy2(src, dst)


def reads_json(site):
    """Each covered name's Start/Stop light and its plain-English read, for the alert emails."""
    from qstrat import stockview as sv
    from qstrat.content import TICKERS
    out = {}
    for t in TICKERS:
        sym = t["sym"]
        if t.get("index") or (sym, "buy-and-hold") not in site.R:
            continue
        L = site.light(t)
        meta = site.meta.get(sym)
        try:
            read = sv.read_lines(site, t, meta, site.fund.get(sym)) if meta else []
        except Exception:
            read = []
        oh = (meta or {}).get("ohlc")
        d1 = float(oh["close"].iloc[-1] / oh["close"].iloc[-2] - 1) if oh is not None and len(oh) > 1 else None
        out[sym] = {"n": t["name"], "s": t["short"], "u": t["slug"], "cur": t["cur"], "p": round(float(site.r(sym, "buy-and-hold")["price"]), 4),
                    "g": t["group"], "d1": None if d1 is None else round(d1, 5),
                    "L": None if not L["state"] else (1 if L["state"] == "start" else 0), "k": L["k"], "of": L["n"],
                    "since": L["since"].strftime("%Y-%m-%d") if L.get("since") is not None else None, "read": read}
    return json.dumps({"asof": site.asof.strftime("%Y-%m-%d"), "t": out}, ensure_ascii=False, separators=(",", ":"))


def static_footer():
    """The site footer (disclaimer, Click Shift credit, Proudly Canadian) for the hand-written
    pages, with its own styles since they use a different stylesheet."""
    from qstrat.render import FOOT_DISCLAIM, FOOT_CREDITS
    css = ("<style>.bp-foot{border-top:1px solid #232d42;background:#0b0f17;color:#8a95a9;font:13px/1.55 Geist,-apple-system,'Segoe UI',Roboto,sans-serif}"
           ".bp-foot .in{max-width:1160px;margin:0 auto;padding:20px 16px 36px;display:flex;flex-direction:column;gap:12px}"
           ".bp-foot p{margin:0}.bp-foot .foot-disclaim{color:#c3cad8;padding:12px 14px;border:1px solid #232d42;border-radius:10px;background:#131927}"
           ".bp-foot .foot-disclaim b{color:#eef2f9}.bp-foot .foot-credits{display:flex;flex-wrap:wrap;align-items:center;gap:12px 26px}"
           ".bp-foot .foot-credits a{display:inline-flex;align-items:center;gap:9px;color:#c3cad8;text-decoration:none}"
           ".bp-foot .cs-mark{display:inline-flex;align-items:center;gap:6px;line-height:1}.bp-foot .cs-click svg{width:17px;height:17px;display:block}"
           ".bp-foot .cs-shift{display:inline-flex;align-items:center;gap:5px;font:600 11.5px/1 ui-monospace,Menlo,monospace;letter-spacing:.5px;color:#0c0d10;"
           "background:#ffd400;border-radius:7px;padding:5px 10px 6px;box-shadow:0 2px 0 #b89700,inset 0 1px 0 rgba(255,255,255,.35)}"
           ".bp-foot .cs-shift:before{content:'\\21E7';font-size:13px}.bp-foot .maple{width:17px;height:17px;color:#e0b13a}</style>")
    return f'{css}<footer class="bp-foot"><div class="in">{FOOT_DISCLAIM}{FOOT_CREDITS}</div></footer>'


def link_static_pages(out):
    """Glossary-link the Stories pages and the live desk shell (in the output copy)."""
    done = []
    for folder, script_src in STATIC_LINKED.items():
        d = os.path.join(out, folder)
        if not os.path.isdir(d):
            continue
        for name in sorted(os.listdir(d)):
            if not name.endswith(".html"):
                continue
            fp = os.path.join(d, name)
            with open(fp, encoding="utf-8") as f:
                html = f.read()
            i = html.find("<body")
            if i < 0:
                continue
            new = html[:i] + link_terms(html[i:], root_href)
            if "glossary.js" not in new:
                j = new.rfind("</body>")
                new = new[:j] + f'<script src="{script_src}" defer></script>\n' + new[j:]
            if "bp-foot" not in new:
                j = new.rfind("</body>")
                new = new[:j] + static_footer() + "\n" + new[j:]
            if new != html:
                with open(fp, "w", encoding="utf-8") as f:
                    f.write(new)
            done.append(f"{folder}/{name}")
    return done


def write_pages(pages, out):
    for path, html in pages.items():
        d = os.path.join(out, path)
        os.makedirs(d, exist_ok=True)
        with open(os.path.join(d, "index.html"), "w", encoding="utf-8") as f:
            f.write(html)


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--out", default=os.path.join(ROOT, "_site"), help="output folder (default: _site)")
    ap.add_argument("--preview", action="store_true", help="spell out index.html in links, for file:// or plain static hosts")
    ap.add_argument("--workers", type=int, default=None)
    args = ap.parse_args()
    out = os.path.abspath(args.out)

    t0 = time.time()
    prices, irx, now = engine.load_all()
    print(f"loaded {len(prices)} tickers (closes to {max(d.index[-1] for d in prices.values()).date()})")
    # the bulky part of each result (chart windows, call lists) waits on disk until its page is made
    spill = os.environ.get("QSTRAT_SPILL") or tempfile.mkdtemp(prefix="qstrat-spill-")
    results = engine.run(prices, irx, now, workers=args.workers, spill=spill)
    meta = {k[0]: results.pop(k) for k in [k for k in results if k[1] == "__meta"]}
    print(f"evaluated {len(results)} play x ticker pairs in {time.time() - t0:.0f}s")

    # the hand-written files go in first; each generated page is then written as it is made
    shutil.rmtree(out, ignore_errors=True)
    os.makedirs(out)
    copy_static(out)

    t1 = time.time()
    site = Site(results, preview=args.preview, prices=prices, irx=irx, meta=meta)
    site.out = out
    pages = site.build()
    print(f"rendered and wrote {len(pages)} pages in {time.time() - t1:.0f}s")
    write_pages({k: v for k, v in pages.items() if v is not None}, out)
    os.makedirs(os.path.join(out, "data"), exist_ok=True)
    with open(os.path.join(out, "data", "signals.json"), "w") as f:
        f.write(site.signals_json())
    with open(os.path.join(out, "data", "glossary.json"), "w", encoding="utf-8") as f:
        f.write(glossary_json())
    with open(os.path.join(out, "data", "names.json"), "w", encoding="utf-8") as f:
        f.write(site.names_json())
    with open(os.path.join(out, "data", "plays.json"), "w", encoding="utf-8") as f:
        f.write(site.plays_json())
    with open(os.path.join(out, "data", "reads.json"), "w", encoding="utf-8") as f:
        f.write(reads_json(site))
    from qstrat import screen, theory
    with open(os.path.join(out, "data", "tickers.json"), "w", encoding="utf-8") as f:
        f.write(screen.tickers_json(site))
    with open(os.path.join(out, "data", "screen.json"), "w", encoding="utf-8") as f:
        f.write(screen.screen_json(site))
    t2 = time.time()
    os.makedirs(os.path.join(out, "data", "theory"), exist_ok=True)
    tfiles = getattr(site, "theory_json", None) or theory.files(site)
    for slug, js in tfiles.items():
        with open(os.path.join(out, "data", "theory", slug + ".json"), "w", encoding="utf-8") as f:
            f.write(js)
    print(f"theory tester: {len(tfiles)} stocks in {time.time() - t2:.0f}s")
    from qstrat.watchlist import watch_json
    from qstrat.rules import write_hist
    print("weekly call history files:", write_hist(site, out))
    with open(os.path.join(out, "data", "watch.json"), "w", encoding="utf-8") as f:
        f.write(watch_json(site))
    t2 = time.time()
    items = build_practice(prices, irx, now)
    with open(os.path.join(out, "data", "practice.json"), "w", encoding="utf-8") as f:
        f.write(practice_json(items))
    print(f"built {len(items)} practice charts in {time.time() - t2:.0f}s")
    with open(os.path.join(out, "sitemap.xml"), "w") as f:
        f.write(site.sitemap())
    print("glossary-linked:", ", ".join(link_static_pages(out)))
    if not os.environ.get("QSTRAT_SPILL"):
        shutil.rmtree(spill, ignore_errors=True)
    print(f"wrote the site to {out} in {time.time() - t0:.0f}s")


if __name__ == "__main__":
    main()
