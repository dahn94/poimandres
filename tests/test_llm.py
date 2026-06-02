import pytest

from poimandres.pipeline.llm import FakeLLM, PedidoLLM


def test_fakellm_devolve_respostas_em_ordem_e_registra_chamadas():
    llm = FakeLLM(["primeira", "segunda"])
    p1 = PedidoLLM(sistema="s", usuario="u1")
    p2 = PedidoLLM(sistema="s", usuario="u2")
    assert llm.gerar(p1) == "primeira"
    assert llm.gerar(p2) == "segunda"
    assert llm.chamadas == [p1, p2]


def test_fakellm_esgotado_falha_alto():
    llm = FakeLLM([])
    with pytest.raises(AssertionError):
        llm.gerar(PedidoLLM(sistema="s", usuario="u"))


def test_pedido_carrega_schema_opcional():
    p = PedidoLLM(sistema="s", usuario="u", schema={"type": "object"})
    assert p.schema == {"type": "object"}


def test_pedido_schema_default_none():
    p = PedidoLLM(sistema="s", usuario="u")
    assert p.schema is None
