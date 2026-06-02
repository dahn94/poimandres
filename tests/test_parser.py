import pytest

from poimandres.corpus.parser import parse_texto
from poimandres.domain import Proveniencia

ARQUIVO = """---
obra: "Corpus Hermeticum"
tratado: "I (Poimandres)"
proveniencia: primaria
autor_ou_tradutor: "Copenhaver 1992"
idioma: "pt"
ref_base: "CH I"
---
§14 a beleza da natureza
§15 o homem é duplo, mortal pelo corpo
"""


def test_parse_extrai_metadados_e_passagens():
    t = parse_texto(ARQUIVO)
    assert t.obra == "Corpus Hermeticum"
    assert t.proveniencia is Proveniencia.PRIMARIA
    assert len(t.passagens) == 2


def test_passagem_recebe_ref_canonica_e_id():
    t = parse_texto(ARQUIVO)
    p = t.passagens[1]
    assert p.ref_canonica == "CH I §15"
    assert p.id == "ch-i-15"
    assert p.texto == "o homem é duplo, mortal pelo corpo"


def test_passagem_herda_proveniencia_do_texto():
    t = parse_texto(ARQUIVO)
    assert all(p.proveniencia is Proveniencia.PRIMARIA for p in t.passagens)


def test_arquivo_sem_frontmatter_erra():
    with pytest.raises(ValueError, match="frontmatter"):
        parse_texto("§1 sem cabeçalho")
