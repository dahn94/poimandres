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

import os
import platform
from collections.abc import Callable

from poimandres.corpus.store import CorpusStore
from poimandres.pipeline.compositor import Compositor
from poimandres.pipeline.discernidor import Discernidor
from poimandres.pipeline.llm import ClaudeLLM, LLMBackend, LocalLLM
from poimandres.pipeline.memoria import Memoria
from poimandres.pipeline.orquestrador import Oraculo
from poimandres.pipeline.recuperador import Recuperador
from poimandres.pipeline.verificador import Verificador

_MODELO_MESTRE = "claude-opus-4-8"
_MODELO_RAPIDO = "claude-sonnet-4-6"
_MODELO_LOCAL = "gemma-4-26b-a4b"


def endpoint_local_padrao() -> str:
    """URL default do servidor local por plataforma: Mac→mlx-lm :8080, Linux→vLLM :8000."""
    if platform.system() == "Darwin":
        return "http://127.0.0.1:8080/v1"
    return "http://127.0.0.1:8000/v1"


def resolver_url_local(base_url: str | None = None) -> str:
    """Precedência: argumento explícito > ``POIMANDRES_LOCAL_URL`` > default por plataforma."""
    return base_url or os.environ.get("POIMANDRES_LOCAL_URL") or endpoint_local_padrao()


def montar_oraculo(
    *,
    store: CorpusStore,
    db_memoria: str,
    modelo_mestre: str = _MODELO_MESTRE,
    modelo_rapido: str = _MODELO_RAPIDO,
    effort: str = "high",
    max_tokens: int = 8192,
    limiar: float = 1.15,
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
        limiar: distância máxima (BGE-M3) para uma primária fundar; acima dela o
            tema é tratado como silente. ~1.15 separa relevante (≲1.0) de
            fora-do-tema (≳1.33).
        fazer_llm: fábrica de backend por modelo (injetável nos testes). Quando
            ``None``, usa ``ClaudeLLM`` com ``effort``/``max_tokens`` acima.
        max_retries: tentativas do Compositor antes do limite honesto.
    """
    if fazer_llm is None:

        def fazer_llm(modelo: str) -> LLMBackend:
            return ClaudeLLM(modelo, max_tokens=max_tokens, effort=effort)

    return Oraculo(
        discernidor=Discernidor(fazer_llm(modelo_rapido)),
        recuperador=Recuperador(store, limiar=limiar),
        compositor=Compositor(fazer_llm(modelo_mestre)),
        verificador=Verificador(juiz=fazer_llm(modelo_rapido)),
        memoria=Memoria(db_memoria),
        max_retries=max_retries,
    )


def montar_oraculo_local(
    *,
    store: CorpusStore,
    db_memoria: str,
    base_url: str | None = None,
    modelo: str = _MODELO_LOCAL,
    max_tokens: int = 4096,
    **kwargs,
) -> Oraculo:
    """Preset LOCAL: todos os papéis na Gemma 4 (offline, $0). Thinking só no Compositor.

    ``base_url`` resolve por plataforma/env quando ``None`` (ver :func:`resolver_url_local`).
    Os rótulos ``"mestre"``/``"rapido"`` (passados a ``fazer_llm`` pelo ``montar_oraculo``)
    só decidem ``pensar``; o modelo servido é o mesmo ``modelo`` em todos os papéis.
    ``**kwargs`` repassa o resto (ex.: ``max_retries``, ``limiar``).
    """
    url = resolver_url_local(base_url)

    def fazer_llm(papel: str) -> LLMBackend:
        return LocalLLM(
            base_url=url, modelo=modelo, pensar=(papel == "mestre"), max_tokens=max_tokens
        )

    return montar_oraculo(
        store=store,
        db_memoria=db_memoria,
        modelo_mestre="mestre",
        modelo_rapido="rapido",
        fazer_llm=fazer_llm,
        **kwargs,
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


def montar_por_ambiente(
    *,
    store: CorpusStore,
    db_memoria: str,
    economico: bool = True,
    base_url: str | None = None,
) -> Oraculo:
    """Escolhe o backend por ``POIMANDRES_LLM`` (``claude``|``local``; default ``claude``).

    ``local`` → :func:`montar_oraculo_local` (Gemma 4). ``claude`` → preset econômico
    (Sonnet) ou, com ``economico=False``, produção (Opus). Ponto único de toggle que a
    CLI usa, amigável a Docker (só troca env).
    """
    if os.environ.get("POIMANDRES_LLM", "claude").lower() == "local":
        return montar_oraculo_local(store=store, db_memoria=db_memoria, base_url=base_url)
    montar = montar_oraculo_economico if economico else montar_oraculo
    return montar(store=store, db_memoria=db_memoria)
