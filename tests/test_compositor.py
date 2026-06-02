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
