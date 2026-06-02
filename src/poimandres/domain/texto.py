"""O texto — um arquivo curado do corpus já parseado em metadados + passagens."""

from __future__ import annotations

from dataclasses import dataclass

from poimandres.domain.passagem import Passagem
from poimandres.domain.proveniencia import Proveniencia


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
