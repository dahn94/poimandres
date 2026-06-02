from poimandres.pipeline import (
    Afirmacao,
    Discernimento,
    Marca,
    Movimento,
    RascunhoRevelacao,
    Recuperacao,
    RevelacaoFinal,
    Verificacao,
)


def test_discernimento_carrega_marcas_com_incerteza():
    d = Discernimento(
        registro="existencial",
        marcas={"pureza": Marca(valor=0.5, incerteza=0.3)},
        grau=1,
        lingua_ausente=False,
        e_retorno=False,
    )
    assert d.marcas["pureza"].incerteza == 0.3
    assert d.grau == 1


def test_recuperacao_tem_defaults_seguros():
    r = Recuperacao(fundantes=[], iluminantes=[])
    assert r.tensoes == []
    assert r.silencio is False
    assert r.so_tecnico is False


def test_rascunho_declara_afirmacoes_citadas():
    rasc = RascunhoRevelacao(
        texto="...",
        afirmacoes=[Afirmacao(frase="o homem é duplo", citacao_id="ch-i-15")],
    )
    assert rasc.afirmacoes[0].citacao_id == "ch-i-15"
    assert rasc.devolveu is False
    assert rasc.genero_declarado is False


def test_revelacao_final_e_verificacao():
    assert Verificacao(aprovado=True).violacoes == []
    assert RevelacaoFinal(texto="silente").foi_limite is False
    assert Movimento(pedido="observe-se").pedido == "observe-se"
