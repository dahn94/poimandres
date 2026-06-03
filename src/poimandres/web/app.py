"""Interface web do oráculo (Plano 3a) — chat local de um único buscador.

Envolve o :class:`~poimandres.pipeline.orquestrador.Oraculo` num app FastAPI. O
turno é lento (~minuto), então ``POST /perguntar`` dispara ``consultar`` numa
thread e responde na hora; a página faz polling em ``GET /turno/{id}``. O Oráculo
roda intocado. ``criar_app(oraculo, em_thread=False)`` roda síncrono nos testes.
"""

from __future__ import annotations

import threading
import uuid
from pathlib import Path

from fastapi import FastAPI, Request
from fastapi.responses import JSONResponse
from fastapi.staticfiles import StaticFiles
from fastapi.templating import Jinja2Templates

_AQUI = Path(__file__).parent
_BUSCADOR = "local"  # único buscador no 3a (sem auth)


def criar_app(oraculo, *, em_thread: bool = True) -> FastAPI:
    """Cria o app FastAPI do chat, envolvendo ``oraculo``.

    Args:
        oraculo: objeto com ``consultar(buscador_id, fala) -> RevelacaoFinal`` e
            ``memoria.ler_turnos(buscador_id)``. Em produção é o :class:`Oraculo`
            real; nos testes, um fake sem LLM.
        em_thread: se ``True`` (produção), o turno roda numa thread (não bloqueia);
            se ``False`` (testes), roda síncrono no próprio ``POST`` — determinístico.
    """
    app = FastAPI()
    templates = Jinja2Templates(directory=str(_AQUI / "templates"))
    app.mount("/static", StaticFiles(directory=str(_AQUI / "static")), name="static")
    em_voo: dict[str, dict] = {}

    @app.get("/")
    def inicio(request: Request):
        turnos = oraculo.memoria.ler_turnos(_BUSCADOR)
        return templates.TemplateResponse(
            request, "chat.html", {"turnos": turnos}
        )

    def _disparar(turno_id: str, fala: str) -> None:
        def trabalho() -> None:
            try:
                final = oraculo.consultar(_BUSCADOR, fala)
                em_voo[turno_id] = {"estado": "pronto", "final": final}
            except Exception as e:  # falha de API etc. — confissão honesta, não quebra
                em_voo[turno_id] = {"estado": "erro", "msg": str(e)}

        if em_thread:
            threading.Thread(target=trabalho, daemon=True).start()
        else:
            trabalho()

    @app.post("/perguntar")
    def perguntar(payload: dict | None = None):
        fala = (payload or {}).get("fala", "").strip()
        if not fala:
            return JSONResponse({"erro": "fala vazia"}, status_code=400)
        turno_id = uuid.uuid4().hex
        em_voo[turno_id] = {"estado": "considerando"}
        _disparar(turno_id, fala)
        return {"turno_id": turno_id, "estado": "considerando", "fala": fala}

    @app.get("/turno/{turno_id}")
    def turno(turno_id: str):
        info = em_voo.get(turno_id)
        if info is None:
            return JSONResponse({"estado": "desconhecido"}, status_code=404)
        if info["estado"] == "considerando":
            return {"estado": "considerando"}
        # Estado terminal (pronto|erro): entrega e descarta — mantém o em_voo
        # limitado; o histórico durável vive na Memória.
        em_voo.pop(turno_id, None)
        if info["estado"] == "pronto":
            f = info["final"]
            return {
                "estado": "pronto",
                "texto": f.texto,
                "citacoes": list(f.citacoes),
                "movimentos": list(f.movimentos),
                "foi_limite": f.foi_limite,
            }
        return {"estado": "erro", "msg": info["msg"]}

    return app
