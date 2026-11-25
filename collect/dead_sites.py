"""Pages of company websites that left the live web around 2008-2015, from Wayback snapshots taken 2000-2015.

    python3 -m collect.dead_sites OUT.jsonl [PAGES_PER_SITE]

For each site: the Wayback listing of its HTML pages (one capture per address), without query strings, files, shop
and login pages; addresses that look like press, news, about, investor or history pages come first, each group
shuffled with a fixed seed; up to PAGES_PER_SITE (default 120) are read. A page's main text is its longest run of
prose paragraphs (20+ words each, one shorter paragraph allowed inside the run); runs of 300-1,200 words are kept
whole. Wayback refuses more than about 15 requests a minute, so set COLLECT_PAUSE_SECONDS=4 for this collector.
"""

import hashlib
import json
import random
import re
import sys

from collect import wayback
from collect.fetch import fetch
from collect.text import page_paragraphs

SITES = {
    "bearstearns.com": "Bear Stearns (bank, acquired 2008)",
    "wamu.com": "Washington Mutual (bank, failed 2008)",
    "countrywide.com": "Countrywide (mortgage lender, acquired 2008)",
    "wachovia.com": "Wachovia (bank, acquired 2008)",
    "ml.com": "Merrill Lynch (bank, acquired 2009)",
    "nationalcity.com": "National City (bank, acquired 2008)",
    "indymacbank.com": "IndyMac (bank, failed 2008)",
    "newcenturycorp.com": "New Century (mortgage lender, failed 2007)",
    "ameriquest.net": "Ameriquest (mortgage lender, closed 2007)",
    "colonialbank.com": "Colonial Bank (failed 2009)",
    "enron.com": "Enron (energy, bankrupt 2001)",
    "worldcom.com": "WorldCom (telecom, bankrupt 2002)",
    "nortel.com": "Nortel (telecom equipment, bankrupt 2009)",
    "alltel.com": "Alltel (telecom, acquired 2009)",
    "nextel.com": "Nextel (telecom, merged 2005)",
    "cingular.com": "Cingular (telecom, renamed 2007)",
    "circuitcity.com": "Circuit City (retail, liquidated 2009)",
    "bordersgroupinc.com": "Borders Group (retail, liquidated 2011)",
    "linensnthings.com": "Linens 'n Things (retail, liquidated 2008)",
    "sharperimage.com": "Sharper Image (retail, bankrupt 2008)",
    "compusa.com": "CompUSA (retail, closed 2007)",
    "mervyns.com": "Mervyns (retail, liquidated 2008)",
    "tweeter.com": "Tweeter (retail, closed 2008)",
    "kbtoys.com": "KB Toys (retail, liquidated 2009)",
    "sun.com": "Sun Microsystems (tech, acquired 2010)",
    "palm.com": "Palm (tech, acquired 2010)",
    "3com.com": "3Com (tech, acquired 2010)",
    "novell.com": "Novell (tech, acquired 2011)",
    "gateway.com": "Gateway (tech, acquired 2007)",
    "compaq.com": "Compaq (tech, acquired 2002)",
    "wyeth.com": "Wyeth (pharma, acquired 2009)",
    "schering-plough.com": "Schering-Plough (pharma, merged 2009)",
    "genzyme.com": "Genzyme (biotech, acquired 2011)",
    "medimmune.com": "MedImmune (biotech, acquired 2007)",
    "continental.com": "Continental Airlines (merged 2010)",
    "nwa.com": "Northwest Airlines (merged 2008)",
    "usairways.com": "US Airways (merged 2013)",
    "airtran.com": "AirTran (merged 2011)",
    "saturn.com": "Saturn (car brand, closed 2010)",
    "pontiac.com": "Pontiac (car brand, closed 2010)",
    "hummer.com": "Hummer (car brand, closed 2010)",
    "mercury-vehicles.com": "Mercury (car brand, closed 2011)",
    "anheuser-busch.com": "Anheuser-Busch (brewer, acquired 2008)",
    "cadburyschweppes.com": "Cadbury Schweppes (food, split 2008)",
    "wrigley.com": "Wrigley (food, acquired 2008)",
    "gillette.com": "Gillette (consumer goods, acquired 2005)",
    "mirant.com": "Mirant (power, merged 2010)",
    "txu.com": "TXU (power, bought out 2007)",
    "blockbuster.com": "Blockbuster (video rental, bankrupt 2010)",
    "hollywoodvideo.com": "Hollywood Video (video rental, closed 2010)",
}
SEED = 20261121
LIKELY_PROSE = re.compile(
    r"press|news|release|about|investor|history|annual|letter|overview|story|stories|article|feature|profile|"
    r"company|corporate|responsib|community|speech|message|report",
    re.I,
)
SKIP = re.compile(
    r"\.(jpg|jpeg|gif|png|pdf|css|js|zip|exe|swf|xml|txt|doc|xls|ppt)(\?|$)|login|signin|search|cart|"
    r"store\.|shop|product|sku|locator|map|\bcgi-bin\b|sessionid|jsessionid",
    re.I,
)


def prose_run(paras):
    """The longest run of paragraphs of 20+ words, with at most one shorter paragraph (3+ words) inside it."""
    best, cur, gap = [], [], 0

    def words(run):
        return sum(len(p.split()) for p in run)

    for p in paras:
        n = len(p.split())
        if n >= 20:
            cur.append(p)
            gap = 0
        elif cur and gap == 0 and n >= 3:
            cur.append(p)
            gap = 1
        else:
            if gap and cur:
                cur.pop()
            if words(cur) > words(best):
                best = cur
            cur, gap = [], 0
    if gap and cur:
        cur.pop()
    return cur if words(cur) > words(best) else best


def main_text(raw):
    return "\n\n".join(prose_run(page_paragraphs(raw)))


def site_pages(domain, rng, limit):
    rows = wayback.listing(
        f"{domain}/*",
        fl="original,timestamp",
        filter=["statuscode:200", "mimetype:text/html"],
        collapse="urlkey",
        limit="30000",
        **{"from": "2000", "to": "2015"},
    )
    rows = [r for r in rows if not SKIP.search(r["original"]) and "?" not in r["original"]]
    first = [r for r in rows if LIKELY_PROSE.search(r["original"])]
    rest = [r for r in rows if not LIKELY_PROSE.search(r["original"])]
    rng.shuffle(first)
    rng.shuffle(rest)
    return (first + rest)[:limit]


def main():
    limit = int(sys.argv[2]) if len(sys.argv) > 2 else 120
    rng, seen = random.Random(SEED), set()
    with open(sys.argv[1], "w") as f:
        for domain, firm in SITES.items():
            for r in site_pages(domain, rng, limit):
                raw = fetch(wayback.raw(r["timestamp"], r["original"]))
                text = main_text(raw) if raw else ""
                key = hashlib.sha1(text.encode()).hexdigest()
                if 300 <= len(text.split()) <= 1200 and key not in seen:
                    seen.add(key)
                    source = wayback.shown(r["timestamp"], r["original"])
                    f.write(json.dumps({"site": domain, "firm": firm, "source": source, "text": text}) + "\n")


if __name__ == "__main__":
    main()
