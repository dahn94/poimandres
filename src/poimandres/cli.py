"""Interface de linha de comando do Poimandres.

Responsabilidade única: expor o corpus ao Curador pela linha de comando. Por ora
esta é a porta de entrada do Curador — quem cuida do corpus — e oferece apenas o
essencial do seu fluxo: ``ingest`` (alimentar o índice a partir da pasta curada)
e ``buscar`` (consultar as passagens fundantes). A camada de oráculo propriamente
dita virá depois; aqui só se cura e se consulta.

O backend de embeddings é obtido por ``_fazer_embeddings`` — um único ponto de
troca, sobrescrito nos testes para o ``FakeEmbeddings`` e assim evitar o download
do modelo BGE-M3.
"""

from __future__ import annotations

from pathlib import Path

import click

from poimandres.corpus.embeddings import EmbeddingsBackend, LocalEmbeddings
from poimandres.corpus.ingest import ingerir_pasta
from poimandres.corpus.store import CorpusStore

# Banco padrão: fica sob ``.poimandres/`` (gitignored), local ao projeto.
_DB_PADRAO = ".poimandres/corpus.lance"


def _fazer_embeddings() -> EmbeddingsBackend:
    """Ponto único de troca do backend de embeddings (sobrescrito nos testes).

    Em produção devolve o ``LocalEmbeddings`` (BGE-M3); nos testes é
    monkeypatchado para o ``FakeEmbeddings``, de modo que nada seja baixado.
    """
    return LocalEmbeddings()


@click.group()
def cli() -> None:
    """Poimandres — curadoria e consulta do corpus hermético."""


@cli.command()
@click.argument(
    "corpus", type=click.Path(exists=True, file_okay=False, path_type=Path)
)
@click.option("--db", default=_DB_PADRAO, show_default=True)
def ingest(corpus: Path, db: str) -> None:
    """Ingere a pasta CORPUS (arquivos Markdown) no vector store.

    Varre CORPUS recursivamente, vetoriza cada passagem encontrada e a persiste
    no índice em ``--db``, preparando o corpus para ser consultado.
    """
    store = CorpusStore(db, _fazer_embeddings())
    n = ingerir_pasta(corpus, store)
    click.echo(f"ingeridas {n} passagens de {corpus}")


@cli.command()
@click.argument("consulta")
@click.option("--db", default=_DB_PADRAO, show_default=True)
@click.option("--k", default=6, show_default=True)
def buscar(consulta: str, db: str, k: int) -> None:
    """Busca passagens FUNDANTES (primárias) semanticamente próximas de CONSULTA.

    Recupera, do índice em ``--db``, as ``--k`` fontes primárias mais próximas da
    CONSULTA — apenas as que têm autoridade para fundar uma resposta.
    """
    store = CorpusStore(db, _fazer_embeddings())
    resultados = store.buscar_fundantes(consulta, k)
    if not resultados:
        click.echo("(o corpus é silente sobre isto)")
        return
    for r in resultados:
        click.echo(f"[{r.passagem.ref_canonica}] {r.passagem.texto[:120]}")


@cli.command()
@click.argument("fala")
@click.option("--buscador", default="anon", show_default=True)
@click.option("--db", default=_DB_PADRAO, show_default=True)
def perguntar(fala: str, buscador: str, db: str) -> None:
    """Conduz um turno do oráculo (Claude real) para a FALA do buscador.

    Requer ``ANTHROPIC_API_KEY`` no ambiente. Usa o índice em ``--db``.
    """
    from poimandres.pipeline.fabrica import montar_oraculo

    store = CorpusStore(db, _fazer_embeddings())
    oraculo = montar_oraculo(store=store, db_memoria=str(Path(db).parent / "estado.db"))
    final = oraculo.consultar(buscador, fala)
    if final.foi_limite:
        click.echo(f"[limite] {final.texto}")
    else:
        click.echo(final.texto)
        for cit in final.citacoes:
            click.echo(f"  — funda em {cit}")
        for mov in final.movimentos:
            click.echo(f"  → {mov}")
