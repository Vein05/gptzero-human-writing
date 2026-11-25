"""Send texts to the GPTZero API and save each full response.

    GPTZERO_API_KEY=... python3 -m scan.gptzero TEXTS.jsonl OUT_DIR --model 2026-11-04-base

TEXTS.jsonl rows need "id" and "text". Each response is saved as OUT_DIR/<id>.json; texts with a saved response are
skipped, so a stopped run can be started again. Without --yes it only counts the texts and words it would send.
The post used model version 2026-11-04-base (GPTZero 5.0b).
"""

import argparse
import json
import os
import time
import urllib.request
from pathlib import Path

API = "https://api.gptzero.me/v2/predict/text"
PAUSE_SECONDS = 1.0


def predict(text, model, key):
    """Return GPTZero's JSON response for one text."""
    body = json.dumps({"document": text, "modelVersion": model, "multilingual": False}).encode()
    headers = {"x-api-key": key, "Accept": "application/json", "Content-Type": "application/json"}
    request = urllib.request.Request(API, data=body, headers=headers, method="POST")
    with urllib.request.urlopen(request, timeout=180) as response:
        return json.load(response)


def summary(response):
    doc = response["documents"][0]
    return f"{doc['predicted_class']} p_ai={doc['class_probabilities']['ai']:.4g} ({response.get('version', '')})"


def main():
    ap = argparse.ArgumentParser(description="Scan texts with GPTZero.")
    ap.add_argument("texts", type=Path)
    ap.add_argument("out", type=Path)
    ap.add_argument("--model", required=True, help="GPTZero model version, e.g. 2026-11-04-base")
    ap.add_argument("--yes", action="store_true", help="send the texts (spends API credits)")
    a = ap.parse_args()
    rows = [json.loads(line) for line in open(a.texts, encoding="utf-8")]
    todo = [r for r in rows if not (a.out / f"{r['id']}.json").exists()]
    print(f"{len(rows)} texts, {len(todo)} not scanned, {sum(len(r['text'].split()) for r in todo):,} words to send")
    if not a.yes:
        return
    key = os.environ["GPTZERO_API_KEY"]
    a.out.mkdir(parents=True, exist_ok=True)
    for r in todo:
        response = predict(r["text"], a.model, key)
        (a.out / f"{r['id']}.json").write_text(json.dumps(response))
        print(r["id"], summary(response), flush=True)
        time.sleep(PAUSE_SECONDS)


if __name__ == "__main__":
    main()
