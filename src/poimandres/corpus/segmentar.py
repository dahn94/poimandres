"""Segmentação do *corpo* de um arquivo em passagens numeradas.

Responsabilidade única: quebrar o corpo de UM arquivo Markdown (o texto abaixo
do frontmatter) em pares ``(numero, texto)``, usando as marcas ``§N`` que abrem
cada passagem. É o passo entre ``parser.parse_texto`` e a criação das
``Passagem``: o parser entrega o corpo bruto, este módulo o fatia.
"""

from __future__ import annotations

import re

# Marca de início de passagem: '§' seguido do número canônico (ex.: '§14', '§9a'),
# obrigatoriamente no início de uma linha (re.MULTILINE).
_MARK_RE = re.compile(r"^§\s*(\d+[a-z]?)\s*", re.MULTILINE)


def segmentar(corpo: str) -> list[tuple[str, str]]:
    """Divide o corpo em pares ``(numero, texto)`` por marcas ``§N`` na linha.

    Cada passagem vai da sua marca até a marca seguinte (ou o fim do corpo).
    Texto antes da primeira marca é ignorado, pois não pertence a passagem
    alguma.

    Args:
        corpo: o corpo do arquivo (texto abaixo do frontmatter).

    Returns:
        Lista de pares ``(numero, texto)`` na ordem em que aparecem.
    """
    secoes: list[tuple[str, str]] = []
    marcas = list(_MARK_RE.finditer(corpo))
    for i, m in enumerate(marcas):
        numero = m.group(1)
        # Texto da passagem = do fim DESTA marca até o início da PRÓXIMA
        # (ou o fim do corpo, na última passagem).
        inicio = m.end()
        fim = marcas[i + 1].start() if i + 1 < len(marcas) else len(corpo)
        texto = corpo[inicio:fim].strip()
        secoes.append((numero, texto))
    return secoes
