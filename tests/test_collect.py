"""The collectors give back the dataset's texts from the raw pages in the download cache.

Skipped when the cache ($COLLECT_CACHE, default .cache) is empty: fill it by running the collectors once, online.
"""

import pytest

from collect import check
from collect.fetch import cache_dir


@pytest.fixture(scope="module")
def results(data):
    if not cache_dir().is_dir() or not any(cache_dir().iterdir()):
        pytest.skip(f"no download cache at {cache_dir()}")
    return check.report(data)


@pytest.mark.parametrize("source", ["SEC filings", "Student essays", "Other Wayback pages"])
def test_every_cached_text_is_reproduced(results, source):
    same, total = results[source]
    if total == 0:
        pytest.skip(f"no cached pages for {source}")
    assert same == total


def test_lehman_cuts(results):
    same, total = results["Lehman releases (lehman.com)"]
    if total == 0:
        pytest.skip("no cached Lehman release pages")
    assert same == total
