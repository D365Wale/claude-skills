import pathlib
import sys

import pytest

sys.path.insert(0, str(pathlib.Path(__file__).resolve().parents[1]))

FIXTURES = pathlib.Path(__file__).parent / "fixtures"


@pytest.fixture
def sample_edmx() -> str:
    return (FIXTURES / "sample_edmx.xml").read_text()
