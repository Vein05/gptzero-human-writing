"""Earnings releases and other press releases filed with the SEC (8-K exhibits EX-99), 2005-2020.

    SEC_USER_AGENT="name email" python3 -m collect.edgar earnings|peers|short|regional|warm|dividends OUT.jsonl

  earnings  8-K filings with item 2.02 (results of operations), 2005-2020, from the companies in TICKERS and DEFUNCT:
            two filings a year per company, at most 25 per company, in a seeded random order; the EX-99.1 exhibit;
            every prose run of 300+ words
  peers     every item 2.02 filing of Lehman's four peers, 2005-2008: every prose run of 300+ words
  short     every 8-K of Lehman and its four peers, 2005-2008: every EX-99 exhibit with no data table and 250-450
            words, taken whole
  regional  every item 2.02 filing of about 30 US regional banks, 2005-2008: prose runs of 750+ words, and headed
            sections of 750+ words inside a run
  warm      four paragraph ranges of peer prose runs (WARM_CUTS)
  dividends three Bear Stearns dividend releases, whole (DIVIDEND_RELEASES)

A prose run is consecutive published prose: lines of 6+ words with under 40% numeric tokens. A table row or a line of
figures ends a run; a short heading between prose paragraphs stays in it; a sentence broken by a page break is joined.
"""

import hashlib
import json
import random
import re
import sys

from collect.fetch import fetch
from collect.text import html_lines

TICKERS = (
    "GS MS JPM BAC C WFC USB PNC COF BK STT SCHW AXP BLK NTRS FITB KEY RF TFC CMA HBAN MTB ZION AMP BEN TROW RJF "
    "PRU MET AIG ALL TRV CB MMC AON SPGI MCO ICE CME NDAQ "
    "AAPL MSFT IBM INTC CSCO ORCL HPQ XOM CVX GE KO PEP PG JNJ PFE MRK WMT HD MCD DIS T VZ CAT DE MMM BA LMT UPS FDX"
).split()
DEFUNCT = {
    "Lehman Brothers": 806085,
    "Bear Stearns": 777001,
    "Merrill Lynch": 65100,
    "Washington Mutual": 933136,
    "Wachovia": 36995,
    "Countrywide": 25191,
    "National City": 69970,
}
PEERS = {"GoldmanSachs": 886982, "MorganStanley": 895421, "BearStearns": 777001, "MerrillLynch": 65100}
LEHMAN_AND_PEERS = {"Lehman": 806085, "BearStearns": 777001, "MorganStanley": 895421, "GoldmanSachs": 886982}
LEHMAN_AND_PEERS["MerrillLynch"] = 65100
REGIONAL_BANKS = {
    "Huntington": 49196,
    "FifthThird": 35527,
    "KeyCorp": 91576,
    "PNC": 713676,
    "Regions": 1281761,
    "RegionsOld": 36032,
    "SunTrust": 750556,
    "BBT": 92230,
    "MTBank": 36270,
    "Comerica": 28412,
    "Zions": 109380,
    "NationalCity": 69970,
    "MarshallIlsley": 62741,
    "MarshallIlsleyNew": 1399315,
    "USBancorp": 36104,
    "Wachovia": 36995,
    "FirstHorizon": 36966,
    "Synovus": 18349,
    "Associated": 7789,
    "TCF": 814184,
    "CommerceBancshares": 22356,
    "Colonial": 92339,
    "Webster": 801337,
    "CityNational": 201461,
    "CullenFrost": 39263,
    "BOKF": 875357,
    "ValleyNational": 714310,
    "Fulton": 700564,
    "Sovereign": 811830,
    "FirstMidwest": 702325,
    "UnionBanCal": 1011659,
    "WilmingtonTrust": 872821,
}
# Paragraph ranges of single prose runs from the peer releases, picked after scanning from GPTZero's sentence scores
# as the warmest stretches: (exhibit, run number in the exhibit, first and last paragraph).
SEC_ARCHIVES = "https://www.sec.gov/Archives/edgar/data/"
WARM_CUTS = [
    (SEC_ARCHIVES + "886982/000095012307003690/y31714exv99w1.htm", 0, 9, 14),
    (SEC_ARCHIVES + "886982/000095012307003690/y31714exv99w1.htm", 0, 8, 14),
    (SEC_ARCHIVES + "777001/000077700106000053/ex99.htm", 0, 0, 6),
    (SEC_ARCHIVES + "895421/000115752307006209/a5427779ex991.htm", 0, 5, 7),
]
# Three of the five Bear Stearns dividend releases among the short releases, picked by hand.
DIVIDEND_RELEASES = [
    SEC_ARCHIVES + "777001/000077700105000084/ex99.htm",
    SEC_ARCHIVES + "777001/000077700106000088/ex99.htm",
    SEC_ARCHIVES + "777001/000077700106000100/ex99.htm",
]
SEED = 20261120
ANY_EX99 = re.compile(r">\s*EX-99(\.\d+)?\s*<")
EX99_1 = re.compile(r">\s*EX-99\.?1?\s*<")
ENDS_CLAUSE = re.compile(r"[.!?:;)\"”’]\s*$")
FORWARD_LOOKING = re.compile(r"forward-looking statements|safe harbor|Private Securities Litigation", re.I)
HIDDEN_OCR_LAYER = re.compile(r"font-size:\s*1pt[^\"']*color:\s*white|color:\s*white[^\"']*font-size:\s*1pt", re.I)


def get(url):
    return (fetch(url) or b"").decode("latin-1")


def filings(cik, first_year, last_year, item="2.02"):
    """(company name, [(filing date, accession number, items)]) of the 8-K filings in the years given whose items
    include `item` (any 8-K when item is None), in the order EDGAR lists them."""
    s = json.loads(get(f"https://data.sec.gov/submissions/CIK{cik:010d}.json") or "{}")
    if not s:
        return "", []
    blocks = [s["filings"]["recent"]]
    blocks += [json.loads(get("https://data.sec.gov/submissions/" + f["name"]) or "{}") for f in s["filings"]["files"]]
    found = []
    for b in blocks:
        for i, form in enumerate(b.get("form", [])):
            items = b.get("items", [""] * (i + 1))[i] or ""
            year = b["filingDate"][i][:4]
            if form == "8-K" and str(first_year) <= year <= str(last_year) and (item is None or item in items):
                found.append((b["filingDate"][i], b["accessionNumber"][i], items))
    return s.get("name", ""), found


def filing_index(cik, acc):
    return f"https://www.sec.gov/Archives/edgar/data/{cik}/{acc.replace('-', '')}/{acc}-index.htm"


def exhibits(cik, acc, label=ANY_EX99):
    """Addresses of the filing's documents whose type matches `label`, in the order of the filing index."""
    index = filing_index(cik, acc)
    base = index.rsplit("/", 1)[0] + "/"
    for row in re.findall(r"<tr[^>]*>(.*?)</tr>", get(index), re.S):
        m = re.search(r'href="([^"]+)"', row)
        if label.search(row) and m:
            yield "https://www.sec.gov" + m.group(1) if m.group(1).startswith("/") else base + m.group(1)


def is_html(url):
    return url.lower().endswith((".htm", ".html"))


def trim_to_sentences(run):
    """Drop a broken sentence at either end of a run (a run cut by a table or a page break)."""
    if re.match(r"[a-z(,;]", run):
        m = re.search(r"[.!?][\"”’)]?\s+(?=[A-Z“\"])", run)
        run = run[m.end() :] if m else ""
    if run and not ENDS_CLAUSE.search(run):
        ends = list(re.finditer(r"[.!?][\"”’)]?(?=\s)", run))
        run = run[: ends[-1].end()] if ends else ""
    return run.strip()


def is_numeric(token):
    return bool(re.search(r"\d", token)) or token in {"$", "%", "|", "-", "--"}


def prose_runs(raw, html, min_words=300):
    """Runs of consecutive prose paragraphs in a filing, each of at least `min_words` words."""
    if html and HIDDEN_OCR_LAYER.search(raw):
        return []
    lines = html_lines(raw) if html else [re.sub(r"[ \t\xa0]+", " ", x).strip() for x in raw.split("\n")]
    runs, run, para = [], [], []

    def end_paragraph():
        if para:
            run.append(" ".join(para))
            para.clear()

    def end_run():
        end_paragraph()
        if run:
            runs.append("\n\n".join(run))
            run.clear()

    i = 0
    while i < len(lines):
        line = lines[i]
        i += 1
        if not line:
            end_paragraph()
            continue
        last = para[-1] if para else (run[-1] if run else "")
        if last and not ENDS_CLAUSE.search(last) and len(line.split()) <= 8 and not re.match(r"[a-z]", line):
            # A page break inside a sentence: up to 8 short lines (page number, running head, blank lines), then the
            # sentence goes on in lower case.
            j, skipped, blank = i - 1, 0, False
            while j < len(lines) and skipped <= 8 and len(lines[j].split()) <= 8 and not re.match(r"[a-z]", lines[j]):
                skipped += bool(lines[j])
                blank |= not lines[j]
                j += 1
            if j < len(lines) and skipped <= 8 and blank and re.match(r"[a-z]", lines[j]) and "|" not in lines[j]:
                if not para:
                    para.append(run.pop())
                para.append(lines[j])
                i = j + 1
                continue
        if "|" in line:
            # A layout table whose one long cell holds the prose and whose other cells are bullets or notes.
            cells = [c.strip() for c in line.split("|") if c.strip()]
            long = [c for c in cells if len(c.split()) >= 12]
            if len(long) == 1 and sum(len(c.split()) for c in cells if c is not long[0]) <= 3:
                line = long[0]
        tokens = line.split()
        numeric = sum(map(is_numeric, tokens))
        if "|" not in line and len(tokens) >= 6 and numeric / len(tokens) < 0.4:
            para.append(line)
        elif para and len(tokens) < 6 and numeric == 0 and not line.endswith(":"):
            para.append(line)
        elif not para and run and len(tokens) <= 8 and numeric == 0:
            run.append(line)
        else:
            end_run()
    end_run()
    runs = [trim_to_sentences(re.sub(r"(\n\n[^\n]{0,80})+$", "", r)) for r in runs]
    return [r for r in runs if len(r.split()) >= min_words]


def whole_text(raw, html):
    """A whole exhibit as paragraphs, or None if it holds a data table. Exhibit labels and page numbers are dropped;
    hard-wrapped lines are joined."""
    if html:
        t = re.sub(r"\s+", " ", re.sub(r"(?is)<(script|style).*?</\1>", " ", raw))
        if re.search(r"(?i)<td[^>]*>[^<]*\d[^<]*</td>\s*<td", t) and len(re.findall(r"(?i)<tr", t)) > 6:
            return None
        lines = html_lines(t, cells=" ")
    else:
        lines = [re.sub(r"[ \t\xa0]+", " ", x).strip() for x in re.sub(r"(?s)<[^>]+>", "", raw).split("\n")]
    label = re.compile(r"(?i)(exhibit|ex-)\s*99(\.\d+)?|page \d+|-?\s*\d+\s*-?")
    paras, cur = [], []
    for line in (x for x in lines if x and not label.fullmatch(x)):
        cur.append(line)
        if re.search(r"[.!?:\"”)]$", line) or len(line.split()) <= 8:
            paras.append(" ".join(cur))
            cur = []
    if cur:
        paras.append(" ".join(cur))
    return "\n\n".join(paras)


def headed_sections(run):
    """Each heading (a short paragraph with no figures and no end punctuation) with the paragraphs under it."""
    sections, cur = [], []
    for p in run.split("\n\n"):
        if len(p.split()) <= 10 and not re.search(r"\d", p) and not re.search(r"[.!?:]$", p):
            if cur:
                sections.append(cur)
            cur = [p]
        else:
            cur.append(p)
    if cur:
        sections.append(cur)
    return [
        "\n\n".join(s) for s in sections if len(s) > 1 and len(s[0].split()) <= 10 and not re.search(r"[.!?]$", s[0])
    ]


def row(text, url, cik, acc, date, company, **extra):
    return {
        "text": text,
        "words": len(text.split()),
        "source": url,
        "filing_index": filing_index(cik, acc),
        "date": date,
        "company": company,
        **extra,
    }


def runs_of(url):
    return prose_runs(get(url), is_html(url)) if url else []


def earnings(per_company=25):
    """Prose runs from a seeded sample of item 2.02 filings, 2005-2020."""
    tickers = json.loads(get("https://www.sec.gov/files/company_tickers.json"))
    cik_of = {v["ticker"]: int(v["cik_str"]) for v in tickers.values()}
    companies = [(t, cik_of[t]) for t in TICKERS if t in cik_of] + list(DEFUNCT.items())
    rng, out, seen = random.Random(SEED), [], set()
    for label, cik in companies:
        name, found = filings(cik, 2005, 2020)
        if label in DEFUNCT and label.split()[0].lower() not in name.lower():
            continue
        by_year = {}
        for f in found:
            by_year.setdefault(f[0][:4], []).append(f[:2])
        pick = []
        for year in sorted(by_year):
            rng.shuffle(by_year[year])
            pick += by_year[year][:2]
        rng.shuffle(pick)
        for date, acc in pick[:per_company]:
            url = next(exhibits(cik, acc, EX99_1), None)
            for run in runs_of(url):
                if run[:500] not in seen:
                    seen.add(run[:500])
                    out.append(row(run, url, cik, acc, date, name, boilerplate=bool(FORWARD_LOOKING.search(run[:400]))))
    return out


def peers():
    """Every prose run of 300+ words in the earnings releases of Lehman's four peers, 2005-2008."""
    out, seen = [], set()
    for cik in PEERS.values():
        name, found = filings(cik, 2005, 2008)
        for date, acc, _ in sorted(set(found)):
            url = next(exhibits(cik, acc, EX99_1), None)
            for run in runs_of(url):
                if run[:500] not in seen:
                    seen.add(run[:500])
                    out.append(row(run, url, cik, acc, date, name, boilerplate=bool(FORWARD_LOOKING.search(run[:400]))))
    return out


def short_releases():
    """Whole EX-99 exhibits of 250-450 words with no data table, from every 8-K of Lehman and its peers, 2005-2008."""
    out = []
    for company, cik in LEHMAN_AND_PEERS.items():
        for date, acc, items in sorted(set(filings(cik, 2005, 2008, item=None)[1])):
            for url in exhibits(cik, acc):
                text = whole_text(get(url), is_html(url))
                if text and 250 <= len(text.split()) <= 450:
                    out.append(row(text, url, cik, acc, date, company, items=items))
    return out


def regional():
    """Prose runs and headed sections of 750+ words from the earnings releases of US regional banks, 2005-2008."""
    out, seen = [], set()
    for company, cik in REGIONAL_BANKS.items():
        for date, acc, _ in sorted(set(filings(cik, 2005, 2008)[1])):
            for url in exhibits(cik, acc):
                for run in runs_of(url):
                    units = [("whole prose run", run)] + [
                        ("headed section", s) for s in headed_sections(run) if s != run
                    ]
                    for unit, text in units:
                        key = hashlib.sha1(text[:600].encode()).hexdigest()
                        if len(text.split()) >= 750 and key not in seen:
                            seen.add(key)
                            out.append(row(text, url, cik, acc, date, company, unit=unit))
    return out


def warm_cuts():
    out = []
    for url, k, first, last in WARM_CUTS:
        paras = runs_of(url)[k].split("\n\n")
        out.append({"text": "\n\n".join(paras[first : last + 1]), "source": url, "paragraphs": [first, last]})
    return out


def dividend_releases():
    """The whole releases without EDGAR's label line ("EX-99 2 ex99.htm EXHIBIT 99")."""
    out = []
    for url in DIVIDEND_RELEASES:
        first, rest = whole_text(get(url), True).split("\n\n", 1)
        assert first.startswith("EX-99")
        out.append({"text": rest, "source": url})
    return out


def main():
    collect = {
        "earnings": earnings,
        "peers": peers,
        "short": short_releases,
        "regional": regional,
        "warm": warm_cuts,
        "dividends": dividend_releases,
    }[sys.argv[1]]
    rows = collect()
    with open(sys.argv[2], "w") as f:
        f.writelines(json.dumps(r) + "\n" for r in rows)
    print(len(rows), "texts,", sum(len(r["text"].split()) for r in rows), "words")


if __name__ == "__main__":
    main()
