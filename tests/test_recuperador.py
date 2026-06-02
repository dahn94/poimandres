from poimandres.corpus.embeddings import FakeEmbeddings
from poimandres.corpus.store import CorpusStore
from poimandres.domain import Passagem, Proveniencia
from poimandres.pipeline.recuperador import Recuperador


def _passagem(id, texto, prov, obra):
    return Passagem(
        id=id, ref_canonica=id, texto=texto, proveniencia=prov, obra=obra
    )


def test_recupera_fundantes_e_marca_nao_silencio(tmp_path):
    store = CorpusStore(str(tmp_path / "c.lance"), FakeEmbeddings())
    store.adicionar(
        [_passagem("ch-i-15", "o homem é duplo", Proveniencia.PRIMARIA, "CH")]
    )
    rec = Recuperador(store).recuperar("homem duplo")
    assert any(p.id == "ch-i-15" for p in rec.fundantes)
    assert rec.silencio is False
    assert rec.tensoes == []


def test_sem_primarias_confessa_silencio(tmp_path):
    store = CorpusStore(str(tmp_path / "c.lance"), FakeEmbeddings())
    store.adicionar(
        [_passagem("kyb-1", "o tudo é mente", Proveniencia.EXCLUIDO, "Kyb")]
    )
    rec = Recuperador(store).recuperar("o tudo é mente")
    assert rec.fundantes == []
    assert rec.silencio is True
    assert rec.so_tecnico is False


def test_limiar_estrito_corta_fundantes_distantes(tmp_path):
    store = CorpusStore(str(tmp_path / "c.lance"), FakeEmbeddings())
    store.adicionar(
        [_passagem("ch-i-15", "o homem é duplo", Proveniencia.PRIMARIA, "CH")]
    )
    # limiar negativo: nenhuma distância (>= 0) qualifica → silêncio forçado
    rec = Recuperador(store).recuperar("homem duplo", limiar=-1.0)
    assert rec.fundantes == []
    assert rec.silencio is True


def test_so_tecnico_quando_so_ha_tecnica(tmp_path):
    store = CorpusStore(str(tmp_path / "c.lance"), FakeEmbeddings())
    store.adicionar(
        [_passagem("dec-1", "decano de áries", Proveniencia.TECNICA, "Liber")]
    )
    rec = Recuperador(store).recuperar("decano")
    assert rec.silencio is True
    assert rec.so_tecnico is True
