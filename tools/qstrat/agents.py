"""Be The Puck for AI tools: the files and the page that let Claude, ChatGPT and other assistants read the site.

    data/api.json     the plays in full (rules, people, record) and the market guard on the S&P 500 and the TSX, for
                      the read API (netlify/functions/api.mjs, /api/v1/*) and the MCP server (netlify/functions/mcp.mjs, /mcp)
    llms.txt          what Be The Puck is, how the signal works, how to connect, the rules (llmstxt.org)
    llms-full.txt     the same plus every factor, every play and every public name
    openapi.json      OpenAPI 3.1 for the v1 API (ChatGPT Actions and others)
    /developers/      the human page: both tiers, how to get a key, how to connect Claude, ChatGPT and others

Everything here states facts with the disclaimer, never advice. Reader-requested names are private and stay out
(render.universe()); the build checks every file for the companies the site never names (build_strategies.BANNED_HITS).
"""
import html
import json

import pandas as pd

from .content import TIMED, FAMILIES, THINKER, BAR_WORD, TK_BY_SYM
from .render import DISCLAIMER, BASE, EXTRA_PAIRS, universe, n_stocks, rankable, n_people, dlong

e = html.escape
SITE = BASE.rstrip("/")
MCP_URL = SITE + "/mcp"
FREE_PER_DAY, KEY_PER_DAY = 30, 2000          # netlify/lib/agentkeys.mjs FREE_PER_DAY, KEY_PER_DAY
FREE_UNTIL = "January 1, 2027"                # netlify/lib/account.mjs FREE_UNTIL_LABEL
PRICE = "$5"
STANCE = ("Be The Puck is not a broker or an adviser and never places trades. An assistant can read the signal and draft an order, "
          "but nothing is placed until you approve it in your own broker, and paper trading comes first.")
BENCH = (("^GSPC", "S&P 500"), ("^GSPTSE", "TSX"))
TOOLS = [
    ("get_stock_signal", "GET /api/v1/stock/{ticker}", "free", "The signal (Buy, Hold or Sell), score, plays in and the plain-English read on one name. "
     "Members also get the factor points, the closes that would change the call, and scoring with their own weights (w, buy, sell, plays)."),
    ("search_stocks", "GET /api/v1/search?q=", "free", "Covered names by ticker or company name, with each one's signal and score."),
    ("screen_stocks", "GET /api/v1/screen", "member", "Every public name filtered by signal (buy, hold, sell), market (us, ca, crypto, fund), group and "
     "min_plays (percent of plays in), sorted by score or plays, up to 50 rows."),
    ("list_plays", "GET /api/v1/plays", "member", "Every play by family, with the people behind it and how often it has been right."),
    ("explain_play", "GET /api/v1/plays/{slug}", "member", "One play in full: its rules, timeframe, source, Be The Puck's assumptions and its record."),
    ("market_conditions", "GET /api/v1/market", "member", "The market guard on the S&P 500 and the TSX, the crash gauges' verdict, and how many names read Buy, Hold and Sell."),
]
EXAMPLES = [
    "What is Be The Puck's signal on Micron, and what close would change it?",
    "Which Canadian stocks read Buy with at least 60% of the plays in?",
    "Is the market guard on for the S&P 500 or the TSX right now?",
    "Explain the Stage Analysis play and how often it has been right.",
    "Score NVDA with 50% plays in and 50% earnings growth.",
    "Draft (don't place) a paper-trading order list for the names on my watchlist that turned Sell.",
]


# ------------------------------------------------------------------ data/api.json
def _market(site):
    """The market guard on each bench index at the latest close (as callpath.bench_drawdowns works it out)."""
    from .factors import GUARD
    out = []
    for sym, name in BENCH:
        try:
            c = site.prices[sym]["close"]
            c = c[c.index <= pd.Timestamp(site.asof)]
            hi = c.rolling(252, min_periods=120).max()
            dd = float(c.iloc[-1] / hi.iloc[-1] - 1)
        except Exception:
            continue
        out.append({"symbol": sym, "name": name, "close": round(float(c.iloc[-1]), 2), "high_1y": round(float(hi.iloc[-1]), 2),
                    "below_high": round(dd, 4), "guard": bool(dd <= -GUARD), "date": c.index[-1].strftime("%Y-%m-%d"),
                    "url": f"{SITE}/stocks/{TK_BY_SYM[sym]['slug']}/"})
    return out


def _weather(site):
    M = getattr(site, "macro", None)
    if not M:
        try:
            from . import macro
            M = macro.build(plays_in={t["sym"]: site.consensus(t) for t in universe() if t.get("index")})
        except Exception:
            return None
    c = M.get("counts") or {}
    return {"word": M.get("weather"), "warning": c.get("warning", 0), "watch": c.get("watch", 0), "calm": c.get("calm", 0)}


def plays_data(site):
    """Every play as the API and llms-full.txt describe it."""
    ns = n_stocks()
    top = {p["slug"] for _, p, _ in site.top_plays()}
    fam_name = {k: n for k, n, _ in FAMILIES}
    out = []
    for p in TIMED:
        a = site.play_accuracy(p)
        people = [{"name": THINKER[x]["name"], "role": THINKER[x].get("role") or None, "url": f"{SITE}/thinkers/{x}/"} for x in p["analysts"]]
        out.append({
            "slug": p["slug"], "name": p["name"], "long_name": p.get("long") or p["name"], "family": p["family"], "family_name": fam_name[p["family"]],
            "timeframe": BAR_WORD.get(p["bar"], p["bar"]), "about": p["short"], "rules": list(p["rules"]), "assumptions": list(p.get("assumptions") or []),
            "origin": p.get("origin") or None, "flag": p.get("flag") or None, "people": people,
            "record": {"calls_right": None if a["bat"] is None else round(a["bat"], 4), "right": a["right"], "calls": a["calls"], "stocks": a["stocks"],
                       "ranked": bool(rankable(a, ns)), "top": p["slug"] in top},
            "url": f"{SITE}/strategies/{p['slug']}/",
            "example": f"{SITE}/stocks/spy/{p['slug']}/" if ("SPY", p["slug"]) in EXTRA_PAIRS else None,
        })
    return out


def api_json(site):
    from .factors import GUARD, MODEL
    from .render import GRADE_YEAR
    return json.dumps({"asof": site.asof.strftime("%Y-%m-%d"), "mv": MODEL, "since": GRADE_YEAR,
                       "families": [{"key": k, "name": n, "about": d} for k, n, d in FAMILIES if any(p["family"] == k for p in TIMED)],
                       "plays": plays_data(site), "markets": _market(site), "guard_at": GUARD, "weather": _weather(site)},
                      ensure_ascii=False, separators=(",", ":"))


# ------------------------------------------------------------------ llms.txt
def _signal_lines():
    from .factors import default_words, BUY, SELL, MID, GUARD, FACTORS
    return [
        f"- Each play is a published trading rule reduced to a long-or-cash switch, run on every covered name since 2005 and graded: "
        f"\"calls right\" is the share of its finished calls on real stocks that went the right way.",
        f"- The standard signal scores each name 0 to 100 from {default_words()}. Buy at {BUY} or more, Sell at {SELL} or less, Hold in between.",
        f"- Plays in is the share of the plays that hold the name. Off the high is 100 points at the 1-year high and none at 30% or more below. "
        f"Trend is how far the price sits above its 200-day average, ranked among the covered names.",
        f"- Market guard: while a name's market (the S&P 500, or the TSX) is {round(GUARD * 100)}% or more below its 1-year high, the price factors "
        f"stand down and the rest of the weights decide.",
        f"- Sticky calls: on the standard weights, a Buy holds until the score drops below {MID} and a Sell until it rises above {MID}.",
        f"- Readers can weight any of {len(FACTORS)} factors their own way; members can do the same through the API. Every factor and play shows its graded record.",
    ]


def _tier_lines():
    return [
        f"- Free sample, no key: get_stock_signal and search_stocks (signal, score, plays in and the read), {FREE_PER_DAY} calls a day from one address.",
        f"- Members, with a personal API key: every tool, including the screener, factor points, the plays, market conditions, flip prices and "
        f"custom weights, {KEY_PER_DAY:,} calls a day. A key comes with a Be The Puck membership ({PRICE} a month; member tools are free for every "
        f"account until {FREE_UNTIL}). Make one on the account page ({SITE}/me/#apikey); it is shown once and can be revoked there.",
        f"- Send the key as `Authorization: Bearer <key>`. For an MCP client that can't set headers (a claude.ai custom connector), use the "
        f"secret URL {MCP_URL}/k/<key> and keep it private like a password.",
    ]


def llms_txt(site, full=False):
    names = universe()
    L = [
        "# Be The Puck", "",
        f"> Be The Puck (bethepuck.com) runs {len(TIMED)} published trading plays from {n_people()} named analysts on {len(names)} stocks, funds, "
        f"indexes and coins after every U.S. close, scores each name on graded factors, and makes one call per name: Buy, Hold or Sell. "
        f"It states facts and evidence, never a recommendation to the reader. {DISCLAIMER}", "",
        f"Data as of the {dlong(site.asof)} close; rebuilt after each U.S. close. Made in Canada by Click Shift Marketing.", "",
        "## How the signal works", "", *_signal_lines(), "",
        "## For AI tools", "",
        f"- MCP server (Streamable HTTP, stateless JSON): {MCP_URL}",
        f"- Read API (JSON over GET, CORS open): {SITE}/api/v1/",
        f"- OpenAPI 3.1 description (for ChatGPT Actions and others): {SITE}/openapi.json",
        f"- How to connect Claude, ChatGPT and other tools: {SITE}/developers/", "",
        "Tools (each is also a REST endpoint):", "",
        *[f"- {n} ({path}, {'free sample' if tier == 'free' else 'members'}): {what}" for n, path, tier, what in TOOLS], "",
        "## Tiers", "", *_tier_lines(), "",
        "## Rules for anyone quoting Be The Puck", "",
        "- Report what Be The Puck says as facts with their date (the signal, the score and the close they come from), not as advice to the person.",
        f"- Carry the disclaimer: {DISCLAIMER}",
        f"- {STANCE}",
        "- Names a reader asks Be The Puck to add are private to that reader and never appear in the API, the lists or search.",
        "- Past results are backtests on stocks still listed today, which flatters every play and buying and holding alike (the method page explains).", "",
        "## Pages", "",
        f"- [Method]({SITE}/method/): how the call is made and how every play is tested",
        f"- [Stocks]({SITE}/stocks/): every covered name with its signal",
        f"- [Plays]({SITE}/strategies/): all {len(TIMED)} plays and how often each has been right",
        f"- [Markets]({SITE}/markets/): the nine crash gauges",
        f"- [This week's calls, graded]({SITE}/articles/calls-graded/): every standard call since October 13, 2026, scored in public",
        f"- [Ways to invest, by country]({SITE}/guides/ways-to-invest/): who can advise you, and how to check them",
        f"- [For AI tools]({SITE}/developers/)", "",
        "## Optional", "",
        f"- [Everything in one file]({SITE}/llms-full.txt): every factor, every play and every public name",
    ]
    if full:
        from .factors import FACTORS
        L += ["", "## The factors", ""]
        L += [f"- {k} ({n}): {d}" for k, n, _, d in FACTORS]
        L += ["", "## The plays", ""]
        plays = plays_data(site)
        for k, fname, fdesc in FAMILIES:
            fam = [p for p in plays if p["family"] == k]
            if not fam:
                continue
            L += [f"### {fname}", "", fdesc, ""]
            for p in fam:
                r = p["record"]
                rec = f"right on {round(100 * r['calls_right'])}% of {r['calls']:,} calls" if r["calls_right"] is not None else "no graded record yet"
                L.append(f"- {p['name']} ({p['slug']}, {p['timeframe']} bars, {' & '.join(x['name'] for x in p['people'])}; {rec}"
                         f"{', the most accurate in its family' if r['top'] else ''}): {p['about']} {p['url']}")
            L.append("")
        L += ["## Covered names", "", "Ticker, name and group; each has a page at https://bethepuck.com/stocks/<slug>/.", ""]
        L += [f"- {t['sym']}: {t['name']} ({t['group']}) {SITE}/stocks/{t['slug']}/" for t in names if (t["sym"], "buy-and-hold") in site.R]
    return "\n".join(L) + "\n"


# ------------------------------------------------------------------ openapi.json
def openapi_json(site):
    err = {"$ref": "#/components/responses/Error"}
    weights = [
        {"name": "w", "in": "query", "required": False, "schema": {"type": "string"}, "example": "plays40.offhigh30.trend30",
         "description": "Members: factor weights as factor+weight joined by dots (plays, upside, rating, pe, fpe, peg, ps, pb, dy, eg, rg, pm, roe, de, offhigh, trend, mom, calm)."},
        {"name": "buy", "in": "query", "required": False, "schema": {"type": "integer", "minimum": 50, "maximum": 95}, "description": "Members: the Buy line (standard 60)."},
        {"name": "sell", "in": "query", "required": False, "schema": {"type": "integer", "minimum": 5, "maximum": 90}, "description": "Members: the Sell line (standard 40)."},
        {"name": "plays", "in": "query", "required": False, "schema": {"type": "string"}, "example": "top1",
         "description": "Members: which plays count: all, top1, top3, half, or play slugs joined by dots."},
    ]
    obj = {"type": "object", "additionalProperties": True}

    def op(oid, summary, desc, params, member, schema=obj):
        out = {"operationId": oid, "summary": summary, "description": desc + (" Members only." if member else " Free sample without a key."),
               "parameters": params,
               "responses": {"200": {"description": "The answer, with `text` (plain English), `as_of` and `disclaimer`.", "content": {"application/json": {"schema": schema}}},
                             "400": err, "401": err, "403": err, "404": err, "429": err}}
        return {"get": out}
    spec = {
        "openapi": "3.1.0",
        "info": {"title": "Be The Puck read API", "version": "1.0.0",
                 "description": (f"Facts from {len(TIMED)} published trading plays and Be The Puck's signal (Buy, Hold or Sell) on {len(universe())} stocks, "
                                 f"funds, indexes and coins, rebuilt after each U.S. close. Every answer carries the disclaimer: {DISCLAIMER} {STANCE} "
                                 f"Free sample without a key ({FREE_PER_DAY} calls a day: stock and search); members send a personal key as a Bearer token "
                                 f"({KEY_PER_DAY:,} calls a day, everything). How to get a key: {SITE}/developers/"),
                 "contact": {"name": "Be The Puck", "url": f"{SITE}/developers/"}},
        "servers": [{"url": SITE}],
        "security": [{}, {"memberKey": []}],
        "paths": {
            "/api/v1/stock/{ticker}": op("getStockSignal", "Signal on one stock",
                                         "Be The Puck's signal, score out of 100, plays in and plain-English read on one covered name. Members also get factor points, flip prices and custom weights.",
                                         [{"name": "ticker", "in": "path", "required": True, "schema": {"type": "string"}, "example": "MU",
                                           "description": "Ticker or name: MU, SHOP.TO, BTC-USD, SPY, Micron."}] + weights, False,
                                         {"$ref": "#/components/schemas/Stock"}),
            "/api/v1/search": op("searchStocks", "Find a covered name", "Covered names by ticker or company name, with each one's signal and score.",
                                 [{"name": "q", "in": "query", "required": True, "schema": {"type": "string"}, "example": "shopify"},
                                  {"name": "limit", "in": "query", "required": False, "schema": {"type": "integer", "minimum": 1, "maximum": 25, "default": 10}}], False),
            "/api/v1/screen": op("screenStocks", "Screen every covered name", "Filter and sort every public name by signal, market, group and share of plays in.",
                                 [{"name": "signal", "in": "query", "required": False, "schema": {"type": "string", "enum": ["buy", "hold", "sell"]}},
                                  {"name": "market", "in": "query", "required": False, "schema": {"type": "string", "enum": ["us", "ca", "crypto", "fund"]}},
                                  {"name": "group", "in": "query", "required": False, "schema": {"type": "string"}, "example": "Semiconductors"},
                                  {"name": "min_plays", "in": "query", "required": False, "schema": {"type": "number", "minimum": 0, "maximum": 100},
                                   "description": "Lowest share of plays in, in percent."},
                                  {"name": "sort", "in": "query", "required": False, "schema": {"type": "string", "enum": ["score", "plays"], "default": "score"}},
                                  {"name": "limit", "in": "query", "required": False, "schema": {"type": "integer", "minimum": 1, "maximum": 50, "default": 20}}] + weights, True),
            "/api/v1/plays": op("listPlays", "List the plays", "Every play by family, with the people behind it and how often its calls have been right.",
                                [{"name": "family", "in": "query", "required": False,
                                  "schema": {"type": "string", "enum": [k for k, _, _ in FAMILIES if any(p["family"] == k for p in TIMED)]}}], True),
            "/api/v1/plays/{slug}": op("explainPlay", "Explain one play", "One play in full: rules, timeframe, source, assumptions and record.",
                                       [{"name": "slug", "in": "path", "required": True, "schema": {"type": "string"}, "example": "stage-analysis"}], True),
            "/api/v1/market": op("marketConditions", "Market conditions",
                                 "The market guard on the S&P 500 and the TSX, the crash gauges' verdict, and how many covered names read Buy, Hold and Sell.", [], True),
        },
        "components": {
            "securitySchemes": {"memberKey": {"type": "http", "scheme": "bearer", "description": f"A member's personal API key from {SITE}/me/#apikey (btp_...)."}},
            "responses": {"Error": {"description": "An error, with `error`, `text` and `disclaimer` (403: needs a membership key; 429: the day's calls are used).",
                                    "content": {"application/json": {"schema": {"$ref": "#/components/schemas/Error"}}}}},
            "schemas": {
                "Error": {"type": "object", "properties": {"error": {"type": "string"}, "code": {"type": "string"}, "text": {"type": "string"},
                                                           "disclaimer": {"type": "string"}, "membership": {"type": "string"}}},
                "Stock": {"type": "object", "properties": {
                    "ticker": {"type": "string"}, "symbol": {"type": "string"}, "name": {"type": "string"}, "group": {"type": "string"},
                    "market": {"type": "string", "enum": ["us", "ca", "crypto", "fund"]}, "currency": {"type": "string"},
                    "close": {"type": "number"}, "close_date": {"type": "string", "format": "date"},
                    "signal": {"type": "string", "enum": ["Buy", "Hold", "Sell", "No score"]}, "score": {"type": ["integer", "null"]},
                    "held": {"type": "boolean"}, "guard": {"type": "boolean"},
                    "plays_in": {"type": "object", "properties": {"k": {"type": "integer"}, "of": {"type": "integer"}, "words": {"type": "string"}}},
                    "read": {"type": "array", "items": {"type": "string"}},
                    "factors": {"type": "array", "items": {"type": "object"}, "description": "Members: each factor's points, shown value and weight."},
                    "flip": {"type": ["string", "null"], "description": "Members: the closes at which the standard signal would change."},
                    "url": {"type": "string"}, "as_of": {"type": "string", "format": "date"}, "tier": {"type": "string"},
                    "text": {"type": "string"}, "disclaimer": {"type": "string"}, "membership": {"type": "string"}}},
            },
        },
    }
    return json.dumps(spec, ensure_ascii=False, indent=1)


# ------------------------------------------------------------------ /developers/
def developers_page(site):
    path, depth = "developers/", 1
    h = lambda x: site.href(depth, x)
    tool_rows = "".join(f'<tr><td><code>{e(n)}</code></td><td><code>{e(p)}</code></td><td>{"Free sample" if t == "free" else "Members"}</td><td>{e(w)}</td></tr>'
                        for n, p, t, w in TOOLS)
    ex = "".join(f"<li>{e(x)}</li>" for x in EXAMPLES)
    body = f"""
<section class="pair-head"><p class="eyebrow">For AI tools</p><h1 class="h1">Ask Claude, ChatGPT or any assistant what Be The Puck says</h1>
<p class="lede">Be The Puck's signal, the plays behind it and the read on every covered name are open to AI assistants: a remote MCP server for Claude and other MCP clients, and a JSON API for ChatGPT and everything else. Answers are facts with their date, from the latest U.S. close, and every one carries the disclaimer.</p></section>

<section class="dev dev-tiers">
<div class="card prose"><p class="eyebrow">Free sample</p><h2 class="h3">No key</h2>
<ul><li>The signal on one name: Buy, Hold or Sell, the score, plays in and the plain-English read</li><li>Search the covered names</li>
<li>{FREE_PER_DAY} calls a day from one address</li></ul>
<p class="small muted">Connect with <code>{e(MCP_URL)}</code> or call <code>{e(SITE)}/api/v1/stock/MU</code>.</p></div>
<div class="card prose"><p class="eyebrow">Members</p><h2 class="h3">A personal API key</h2>
<ul><li>Everything: the screener, factor points, all {len(TIMED)} plays, market conditions, the closes that would change a call, and your own weights</li>
<li>{KEY_PER_DAY:,} calls a day per key</li><li>Part of the membership: {PRICE} a month, and free for every account until {FREE_UNTIL}</li></ul>
<p class="small"><a class="btn sm" href="{h('me/')}#apikey">Get a key on your account page</a></p></div>
</section>

<section class="dev card prose" id="key"><p class="eyebrow">Your key</p><h2 class="h3">Get one, use it, revoke it</h2>
<ol><li>Sign in and open <a href="{h('me/')}#apikey">your account page</a>. Under <b>API key</b>, choose <b>Create a key</b>.</li>
<li>Copy the key (it starts <code>btp_</code>) and the secret MCP address. They are shown once: Be The Puck keeps only a fingerprint of the key, so it can't show it again.</li>
<li>Send it as a header, <code>Authorization: Bearer btp_…</code>, or for an MCP client that can't set headers, use the secret address <code>{e(MCP_URL)}/k/btp_…</code>. Treat that address like a password.</li>
<li>Lost it, or shared it by mistake? <b>Revoke</b> on the same card stops it at once; make a new one whenever you like. If your membership lapses, the key gets the free sample until you renew.</li></ol></section>

<section class="dev card prose" id="claude"><p class="eyebrow">Claude</p><h2 class="h3">Add Be The Puck as a custom connector</h2>
<ol><li>In Claude (the web, desktop or mobile app), open <b>Customize &gt; Connectors</b> and choose <b>Add custom connector</b>. On a Team or Enterprise plan an owner adds it under <b>Organization settings &gt; Connectors</b>.</li>
<li>Name it Be The Puck. For the URL, paste your secret address, <code>{e(MCP_URL)}/k/</code> followed by your key, or <code>{e(MCP_URL)}</code> for the free sample. No sign-in is needed.</li>
<li>If your dialog has a <b>Request headers</b> section, you can use <code>{e(MCP_URL)}</code> and add the header <code>authorization</code> with the value <code>Bearer btp_…</code> instead.</li>
<li>Turn it on for a chat from the <b>+</b> menu under Connectors, then ask away.</li></ol>
<p>Claude Code, from a terminal:</p>
<pre class="dev-code"><code>claude mcp add --transport http bethepuck {e(MCP_URL)} --header "Authorization: Bearer btp_…"</code></pre></section>

<section class="dev card prose" id="chatgpt"><p class="eyebrow">ChatGPT</p><h2 class="h3">Use the OpenAPI description in a custom GPT</h2>
<ol><li>Create a GPT, open <b>Configure</b>, then <b>Create new action</b>.</li>
<li><b>Import from URL</b>: <code>{e(SITE)}/openapi.json</code>.</li>
<li>Under <b>Authentication</b>, choose <b>API key</b>, type <b>Bearer</b>, and paste your key (or leave it at None for the free sample).</li></ol>
<p>Where your ChatGPT plan can add MCP connectors, the MCP address above works there too.</p></section>

<section class="dev card prose" id="others"><p class="eyebrow">Everything else</p><h2 class="h3">Any MCP client, or plain HTTP</h2>
<p>The MCP server speaks Streamable HTTP and is stateless (plain JSON replies, no event stream): point Cursor, VS Code, an agent framework or your own code at <code>{e(MCP_URL)}</code> with the header above. The same answers come from the JSON API:</p>
<pre class="dev-code"><code>curl {e(SITE)}/api/v1/stock/MU
curl -H "Authorization: Bearer btp_…" "{e(SITE)}/api/v1/screen?signal=buy&amp;market=ca&amp;min_plays=60"
curl -H "Authorization: Bearer btp_…" "{e(SITE)}/api/v1/stock/NVDA?w=plays50.eg50"</code></pre>
<div class="tbl-wrap"><table class="tbl dev-tools" data-nosort><thead><tr><th scope="col">MCP tool</th><th scope="col">API</th><th scope="col">Who</th><th scope="col">What it answers</th></tr></thead><tbody>{tool_rows}</tbody></table></div>
<p class="small muted">Machine-readable: <a href="{h('openapi.json')}">openapi.json</a> · <a href="{h('llms.txt')}">llms.txt</a> · <a href="{h('llms-full.txt')}">llms-full.txt</a> (every factor, play and public name).</p></section>

<section class="dev split">
<div class="card prose"><p class="eyebrow">Try asking</p><ul>{ex}</ul></div>
<div class="card prose"><p class="eyebrow">How it behaves</p><ul>
<li><b>Facts, not advice.</b> Answers say what Be The Puck's signal and plays read at a dated close, with the evidence, never what you should do. Every answer ends with: {e(DISCLAIMER)}</li>
<li><b>Drafts, never trades.</b> {e(STANCE)}</li>
<li><b>Your requests stay private.</b> A stock you ask Be The Puck to add is analysed for you and never appears in the API, a list or search.</li>
<li><b>Same numbers as the site.</b> The API reads the files the pages read, so an answer matches the stock page for the same close.</li>
</ul></div>
</section>
"""
    site.add(path, site.shell(path, "For AI tools: connect Claude, ChatGPT and other assistants",
                              "Be The Puck's signal, plays and read for AI assistants: a remote MCP server for Claude and a JSON API for ChatGPT and others. "
                              "A free sample without a key; everything with a member's key.",
                              body, active="", link=False))
