"""Drawing helpers shared by the figures: colours for the post's cold, warm and hot terms, text, dots and legends."""

import html
import math
import os
from functools import cache
from pathlib import Path

from PIL import ImageFont

FONT = "Source Serif 4"
FONT_FILES = [
    os.environ.get("FIGURE_FONT", ""),
    "~/Library/Fonts/SourceSerif4[opsz,wght].ttf",
    "~/.local/share/fonts/SourceSerif4[opsz,wght].ttf",
    "/usr/share/fonts/truetype/source-serif-4/SourceSerif4[opsz,wght].ttf",
]
INK, MUTED, BG, GRID = "#111827", "#6B7280", "#FFFFFF", "#E5E7EB"
COLD, WARM, HOT, HOT_LIGHT, RING = "#3F8F5A", "#EBC04D", "#C0392B", "#F2A097", "#111827"
WARM_TEXT = "#8A6100"
WARM_AT = 0.05


@cache
def font(size, weight):
    path = next((Path(p).expanduser() for p in FONT_FILES if p and Path(p).expanduser().is_file()), None)
    if path is None:
        raise SystemExit("Source Serif 4 (variable, from Google Fonts) not found; set FIGURE_FONT to its .ttf file")
    f = ImageFont.truetype(str(path), size)
    f.set_variation_by_axes([weight, min(size, 60)])
    return f


def text_width(s, size, weight=400):
    return font(size, weight).getlength(s)


def term(p, ai=None):
    """hot, warm or cold; `ai` is GPTZero's label when known, else an AI probability of 0.5 or more counts as AI."""
    hot = p >= 0.5 if ai is None else ai
    return "hot" if hot else ("warm" if p >= WARM_AT else "cold")


def fill(p, ai=None):
    t = term(p, ai)
    if t == "hot":
        return HOT if p >= 0.75 else HOT_LIGHT
    return WARM if t == "warm" else COLD


def ring(p, width=2.4, ai=None):
    """A dark ring at 75% AI or more, a red outline for the other hot marks."""
    if p >= 0.75:
        return f' stroke="{RING}" stroke-width="{width}"'
    outline = 2.5 if width == 2.5 else 1.5
    return f' stroke="{HOT}" stroke-width="{outline}"' if term(p, ai) == "hot" else ""


def score_colour(p):
    return {"hot": HOT, "warm": WARM_TEXT, "cold": MUTED}[term(p)]


def text(x, y, s, size, colour=INK, anchor="middle", weight=400):
    return (
        f'<text x="{x:.1f}" y="{y:.1f}" font-size="{size}" fill="{colour}" text-anchor="{anchor}" '
        f'font-weight="{weight}">{html.escape(s)}</text>'
    )


def dot(x, y, r, p, tip="", ai=None, width=None):
    title = f"<title>{html.escape(tip)}AI probability {p:.3g}</title>" if tip is not None else ""
    width = width or (2 if r < 8 else 2.4)
    return f'<circle cx="{x:.1f}" cy="{y:.1f}" r="{r}" fill="{fill(p, ai)}"{ring(p, width, ai)}>{title}</circle>'


def svg(width, height, body):
    return (
        f'<svg xmlns="http://www.w3.org/2000/svg" width="{width}" height="{height}" '
        f'viewBox="0 0 {width} {height}" font-family="&apos;{FONT}&apos;">'
        f'<rect x="0" y="0" width="{width}" height="{height}" fill="{BG}"/>\n' + "\n".join(body) + "\n</svg>\n"
    )


def legend(cx, y, counts=None, size=22):
    """The four marks, centred on cx; `counts` adds the number of scans in each."""
    items = [(0.0, "Cold"), (0.1, "Warm"), (0.6, "Hot, under 75%"), (0.9, "Hot, 75% or more")]
    if counts:
        items = [(p, f"{label} ({n})") for (p, label), n in zip(items, counts)]
    widths = [22 + text_width(label, size) for _, label in items]
    x, out = cx - (sum(widths) + 36 * (len(items) - 1)) / 2, []
    for (p, label), w in zip(items, widths):
        out += [dot(x + 8, y - 7, 8, p, None), text(x + 22, y, label, size, INK, "start")]
        x += w + 36
    return out


def sunflower(n, spacing):
    """Offsets of n points: point i at radius spacing*sqrt(i+0.5), a golden angle apart."""
    g = math.pi * (3 - math.sqrt(5))
    return [
        (spacing * math.sqrt(i + 0.5) * math.cos(i * g), spacing * math.sqrt(i + 0.5) * math.sin(i * g))
        for i in range(n)
    ]
