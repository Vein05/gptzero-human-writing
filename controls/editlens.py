"""Score texts with EditLens (Pangram's released detector), using its own inference code and ternary calibration.

    EDITLENS_REPO=path/to/EditLens python3 -m controls.editlens TEXTS.jsonl OUT.json --model roberta|llama

The thresholds are the repository's F1-optimal ones on Pangram's shipped validation scores (data/val.csv,
scripts/eval/ternary_eval.py). Documents are cut into chunks of at most 350 words at paragraph breaks; the document
score is the word-weighted mean. A first check re-scores 20 validation texts and compares them with the shipped scores.
The post used github.com/pangramlabs/EditLens at commit 05a588f. Needs a GPU, access to the gated pangram/editlens_*
models on Hugging Face, and the detectors extra.
"""

import argparse
import json
import os
import sys
import tempfile

import numpy as np
import pandas as pd

from controls.chunks import chunks

REPO = os.environ["EDITLENS_REPO"]
sys.path[:0] = [os.path.join(REPO, "scripts"), REPO]
from datasets import Dataset  # noqa: E402
from inference import run_inference  # noqa: E402
from scripts.eval.ternary_eval import LABEL_TO_ID, calibrate_thresholds, minmax_scale, orient_scores  # noqa: E402

MODELS = {
    "roberta": ("pangram/editlens_roberta-large", "FacebookAI/roberta-large", 512),
    "llama": ("pangram/editlens_Llama-3.2-3B", "meta-llama/Llama-3.2-3B", 1024),
}
CHECK_ROWS = 20


def score(texts, model):
    """Return EditLens scores for a list of texts."""
    checkpoint, base, max_length = MODELS[model]
    with tempfile.TemporaryDirectory() as tmp:
        Dataset.from_list([{"text": t} for t in texts]).save_to_disk(tmp)
        out = run_inference(checkpoint, base, tmp, text_col="text", max_length=max_length, batch_size=8)
    return list(out[f"editlens_{base.split('/')[-1]}_score"])


def thresholds(val, column):
    """Raw-score thresholds: below `human` is human, above `ai` is AI-generated, between is AI-edited."""
    labels = val["text_type"].map(LABEL_TO_ID).values
    scores, flipped = orient_scores(val[column].values, labels)
    assert not flipped
    lo, hi = scores.min(), scores.max()
    human, ai, _, _ = calibrate_thresholds(labels, minmax_scale(scores))
    return {"human": lo + human * (hi - lo), "ai": lo + ai * (hi - lo)}


def main():
    ap = argparse.ArgumentParser(description="Score texts with EditLens.")
    ap.add_argument("texts")
    ap.add_argument("out")
    ap.add_argument("--model", required=True, choices=MODELS)
    a = ap.parse_args()
    column = f"editlens_{MODELS[a.model][1].split('/')[-1]}_score"
    val = pd.read_csv(os.path.join(REPO, "data", "val.csv"))
    cut = thresholds(val, column)
    check = val.sample(CHECK_ROWS, random_state=0)
    diff = np.abs(np.array(score(list(check["text"]), a.model)) - check[column].values)
    print(f"thresholds {cut}; re-scored validation texts differ by at most {diff.max():.4f}")

    rows = [json.loads(line) for line in open(a.texts, encoding="utf-8")]
    parts = [(r["id"], c) for r in rows for c in chunks(r["text"])]
    scores = score([c for _, c in parts], a.model)
    docs = {}
    for (i, c), s in zip(parts, scores):
        docs.setdefault(i, []).append((len(c.split()), float(s)))
    out = {"model": a.model, "thresholds": cut, "docs": {}}
    for i, cs in docs.items():
        mean = sum(w * s for w, s in cs) / sum(w for w, _ in cs)
        label = "human" if mean < cut["human"] else ("ai_generated" if mean > cut["ai"] else "ai_edited")
        out["docs"][i] = {"score": mean, "label": label}
    json.dump(out, open(a.out, "w"), indent=1)
    print(f"{len(docs)} documents scored")


if __name__ == "__main__":
    main()
