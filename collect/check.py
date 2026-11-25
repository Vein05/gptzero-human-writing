"""Check, offline, that the collectors give back the dataset's texts: every text is rebuilt from the raw pages in the
download cache and compared with the dataset's text_sha256 (withheld texts included).

    COLLECT_CACHE=.cache python3 -m collect.check [DATA_FOLDER] [LEHMAN_PAGE_TEXTS.jsonl]

A source counts only the dataset texts whose raw page is in the cache. Lehman's cuts can also be checked from a file
of page texts ("source" and "text" per line), as collect.lehman writes to pages.jsonl.
"""

import hashlib
import importlib.util
import json
import os
import re
import sys

from collect import dead_sites, edgar, essays, google_answers, lehman, results_prose, wayback
from collect.fetch import NotCached, cache_path
from dataset import DEFAULT, load

os.environ["COLLECT_OFFLINE"] = "1"
HAS_TRAFILATURA = importlib.util.find_spec("trafilatura") is not None
RESULTS_PROSE = {"bls.gov": "bls", "ncdc.noaa.gov": "noaa", "usda.gov": "wasde", "espn.com": "espn"}


def sha(text):
    return hashlib.sha256(text.encode()).hexdigest()


def cached(url):
    return cache_path(wayback.raw_from_shown(url) if "web.archive.org" in url else url).exists()


def lehman_quarter(url):
    return lehman.quarter(re.sub(r"[?#].*", "", url))


def check_lehman(rows, page_texts):
    """The cuts of Lehman's release pages. Whole pages from the early web sampling (described as "pre-2008 ...") and
    the one cleaned copy of such a page ("same span as ...") had no script and are left out. A page's text comes from
    its cached snapshot, else from page_texts, any snapshot of the same quarter."""
    rows = [
        r
        for r in rows
        if re.search(r"lehman\.com.*/qe/", r["source_url"])
        and not r["description"].startswith("pre-2008")
        and "same span as" not in r["description"]
    ]
    texts = {lehman_quarter(url): text for url, text in page_texts.items()}
    for url in {r["source_url"] for r in rows if cached(r["source_url"])}:
        texts[lehman_quarter(url)] = lehman.page_text(url)
    found = {sha(c) for q, text in texts.items() for _, c in lehman.cuts(q, text)}
    return [r for r in rows if lehman_quarter(r["source_url"]) in texts], found


def check_edgar(rows):
    found, read = set(), set()
    for collect in (edgar.peers, edgar.short_releases, edgar.warm_cuts, edgar.dividend_releases):
        try:
            out = collect()
        except NotCached:
            continue
        found |= {sha(r["text"]) for r in out}
        read |= {r["source"] for r in out}
    return [r for r in rows if r["source_url"] in read], found


def check_essays(rows):
    essay_rows = [r for r in rows if "buckhoff" in r["source_url"] and cached(r["source_url"])]
    captures = {"buckhoff.topcities.com": [r["source_url"].split("/web/")[1].split("/", 1) for r in essay_rows]}
    found = essays.essays(captures)
    return essay_rows, {sha(r["text"]) for r in essays.twe_batch(found) + essays.long_batch(found)}


def check_wayback_pages(rows):
    """Results prose, Google Answers, web genres (with trafilatura installed) and dead company sites: one text per
    page."""
    out, found = [], set()
    for r in rows:
        url = r["source_url"]
        host = next((h for h in RESULTS_PROSE if h in url), None)
        if "web.archive.org" not in url or not cached(url):
            continue
        raw = open(cache_path(wayback.raw_from_shown(url)), "rb").read()
        if host:
            family = RESULTS_PROSE[host]
            anchor = next(a for f, s, a, _ in results_prose.PAGES if s in url)
            text = results_prose.results_text(family, raw, anchor)
        elif "answers.google.com" in url:
            text = google_answers.answer_text(raw.decode("latin-1"))
        elif r["kind"].startswith("Corporate web pages"):
            text = dead_sites.main_text(raw)
        elif r["kind"].startswith("Plain web genres") and HAS_TRAFILATURA:
            from collect import web_genres

            text = web_genres.main_text(raw)
        else:
            continue
        out.append(r)
        found.add(sha(text))
    return out, found


def report(data, page_texts=None):
    """{source: (texts reproduced, texts whose raw input is available)}."""
    rows = data["human_scans"]
    checks = {
        "Lehman releases (lehman.com)": check_lehman(rows, page_texts or {}),
        "SEC filings": check_edgar(rows),
        "Student essays": check_essays(rows),
        "Other Wayback pages": check_wayback_pages(rows),
    }
    return {name: (sum(r["text_sha256"] in found for r in got), len(got)) for name, (got, found) in checks.items()}


def main():
    data = load(sys.argv[1] if len(sys.argv) > 1 else DEFAULT)
    page_texts = {}
    if len(sys.argv) > 2:
        page_texts = {p["source"]: p["text"] for p in map(json.loads, open(sys.argv[2]))}
    for name, (same, total) in report(data, page_texts).items():
        print(f"{name}: {same} of {total} texts reproduced")


if __name__ == "__main__":
    main()
