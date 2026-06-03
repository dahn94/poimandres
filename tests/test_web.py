from fastapi.testclient import TestClient

from poimandres.web import criar_app


class _MemoriaFake:
    def __init__(self, turnos):
        self._turnos = turnos

    def ler_turnos(self, buscador_id):
        return list(self._turnos)


class _OraculoFake:
    """Oráculo de teste: sem LLM. Devolve uma RevelacaoFinal pré-definida."""

    def __init__(self, *, turnos=(), final=None, erro=None):
        self.memoria = _MemoriaFake(turnos)
        self._final = final
        self._erro = erro
        self.consultas = []

    def consultar(self, buscador_id, fala):
        self.consultas.append((buscador_id, fala))
        if self._erro is not None:
            raise self._erro
        return self._final


def test_get_inicio_renderiza_historico():
    turnos = [{"fala": "o que sou?", "revelacao": "és duplo", "citacoes": ["ch-i-15"], "foi_limite": False}]
    app = criar_app(_OraculoFake(turnos=turnos), em_thread=False)
    resp = TestClient(app).get("/")
    assert resp.status_code == 200
    assert "o que sou?" in resp.text
    assert "és duplo" in resp.text
