"""Ingestão recursiva da pasta do corpus para dentro do ``CorpusStore``.

Responsabilidade única: percorrer UMA pasta de corpus, ler cada arquivo Markdown
que carrega texto-de-corpus (com passagens), delegar o parsing a ``parse_texto``
e adicionar as passagens resultantes ao índice. É a ponte entre o sistema de
arquivos curado e o armazenamento consultável; não interpreta conteúdo nem
decide proveniência — isso é trabalho do parser e do domínio.
"""

from __future__ import annotations

from pathlib import Path

from poimandres.corpus.parser import parse_texto
from poimandres.corpus.store import CorpusStore

# Diretórios cujo conteúdo NÃO é texto-de-corpus e por isso são ignorados aqui:
# ``tensoes/`` guarda pares de relação (tensões doutrinárias) e ``glossario/``
# guarda glosas de termos. Nenhum dos dois tem passagens com referência (§) para
# indexar como corpus; eles seguem um modelo de dados próprio, tratado num plano
# posterior. Pulá-los evita que ``parse_texto`` receba arquivos sem frontmatter
# de corpus e mantém este ingestor focado apenas nos textos.
_PULAR = {"tensoes", "glossario"}


def ingerir_pasta(pasta: Path, store: CorpusStore) -> int:
    """Ingere todos os textos-de-corpus de ``pasta`` no ``store``.

    Percorre a pasta recursivamente em ordem determinística (alfabética), de
    modo que a indexação seja reprodutível entre execuções. Para cada arquivo
    ``*.md`` que não esteja sob um diretório de ``_PULAR`` (``tensoes`` ou
    ``glossario`` — ver justificativa na constante), faz o parsing e adiciona
    suas passagens ao índice, propagando a proveniência declarada no frontmatter
    (primárias e excluídas convivem no mesmo índice; o ``store`` é quem as separa
    nas buscas).

    Args:
        pasta: Diretório-raiz do corpus a ser varrido recursivamente.
        store: Índice onde as passagens lidas serão adicionadas.

    Returns:
        O número total de passagens ingeridas em todos os arquivos lidos.
    """
    total = 0
    for arquivo in sorted(pasta.rglob("*.md")):
        partes = arquivo.relative_to(pasta).parts
        if any(p in _PULAR for p in partes):
            continue
        texto = parse_texto(arquivo.read_text(encoding="utf-8"))
        store.adicionar(texto.passagens)
        total += len(texto.passagens)
    return total
