"""Write one AI text per human text with Qwen3-14B (vLLM, thinking off): a brief from the human text, then a new text
of the same kind and length written from the brief alone.

    python3 -m controls.generate HUMAN.jsonl OUT.jsonl

HUMAN.jsonl rows need "id", "text" and "description" (the dataset's description names the kind of text).
Needs a GPU and the generation extra (vllm).
"""

import json
import re
import sys

from vllm import LLM, SamplingParams

KINDS = [
    ("nsf", "an NSF award abstract (the public abstract of a US National Science Foundation grant)"),
    ("federal", "a passage from the executive summary of a US federal government strategy document"),
    ("earnings", "a passage from a US company's quarterly earnings press release or financial report"),
    ("explainer", "a corporate web page that explains a topic to customers or readers"),
    ("corporate web", "a page from a large US company's website (press release, company profile or letter)"),
    ("nepali", "an opinion column, editorial or news report in a Nepali English-language newspaper"),
    ("pib", "a press release from India's Press Information Bureau"),
    ("court", "a passage from the reasoning of an Indian High Court or Supreme Court judgment"),
    ("iosr", "the introduction of a paper in an Indian humanities and social science journal"),
    (
        "digital library",
        "a passage from an Indian English book of speeches, lectures or essays from the early twentieth century",
    ),
]
BRIEF = (
    "Read the text below. Write a brief for a writer who will write a new text of the same kind without seeing this "
    "one. Give: the kind of text and its audience; the topic; and the key facts (names, numbers, dates, claims, "
    "conclusions) as short notes. Do not copy sentences or phrases from the text. Write only the brief."
    "\n\nText:\n{text}"
)
WRITE = (
    "Write {genre}, about {words} words long, using the brief below. Write only the text itself, in plain paragraphs: "
    "no title, no headings, no bullet points, no notes before or after.\n\nBrief:\n{brief}"
)
# The dataset describes this Lehman release as a corporate web page; its AI text was written as an earnings release.
KIND_FIXES = {"lehman_167": "earnings"}
SEED = 20261120
LENGTH_RANGE = (0.6, 1.4)


def kind_of(row):
    d = KIND_FIXES.get(row["id"], row["description"]).lower()
    return next(v for k, v in KINDS if k in d)


def clean(text):
    """Drop think tags, Markdown headings, bullets and a leading title line."""
    text = re.sub(r"</?think>", "", text).strip()
    lines = [x for x in text.splitlines() if not re.match(r"\s*(#+\s|[-*•]\s|\*\*[^*]+\*\*\s*$)", x)]
    paras = [p.strip() for p in re.split(r"\n\s*\n", "\n".join(lines).strip()) if p.strip()]
    if paras and len(paras[0].split()) < 15 and not re.search(r"[.!?]$", paras[0]):
        paras = paras[1:]
    return "\n\n".join(paras)


def main():
    rows = [json.loads(line) for line in open(sys.argv[1], encoding="utf-8")]
    llm = LLM("Qwen/Qwen3-14B", gpu_memory_utilization=0.5, max_model_len=8192, dtype="bfloat16", seed=SEED)

    def chat(prompts, max_tokens):
        params = SamplingParams(temperature=0.7, top_p=0.8, top_k=20, max_tokens=max_tokens)
        messages = [[{"role": "user", "content": p}] for p in prompts]
        outputs = llm.chat(messages, params, chat_template_kwargs={"enable_thinking": False})
        return [o.outputs[0].text for o in outputs]

    def write(indices):
        prompts = [
            WRITE.format(genre=kind_of(rows[i]), words=len(rows[i]["text"].split()), brief=briefs[i]) for i in indices
        ]
        return [clean(t) for t in chat(prompts, 3000)]

    def in_range(i, text):
        ratio = len(text.split()) / len(rows[i]["text"].split())
        return LENGTH_RANGE[0] <= ratio <= LENGTH_RANGE[1]

    briefs = chat([BRIEF.format(text=r["text"]) for r in rows], 1200)
    texts = write(range(len(rows)))
    retry = [i for i in range(len(rows)) if not in_range(i, texts[i])]
    for i, text in zip(retry, write(retry)):
        if in_range(i, text):
            texts[i] = text
    with open(sys.argv[2], "w", encoding="utf-8") as f:
        for i, r in enumerate(rows):
            out = {"matched_to": r["id"], "words": len(texts[i].split()), "length_ok": in_range(i, texts[i])}
            f.write(json.dumps({**out, "brief": briefs[i], "text": texts[i]}) + "\n")
    print(f"{len(rows)} texts, {len(retry)} out of the length range on the first try")


if __name__ == "__main__":
    main()
