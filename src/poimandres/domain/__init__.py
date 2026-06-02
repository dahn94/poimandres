"""Modelo de domínio do *corpus* — tipos compartilhados por todo o subsistema.

Define o vocabulário central com que parser, store e busca conversam:

* :class:`Proveniencia` — a autoridade de uma fonte (quem pode FUNDAR, quem só
  ILUMINA, quem fica em QUARENTENA). É a regra de domínio que justifica a
  existência de métodos de busca separados em ``CorpusStore``.
* :class:`Passagem` — a menor unidade pesquisável (um trecho citável).
* :class:`Texto` — um arquivo curado já parseado, com seus metadados e a lista
  de passagens que dele derivam.

Este pacote é puro (sem I/O nem dependências externas): é o contrato estável
sobre o qual os demais módulos se apoiam. Cada tipo vive em seu próprio módulo
e é re-exportado aqui, de modo que os consumidores continuam a importar de
``poimandres.domain`` diretamente (ex.: ``from poimandres.domain import
Passagem``), independentemente de como o domínio for subdividido internamente.
"""

from poimandres.domain.passagem import Passagem
from poimandres.domain.proveniencia import Proveniencia
from poimandres.domain.texto import Texto

__all__ = ["Proveniencia", "Passagem", "Texto"]
