import os
from pathlib import Path

import pytest

_EVALS_DIR = Path(__file__).parent


def pytest_collection_modifyitems(config, items):
    """Pula os evals (e só eles) quando não há ANTHROPIC_API_KEY — sem chave, sem rede."""
    if os.environ.get("ANTHROPIC_API_KEY"):
        return
    skip = pytest.mark.skip(reason="evals exigem ANTHROPIC_API_KEY")
    for item in items:
        if Path(item.fspath).is_relative_to(_EVALS_DIR):
            item.add_marker(skip)
