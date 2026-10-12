"""Smoke test for Be The Puck: open the key pages at phone (390px) and desktop (1280px)
widths and fail on anything a reader would notice.

    python tools/smoke.py https://bethepuck.com
    python tools/smoke.py https://bethepuck.com --commit <sha>   # first wait for that commit to be live
    python tools/smoke.py http://localhost:8792 --local          # a tools/dev_render.py preview

Fails on: a page that doesn't load, a script error, a failed request to the site itself, sideways
scroll, a page with no headline, a stock page whose signal never draws, a retired address that
doesn't forward, or data older than MAX_AGE_DAYS. Needs `pip install playwright` and
`python -m playwright install chromium` (already set up in the cloud sessions).
"""
import argparse
import asyncio
import datetime as dt
import json
import sys
import time
import urllib.request

PAGES = [
    "/", "/stocks/", "/stocks/shop-to/", "/stocks/mu/", "/stocks/mstr/", "/stocks/spy/", "/stocks/btc-usd/",
    "/stocks/spy/mayer-multiple/", "/strategies/", "/strategies/mayer-multiple/", "/thinkers/", "/watchlist/", "/markets/",
    "/learn/", "/guides/", "/guides/your-plays/", "/guides/news-that-moves-stocks/", "/method/", "/articles/", "/theory/",
    "/me/", "/alerts/",
]
LOCAL_PAGES = ["/", "/stocks/", "/stocks/shop-to/", "/stocks/mu/", "/stocks/spy/", "/watchlist/", "/me/", "/guides/your-plays/"]
# retired addresses -> where they must end up
FORWARDS = {
    "/stocks/mu/rsi-30-70/": "/stocks/mu/?play=rsi-30-70",
    "/stocks/mu/golden-cross/": "/stocks/mu/?play=golden-cross",
}
WIDTHS = (390, 1280)
MAX_AGE_DAYS = 4
STOCK_CHECK = """() => { const b = document.querySelector('[data-sig-badge]'); return b ? b.textContent.trim() : 'no-signal-card'; }"""


def get_json(url):
    req = urllib.request.Request(url, headers={"User-Agent": "bethepuck-smoke", "Cache-Control": "no-cache"})
    with urllib.request.urlopen(req, timeout=30) as r:
        return json.loads(r.read().decode())


def wait_for_commit(base, sha, minutes):
    """Poll /data/build.json until the deploy built from `sha` is live."""
    end = time.time() + minutes * 60
    while time.time() < end:
        try:
            b = get_json(f"{base}/data/build.json?t={int(time.time())}")
            if b.get("commit", "").startswith(sha[:12]):
                print(f"live: commit {sha[:8]} built {b.get('built')}")
                return True
            print(f"waiting for {sha[:8]} (live is {str(b.get('commit'))[:8] or 'unknown'})")
        except Exception as ex:
            print("waiting:", ex)
        time.sleep(30)
    return False


async def run(base, local):
    from playwright.async_api import async_playwright
    fails, host = [], base.split("//", 1)[-1].split("/")[0]
    ix = (lambda p: p + "index.html" if p.endswith("/") else p) if local else (lambda p: p)
    pages = LOCAL_PAGES if local else PAGES
    async with async_playwright() as pw:
        browser = await pw.chromium.launch()
        for w in WIDTHS:
            ctx = await browser.new_context(viewport={"width": w, "height": 900})
            for path in pages:
                pg = await ctx.new_page()
                errs = []
                pg.on("pageerror", lambda e: errs.append("script error: " + str(e)[:160]))
                pg.on("response", lambda r: (r.status >= 400 and host in r.url and "/api/" not in r.url and "favicon" not in r.url)
                      and errs.append(f"{r.status} {r.url}"))
                try:
                    resp = await pg.goto(base + ix(path), wait_until="load", timeout=60000)
                    if not resp or resp.status >= 400:
                        errs.append(f"page status {resp.status if resp else 'none'}")
                    await pg.wait_for_timeout(1500)
                    got = await pg.evaluate("() => ({sw: document.documentElement.scrollWidth, h1: !!document.querySelector('h1, .h1')})")
                    if got["sw"] > w + 1:
                        errs.append(f"sideways scroll: {got['sw']}px wide at {w}px")
                    if not got["h1"]:
                        errs.append("no headline")
                    if path.startswith("/stocks/") and path.count("/") == 3:
                        badge = await pg.evaluate(STOCK_CHECK)
                        if badge not in ("Buy", "Hold", "Sell", "No score"):
                            errs.append(f"signal didn't draw ({badge!r})")
                except Exception as ex:
                    errs.append("load failed: " + str(ex)[:160])
                for x in errs:
                    fails.append(f"{w}px {path}: {x}")
                print(f"{'FAIL' if errs else 'ok  '} {w:4d} {path}")
                await pg.close()
            await ctx.close()
        if not local:
            ctx = await browser.new_context()
            for old, new in FORWARDS.items():
                pg = await ctx.new_page()
                try:
                    await pg.goto(base + old, wait_until="load", timeout=60000)
                    if not pg.url.split(host, 1)[-1].startswith(new):
                        fails.append(f"forward {old}: ended at {pg.url}, expected {new}")
                    print(f"{'ok  ' if pg.url.split(host, 1)[-1].startswith(new) else 'FAIL'} forward {old}")
                except Exception as ex:
                    fails.append(f"forward {old}: {ex}")
                await pg.close()
            await ctx.close()
        await browser.close()
    return fails


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("base")
    ap.add_argument("--local", action="store_true", help="a local preview (index.html links, fewer pages, no forwards)")
    ap.add_argument("--commit", help="wait until /data/build.json reports this commit")
    ap.add_argument("--wait", type=int, default=40, help="minutes to wait for --commit")
    args = ap.parse_args()
    base = args.base.rstrip("/")
    fails = []
    if args.commit and not wait_for_commit(base, args.commit, args.wait):
        fails.append(f"commit {args.commit[:8]} wasn't live after {args.wait} minutes")
    try:
        b = get_json(f"{base}/data/build.json?t={int(time.time())}")
        age = (dt.date.today() - dt.date.fromisoformat(b["asof"])).days
        print(f"data as of {b['asof']} ({age} days), built {b.get('built')}, commit {str(b.get('commit'))[:8]}")
        if age > MAX_AGE_DAYS and not args.local:
            fails.append(f"stale data: prices as of {b['asof']}, {age} days ago")
    except Exception as ex:
        fails.append(f"no build.json: {ex}")
    fails += asyncio.run(run(base, args.local))
    print()
    if fails:
        print(f"{len(fails)} problem(s):")
        for f in fails:
            print(" -", f)
        sys.exit(1)
    print("all clear")


if __name__ == "__main__":
    main()
