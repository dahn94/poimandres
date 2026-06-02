from poimandres.corpus.segmentar import segmentar


def test_divide_por_marcas():
    corpo = "§14 a beleza da natureza\n§15 o homem é duplo\n§16 mortal pelo corpo"
    secoes = segmentar(corpo)
    assert secoes == [
        ("14", "a beleza da natureza"),
        ("15", "o homem é duplo"),
        ("16", "mortal pelo corpo"),
    ]


def test_ignora_texto_antes_da_primeira_marca():
    corpo = "preâmbulo solto\n§1 começo de fato"
    assert segmentar(corpo) == [("1", "começo de fato")]


def test_aceita_sufixo_de_letra_na_secao():
    corpo = "§9a parte um\n§9b parte dois"
    assert segmentar(corpo) == [("9a", "parte um"), ("9b", "parte dois")]


def test_corpo_sem_marcas_retorna_vazio():
    assert segmentar("texto sem marca alguma") == []
