import json

from poimandres.domain import Passagem, Proveniencia
from poimandres.pipeline.compositor import Compositor
from poimandres.pipeline.llm import FakeLLM
from poimandres.pipeline.tipos import Discernimento, Marca, Recuperacao

_DISC = Discernimento(
    registro="existencial",
    marcas={m: Marca(0.5, 0.2) for m in ("a", "b")},
    grau=1,
    lingua_ausente=False,
    e_retorno=False,
)
_REC = Recuperacao(
    fundantes=[
        Passagem(
            id="ch-i-15",
            ref_canonica="CH I §15",
            texto="o homem é duplo",
            proveniencia=Proveniencia.PRIMARIA,
            obra="Corpus Hermeticum",
        )
    ],
    iluminantes=[],
)
_RESP = json.dumps(
    {
        "texto": "O homem é duplo, mortal e imortal.",
        "afirmacoes": [{"frase": "o homem é duplo", "citacao_id": "ch-i-15"}],
        "devolveu": False,
        "genero_declarado": False,
    }
)


def test_compor_parseia_afirmacoes_citadas():
    llm = FakeLLM([_RESP])
    rasc = Compositor(llm).compor(_DISC, _REC)
    assert rasc.afirmacoes[0].citacao_id == "ch-i-15"
    assert rasc.devolveu is False
    assert "REFAÇA" not in llm.chamadas[0].usuario


def test_retry_inclui_violacoes_no_pedido():
    llm = FakeLLM([_RESP])
    Compositor(llm).compor(_DISC, _REC, violacoes=["citação inexistente: x"])
    assert "citação inexistente: x" in llm.chamadas[0].usuario


def test_compositor_envia_schema_estruturado():
    llm = FakeLLM([_RESP])
    Compositor(llm).compor(_DISC, _REC)
    pedido = llm.chamadas[0]
    assert pedido.schema is not None
    assert "afirmacoes" in pedido.schema["properties"]


def test_compositor_inclui_iluminantes_no_pedido():
    rec = Recuperacao(
        fundantes=_REC.fundantes,
        iluminantes=[
            Passagem(
                id="coment-15",
                ref_canonica="Coment. §15",
                texto="o homem duplo na tradição órfica",
                proveniencia=Proveniencia.ERUDICAO,
                obra="Comentário",
            )
        ],
    )
    llm = FakeLLM([_RESP])
    Compositor(llm).compor(_DISC, rec)
    usuario = llm.chamadas[0].usuario
    assert "ILUMINANTES" in usuario
    assert "coment-15" in usuario


def test_compositor_inclui_historico_no_pedido():
    # o loop: a regra #7 promete "o DIÁLOGO até aqui" — o turno completo
    # (fala do Buscador + Revelação do Mestre) tem de entrar no pedido.
    historico = [
        {
            "fala": "o que sou?",
            "revelacao": "O homem é duplo.",
            "citacoes": ["ch-i-15"],
            "foi_limite": False,
        }
    ]
    llm = FakeLLM([_RESP])
    Compositor(llm).compor(_DISC, _REC, historico=historico)
    usuario = llm.chamadas[0].usuario
    assert "DIÁLOGO" in usuario
    assert "o que sou?" in usuario
    assert "O homem é duplo." in usuario


def test_compositor_sem_historico_nao_anuncia_dialogo():
    # primeiro turno: nada de prometer um diálogo que não existe.
    llm = FakeLLM([_RESP])
    Compositor(llm).compor(_DISC, _REC)
    assert "DIÁLOGO" not in llm.chamadas[0].usuario


def test_compositor_parseia_movimentos():
    resp = json.dumps(
        {
            "texto": "Antes de revelar, observe.",
            "afirmacoes": [],
            "movimentos": ["Quem é você diante disto?"],
            "devolveu": True,
            "genero_declarado": False,
        }
    )
    rasc = Compositor(FakeLLM([resp])).compor(_DISC, _REC)
    assert [m.pedido for m in rasc.movimentos] == ["Quem é você diante disto?"]
    assert rasc.devolveu is True
