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
