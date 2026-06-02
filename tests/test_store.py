import pytest

from poimandres.corpus.embeddings import FakeEmbeddings
from poimandres.corpus.store import CorpusStore
from poimandres.domain import Passagem, Proveniencia


def _p(id, texto, prov):
    return Passagem(id, id.upper(), texto, prov, "Obra")


@pytest.fixture
def store(tmp_path):
    s = CorpusStore(str(tmp_path / "c.lance"), FakeEmbeddings())
    s.adicionar([
        _p("a1", "o nous é livre da heimarmene", Proveniencia.PRIMARIA),
        _p("a2", "o destino tece o corpo pelas esferas", Proveniencia.PRIMARIA),
        _p("e1", "fowden comenta o fatalismo astrológico", Proveniencia.ERUDICAO),
        _p("x1", "a lei da atração e o mentalismo do kybalion", Proveniencia.EXCLUIDO),
    ])
    return s


def test_fundantes_so_trazem_primarias(store):
    res = store.buscar_fundantes("heimarmene destino", k=10)
    assert res, "deveria achar primárias"
    assert all(r.passagem.proveniencia is Proveniencia.PRIMARIA for r in res)


def test_iluminantes_nao_trazem_primarias_nem_excluidas(store):
    res = store.buscar_iluminantes("fatalismo", k=10)
    assert all(r.passagem.proveniencia is Proveniencia.ERUDICAO for r in res)


def test_excluidas_nunca_aparecem_nas_fundantes(store):
    res = store.buscar_fundantes("kybalion lei da atração mentalismo", k=10)
    assert all(r.passagem.id != "x1" for r in res)


def test_reconhecer_excluidas_so_traz_quarentena(store):
    res = store.reconhecer_excluidas("kybalion", k=10)
    assert all(r.passagem.proveniencia is Proveniencia.EXCLUIDO for r in res)


def test_busca_em_store_vazio_retorna_lista_vazia(tmp_path):
    s = CorpusStore(str(tmp_path / "vazio.lance"), FakeEmbeddings())
    assert s.buscar_fundantes("qualquer") == []
