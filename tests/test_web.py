import time
from types import SimpleNamespace

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


def _final(texto, *, citacoes=(), movimentos=(), foi_limite=False):
    return SimpleNamespace(
        texto=texto,
        citacoes=list(citacoes),
        movimentos=list(movimentos),
        foi_limite=foi_limite,
    )


def test_perguntar_inicia_turno_e_polling_entrega_revelacao():
    final = _final("O homem é duplo.", citacoes=["ch-i-15"], movimentos=["observe-se"])
    cliente = TestClient(criar_app(_OraculoFake(final=final), em_thread=False))
    r = cliente.post("/perguntar", json={"fala": "o que sou?"})
    assert r.status_code == 200
    body = r.json()
    assert body["estado"] == "considerando"
    turno_id = body["turno_id"]
    # com em_thread=False o turno já rodou síncrono no POST
    p = cliente.get(f"/turno/{turno_id}").json()
    assert p["estado"] == "pronto"
    assert p["texto"] == "O homem é duplo."
    assert p["citacoes"] == ["ch-i-15"]
    assert p["movimentos"] == ["observe-se"]
    assert p["foi_limite"] is False


def test_perguntar_fala_vazia_rejeita():
    cliente = TestClient(criar_app(_OraculoFake(final=_final("x")), em_thread=False))
    assert cliente.post("/perguntar", json={"fala": "   "}).status_code == 400


def test_turno_de_silencio_marca_foi_limite():
    final = _final("Sobre isto o corpus é silente.", foi_limite=True)
    cliente = TestClient(criar_app(_OraculoFake(final=final), em_thread=False))
    tid = cliente.post("/perguntar", json={"fala": "dieta?"}).json()["turno_id"]
    p = cliente.get(f"/turno/{tid}").json()
    assert p["estado"] == "pronto" and p["foi_limite"] is True and p["citacoes"] == []


def test_turno_com_erro_nao_quebra():
    cliente = TestClient(criar_app(_OraculoFake(erro=RuntimeError("API caiu")), em_thread=False))
    tid = cliente.post("/perguntar", json={"fala": "x"}).json()["turno_id"]
    p = cliente.get(f"/turno/{tid}").json()
    assert p["estado"] == "erro" and "API caiu" in p["msg"]


def test_turno_desconhecido_404():
    cliente = TestClient(criar_app(_OraculoFake(final=_final("x")), em_thread=False))
    assert cliente.get("/turno/naoexiste").status_code == 404


def test_perguntar_em_thread_eventualmente_pronto():
    final = _final("pronto via thread", citacoes=["ch-i-1"])
    cliente = TestClient(criar_app(_OraculoFake(final=final), em_thread=True))
    tid = cliente.post("/perguntar", json={"fala": "?"}).json()["turno_id"]
    p = {"estado": "considerando"}
    for _ in range(50):  # ~5s no máximo; o fake retorna quase instantâneo
        p = cliente.get(f"/turno/{tid}").json()
        if p["estado"] == "pronto":
            break
        time.sleep(0.1)
    assert p["estado"] == "pronto" and p["texto"] == "pronto via thread"


def test_inicio_tem_caixa_de_fala_e_polling():
    app = criar_app(_OraculoFake(turnos=()), em_thread=False)
    html = TestClient(app).get("/").text
    assert 'id="fala"' in html          # caixa de fala
    assert "/perguntar" in html          # JS chama o endpoint
    assert "/turno/" in html             # JS faz polling
    assert "considera tua fala" in html  # estado de espera temático
