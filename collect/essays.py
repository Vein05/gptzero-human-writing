"""Student essays from two dead sites on the Wayback Machine, and the two batches that were scanned.

    python3 -m collect.essays OUT_DIR [LISTING.json]

  buckhoff.topcities.com  a college ESL and composition instructor's pages: each student essay sits under a "Score N"
                          heading and its own title
  gettoefl.com            TOEFL writing (TWE) practice: pages of scored sample essays, and model essays

An essay is its title line (if any) and its body paragraphs, from the line after its score heading (rubric lines
skipped) to the next score heading, rubric block, "Back to Top" or comments line. Each page's earliest snapshot is used.

Writes OUT_DIR/essays.jsonl (every essay of 80+ words) and the two scanned batches:
  twe.jsonl    every buckhoff essay of 300+ words on a TOEFL writing prompt (pages with "twe" in the address)
  long.jsonl   five whole essays of 750+ words from the English 306 pages, picked by reading them (LONG_ESSAYS)
Cleaning only undoes the archive's encoding and the page layout: Windows-1252 punctuation is decoded, hard line breaks
inside a sentence are joined (twe), and works-cited lists and footnote digits are left out (long).

LISTING.json maps each site to its Wayback captures as [timestamp, address, type] rows; without it the listing is
downloaded.
"""

import hashlib
import json
import re
import sys
from html import unescape
from pathlib import Path

from collect import wayback
from collect.fetch import fetch

SITES = ("buckhoff.topcities.com", "gettoefl.com")
LONG_ESSAYS = ["72510bee", "a07c1c54", "057b942a", "a4a32cef", "aed3eaed"]
CP1252_PUNCTUATION = str.maketrans({"\x91": "‘", "\x92": "’", "\x93": "“", "\x94": "”", "\x96": "–", "\x97": "—"})
SCORE = re.compile(r"^Score:?\s*\d(\.\d)?\s*[+-]?$", re.I)
RUBRIC = re.compile(
    r"^(Demonstrates|Suggests|A paper in this category|An essay in this category|"
    r"(Inadequate|Marginal|Adequate|Competent|Superior|Excellent|Seriously|Weak|Limited|Strong|Very)\b.{0,20}\d|[a-z])"
)
END = re.compile(
    r"^(Back to Top|\d+\. Comments on how|Score\b|\||\d+\.\s+\S|.*out of \d+ =|Copyright \(C\)|Grading Form)", re.I
)


def listing(domain):
    """[(timestamp, address)] of the HTML pages captured on a site before 2012."""
    rows = wayback.listing(
        domain,
        matchType="domain",
        to="2012",
        filter="statuscode:200",
        fl="timestamp,original,mimetype",
        collapse="urlkey",
        limit="5000",
    )
    return [(r["timestamp"], r["original"]) for r in rows if "html" in r["mimetype"]]


def lines(raw):
    """A page's non-empty text lines (block elements end lines; the pages are Latin-1)."""
    s = re.sub(r"\s+", " ", re.sub(r"(?is)<(script|style).*?</\1>", " ", raw.decode("latin-1")))
    s = re.sub(r"(?i)</?(p|div|br|tr|li|h\d|table|td|blockquote|pre)\b[^>]*>", "\n", s)
    s = unescape(re.sub(r"<[^>]+>", "", s))
    return [re.sub(r"[ \xa0]+", " ", x).strip() for x in s.split("\n") if x.strip()]


def essay_pages(domain, captures):
    """{page key: (timestamp, address)}: the earliest capture of each essay page."""
    first = {}
    for ts, url in captures:
        key = re.sub(r"^https?://(www\.)?|:80", "", url).lower()
        if domain == "gettoefl.com":
            wanted = re.search(r"/toefl_essay/(day/\d+|scored_samples|[ivx]+/essa)", key)
        else:
            wanted = re.search(r"essay|sample|twe|writing", key) and "scoring" not in key
        if wanted and (key not in first or ts < first[key][0]):
            first[key] = (ts, url)
    return first


def model_essay(lines_):
    """A gettoefl model essay: the body between the scoring criteria and the comments line."""
    a = next((j for j, x in enumerate(lines_) if x.startswith('To score a "6')), None)
    b = next((j for j, x in enumerate(lines_) if re.match(r"\d+\. Comments on how", x)), None)
    if a is None or not b:
        return None
    return {"score": "model 6", "title": lines_[a - 1][:100] if a else "", "text": "\n\n".join(lines_[a + 1 : b])}


def scored_essays(lines_):
    """Each essay under a score heading: [{score, title, text}]."""
    out, i = [], 0
    while i < len(lines_):
        if not SCORE.match(lines_[i]):
            i += 1
            continue
        score, j, title = lines_[i], i + 1, ""
        while j < len(lines_) and RUBRIC.match(lines_[j]) and len(lines_[j].split()) < 40:
            j += 1
        if j < len(lines_) and len(lines_[j].split()) <= 14 and not END.match(lines_[j]):
            title, j = lines_[j], j + 1
        short = j < len(lines_) and len(lines_[j].split()) <= 14
        if short and not END.match(lines_[j]) and not re.search(r"[.!?\"]$", lines_[j]):
            title, j = title + " / " + lines_[j], j + 1
        body = []
        while j < len(lines_) and not END.match(lines_[j]):
            if RUBRIC.match(lines_[j]) and re.match(r"^[A-Z][a-z]+ \d", lines_[j]):
                break
            body.append(lines_[j])
            j += 1
        if body:
            out.append({"score": score, "title": title, "text": "\n\n".join(([title] if title else []) + body)})
        i = j
    return out


def essays(captures_by_site):
    """Every distinct essay of 80+ words, keyed by the first 60 words."""
    out, seen = [], set()
    for domain, captures in captures_by_site.items():
        for key, (ts, url) in sorted(essay_pages(domain, captures).items()):
            page = lines(fetch(wayback.raw(ts, url)) or b"")
            if domain == "gettoefl.com" and re.search(r"/essay\d+\.htm$", key):
                found = [e for e in [model_essay(page)] if e]
            else:
                found = scored_essays(page)
            for e in found:
                h = hashlib.sha1(" ".join(e["text"].split()[:60]).encode()).hexdigest()
                if h in seen or len(e["text"].split()) < 80:
                    continue
                seen.add(h)
                e |= {"id": f"{domain.split('.')[0]}_{h[:8]}", "site": domain, "page": key, "ts": ts, "url": url}
                out.append(e | {"words": len(e["text"].split())})
    return out


def unwrap(text):
    """Join a paragraph to the next when the break falls inside a sentence."""
    out = []
    for p in text.split("\n\n"):
        if out and not re.search(r"[.!?:\"”’')]\s*$", out[-1]) and (p[:1].islower() or out[-1].rstrip().endswith(",")):
            out[-1] = out[-1].rstrip() + " " + p
        else:
            out.append(p)
    return "\n\n".join(out)


def twe_batch(all_essays):
    return [
        {
            "id": e["id"],
            "text": unwrap(e["text"].translate(CP1252_PUNCTUATION)),
            "source": wayback.shown(e["ts"], e["url"]),
        }
        for e in all_essays
        if "twe" in e["page"] and e["words"] >= 300
    ]


def long_batch(all_essays):
    by_key = {e["id"][-8:]: e for e in all_essays}
    out = []
    for key in LONG_ESSAYS:
        e = by_key[key]
        t = e["text"].translate(CP1252_PUNCTUATION)
        t = re.split(r"\n\n(?:Works? Cited|Footnotes:?|Bibliography|References)\s*(?:\n\n|$)", t)[0].strip()
        t = re.sub(r'([.!?]["”]?)\d{1,2}(?=\s|$)', r"\1", t)
        out.append({"id": e["id"], "text": t, "source": wayback.shown(e["ts"], e["url"])})
    return out


def main():
    out = Path(sys.argv[1])
    out.mkdir(parents=True, exist_ok=True)
    if len(sys.argv) > 2:
        captures = {d: [(ts, url) for ts, url, _ in rows] for d, rows in json.load(open(sys.argv[2])).items()}
    else:
        captures = {d: listing(d) for d in SITES}
    found = essays(captures)
    for name, rows in (("essays", found), ("twe", twe_batch(found)), ("long", long_batch(found))):
        (out / f"{name}.jsonl").write_text("".join(json.dumps(r) + "\n" for r in rows))
        print(name, len(rows), "texts")


if __name__ == "__main__":
    main()
