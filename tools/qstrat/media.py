"""Be The Puck's photography: one dark, cool "night ice" set, used sparingly.

Every image lives in assets/img/<name>-<640|1200|1920>.webp (16:9). Sources, all through
Canva: the four stock photos come from Canva's licensed library; the rest were generated
with Canva's image generator for this site. The working file is the "Be The Puck Photo
Board" design in Dave's Canva account (pages 1-4 stock, 5-15 generated).
pic() writes a responsive <img>; WEATHER_IMG picks the lake sky for tonight's market weather.
"""
import html

e = html.escape
WIDTHS = (640, 1200, 1920)

ALT = {
    "hero-trail": "A hockey puck sliding across dark ice, its violet trail rising like a stock chart",
    "theory-board": "A hockey coach's whiteboard with set plays drawn in marker",
    "wx-calm": "A frozen lake under a clear dusk sky",
    "wx-mostly": "A frozen lake at dusk with a few scattered clouds",
    "wx-unsettled": "Clouds building over a frozen lake at dusk",
    "wx-stormy": "A storm rolling over a frozen lake",
    "cracked-ice": "Cracks spreading through dark lake ice",
    "puck-row": "A row of hockey pucks on dark ice, one lit violet and a little ahead of the line",
    "bubble": "A single soap bubble against a dark background",
    "phone-alert": "A phone glowing on a bench beside a dark rink",
    "puck-ice": "A hockey puck on scratched ice",
    "arena": "An empty hockey arena at night, spotlights on the ice",
    "toronto": "The Toronto skyline at night, reflected in Lake Ontario",
    "skates": "A hockey player's skates and stick on the ice",
    "rental-lot": "Rows of rental cars in a snowy lot at night",
}
WEATHER_IMG = {"Calm": "wx-calm", "Mostly calm": "wx-mostly", "Unsettled": "wx-unsettled", "Stormy": "wx-stormy"}


def src(h, name, w=1200):
    return h(f"assets/img/{name}-{w}.webp")


def pic(h, name, sizes="100vw", cls="", alt=None, eager=False, decorative=False):
    """A responsive image. decorative=True for images that sit behind text and add nothing to read."""
    srcset = ", ".join(f"{h(f'assets/img/{name}-{w}.webp')} {w}w" for w in WIDTHS)
    a = "" if decorative else e(alt if alt is not None else ALT.get(name, ""))
    load = 'fetchpriority="high" loading="eager"' if eager else 'loading="lazy"'
    hide = ' aria-hidden="true"' if decorative else ""
    return (f'<img class="{cls}" src="{src(h, name)}" srcset="{srcset}" sizes="{e(sizes)}" width="1920" height="1080" '
            f'alt="{a}" {load} decoding="async"{hide}>')


def page_art(h, name, pos="50% 50%"):
    """A section page's header picture: full bleed behind the page title, faded into the page."""
    return (f'<div class="page-art" aria-hidden="true" style="--art-pos:{pos}">'
            f'{pic(h, name, sizes="100vw", cls="page-art-img", eager=True, decorative=True)}</div>')


# which picture heads which section page
PAGE_ART = {"theory/": "theory-board", "guides/": "puck-row", "alerts/": "phone-alert", "me/": "phone-alert",
            "members/": "puck-ice", "stocks/": "toronto", "strategies/": "skates", "learn/": "arena",
            "articles/": "cracked-ice"}
# article covers, by article slug
ARTICLE_ART = {"is-this-a-bubble": "bubble", "bubbles-and-crashes": "cracked-ice", "cash-or-invested": "wx-stormy",
               "debt-and-crashes": "puck-ice", "green-across-the-board": "hero-trail", "the-hertz-lesson": "rental-lot"}
