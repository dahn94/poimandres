import json

from poimandres.corpus.embeddings import FakeEmbeddings
from poimandres.corpus.store import CorpusStore
from poimandres.domain import Passagem, Proveniencia
from poimandres.pipeline.compositor import Compositor
from poimandres.pipeline.discernidor import Discernidor
from poimandres.pipeline.llm import FakeLLM
from poimandres.pipeline.memoria import Memoria
from poimandres.pipeline.orquestrador import Oraculo
from poimandres.pipeline.recuperador import Recuperador
from poimandres.pipeline.verificador import Verificador

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
_BOM = json.dumps(
    {
        "texto": "O homem é duplo.",
        "afirmacoes": [{"frase": "o homem é duplo", "citacao_id": "ch-i-15"}],
        "devolveu": False,
        "genero_declarado": False,
    }
)
_RUIM = json.dumps(
    {
        "texto": "invenção",
        "afirmacoes": [{"frase": "invenção", "citacao_id": "nao-existe"}],
        "devolveu": False,
        "genero_declarado": False,
    }
)


def _store(tmp_path):
    store = CorpusStore(str(tmp_path / "c.lance"), FakeEmbeddings())
    store.adicionar(
        [
            Passagem(
                id="ch-i-15",
                ref_canonica="CH I §15",
                texto="o homem é duplo",
                proveniencia=Proveniencia.PRIMARIA,
                obra="Corpus Hermeticum",
            )
        ]
    )
    return store


def _oraculo(tmp_path, respostas, *, max_retries=2):
    llm = FakeLLM(respostas)
    return Oraculo(
        discernidor=Discernidor(llm),
        recuperador=Recuperador(_store(tmp_path)),
        compositor=Compositor(llm),
        verificador=Verificador(),
        memoria=Memoria(str(tmp_path / "estado.db")),
        max_retries=max_retries,
    )


def test_turno_aprovado_de_primeira(tmp_path):
    orac = _oraculo(tmp_path, [_DISC, _BOM])
    final = orac.consultar("b1", "o que sou?")
    assert final.foi_limite is False
    assert final.citacoes == ["ch-i-15"]


def test_reprova_depois_corrige_no_retry(tmp_path):
    orac = _oraculo(tmp_path, [_DISC, _RUIM, _BOM])
    final = orac.consultar("b1", "o que sou?")
    assert final.foi_limite is False
    assert final.citacoes == ["ch-i-15"]


def test_esgota_retries_e_rebaixa_ao_limite(tmp_path):
    orac = _oraculo(tmp_path, [_DISC, _RUIM, _RUIM, _RUIM], max_retries=2)
    final = orac.consultar("b1", "o que sou?")
    assert final.foi_limite is True
    assert len(orac.memoria.ler_turnos("b1")) == 1


def test_turno_e_registrado_na_memoria(tmp_path):
    orac = _oraculo(tmp_path, [_DISC, _BOM])
    orac.consultar("b1", "o que sou?")
    assert len(orac.memoria.ler_turnos("b1")) == 1


def test_revelar_abre_o_grau_da_fundante(tmp_path):
    # opção 1, face 1: o único fato observado num turno revelado é "fundou em
    # ch-i-15" → o assunto dessa fundante vira 'aberto' (tema = citacao_id).
    orac = _oraculo(tmp_path, [_DISC, _BOM])
    orac.consultar("b1", "o que sou?")
    assert orac.memoria.ler_graus("b1") == {"ch-i-15": "aberto"}


def test_limite_nao_abre_grau(tmp_path):
    # rebaixado ao limite (sem citações) → nada foi revelado → nada se abre.
    orac = _oraculo(tmp_path, [_DISC, _RUIM, _RUIM, _RUIM], max_retries=2)
    orac.consultar("b1", "o que sou?")
    assert orac.memoria.ler_graus("b1") == {}


def test_retorno_nao_promove_a_integrado(tmp_path):
    # opção 1, face 2 (o invariante): 'integrado' é adiado. Voltar e reabrir o
    # mesmo assunto NÃO o marca integrado — só o vivido (lei nº3) seria, e o
    # pipeline não observa isso. Permanece 'aberto'.
    orac = _oraculo(tmp_path, [_DISC, _BOM, _DISC, _BOM])
    orac.consultar("b1", "o que sou?")
    orac.consultar("b1", "o que sou?")
    assert orac.memoria.ler_graus("b1") == {"ch-i-15": "aberto"}


def test_compositor_recebe_historico_dos_turnos_anteriores(tmp_path):
    # o loop: no 2º turno, o diálogo do 1º (fala + Revelação) entra no pedido
    # do Compositor — para o Mestre não re-sondar nem repetir.
    llm = FakeLLM([_DISC, _BOM, _DISC, _BOM])
    orac = Oraculo(
        discernidor=Discernidor(llm),
        recuperador=Recuperador(_store(tmp_path)),
        compositor=Compositor(llm),
        verificador=Verificador(),
        memoria=Memoria(str(tmp_path / "estado.db")),
    )
    orac.consultar("b1", "o que sou?")
    orac.consultar("b1", "e depois da morte?")
    # último pedido = Compositor do 2º turno
    usuario = llm.chamadas[-1].usuario
    assert "DIÁLOGO ATÉ AQUI" in usuario
    assert "o que sou?" in usuario


def test_devolucao_surfaca_movimentos(tmp_path):
    devolve = json.dumps(
        {
            "texto": "Antes de responder: o que você já entregou ao buscar isto?",
            "afirmacoes": [],
            "movimentos": ["observe o que move sua pergunta"],
            "devolveu": True,
            "genero_declarado": False,
        }
    )
    orac = _oraculo(tmp_path, [_DISC, devolve])
    final = orac.consultar("b1", "o que é a gnose?")
    assert final.foi_limite is False
    assert final.movimentos == ["observe o que move sua pergunta"]
    assert final.citacoes == []
