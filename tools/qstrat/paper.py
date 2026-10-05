"""/paper/: the paper-trading game.

Players sign up with a username and password, start with US$100,000 and trade
the names Be The Puck covers. The live part (accounts, trades, quotes) is the
Netlify Function netlify/functions/paper.mjs; this module builds

  data/paper.json      the tradable names: short, name, page, currency, last
                       close, kind, and how many plays hold it
  /paper/              the game (assets/paper.js does the rest in the browser)
  /paper/leaders/      the leaderboard of shared portfolios
  /paper/player/?u=    a shared portfolio

and, in the production build only, the nightly snapshot: it reads every
portfolio from /api/paper/admin/export (bearer PICKS_STATE_TOKEN), values it
at the night's closes, stores each player's value for their performance chart
and writes the leaderboard. A date is written once, by the first build after
the prices for that date land.
"""
import html
import json
import os
import urllib.error
import urllib.request

from .content import TICKERS, TIMED
from .engine import _read, PRICE_DIR
from .render import sig

e = html.escape
START = 100000
BENCH = "SPY"


def _bases():
    if os.environ.get("QUIPLEE_PAPER_URL"):
        return [os.environ["QUIPLEE_PAPER_URL"].rstrip("/")]
    out = [(os.environ.get("URL") or "https://bethepuck.com").rstrip("/")]
    if os.environ.get("SITE_NAME"):
        out.append(f"https://{os.environ['SITE_NAME']}.netlify.app")
    return out


def tradable(site):
    return [t for t in TICKERS if not t.get("index") and (t["sym"], "buy-and-hold") in site.R]


def cad_per_usd():
    try:
        return float(_read("CAD=X", PRICE_DIR)["close"].iloc[-1])
    except Exception:
        return None


def paper_json(site):
    names = {}
    for t in tradable(site):
        x = site.r(t["sym"], "buy-and-hold")
        k, n = site.consensus(t)
        kind = "crypto" if t["crypto"] else ("fund" if t["group"] in ("Indexes & ETFs", "Sectors") else "stock")
        names[t["sym"]] = [t["short"], t["name"], t["slug"], "CAD" if t["cur"] == "C$" else "USD", sig(x["price"], 6), kind, k, n, t["group"]]
    fx = cad_per_usd()
    return json.dumps({"asof": site.asof.strftime("%Y-%m-%d"), "start": START, "fx": {"CAD": fx} if fx else {}, "names": names},
                      ensure_ascii=False, separators=(",", ":"))


# --------------------------------------------------------------------------
# nightly snapshot (production build only)
# --------------------------------------------------------------------------
def _call(path, body=None):
    tok = os.environ.get("PICKS_STATE_TOKEN")
    last = None
    for base in _bases():
        req = urllib.request.Request(base + path, data=None if body is None else json.dumps(body).encode(),
                                     headers={"Authorization": f"Bearer {tok}", "Accept": "application/json",
                                              "Content-Type": "application/json"}, method="GET" if body is None else "POST")
        try:
            with urllib.request.urlopen(req, timeout=60) as r:
                return json.load(r)
        except (urllib.error.URLError, OSError, ValueError) as ex:
            last = ex
    raise RuntimeError(f"paper API unreachable: {last}")


def snapshot(site):
    """Value every portfolio at tonight's closes and post the values and leaderboard."""
    if os.environ.get("CONTEXT") != "production" or not os.environ.get("PICKS_STATE_TOKEN"):
        return "skipped (not the production build)"
    spy = site.prices.get(BENCH)
    if spy is None:
        return "skipped (no SPY prices)"
    date = spy.index[-1].strftime("%Y-%m-%d")
    try:
        board_now = _call("/api/paper/board")
        if board_now.get("asof") and board_now["asof"] >= date:
            return f"already written for {date}"
        data = _call("/api/paper/admin/export")
    except RuntimeError as ex:
        return f"skipped ({ex})"
    bench = float(spy["close"].iloc[-1])
    fx = cad_per_usd()
    if not fx:
        return "skipped (no USD/CAD rate)"
    meta = {t["sym"]: t for t in TICKERS}
    rows, board = [], []
    for p in data.get("players", []):
        total, held = float(p.get("cash") or 0), []
        for sym, q in (p.get("pos") or {}).items():
            d = site.prices.get(sym)
            t = meta.get(sym)
            if d is None or t is None or not q:
                continue
            px = float(d["close"].iloc[-1])
            v = q * px / (fx if t["cur"] == "C$" else 1.0)
            total += v
            held.append((v, t["short"]))
        start = float(p.get("start") or START)
        rows.append([p["u"], round(total, 2), round(bench, 4)])
        if p.get("share") and not p.get("hidden") and p.get("n_trades"):
            held.sort(reverse=True)
            board.append({"name": p["name"], "u": p["u"], "value": round(total, 2), "ret": total / start - 1, "since": p.get("created"),
                          "n": len(held), "top": [s for _, s in held[:3]], "cash": round(float(p.get("cash") or 0) / total, 4) if total else 1})
    board.sort(key=lambda b: -b["ret"])
    for i in range(0, max(1, len(rows)), 200):
        last = i + 200 >= len(rows)
        _call("/api/paper/admin/snapshot", {"date": date, "rows": rows[i:i + 200], **({"board": board, "players": len(rows)} if last else {})})
    return f"{len(rows)} portfolios valued for {date}, {len(board)} on the leaderboard"


# --------------------------------------------------------------------------
# pages
# --------------------------------------------------------------------------
HOW = [
    ("US$100,000 to start", "Everyone gets the same play money. No real money, ever, and nothing to pay."),
    ("The latest price", "Orders fill at Yahoo's latest price, delayed up to 15 minutes. When a market is closed, they fill at the last close."),
    ("Toronto names in C$", "TSX stocks trade in Canadian dollars, converted at the live USD/CAD rate. Your account is kept in US dollars."),
    ("Keep it simple", "Buy and sell only: no short selling, margin or options. Whole shares for stocks and funds; coins in fractions. No fees, and dividends aren't paid in."),
    ("Your call to share", "Portfolios are private unless you choose to show yours. Shared ones get a public page and a spot on the leaderboard, updated each night."),
]


def _how_html():
    return "".join(f'<li><b>{e(a)}.</b> {e(b)}</li>' for a, b in HOW)


def paper_pages(site):
    n = len(tradable(site))
    _game(site, n)
    _leaders(site)
    _player(site)


def _game(site, n):
    path, depth = "paper/", 1
    h = lambda x: site.href(depth, x)
    uni = h("data/paper.json") + "?v=" + site.ver
    tmpl = h("stocks/{s}/")
    body = f"""<section class="pair-head"><p class="eyebrow">Paper trading</p><h1 class="h1">Trade US$100,000 of play money</h1>
<p class="lede">Pick from the {n} stocks, funds and coins Be The Puck covers, buy and sell at the latest price, and see how you do against the S&amp;P 500. Share your portfolio on the <a href="{h('paper/leaders/')}">leaderboard</a> if you like. No real money, ever.</p></section>

<div id="pt-app" class="pt-app" data-api="/api/paper/" data-universe="{e(uni)}" data-stock="{e(tmpl)}" data-player="{e(h('paper/player/'))}" data-mode="game">
<p class="pt-loading muted" data-pt-loading>Loading your portfolio…</p>

<section class="pt-auth" data-pt-out hidden>
<div class="card pt-card">
<h2 class="h3">Start playing</h2>
<form class="pt-form" data-pt-form="signup" novalidate>
<label>Username<input name="name" autocomplete="username" required minlength="3" maxlength="20" pattern="[A-Za-z0-9_]{{3,20}}" placeholder="3 to 20 letters, numbers or _"></label>
<label>Password<input name="password" type="password" autocomplete="new-password" required minlength="8" placeholder="At least 8 characters"></label>
<label class="pt-check"><input type="checkbox" name="share"> Show my portfolio on the leaderboard</label>
<button class="btn primary" type="submit">Get my US$100,000</button>
<p class="pt-msg" role="alert" data-pt-msg></p>
<p class="muted small">No email needed, so a lost password can't be reset. Keep it somewhere safe.</p>
</form>
</div>
<div class="card pt-card">
<h2 class="h3">Sign in</h2>
<form class="pt-form" data-pt-form="login" novalidate>
<label>Username<input name="name" autocomplete="username" required></label>
<label>Password<input name="password" type="password" autocomplete="current-password" required></label>
<button class="btn btn-ghost" type="submit">Sign in</button>
<p class="pt-msg" role="alert" data-pt-msg></p>
</form>
</div>
</section>

<section class="pt-in" data-pt-in hidden></section>
</div>

<section class="card prose pt-how"><h2 class="h3">How it works</h2><ul>{_how_html()}</ul>
<p class="muted small">A game for learning, not financial advice. Be The Puck shows what published trading rules say about each name; it doesn't know your goals, taxes or timeline.</p></section>
"""
    site.add(path, site.shell(path, "Paper trading: US$100,000 of play money",
                              f"Trade the {n} stocks, funds and coins Be The Puck covers with US$100,000 of play money, track your returns against the S&P 500 and share your portfolio.",
                              body, active="paper/", charts=True, scripts=("assets/paper.js",), link=False))


def _leaders(site):
    path, depth = "paper/leaders/", 2
    h = lambda x: site.href(depth, x)
    body = f"""<nav class="crumbs"><a href="{h('paper/')}">Paper trading</a><span>/</span><span>Leaderboard</span></nav>
<section class="pair-head"><p class="eyebrow">Paper trading</p><h1 class="h1">Leaderboard</h1>
<p class="lede">Shared portfolios ranked by return since they started, valued at each night's close. Everyone began with US$100,000 of play money. <a href="{h('paper/')}">Start your own</a>.</p></section>
<div id="pt-app" class="pt-app" data-api="/api/paper/" data-player="{e(h('paper/player/'))}" data-stock="{e(h('stocks/{s}/'))}" data-mode="board">
<p class="pt-loading muted" data-pt-loading>Loading the leaderboard…</p>
<section data-pt-board></section>
</div>
<p class="muted small">Only portfolios whose owners chose to share them appear here. Returns are price changes only (no dividends) and are hypothetical.</p>
"""
    site.add(path, site.shell(path, "Paper trading leaderboard", "The shared paper-trading portfolios on Be The Puck, ranked by return since they started with US$100,000.",
                              body, active="paper/", scripts=("assets/paper.js",), link=False))


def _player(site):
    path, depth = "paper/player/", 2
    h = lambda x: site.href(depth, x)
    body = f"""<nav class="crumbs"><a href="{h('paper/')}">Paper trading</a><span>/</span><a href="{h('paper/leaders/')}">Leaderboard</a><span>/</span><span data-pt-crumb>Player</span></nav>
<div id="pt-app" class="pt-app" data-api="/api/paper/" data-universe="{e(h('data/paper.json') + '?v=' + site.ver)}" data-player="{e(h('paper/player/'))}" data-stock="{e(h('stocks/{s}/'))}" data-mode="player">
<p class="pt-loading muted" data-pt-loading>Loading the portfolio…</p>
<section class="pt-in" data-pt-in hidden></section>
</div>
<p class="muted small">Play money, not advice. Holdings are valued at the latest price, delayed up to 15 minutes.</p>
"""
    page = site.shell(path, "A paper-trading portfolio", "A shared paper-trading portfolio on Be The Puck: holdings, trades and returns against the S&P 500.",
                      body, active="paper/", charts=True, scripts=("assets/paper.js",), link=False)
    site.add(path, page.replace('<meta name="description"', '<meta name="robots" content="noindex">\n<meta name="description"', 1))
