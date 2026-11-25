"""Lehman Brothers' quarterly earnings releases (lehman.com/press/qe/, 1998-2008) on the Wayback Machine, and the
unchanged cuts of them that were scanned.

    python3 -m collect.lehman OUT_DIR

Writes OUT_DIR/pages.jsonl (one release per quarter, the latest snapshot) and OUT_DIR/cuts.jsonl:
  metrics       the metrics section, from "Investment Management reported" (or "Non-interest expenses") to the
                book value sentence, with whole sentences added before it to reach 300 words
  expenses      from "Non-interest expenses" to the release's last sentence
  starts        for Q2 2008: from each sentence start between "Capital Markets reported" and the expense paragraph,
                whole sentences to 300 words; and two 750+ word cuts to the end of the release text
  Q2 2007       ten more cuts of the Q2 2007 release (Q2_2007_CUTS)
"""

import json
import re
import sys
from pathlib import Path

from collect import wayback
from collect.fetch import fetch
from collect.text import cut, extend_back, page_paragraphs, sentence_starts

PAGE = re.compile(r"/(\d)_(\d\d)qe\.htm$")
SECTION_END = re.compile(r"Book value per (common )?share (was|of) \$\d+\.\d\d\.")
RELEASE_END = ("\n\nConference Call", "\n\nFinancial Statements Attached", "\n\nFinancial Information Attached")
SIPC = "Lehman Brothers Inc. is a member of SIPC."
Q2_2008_FIRST, Q2_2008_LAST = "Capital Markets reported net revenues", "Non-interest expenses"
Q2_2008_LONG = ("Chairman and Chief Executive Officer", "With these actions")
# Cuts of the Q2 2007 release: (first words, end), where the end is a word count (whole sentences up to it) or the
# number of whole sentences kept after the book value sentence.
Q2_2007_CUTS = [
    ("This increase was driven", 300),
    ("Assets under management grew", 300),
    ("Non-interest expenses", 300),
    ("Net revenues (total revenues", "book value"),
    ("Investment Banking reported", "book value"),
    ("This increase was driven", "book value"),
    ("This performance was driven by record net revenues", "book value"),
    ("This performance was driven by record net revenues", "book value + 1"),
    ("This performance was driven by record net revenues", "book value + 2"),
    ("This performance was driven by record net revenues", "book value + 4"),
]
# The first metrics cuts, for these quarters, ended at the first full stop after "Book value per common share was $",
# which is the decimal point of the figure: "... was $35."
CUT_AT_DECIMAL_POINT = ("Q1 2007", "Q2 2007", "Q3 2007", "Q4 2007", "Q1 2008")


def quarter(url):
    q, y = PAGE.search(url).groups()
    return f"Q{q} {1900 + int(y) if int(y) > 50 else 2000 + int(y)}"


def release_pages():
    """The latest snapshot of each quarter's release page: [(quarter, Wayback address)] in date order."""
    rows = wayback.listing("lehman.com/press/qe/", matchType="prefix", fl="original,timestamp", filter="statuscode:200")
    latest = {}
    for r in rows:
        if PAGE.search(r["original"]):
            q = quarter(r["original"])
            if q not in latest or r["timestamp"] > latest[q][0]:
                latest[q] = (r["timestamp"], r["original"])
    order = sorted(latest, key=lambda q: (q[3:], q[:2]))
    return [(q, wayback.shown(*latest[q])) for q in order]


def page_text(source):
    """The release page's text, paragraphs separated by blank lines, from its Wayback address."""
    return "\n\n".join(page_paragraphs(fetch(wayback.raw_from_shown(source))))


def section(text, start):
    """(start, end) offsets from the first `start` to the end of the book value sentence."""
    i = text.find(start)
    m = SECTION_END.search(text, i)
    return i, m.end()


def metrics(text):
    """The metrics section, extended back with whole sentences to 300 words; None if the release has none."""
    i = text.find("Investment Management reported")
    i = i if i >= 0 else text.find("Non-interest expenses")
    if i < 0 or not SECTION_END.search(text, i):
        return None
    start, end = section(text, text[i : i + 30])
    return extend_back(text, start, end)


def release_end(text, start):
    """Offset of the end of the release text: before the conference call notice, the attached statements or the
    SIPC line, whichever comes first; None if there is none of them."""
    ends = [text.find(e, start) for e in RELEASE_END] + [text.find(" " + SIPC, start)]
    return min((e for e in ends if e > 0), default=None)


def expenses(text):
    """From "Non-interest expenses" to the release's last sentence; None if the release has no such paragraph."""
    i = text.find("Non-interest expenses")
    end = release_end(text, i) if i >= 0 else None
    return text[i:end].rstrip() if end else None


def q2_2008_cuts(text):
    """[(name, cut)] for the Q2 2008 release: one 300-word cut per starting sentence, then the two long cuts."""
    first, last = text.find(Q2_2008_FIRST), text.find(Q2_2008_LAST)
    out = [(f"from '{text[s : s + 30]}'", cut(text, s)) for s in sentence_starts(text) if first <= s < last]
    out = (
        [(f"from '{text[first : first + 30]}'", cut(text, first))] + out if first not in sentence_starts(text) else out
    )
    end = text.find(SIPC) + len(SIPC)
    for start in Q2_2008_LONG:
        i = text.find(start)
        out.append((f"from '{start}' to the end", text[i:end]))
    return out


def to_book_value(text, first, end):
    """From `first` to the book value sentence, plus the number of whole sentences that `end` names after it."""
    start, stop = section(text, first)
    extra = int(end.partition("+")[2] or 0)
    if extra:
        later = [s for s in sentence_starts(text) if s > stop]
        stop = later[extra] if extra < len(later) else release_end(text, stop)
    return text[start:stop].rstrip()


def q2_2007_cuts(text):
    out = []
    for first, end in Q2_2007_CUTS:
        if isinstance(end, int):
            out.append((f"from '{first}', whole sentences to {end} words", cut(text, text.find(first), end)))
        else:
            out.append((f"from '{first}' to {end}", to_book_value(text, first, end)))
    return out


def metrics_to_decimal_point(text):
    i = text.find("Investment Management reported")
    j = text.find(".", text.find("Book value per common share was $", i)) + 1
    return text[i:j]


def cuts(quarter_, text):
    """[(name, text)] of every cut taken from one quarter's release."""
    out = [
        ("metrics section", metrics(text)),
        ("'Non-interest expenses' to the release's last sentence", expenses(text)),
    ]
    if quarter_ in CUT_AT_DECIMAL_POINT:
        out.append(("metrics section, ended at the decimal point of book value", metrics_to_decimal_point(text)))
    if quarter_ == "Q2 2007":
        out += q2_2007_cuts(text)
    if quarter_ == "Q2 2008":
        out += q2_2008_cuts(text)
    return [(name, c) for name, c in out if c]


def main():
    out = Path(sys.argv[1])
    out.mkdir(parents=True, exist_ok=True)
    pages, found = [], []
    for q, source in release_pages():
        text = page_text(source)
        pages.append({"quarter": q, "source": source, "text": text, "words": len(text.split())})
        for name, c in cuts(q, text):
            found.append({"quarter": q, "cut": name, "source": source, "text": c, "words": len(c.split())})
        print(q, len(text.split()), "words", flush=True)
    for name, rows in (("pages", pages), ("cuts", found)):
        (out / f"{name}.jsonl").write_text("".join(json.dumps(r) + "\n" for r in rows))
    print(len(pages), "pages,", len(found), "cuts")


if __name__ == "__main__":
    main()
