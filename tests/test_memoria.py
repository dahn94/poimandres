from poimandres.pipeline.memoria import Memoria
from poimandres.pipeline.tipos import RevelacaoFinal


def test_registra_turno_e_le_de_volta(tmp_path):
    mem = Memoria(str(tmp_path / "estado.db"))
    final = RevelacaoFinal(texto="o homem é duplo", citacoes=["ch-i-15"])
    mem.registrar_turno("buscador-1", "o que sou?", final)
    turnos = mem.ler_turnos("buscador-1")
    assert len(turnos) == 1
    assert turnos[0]["fala"] == "o que sou?"
    assert turnos[0]["citacoes"] == ["ch-i-15"]
    assert turnos[0]["foi_limite"] is False


def test_atualiza_e_le_graus(tmp_path):
    mem = Memoria(str(tmp_path / "estado.db"))
    mem.atualizar_grau("buscador-1", "morte", "aberto")
    mem.atualizar_grau("buscador-1", "morte", "integrado")
    assert mem.ler_graus("buscador-1") == {"morte": "integrado"}


def test_graus_de_outro_buscador_nao_vazam(tmp_path):
    mem = Memoria(str(tmp_path / "estado.db"))
    mem.atualizar_grau("a", "morte", "aberto")
    assert mem.ler_graus("b") == {}
