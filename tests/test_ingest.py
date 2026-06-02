from poimandres.corpus.embeddings import FakeEmbeddings
from poimandres.corpus.ingest import ingerir_pasta
from poimandres.corpus.store import CorpusStore
from poimandres.domain import Proveniencia

PRIMARIA = """---
obra: "Corpus Hermeticum"
tratado: "I"
proveniencia: primaria
ref_base: "CH I"
---
§15 o homem é duplo
"""

EXCLUIDA = """---
obra: "Kybalion"
proveniencia: excluido
ref_base: "Kyb"
---
§1 o tudo é mente
"""


def _corpus(tmp_path):
    (tmp_path / "primarias").mkdir()
    (tmp_path / "primarias" / "ch01.md").write_text(PRIMARIA, encoding="utf-8")
    (tmp_path / "excluidas").mkdir()
    (tmp_path / "excluidas" / "kyb.md").write_text(EXCLUIDA, encoding="utf-8")
    # estes diretórios devem ser PULADOS neste plano:
    (tmp_path / "tensoes").mkdir()
    (tmp_path / "tensoes" / "heimarmene.md").write_text("pares\n", encoding="utf-8")
    return tmp_path


def test_ingere_conta_passagens_dos_textos(tmp_path):
    corpus = _corpus(tmp_path)
    store = CorpusStore(str(tmp_path / "c.lance"), FakeEmbeddings())
    n = ingerir_pasta(corpus, store)
    assert n == 2  # 1 primária + 1 excluída; tensoes/ é pulado


def test_excluida_vai_para_quarentena_nao_para_fundantes(tmp_path):
    corpus = _corpus(tmp_path)
    store = CorpusStore(str(tmp_path / "c.lance"), FakeEmbeddings())
    ingerir_pasta(corpus, store)
    assert store.buscar_fundantes("mente tudo", k=10) == [] or all(
        r.passagem.proveniencia is Proveniencia.PRIMARIA
        for r in store.buscar_fundantes("mente tudo", k=10)
    )
    assert any(r.passagem.id == "kyb-1" for r in store.reconhecer_excluidas("mente"))
