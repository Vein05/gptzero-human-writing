import os
import sys
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

from dataset import DEFAULT, load  # noqa: E402


@pytest.fixture(scope="session")
def data():
    folder = DEFAULT if DEFAULT.is_absolute() else ROOT / DEFAULT
    if not (folder / "human_scans.jsonl").exists():
        pytest.skip(f"dataset not found at {folder} (set GPTZERO_HUMAN_DATA)")
    return load(folder)


@pytest.fixture(scope="session")
def liang_file():
    """GPTZero.json from Liang et al.'s repository, if $LIANG_GPTZERO_JSON points to it."""
    path = os.environ.get("LIANG_GPTZERO_JSON")
    return path if path and Path(path).exists() else None
