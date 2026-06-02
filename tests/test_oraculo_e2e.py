import json
from pathlib import Path

from poimandres.corpus.embeddings import FakeEmbeddings
from poimandres.corpus.ingest import ingerir_pasta
from poimandres.corpus.store import CorpusStore
from poimandres.pipeline.compositor import Compositor
from poimandres.pipeline.discernidor import Discernidor
from poimandres.pipeline.llm import FakeLLM
from poimandres.pipeline.memoria import Memoria
from poimandres.pipeline.orquestrador import Oraculo
from poimandres.pipeline.recuperador import Recuperador
from poimandres.pipeline.verificador import Verificador

CORPUS = Path(__file__).resolve().parents[1] / "corpus"

# Discernimento fixo: valores arbitrários — estes casos-ouro exercitam o
# Verificador/Orquestrador, não o Discernidor.
_DISC = json.dumps(
    {
        "registro": "existencial",
        "marcas": {
            m: {"valor": 0.5, "incerteza": 0.2}
            for m in (
                "reconhecimento_de_si",
                "pureza",
                "reta_intencao",
                "capacidade_de_receber",
            )
        },
        "grau": 1,
        "lingua_ausente": False,
        "e_retorno": False,
    }
)


def _oraculo(tmp_path, store, respostas):
    llm = FakeLLM(respostas)
    return Oraculo(
        discernidor=Discernidor(llm),
        recuperador=Recuperador(store),
        compositor=Compositor(llm),
        verificador=Verificador(),
        memoria=Memoria(str(tmp_path / "estado.db")),
    )


def _store_corpus_real(tmp_path):
    store = CorpusStore(str(tmp_path / "c.lance"), FakeEmbeddings())
    ingerir_pasta(CORPUS, store)
    return store


def test_caso_ouro_contrato_de_citacao(tmp_path):
    # Buscador pergunta sobre o homem duplo; o Mestre tenta citar algo inexistente,
    # o Verificador reprova, e no retry corrige citando uma primária real do corpus.
    store = _store_corpus_real(tmp_path)
    ruim = json.dumps(
        {
            "texto": "x",
            "afirmacoes": [{"frase": "x", "citacao_id": "inventado-99"}],
            "devolveu": False,
            "genero_declarado": False,
        }
    )
    bom = json.dumps(
        {
            "texto": "O homem é duplo.",
            "afirmacoes": [{"frase": "o homem é duplo", "citacao_id": "ch-i-15"}],
            "devolveu": False,
            "genero_declarado": False,
        }
    )
    final = _oraculo(tmp_path, store, [_DISC, ruim, bom]).consultar(
        "b1", "o que é o homem?"
    )
    # (FakeEmbeddings torna a recuperação determinística; com ≤6 primárias, todas entram nas fundantes.)
    assert final.foi_limite is False
    assert final.citacoes == ["ch-i-15"]


def test_caso_ouro_silencio(tmp_path):
    # Corpus SEM primárias (só a excluída) → silêncio. Mesmo que o Mestre tente
    # afirmar com citação, o Verificador reprova; esgotado, rebaixa ao silêncio.
    store = CorpusStore(str(tmp_path / "c.lance"), FakeEmbeddings())
    ingerir_pasta(CORPUS / "excluidas", store)  # só excluídas → nenhuma primária → buscar_fundantes vazio → silencio=True
    afirma = json.dumps(
        {
            "texto": "tento afirmar",
            "afirmacoes": [{"frase": "algo", "citacao_id": "kyb-1"}],
            "devolveu": False,
            "genero_declarado": False,
        }
    )
    final = _oraculo(tmp_path, store, [_DISC, afirma, afirma, afirma]).consultar(
        "b1", "o que ensina o Tudo-mente?"
    )
    assert final.foi_limite is True
    assert "silente" in final.texto.lower()


def test_caso_ouro_recusa_do_excluido(tmp_path):
    # O buscador cita o Kybalion (que ESTÁ no índice, em quarentena). O Mestre
    # tenta fundar nele — e o Verificador REPROVA, porque o excluído jamais entra
    # nas fundantes (buscar_fundantes filtra a proveniência por construção). No
    # retry, o Mestre funda numa primária real do CH e é aprovado.
    store = _store_corpus_real(tmp_path)
    cita_excluido = json.dumps(
        {
            "texto": "O tudo é mente.",
            "afirmacoes": [{"frase": "o tudo é mente", "citacao_id": "kyb-1"}],
            "devolveu": False,
            "genero_declarado": False,
        }
    )
    bom = json.dumps(
        {
            "texto": "Isto não pertence à Hermética clássica; o que as fontes dizem é outro.",
            "afirmacoes": [{"frase": "o homem é duplo", "citacao_id": "ch-i-15"}],
            "devolveu": False,
            "genero_declarado": False,
        }
    )
    final = _oraculo(tmp_path, store, [_DISC, cita_excluido, bom]).consultar(
        "b1", "o tudo é mente, o universo é mental?"
    )
    assert final.foi_limite is False
    # o excluído nunca funda; toda citação entregue é primária do CH (ch-i-*)
    assert "kyb-1" not in final.citacoes
    assert final.citacoes and all(c.startswith("ch-i-") for c in final.citacoes)
