from click.testing import CliRunner

from poimandres.cli import cli

PRIMARIA = """---
obra: "Corpus Hermeticum"
proveniencia: primaria
ref_base: "CH I"
---
§15 o homem é duplo, mortal pelo corpo
"""


def test_ingest_e_buscar_fim_a_fim(tmp_path, monkeypatch):
    # Usa embeddings Fake p/ não baixar BGE-M3 nos testes.
    import poimandres.cli as climod
    from poimandres.corpus.embeddings import FakeEmbeddings
    monkeypatch.setattr(climod, "_fazer_embeddings", lambda: FakeEmbeddings())

    corpus = tmp_path / "corpus" / "primarias"
    corpus.mkdir(parents=True)
    (corpus / "ch01.md").write_text(PRIMARIA, encoding="utf-8")
    db = str(tmp_path / "c.lance")

    runner = CliRunner()
    r1 = runner.invoke(cli, ["ingest", str(tmp_path / "corpus"), "--db", db])
    assert r1.exit_code == 0, r1.output
    assert "ingeridas 1 passagens" in r1.output

    r2 = runner.invoke(cli, ["buscar", "o homem é duplo", "--db", db])
    assert r2.exit_code == 0, r2.output
    assert "CH I §15" in r2.output


def test_servir_listado_no_help():
    from click.testing import CliRunner

    from poimandres.cli import cli

    res = CliRunner().invoke(cli, ["servir", "--help"])
    assert res.exit_code == 0
    assert "--economico" in res.output
    assert "--opus" in res.output
    assert "--porta" in res.output


def test_perguntar_usa_montar_por_ambiente(tmp_path, monkeypatch):
    from click.testing import CliRunner

    from poimandres import cli as cli_mod
    from poimandres.corpus.embeddings import FakeEmbeddings
    from poimandres.pipeline import fabrica

    class _FinalFake:
        foi_limite = False
        texto = "eis a revelação"
        citacoes = ["ch-i-15"]
        movimentos = []

    class _OraculoFake:
        def consultar(self, buscador, fala):
            return _FinalFake()

    visto = {}

    def fake_por_ambiente(*, store, db_memoria, economico=True, base_url=None):
        visto["economico"] = economico
        return _OraculoFake()

    monkeypatch.setattr(cli_mod, "_fazer_embeddings", lambda: FakeEmbeddings())
    monkeypatch.setattr(fabrica, "montar_por_ambiente", fake_por_ambiente)

    res = CliRunner().invoke(
        cli_mod.cli, ["perguntar", "quem sou?", "--db", str(tmp_path / "c.lance")]
    )
    assert res.exit_code == 0, res.output
    assert "eis a revelação" in res.output
    assert visto["economico"] is True


def test_servir_aceita_host(tmp_path, monkeypatch):
    from click.testing import CliRunner

    from poimandres import cli as cli_mod
    from poimandres.corpus.embeddings import FakeEmbeddings
    from poimandres.pipeline import fabrica

    capturado = {}

    import poimandres.web as web_mod

    monkeypatch.setattr(cli_mod, "_fazer_embeddings", lambda: FakeEmbeddings())
    monkeypatch.setattr(fabrica, "montar_por_ambiente", lambda **kw: object())
    monkeypatch.setattr(web_mod, "criar_app", lambda oraculo: "APP")

    def fake_run(app, host, port):
        capturado["host"] = host
        capturado["port"] = port

    import uvicorn

    monkeypatch.setattr(uvicorn, "run", fake_run)

    res = CliRunner().invoke(
        cli_mod.cli,
        ["servir", "--host", "0.0.0.0", "--porta", "9999", "--db", str(tmp_path / "c.lance")],
    )
    assert res.exit_code == 0, res.output
    assert capturado == {"host": "0.0.0.0", "port": 9999}
