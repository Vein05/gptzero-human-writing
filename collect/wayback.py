"""Wayback Machine listings and snapshot addresses."""

import json
import urllib.parse

from collect.fetch import fetch

CDX = "https://web.archive.org/cdx/search/cdx?"


def listing(url, **params):
    """Return CDX rows as dicts (timestamp, original, ...) for `url` and the given CDX parameters."""
    query = urllib.parse.urlencode({"url": url, "output": "json", **params}, doseq=True)
    rows = json.loads(fetch(CDX + query) or b"[]")
    return [dict(zip(rows[0], r)) for r in rows[1:]]


def raw(timestamp, original):
    """Address of the archived file as captured, without the Wayback banner."""
    return f"http://web.archive.org/web/{timestamp}id_/{original}"


def shown(timestamp, original):
    """Address of the snapshot as a reader sees it: the proof of date given for each text."""
    return f"https://web.archive.org/web/{timestamp}/{original}"


def raw_from_shown(url):
    timestamp, original = url.split("/web/", 1)[1].split("/", 1)
    return raw(timestamp, original)
