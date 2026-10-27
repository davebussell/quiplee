"""Fast local renders for Be The Puck: run the engine once (cached), then render only the
pages you're working on, in about a minute.

    python tools/dev_render.py engine                  # every play on every ticker, cached in .cache/
    python tools/dev_render.py render MU,SHOP.TO       # those stock pages + the data files, into .cache/prev/
    python tools/dev_render.py render ALL              # every stock page
    PAGES=home,stocks,watchlist,me,guide,strategies python tools/dev_render.py render SPY
    python tools/dev_render.py render SPY --report     # also print each play's accuracy by family
    python tools/dev_render.py full                    # the whole site from the cache, as Netlify would build it (~10 min)

Serve the result with `node tools/dev_serve.mjs .cache/prev 8792` (fakes a signed-in account).
"""
import os
import pickle
import shutil
import sys
import time

HERE = os.path.dirname(os.path.abspath(__file__))
ROOT = os.path.dirname(HERE)
sys.path.insert(0, HERE)

from qstrat import engine  # noqa: E402
from qstrat.content import TICKERS  # noqa: E402
# PRIVATE=SYM1,SYM2 treats covered names as reader-requested (private) for this run, to test that they stay off
# the public lists and out of the public ranks. Set before render.py is imported (it reads the flags once).
for _t in TICKERS:
    if _t["sym"] in set(filter(None, os.environ.get("PRIVATE", "").split(","))):
        _t["requested"], _t["since"] = True, "2026-10-26"
import build_strategies as B  # noqa: E402

CACHE_DIR = os.environ.get("BTP_CACHE") or os.path.join(ROOT, ".cache")
CACHE = os.path.join(CACHE_DIR, "results.pkl")
SPILL = os.path.join(CACHE_DIR, "spill")
OUT = os.path.join(CACHE_DIR, "prev")


def main():
    if len(sys.argv) < 2 or sys.argv[1] not in ("engine", "render", "full"):
        print(__doc__)
        sys.exit(1)
    mode = sys.argv[1]
    os.makedirs(CACHE_DIR, exist_ok=True)
    t0 = time.time()
    prices, irx, now = engine.load_all()
    if mode == "engine":
        shutil.rmtree(SPILL, ignore_errors=True)
        results = engine.run(prices, irx, now, spill=SPILL)
        with open(CACHE, "wb") as f:
            pickle.dump(results, f, protocol=pickle.HIGHEST_PROTOCOL)
        print(f"engine {time.time() - t0:.0f}s, {len(results)} results cached in {CACHE}")
        return
    if not os.path.exists(CACHE):
        sys.exit("No engine cache yet: run `python tools/dev_render.py engine` first.")
    with open(CACHE, "rb") as f:
        results = pickle.load(f)
    meta = {k[0]: results.pop(k) for k in [k for k in results if k[1] == "__meta"]}
    # names added to the universe after the cache was made (a reader's request overnight) have no results in it:
    # leave them out of this preview rather than fail (a real build runs the engine on every name)
    have = {k[0] for k in results}
    late = [t["sym"] for t in TICKERS if t["sym"] not in have]
    if late:
        TICKERS[:] = [t for t in TICKERS if t["sym"] in have]
        print("not in the engine cache, left out of this preview:", ", ".join(late))
    # a cache from an earlier close than data/prices: cut the prices to the engine's close, so the
    # pages, the signal and its day-by-day path (callpath.py) all see the same day, as a real build does
    asof = max(r["asof"] for r in results.values())
    cut = {k: v for k, v in prices.items() if len(v.index) and v.index[-1] > asof}
    if cut:
        import pandas as pd
        for k, v in cut.items():
            prices[k] = v[v.index <= pd.Timestamp(asof)]
        print(f"prices cut to the engine cache's close {asof} ({len(cut)} files had newer days)")
    from qstrat.render import Site
    if mode == "full":
        out = os.path.join(CACHE_DIR, "site")
        shutil.rmtree(out, ignore_errors=True)
        os.makedirs(out)
        B.copy_static(out)
        site = Site(results, preview=True, prices=prices, irx=irx, meta=meta)
        site.out = out
        pages = site.build()
        B.write_pages({k: v for k, v in pages.items() if v is not None}, out)
        B.write_data(site, out)
        with open(os.path.join(out, "sitemap.xml"), "w") as f:
            f.write(site.sitemap())
        B.link_static_pages(out)
        B.write_404(site, out)
        n = sum(len(fs) for _, _, fs in os.walk(out))
        print(f"full site: {len(pages)} pages, {n} files in {time.time() - t0:.0f}s ->", out)
        return
    site = Site(results, preview=True, prices=prices, irx=irx, meta=meta)
    # the factor grading takes a minute or two; reuse the last one (delete .cache/factorgrade.json to redo it)
    fg = os.path.join(CACHE_DIR, "factorgrade.json")
    if os.path.exists(fg):
        import json
        site.__dict__["_factorgrade"] = json.load(open(fg))
    else:
        from qstrat.factorgrade import grade_json
        open(fg, "w").write(grade_json(site))
    want = sys.argv[2] if len(sys.argv) > 2 else "SPY"
    syms = [t["sym"] for t in TICKERS] if want == "ALL" else want.split(",")
    for t in TICKERS:
        if t["sym"] in syms:
            site.stock_page(t)
    extra = set(os.environ.get("PAGES", "").split(","))
    if "home" in extra:
        site.home()
    if "stocks" in extra:
        site.stocks_index()
    if "strategies" in extra:
        from qstrat.content import PLAYS
        site.strategies_index()
        for s in PLAYS:
            site.strategy_page(s)
    if "classics" in extra:
        from qstrat import classics
        classics.build(site)
    if "pairs" in extra:
        for t in TICKERS:
            if t["sym"] in syms:
                for s in site.headline_plays():
                    site.pair_page(t, s)
    if "articles" in extra:
        from qstrat.articles import Articles
        Articles(site).build()            # its data/articles.json is written by B.write_data below
    if "watchlist" in extra:
        from qstrat.watchlist import watchlist_page
        watchlist_page(site)
    if "picks" in extra:
        from qstrat import picks
        state, info = picks.run(site)
        picks.picks_page(site, state, info)
    if "me" in extra:
        from qstrat.me import me_page
        me_page(site)
    if "alerts" in extra:
        from qstrat.alerts import alerts_page
        alerts_page(site)
    if "plan" in extra:
        from qstrat.accountplan import guide_page as plan_page
        plan_page(site)
    if "invest" in extra:
        from qstrat.waystoinvest import ways_to_invest_page
        ways_to_invest_page(site)
    if "method" in extra:
        site.method_page()
    if "guide" in extra:
        from qstrat.playset import guide_page
        guide_page(site)
        from qstrat.newsevents import guide_page as news_guide
        news_guide(site)
    if "--report" in sys.argv:
        from qstrat.plays import FAMILIES
        for fk, fname, _ in FAMILIES:
            rows = sorted(((site.play_accuracy(p), p["name"]) for p in site.timed_family(fk)), key=lambda x: -(x[0]["bat"] or 0))
            print(f"\n{fname}")
            for a, nm in rows:
                print(f"  {nm:34s} {(a['bat'] or 0) * 100:5.1f}%  of {a['calls']:6d} calls on {a['stocks']} stocks")
    shutil.rmtree(OUT, ignore_errors=True)
    os.makedirs(OUT)
    B.copy_static(OUT)
    B.write_pages({k: v for k, v in site.pages.items() if v is not None}, OUT)
    B.write_404(site, OUT)
    B.write_data(site, OUT, quick=True)
    named = B.files_naming_banned(OUT)
    if named:
        print(f"{len(named)} file(s) name a company the site never mentions:", *[f"{f}: {w}" for f, w in named[:20]], sep="\n  ")
    missing = B.pages_without_disclaimer(OUT)
    if missing:
        print("pages without the disclaimer:", *missing, sep="\n  ")
    print("pages:", len(site.pages), f"in {time.time() - t0:.0f}s ->", OUT)


if __name__ == "__main__":
    main()
