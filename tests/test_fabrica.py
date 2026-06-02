from poimandres.corpus.embeddings import FakeEmbeddings
from poimandres.corpus.store import CorpusStore
from poimandres.pipeline.fabrica import montar_oraculo, montar_oraculo_economico
from poimandres.pipeline.llm import FakeLLM
from poimandres.pipeline.orquestrador import Oraculo


def test_monta_oraculo_com_backend_injetado(tmp_path):
    store = CorpusStore(str(tmp_path / "c.lance"), FakeEmbeddings())
    criados = []

    def fazer_llm(modelo):
        criados.append(modelo)
        return FakeLLM([])

    oraculo = montar_oraculo(
        store=store,
        db_memoria=str(tmp_path / "estado.db"),
        fazer_llm=fazer_llm,
    )
    assert isinstance(oraculo, Oraculo)
    assert criados == ["claude-sonnet-4-6", "claude-opus-4-8", "claude-sonnet-4-6"]


def test_oraculo_economico_usa_sonnet_em_tudo(tmp_path):
    store = CorpusStore(str(tmp_path / "c.lance"), FakeEmbeddings())
    criados = []

    def fazer_llm(modelo):
        criados.append(modelo)
        return FakeLLM([])

    oraculo = montar_oraculo_economico(
        store=store,
        db_memoria=str(tmp_path / "estado.db"),
        fazer_llm=fazer_llm,
    )
    assert isinstance(oraculo, Oraculo)
    # modo econômico: Sonnet também na voz do Mestre (sem Opus)
    assert criados == ["claude-sonnet-4-6", "claude-sonnet-4-6", "claude-sonnet-4-6"]
