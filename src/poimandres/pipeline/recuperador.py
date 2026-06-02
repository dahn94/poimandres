"""② Recuperador — do corpus para a :class:`Recuperacao`, com filtro DURO de autoridade.

Envolve o :class:`~poimandres.corpus.store.CorpusStore` (que já separa as buscas
por proveniência) e deriva os sinais que as unidades seguintes precisam: se
nenhuma primária funda o tema dentro do ``limiar`` de distância, marca
``silencio``; se nesse caso há suporte técnico, marca ``so_tecnico``. A Tensão
foi adiada (Plano 2a), então ``tensoes`` sai sempre vazia — mas o campo já existe.
"""

from __future__ import annotations

from math import inf

from poimandres.corpus.store import CorpusStore, Resultado
from poimandres.pipeline.tipos import Recuperacao


class Recuperador:
    """Recupera do corpus o material de um turno, separado por papel de autoridade."""

    def __init__(self, store: CorpusStore) -> None:
        self._store = store

    def recuperar(
        self,
        consulta: str,
        *,
        k_fundantes: int = 6,
        k_iluminantes: int = 4,
        limiar: float = inf,
    ) -> Recuperacao:
        """Monta a :class:`Recuperacao` para ``consulta``.

        Args:
            consulta: a fala/tema do Buscador.
            k_fundantes: quantas primárias buscar (antes do corte por ``limiar``).
            k_iluminantes: quantas fontes de erudição/testemunho buscar.
            limiar: distância máxima para uma fundante "fundar" de fato; acima
                dela, o corpus é tratado como silente sobre o tema. ``inf`` =
                sem corte (o valor real é afinado no Plano 2b).
        """
        fundantes = self._dentro(self._store.buscar_fundantes(consulta, k_fundantes), limiar)
        iluminantes = [r.passagem for r in self._store.buscar_iluminantes(consulta, k_iluminantes)]
        silencio = not fundantes
        so_tecnico = silencio and bool(self._store.buscar_tecnicas(consulta, k_iluminantes))
        return Recuperacao(
            fundantes=fundantes,
            iluminantes=iluminantes,
            tensoes=[],
            silencio=silencio,
            so_tecnico=so_tecnico,
        )

    @staticmethod
    def _dentro(resultados: list[Resultado], limiar: float) -> list:
        """Passagens cuja distância à consulta não excede o ``limiar``."""
        return [r.passagem for r in resultados if r.distancia <= limiar]
