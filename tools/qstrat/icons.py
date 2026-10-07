"""Be The Puck's line icons and logo mark, drawn as inline SVG.

One family of icons: a 24px grid, 1.75px strokes, round caps and joins, currentColor,
so each one takes the colour of the text around it and stays sharp at any size.
icon(name) returns the markup; FAMILY_ICON maps each play family to its icon.
"""

P = {
    # the seven play families
    "trend": '<path d="M3 17l5.5-5.5 4 4L21 7"/><path d="M15 7h6v6"/>',
    "breakout": '<path d="M3 9h11M3 17h11"/><path d="M8 13l5-5 3 3 5-6"/><path d="M17 5h4v4"/>',
    "momentum": '<path d="M5 6l6 6-6 6"/><path d="M12 6l6 6-6 6"/>',
    "reversion": '<path d="M3 12h18" stroke-dasharray="2 3"/><path d="M3 12c2.5-6 5-6 7.5 0s5 6 7.5 0c1-2.4 2-3.6 3-3.6"/>',
    "volume": '<path d="M5 20v-6M10 20V9M15 20v-8M20 20V5"/><path d="M3 20h19"/>',
    "pattern": '<path d="M7 3v4M7 15v6M17 5v3M17 17v3"/><rect x="5" y="7" width="4" height="8" rx="1"/><rect x="15" y="8" width="4" height="9" rx="1"/>',
    "calendar": '<rect x="3.5" y="5" width="17" height="15.5" rx="2.5"/><path d="M3.5 10h17M8 3v4M16 3v4"/><path d="M8 14h2M14 14h2M8 17h2"/>',
    # tools and sections
    "theory": '<rect x="3" y="4" width="18" height="13" rx="2"/><path d="M7 8l3 3M10 8l-3 3"/><circle cx="16" cy="12" r="2"/><path d="M10.5 13.5c1.5 1 3 .5 4-0.5"/><path d="M9 21h6M12 17v4"/>',
    "screener": '<path d="M4 5h16l-6 7.5V19l-4 2v-8.5L4 5z"/>',
    "weather": '<path d="M7 18h10a4 4 0 0 0 .6-7.96A6 6 0 0 0 6.2 11.1 3.5 3.5 0 0 0 7 18z"/><path d="M9 21l1-2M13 21l1-2"/>',
    "gauge": '<path d="M4.2 17a9 9 0 1 1 15.6 0"/><path d="M12 13l4-5"/><circle cx="12" cy="13" r="1.4"/>',
    "alert": '<path d="M6 16V11a6 6 0 1 1 12 0v5l1.5 2h-15L6 16z"/><path d="M10 20.5a2.2 2.2 0 0 0 4 0"/>',
    "puck": '<ellipse cx="12" cy="9" rx="8" ry="3.5"/><path d="M4 9v5c0 1.9 3.6 3.5 8 3.5s8-1.6 8-3.5V9"/>',
    "guide": '<path d="M4 5.5A2.5 2.5 0 0 1 6.5 3H20v15H6.5A2.5 2.5 0 0 0 4 20.5v-15z"/><path d="M4 20.5A2.5 2.5 0 0 1 6.5 18H20v3H6.5"/><path d="M9 8h7M9 11.5h5"/>',
    "learn": '<path d="M2.5 9L12 4.5 21.5 9 12 13.5 2.5 9z"/><path d="M6.5 11v4.5c1.5 1.5 3.5 2.2 5.5 2.2s4-.7 5.5-2.2V11"/><path d="M21.5 9v5"/>',
    "desk": '<rect x="3" y="4" width="15" height="16" rx="2"/><path d="M18 8h2.5a.5.5 0 0 1 .5.5V18a2 2 0 0 1-2 2H6"/><path d="M6.5 8h8M6.5 11.5h8M6.5 15h5"/>',
    "list": '<path d="M9 6h11M9 12h11M9 18h11"/><circle cx="4.5" cy="6" r="1"/><circle cx="4.5" cy="12" r="1"/><circle cx="4.5" cy="18" r="1"/>',
    "watch": '<path d="M12 3.5l2.6 5.3 5.9.9-4.3 4.1 1 5.8L12 16.9l-5.2 2.7 1-5.8-4.3-4.1 5.9-.9L12 3.5z"/>',
    "crash": '<path d="M3 5l5 5 3-2 4 6 3-2 3 4"/><path d="M17 20h4v-4"/>',
    "member": '<rect x="3" y="10" width="18" height="11" rx="2.5"/><path d="M7.5 10V7a4.5 4.5 0 0 1 9 0v3"/><circle cx="12" cy="15.5" r="1.4"/>',
    "buy": '<path d="M12 19V5M6 11l6-6 6 6"/>',
    "sell": '<path d="M12 5v14M6 13l6 6 6-6"/>',
    "where": '<circle cx="12" cy="12" r="8.5"/><path d="M3.5 12h17M12 3.5c2.4 2.4 3.5 5.3 3.5 8.5s-1.1 6.1-3.5 8.5c-2.4-2.4-3.5-5.3-3.5-8.5S9.6 5.9 12 3.5z"/>',
    "agree": '<path d="M4 12.5l4.5 4.5L20 6"/>',
    "arrow": '<path d="M5 12h14M13 6l6 6-6 6"/>',
}

FAMILY_ICON = {"trend": "trend", "breakout": "breakout", "momentum": "momentum", "reversion": "reversion",
               "volume": "volume", "pattern": "pattern", "calendar": "calendar"}


def icon(name, cls="ic", label=None, size=None):
    """Inline SVG for an icon. Decorative unless a label is given."""
    a11y = f' role="img" aria-label="{label}"' if label else ' aria-hidden="true" focusable="false"'
    wh = f' width="{size}" height="{size}"' if size else ""
    return (f'<svg class="{cls}" viewBox="0 0 24 24"{wh} fill="none" stroke="currentColor" stroke-width="1.75" '
            f'stroke-linecap="round" stroke-linejoin="round"{a11y}>{P[name]}</svg>')


# The logo mark: a chart line running into the puck (Chase where it's going).
MARK_BODY = ('<defs><linearGradient id="GID" x1="0" y1="1" x2="1" y2="0"><stop offset="0" stop-color="#7c6cf5" stop-opacity="0"/>'
             '<stop offset=".5" stop-color="#7c6cf5"/><stop offset="1" stop-color="#a99cff"/></linearGradient></defs>'
             '<path d="M5 53 L16.5 44.5 L23 47.5 L33.5 35" fill="none" stroke="url(#GID)" stroke-width="5" stroke-linecap="round" stroke-linejoin="round"/>'
             '<ellipse cx="45" cy="28.5" rx="14" ry="6" fill="#4b5873"/><rect x="31" y="22.5" width="28" height="6" fill="#4b5873"/>'
             '<ellipse cx="45" cy="22.5" rx="14" ry="6" fill="#e7edf7"/>')
TICK = '<path d="M52 6.5 L58 16.5 L46 16.5 Z" fill="#1fd093"/>'


def mark(size=28, cls="logo-mark", gid="bp-trail"):
    """The mark beside the wordmark (the wordmark carries the green tick). gid keeps gradient ids unique per page."""
    return f'<svg class="{cls}" viewBox="0 0 64 64" width="{size}" height="{size}" aria-hidden="true" focusable="false">{MARK_BODY.replace("GID", gid)}</svg>'


def app_icon_svg(tick=True):
    """The square app icon / favicon: the mark on night navy, with the green tick."""
    return ('<svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 64 64"><rect width="64" height="64" rx="15" fill="#0b0f17"/>'
            + MARK_BODY.replace("GID", "t") + (TICK if tick else "") + '</svg>')
