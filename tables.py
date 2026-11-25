"""Write the post's appendix tables (A1-A4) as Markdown from the released data.

python3 tables.py [DATA_FOLDER] > tables.md
"""

from dataset import DETECTORS, auroc, called_ai, folder_from_argv, load, p_ai, sentence_mean, short
from recompute import Q2_2008_CUTS, described, one


def table(header, rows):
    def line(cells):
        return "|" + "|".join(f" {c} " if c != "" else " " for c in cells) + "|"

    return [line(header), "|" + "---|" * len(header)] + [line(row) for row in rows]


def by_kind(data):
    """Table A1: scans, words and GPTZero's calls for each kind of human text."""
    kinds = {}
    for r in data["human_scans"]:
        kinds.setdefault(r["kind"], []).append(r)
    order = sorted(kinds, key=lambda k: -max(map(p_ai, kinds[k])))

    def counts(rows):
        return [
            len(rows),
            f"{sum(r['words'] for r in rows):,}",
            sum(map(called_ai, rows)),
            sum(p_ai(r) >= 0.75 for r in rows),
        ]

    rows = [[k, *counts(kinds[k]), short(max(map(p_ai, kinds[k])))] for k in order]
    rows.append(["**All**", *(f"**{x}**" for x in counts(data["human_scans"])), ""])
    header = ["Kind of text", "Scans", "Words", "Called AI", "75% AI or more", "Highest AI probability"]
    return [
        "### Table A1. What we scanned, and what GPTZero said",
        "",
        "Human text written 1902-2020, unchanged. Many Lehman rows are overlapping cuts of the same few releases.",
        "",
        *table(header, rows),
    ]


def q2_2008_cuts(data):
    """The Lehman Q2 2008 cuts: the full 840-word text, the cuts in release order, then the 750+ word cuts."""
    cuts = described(data["human_scans"], Q2_2008_CUTS)
    full = max(cuts, key=lambda r: r["words"])
    by_place = sorted((r for r in cuts if r["words"] < 700), key=lambda r: full["text"].find(r["text"][:200]))
    long_cuts = sorted((r for r in cuts if r["words"] >= 700), key=lambda r: -r["words"])
    return full, by_place, long_cuts


def start_words(row):
    return " ".join(row["text"].split()[:4]) + " ..."


def by_start(data):
    """Table A2: the Lehman Q2 2008 release cut at different starting sentences."""
    _, by_place, long_cuts = q2_2008_cuts(data)
    rows = [[f'"{start_words(r)}"', r["words"], short(p_ai(r))] for r in by_place]
    rows += [[f'"{start_words(r)}" (750+ words, to the end)', r["words"], short(p_ai(r))] for r in long_cuts]
    return [
        "### Table A2. Same release, different starting sentence (Lehman Q2 2008, unchanged text)",
        "",
        *table(["Text starts at", "Words", "AI probability"], rows),
    ]


def edit_rows(data):
    """Return (label, row) for the published Q2 2007 text, its edited copies and the previous quarter's release."""
    h, edited = data["human_scans"], data["edited_copies"]
    published = one(h, "Lehman Q2 2007 earnings release (Wayback page text, unchanged), whole paragraphs")
    previous = one(h, "Lehman Q1 2007 earnings release (Wayback page text, unchanged), 'Non-interest")
    prefix = "Lehman Q2 2007 earnings release. "
    rows = [(f"As published ({published['words']} words)", published)]
    for group in ("Wording", "Figures"):
        rows += [(r["description"].removeprefix(prefix), r) for r in described(edited, prefix + group)]
    return rows + [
        ("The previous quarter's release, as published", previous),
        ("The previous quarter's release with this quarter's figures", one(edited, prefix + "The previous quarter's")),
    ]


def by_edit(data):
    """Table A3: edited copies of the Lehman Q2 2007 text, wording edits against figure edits."""
    rows = [[label, short(p_ai(r)), f"{sentence_mean(r):.2f}"] for label, r in edit_rows(data)]
    return [
        "### Table A3. Is it the words or the numbers? (Lehman Q2 2007; edited copies are tests only)",
        "",
        *table(["Text", "AI probability", "Mean sentence score"], rows),
    ]


def free_detectors(data):
    """Table A4: four free detectors on the same human texts, against GPTZero's AI calls."""
    od = data["open_detectors"]
    score = {r["id"]: p_ai(r) for r in data["human_scans"] + data["edited_copies"]}
    hit = [score[r["id"]] >= 0.5 for r in od]
    rows = [
        [m, f"{100 * sum(r[m] > 0.5 for r in od) / len(od):.0f}%", f"{auroc([r[m] for r in od], hit):.2f}"]
        for m in DETECTORS
    ]
    header = ["Detector", f"Flags as AI (of {len(od)} human texts)", "Finds the ones GPTZero calls AI (AUROC)"]
    return [
        "### Table A4. Free detectors from Hugging Face on the same human texts",
        "",
        *table(header, rows),
        "",
        f"GPTZero itself calls {sum(hit)} of these {len(od)} texts AI (cuts of the Lehman Q2 2007 and Q2 2008 "
        "releases, and one Bear Stearns dividend release). AUROC 0.5 is chance.",
    ]


def appendix(data):
    """Return Tables A1-A4 as the post's appendix prints them."""
    parts = [by_kind(data), by_start(data), by_edit(data), free_detectors(data)]
    return "\n\n".join("\n".join(p) for p in parts) + "\n"


if __name__ == "__main__":
    print(appendix(load(folder_from_argv())), end="")
