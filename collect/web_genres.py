"""Web pages from seven genres guessed to be plain, even-rhythm human writing, from Wayback snapshots taken before 2020.

    python3 -m collect.web_genres OUT.jsonl

For each site: the Wayback listing of its address prefix (one capture per page, filtered by the address pattern),
shuffled with a fixed seed; pages are read in that order until the site gives 3 English texts of 300+ words (at most
25 tries). The main text is extracted with trafilatura and cut to the first paragraphs that reach 1,000 words. Then 5
texts per genre are taken in turn across its sites. The genres are guesses; no detector picks the texts.
Needs the collect extra (trafilatura).
"""

import hashlib
import json
import random
import re
import sys

import trafilatura

from collect import wayback
from collect.fetch import fetch

# genre: [(site, address prefix, first year, last year, pattern the page address must match)]
GENRES = {
    "Model and sample essays": [
        ("ukessays", "ukessays.com/essays/", "2012", "2019", r"/essays/[a-z-]+/[a-z0-9-]+\.php$"),
        ("123helpme", "123helpme.com/", "2008", "2019", r"view\.asp\?id=\d+$|/[a-z0-9-]+-preview\.asp\?id=\d+$"),
        (
            "ielts-simon",
            "ielts-simon.com/ielts-help-and-english-pr/20",
            "2011",
            "2019",
            r"/20\d\d/\d\d/[a-z0-9-]+\.html$",
        ),
    ],
    "Content-farm articles 2008-2013": [
        ("ehow", "ehow.com/how_", "2009", "2013", r"/how_\d+_[a-z0-9-]+\.html$"),
        ("ezinearticles", "ezinearticles.com/?", "2007", "2013", r"\?[A-Za-z0-9-]+&id=\d+$"),
        ("suite101", "suite101.com/article/", "2010", "2013", r"/article/[a-z0-9-]+-a\d+$"),
    ],
    "Text written to be simple": [
        ("voa-learning", "learningenglish.voanews.com/a/", "2014", "2019", r"/a/[a-z0-9-]+/\d+\.html$"),
        ("simple-wiki", "simple.wikipedia.org/wiki/", "2012", "2019", r"/wiki/[A-Za-z_()%0-9-]+$"),
    ],
    "Committee-edited and devotional text": [
        ("jw-wol", "wol.jw.org/en/wol/d/r1/lp-e/", "2014", "2019", r"/lp-e/\d+$"),
        ("odb", "odb.org/20", "2012", "2019", r"/20\d\d/\d\d/\d\d/[a-z0-9-]+/?$"),
    ],
    "Upbeat second-person self-help": [
        ("lifehack", "lifehack.org/articles/", "2011", "2019", r"/articles/[a-z-]+/[a-z0-9-]+\.html$"),
        ("tinybuddha", "tinybuddha.com/blog/", "2010", "2019", r"/blog/[a-z0-9-]+/?$"),
    ],
    "Chinese official English": [
        (
            "gov-cn-whitepaper",
            "english.gov.cn/archive/white_paper/",
            "2014",
            "2019",
            r"/white_paper/20\d\d/\d\d/\d\d/content_\d+\.htm$",
        ),
        (
            "chinadaily-opinion",
            "chinadaily.com.cn/opinion/20",
            "2012",
            "2019",
            r"/opinion/20\d\d-\d\d/\d\d/content_\d+\.htm$",
        ),
        (
            "china-org-whitepaper",
            "china.org.cn/government/whitepaper/",
            "2010",
            "2019",
            r"/whitepaper/\d{4}-\d\d/\d\d/content_\d+\.htm$",
        ),
    ],
    "Help pages and how-tos": [
        ("ms-support", "support.microsoft.com/en-us/help/", "2015", "2019", r"/en-us/help/\d+/[a-z0-9-]+$"),
        ("apple-support", "support.apple.com/en-us/HT", "2014", "2019", r"/en-us/HT\d+$"),
        ("wikihow", "wikihow.com/", "2012", "2019", r"wikihow\.com/[A-Z][A-Za-z0-9-]+$"),
    ],
}
PER_SITE, PER_GENRE, MAX_TRIES, CUT_WORDS = 3, 5, 25, 1000
SEED = 20261120
STOPWORDS = set("the of and to a in is that for it as with be on are this by you or your have can".split())
ERROR_PAGE = re.compile(
    r"page not found|404|access denied|cookies? (policy|settings)|javascript (is )?(disabled|required)|sign in to", re.I
)


def is_english(text):
    w = re.findall(r"[a-z']+", text.lower())
    ascii_share = sum(c.isascii() for c in text) / len(text)
    return len(w) > 0 and sum(x in STOPWORDS for x in w) / len(w) > 0.18 and ascii_share > 0.97


def first_paragraphs(text, words=CUT_WORDS):
    """The first paragraphs, up to the one that reaches `words` words."""
    out, n = [], 0
    for p in (p.strip() for p in text.split("\n") if p.strip()):
        out.append(p)
        n += len(p.split())
        if n >= words:
            break
    return "\n\n".join(out)


def main_text(raw):
    html = raw.decode("utf-8", "replace")
    text = trafilatura.extract(html, include_comments=False, include_tables=False, favor_precision=True) or ""
    return first_paragraphs(text)


def site_pages(prefix, first, last, pattern):
    rows = wayback.listing(
        prefix,
        matchType="prefix",
        limit=4000,
        filter=["statuscode:200", "mimetype:text/html"],
        collapse="urlkey",
        **{"from": first, "to": last},
    )
    return [r for r in rows if re.search(pattern, r["original"])]


def main():
    rng, pool, seen = random.Random(SEED), [], set()
    for genre, sites in GENRES.items():
        for site, prefix, first, last, pattern in sites:
            rows = site_pages(prefix, first, last, pattern)
            rng.shuffle(rows)
            kept = 0
            for r in rows[:MAX_TRIES]:
                if kept >= PER_SITE:
                    break
                raw = fetch(wayback.raw(r["timestamp"], r["original"]))
                text = main_text(raw) if raw else ""
                key = hashlib.sha1(text.encode()).hexdigest()[:10]
                if len(text.split()) < 300 or ERROR_PAGE.search(text[:400]) or not is_english(text) or key in seen:
                    continue
                seen.add(key)
                kept += 1
                source = wayback.shown(r["timestamp"], r["original"])
                pool.append({"genre": genre, "site": site, "source": source, "text": text})
    chosen = []
    for sites in GENRES.values():
        by_site = {s[0]: [p for p in pool if p["site"] == s[0]] for s in sites}
        pick = []
        while len(pick) < PER_GENRE and any(by_site.values()):
            for texts in by_site.values():
                if texts and len(pick) < PER_GENRE:
                    pick.append(texts.pop(0))
        chosen += pick
    with open(sys.argv[1], "w") as f:
        f.writelines(json.dumps(p) + "\n" for p in chosen)
    print(len(chosen), "texts from", len(pool), "found")


if __name__ == "__main__":
    main()
