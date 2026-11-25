"""Cut a document into paragraph groups for detectors that read a few hundred words at a time."""

import re

CHUNK_WORDS = 350


def chunks(text):
    """Paragraph groups of at most 350 words (a longer paragraph is a chunk of its own)."""
    paras = [" ".join(p.split()) for p in re.split(r"\n\s*\n", text) if p.strip()]
    out, cur = [], []
    for p in paras:
        if cur and len(" ".join(cur + [p]).split()) > CHUNK_WORDS:
            out.append("\n\n".join(cur))
            cur = []
        cur.append(p)
    if cur:
        out.append("\n\n".join(cur))
    return out
