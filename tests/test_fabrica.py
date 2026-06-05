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


def test_endpoint_padrao_por_plataforma(monkeypatch):
    from poimandres.pipeline import fabrica

    monkeypatch.setattr(fabrica.platform, "system", lambda: "Darwin")
    assert fabrica.endpoint_local_padrao() == "http://127.0.0.1:8080/v1"
    monkeypatch.setattr(fabrica.platform, "system", lambda: "Linux")
    assert fabrica.endpoint_local_padrao() == "http://127.0.0.1:8000/v1"


def test_resolver_url_local_precedencia(monkeypatch):
    from poimandres.pipeline import fabrica

    monkeypatch.setattr(fabrica.platform, "system", lambda: "Linux")
    monkeypatch.delenv("POIMANDRES_LOCAL_URL", raising=False)
    assert fabrica.resolver_url_local() == "http://127.0.0.1:8000/v1"

    monkeypatch.setenv("POIMANDRES_LOCAL_URL", "http://env:9/v1")
    assert fabrica.resolver_url_local() == "http://env:9/v1"

    assert fabrica.resolver_url_local("http://arg:1/v1") == "http://arg:1/v1"
