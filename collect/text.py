"""Turn HTML into text, and cut text into stretches of whole sentences.

Two HTML readers are used, as in the original collection: `page_paragraphs` for web pages, where a blank line in the
source also ends a paragraph, and `html_lines` for SEC filings, which keeps each block element on its own line so that
table rows and page breaks can be recognised.
"""

import re
from html import unescape
from html.parser import HTMLParser

LINE_TAGS = r"p|div|br|tr|li|h\d|table|center|hr"
SENTENCE_END = re.compile(r"[.!?](?=\s|$)")


class _Text(HTMLParser):
    BLOCK = {
        "p",
        "br",
        "div",
        "tr",
        "li",
        "h1",
        "h2",
        "h3",
        "h4",
        "h5",
        "table",
        "td",
        "ul",
        "ol",
        "dd",
        "dt",
        "blockquote",
    }
    HIDDEN = {"script", "style", "noscript"}

    def __init__(self):
        super().__init__()
        self.out, self.hidden = [], 0

    def handle_starttag(self, tag, attrs):
        self.hidden += tag in self.HIDDEN
        if tag in self.BLOCK:
            self.out.append("\n\n")

    def handle_endtag(self, tag):
        self.hidden = max(0, self.hidden - (tag in self.HIDDEN))
        if tag in self.BLOCK:
            self.out.append("\n\n")

    def handle_data(self, data):
        if not self.hidden:
            self.out.append(data)


def decode(raw):
    """Bytes to str: UTF-8, else Windows-1252."""
    try:
        return raw.decode("utf-8")
    except UnicodeDecodeError:
        return raw.decode("cp1252", errors="replace")


def page_paragraphs(raw):
    """The visible text of a web page as a list of paragraphs, whitespace inside each collapsed.

    Block elements and blank lines in the source end a paragraph; inline tags add no space.
    """
    parser = _Text()
    parser.feed(decode(raw))
    text = "".join(parser.out).replace("\xa0", " ")
    return [" ".join(p.split()) for p in re.split(r"\n\s*\n", text) if p.strip()]


def html_lines(html, cells=" | "):
    """The text of an HTML filing, one line per block element, with empty lines where blocks meet.

    Whitespace inside a block is collapsed, inline tags add no space ("share<sup>7</sup>," gives "share7,"), and each
    table cell ends with `cells`, so a table row stays on one line.
    """
    t = re.sub(r"(?is)<(script|style).*?</\1>", " ", html)
    t = re.sub(r"(?s)<!--.*?-->", "", t)
    t = re.sub(r"\s+", " ", t)
    t = re.sub(rf"(?i)</?({LINE_TAGS})\b[^>]*>", "\n", t)
    t = re.sub(r"(?i)</t[dh]>", cells, t)
    t = unescape(re.sub(r"<[^>]+>", "", t))
    return [re.sub(r"[ \t\xa0]+", " ", line).strip() for line in t.split("\n")]


def words(text):
    return len(text.split())


def sentence_starts(text):
    """Offsets where sentences begin: the start of the text and after each [.!?] that is followed by a space."""
    starts = []
    for end in [0] + [m.end() for m in SENTENCE_END.finditer(text)]:
        while end < len(text) and text[end].isspace():
            end += 1
        if end < len(text) and (not starts or starts[-1] != end):
            starts.append(end)
    return starts


def cut(text, start, min_words=300):
    """Whole sentences from offset `start` up to the first sentence end that reaches `min_words` words."""
    for m in SENTENCE_END.finditer(text, start):
        if words(text[start : m.end()]) >= min_words:
            return text[start : m.end()]
    return None


def extend_back(text, start, end, min_words=300):
    """text[start:end], with whole sentences added before it until it has `min_words` words."""
    for s in reversed([s for s in sentence_starts(text) if s <= start]):
        if words(text[s:end]) >= min_words:
            return text[s:end]
    return text[:end]
