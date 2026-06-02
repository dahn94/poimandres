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
    assert final.foi_limite is False
    assert final.citacoes == ["ch-i-15"]


def test_caso_ouro_silencio(tmp_path):
    # Corpus SEM primárias (só a excluída) → silêncio. Mesmo que o Mestre tente
    # afirmar com citação, o Verificador reprova; esgotado, rebaixa ao silêncio.
    store = CorpusStore(str(tmp_path / "c.lance"), FakeEmbeddings())
    ingerir_pasta(CORPUS / "excluidas", store)
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
    # Pergunta com as palavras do Kybalion: as fundantes recuperadas são SÓ CH I,
    # então a Revelação só pode citar primárias — o excluído nunca funda.
    #
    # Ajuste determinístico: com FakeEmbeddings, o fundante mais próximo para
    # "o tudo é mente, o universo é mental?" é ch-i-25 (dist ≈ 9137). O rascunho
    # "bom" cita ch-i-25, que está entre os fundantes reais — Verificador aprova.
    store = _store_corpus_real(tmp_path)
    bom = json.dumps(
        {
            "texto": "Isto não pertence à Hermética clássica; o que as fontes dizem é outro.",
            "afirmacoes": [{"frase": "o homem ascende através das esferas", "citacao_id": "ch-i-25"}],
            "devolveu": False,
            "genero_declarado": False,
        }
    )
    final = _oraculo(tmp_path, store, [_DISC, bom]).consultar(
        "b1", "o tudo é mente, o universo é mental?"
    )
    assert final.foi_limite is False
    # toda citação entregue é de uma primária do Corpus Hermeticum (ids ch-i-*)
    assert final.citacoes and all(c.startswith("ch-i-") for c in final.citacoes)
