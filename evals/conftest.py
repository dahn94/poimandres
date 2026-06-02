import os
from pathlib import Path

import pytest

_EVALS_DIR = Path(__file__).parent
_CRED_DIR = Path.home() / ".config" / "anthropic" / "credentials"


def _tem_credencial() -> bool:
    """Há credencial da Anthropic resolvível?

    O SDK aceita ``ANTHROPIC_API_KEY``, ``ANTHROPIC_AUTH_TOKEN`` ou um perfil do
    ``ant auth login`` (OAuth) em ``~/.config/anthropic/credentials``. Os evals só
    devem pular quando NENHUMA delas existe.
    """
    return bool(
        os.environ.get("ANTHROPIC_API_KEY")
        or os.environ.get("ANTHROPIC_AUTH_TOKEN")
        or (_CRED_DIR.is_dir() and any(_CRED_DIR.iterdir()))
    )


def pytest_collection_modifyitems(config, items):
    """Pula os evals (e só eles) quando não há credencial Anthropic — sem credencial, sem rede."""
    if _tem_credencial():
        return
    skip = pytest.mark.skip(
        reason="evals exigem credencial Anthropic (ANTHROPIC_API_KEY ou `ant auth login`)"
    )
    for item in items:
        if Path(item.fspath).is_relative_to(_EVALS_DIR):
            item.add_marker(skip)
