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


def test_oraculo_local_pensa_so_no_compositor(tmp_path, monkeypatch):
    from poimandres.pipeline import fabrica

    construidos = []

    class _FakeLocal:
        def __init__(self, *, base_url, modelo, pensar=False, max_tokens=4096):
            construidos.append({"base_url": base_url, "modelo": modelo, "pensar": pensar})

        def gerar(self, pedido):  # nunca chamado neste teste
            raise AssertionError("não deve gerar")

    monkeypatch.setattr(fabrica, "LocalLLM", _FakeLocal)
    store = CorpusStore(str(tmp_path / "c.lance"), FakeEmbeddings())

    oraculo = fabrica.montar_oraculo_local(
        store=store,
        db_memoria=str(tmp_path / "estado.db"),
        base_url="http://x:8080/v1",
    )
    assert isinstance(oraculo, Oraculo)
    assert [c["pensar"] for c in construidos] == [False, True, False]
    assert all(c["base_url"] == "http://x:8080/v1" for c in construidos)
    assert all(c["modelo"] == "gemma-4-26b-a4b" for c in construidos)
