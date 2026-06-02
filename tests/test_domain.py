from poimandres.domain import Proveniencia


def test_so_primaria_funda():
    assert Proveniencia.PRIMARIA.pode_fundar is True
    for p in (Proveniencia.TECNICA, Proveniencia.TESTEMUNHO,
              Proveniencia.ERUDICAO, Proveniencia.EXCLUIDO):
        assert p.pode_fundar is False


def test_iluminam_erudicao_e_testemunho():
    assert Proveniencia.ERUDICAO.pode_iluminar is True
    assert Proveniencia.TESTEMUNHO.pode_iluminar is True
    assert Proveniencia.PRIMARIA.pode_iluminar is False
    assert Proveniencia.EXCLUIDO.pode_iluminar is False


def test_so_excluido_em_quarentena():
    assert Proveniencia.EXCLUIDO.em_quarentena is True
    assert Proveniencia.PRIMARIA.em_quarentena is False


def test_valor_serializa_em_string():
    assert Proveniencia.PRIMARIA.value == "primaria"
    assert Proveniencia("erudicao") is Proveniencia.ERUDICAO


from poimandres.domain import Passagem, Texto


def test_passagem_e_imutavel_e_carrega_proveniencia():
    p = Passagem(
        id="ch-i-15",
        ref_canonica="CH I §15",
        texto="o homem é duplo",
        proveniencia=Proveniencia.PRIMARIA,
        obra="Corpus Hermeticum",
        tratado="I (Poimandres)",
    )
    assert p.ref_canonica == "CH I §15"
    assert p.proveniencia.pode_fundar is True
    import dataclasses
    try:
        p.texto = "outro"  # type: ignore[misc]
        assert False, "Passagem deveria ser imutável"
    except dataclasses.FrozenInstanceError:
        pass


def test_texto_agrega_passagens():
    p = Passagem("ch-i-15", "CH I §15", "x", Proveniencia.PRIMARIA, "Corpus Hermeticum")
    t = Texto(
        obra="Corpus Hermeticum",
        tratado="I (Poimandres)",
        proveniencia=Proveniencia.PRIMARIA,
        autor_ou_tradutor="Copenhaver 1992",
        idioma="pt",
        ref_base="CH I",
        passagens=[p],
    )
    assert len(t.passagens) == 1
    assert t.passagens[0].id == "ch-i-15"
