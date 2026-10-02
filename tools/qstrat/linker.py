"""Link technical terms in page HTML to the glossary or a lesson.

link_terms(html, href_for, self_targets) walks the HTML, skips anything that
shouldn't carry a link (existing links, buttons, headings, navigation, table
headers, labels, pills, code...), and wraps the FIRST use of each glossary
term on the page in:

    <a class="term" href="..." data-tip="short definition">word</a>

It is idempotent: previously inserted term links are stripped first, so it can
be re-run on hand-written pages (Stories, the desk shell) on every build.
"""
import html as _html
import re

from .glossary import GLOSSARY

SKIP_TAGS = {"a", "button", "select", "option", "textarea", "script", "style", "title", "head",
             "h1", "h2", "h3", "h4", "nav", "footer", "th", "code", "pre", "svg", "label", "summary", "dt"}
SKIP_CLASSES = {"pill", "tag", "crumbs", "eyebrow", "sym", "sym-sub", "tile-value", "level", "level-sub",
                "logo", "site-head", "band-mark", "consensus", "key", "no-gloss", "chart", "tt",
                "art-meta", "masthead", "topbar", "tabs", "tab"}
VOID = {"area", "base", "br", "col", "embed", "hr", "img", "input", "link", "meta", "source", "track", "wbr"}

TOKEN = re.compile(r"(<!--.*?-->|<![^>]*>|<[^>]+>)", re.S)
TAG = re.compile(r"<\s*(/)?\s*([a-zA-Z][a-zA-Z0-9-]*)([^>]*)>", re.S)
CLASS_ATTR = re.compile(r'class\s*=\s*"([^"]*)"|class\s*=\s*\'([^\']*)\'')
OLD_TERM = re.compile(r'<a class="term" href="[^"]*" data-tip="[^"]*">(.*?)</a>', re.S)


def _alias_pattern(alias):
    body = re.escape(alias).replace(r"\ ", r"\s+")
    return rf"(?<![\w\-&]){body}(?![\w\-])"


def _build():
    entries = []   # (alias, slug, case_sensitive)
    for g in GLOSSARY:
        for a in g["aliases"]:
            entries.append((a, g["slug"], a != a.lower()))
    entries.sort(key=lambda x: -len(x[0]))
    alias_slug = {}
    parts_ci, parts_cs = [], []
    for a, slug, cs in entries:
        alias_slug[(a.lower(), cs)] = slug
        (parts_cs if cs else parts_ci).append(_alias_pattern(a))
    rx_ci = re.compile("|".join(parts_ci), re.I) if parts_ci else None
    rx_cs = re.compile("|".join(parts_cs)) if parts_cs else None
    return rx_ci, rx_cs, alias_slug


RX_CI, RX_CS, ALIAS_SLUG = _build()
CS_ALIASES = {a: g["slug"] for g in GLOSSARY for a in g["aliases"] if a != a.lower()}
CI_ALIASES = {a.lower(): g["slug"] for g in GLOSSARY for a in g["aliases"] if a == a.lower()}
TIPS = {g["slug"]: g["tip"] for g in GLOSSARY}


def _slug_for(match_text, cs):
    norm = re.sub(r"\s+", " ", match_text)
    if cs:
        return CS_ALIASES.get(norm)
    return CI_ALIASES.get(norm.lower())


def _matches(text):
    """All non-overlapping alias matches in text, longest-first at each position."""
    found = []
    for rx, cs in ((RX_CS, True), (RX_CI, False)):
        if rx is None:
            continue
        for m in rx.finditer(text):
            slug = _slug_for(m.group(0), cs)
            if slug:
                found.append((m.start(), m.end(), slug))
    found.sort(key=lambda x: (x[0], -(x[1] - x[0])))
    out, last_end = [], -1
    for s, e, slug in found:
        if s >= last_end:
            out.append((s, e, slug))
            last_end = e
    return out


def link_terms(page_html, href_for, self_targets=(), used=None):
    """href_for(slug) -> URL. self_targets: slugs whose target is this page (not linked).
    used: optional set shared across calls (first-use-per-page)."""
    page_html = OLD_TERM.sub(lambda m: m.group(1), page_html)
    used = set(used or ()) | set(self_targets)
    out, stack = [], []        # stack of (tag, skip)
    skip_depth = 0
    for tok in TOKEN.split(page_html):
        if not tok:
            continue
        if tok.startswith("<"):
            out.append(tok)
            m = TAG.match(tok)
            if not m or tok.startswith("<!"):
                continue
            closing, name, attrs = m.group(1), m.group(2).lower(), m.group(3)
            if closing:
                # pop to the matching tag (tolerates sloppy markup)
                for i in range(len(stack) - 1, -1, -1):
                    if stack[i][0] == name:
                        for _ in range(len(stack) - i):
                            _, sk = stack.pop()
                            if sk:
                                skip_depth -= 1
                        break
                continue
            if name in VOID or attrs.rstrip().endswith("/"):
                continue
            cls = CLASS_ATTR.search(attrs)
            classes = set((cls.group(1) or cls.group(2) or "").split()) if cls else set()
            sk = name in SKIP_TAGS or bool(classes & SKIP_CLASSES)
            if name == "script" or name == "style":
                sk = True
            stack.append((name, sk))
            if sk:
                skip_depth += 1
            continue
        # text node
        if skip_depth > 0 or not tok.strip():
            out.append(tok)
            continue
        pieces, pos = [], 0
        for s, e, slug in _matches(tok):
            if slug in used:
                continue
            used.add(slug)
            word = tok[s:e]
            tip = _html.escape(TIPS[slug], quote=True)
            pieces.append(tok[pos:s])
            pieces.append(f'<a class="term" href="{href_for(slug)}" data-tip="{tip}">{word}</a>')
            pos = e
        pieces.append(tok[pos:])
        out.append("".join(pieces))
    return "".join(out)
