import json

from poimandres.pipeline.discernidor import Discernidor
from poimandres.pipeline.llm import FakeLLM

_RESP = json.dumps(
    {
        "registro": "existencial",
        "marcas": {
            "reconhecimento_de_si": {"valor": 0.6, "incerteza": 0.2},
            "pureza": {"valor": 0.4, "incerteza": 0.3},
            "reta_intencao": {"valor": 0.7, "incerteza": 0.1},
            "capacidade_de_receber": {"valor": 0.5, "incerteza": 0.4},
        },
        "grau": 2,
        "lingua_ausente": True,
        "e_retorno": False,
    }
)


def test_discerne_parseia_saida_estruturada():
    d = Discernidor(FakeLLM([_RESP])).discernir("o que há após a morte?")
    assert d.registro == "existencial"
    assert d.grau == 2
    assert d.lingua_ausente is True
    assert d.marcas["reta_intencao"].valor == 0.7
    assert d.marcas["capacidade_de_receber"].incerteza == 0.4


def test_discernidor_envia_a_fala_ao_llm():
    llm = FakeLLM([_RESP])
    Discernidor(llm).discernir("minha fala")
    assert "minha fala" in llm.chamadas[0].usuario


def test_graus_memoria_entra_no_pedido():
    llm = FakeLLM([_RESP])
    Discernidor(llm).discernir("retorno", graus_memoria={"morte": "aberto"})
    assert "morte" in llm.chamadas[0].usuario


def test_discernidor_envia_schema_estruturado():
    llm = FakeLLM([_RESP])
    Discernidor(llm).discernir("uma fala")
    pedido = llm.chamadas[0]
    assert pedido.schema is not None
    assert pedido.schema["type"] == "object"
    marcas = pedido.schema["properties"]["marcas"]["properties"]
    assert set(marcas) == {
        "reconhecimento_de_si",
        "pureza",
        "reta_intencao",
        "capacidade_de_receber",
    }
