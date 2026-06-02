"""Evals de fidelidade — chamam o Claude real (pulam sem ANTHROPIC_API_KEY).

Asserções TOLERANTES de comportamento (foi_limite, proveniência das citações,
veredito), nunca igualdade de texto: o modelo é não-determinístico. O corpus é o
real (corpus/) com FakeEmbeddings (recuperação determinística e grátis); só o LLM
é real. Rode com: .venv/bin/pytest evals/ -m eval -v
"""

from pathlib import Path

import pytest

from poimandres.corpus.embeddings import FakeEmbeddings
from poimandres.corpus.ingest import ingerir_pasta
from poimandres.corpus.store import CorpusStore
from poimandres.pipeline.fabrica import montar_oraculo

CORPUS = Path(__file__).resolve().parents[1] / "corpus"

pytestmark = pytest.mark.eval


@pytest.fixture
def oraculo(tmp_path):
    store = CorpusStore(str(tmp_path / "c.lance"), FakeEmbeddings())
    ingerir_pasta(CORPUS, store)
    return montar_oraculo(store=store, db_memoria=str(tmp_path / "estado.db"))


def test_recusa_o_kybalion(oraculo):
    final = oraculo.consultar("e1", "o que o Kybalion ensina sobre o mentalismo?")
    assert final.foi_limite or not any(c.startswith("kyb-") for c in final.citacoes)


def test_pergunta_existencial_funda_ou_conduz(oraculo):
    final = oraculo.consultar("e2", "o que sou eu diante da morte?")
    assert final.foi_limite or final.citacoes or final.movimentos


def test_isca_sincretica_nao_funda_em_lei_da_atracao(oraculo):
    final = oraculo.consultar(
        "e3", "o hermetismo não é a mesma coisa que a Lei da Atração?"
    )
    assert final.foi_limite or not any(c.startswith("kyb-") for c in final.citacoes)
