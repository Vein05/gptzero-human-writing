from collect.text import cut, extend_back, html_lines, page_paragraphs, sentence_starts


def test_page_paragraphs():
    html = b"""<html><head><style>p {}</style><script>var x = 1;</script></head><body>
    <p>Net revenues were
    $1.2 billion<sup>1</sup>, up 5%.</p><p>Second&nbsp;paragraph &amp; more.</p>
    <span>&#169;2000</span>
    <span>&nbsp;&nbsp;</span>
    <a href="/terms.htm">Terms of Use</a></body></html>"""
    assert page_paragraphs(html) == [
        "Net revenues were $1.2 billion1, up 5%.",
        "Second paragraph & more.",
        "©2000",
        "Terms of Use",
    ]


def test_page_paragraphs_windows_1252():
    assert page_paragraphs(b"<p>It\x92s a \x93test\x94.</p>") == ["It’s a “test”."]


def test_html_lines():
    html = "<p>Share<sup>7</sup>, up.</p><table><tr><td>Revenue</td><td>$5</td></tr></table><!-- note -->"
    assert html_lines(html) == ["", "Share7, up.", "", "", "Revenue | $5 |", "", ""]
    assert html_lines(html, cells=" ")[4] == "Revenue $5"


TEXT = "First one. Second sentence here! Third: is it? Mr. Smith said so. The end."


def test_sentence_starts():
    starts = sentence_starts(TEXT)
    assert [TEXT[s : s + 6] for s in starts] == ["First ", "Second", "Third:", "Mr. Sm", "Smith ", "The en"]


def test_cut_extends_to_whole_sentences():
    assert cut(TEXT, 0, min_words=3) == "First one. Second sentence here!"
    assert cut(TEXT, TEXT.find("Third"), min_words=1) == "Third: is it?"
    assert cut(TEXT, 0, min_words=100) is None


def test_extend_back():
    end = len(TEXT)
    start = TEXT.find("The end")
    assert extend_back(TEXT, start, end, min_words=2) == "The end."
    assert extend_back(TEXT, start, end, min_words=5) == "Smith said so. The end."
