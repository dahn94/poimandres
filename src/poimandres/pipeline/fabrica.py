"""Fábrica do oráculo — fia os backends de LLM nas 5 unidades do pipeline.

Concentra a injeção de dependência do Plano 2b: Opus 4.8 (a voz do Mestre) no
Compositor; Sonnet 4.6 (rápido, estruturado) no Discernidor e no juiz do
Verificador. ``fazer_llm`` é injetável para que os testes não toquem a rede.
"""

from __future__ import annotations

from collections.abc import Callable

from poimandres.corpus.store import CorpusStore
from poimandres.pipeline.compositor import Compositor
from poimandres.pipeline.discernidor import Discernidor
from poimandres.pipeline.llm import ClaudeLLM, LLMBackend
from poimandres.pipeline.memoria import Memoria
from poimandres.pipeline.orquestrador import Oraculo
from poimandres.pipeline.recuperador import Recuperador
from poimandres.pipeline.verificador import Verificador

_MODELO_MESTRE = "claude-opus-4-8"
_MODELO_RAPIDO = "claude-sonnet-4-6"


def montar_oraculo(
    *,
    store: CorpusStore,
    db_memoria: str,
    fazer_llm: Callable[[str], LLMBackend] = ClaudeLLM,
    max_retries: int = 2,
) -> Oraculo:
    """Constrói um :class:`Oraculo` pronto para responder com Claude.

    Args:
        store: índice do corpus já ingerido.
        db_memoria: caminho do SQLite de estado.
        fazer_llm: fábrica de backend por modelo (injetável nos testes).
        max_retries: tentativas do Compositor antes do limite honesto.
    """
    return Oraculo(
        discernidor=Discernidor(fazer_llm(_MODELO_RAPIDO)),
        recuperador=Recuperador(store),
        compositor=Compositor(fazer_llm(_MODELO_MESTRE)),
        verificador=Verificador(juiz=fazer_llm(_MODELO_RAPIDO)),
        memoria=Memoria(db_memoria),
        max_retries=max_retries,
    )
