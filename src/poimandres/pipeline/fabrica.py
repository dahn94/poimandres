"""Fábrica do oráculo — fia os backends de LLM nas 5 unidades do pipeline.

Concentra a injeção de dependência do Plano 2b. **Produção:** Opus 4.8 (a voz do
Mestre) no Compositor; Sonnet 4.6 (rápido, estruturado) no Discernidor e no juiz
do Verificador; ``effort`` alto. **Modo econômico** (:func:`montar_oraculo_economico`,
para a fase de afinação de prompts): Sonnet em tudo, ``effort`` baixo e saída
curta — corta o custo ~5-10×, pois Opus + adaptive thinking (tokens de pensamento
contam como saída a $25/1M) é o grande dreator. ``fazer_llm`` é injetável para que
os testes não toquem a rede.
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
    modelo_mestre: str = _MODELO_MESTRE,
    modelo_rapido: str = _MODELO_RAPIDO,
    effort: str = "high",
    max_tokens: int = 8192,
    fazer_llm: Callable[[str], LLMBackend] | None = None,
    max_retries: int = 2,
) -> Oraculo:
    """Constrói um :class:`Oraculo` pronto para responder com Claude.

    Args:
        store: índice do corpus já ingerido.
        db_memoria: caminho do SQLite de estado.
        modelo_mestre: modelo da voz do Mestre (Compositor). Padrão: Opus.
        modelo_rapido: modelo do Discernidor e do juiz. Padrão: Sonnet.
        effort: esforço de raciocínio (``low``|``medium``|``high``|``max``). Padrão
            ``high`` (produção); ``low`` corta drasticamente o custo (afinação).
        max_tokens: teto de tokens por chamada.
        fazer_llm: fábrica de backend por modelo (injetável nos testes). Quando
            ``None``, usa ``ClaudeLLM`` com ``effort``/``max_tokens`` acima.
        max_retries: tentativas do Compositor antes do limite honesto.
    """
    if fazer_llm is None:

        def fazer_llm(modelo: str) -> LLMBackend:
            return ClaudeLLM(modelo, max_tokens=max_tokens, effort=effort)

    return Oraculo(
        discernidor=Discernidor(fazer_llm(modelo_rapido)),
        recuperador=Recuperador(store),
        compositor=Compositor(fazer_llm(modelo_mestre)),
        verificador=Verificador(juiz=fazer_llm(modelo_rapido)),
        memoria=Memoria(db_memoria),
        max_retries=max_retries,
    )


def montar_oraculo_economico(
    *, store: CorpusStore, db_memoria: str, **kwargs
) -> Oraculo:
    """Preset BARATO para a fase de afinação: Sonnet em tudo, effort baixo, saída curta.

    Sem Opus e sem pensamento pesado, corta o custo ~5-10× vs. produção. Use para
    iterar os prompts da Condução; valide a qualidade final com :func:`montar_oraculo`
    (Opus). ``**kwargs`` repassa o resto (ex.: ``fazer_llm`` nos testes, ``max_retries``).
    """
    return montar_oraculo(
        store=store,
        db_memoria=db_memoria,
        modelo_mestre=_MODELO_RAPIDO,
        modelo_rapido=_MODELO_RAPIDO,
        effort="low",
        max_tokens=2048,
        **kwargs,
    )
