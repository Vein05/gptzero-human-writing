"""Score whole documents with six open detectors, each with its official code or model-card recipe.

    python3 -m controls.detectors TEXTS.jsonl OUT.json

  binoculars   Binoculars (github.com/ahans30/Binoculars, binoculars/metrics.py): observer Falcon-7B, performer
               Falcon-7B-Instruct, bf16. Lower means more AI; flagged below the repository's low false-positive
               threshold.
  fastdetect   Fast-DetectGPT (github.com/baoguangsheng/fast-detect-gpt, get_sampling_discrepancy_analytic): sampling
               model Falcon-7B, scoring model Falcon-7B-Instruct; probability from the repository's fitted normals.
  radar        TrustSafeAI/RADAR-Vicuna-7B, p(AI) = softmax index 0.
  desklib      desklib/ai-text-detector-v1.01, the model card's class, sigmoid, at most 768 tokens.
  fakespot     fakespot-ai/roberta-base-ai-text-detection-v1, label "AI", the model card's clean_text.
  openai       openai-community/roberta-large-openai-detector, index 0 ("fake"), at most 512 tokens.

Each document is cut at paragraph breaks into chunks of at most 350 words; its score is the word-weighted mean of the
chunk scores. TEXTS.jsonl rows need "id" and "text". Set BINOCULARS_REPO and FAST_DETECT_GPT_REPO to clones of the
two repositories. Needs a CUDA GPU and the detectors extra.
"""

import json
import os
import re
import sys
from html import unescape

import torch
import torch.nn as nn
from scipy.stats import norm
from transformers import (
    AutoConfig,
    AutoModel,
    AutoModelForCausalLM,
    AutoModelForSequenceClassification,
    AutoTokenizer,
    PreTrainedModel,
)

from controls.chunks import chunks

sys.path[:0] = [os.environ["BINOCULARS_REPO"], os.path.join(os.environ["FAST_DETECT_GPT_REPO"], "scripts")]
from binoculars.metrics import entropy, perplexity  # noqa: E402
from fast_detect_gpt import get_sampling_discrepancy_analytic  # noqa: E402

BINOCULARS_THRESHOLD = 0.8536432310785527
FAST_DETECT_NORMALS = {"mu0": -0.0707, "sigma0": 0.9520, "mu1": 2.9306, "sigma1": 1.9039}
DEVICE = "cuda"
CLASSIFIERS = ("radar", "desklib", "fakespot", "openai")
torch.set_grad_enabled(False)


class Falcon:
    """Binoculars and Fast-DetectGPT share the Falcon-7B pair."""

    def __init__(self):
        kw = {"device_map": {"": DEVICE}, "torch_dtype": torch.bfloat16}
        self.observer = AutoModelForCausalLM.from_pretrained("tiiuae/falcon-7b", **kw).eval()
        self.performer = AutoModelForCausalLM.from_pretrained("tiiuae/falcon-7b-instruct", **kw).eval()
        self.tok = AutoTokenizer.from_pretrained("tiiuae/falcon-7b")
        self.tok.pad_token = self.tok.pad_token or self.tok.eos_token

    def score(self, text):
        enc = self.tok([text], return_tensors="pt", truncation=True, max_length=2048, return_token_type_ids=False)
        enc = enc.to(DEVICE)
        lo, lp = self.observer(**enc).logits, self.performer(**enc).logits
        bino = float(perplexity(enc, lp)[0] / entropy(lo, lp, enc, self.tok.pad_token_id)[0])
        crit = get_sampling_discrepancy_analytic(lo[:, :-1].float(), lp[:, :-1].float(), enc.input_ids[:, 1:])
        n = FAST_DETECT_NORMALS
        p0, p1 = norm.pdf(crit, n["mu0"], n["sigma0"]), norm.pdf(crit, n["mu1"], n["sigma1"])
        return {"binoculars": bino, "fastdetect": float(p1 / (p0 + p1))}


class Desklib(PreTrainedModel):
    """The model card's class: mean-pooled DeBERTa with one logit."""

    config_class = AutoConfig

    def __init__(self, config):
        super().__init__(config)
        self.model = AutoModel.from_config(config)
        self.classifier = nn.Linear(config.hidden_size, 1)
        self.init_weights()

    def forward(self, input_ids, attention_mask=None):
        h = self.model(input_ids, attention_mask=attention_mask)[0]
        m = attention_mask.unsqueeze(-1).expand(h.size()).float()
        return {"logits": self.classifier((h * m).sum(1) / torch.clamp(m.sum(1), min=1e-9))}


def fakespot_clean(t):
    """The parts of the model card's clean_text that apply to plain text."""
    t = unescape(re.sub(r"<.*?>", "", re.sub(r"#+ ", "", t)))
    for c in ("\n", "\t", "\r"):
        t = t.replace(c, " ")
    return re.sub(" +", " ", t.replace(" ,", ",")).strip()


REPOS = {
    "radar": "TrustSafeAI/RADAR-Vicuna-7B",
    "desklib": "desklib/ai-text-detector-v1.01",
    "fakespot": "fakespot-ai/roberta-base-ai-text-detection-v1",
    "openai": "openai-community/roberta-large-openai-detector",
}


def classifier(name):
    """Return a function from text to p(AI) for one of the four classifiers."""
    tok = AutoTokenizer.from_pretrained(REPOS[name])
    model = (Desklib if name == "desklib" else AutoModelForSequenceClassification).from_pretrained(REPOS[name])
    model = model.to(DEVICE).eval()
    if name == "desklib":

        def desklib(t):
            enc = tok(t, padding="max_length", truncation=True, max_length=768, return_tensors="pt").to(DEVICE)
            logits = model(input_ids=enc["input_ids"], attention_mask=enc["attention_mask"])["logits"]
            return float(torch.sigmoid(logits).item())

        return desklib
    if name == "fakespot":
        ai_index = {v: k for k, v in model.config.id2label.items()}["AI"]
    else:
        ai_index = 0
    prepare = fakespot_clean if name == "fakespot" else str

    def score(t):
        enc = tok([prepare(t)], truncation=True, max_length=512, return_tensors="pt").to(DEVICE)
        return float(torch.softmax(model(**enc).logits, -1)[0, int(ai_index)])

    return score


def main():
    rows = [json.loads(line) for line in open(sys.argv[1], encoding="utf-8")]
    docs = {r["id"]: chunks(r["text"]) for r in rows}
    found = {i: [{"words": len(c.split())} for c in cs] for i, cs in docs.items()}
    falcon = Falcon()
    for i, cs in docs.items():
        for c, rec in zip(cs, found[i]):
            rec.update(falcon.score(c))
    del falcon
    torch.cuda.empty_cache()
    for name in CLASSIFIERS:
        score = classifier(name)
        for i, cs in docs.items():
            for c, rec in zip(cs, found[i]):
                rec[name] = score(c)
        del score
        torch.cuda.empty_cache()
    out = {}
    for i, cs in found.items():
        words = sum(c["words"] for c in cs)
        doc = {k: sum(c[k] * c["words"] for c in cs) / words for k in ("binoculars", "fastdetect", *CLASSIFIERS)}
        flag = {k: (v < BINOCULARS_THRESHOLD if k == "binoculars" else v > 0.5) for k, v in doc.items()}
        out[i] = {"chunks": cs, "doc": doc, "flag": flag}
    json.dump(out, open(sys.argv[2], "w"), indent=1)
    print(f"{len(out)} documents scored")


if __name__ == "__main__":
    main()
