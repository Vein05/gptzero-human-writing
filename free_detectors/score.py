"""Score texts with four free AI-text detectors from Hugging Face, each as its model card says.

    python3 -m free_detectors.score TEXTS.jsonl OUT.jsonl

  tropa-mini   wasitaigeneratedcom/tropa-mini-ai-text-detector: mean-pooled DeBERTa, four classes (human, ai,
               ai_edited, humanized); AI score = 1 - p(human); at most 768 tokens.
  tabularisai  tabularisai/ai-text-detection: ModernBERT, softmax class 1, NFKC and whitespace normalised; 512 tokens.
  tmr          Oxidane/tmr-ai-text-detector: RoBERTa-base, softmax class 1; 512 tokens.
  vanguard     ShantanuT01/vanguard-ai-text-detector: ModernBERT-large, one logit, sigmoid; 512 tokens.

Only the first tokens of a long text are scored. TEXTS.jsonl rows need "id" and "text"; OUT.jsonl has one row per
text with the four scores, the format of the dataset's open_detectors.jsonl. Runs on CUDA, Apple MPS or CPU
(DEVICE overrides). Needs the detectors extra.
"""

import json
import os
import re
import sys
import unicodedata

import torch
import torch.nn as nn
from transformers import AutoConfig, AutoModel, AutoModelForSequenceClassification, AutoTokenizer, PreTrainedModel

MODELS = {
    "tropa-mini": ("wasitaigeneratedcom/tropa-mini-ai-text-detector", 768),
    "tabularisai": ("tabularisai/ai-text-detection", 512),
    "tmr": ("Oxidane/tmr-ai-text-detector", 512),
    "vanguard": ("ShantanuT01/vanguard-ai-text-detector", 512),
}
BATCH = 8
ZERO_WIDTH = re.compile("[​-‏⁠﻿­]")


def device():
    if os.environ.get("DEVICE"):
        return os.environ["DEVICE"]
    if torch.cuda.is_available():
        return "cuda"
    return "mps" if torch.backends.mps.is_available() else "cpu"


class TropaMini(PreTrainedModel):
    """The model card's class: mean-pooled encoder with a linear head."""

    config_class = AutoConfig
    _tied_weights_keys = []

    @property
    def all_tied_weights_keys(self):
        return {}

    def __init__(self, config):
        super().__init__(config)
        self.model = AutoModel.from_config(config)
        self.classifier = nn.Linear(config.hidden_size, getattr(config, "detector_num_labels", 1))

    def forward(self, input_ids, attention_mask=None, **kw):
        h = self.model(input_ids, attention_mask=attention_mask)[0]
        m = attention_mask.unsqueeze(-1).float()
        return self.classifier((h * m).sum(1) / m.sum(1))


def normalise(text):
    return re.sub(r"\s+", " ", ZERO_WIDTH.sub("", unicodedata.normalize("NFKC", text))).strip()


def score_all(name, texts, dev):
    """Return one AI score per text for one detector."""
    repo, max_length = MODELS[name]
    tok = AutoTokenizer.from_pretrained(repo)
    model = (TropaMini if name == "tropa-mini" else AutoModelForSequenceClassification).from_pretrained(repo)
    model = model.eval().to(dev)
    order = sorted(range(len(texts)), key=lambda i: len(texts[i]))
    scores = [0.0] * len(texts)
    for k in range(0, len(order), BATCH):
        idx = order[k : k + BATCH]
        batch = [normalise(texts[i]) if name == "tabularisai" else texts[i] for i in idx]
        enc = tok(batch, truncation=True, max_length=max_length, padding=True, return_tensors="pt").to(dev)
        with torch.inference_mode():
            if name == "tropa-mini":
                p = 1 - torch.softmax(model(enc["input_ids"], enc["attention_mask"]).float(), -1)[:, 0]
            else:
                logits = model(**enc).logits.float()
                p = torch.sigmoid(logits[:, 0]) if logits.shape[1] == 1 else torch.softmax(logits, -1)[:, 1]
        for i, v in zip(idx, p.cpu().tolist()):
            scores[i] = v
    return scores


def main():
    rows = [json.loads(line) for line in open(sys.argv[1], encoding="utf-8")]
    texts, dev = [r["text"] for r in rows], device()
    found = {name: score_all(name, texts, dev) for name in MODELS}
    with open(sys.argv[2], "w") as f:
        for i, r in enumerate(rows):
            f.write(json.dumps({"id": r["id"], **{name: found[name][i] for name in MODELS}}) + "\n")
    print(f"{len(rows)} texts scored")


if __name__ == "__main__":
    main()
