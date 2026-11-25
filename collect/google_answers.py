"""Google Answers (2002-2006): answers that paid researchers wrote to users' questions, from Wayback snapshots taken
2002-2007.

    python3 -m collect.google_answers LISTING.txt OUT.jsonl [N]

LISTING.txt is a Wayback CDX listing of answers.google.com/answers/threadview?id=... ("timestamp address ..." per
line). One snapshot per thread, shuffled with a fixed seed; the first N threads (default 400) are read. The answer is
the <pre> block after the page's answer marker; the only change is joining the hard-wrapped lines of each paragraph.
"""

import json
import random
import re
import sys
from html import unescape

from collect import wayback
from collect.fetch import fetch

SEED = 20261120
ANSWER_MARKER = "google_ad_region_start=answer_text"


def answer_text(page):
    """The researcher's answer as paragraphs, or None."""
    i = page.find(ANSWER_MARKER)
    m = re.search(r"<pre>(.*?)</pre>", page[i : i + 400000], re.S) if i >= 0 else None
    if not m:
        return None
    raw = unescape(re.sub(r"<[^>]+>", "", m.group(1))).replace("\r", "")
    paras = [" ".join(x.strip() for x in p.split("\n") if x.strip()) for p in re.split(r"\n\s*\n", raw)]
    return "\n\n".join(p for p in paras if p)


def threads(listing):
    """[(thread id, (timestamp, address))]: the first snapshot listed for each thread, up to 2007, shuffled."""
    first = {}
    for line in open(listing):
        ts, url, *_ = line.split()
        tid = re.search(r"id=(\d+)", url)
        if tid and ts[:4] <= "2007":
            first.setdefault(tid.group(1), (ts, url))
    items = sorted(first.items())
    random.Random(SEED).shuffle(items)
    return items


def main():
    n = int(sys.argv[3]) if len(sys.argv) > 3 else 400
    with open(sys.argv[2], "w") as f:
        for tid, (ts, url) in threads(sys.argv[1])[:n]:
            raw = fetch(wayback.raw(ts, url))
            text = answer_text(raw.decode("latin-1")) if raw else None
            if text:
                f.write(json.dumps({"thread": tid, "source": wayback.shown(ts, url), "text": text}) + "\n")


if __name__ == "__main__":
    main()
