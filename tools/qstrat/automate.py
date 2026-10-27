"""Automate with Claude (AUD-51, Dave, Oct 27, 2026): "extensive articles about how to automate buying and selling with
claude using the data supplied by our site ... make sure across sites that this is not financial advice and that they
should find a broker. Then show available brokers ... and which manage money. Then show other sites that allow you to
match and mirror and do other angles. It should also provide these tools when possible."

Dave's choices: a plain directory (no affiliation, no endorsements, no ranking), members get an API key, and every
setup keeps the reader approving each order in their own broker, with paper trading first.

    guides/brokers/                     free: self-directed brokers, managed accounts, copy and follow platforms, the rules
    articles/automate-with-claude/      members: Claude reads the signal, applies your written rules, drafts; you approve
    articles/automate-build-it/         members: the downloadable script (assets/downloads/bethepuck_drafts.py), paper first
    articles/copy-mirror-follow/        members: the other angles, what each does with your money, what to check
    articles/before-you-automate/       free: who answers for an order, trading and tax rules, scams, a checklist

Every fact about a firm comes from brokers.json, checked on the firm's or a regulator's own pages on Oct 27, 2026 (the
research notes what couldn't be confirmed, and the pages say so). Nothing here ranks or recommends a firm, and no
example is a suggestion: every number in a rule is a placeholder for the reader's own.
"""
import html
import json
import os
import re

from .content import TIMED, TICKERS
from .members import PRICE, FREE_UNTIL
from .render import DISCLAIMER
from .agents import FREE_PER_DAY

e = html.escape
CHECKED = "Oct 27, 2026"
DIR = "guides/brokers/"
DOWNLOADS = "assets/downloads/"
SCRIPT = os.path.join(os.path.dirname(__file__), "..", "..", "assets", "downloads", "bethepuck_drafts.py")
with open(os.path.join(os.path.dirname(__file__), "brokers.json"), encoding="utf-8") as _f:
    DATA = json.load(_f)
BROKERS, MANAGERS, PLATFORMS, RULES, ANTHROPIC = (DATA[k] for k in ("brokers", "managers", "copy_platforms", "rules", "anthropic"))

BUCKET = ("automate", "Automate with Claude",
          "How to have Claude read Be The Puck's signal on your stocks and draft the orders your own rules call for, with every order "
          "approved by you at your own broker: the setups, a script to start on paper, the platforms that copy and follow, and the rules first.")
PIECES = [
    ("articles/automate-with-claude/", "Automating with Claude, the careful way: it drafts, you approve",
     "Claude reads Be The Puck's signal on your stocks each day, applies rules you wrote, and drafts the orders they call for. "
     "You approve every one in your own broker. Three ways to get the drafts there, and the setups we leave out."),
    ("articles/automate-build-it/", "Build it: a daily check that drafts orders, tested on paper first",
     "A short Python script to download: it reads the signal on your list, applies your rules, saves the drafts, and offers each "
     "one to a paper account only when you type yes. How to set it up, test it, and change it with Claude."),
    ("articles/copy-mirror-follow/", "Copy, mirror and follow: the other ways to automate, and what each one really does",
     "Copy a stranger's portfolio, subscribe to a strategy that trades your account, track politicians' filings, build rules "
     "without code, or only get the data: eleven platforms, what each does with your money, and what to check first."),
    ("articles/before-you-automate/", "Before you automate: the rules, the risks, and who answers for every order",
     "Whoever drafts an order, the account holder owns it. The trading and tax rules in the U.S. and Canada that automated rules "
     "run into, the scams that use AI as bait, and a checklist for before any rule touches real money."),
]
FREE = {"articles/before-you-automate/"}

# The directory's short answers, one per broker, read from the full records in brokers.json (checked Oct 27, 2026).
# where: (Canada, U.S.) residents can open; flags: practice account, own program (API), AI assistant.
SHORT = {
    "Interactive Brokers (IBKR)": ("Canada and U.S.", (1, 1), "U.S.: from $0.005 a share, $1 minimum (IBKR Fixed); $0 on IBKR Lite for U.S. residents. Canada: 1¢ a share, $1 minimum",
                                   "Yes, with every account", "Yes (TWS API, Web API)", "Yes: you review and submit each order (AI Integration)", (1, 1, 1)),
    "Questrade": ("Canada", (1, 0), "$0 on stocks and ETFs", "A practice site exists; its terms weren't confirmed",
                  "Read-only for individuals (trading is for partner developers)", "Yes: it drafts, you approve or decline each order in the Questrade app", (0, 0, 1)),
    "Wealthsimple (self-directed investing)": ("Canada", (1, 0), "$0; 1.5% currency fee on U.S. trades in a CAD account", "None found", "None found", "None found", (0, 0, 0)),
    "Qtrade Direct Investing": ("Canada", (1, 0), "$0 on stocks and ETFs", "No (the trial account is view-only)", "None found", "None found", (0, 0, 0)),
    "TD Direct Investing": ("Canada", (1, 0), "$9.99 ($7 at 150+ trades a quarter)", "Yes (TD Active Trader practice account)", "None found", "None found", (1, 0, 0)),
    "RBC Direct Investing": ("Canada", (1, 0), "$9.95 ($6.95 for active traders)", "Yes ($100,000 practice account)", "None found", "None found", (1, 0, 0)),
    "BMO InvestorLine (Self-Directed)": ("Canada", (1, 0), "$0 on stocks and ETFs (since Sept 14, 2026)", "None found", "None found", "None found", (0, 0, 0)),
    "CIBC Investor's Edge": ("Canada", (1, 0), "$6.95 ($4.95 for active investors; $0 under 25)", "None found", "None found", "None found", (0, 0, 0)),
    "Scotia iTRADE": ("Canada", (1, 0), "$9.99 ($4.99 at 150+ trades a quarter)", "None found", "None found", "None found", (0, 0, 0)),
    "National Bank Direct Brokerage (NBDB)": ("Canada", (1, 0), "$0 on stocks and ETFs", "None found", "None found", "None found", (0, 0, 0)),
    "Charles Schwab": ("U.S.", (0, 1), "$0 on U.S. stocks and ETFs; $6.95 on Canadian listings", "Yes (thinkorswim paperMoney)",
                       "Yes (Trader API for individuals)", "Through the Trader API; outside apps are reviewed", (1, 1, 1)),
    "Fidelity Investments": ("U.S.", (0, 1), "$0 on U.S. stocks and ETFs", "None found", "None found for individuals", "None found", (0, 0, 0)),
    "E*TRADE from Morgan Stanley": ("U.S.", (0, 1), "$0 on U.S. stocks and ETFs", "Yes (Power E*TRADE; API sandbox)", "Yes (Developer Platform API)", "None found", (1, 1, 0)),
    "Robinhood": ("U.S.", (0, 1), "$0 on stocks and ETFs", "None found", "No stock API found (a crypto API exists)", "Yes, in a separate account; it can trade without asking if you set it to", (0, 0, 1)),
    "Webull (Webull Financial LLC in the US; Webull Securities (Canada) Limited in Canada)":
        ("Canada and U.S.", (1, 1), "$0 on stocks and ETFs", "Yes, in both countries", "Yes in the U.S. (OpenAPI); Canada not confirmed",
         "Agent Skills for AI assistants, with optional preview and limits", (1, 1, 1)),
    "Alpaca": ("U.S. and many other countries; not Canadian residents", (0, 1), "$0 through its API", "Yes, free, up to 3 paper accounts",
               "Yes: built around its API", "Yes (MCP), paper by default", (1, 1, 1)),
    "Tradier Brokerage": ("U.S. and permitted countries; not Canadian residents", (0, 1), "$0.35 a trade on the free plan; $0 on paid plans",
                          "Yes (sandbox with delayed prices)", "Yes", "None found", (1, 1, 0)),
    "tastytrade": ("U.S.; Canada not confirmed", (0, 1), "$0 on stocks and ETFs", "API sandbox only", "Yes (Open API)", "An MCP option is mentioned", (1, 1, 1)),
}
NAME = {"Webull (Webull Financial LLC in the US; Webull Securities (Canada) Limited in Canada)": "Webull",
        "Wealthsimple (self-directed investing)": "Wealthsimple", "BMO InvestorLine (Self-Directed)": "BMO InvestorLine",
        "National Bank Direct Brokerage (NBDB)": "National Bank Direct Brokerage", "Interactive Brokers (IBKR)": "Interactive Brokers",
        "E*TRADE from Morgan Stanley": "E*TRADE", "Composer (Composer by SoFi)": "Composer", "Public.com (Individual API and MCP)": "Public.com"}
ANGLE = {"eToro CopyTrader": "Copy a person", "dub": "Copy a person", "Autopilot": "Copy a person (filings)", "Collective2": "A strategy trades your account",
         "Composer (Composer by SoFi)": "Your rules, run for you", "Surmount": "Your rules, run for you", "Public.com (Individual API and MCP)": "An AI trades through your broker",
         "Quiver Quantitative": "Data and alerts", "Unusual Whales": "Data and alerts", "Tickeron": "Data and alerts", "TradingView": "Charts and alerts; trades through your broker",
         "Iris": "Now part of Autopilot"}
EXTRA_SOURCES = {
    "connectors": ("Claude Help Center: get started with custom connectors using remote MCP", "https://support.claude.com/en/articles/11175166-get-started-with-custom-connectors-using-remote-mcp"),
    "scheduled": ("Claude Help Center: scheduled tasks", "https://support.claude.com/en/articles/13854387-schedule-rec"),
    "washsale": ("IRS Publication 550, Investment Income and Expenses (wash sales)", "https://www.irs.gov/publications/p550"),
    "superficial": ("TaxTips.ca: superficial losses and other disallowed losses", "https://www.taxtips.ca/personaltax/investing/taxtreatment/superficial-losses-and-other-disallowed-losses.htm"),
    "tfsa": ("Investment Executive (Jamie Golombek, July 24, 2017): day trading in a TFSA or RRSP", "https://www.investmentexecutive.com/inside-track_/jamie-golombek/day-trading-in-a-tfsa-or-rrsp/"),
    "stock_act": ("STOCK Act (Wikipedia): periodic transaction reports within 45 days", "https://en.wikipedia.org/wiki/STOCK_Act"),
}


def nm(x):
    return NAME.get(x["name"], x["name"])


def find(items, start):
    return next(x for x in items if x["name"].startswith(start))


def src_of(x, n=None):
    """(label, url) pairs for a firm's sources, labelled by firm and host."""
    out = []
    for s in (x.get("sources") or [])[:n]:
        u = s["url"]
        host = re.sub(r"^https?://(www\.)?", "", u).split("/")[0]
        out.append((f"{nm(x)}: {host}", u))
    return out


def rule(topic_start):
    return next(r for r in RULES if r["topic"].startswith(topic_start))


def links(sources):
    return " ".join(f'<a href="{e(u)}" rel="noopener nofollow" target="_blank">{e(lab)}</a>' for lab, u in sources)


def code(text, wrap=False):
    return f'<pre class="dev-code{" wrap" if wrap else ""}"><code>{e(text)}</code></pre>'


def copyable(text, label="Copy"):
    return (f'<div class="auto-copy"><pre class="dev-code"><code>{e(text)}</code></pre>'
            f'<button type="button" class="btn sm" data-copy-prev>{e(label)}</button></div>')


def signal_bits():
    """The signal's own mechanics, worded from factors.py so the guides can't drift from the site."""
    from .factors import DEFAULT, BUY, SELL, MID, GUARD, default_words
    return {"words": default_words(), "buy": BUY, "sell": SELL, "mid": MID, "guard": round(GUARD * 100), "n": len(TIMED), "w": DEFAULT}


# ================================================================ the directory (free)
def directory(site):
    path, depth = DIR, 2
    h = lambda x: site.href(depth, x)
    rows, cards = "", ""
    for b in BROKERS:
        where, (ca, us), trades, paper, own, ai, (fp, fa, fai) = SHORT[b["name"]]
        rows += (f'<tr data-ca="{ca}" data-us="{us}" data-paper="{fp}" data-api="{fa}" data-ai="{fai}"><td><a href="#b-{_slug(nm(b))}"><b>{e(nm(b))}</b></a></td>'
                 f'<td>{e(where)}</td><td>{e(trades)}</td><td>{e(paper)}</td><td>{e(own)}</td><td>{e(ai)}</td></tr>')
        reg = b.get("regulator") or {}
        api = b.get("public_api") or {}
        unv = "".join(f"<li>{e(x)}</li>" for x in (b.get("unverified") or []))
        recent = "".join(f"<li>{e(x)}</li>" for x in (b.get("recent_changes") or []))
        cards += f"""<details class="card auto-firm" id="b-{_slug(nm(b))}" data-ca="{ca}" data-us="{us}" data-paper="{fp}" data-api="{fa}" data-ai="{fai}">
<summary><span class="name">{e(nm(b))}</span><span class="small muted">{e(where)} · {e(b.get("known_for") or "")}</span></summary>
<dl class="auto-dl">
<dt>Who can open an account</dt><dd>{e(b.get("who_can_open") or "")}</dd>
{''.join(f"<dt>Regulated ({'Canada' if k == 'canada' else 'U.S.'})</dt><dd>{e(v)}</dd>" for k, v in reg.items())}
<dt>U.S. stock trades</dt><dd>{e(b.get("commission_us_stocks") or "")}</dd>
<dt>Canadian stock trades</dt><dd>{e(b.get("commission_cdn_stocks") or "")}</dd>
<dt>Registered and retirement accounts</dt><dd>{e(b.get("registered_accounts") or "")}</dd>
<dt>Practice (paper) account</dt><dd>{e(b.get("paper_trading") or "")}</dd>
<dt>Your own program</dt><dd>{e(", ".join(api.get("names") or []) or "None found")}{(" · " + e(api.get("requirements"))) if api.get("requirements") and api.get("requirements") != "None found." else ""}</dd>
<dt>AI assistants</dt><dd>{e(api.get("ai_connection") or "None found.")}</dd>
{f"<dt>Recent changes</dt><dd><ul>{recent}</ul></dd>" if recent else ""}
{f"<dt>Not confirmed</dt><dd><ul>{unv}</ul></dd>" if unv else ""}
</dl>
<p class="small muted">Checked {CHECKED}: {links(src_of(b))}</p></details>"""
    mrows = "".join(f'<tr data-ca="{1 if "Canada" in m["country"] else 0}" data-us="{1 if "United States" in m["country"] else 0}"><td><a href="{e(m["url"])}" rel="noopener nofollow" target="_blank"><b>{e(m["name"])}</b></a>'
                    f'<span class="sym-sub">{e(m.get("known_for") or "")}</span></td><td>{e(m["country"].split(" (")[0])}</td><td>{e(m.get("minimum") or "")}</td>'
                    f'<td>{e(m.get("management_fee") or "")}</td><td class="adv-col small">{e(m.get("regulator") or "")}</td></tr>' for m in MANAGERS)
    prows = ""
    for p in PLATFORMS:
        if p["name"] == "Iris":
            continue
        av = p.get("availability") or {}
        places = p.get("places_trades")
        places = "Yes" if places is True else ("No" if places is False else str(places))
        status = p.get("status")
        prows += ('<tr>'
                  f'<td><a href="{e(p["url"])}" rel="noopener nofollow" target="_blank"><b>{e(nm(p))}</b></a><span class="sym-sub">{e(ANGLE.get(p["name"], ""))}</span></td>'
                  f'<td>{e(p["what_it_does"])}{(" <span class=small muted>" + e(status) + "</span>") if status else ""}</td><td>{e(places)}</td>'
                  f'<td class="small">U.S.: {e(av.get("us") or "")}<br>Canada: {e(av.get("canada") or "")}</td><td class="small">{e(p.get("price") or "")}</td>'
                  f'<td class="adv-col small">{e(p.get("regulator_or_broker") or "")}</td></tr>')
    iris = find(PLATFORMS, "Iris")
    filt = ('<div class="auto-filter card" data-auto-filter hidden><span class="small muted">Show:</span>'
            '<div class="seg" role="group" aria-label="Where you live"><button type="button" data-where="all" aria-pressed="true">Everyone</button>'
            '<button type="button" data-where="ca" aria-pressed="false">Canadian residents</button><button type="button" data-where="us" aria-pressed="false">U.S. residents</button></div>'
            '<label class="small"><input type="checkbox" data-need="paper"> Practice account</label>'
            '<label class="small"><input type="checkbox" data-need="api"> Your own program</label>'
            '<label class="small"><input type="checkbox" data-need="ai"> AI assistant</label>'
            '<span class="small muted" data-auto-count></span></div>')
    rules = "".join(f'<li><b>{e(r["topic"])}.</b> {e(r["summary"])} <span class="small muted">Sources: {links([(_host(s["url"]), s["url"]) for s in r["sources"]])}</span></li>' for r in RULES)
    body = f"""
<nav class="crumbs"><a href="{h('guides/')}">Guides</a><span>/</span><span>Brokers and platforms</span></nav>
<section class="pair-head"><p class="eyebrow">Directory · checked {CHECKED}</p><h1 class="h1">Brokers, managed accounts, and the platforms that copy and follow</h1>
<p class="lede">Be The Puck is not a broker or an adviser and never places trades. To buy or sell anything you need an account at a registered broker, or a firm that manages the money for you. Here are {len(BROKERS)} brokers, {len(MANAGERS)} managed-account services and {len(PLATFORMS) - 1} copy, follow and automation platforms, with what each one says about itself: who can open an account, what a trade costs, and whether a practice account, your own program or an AI assistant can connect.</p>
<p class="auto-note small"><b>A plain list, not a ranking.</b> Be The Puck has no affiliation with any firm here, takes no payment or referral fee from any of them, and doesn't endorse one over another. The order is by country and kind, nothing else.</p></section>

<section class="split auto-qs">
<div class="card prose"><p class="eyebrow">Three questions first</p><ol>
<li><b>Where do you live?</b> Who can open an account depends on it: most firms here serve one country, and a few take residents of many. The second column says who can open, as each firm states it.</li>
<li><b>Do you want to place your own orders, or have the money managed?</b> A self-directed broker takes your orders and gives no advice. A managed account builds and rebalances a portfolio for a yearly fee.</li>
<li><b>Does a program or an AI need to connect?</b> Only some brokers have an API, a practice account, or a way for an AI assistant to draft or place orders. The last three columns below say which.</li></ol></div>
<div class="card prose"><p class="eyebrow">Check the firm, not the list</p><p>Before opening any account, look the firm up on the official register for your country: CIRO's and CIPF's in Canada, FINRA BrokerCheck and the SEC's adviser search in the U.S. <a href="{h('guides/ways-to-invest/')}">Ways to invest, by country</a> links each register and explains what each kind of firm must promise you.</p>
<p>Want Claude to work with your broker? <a href="{h('articles/automate-with-claude/')}">Automating with Claude, the careful way</a> shows three setups where you approve every order, and <a href="{h('articles/before-you-automate/')}">Before you automate</a> (free) has the rules.</p></div></section>

<section id="brokers"><div class="sec-head"><h2 class="h2">Self-directed brokers: you place the orders</h2><p>Order-execution-only in Canada (no advice, no suitability check) and self-directed in the U.S. Fees are the online stock and ETF commission each firm published; other fees apply at most of them.</p></div>
{filt}
<div class="tbl-wrap"><table class="tbl auto-tbl" data-auto-rows data-nosort><thead><tr><th scope="col">Broker</th><th scope="col">Who can open</th><th scope="col">Stock trades</th><th scope="col">Practice account</th><th scope="col">Your own program</th><th scope="col">AI assistant</th></tr></thead>
<tbody>{rows}</tbody></table></div>
<p class="small muted">"None found" means we looked on the firm's site and didn't find it, not that the firm says it doesn't exist.</p>
<h3 class="h3 auto-sub">Each broker in full</h3><p class="small muted">Tap a name for who regulates it, every fee we found, its accounts, its API and AI terms, what changed lately, what we couldn't confirm, and the sources.</p>
<div class="auto-firms" data-auto-rows>{cards}</div></section>

<section id="managed"><div class="sec-head"><h2 class="h2">Firms that manage the money for you</h2><p>Often called robo-advisors: you choose a portfolio by answering questions, and the firm picks the funds, rebalances and charges a yearly fee on top of the funds' own costs. They don't take outside signals, Be The Puck's included.</p></div>
<div class="tbl-wrap"><table class="tbl auto-tbl" data-auto-rows data-nosort><thead><tr><th scope="col">Service</th><th scope="col">Country</th><th scope="col">Minimum</th><th scope="col">Yearly fee</th><th scope="col" class="adv-col">Who regulates it</th></tr></thead>
<tbody>{mrows}</tbody></table></div>
<p class="adv-cols-note small"><button type="button" class="linkish" data-adv-cols>Show who regulates each one</button></p>
<p class="small muted">Sources: {links([x for m in MANAGERS for x in src_of(m, 1)])}</p></section>

<section id="copy"><div class="sec-head"><h2 class="h2">Copy, mirror and follow: other angles</h2><p>Platforms that copy another investor's portfolio into yours, send a published strategy's trades to your broker, run rules you build, let an AI trade through the account, or only sell the data and alerts. What each does with your money, and who stands behind it, differs a lot; <a href="{h('articles/copy-mirror-follow/')}">Copy, mirror and follow</a> goes through what to check.</p></div>
<div class="tbl-wrap"><table class="tbl auto-tbl" data-nosort><thead><tr><th scope="col">Platform</th><th scope="col">What it does</th><th scope="col">Places trades?</th><th scope="col">Where</th><th scope="col">Price</th><th scope="col" class="adv-col">Who holds the money, who is registered</th></tr></thead>
<tbody>{prows}</tbody></table></div>
<p class="adv-cols-note small"><button type="button" class="linkish" data-adv-cols>Show who holds the money and who is registered</button></p>
<p class="small muted">{e(iris["what_it_does"])} Sources: {links([x for p in PLATFORMS for x in src_of(p, 1)])}</p></section>

<section class="card prose" id="rules"><p class="eyebrow">The rules that apply</p><h2 class="h3">Before a program or an AI touches an account</h2><ul class="auto-rules">{rules}</ul>
<p class="small"><a href="{h('articles/before-you-automate/')}">Before you automate</a> puts these in plain English with the tax rules and a checklist.</p></section>

<section class="card prose"><p class="small muted">Facts as each firm or regulator published them, checked {CHECKED}. Prices, eligibility and features change; the firm's own page is the authority. Be The Puck is not registered as a dealer, adviser or planner anywhere, takes no payment from any firm named here, and takes no positions in the names it covers. {DISCLAIMER}</p></section>
"""
    site.add(path, site.shell(path, "Brokers, managed accounts and copy platforms: a plain directory",
                              f"{len(BROKERS)} brokers in Canada and the U.S., {len(MANAGERS)} managed-account services and {len(PLATFORMS) - 1} copy, follow and automation platforms: "
                              "who can open one, what a trade costs, and which take a practice account, your own program or an AI assistant. No affiliation, no ranking.",
                              body, active="learn/", link=False, scripts=("assets/automate.js",)))


def _host(u):
    return re.sub(r"^https?://(www\.)?", "", u).split("/")[0]


def _slug(s):
    return re.sub(r"[^a-z0-9]+", "-", s.lower()).strip("-")


# ================================================================ the articles
def plan(A):
    for sp, title, dek in PIECES:
        A.list.append((BUCKET[0], sp, title, dek, "written", _date()))


def _date():
    import pandas as pd
    return pd.Timestamp("2026-10-27")


def build(A):
    with_claude(A)
    build_it(A)
    copy_follow(A)
    before(A)


def _piece(sp):
    return next(p for p in PIECES if p[0] == sp)


def _tools_table():
    from .agents import TOOLS
    return ('<div class="tbl-wrap"><table class="tbl" data-nosort><thead><tr><th scope="col">Tool Claude sees</th><th scope="col">Who</th><th scope="col">What it answers</th></tr></thead><tbody>'
            + "".join(f'<tr><td><code>{e(n)}</code></td><td>{"Free sample" if t == "free" else "Members"}</td><td>{e(w)}</td></tr>' for n, p, t, w in TOOLS)
            + "</tbody></table></div>")


DAILY_PROMPT = """Use the Be The Puck connector. My stocks: [MU, NVDA, SHOP.TO, SPY].
What I hold: [NVDA, 5 shares]. My account is worth about [$10,000].

For each stock, get Be The Puck's signal and tell me the signal, the score,
the close date, whether the call is held by the sticky rule, whether the
market guard is on, and the close that would change the call.

Then apply my rules below exactly as written and list the orders they call
for as drafts: ticker, buy or sell, number of shares, and the rule that
called for it. Don't place or send anything. If a rule doesn't clearly
apply, or a number looks wrong, say so instead of guessing.

My rules:
1. When the signal reads Buy and I own none: buy about [$1,000], never
   more than [10%] of the account in one stock.
2. When the signal reads Sell and I own it: sell the whole position.
3. No new buys while the market guard is on.
4. Hold means do nothing."""


def with_claude(A):
    sp, title, dek = _piece("articles/automate-with-claude/")
    h = A.h(sp.count("/"))
    S = signal_bits()
    ib, qt, rh, pub = find(BROKERS, "Interactive"), find(BROKERS, "Questrade"), find(BROKERS, "Robinhood"), find(PLATFORMS, "Public")
    pol_now, pol_new = ANTHROPIC[0], ANTHROPIC[1]
    body = f"""
<section class="prose"><h2 class="h2">What this is, and what it isn't</h2>
<p>Automating, in these guides, means one thing: Claude does the reading and the drafting, and you make every decision. Each day it checks Be The Puck's signal on the stocks you follow, compares what it finds with rules you wrote down in advance, and lists the orders those rules call for. You read the list, check anything that looks off on the stock's page, and then place or approve each order yourself, in your own account at a registered broker.</p>
<p>It isn't a robot that trades for you. Be The Puck is not a broker or an adviser and never places trades: its connector and API can only read. Claude isn't a broker either. A few brokers now let an AI place orders without asking; they're described at the end, factually, and none of the setups here uses them.</p></section>

<section class="card prose auto-need"><p class="eyebrow">What you need</p><ul>
<li><b>A Be The Puck member key.</b> Membership is {PRICE} a month, and every member tool is free for any account until {FREE_UNTIL}. The key unlocks your own weights, the factor points behind each score, the closes that would flip each call, the screener and market conditions. Without one, the free sample still answers the standard signal on one stock at a time. <a href="{h('developers/')}#key">How to get a key</a>.</li>
<li><b>Claude, with Be The Puck added as a connector.</b> Custom connectors work on every Claude plan; a free account can add one. Steps below.</li>
<li><b>An account at a registered broker.</b> <a href="{h(DIR)}">The broker directory</a> lists {len(BROKERS)} in Canada and the U.S., with which ones take a practice account, your own program or an AI assistant.</li>
<li><b>Your rules, written down</b>, before any of the rest.</li></ul></section>

<section class="prose"><h2 class="h2">1. Write your rules down first</h2>
<p>A rule is something you could hand to a stranger and get the same orders back. "Buy good companies when they're cheap" isn't one. "When the signal on a stock in my list turns Buy and I own none, buy about $1,000 of it" is. Claude is good at applying a rule exactly and poor at guessing what you meant, so the deciding happens here, once, while nothing is moving and no price is pulling at you.</p></section>
<div class="card rule-card auto-rule"><p class="eyebrow">The shape of a rule set</p><p class="small muted">Every number is a placeholder for your own. None of it is a suggestion.</p><ol>
<li>Only the stocks on my list: <i>[your tickers]</i>.</li>
<li>When Be The Puck's signal reads Buy and I own none: draft a buy of <i>[amount]</i>, and never more than <i>[share]</i> of the account in one stock.</li>
<li>When it reads Sell and I own it: draft a sale of the whole position.</li>
<li>While the market guard is on: no new buys. Sells are still drafted.</li>
<li>Hold means do nothing. A call held by the sticky rule counts as the call it shows.</li>
<li>No more than <i>[number]</i> new buys on one day.</li></ol></div>
<section class="prose"><p>Rules like those lean on the signal's own mechanics, so it's worth knowing them exactly. The standard signal weighs {e(S["words"])}; it reads Buy at a score of {S["buy"]} or more and Sell at {S["sell"]} or less. On the standard weights a Buy holds until the score drops below {S["mid"]}, and a Sell until it rises above {S["mid"]}, so a stock hovering near a line doesn't flip every day. When the S&amp;P 500 or the TSX is {S["guard"]}% or more below its 1-year high, the market guard is on and the price factors stand down. <a href="{h('guides/your-plays/')}#your-signal">Your signal, explained</a> has each piece, and <a href="{h('articles/calls-graded/')}">this week's calls, graded</a> shows how the standard calls have done since October 13, week by week, in public.</p></section>

<section class="prose"><h2 class="h2">2. Connect Be The Puck to Claude</h2>
<ol><li>In Claude, open <b>Customize &gt; Connectors</b>, choose <b>+ Add</b>, then <b>Add custom connector</b>. On a Team plan an owner adds it under <b>Organization settings &gt; Connectors</b> (on Enterprise, an owner or a custom role that can manage connectors).</li>
<li>Name it Be The Puck and enter <code>https://bethepuck.com/mcp</code> as the server address. Choose <b>No sign in</b>.</li>
<li>Under <b>Request headers</b>, add <code>authorization</code> with the value <code>Bearer btp_…</code> (your key). Or skip the header and use your secret address, <code>https://bethepuck.com/mcp/k/btp_…</code>, which works the same way. Either one is a password: keep it out of chats, screenshots and shared files.</li>
<li>In a chat, open <b>+</b>, then <b>Connectors</b>, and turn Be The Puck on.</li></ol>
<p>In Claude Code, from a terminal: <code>claude mcp add --transport http bethepuck https://bethepuck.com/mcp --header "Authorization: Bearer btp_…"</code>. <a href="{h('developers/')}">For AI tools</a> has ChatGPT and other clients. Claude then sees these tools, and picks the right one when you ask in plain words:</p>
{_tools_table()}
<p>Try: <i>"What does Be The Puck say about Micron right now, and what close would change the call?"</i> The answer comes back with its close date and the disclaimer, like every answer from Be The Puck.</p></section>

<section class="prose"><h2 class="h2">3. The daily check</h2>
<p>Paste this into a chat with the connector on, and replace everything in square brackets with your own stocks, holdings and numbers. They're placeholders, not suggestions.</p></section>
{copyable(DAILY_PROMPT, "Copy the prompt")}
<section class="prose"><p>Run it after the U.S. close or before the next open. Be The Puck rebuilds after each U.S. close and every answer carries its close date, so check that the date is the latest trading day before acting on anything. If you tell Claude what you hold, it can work out share counts; if you'd rather not, ask for the signals and the rule that applies to each, and do the arithmetic yourself.</p>
<p>Two ways to make it a habit without watching the screen: on a paid Claude plan, <b>scheduled tasks</b> can run the same prompt on a schedule, with your connectors. Or turn on Be The Puck's free <a href="{h('alerts/')}">email alerts</a>, which write when the signal flips on one of your stocks, and run the check then. Most days nothing flips and nothing needs drafting.</p></section>

<section class="prose"><h2 class="h2">4. Get the drafts to your broker</h2><p>Three ways, from the most hands-on. All three keep you approving each order.</p></section>
<div class="grid grid-3 auto-ways">
<div class="card prose"><p class="eyebrow">Works with every broker</p><h3 class="h3">Enter them yourself</h3><p>Copy each draft into your broker's order ticket, look at the price, and submit. It's the only way at brokers where we found no API or AI connection when we checked ({CHECKED}), which includes Wealthsimple, the bank-owned Canadian brokers and Fidelity. It takes a minute an order, and it puts your eyes on every one.</p></div>
<div class="card prose"><p class="eyebrow">A broker that asks each time</p><h3 class="h3">Questrade or Interactive Brokers</h3><p><b>Questrade</b> (Canada): its MCP connects Claude; reading is always allowed and trading only if you grant it. The assistant drafts an order preview and you approve or decline every order in the Questrade app; it can't place, change or cancel an order on its own, or move money. <b>Interactive Brokers</b> (Canada and U.S.): its AI Integration connects Claude through an IBKR-hosted MCP server, and you review and submit every order. With Be The Puck and the broker both on in one chat, Claude can read the signal and put the draft where you approve it.</p></div>
<div class="card prose"><p class="eyebrow">Your own program</p><h3 class="h3">A script, on paper first</h3><p>A short script reads the signal, applies your rules, saves the drafts to a spreadsheet, and offers each one to a paper (practice) account only when you type yes. <a href="{h('articles/automate-build-it/')}">Build it</a> has the download and the setup. With no broker connected it still writes the drafts, for any broker.</p></div></div>
<p class="small muted">Questrade's setup as Questrade describes it, reported Sept 7, 2026; IBKR's as IBKR describes it. Both were checked {CHECKED}: {links(src_of(qt)[5:8] + src_of(ib)[10:12])}</p>

<section class="prose"><h2 class="h2">The setups these guides leave out</h2>
<p>Some brokers now let an AI place orders without asking each time. They exist, they're offered under each broker's own terms, and those terms say the orders are yours:</p>
<ul><li><b>Robinhood Agentic</b> (U.S., an early-access release since May 27, 2026): the AI trades in a separate account you fund, equities only at launch. Approval is a setting: if you tell the agent to act without asking, it can place trades without your confirmation, and it gets read access to all your Robinhood accounts.</li>
<li><b>IBKR Autonomous Trading</b> (announced Oct 21, 2026): connected AI submits supported orders without per-order approval inside a dedicated "AI Partition", for individual non-margin accounts, after 10 trades of $100 or more over two weeks approved one by one. IBKR says availability varies by entity and country; Canada wasn't stated.</li>
<li><b>Public.com's API and MCP</b> (U.S.): trades may be executed by your AI agent without your direct input on each one, and are deemed authorized by you.</li></ul>
<p>Be The Puck's guides keep a person approving each order because a rule-based signal can be wrong in ways a person catches at a glance: a price file with a glitch, a stale close, a company halted on news, or a rule that fires on a stock you meant to leave alone.</p></section>

<section class="split"><div class="card prose"><p class="eyebrow">What Claude does well here</p><ul>
<li>Applies written rules the same way every day, without getting bored or hopeful.</li><li>Notices what changed since yesterday, and which rule it touches.</li>
<li>Explains a call in plain words, with the factor points behind it.</li><li>Says when a rule doesn't fit a case, if you ask it to.</li></ul></div>
<div class="card prose"><p class="eyebrow">Where it needs you</p><ul>
<li>It doesn't know your taxes, your goals or the rest of your money unless you tell it, and those are what decide whether a rule suits you.</li>
<li>It can misread a number or slip on arithmetic: check share counts and amounts.</li>
<li>It only knows what the connectors return, as of the close shown.</li><li>A confident tone isn't evidence. The stock's page and the play records are.</li></ul></div></section>

<section class="prose"><h2 class="h2">Anthropic's rules for financial uses</h2>
<p>Anthropic's Usage Policy, in force since Sept 15, 2025, treats financial uses as high-risk: they need a human in the loop to oversee outputs, and disclosure that AI is involved. An update published Oct 8, 2026 and effective Nov 12, 2026 spells finance out: a personalized recommendation to buy, sell, hold or allocate among specific investments must be reviewed by a qualified person before it reaches the individual or is used to carry out a decision, and the person must be told AI was used. Not covered: general financial education that isn't applied to someone's own situation, and internal research and drafting. The text doesn't say how the rules apply when the person using Claude and the person getting the recommendation are the same, and it says users are responsible for actions their agents take through connected systems.</p>
<p>The setups here keep the decision with you: the rules are yours, Claude applies them and drafts, and you approve each order. Whether a particular use fits the policy is for you to judge from the policy itself, linked below.</p></section>
<p class="small"><a href="{h('articles/before-you-automate/')}">Before you automate</a> (free) covers the trading and tax rules, scams and a checklist. <a href="{h(DIR)}">The broker directory</a> has every firm mentioned here.</p>
"""
    srcs = [("Be The Puck: for AI tools", "https://bethepuck.com/developers/"), EXTRA_SOURCES["connectors"], EXTRA_SOURCES["scheduled"]]
    srcs += src_of(qt)[5:8] + src_of(ib)[10:13] + src_of(rh)[3:5] + src_of(pub)[1:3]
    srcs += [("Anthropic: usage policy update (2025)", pol_now["sources"][0]["url"]), ("Anthropic: 2026 usage policy update", pol_new["sources"][0]["url"])]
    A.shell(sp, BUCKET[0], title, dek, body, sources=srcs, related=A.related(sp.count("/"), [p for p, _, _ in PIECES if p != sp]),
            date=_date(), free=sp in FREE)


def _script():
    """The downloadable script itself, loaded as a module (its main() only runs from the command line)."""
    import importlib.util
    spec = importlib.util.spec_from_file_location("bethepuck_drafts", SCRIPT)
    mod = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(mod)
    return mod


def _example(site):
    """What a dry run with the sample rules file would print at the latest close: the script's own draft() and wording,
    fed the site's own signal for the sample tickers, so it can't drift from the script or go stale."""
    from .factors import score, held, guard_on, BUY, SELL, MID
    mod = _script()
    with open(os.path.join(os.path.dirname(SCRIPT), "bethepuck_rules.json"), encoding="utf-8") as f:
        rules = {**mod.DEFAULT_RULES, **json.load(f)}
    hold = {str(k).upper(): float(v) for k, v in (rules.get("holdings") or {}).items()}
    value = float(rules.get("account_value") or 0)
    by = {t["sym"]: t for t in TICKERS}
    out, n = [], 0
    for sym in rules["tickers"]:
        t = by.get(sym)
        if not t or (sym, "buy-and-hold") not in site.R or t.get("requested"):
            continue
        sc, sg, _ = score(site, t)
        word = {1: "Buy", 0: "Hold", -1: "Sell"}.get(sg, "?")
        mk = "ca" if sym.endswith(".TO") else ("crypto" if t.get("crypto") else ("fund" if t["group"] in ("Indexes & ETFs", "Sectors") else "us"))
        j = {"symbol": sym, "ticker": t["short"], "signal": word, "score": sc, "close": float(site.r(sym, "buy-and-hold")["price"]),
             "currency": "CAD" if sym.endswith(".TO") else "USD", "market": mk, "guard": bool(guard_on(site, sym))}
        d, why = mod.draft(j, rules, hold, value)
        n += bool(d)
        out.append(f"{sym:<9} {word:<5} score {str(sc):<4} {why}")
        extra = []
        if held(site, t, sc, sg):              # the API's wording (agentdata.mjs heldWords), as the script prints it
            extra.append(f"Held at Buy: the score of {sc} is under the Buy line of {BUY}, and a Buy holds until the score drops below {MID}." if sg == 1
                         else f"Held at Sell: the score of {sc} is over the Sell line of {SELL}, and a Sell holds until the score rises above {MID}.")
        if j["guard"]:
            extra.append("Market guard on: the price factors stand down and the rest of the weights decide.")
        if extra:
            out.append("          " + " · ".join(extra))
    asof = site.asof.strftime("%Y-%m-%d")
    tail = (f"{n} draft(s) saved to …/drafts-YYYY-MM-DD.csv (the day you run it)\nNothing was sent anywhere. Enter any order you decide on at your broker yourself."
            if n else f"No drafts: your rules call for nothing at the {asof} close.")
    return (f"Be The Puck daily drafts {mod.VERSION}\n{mod.DISCLAIMER}\nBe The Puck is not a broker or an adviser and never places trades. You decide on every order.\n\n"
            "Drafts only: holdings and account value come from your rules file.\nSignal from https://bethepuck.com (free sample, standard signal)\n\n"
            + "\n".join(out) + "\n\n" + tail), asof


def _draft_source():
    with open(SCRIPT, encoding="utf-8") as f:
        s = f.read()
    a, b = s.index("def draft("), s.index("\ndef main(")
    return s[a:b].strip()


def build_it(A):
    sp, title, dek = _piece("articles/automate-build-it/")
    h = A.h(sp.count("/"))
    ex, asof = _example(A.s)
    al, ib, tr, et, wb, tt = (find(BROKERS, x) for x in ("Alpaca", "Interactive", "Tradier", "E*TRADE", "Webull", "tastytrade"))
    paper_rows = "".join(f'<tr><td><b>{e(nm(b))}</b></td><td>{e(SHORT[b["name"]][0])}</td><td>{e(b.get("paper_trading") or "")}</td></tr>' for b in (al, ib, wb, tr, et, tt))
    body = f"""
<section class="prose"><h2 class="h2">What the script does</h2>
<p>It's one Python file, under 250 lines, with nothing to install beyond Python itself. Each time you run it, it:</p>
<ol><li>reads your rules from a small settings file;</li>
<li>asks Be The Puck's API for the signal on each stock in your list (with your member key it can use your own weights; without one it uses the free sample, the standard signal, {FREE_PER_DAY} calls a day);</li>
<li>works out what you hold, from an Alpaca paper account if you connect one, or from the settings file if you don't;</li>
<li>applies your rules and prints the drafts, and saves them to a spreadsheet (<code>drafts-YYYY-MM-DD.csv</code>) you can enter at any broker by hand;</li>
<li>if a paper account is connected, offers each draft for a U.S.-listed stock or fund to it, one at a time, and sends it only if you type <code>yes</code>.</li></ol>
<p>It only ever talks to Alpaca's paper-trading address. It won't send an order to a live account, and it doesn't try: whether a rule is ever used with real money is a decision for you, your broker and ideally an advisor.</p>
<p class="auto-dl-btns"><a class="btn primary" href="{h(DOWNLOADS + 'bethepuck_drafts.py')}" download>Download the script</a> <a class="btn" href="{h(DOWNLOADS + 'bethepuck_rules.json')}" download>Download the sample rules</a></p></section>

<section class="prose"><h2 class="h2">Why paper first</h2>
<p>A paper account fills orders with pretend money at real prices. It shows how often your rules trade, what fills at the open look like next to the last close, and how it feels when a Sell lands on a stock you like, before any of it costs anything. The standard signal is built to change its mind rarely (the sticky rule exists for that), but a list of twenty names still flips somewhere most weeks; <a href="{h('articles/old-vs-new-signal/')}">Old signal vs new</a> counts the flips a year, and <a href="{h('articles/calls-graded/')}">this week's calls, graded</a> keeps the live record.</p></section>

<section><div class="sec-head"><h2 class="h2">Which practice account</h2><p>The script speaks Alpaca's paper API. The others are here for anyone adapting it; each broker's own documentation is the authority.</p></div>
<div class="tbl-wrap"><table class="tbl" data-nosort><thead><tr><th scope="col">Broker</th><th scope="col">Who can open</th><th scope="col">Practice account, as the broker describes it</th></tr></thead><tbody>{paper_rows}</tbody></table></div>
<p class="small muted">Alpaca's paper keys and live keys are separate; its own MCP server for Claude also defaults to paper. Canadian residents can't open a live Alpaca account; Alpaca doesn't state residency rules for paper-only accounts. With <code>--dry-run</code> the script needs no broker at all, which is how someone at Wealthsimple or a bank-owned broker can use it: it writes the drafts to the spreadsheet and nothing else. Sources: {links(src_of(al) + src_of(ib)[7:10])}</p></section>

<section class="prose"><h2 class="h2">Set it up</h2>
<ol><li>Install Python 3.8 or newer from python.org if you don't have it (<code>python3 --version</code> to check).</li>
<li>Download the script and the sample rules into one folder.</li>
<li>Open <code>bethepuck_rules.json</code> and put in your own list and numbers. Every number in the sample is a placeholder; buy sizes are in each stock's own currency, and holdings use the same tickers as your list.</li>
<li>Optional: get your Be The Puck key from <a href="{h('me/')}#apikey">your account page</a>. Optional: open an Alpaca paper account and make <b>paper</b> API keys.</li>
<li>Put the keys in environment variables, never in the files, then run it with <code>--dry-run</code> first.</li></ol></section>
{code('''# macOS or Linux (Terminal)
export BETHEPUCK_KEY="btp_…"            # optional: your Be The Puck member key
export ALPACA_KEY_ID="PK…"              # optional: Alpaca PAPER keys only
export ALPACA_SECRET_KEY="…"
python3 bethepuck_drafts.py --dry-run   # drafts only, contacts no broker
python3 bethepuck_drafts.py             # offers each draft to the paper account

# Windows (PowerShell)
$env:BETHEPUCK_KEY = "btp_…"
py bethepuck_drafts.py --dry-run''')}
<section class="prose"><p>With the sample rules file, a dry run at the {e(A.s.asof.strftime('%b %-d, %Y'))} close would print this (worked out with the script's own decision code; your stocks and numbers will differ):</p></section>
{code(ex, wrap=True)}

<section class="prose"><h2 class="h2">How it decides</h2>
<p>This is the whole decision, straight from the file. It reads the signal, what you hold and your rules, and nothing else:</p></section>
{code(_draft_source())}

<section class="split"><div class="card prose"><p class="eyebrow">Built-in brakes</p><ul>
<li>It refuses any broker address but Alpaca's paper one.</li>
<li>Each order needs <code>yes</code>, typed at a terminal. Run from a schedule, with no one at the keyboard, it sends nothing.</li>
<li>If an open order for the same stock and side is already waiting, it skips it.</li>
<li>Each order carries an ID made of the stock, the side and the day, so a second send the same day is turned away.</li>
<li>Toronto listings, coins and indexes are drafts only.</li></ul></div>
<div class="card prose"><p class="eyebrow">Keys and passwords</p><ul>
<li>Keys live in environment variables, not in the script or the rules file, so sharing either is safe.</li>
<li>Use paper keys. Live keys are a different set, and the script has no use for them.</li>
<li>Never give anyone, or any program, your broker username and password. FINRA's warning about auto-trading services says never to share them.</li>
<li>Revoke a Be The Puck key any time on your account page; a broker key in the broker's settings.</li></ul></div></section>

<section class="prose"><h2 class="h2">Run it every day</h2>
<p>A scheduled run has no one to type yes, so schedule the dry run: it writes the day's spreadsheet, and you approve anything from a terminal or at your broker when you're there. On macOS or Linux, <code>crontab -e</code> and a line like this runs it at 6:35 p.m. on weekdays by the computer's own clock. That's after Be The Puck's evening rebuild in Eastern time, so set the hour for your time zone; the spreadsheet records which close the signal came from, and a run before the rebuild gets the previous close.</p></section>
{code('35 18 * * 1-5  cd ~/bethepuck && /usr/bin/python3 bethepuck_drafts.py --dry-run >> drafts.log 2>&1')}
<section class="prose"><p>On Windows, Task Scheduler does the same with <code>py bethepuck_drafts.py --dry-run</code> as the action.</p>

<h2 class="h2">Change it with Claude</h2>
<p>Claude Code can read the script, explain any line and change a rule for you: <i>"Add a rule: no new buys when the score is under 65."</i> Read the change before you run it, and do a dry run after every change. Alpaca also has its own MCP server that connects Claude to an Alpaca account, paper by default. Orders sent through it go straight to the account, with no draft-and-approve step of its own, which is why the script asks you instead.</p>

<h2 class="h2">Going live</h2>
<p>The script won't. Using any rule with real money is a step to take with your broker's terms in front of you and, ideally, an advisor. <a href="{h('articles/before-you-automate/')}">Before you automate</a> has the trading rules, the tax rules frequent trading runs into, and a checklist.</p></section>
"""
    srcs = [("Be The Puck: for AI tools and the API", "https://bethepuck.com/developers/")] + src_of(al) + src_of(ib)[7:10] + [src_of(wb)[7], src_of(tr)[1], src_of(et)[2], src_of(tt)[2]]
    srcs.append(("FINRA: auto-trading services from unregistered entities", rule("US: auto-trading")["sources"][0]["url"]))
    A.shell(sp, BUCKET[0], title, dek, body, sources=srcs, related=A.related(sp.count("/"), [p for p, _, _ in PIECES if p != sp]),
            date=_date(), free=sp in FREE)


def copy_follow(A):
    sp, title, dek = _piece("articles/copy-mirror-follow/")
    h = A.h(sp.count("/"))
    P = {x["name"]: x for x in PLATFORMS}
    def card(kind, names, words):
        items = "".join(f'<li><b>{e(nm(P[n]))}</b>: {e(P[n]["what_it_does"])}</li>' for n in names)
        return f'<div class="card prose"><p class="eyebrow">{e(kind)}</p><p>{words}</p><ul class="small">{items}</ul></div>'
    rows = ""
    for p in PLATFORMS:
        if p["name"] == "Iris":
            continue
        places = p.get("places_trades")
        places = "Yes" if places is True else ("No" if places is False else str(places))
        rows += (f'<tr><td><b>{e(nm(p))}</b><span class="sym-sub">{e(ANGLE.get(p["name"], ""))}</span></td><td>{e(places)}</td>'
                 f'<td class="small">{e(p.get("price") or "")}</td><td class="small">{e(p.get("regulator_or_broker") or "")}</td></tr>')
    sur, pub, ap = P["Surmount"], P["Public.com (Individual API and MCP)"], P["Autopilot"]
    body = f"""
<section class="prose"><p>Be The Puck takes one angle: it publishes how {len(TIMED)} trading rules have done on every covered stock since 2005, combines them into one signal that's graded in public, and lets you or Claude read it. It doesn't copy anyone and never trades. Other platforms take very different angles, and some put a stranger's decisions straight into your account. Here's what each says it does, checked {CHECKED}, and what to look at before trusting any of them with money.</p></section>

<section><div class="sec-head"><h2 class="h2">Five angles</h2></div><div class="grid grid-3">
{card("Copy a person", ["eToro CopyTrader", "dub", "Autopilot"], "Your account mirrors someone else's portfolio in proportion: an investor on the platform, a creator, or a portfolio built from public filings. Their decisions become your trades.")}
{card("A strategy trades your account", ["Collective2"], "You subscribe to a published trading strategy and its trades are sent into your own broker account. The strategy's author decides; your broker carries it out.")}
{card("Your rules, run for you", ["Composer (Composer by SoFi)", "Surmount"], "You build or pick rules (now often with AI help), test them on history, and the platform executes them automatically.")}
{card("An AI trades through your broker", ["Public.com (Individual API and MCP)"], f'A broker opens an API and an MCP server so your own code or an AI assistant can place trades. The broker-native versions (Robinhood Agentic, IBKR Autonomous Trading) are in <a href="{h("articles/automate-with-claude/")}">the main guide</a>.')}
{card("Data and alerts only", ["Quiver Quantitative", "Unusual Whales", "Tickeron", "TradingView"], "They sell the information (congressional trades, options flow, chart patterns, alerts) and you act on it, or not, at your broker. TradingView can send orders, but only through a broker you connect.")}
</div></section>

<section><div class="sec-head"><h2 class="h2">Side by side</h2><p>As each platform describes itself. Iris, a social investing app from 2020, became Autopilot in 2023.</p></div>
<div class="tbl-wrap"><table class="tbl" data-nosort><thead><tr><th scope="col">Platform</th><th scope="col">Places trades in your account?</th><th scope="col">Price</th><th scope="col">Who holds the money, who is registered</th></tr></thead><tbody>{rows}</tbody></table></div>
<p class="small muted">Availability by country is in <a href="{h(DIR)}#copy">the directory</a>.</p></section>

<section class="prose"><h2 class="h2">What to check before you copy or follow anyone</h2>
<h3 class="h3">Who holds the money?</h3><p>For stocks, the platforms above that trade say they send orders through a registered broker-dealer: their own (eToro USA Securities, Composer Securities, dub Financial, Open to the Public Investing) or one you connect (Collective2 names Tradier and Interactive Brokers among others; Surmount's accounts are held at Alpaca Securities; Autopilot names Robinhood and Schwab). Crypto can run through firms that aren't broker-dealers (eToro USA LLC, Zero Hash), and Collective2 also works with futures and forex brokers. Look the firm that holds your account up on the official register (<a href="{h('guides/ways-to-invest/')}">Ways to invest</a> links each one), not the app's name.</p>
<h3 class="h3">Who is giving the advice?</h3><p>Copying a portfolio someone manages is advice in most places, and the firm doing it should be registered to give it. Read the small print. Surmount says Surmount AI Inc. is not a registered investment adviser, and that its advisory services come from Quantbase, LLC, an SEC-registered investment adviser, with accounts held at Alpaca Securities. Autopilot's portfolios come from Autopilot Advisers, LLC, an SEC-registered investment adviser. The adviser's own filing (the SEC's adviser search in the U.S.) says what it's allowed to do.</p>
<h3 class="h3">What the record leaves out</h3><p>A leaderboard shows the traders who are still on it; the ones who blew up have dropped off, so the visible records are the survivors. A strategy's past results are someone's past, often before fees, and rarely tested across a crash. Be The Puck's records include every play on every stock since 2005, the failures too (<a href="{h('articles/what-backtests-say/')}">what thousands of backtests say</a>), and even they are flattered by testing only stocks still listed today.</p>
<h3 class="h3">How late is the signal?</h3><p>Members of Congress report their trades up to 45 days after making them under the STOCK Act. A portfolio built from those filings buys weeks later, at a different price, without knowing why the trade was made.</p>
<h3 class="h3">What it costs, all in</h3><p>Subscription, plus the broker's fees, plus currency conversion on U.S. trades from a Canadian dollar account, set against what the strategy earned. Collective2's smallest AutoTrade plan is $49 a month, or $390 paid yearly: on a $10,000 account that's about 4% to 6% a year to make up before the strategy earns anything for you.</p>
<h3 class="h3">Can it trade without asking you?</h3><p>Several can, by design. Public's terms say trades submitted through its MCP server may be executed without your direct input on each one and are deemed authorized by you. Copy and strategy services trade on their schedule, not yours. If a platform can trade without asking, find out how to pause it before you need to.</p>
<h3 class="h3">Is it a scam wearing an AI badge?</h3><p>Canada's securities regulators keep alerts on AI-branded trading platforms, and FINRA warns that auto-trading services from unregistered firms may not fit your goals, can rack up losses before you notice, and may exaggerate their AI. Its plainest advice: never hand over your brokerage username and password.</p></section>

<section class="card prose"><p class="eyebrow">Where Be The Puck fits</p><p>Be The Puck publishes the rules' records and one signal, and lets Claude read them through its connector. It isn't affiliated with any platform above, takes no payment from them, and doesn't copy or trade. Any of them can sit alongside it; whether one belongs in your plan is a question for you and, ideally, an advisor.</p></section>
"""
    srcs = [x for p in PLATFORMS for x in src_of(p, 2)] + [EXTRA_SOURCES["stock_act"]]
    srcs += [("FINRA: auto-trading services from unregistered entities", rule("US: auto-trading")["sources"][0]["url"]),
             ("CSA investor alert: Quantum AI", rule("Canada: AI")["sources"][1]["url"])]
    A.shell(sp, BUCKET[0], title, dek, body, sources=srcs, related=A.related(sp.count("/"), [p for p, _, _ in PIECES if p != sp]),
            date=_date(), free=sp in FREE)


def before(A):
    sp, title, dek = _piece("articles/before-you-automate/")
    h = A.h(sp.count("/"))
    resp, pdt, cash, auto, oeo, csa = (rule(x) for x in ("You remain", "US: pattern", "US: cash", "US: auto-trading", "Canada: order", "Canada: AI"))
    pol_now, pol_new = ANTHROPIC[0], ANTHROPIC[1]
    body = f"""
<section class="prose"><p>Every guide on Be The Puck about automating keeps you approving each order, and this is why: whoever or whatever drafts an order, the account holder owns it. Here are the rules that apply to automated trading in the U.S. and Canada, the tax rules that frequent trading runs into without anyone noticing, the scams that use AI as bait, and the things that go wrong with rules that run on their own. It's free to read, like everything on Be The Puck about risk.</p></section>

<section class="prose"><h2 class="h2">You answer for every order</h2>
<p>The brokers we checked that let an AI connect say the same thing in different words. Interactive Brokers says you're responsible for reviewing AI-generated instructions and deciding whether to turn them into orders. Questrade requires you to approve every order in its app. Public says trades submitted through its MCP server are deemed authorized by you. Robinhood and IBKR's Autonomous Trading allow orders without per-order approval if you set them up that way, and the orders are still yours.</p>
<p>The same goes for a script you wrote, a platform you subscribed to and a portfolio you copied. "The program did it" isn't a defence with a broker, a tax authority or your own account balance.</p></section>

<section class="split"><div class="card prose"><p class="eyebrow">United States</p><h2 class="h3">Trading rules</h2>
<p><b>The pattern day trader rule is being replaced.</b> FINRA amended Rule 4210 to replace the day-trading margin rules, including the trade-count "pattern day trader" label and the $25,000 minimum, with intraday margin standards. The SEC approved it on April 14, 2026, effective June 4, 2026, but brokers may phase it in until Oct 20, 2027, so yours may still apply the old rule. Under the new one: no label by trade count, 25% maintenance margin on long margin-eligible stocks through the day (firms may ask for more), and under $2,000 of equity you can trade in a margin account without leverage. FINRA tells investors to ask their own firm when it switches.</p>
<p><b>Cash accounts</b> must pay in full by settlement, generally one business day after the trade for most securities, and firms can restrict an account after a violation.</p></div>
<div class="card prose"><p class="eyebrow">Canada</p><h2 class="h3">Trading rules</h2>
<p><b>Self-directed accounts give no advice.</b> At order-execution-only dealers, which include every Canadian self-directed broker in <a href="{h(DIR)}">the directory</a>, you make your own decisions; the dealer makes no recommendations and doesn't assess suitability. CIRO's research (May 26, 2026) found that concrete risk examples at the moment of decision cut high-risk activity, while tick-box acknowledgements didn't.</p>
<p><b>AI doesn't change the law.</b> The CSA's Staff Notice 11-348 (Dec 5, 2024) explains how existing securities law applies to AI systems and creates no new requirements. We found no Canadian equivalent of the U.S. day-trading rule; your dealer's own margin rules apply.</p></div></section>

<section class="prose"><h2 class="h2">The tax rules frequent trading runs into</h2>
<p>A rule that sells and buys back often can trip these without anyone noticing. A tax professional can say how they apply to you.</p>
<ul><li><b>U.S. wash sales.</b> A loss on a sale is disallowed if you buy substantially identical stock within 30 days before or after it; the disallowed loss is added to the cost of the new shares (IRS Publication 550).</li>
<li><b>Canada's superficial loss rule.</b> A loss is denied if you, your spouse or an affiliated person buys identical property within 30 days before or after the sale and still holds it 30 days after. Normally the loss is added to the cost of the new shares; when the buyer is your own RRSP or TFSA, it's lost for good.</li>
<li><b>Frequent trading in a TFSA.</b> The CRA can treat active trading in a TFSA as carrying on a business, which makes the income taxable. It looks at how often you trade, how long you hold, your intent, and the time you spend.</li></ul></section>

<section class="prose"><h2 class="h2">Scams that use AI as bait</h2>
<p>FINRA (July 29, 2025) warns about auto-trading services from unregistered firms: their trades may not fit your goals, losses can build before you notice, and AI claims may be exaggerated. Never hand over your brokerage username and password, check any firm on BrokerCheck, and keep watching the account even with a regulated service. The SEC has charged advisers for claiming AI they didn't use. Canada's securities regulators keep investor alerts on AI-branded trading platforms with names like "Quantum AI". A promise of high returns with little risk is the first warning sign on every regulator's list, whatever technology it claims.</p></section>

<section class="prose"><h2 class="h2">Anthropic's rules, if Claude is involved</h2>
<p>Anthropic's Usage Policy treats financial uses as high-risk, needing a human in the loop and disclosure that AI is involved. From Nov 12, 2026, it says a personalized recommendation to buy, sell, hold or allocate among specific investments must be reviewed by a qualified person before it reaches the individual or is used to carry out a decision; general education not applied to someone's own situation, and internal research and drafting, aren't covered. It doesn't say how the rules apply when the person using Claude and the person getting the recommendation are the same, and users are responsible for actions their agents take through connected systems.</p></section>

<section class="prose"><h2 class="h2">What goes wrong when rules run on their own</h2>
<ul><li><b>Bad data.</b> A price file with a glitch can turn a signal overnight. Be The Puck checks its numbers before publishing them and holds back the ones that fail, but no check catches everything: look at the chart before approving an order.</li>
<li><b>Stale data.</b> Every Be The Puck answer carries its close date. If it isn't the latest trading day, nothing should be drafted from it.</li>
<li><b>Gaps at the open.</b> A market order placed overnight fills at the next open, which can be far from the last close after news.</li>
<li><b>A rule that keeps firing.</b> A stock hovering at a line can flip back and forth; the sticky rule on the standard weights exists to damp that, and custom weights don't have it.</li>
<li><b>Running twice.</b> A schedule that fires twice, or a retry after a timeout, can send the same order again. Use order IDs, and check open orders first.</li>
<li><b>The broker's side.</b> APIs go down, keys expire, permissions change, and a margin or settlement rule can block an order your script assumed went through.</li></ul></section>

<section class="card rule-card auto-rule"><p class="eyebrow">Before any rule touches real money</p><ol>
<li>The rules are written down, specific enough that a stranger would draft the same orders.</li>
<li>They've run on paper long enough to buy and sell several times, through at least one bad week.</li>
<li>You know your broker's rules: margin, settlement, and whether the day-trading rule still applies there.</li>
<li>You know the tax rules for the account the rules trade in.</li>
<li>No one stock can grow past a share of the account you've set, and the rules say what happens when it does.</li>
<li>You know how to stop it at once: revoke the keys, turn off the broker's AI permission, pause the platform.</li>
<li>You've talked it through with an advisor, or decided knowingly not to (<a href="{h('guides/ways-to-invest/')}">ways to invest, and how to check an advisor</a>).</li></ol></section>
<p class="small">Next: <a href="{h('articles/automate-with-claude/')}">automating with Claude, the careful way</a> · <a href="{h(DIR)}">the broker directory</a> · <a href="{h('articles/when-to-sell/')}">when to sell: what an exit rule would have done</a> · <a href="{h('articles/one-stock-too-many/')}">one stock too many</a></p>
"""
    srcs = [(f"{_host(s['url'])}: {r['topic']}", s["url"]) for r in (resp, pdt, cash, auto, oeo, csa) for s in r["sources"]]
    srcs += [EXTRA_SOURCES["washsale"], EXTRA_SOURCES["superficial"], EXTRA_SOURCES["tfsa"],
             ("Anthropic: usage policy update (2025)", pol_now["sources"][0]["url"]), ("Anthropic: 2026 usage policy update", pol_new["sources"][0]["url"])]
    A.shell(sp, BUCKET[0], title, dek, body, sources=srcs, related=A.related(sp.count("/"), [p for p, _, _ in PIECES if p != sp]),
            date=_date(), free=sp in FREE)
