"""Compare detectors on the 118 human texts and the 118 AI texts written to match them.

    python3 -m controls.compare SCORES_DIR [DATA_FOLDER]

SCORES_DIR holds the outputs of controls.detectors and controls.editlens, named {human,ai}_detectors.json and
{human,ai}_editlens_{roberta,llama}.json, keyed by the dataset ids (human_scans ids for the human side, ai_controls
ids for the AI side). GPTZero's scores come from the dataset. For each detector: false positives on the human texts,
AI texts detected, AUROC, AI texts detected at a threshold with no false positive, and false positives by English
variety (US texts against South Asian texts).
"""

import json
import sys
from pathlib import Path

from dataset import DEFAULT, auroc, load

DETECTORS = ("binoculars", "fastdetect", "radar", "desklib", "fakespot", "openai")
EDITLENS = ("roberta", "llama")


def gptzero(row):
    """Score 1 - p(human); a detection is any class other than human (AI or mixed)."""
    g = row["gptzero"]
    return 1 - g["class_probabilities"]["human"], g["predicted_class"] != "human"


def side(folder, name, rows):
    """Return {detector: {id: (score, flagged)}} for one side (human or ai)."""
    found = json.load(open(folder / f"{name}_detectors.json"))
    out = {"gptzero": {r["id"]: gptzero(r) for r in rows}}
    for d in DETECTORS:
        out[d] = {}
        for i, v in found.items():
            score = -v["doc"][d] if d == "binoculars" else v["doc"][d]
            out[d][i] = (score, v["flag"][d])
    for m in EDITLENS:
        docs = json.load(open(folder / f"{name}_editlens_{m}.json"))["docs"]
        out[f"editlens_{m}"] = {i: (v["score"], v["label"] != "human") for i, v in docs.items()}
    return out


def main():
    folder = Path(sys.argv[1])
    data = load(sys.argv[2] if len(sys.argv) > 2 else DEFAULT)
    ai = data["ai_controls"]
    human_rows = {r["id"]: r for r in data["human_scans"]}
    human = [human_rows[r["matched_to"]] for r in ai]
    south_asian = {r["id"] for r in human if r["kind"].startswith("South Asian")}
    h, a = side(folder, "human", human), side(folder, "ai", ai)
    columns = ("false pos.", "detected", "AUROC", "at 0 FP", "FP US", "FP SA")
    print(f"{'detector':18s} " + " ".join(f"{c:>10s}" for c in columns))
    for d in h:
        hs = [h[d][r["id"]] for r in human]
        as_ = [a[d][r["id"]] for r in ai]
        top = max(s for s, _ in hs)
        us = sum(f for r, (_, f) in zip(human, hs) if r["id"] not in south_asian)
        sa = sum(f for r, (_, f) in zip(human, hs) if r["id"] in south_asian)
        scores = [s for s, _ in as_] + [s for s, _ in hs]
        labels = [True] * len(as_) + [False] * len(hs)
        print(
            f"{d:18s} {sum(f for _, f in hs):10d} {sum(f for _, f in as_):10d} {auroc(scores, labels):10.3f} "
            f"{sum(s > top for s, _ in as_):10d} {us:10d} {sa:10d}"
        )
    print(
        f"{len(human)} human texts ({len(human) - len(south_asian)} US, {len(south_asian)} South Asian), {len(ai)} AI"
    )


if __name__ == "__main__":
    main()
