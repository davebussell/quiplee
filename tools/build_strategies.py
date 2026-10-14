"""Build Be The Puck's plays site from the cached prices.

    pip install -r requirements.txt
    python tools/fetch_prices.py                 # refresh data/prices/ (network; nightly in CI)
    python tools/build_strategies.py             # build the whole site into _site/ (no network)
    python tools/build_strategies.py --out DIR --preview   # local preview with explicit index.html links

Netlify runs the second command on every push (see netlify.toml) and publishes
_site/. The build copies the hand-written parts of the site (live desk,
stories, assets, js) unchanged apart from glossary links, then generates the
home page, /markets/ (crash gauges and the plays on indexes), /watchlist/,
/articles/, /strategies/ (plays), /thinkers/ (analysts), /stocks/ (each stock, its
headline-play pages and every play on SPY), /learn/ (three tracks), /method/, data/*.json and sitemap.xml.
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
GENERATED = {"index.html", "404.html", "sitemap.xml", "strategies", "thinkers", "stocks", "method", "learn", "markets", "watchlist", "articles",
             "picks", "members", "locked", "theory", "alerts", "rules", "guides", "me", "owner"}
GENERATED_DATA = {"signals.json", "glossary.json", "practice.json", "watch.json", "names.json", "plays.json", "tickers.json", "screen.json", "reads.json", "theory", "hist",
                  "playset.json", "events.json", "events", "build.json", "quality.json", "factorgrade.json", "sec", "px"}   # data/events/ (earnings and rating history) is only read at build time
NOT_PUBLISHED = {".git", ".github", ".ship", ".netlify", "netlify", "tools", "node_modules", "_site", "__pycache__",
                 "netlify.toml", "requirements.txt", "README.md", "BRAND.md", ".gitignore", "SHIP-QUIPLEE.cmd",
                 "package.json", "package-lock.json", "CLAUDE.md", ".cache"}


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
    """Each covered name's standard signal (S: 1 Buy, 0 Hold, -1 Sell; sc: score), plays in (k of `of`)
    and plain-English read, for My Puck and the alert emails (netlify/lib/signal.mjs rescores
    it with an account's own weights from data/playset.json)."""
    from qstrat import stockview as sv
    from qstrat.content import TICKERS
    out = {}
    for t in TICKERS:
        sym = t["sym"]
        if t.get("index") or (sym, "buy-and-hold") not in site.R:
            continue
        from qstrat.factors import score as fx_score
        sc, sg, _ = fx_score(site, t)
        k, n = site.consensus(t)
        meta = site.meta.get(sym)
        try:
            read = sv.read_lines(site, t, meta, site.fund.get(sym)) if meta else []
        except Exception:
            read = []
        oh = (meta or {}).get("ohlc")
        d1 = float(oh["close"].iloc[-1] / oh["close"].iloc[-2] - 1) if oh is not None and len(oh) > 1 else None
        out[sym] = {"n": t["name"], "s": t["short"], "u": t["slug"], "cur": t["cur"], "p": round(float(site.r(sym, "buy-and-hold")["price"]), 4),
                    "g": t["group"], "d1": None if d1 is None else round(d1, 5),
                    "S": sg, "sc": sc, "k": k, "of": n, "y1": None if site.one_year(t) is None else round(float(site.one_year(t)), 4), "read": read}
    from qstrat.factors import MODEL, default_words
    return json.dumps({"asof": site.asof.strftime("%Y-%m-%d"), "mv": MODEL, "wt": default_words(), "t": out}, ensure_ascii=False, separators=(",", ":"))


def static_footer():
    """The site footer (disclaimer, Click Shift credit, Proudly Canadian) for the hand-written
    pages, with its own styles since they use a different stylesheet."""
    from qstrat.render import FOOT_DISCLAIM, FOOT_CREDITS
    css = ("<style>.bp-foot{border-top:1px solid #232d42;background:#0b0f17;color:#8a95a9;font:13px/1.55 Geist,-apple-system,'Segoe UI',Roboto,sans-serif}"
           ".bp-foot .in{max-width:1160px;margin:0 auto;padding:20px 16px 36px;display:flex;flex-direction:column;gap:12px}"
           ".bp-foot p{margin:0}.bp-foot .foot-disclaim{color:#c3cad8;padding:12px 14px;border:1px solid #232d42;border-radius:10px;background:#131927}"
           ".bp-foot .foot-disclaim b{color:#eef2f9}.bp-foot .foot-disclaim a{color:#a99dff}.bp-foot .foot-credits{display:flex;flex-wrap:wrap;align-items:center;gap:12px 26px}"
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


def write_404(site, out):
    with open(os.path.join(out, "404.html"), "w", encoding="utf-8") as f:
        f.write(site.not_found_html())


def pages_without_disclaimer(out):
    """Every page a reader can open must carry the disclaimer (Dave's rule; render.DISCLAIMER).
    Returns the pages that don't. Files with no <body> (fragments, verification files) don't count."""
    from qstrat.render import DISCLAIMER
    key = DISCLAIMER[:60]
    missing = []
    for d, _, fs in os.walk(out):
        for fn in fs:
            if not fn.endswith((".html", ".htm")):
                continue
            path = os.path.join(d, fn)
            with open(path, encoding="utf-8", errors="replace") as f:
                text = f.read()
            if "<body" in text.lower() and key not in text:
                missing.append(os.path.relpath(path, out))
    return sorted(missing)


def write_data(site, out, quick=False):
    """The data files the pages read in the browser (and the alert emails read). quick=True
    (tools/dev_render.py) skips the per-stock Theory tester and weekly history files."""
    from qstrat.playset import playset_json
    from qstrat.newsevents import events_json
    from qstrat import screen, theory
    from qstrat.watchlist import watch_json
    from qstrat.rules import write_hist
    d = os.path.join(out, "data")
    os.makedirs(d, exist_ok=True)

    def put(name, text):
        with open(os.path.join(d, name), "w", encoding="utf-8") as f:
            f.write(text)
    put("signals.json", site.signals_json())
    put("glossary.json", glossary_json())
    put("names.json", site.names_json())
    put("plays.json", site.plays_json())
    put("playset.json", playset_json(site))
    put("events.json", events_json(site))
    put("reads.json", reads_json(site))
    put("tickers.json", screen.tickers_json(site))
    put("screen.json", screen.screen_json(site))
    put("watch.json", watch_json(site))
    put("build.json", build_json(site))
    from qstrat.factorgrade import grade_json
    put("factorgrade.json", grade_json(site))
    gate = site.__dict__.get("_gate")
    if gate is not None:
        put("quality.json", gate.json())
        print(gate.summary())
    from qstrat.accountplan import write_px
    print("weekly price files for the account check:", write_px(site, out))
    if quick:
        return
    t2 = time.time()
    os.makedirs(os.path.join(d, "theory"), exist_ok=True)
    tfiles = getattr(site, "theory_json", None) or theory.files(site)
    for slug, js in tfiles.items():
        put(os.path.join("theory", slug + ".json"), js)
    print(f"theory tester: {len(tfiles)} stocks in {time.time() - t2:.0f}s")
    print("weekly call history files:", write_hist(site, out))


def build_json(site):
    """What this deploy was built from: the smoke test waits for its commit and checks the data's age."""
    import datetime as dt
    commit = os.environ.get("COMMIT_REF") or os.environ.get("GITHUB_SHA") or ""
    return json.dumps({"commit": commit, "asof": site.asof.strftime("%Y-%m-%d"),
                       "built": dt.datetime.now(dt.timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ"),
                       "pages": sum(1 for _ in site.pages)}, separators=(",", ":"))


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
    write_data(site, out)
    t2 = time.time()
    items = build_practice(prices, irx, now)
    with open(os.path.join(out, "data", "practice.json"), "w", encoding="utf-8") as f:
        f.write(practice_json(items))
    print(f"built {len(items)} practice charts in {time.time() - t2:.0f}s")
    with open(os.path.join(out, "sitemap.xml"), "w") as f:
        f.write(site.sitemap())
    print("glossary-linked:", ", ".join(link_static_pages(out)))
    write_404(site, out)
    missing = pages_without_disclaimer(out)
    if missing:
        print(f"{len(missing)} page(s) without the disclaimer:", *missing[:50], sep="\n  ")
        sys.exit("refusing to publish pages without the disclaimer")
    if not os.environ.get("QSTRAT_SPILL"):
        shutil.rmtree(spill, ignore_errors=True)
    print(f"wrote the site to {out} in {time.time() - t0:.0f}s")


if __name__ == "__main__":
    main()
