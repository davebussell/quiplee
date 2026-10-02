"""Build Quiplee's plays site from the cached prices.

    pip install -r requirements.txt
    python tools/fetch_prices.py                 # refresh data/prices/ (network; nightly in CI)
    python tools/build_strategies.py             # build the whole site into _site/ (no network)
    python tools/build_strategies.py --out DIR --preview   # local preview with explicit index.html links

Netlify runs the second command on every push (see netlify.toml) and publishes
_site/. The build copies the hand-written parts of the site (live desk,
stories, assets, js) unchanged apart from glossary links, then generates the
home page, /strategies/ (plays), /thinkers/ (analysts), /stocks/ (every stock x
play page), /learn/, /method/, data/*.json and sitemap.xml.
Edit tools/qstrat/plays.py for plays, analysts.json for analysts, content.py
for tickers.
"""
import argparse
import json
import os
import shutil
import sys
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
GENERATED = {"index.html", "sitemap.xml", "strategies", "thinkers", "stocks", "method", "learn"}
GENERATED_DATA = {"signals.json", "glossary.json", "practice.json"}
NOT_PUBLISHED = {".git", ".github", ".ship", ".netlify", "netlify", "tools", "node_modules", "_site", "__pycache__",
                 "netlify.toml", "requirements.txt", "README.md", "BRAND.md", ".gitignore", "SHIP-QUIPLEE.cmd"}


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
    results = engine.run(prices, irx, now, workers=args.workers)
    print(f"evaluated {len(results)} play x ticker pairs in {time.time() - t0:.0f}s")

    t1 = time.time()
    site = Site(results, preview=args.preview, prices=prices, irx=irx)
    pages = site.build()
    print(f"rendered {len(pages)} pages in {time.time() - t1:.0f}s")

    shutil.rmtree(out, ignore_errors=True)
    os.makedirs(out)
    copy_static(out)
    write_pages(pages, out)
    os.makedirs(os.path.join(out, "data"), exist_ok=True)
    with open(os.path.join(out, "data", "signals.json"), "w") as f:
        f.write(site.signals_json())
    with open(os.path.join(out, "data", "glossary.json"), "w", encoding="utf-8") as f:
        f.write(glossary_json())
    t2 = time.time()
    items = build_practice(prices, irx, now)
    with open(os.path.join(out, "data", "practice.json"), "w", encoding="utf-8") as f:
        f.write(practice_json(items))
    print(f"built {len(items)} practice charts in {time.time() - t2:.0f}s")
    with open(os.path.join(out, "sitemap.xml"), "w") as f:
        f.write(site.sitemap())
    print("glossary-linked:", ", ".join(link_static_pages(out)))
    print(f"wrote the site to {out} in {time.time() - t0:.0f}s")


if __name__ == "__main__":
    main()
