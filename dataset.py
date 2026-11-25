"""Read the released scan data: the data/ folder of the Hugging Face dataset."""

import json
import os
import sys
from pathlib import Path

DEFAULT = Path(os.environ.get("GPTZERO_HUMAN_DATA", "dataset/data"))
FILES = (
    "human_scans",
    "edited_copies",
    "ai_controls",
    "liang91_rescore",
    "pangram_checks",
    "open_detectors",
)
DETECTORS = ("tropa-mini", "tabularisai", "tmr", "vanguard")


def load(folder=DEFAULT):
    """Return {file name: list of rows} for the six dataset files."""
    folder = Path(folder)
    return {name: read_jsonl(folder / f"{name}.jsonl") for name in FILES}


def folder_from_argv():
    """Return the data folder given as the first argument, else the default."""
    return Path(sys.argv[1]) if len(sys.argv) > 1 else DEFAULT


def read_jsonl(path):
    with open(path, encoding="utf-8") as f:
        return [json.loads(line) for line in f]


def p_ai(row):
    return row["gptzero"]["p_ai"]


def called_ai(row):
    """True when GPTZero's predicted class is AI (it can be AI just under 0.5)."""
    return row["gptzero"]["predicted_class"] == "ai"


def sentence_scores(row):
    return [s["p_ai"] for s in row["gptzero"]["sentences"]]


def sentence_mean(row):
    scores = sentence_scores(row)
    return sum(scores) / len(scores)


def auroc(scores, labels):
    """Probability that a positive scores above a negative, ties counted as half."""
    pos = [s for s, y in zip(scores, labels) if y]
    neg = [s for s, y in zip(scores, labels) if not y]
    wins = sum((p > n) + (p == n) / 2 for p in pos for n in neg)
    return wins / (len(pos) * len(neg))


def short(x):
    """An AI probability as the post prints it: two significant figures, 1.0 at the top."""
    return "1.0" if x >= 0.9995 else f"{x:.2g}"
