"""The recomputed numbers and the appendix tables match the post.

recompute.txt is recompute.py's output, checked number by number against the post; appendix.md is the post's
appendix, copied from it.
"""

from pathlib import Path

from recompute import compute, render
from tables import appendix

HERE = Path(__file__).parent
IN_2023 = ("called AI in 2023", "0.75 or more in 2023")


def test_recompute(data, liang_file):
    expected = (HERE / "recompute.txt").read_text().rstrip("\n").splitlines()
    if not liang_file:
        expected = [line for line in expected if not line.strip().startswith(IN_2023)]
    assert render(compute(data, liang_file)).splitlines() == expected


def test_tables(data):
    assert appendix(data) == (HERE / "appendix.md").read_text()
