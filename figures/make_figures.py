"""Draw the post's figures as SVG from the released data.

    python3 -m figures.make_figures OUT_DIR [--data DATA_FOLDER] [--liang GPTZERO_JSON]

central.svg      one dot per human scan, in clusters by kind of text
start_bars.svg   the Lehman Q2 2008 release and where each cut of it starts and ends
edits_rows.svg   edited copies of the Lehman Q2 2007 text: wording edits against figure edits
essays.svg       Liang et al.'s TOEFL essays in 2023 and now, and the 105 other ESL essays (needs --liang)
"""

import argparse
import json
import math
from pathlib import Path

from dataset import DEFAULT, called_ai, load, p_ai, short
from figures.svg import (
    BG,
    COLD,
    GRID,
    HOT,
    INK,
    MUTED,
    dot,
    fill,
    legend,
    ring,
    score_colour,
    sunflower,
    svg,
    term,
    text,
    text_width,
)
from tables import edit_rows, q2_2008_cuts, start_words

LABELS = {
    "Lehman Brothers releases and filings (1998-2008)": ("Lehman Brothers", "releases 1998-2008"),
    "Other companies' financial releases: earnings, dividends, reports": ("Other companies'", "financial releases"),
    "Science, statistics and government writing": ("Science and", "government writing"),
    "Plain web genres: help pages, self-help, content farms, sample essays, Google Answers, a sports recap": (
        "Web pages",
        "and Q&A answers",
    ),
    "South Asian English: newspapers, government releases, court judgments, journals, books (1902-2019)": (
        "South Asian",
        "English, 1902-2019",
    ),
    "Corporate web pages": ("Corporate", "web pages"),
    "Student and ESL essays": ("Student and", "ESL essays"),
}
SHORT_EDITS = {
    'Wording: "compared with" changed to "compared to" twice': '"compared with" to "compared to"',
    "Wording: the previous quarter's reason clause": "last quarter's reason clause",
    "Wording: the previous quarter's word order in the company paragraph": "last quarter's word order",
    "Figures: the previous quarter's expense figures": "last quarter's expense figures",
    "Figures: the previous quarter's ratio figures": "last quarter's ratio figures",
    "Figures: the previous quarter's capital figures": "last quarter's capital figures",
    "Figures: all of the previous quarter's figures": "all of last quarter's figures",
    "Figures: small random changes to every figure, try 1": "small random changes, try 1",
    "Figures: small random changes to every figure, try 2": "small random changes, try 2",
    "Figures: small random changes to every figure, try 3": "small random changes, try 3",
}
NAME, GREY, COUNT = 24, 22, 22


def kinds(data):
    """Human scans grouped by kind, warmest kind first."""
    out = {}
    for r in data["human_scans"]:
        out.setdefault(r["kind"], []).append(r)
    return sorted(out.items(), key=lambda kv: -max(map(p_ai, kv[1])))


def central(data):
    """One sunflower of dots per kind of text, in two rows; the warmest dots sit at each centre."""
    width, radius, spacing, gap = 1000, 5.2, 7.4, 40
    groups = kinds(data)
    first = ("Lehman", "Other", "Student")
    rows = [
        sorted([g for g in groups if g[0].startswith(first)], key=lambda g: -len(g[1])),
        [g for g in groups if not g[0].startswith(first)],
    ]
    counts = [0, 0, 0, 0]
    for r in data["human_scans"]:
        counts[3 if p_ai(r) >= 0.75 else ("cold", "warm", "hot").index(term(p_ai(r), called_ai(r)))] += 1
    body, top = legend(width / 2, 44, counts), 84
    for row in rows:
        size = [spacing * math.sqrt(len(scans)) + radius for _, scans in row]
        slot = [max(2 * s, *(text_width(t, NAME, 600) for t in LABELS[k])) for (k, _), s in zip(row, size)]
        x, cy = (width - sum(slot) - gap * (len(row) - 1)) / 2, top + max(size)
        for (kind, scans), w in zip(row, slot):
            cx = x + w / 2
            for (dx, dy), r in zip(sunflower(len(scans), spacing), sorted(scans, key=lambda r: -p_ai(r))):
                tip = f"{r['description'][:90]} | {r['words']} words | "
                body.append(dot(cx + dx, cy + dy, radius, p_ai(r), tip, called_ai(r), width=2.4))
            name, grey = LABELS[kind]
            y = cy + max(size) + 34
            body += [
                text(cx, y, name, NAME, INK, weight=600),
                text(cx, y + 26, grey, GREY, MUTED),
                text(cx, y + 52, f"{len(scans)} scans", COUNT, MUTED),
            ]
            x += w + gap
        top = cy + max(size) + 34 + 52 + 40
    return svg(width, int(top), body)


def essays(data, liang_file):
    """Three sunflowers: Liang et al.'s essays in 2023 and now, and the 105 other ESL essays."""
    old = [x["completely_generated_prob"] for x in json.load(open(liang_file))]
    now = [p_ai(r) for r in sorted(data["liang91_rescore"], key=lambda r: r["essay_index"])]
    esl = [p_ai(r) for r in data["human_scans"] if "TOEFL" in r["description"]]
    panels = [
        ("Liang et al.'s 91 essays", "GPTZero in 2023", old),
        ("The same 91 essays", "GPTZero 5.0b, 2026", now),
        (f"{len(esl)} other ESL essays", "from 2002, GPTZero 5.0b", esl),
    ]
    width, spacing, radius = 1000, 7.4, 5.2
    body = legend(width / 2, 40)
    size = [spacing * math.sqrt(len(v)) + radius for _, _, v in panels]
    cy = 96 + max(size)
    for i, (title, sub, scores) in enumerate(panels):
        cx = width / 6 + i * width / 3
        for (dx, dy), p in zip(sunflower(len(scores), spacing), sorted(scores, reverse=True)):
            body.append(dot(cx + dx, cy + dy, radius, p))
        hot = sum(p >= 0.5 for p in scores)
        y = cy + max(size) + 36
        body += [
            text(cx, y, title, 24, INK, weight=600),
            text(cx, y + 26, sub, 22, MUTED),
            text(cx, y + 54, f"{hot} hot", 22, HOT if hot else COLD, weight=600),
        ]
    return svg(width, int(cy + max(size) + 110), body)


def steps(cx, y, labels, size=22):
    """A row of numbered steps joined by arrows."""
    r, gap, shaft = 15, 18, 34
    widths = [2 * r + 10 + text_width(label, size) for label in labels]
    x = cx - (sum(widths) + (len(labels) - 1) * (shaft + 2 * gap)) / 2
    out = []
    for i, (label, w) in enumerate(zip(labels, widths)):
        out += [
            f'<circle cx="{x + r:.1f}" cy="{y - 7}" r="{r}" fill="{INK}"/>',
            text(x + r, y + 1, str(i + 1), 22, BG, weight=700),
            text(x + 2 * r + 10, y, label, size, INK, "start", 600),
        ]
        x += w
        if i < len(labels) - 1:
            a, b = x + gap, x + gap + shaft
            out.append(
                f'<path d="M{a:.1f} {y - 7}H{b:.1f}M{b - 8:.1f} {y - 13}L{b:.1f} {y - 7}L{b - 8:.1f} {y - 1}" '
                f'fill="none" stroke="{MUTED}" stroke-width="2.5"/>'
            )
            x = b + gap
    return out


def start_bars(data):
    """The release as a strip of paragraphs; under it, one bar per cut, placed where it starts and ends."""
    full, by_place, long_cuts = q2_2008_cuts(data)
    words = full["text"].split()
    paragraphs, k = [], 0
    for para in (x for x in full["text"].split("\n") if x.strip()):
        paragraphs.append(k)
        k += len(para.split())

    def at(r):
        head = r["text"].split()[:8]
        return next(i for i in range(len(words)) if words[i : i + 8] == head)

    width, x0, x1, row0, row = 1000, 60, 860, 140, 30

    def x(w):
        return x0 + w / len(words) * (x1 - x0)

    body = steps(width / 2, 38, ["One unchanged release", "300-word cut at each sentence", "Scan each cut"])
    body += [
        text(x0, 86, "The release, word 1", 22, MUTED, "start"),
        text(x1, 86, f"word {len(words)}", 22, MUTED, "end"),
    ]
    for a, b in zip(paragraphs, paragraphs[1:] + [len(words)]):
        body.append(
            f'<rect x="{x(a) + 1:.1f}" y="98" width="{max(2, x(b) - x(a) - 2):.1f}" height="14" rx="7" fill="#CBD5E1"/>'
        )
    long_from_start = sorted(long_cuts, key=at)
    for i, r in enumerate(by_place + long_from_start):
        y = row0 + i * row + (16 if r["words"] > 700 else 0)
        p, start = p_ai(r), at(r)
        tip = f'Starts "{start_words(r)}" | {r["words"]} words | AI probability {p:.3g}'
        body.append(
            f'<rect x="{x(start):.1f}" y="{y}" width="{x(start + r["words"]) - x(start):.1f}" height="18" rx="9" '
            f'fill="{fill(p)}"{ring(p, 2.5)}><title>{tip}</title></rect>'
        )
        body.append(
            text(
                x(start + r["words"]) + 10,
                y + 16,
                short(p),
                22,
                score_colour(p),
                "start",
                600 if term(p) != "cold" else 400,
            )
        )
    bottom = row0 + (len(by_place) + len(long_cuts)) * row + 40
    body.append(
        text(
            x0,
            bottom,
            "Each bar is one scan of about 300 words; the bottom two are 750+ words, to the end.",
            22,
            MUTED,
            "start",
        )
    )
    body += legend(width / 2, bottom + 44)
    return svg(width, int(bottom + 66), body)


def edits_rows(data):
    """Two rows of dots on a 0-1 scale under the published text: edits to the wording, edits to the figures."""
    rows = edit_rows(data)
    wording = [(label, p_ai(r)) for label, r in rows if label.startswith("Wording")]
    figures = [(label, p_ai(r)) for label, r in rows if label.startswith("Figures")]
    published_label, published = rows[0]
    groups = [
        ("As published", f"{published['words']} words, unchanged", [(published_label, p_ai(published))]),
        ("Changed the words", f"{len(wording)} edits, figures kept", wording),
        ("Changed the figures", f"{len(figures)} edits, words kept", figures),
    ]
    width, x0, x1, top, row = 1000, 330, 950, 90, 96

    def x(p):
        return x0 + p * (x1 - x0)

    body = legend(width / 2, 40)
    bottom = top + row * len(groups)
    for v in (0, 0.5, 0.75, 1):
        bar = v == 0.75
        dash = ' stroke-dasharray="4 4"' if bar else ""
        body += [
            f'<path d="M{x(v):.1f} {top - 10}V{bottom}" stroke="{HOT if bar else GRID}" stroke-width="1"{dash}/>',
            text(x(v), bottom + 30, "$1,000 bar" if bar else f"{v:g}", 22, HOT if bar else MUTED),
        ]
    for i, (name, sub, rows) in enumerate(groups):
        cy = top + row * i + row / 2
        body += [text(x0 - 26, cy - 3, name, 24, INK, "end", 600), text(x0 - 26, cy + 24, sub, 22, MUTED, "end")]
        same = {}
        for label, p in rows:
            same.setdefault(round(p, 2), []).append((label, p))
        for stack in same.values():
            for n, (label, p) in enumerate(stack):
                tip = f"{SHORT_EDITS.get(label, label)} | "
                body.append(dot(x(p), cy + (n - (len(stack) - 1) / 2) * 25, 11, p, tip))
    body.append(
        text(
            width / 2,
            bottom + 64,
            "GPTZero's AI probability for the edited text (test copies, never submitted)",
            22,
            MUTED,
        )
    )
    return svg(width, int(bottom + 84), body)


def main():
    ap = argparse.ArgumentParser(description="Draw the post's figures as SVG.")
    ap.add_argument("out", type=Path)
    ap.add_argument("--data", type=Path, default=DEFAULT)
    ap.add_argument("--liang", type=Path, help="GPTZero.json from Liang et al.'s repository")
    a = ap.parse_args()
    data = load(a.data)
    a.out.mkdir(parents=True, exist_ok=True)
    figures = {"central": central(data), "start_bars": start_bars(data), "edits_rows": edits_rows(data)}
    if a.liang:
        figures["essays"] = essays(data, a.liang)
    for name, content in figures.items():
        (a.out / f"{name}.svg").write_text(content)
        print(a.out / f"{name}.svg")


if __name__ == "__main__":
    main()
