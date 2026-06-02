"""Modelo de domínio do *corpus* — tipos compartilhados por todo o subsistema.

Define o vocabulário central com que parser, store e busca conversam:

* :class:`Proveniencia` — a autoridade de uma fonte (quem pode FUNDAR, quem só
  ILUMINA, quem fica em QUARENTENA). É a regra de domínio que justifica a
  existência de métodos de busca separados em ``CorpusStore``.
* :class:`Passagem` — a menor unidade pesquisável (um trecho citável).
* :class:`Texto` — um arquivo curado já parseado, com seus metadados e a lista
  de passagens que dele derivam.

Este módulo é puro (sem I/O nem dependências externas): é o contrato estável
sobre o qual os demais módulos se apoiam.
"""

from __future__ import annotations

from dataclasses import dataclass
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


@dataclass(frozen=True)
class Passagem:
    """Menor unidade pesquisável do corpus: um trecho citável de um ``Texto``.

    Imutável (``frozen``) porque, uma vez extraída de um arquivo curado, uma
    passagem é uma citação fixa — identidade e texto não mudam.

    Campos:
        id: identificador estável (slug derivado de ``ref_base`` + número).
        ref_canonica: referência citável legível (ex.: ``"CH I §14"``).
        texto: o trecho em si.
        proveniencia: autoridade herdada do ``Texto`` de origem.
        obra: a obra a que pertence (ex.: ``"Corpus Hermeticum"``).
        tratado: subdivisão da obra, se houver.
    """

    id: str
    ref_canonica: str
    texto: str
    proveniencia: Proveniencia
    obra: str
    tratado: str | None = None


@dataclass
class Texto:
    """Um arquivo curado do corpus, já parseado em metadados + passagens.

    Corresponde a um arquivo Markdown da pasta ``corpus/`` (ver
    ``poimandres.corpus.parser.parse_texto``): o frontmatter vira os metadados
    abaixo e o corpo é segmentado na lista de ``passagens``.

    Campos:
        obra: a obra (ex.: ``"Corpus Hermeticum"``).
        tratado: subdivisão da obra, se houver.
        proveniencia: autoridade aplicada a todas as suas passagens.
        autor_ou_tradutor: responsável pela versão do texto.
        idioma: idioma do texto.
        ref_base: prefixo das referências canônicas das passagens.
        passagens: as passagens extraídas do corpo.
    """

    obra: str
    tratado: str | None
    proveniencia: Proveniencia
    autor_ou_tradutor: str
    idioma: str
    ref_base: str
    passagens: list[Passagem]
