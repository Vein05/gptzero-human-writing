"""Print every number in the post from the released data.

    python3 recompute.py [--data FOLDER] [--liang GPTZero.json]

--data is a local folder with the dataset's jsonl files (default: $GPTZERO_HUMAN_DATA, else the Hugging Face copy).
--liang is GPTZero.json from Liang et al.'s repository; without it the two 2023 counts are skipped.
"""

import argparse
import json
import re
from collections import Counter

from dataset import (
    DEFAULT,
    DETECTORS,
    auroc,
    called_ai,
    load,
    p_ai,
    sentence_mean,
    sentence_scores,
    short,
)

LEHMAN = "Lehman Brothers releases and filings (1998-2008)"
Q2_2008_CUTS = "Lehman Q2 2008 earnings release, unchanged cut of whole sentences"
DIVIDENDS = "Whole short press release (Bear Stearns quarterly dividend)"
REGIONAL = "Earnings release prose, SEC 8-K EX-99 (2005-2008)"
WINDOW_WORDS, LAST_WINDOW_WORDS = 310, 150


def described(rows, start):
    return [r for r in rows if r["description"].startswith(start)]


def one(rows, start, first_words="", url_end=""):
    """The single row whose description, first words and source URL start or end as given."""
    found = [
        r
        for r in described(rows, start)
        if r["first_words"].startswith(first_words) and (r["source_url"] or "").endswith(url_end)
    ]
    assert len(found) == 1, (start, first_words, len(found))
    return found[0]


def edit(data, wording):
    return one(data["edited_copies"], "Lehman Q2 2007 earnings release. " + wording)


def span(values, fmt=short):
    return f"{fmt(min(values))} to {fmt(max(values))}"


def source_of(row):
    """Which release a Lehman or Bear Stearns scan was cut from."""
    if row["description"].startswith(DIVIDENDS):
        return "Bear Stearns dividend releases"
    for quarter, page in (("Q2 2007", "2_07qe.htm"), ("Q2 2008", "2_08qe.htm")):
        if quarter in row["description"] or row["source_url"].endswith(page):
            return f"Lehman {quarter}"
    return row["description"]


def windows(row):
    """Mean sentence score of each run of whole sentences reaching 310 words (a last run of 150+ words counts)."""
    out, cur, words = [], [], 0
    for s in row["gptzero"]["sentences"]:
        cur.append(s["p_ai"])
        words += len(s["text"].split())
        if words >= WINDOW_WORDS:
            out.append(sum(cur) / len(cur))
            cur, words = [], 0
    if cur and words >= LAST_WINDOW_WORDS:
        out.append(sum(cur) / len(cur))
    return out


def flat_runs(scores, jump=0.3):
    """Split sentence scores where they jump by more than `jump`; GPTZero scores a window as a block."""
    runs = [[scores[0]]]
    for a, b in zip(scores, scores[1:]):
        if abs(b - a) > jump:
            runs.append([])
        runs[-1].append(b)
    return runs


def search(data):
    h = data["human_scans"]
    years = [int(y) for r in h for y in re.findall(r"(?:19|20)\d\d", str(r["source_date"]))]
    return {
        "human scans": len(h),
        "words in them": f"{sum(r['words'] for r in h):,}",
        "years of the sources": f"{min(years)}-{max(years)}",
        "human scans called AI": sum(map(called_ai, h)),
        "human scans at 75% AI or more": sum(p_ai(r) >= 0.75 for r in h),
    }


def early_guesses(data):
    h = {r["id"]: r for r in data["human_scans"]}
    ai = data["ai_controls"]
    matched = [h[r["matched_to"]] for r in ai]
    genres = [
        r
        for r in data["human_scans"]
        if r["kind"].startswith("Plain web") and not r["description"].startswith(("Google Answers", "Figure-heavy"))
    ]
    warmest = max(
        ((s["p_ai"], s.get("text", "")) for r in matched for s in r["gptzero"]["sentences"]),
        key=lambda x: x[0],
    )
    return {
        "AI texts written by Qwen3-14B": len(ai),
        "of them called AI": sum(map(called_ai, ai)),
        "human texts they match": len(matched),
        "human texts called AI": sum(map(called_ai, matched)),
        "guessed predictable genres scanned": len(genres),
        "of them called human": sum(not called_ai(r) for r in genres),
        "warmest sentence in the first two guesses": f"{warmest[0]:.2f} ({warmest[1][:45]}...)",
    }


def essays(data, liang_file):
    now = [p_ai(r) for r in data["liang91_rescore"]]
    esl = [r for r in data["human_scans"] if "TOEFL" in r["description"]]
    out = {
        "Liang et al.'s essays": len(now),
        "called AI now": sum(p >= 0.5 for p in now),
        "highest now": f"{max(now):.2g}",
        "ESL essays on TOEFL prompts from 2002": len(esl),
        "of them called AI": sum(map(called_ai, esl)),
        "highest of them": f"{max(map(p_ai, esl)):.1g}",
    }
    if liang_file:
        old = [x["completely_generated_prob"] for x in json.load(open(liang_file))]
        out["called AI in 2023 (0.5 or more)"] = sum(p >= 0.5 for p in old)
        out["0.75 or more in 2023"] = sum(p >= 0.75 for p in old)
    return out


def lehman(data):
    h = data["human_scans"]
    hits = [r for r in h if p_ai(r) >= 0.9995]
    q2_2007 = one(h, "Lehman Q2 2007 earnings release (Wayback page text, unchanged), whole paragraphs")
    q2_2008 = [r for r in described(h, Q2_2008_CUTS) if r["words"] < 700]
    long_cuts = [r for r in described(h, Q2_2008_CUTS) if r["words"] >= 700]
    full = max(long_cuts, key=lambda r: r["words"])
    scores = sorted(map(p_ai, q2_2008), reverse=True)
    lehman_rows = [r for r in h if r["kind"] == LEHMAN]
    return {
        "human texts at 1.0": len(hits),
        "Lehman Q2 2007 cut: words, start": f"{q2_2007['words']}, {q2_2007['first_words'][:21]}",
        "its score": short(p_ai(q2_2007)),
        "Lehman Q2 2008 hit: words, start": ", ".join(
            f"{r['words']}, {r['first_words'][:40]}" for r in hits if r["source_url"].endswith("2_08qe.htm")
        ),
        "whole Q2 2007 page (970 words)": short(
            p_ai(one(h, "pre-2008 earnings release or financial report", url_end="2_07qe.htm"))
        ),
        "full Q2 2008 release text: words, score": f"{full['words']}, {short(p_ai(full))}",
        "Lehman scans": len(lehman_rows),
        "of them called AI": sum(map(called_ai, lehman_rows)),
        "Q2 2008 cuts by starting sentence": len(q2_2008),
        "the two highest": ", ".join(map(short, scores[:2])),
        "the rest": span(scores[2:]),
        "the two 750+ word cuts": ", ".join(short(p_ai(r)) for r in long_cuts),
    }


def windows_and_cliff(data):
    h, e, ai = data["human_scans"], data["edited_copies"], data["ai_controls"]
    driven = "This increase was driven by record debt origination revenues"
    early = [
        one(h, "pre-2008 earnings release or financial report", url_end="2_07qe.htm"),
        one(h, "Lehman quarterly earnings release (Wayback), clean page text, the 9 sentences"),
        one(h, "Lehman quarterly earnings release (Wayback), clean page text, results narrative"),
    ]
    driven_scores = [s["p_ai"] for r in early for s in r["gptzero"]["sentences"] if s["text"].startswith(driven)]
    full = max(described(h, Q2_2008_CUTS), key=lambda r: r["words"])
    runs = flat_runs(sentence_scores(full))
    every = [p_ai(r) for r in h + ai + e]
    exp, ratio = (
        edit(data, "Figures: the previous quarter's expense"),
        edit(data, "Figures: the previous quarter's ratio"),
    )
    return {
        "'This increase was driven...' in three cuts": ", ".join(f"{p:.3f}" for p in sorted(driven_scores)),
        "full Q2 2008 release, sentence runs": "; ".join(f"{min(x):.2f}-{max(x):.2f}" for x in runs),
        "scans in the release (human, AI, edited)": len(every),
        "of them between 0.663 and 0.9999": sum(0.663 < p < 0.9999 for p in every),
        "expense-figure edit: sentence mean, score": f"{sentence_mean(exp):.3f}, {short(p_ai(exp))}",
        "ratio-figure edit: sentence mean, score": f"{sentence_mean(ratio):.3f}, {short(p_ai(ratio))}",
    }


def edits(data):
    h = data["human_scans"]
    wording = described(data["edited_copies"], "Lehman Q2 2007 earnings release. Wording")
    nudges = described(data["edited_copies"], "Lehman Q2 2007 earnings release. Figures: small random")
    q1 = one(h, "Lehman Q1 2007 earnings release (Wayback page text, unchanged), 'Non-interest")
    return {
        "wording edits": len(wording),
        "their scores": ", ".join(short(p_ai(r)) for r in wording),
        "all of the previous quarter's figures": short(p_ai(edit(data, "Figures: all of"))),
        "small random changes to the figures": span([p_ai(r) for r in nudges]),
        "previous quarter's release, as published": short(p_ai(q1)),
        "with this quarter's figures": short(p_ai(edit(data, "The previous quarter's release (Q1 2007) with"))),
        "only the ratio figures, only the capital figures": ", ".join(
            short(p_ai(edit(data, f"Figures: the previous quarter's {k}"))) for k in ("ratio", "capital")
        ),
    }


def other_quarters(data):
    """The metrics section of each Lehman quarter: which quarters reach 0.5."""
    sections = [
        r
        for r in data["human_scans"]
        if r["kind"] == LEHMAN
        and ("metrics section" in r["description"] or "Investment Management through book value" in r["description"])
        and "Wayback" in r["description"]
    ]
    quarter = {r["id"]: re.search(r"Q\d \d{4}", r["description"]).group() for r in sections}
    hot = sorted({quarter[r["id"]] for r in sections if p_ai(r) >= 0.5})
    return {"Lehman quarters with the metrics section scanned": len(set(quarter.values())), "quarters at 0.5+": hot}


def hot_windows(data):
    """Windows of about 310 words in the released human texts (essays left out) with a mean sentence score of 0.5+."""
    reformatted = ("Lehman Q2 2007 earnings release. The 9 warmest", "Lehman Q2 2007 earnings release. Paragraph")
    pool = [r for r in data["human_scans"] if not r["kind"].startswith("Student")]
    pool += [r for r in data["edited_copies"] if r["description"].startswith(reformatted)]
    released = [r for r in pool if r["text_released"]]
    found = [(r, w) for r in released for w in windows(r)]
    hot = [r for r, w in found if w >= 0.5]
    sources = Counter(map(source_of, hot))
    return {
        "windows in released texts": len(found),
        "hot windows": len(hot),
        "they come from": ", ".join(f"{k} ({n})" for k, n in sorted(sources.items())),
        "texts whose windows need the withheld text": len(pool) - len(released),
    }


def near_misses(data):
    h = data["human_scans"]
    div = described(h, DIVIDENDS)
    return {
        "Bear Stearns dividend releases: words": span([r["words"] for r in div], str),
        "scores and labels": ", ".join(f"{p_ai(r):.3f} {r['gptzero']['predicted_class']}" for r in div),
        "regional bank sections of 750+ words scanned": len(described(h, REGIONAL)),
        "highest of them": short(max(p_ai(r) for r in described(h, REGIONAL))),
    }


def second_opinions(data):
    pg = data["pangram_checks"]
    od = data["open_detectors"]
    score = {r["id"]: p_ai(r) for r in data["human_scans"] + data["edited_copies"]}
    hit = [score[r["id"]] >= 0.5 for r in od]
    out = {
        "Pangram checks": len(pg),
        "Pangram verdicts": dict(Counter(r["verdict"] for r in pg)),
        "highest Pangram % AI": max(r["pct_ai"] for r in pg),
        "free detectors: human texts": len(od),
        "GPTZero calls AI": sum(hit),
    }
    for m in DETECTORS:
        flags = sum(r[m] > 0.5 for r in od) / len(od)
        out[f"{m}: flags, AUROC"] = f"{flags:.0%}, {auroc([r[m] for r in od], hit):.2f}"
    return out


SECTIONS = {
    "The search": search,
    "First guesses and the AI check": early_guesses,
    "Essays": essays,
    "Lehman Brothers": lehman,
    "Windows and the score cliff": windows_and_cliff,
    "Words or figures": edits,
    "Lehman's other quarters": other_quarters,
    "Hot windows": hot_windows,
    "Near misses": near_misses,
    "Second opinions": second_opinions,
}


def compute(data, liang_file=None):
    """Return {section: {label: value}} with every number the post states."""
    return {name: (fn(data, liang_file) if fn is essays else fn(data)) for name, fn in SECTIONS.items()}


def render(results):
    """The results as indented text, one number per line."""
    lines = []
    for name, values in results.items():
        lines.append(name)
        lines += [f"  {label.strip()}: {value}" for label, value in values.items()]
    return "\n".join(lines)


def main():
    ap = argparse.ArgumentParser(description="Print every number in the post from the released data.")
    ap.add_argument("--data", default=DEFAULT, help="local data/ folder (default: the Hugging Face copy)")
    ap.add_argument("--liang", help="Liang et al.'s GPTZero.json, for the two 2023 counts")
    a = ap.parse_args()
    print(render(compute(load(a.data), a.liang)))
    if not a.liang:
        print("\n(2023 counts for Liang et al.'s essays need their GPTZero.json: --liang GPTZero.json.)")


if __name__ == "__main__":
    main()
