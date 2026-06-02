import json

from poimandres.domain import Passagem, Proveniencia
from poimandres.pipeline.llm import FakeLLM
from poimandres.pipeline.tipos import Afirmacao, RascunhoRevelacao, Recuperacao
from poimandres.pipeline.verificador import Verificador


def _rec(silencio=False, so_tecnico=False):
    fund = (
        []
        if silencio
        else [
            Passagem(
                id="ch-i-15",
                ref_canonica="CH I §15",
                texto="o homem é duplo",
                proveniencia=Proveniencia.PRIMARIA,
                obra="CH",
            )
        ]
    )
    return Recuperacao(
        fundantes=fund, iluminantes=[], silencio=silencio, so_tecnico=so_tecnico
    )


def test_aprova_quando_toda_afirmacao_cita_fundante():
    rasc = RascunhoRevelacao(
        texto="...", afirmacoes=[Afirmacao("o homem é duplo", "ch-i-15")]
    )
    assert Verificador().verificar(rasc, _rec()).aprovado is True


def test_reprova_citacao_inexistente():
    rasc = RascunhoRevelacao(
        texto="...", afirmacoes=[Afirmacao("invenção", "nao-existe")]
    )
    v = Verificador().verificar(rasc, _rec())
    assert v.aprovado is False
    assert any("nao-existe" in viol for viol in v.violacoes)


def test_reprova_afirmacao_em_silencio():
    rasc = RascunhoRevelacao(
        texto="...", afirmacoes=[Afirmacao("algo", "ch-i-15")]
    )
    v = Verificador().verificar(rasc, _rec(silencio=True))
    assert v.aprovado is False
    assert any("silêncio" in viol.lower() for viol in v.violacoes)


def test_aprova_silencio_sem_afirmacoes():
    rasc = RascunhoRevelacao(texto="o corpus é silente sobre isto.")
    assert Verificador().verificar(rasc, _rec(silencio=True)).aprovado is True


def test_reprova_so_tecnico_sem_declarar_genero():
    rasc = RascunhoRevelacao(texto="...", genero_declarado=False)
    v = Verificador().verificar(rasc, _rec(silencio=True, so_tecnico=True))
    assert v.aprovado is False
    assert any("gênero" in viol.lower() for viol in v.violacoes)


def test_juiz_nao_e_chamado_quando_deterministico_ja_reprova():
    llm = FakeLLM([])  # vazio: se for chamado, levanta AssertionError
    rasc = RascunhoRevelacao(texto="x", afirmacoes=[Afirmacao("x", "nao-existe")])
    v = Verificador(juiz=llm).verificar(rasc, _rec())
    assert v.aprovado is False
    assert llm.chamadas == []


def test_juiz_reprova_quando_passagem_nao_sustenta():
    veredito_juiz = json.dumps(
        {"violacoes": ["a passagem ch-i-15 não sustenta 'a alma é tripartite'"]}
    )
    llm = FakeLLM([veredito_juiz])
    rasc = RascunhoRevelacao(
        texto="...", afirmacoes=[Afirmacao("a alma é tripartite", "ch-i-15")]
    )
    v = Verificador(juiz=llm).verificar(rasc, _rec())
    assert v.aprovado is False
    assert any("não sustenta" in viol for viol in v.violacoes)


def test_juiz_aprova_quando_sem_violacoes():
    llm = FakeLLM([json.dumps({"violacoes": []})])
    rasc = RascunhoRevelacao(
        texto="...", afirmacoes=[Afirmacao("o homem é duplo", "ch-i-15")]
    )
    assert Verificador(juiz=llm).verificar(rasc, _rec()).aprovado is True


def test_sem_juiz_mantem_comportamento_2a():
    rasc = RascunhoRevelacao(
        texto="...", afirmacoes=[Afirmacao("o homem é duplo", "ch-i-15")]
    )
    assert Verificador().verificar(rasc, _rec()).aprovado is True
