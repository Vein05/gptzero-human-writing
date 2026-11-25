"""Figure-dense results prose outside finance, published 2019 or earlier: two BLS Employment Situation releases, two
NOAA national climate reports, two USDA WASDE crop reports (PDF) and one ESPN NBA game recap (AP).

    python3 -m collect.results_prose OUT.jsonl

Each page is read from its Wayback snapshot. The text starts at the paragraph holding the page's anchor and stops before
a table-like paragraph or a short trailer line; it is then cut to whole paragraphs (WASDE: whole commodity sections) of
at most about 900 words, keeping at least 300. The WASDE PDFs need pdftotext (poppler).
"""

import json
import re
import subprocess
import sys
import tempfile
from html import unescape

from collect import wayback
from collect.edgar import prose_runs
from collect.fetch import fetch

# (family, Wayback snapshot, anchor where the published prose starts, label)
PAGES = [
    (
        "bls",
        "20200512020954/bls.gov/news.release/archives/empsit_12062019.htm",
        "Total nonfarm payroll",
        "November 2019",
    ),
    (
        "bls",
        "20190716203818/bls.gov/news.release/archives/empsit_03082019.htm",
        "Total nonfarm payroll",
        "February 2019",
    ),
    ("noaa", "20200103094909/ncdc.noaa.gov/sotc/national/201905", "contiguous U.S.", "May 2019"),
    ("noaa", "20191001130259/ncdc.noaa.gov/sotc/national/201907", "contiguous U.S.", "July 2019"),
    ("wasde", "20190626000650/usda.gov/oce/commodity/wasde/wasde0619.pdf", "WHEAT:", "June 2019"),
    ("wasde", "20190917084531/usda.gov/oce/commodity/wasde/wasde0919.pdf", "WHEAT:", "September 2019"),
    ("espn", "20200210070515/espn.com/nba/recap?gameId=401161400", " -- ", "AP game recap"),
]
LIMIT = 900


def cap(text, limit=LIMIT):
    """Whole paragraphs from the start, stopping before the one that passes `limit` words (at least 300 kept)."""
    out = []
    for p in text.split("\n\n"):
        kept = len(" ".join(out).split())
        if out and kept + len(p.split()) > limit and kept >= 300:
            break
        out.append(p)
    return "\n\n".join(out)


def sections(text, limit=LIMIT):
    """Whole commodity sections ("COARSE GRAINS: ...") from the start, as `cap` does for paragraphs."""
    out = []
    for s in re.split(r"(?=\b[A-Z][A-Z ,/-]{3,}: )", text):
        kept = len(" ".join(out).split())
        if out and kept + len(s.split()) > limit and kept >= 300:
            break
        out.append(s.strip())
    return "\n\n".join(x for x in out if x)


def pdf_text(raw):
    with tempfile.NamedTemporaryFile(suffix=".pdf") as f:
        f.write(raw)
        f.flush()
        return subprocess.run(["pdftotext", f.name, "-"], capture_output=True, text=True, check=True).stdout


def ap_story(html):
    """The AP story's <p> paragraphs, from the dateline ("TORONTO -- ") to the first one- or two-word heading."""
    paras = [unescape(re.sub(r"<[^>]+>", "", x)).strip() for x in re.findall(r"(?s)<p>(.*?)</p>", html)]
    k = next(i for i, x in enumerate(paras) if re.match(r"[A-Z][A-Z .,']+ -- ", x))
    j = next((i for i in range(k, len(paras)) if len(paras[i].split()) <= 2), len(paras))
    return cap("\n\n".join(paras[k:j]))


def page_paragraphs(family, html, anchor):
    """BLS: the <pre> block holding the anchor, hard-wrapped lines joined. NOAA: block elements end paragraphs."""
    if family == "bls":
        pre = re.search(r"(?is)<pre[^>]*>(.*?)</pre>", html[html.find(anchor) - 3000 :])
        text = unescape(re.sub(r"<[^>]+>", "", pre.group(1)))
        paras = [re.sub(r"\s*\n\s*", " ", x).strip() for x in re.split(r"\n\s*\n", text)]
    else:
        h = re.sub(r"\s+", " ", re.sub(r"(?is)<(script|style).*?</\1>", " ", html))
        h = re.sub(r"(?i)</?(p|div|br|tr|li|h\d|table|section|article|header|footer|ul|ol)\b[^>]*>", "\n\n", h)
        paras = [unescape(re.sub(r"<[^>]+>", "", x)).strip() for x in h.split("\n\n")]
    return [x for x in paras if x]


def results_text(family, raw, anchor):
    if family == "wasde":
        run = next(r for r in prose_runs(pdf_text(raw), False) if anchor in r)
        return sections(run[run.find(anchor) :])
    html = raw.decode("utf-8", "replace")
    if family == "espn":
        return ap_story(html)
    paras = page_paragraphs(family, html, anchor)
    k = next(i for i, x in enumerate(paras) if anchor in x)
    kept = []
    for x in paras[k:]:
        if re.search(r" {3,}|\|", x) or (len(x.split()) < 4 and kept and family != "bls"):
            break
        kept.append(x)
    return cap("\n\n".join(kept))


def main():
    with open(sys.argv[1], "w") as f:
        for family, snapshot, anchor, label in PAGES:
            source = "https://web.archive.org/web/" + snapshot
            text = results_text(family, fetch(wayback.raw_from_shown(source)), anchor)
            f.write(json.dumps({"family": family, "label": label, "source": source, "text": text}) + "\n")
            print(family, label, len(text.split()), "words")


if __name__ == "__main__":
    main()
