import os
from pathlib import Path

import pytest

FIXTURES = Path(__file__).parent / "fixtures"
os.environ.setdefault("TRAINER_DATA_DIR", str(FIXTURES))
os.environ.setdefault("TRAINER_DB", ":memory:")


@pytest.fixture(scope="session")
def fixtures_dir() -> Path:
    return FIXTURES


@pytest.fixture(scope="session")
def spy_1m():
    from backend.data.cache import read_csv_bars
    return read_csv_bars(FIXTURES / "SPY_1m.csv")


@pytest.fixture(scope="session")
def qqq_5m():
    from backend.data.cache import read_csv_bars
    return read_csv_bars(FIXTURES / "QQQ_5m.csv")
