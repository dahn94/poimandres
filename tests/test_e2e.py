from pathlib import Path

from poimandres.corpus.embeddings import FakeEmbeddings
from poimandres.corpus.ingest import ingerir_pasta
from poimandres.corpus.store import CorpusStore

CORPUS = Path(__file__).resolve().parents[1] / "corpus"


def test_corpus_de_exemplo_ingere_e_filtra(tmp_path):
    store = CorpusStore(str(tmp_path / "c.lance"), FakeEmbeddings())
    n = ingerir_pasta(CORPUS, store)
    assert n >= 5  # 4 passagens primárias + 1 excluída

    # a pseudo-Hermética jamais funda
    fundantes = store.buscar_fundantes("o tudo é mente universo mental", k=10)
    assert all(r.passagem.obra == "Corpus Hermeticum" for r in fundantes)

    # mas é reconhecível para recusa
    quarentena = store.reconhecer_excluidas("o tudo é mente", k=10)
    assert any(r.passagem.obra == "The Kybalion" for r in quarentena)
