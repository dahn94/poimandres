from __future__ import annotations

import re

_MARK_RE = re.compile(r"^§\s*(\d+[a-z]?)\s*", re.MULTILINE)


def segmentar(corpo: str) -> list[tuple[str, str]]:
    """Divide o corpo em pares (numero, texto) por marcas '§N' no início da linha.

    Texto antes da primeira marca é ignorado.
    """
    secoes: list[tuple[str, str]] = []
    marcas = list(_MARK_RE.finditer(corpo))
    for i, m in enumerate(marcas):
        numero = m.group(1)
        inicio = m.end()
        fim = marcas[i + 1].start() if i + 1 < len(marcas) else len(corpo)
        texto = corpo[inicio:fim].strip()
        secoes.append((numero, texto))
    return secoes
