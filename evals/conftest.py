import os

import pytest


def pytest_collection_modifyitems(config, items):
    """Pula todos os evals quando não há ANTHROPIC_API_KEY (sem chave, sem rede)."""
    if os.environ.get("ANTHROPIC_API_KEY"):
        return
    skip = pytest.mark.skip(reason="evals exigem ANTHROPIC_API_KEY")
    for item in items:
        item.add_marker(skip)
