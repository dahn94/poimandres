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
