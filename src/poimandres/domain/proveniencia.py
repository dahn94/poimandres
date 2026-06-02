"""A proveniência — a hierarquia de autoridade de uma fonte hermética.

Esta é a regra de domínio mais fundamental do oráculo, isolada num módulo
próprio: é ela que justifica a existência de métodos de busca separados em
``CorpusStore`` (cada papel de autoridade tem sua própria consulta).
"""

from __future__ import annotations

from enum import Enum


class Proveniencia(Enum):
    """Hierarquia de autoridade de uma fonte hermética.

    O oráculo nunca trata todas as fontes como iguais. A proveniência codifica
    quanto peso uma passagem pode ter numa resposta:

    * ``PRIMARIA`` — fontes clássicas primárias (Corpus Hermeticum, Asclépio,
      Estobeu, Definições). Só estas podem FUNDAR uma resposta.
    * ``TECNICA`` — hermetismo técnico (astrologia, alquimia, magia antigas).
    * ``TESTEMUNHO`` — testemunhos antigos sobre Hermes.
    * ``ERUDICAO`` — estudo moderno; apenas ILUMINA, nunca funda.
    * ``EXCLUIDO`` — pseudo-hermética (Kybalion, Golden Dawn, Teosofia). Fica em
      QUARENTENA: recuperável só para ser reconhecida e recusada.
    """

    PRIMARIA = "primaria"
    TECNICA = "tecnica"
    TESTEMUNHO = "testemunho"
    ERUDICAO = "erudicao"
    EXCLUIDO = "excluido"

    @property
    def pode_fundar(self) -> bool:
        """Se uma fonte desta proveniência pode FUNDAR (alicerçar) uma resposta.

        Verdadeiro só para ``PRIMARIA``: a regra dura do oráculo é que apenas as
        fontes primárias clássicas têm autoridade para sustentar uma afirmação.
        """
        return self is Proveniencia.PRIMARIA

    @property
    def pode_iluminar(self) -> bool:
        """Se uma fonte desta proveniência pode ILUMINAR (contextualizar).

        A erudição moderna e os testemunhos antigos podem enriquecer e situar
        uma resposta, mas nunca fundá-la.
        """
        return self in (Proveniencia.ERUDICAO, Proveniencia.TESTEMUNHO)

    @property
    def em_quarentena(self) -> bool:
        """Se a fonte está em QUARENTENA (pseudo-hermética excluída).

        Conteúdo recuperável apenas para ser reconhecido e recusado, nunca para
        fundar nem iluminar.
        """
        return self is Proveniencia.EXCLUIDO
