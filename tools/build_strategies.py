"""Build Quiplee's strategy site.

    pip install yfinance pandas numpy
    python tools/build_strategies.py                 # writes the site into the repo root
    python tools/build_strategies.py --preview DIR   # also writes a static preview copy

Pulls prices, runs every rule on every ticker, and regenerates the home page,
/strategies/, /thinkers/, /stocks/ (incl. every stock x rule page), /method/,
data/signals.json and sitemap.xml. The live news desk in /desk/ is left alone.
Edit tools/qstrat/content.py to add tickers, thinkers or rules.
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

# Hand-written pages that also get glossary links (re-linked on every build).
STATIC_LINKED = {"stories": "/assets/glossary.js", "desk": "../assets/glossary.js"}


def root_href(slug):
    g = BY_SLUG[slug]
    if g.get("lesson"):
        lesson, _, anchor = g["lesson"].partition("#")
        return f"/learn/{lesson}/#{anchor}"
    return f"/learn/glossary/#{slug}"


def glossary_json():
    # On the live desk, news headlines use some words in their everyday sense ("suppliers signal..."),
    # so site-mechanics terms are left out of the desk's in-browser linking.
    not_on_desk = {"signal", "in-out", "band", "next-move", "next-check", "closing-price"}
    terms = [{"slug": g["slug"], "term": g["term"], "tip": g["tip"], "href": root_href(g["slug"]), "aliases": g["aliases"]}
             for g in GLOSSARY if g["slug"] not in not_on_desk]
    return json.dumps({"terms": terms}, ensure_ascii=False, indent=1)


def link_static_pages(root):
    """Glossary-link the Stories pages and the live desk shell in place."""
    done = []
    for folder, script_src in STATIC_LINKED.items():
        d = os.path.join(root, folder)
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

GENERATED_DIRS = ["strategies", "thinkers", "stocks", "method", "learn"]


def write_pages(pages, out):
    for path, html in pages.items():
        d = os.path.join(out, path)
        os.makedirs(d, exist_ok=True)
        with open(os.path.join(d, "index.html"), "w", encoding="utf-8") as f:
            f.write(html)


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--preview", help="also write a self-contained preview copy to this folder")
    ap.add_argument("--no-site", action="store_true", help="skip writing into the repo root")
    args = ap.parse_args()

    t0 = time.time()
    prices, irx, now = engine.load_all()
    print(f"loaded {len(prices)} tickers in {time.time() - t0:.0f}s")
    results = engine.run(prices, irx, now)
    print(f"evaluated {len(results)} strategy x ticker pairs")

    if not args.no_site:
        site = Site(results, preview=False)
        pages = site.build()
        for d in GENERATED_DIRS:                      # clear stale pages (e.g. a removed ticker)
            shutil.rmtree(os.path.join(ROOT, d), ignore_errors=True)
        write_pages(pages, ROOT)
        os.makedirs(os.path.join(ROOT, "data"), exist_ok=True)
        with open(os.path.join(ROOT, "data", "signals.json"), "w") as f:
            f.write(site.signals_json())
        with open(os.path.join(ROOT, "sitemap.xml"), "w") as f:
            f.write(site.sitemap())
        with open(os.path.join(ROOT, "data", "glossary.json"), "w", encoding="utf-8") as f:
            f.write(glossary_json())
        print("glossary-linked:", ", ".join(link_static_pages(ROOT)))
        print(f"wrote {len(pages)} pages to {ROOT} (closes to {site.asof.date()})")

    if args.preview:
        out = os.path.abspath(args.preview)
        shutil.rmtree(out, ignore_errors=True)
        pv = Site(results, preview=True)
        pages = pv.build()
        write_pages(pages, out)
        for rel in ["assets/site.css", "assets/site.js", "assets/sortable.js", "assets/glossary.js", "styles.css",
                    "og-default.png", "desk/index.html", "data/glossary.json", "stories/index.html", "stories/the-hertz-lesson.html"] + \
                   [os.path.join("js", n) for n in os.listdir(os.path.join(ROOT, "js"))]:
            dst = os.path.join(out, rel)
            os.makedirs(os.path.dirname(dst), exist_ok=True)
            shutil.copy(os.path.join(ROOT, rel), dst)
        print(f"wrote preview ({len(pages)} pages) to {out}")


if __name__ == "__main__":
    main()
