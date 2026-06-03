# Poimandres — Plano 3a: Chat web local do oráculo (Implementation Plan)

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Tirar o oráculo da CLI com um chat web local de um único buscador (FastAPI + HTML server-rendered), tratando o turno lento (~minuto) por assíncrono + polling com um estado de espera temático.

**Architecture:** Um app FastAPI (`src/poimandres/web/`) envolve o `Oraculo` existente (via `montar_oraculo`/`_economico`). `POST /perguntar` dispara `Oraculo.consultar` numa thread e responde "considerando" na hora; um dict em memória guarda os turnos-em-voo; a página faz polling em `GET /turno/{id}` até a Revelação. O Oráculo roda intocado. `criar_app(oraculo, *, em_thread=…)` permite injetar um oráculo fake e rodar síncrono nos testes (sem LLM, sem rede).

**Tech Stack:** Python 3.12, FastAPI, uvicorn, Jinja2, `fastapi.testclient`. Reusa `poimandres.pipeline` (Oraculo, RevelacaoFinal, montar_oraculo), `poimandres.corpus` (CorpusStore, LocalEmbeddings). Sem SPA, sem build step.

---

## File Structure

| Arquivo | Responsabilidade |
|---|---|
| `pyproject.toml` | + deps `fastapi`, `uvicorn[standard]`, `jinja2`. |
| `src/poimandres/web/__init__.py` | Re-exporta `criar_app`. |
| `src/poimandres/web/app.py` | `criar_app(oraculo, *, em_thread=True)` — FastAPI: `GET /`, `POST /perguntar`, `GET /turno/{id}`; dict de turnos-em-voo. |
| `src/poimandres/web/templates/chat.html` | Página do chat: histórico + caixa de fala + JS de polling. |
| `src/poimandres/web/static/estilo.css` | CSS mínimo. |
| `src/poimandres/cli.py` | + comando `servir` (uvicorn; `--economico/--opus`, `--porta`). |
| `tests/test_web.py` | Testes dos endpoints com Oráculo fake (TestClient, sem LLM). |

Buscador fixo `"local"` no 3a. As citações da `RevelacaoFinal` são `citacao_id`s (ex.: `ch-i-15`) — renderizadas como tal (prettificar para ref. canônica é refinamento futuro).

---

### Task 1: Pacote web + `criar_app` + `GET /` (histórico)

**Files:**
- Modify: `pyproject.toml`
- Create: `src/poimandres/web/__init__.py`, `src/poimandres/web/app.py`, `src/poimandres/web/templates/chat.html`
- Test: `tests/test_web.py`

- [ ] **Step 1: Add dependencies**

In `pyproject.toml`, add to `dependencies` (after `anthropic`):

```toml
    "fastapi>=0.115",
    "uvicorn[standard]>=0.30",
    "jinja2>=3.1",
```

Install: `uv sync --extra dev` (the project uses uv; this resolves the new deps and keeps pytest).

- [ ] **Step 2: Write the failing test** — create `tests/test_web.py`:

```python
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
```

- [ ] **Step 3: Run test to verify it fails**

Run: `.venv/bin/pytest tests/test_web.py -q`
Expected: FAIL — `ModuleNotFoundError: No module named 'poimandres.web'`.

- [ ] **Step 4: Create the web package**

`src/poimandres/web/app.py`:

```python
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
            "chat.html", {"request": request, "turnos": turnos}
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
    def perguntar(payload: dict):
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
        if info["estado"] == "pronto":
            f = info["final"]
            return {
                "estado": "pronto",
                "texto": f.texto,
                "citacoes": list(f.citacoes),
                "movimentos": list(f.movimentos),
                "foi_limite": f.foi_limite,
            }
        if info["estado"] == "erro":
            return {"estado": "erro", "msg": info["msg"]}
        return {"estado": "considerando"}

    return app
```

`src/poimandres/web/__init__.py`:

```python
"""Interface web do oráculo — re-exporta o factory do app."""

from poimandres.web.app import criar_app

__all__ = ["criar_app"]
```

`src/poimandres/web/templates/chat.html` (mínimo por ora; o JS de polling entra na Task 3):

```html
<!doctype html>
<html lang="pt-BR">
<head>
  <meta charset="utf-8">
  <meta name="viewport" content="width=device-width, initial-scale=1">
  <title>Poimandres</title>
  <link rel="stylesheet" href="/static/estilo.css">
</head>
<body>
  <main id="dialogo">
    <h1>Poimandres</h1>
    {% for t in turnos %}
      <p class="fala"><b>você:</b> {{ t.fala }}</p>
      <p class="revelacao"><b>Mestre:</b> {{ t.revelacao }}</p>
      {% if t.citacoes %}<p class="citacoes">▸ funda em {{ t.citacoes | join(", ") }}</p>{% endif %}
    {% endfor %}
  </main>
</body>
</html>
```

Create an empty `src/poimandres/web/static/estilo.css` (filled in Task 3) so the `StaticFiles` mount has a directory:

```css
/* preenchido na Task 3 */
```

- [ ] **Step 5: Run test to verify it passes**

Run: `.venv/bin/pytest tests/test_web.py -q`
Expected: `1 passed`.

- [ ] **Step 6: Commit**

```bash
git add pyproject.toml src/poimandres/web tests/test_web.py
git commit -m "feat(web): pacote web + criar_app + GET / (histórico do chat)"
```
End the commit body with: `Co-Authored-By: Claude Opus 4.8 <noreply@anthropic.com>`

---

### Task 2: Turno assíncrono — `POST /perguntar` + `GET /turno/{id}`

**Files:**
- Test: `tests/test_web.py`

(The endpoints já foram escritos na Task 1; esta task **prova** o fluxo assíncrono, o silêncio/limite e o erro, todos com `em_thread=False` para determinismo.)

- [ ] **Step 1: Write the failing tests** — append to `tests/test_web.py`:

```python
from types import SimpleNamespace


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
```

- [ ] **Step 2: Run tests to verify they pass**

Run: `.venv/bin/pytest tests/test_web.py -q`
Expected: all pass (the Task 1 test + these 5). The endpoints exist from Task 1; these assert behavior.

- [ ] **Step 3: Verify the threaded path too (sanity, não-determinístico)**

Add one test that exercises `em_thread=True` with a short poll loop (the production path):

```python
import time


def test_perguntar_em_thread_eventualmente_pronto():
    final = _final("pronto via thread", citacoes=["ch-i-1"])
    cliente = TestClient(criar_app(_OraculoFake(final=final), em_thread=True))
    tid = cliente.post("/perguntar", json={"fala": "?"}).json()["turno_id"]
    for _ in range(50):  # ~5s no máximo; o fake retorna quase instantâneo
        p = cliente.get(f"/turno/{tid}").json()
        if p["estado"] == "pronto":
            break
        time.sleep(0.1)
    assert p["estado"] == "pronto" and p["texto"] == "pronto via thread"
```

Run: `.venv/bin/pytest tests/test_web.py -q`
Expected: all pass.

- [ ] **Step 4: Commit**

```bash
git add tests/test_web.py
git commit -m "test(web): fluxo assíncrono do turno (considerando→pronto), silêncio, erro, 404"
```
End the commit body with: `Co-Authored-By: Claude Opus 4.8 <noreply@anthropic.com>`

---

### Task 3: Front-end — caixa de fala + polling + CSS

**Files:**
- Modify: `src/poimandres/web/templates/chat.html`
- Modify: `src/poimandres/web/static/estilo.css`
- Test: `tests/test_web.py`

- [ ] **Step 1: Write the failing test** — append to `tests/test_web.py`:

```python
def test_inicio_tem_caixa_de_fala_e_polling():
    app = criar_app(_OraculoFake(turnos=()), em_thread=False)
    html = TestClient(app).get("/").text
    assert 'id="fala"' in html          # caixa de fala
    assert "/perguntar" in html          # JS chama o endpoint
    assert "/turno/" in html             # JS faz polling
    assert "considera tua fala" in html  # estado de espera temático
```

- [ ] **Step 2: Run test to verify it fails**

Run: `.venv/bin/pytest tests/test_web.py::test_inicio_tem_caixa_de_fala_e_polling -q`
Expected: FAIL (the minimal chat.html has no form/JS yet).

- [ ] **Step 3: Flesh out the template + CSS**

Replace `src/poimandres/web/templates/chat.html` with:

```html
<!doctype html>
<html lang="pt-BR">
<head>
  <meta charset="utf-8">
  <meta name="viewport" content="width=device-width, initial-scale=1">
  <title>Poimandres</title>
  <link rel="stylesheet" href="/static/estilo.css">
</head>
<body>
  <main id="dialogo">
    <h1>Poimandres</h1>
    {% for t in turnos %}
      <p class="fala"><b>você:</b> {{ t.fala }}</p>
      <p class="revelacao"><b>Mestre:</b> {{ t.revelacao }}</p>
      {% if t.citacoes %}<p class="citacoes">▸ funda em {{ t.citacoes | join(", ") }}</p>{% endif %}
    {% endfor %}
  </main>
  <form id="forma">
    <input id="fala" name="fala" autocomplete="off" placeholder="fala…" autofocus>
  </form>
  <script>
    const dialogo = document.getElementById("dialogo");
    const forma = document.getElementById("forma");
    const campo = document.getElementById("fala");

    function p(cls, html) {
      const el = document.createElement("p");
      el.className = cls;
      el.innerHTML = html;
      dialogo.appendChild(el);
      el.scrollIntoView();
      return el;
    }
    function escapar(s) {
      const d = document.createElement("div");
      d.textContent = s;
      return d.innerHTML;
    }

    forma.addEventListener("submit", async (ev) => {
      ev.preventDefault();
      const fala = campo.value.trim();
      if (!fala) return;
      campo.value = "";
      campo.disabled = true;
      p("fala", "<b>você:</b> " + escapar(fala));
      const espera = p("espera", "⟡ o Mestre considera tua fala…");

      const r = await fetch("/perguntar", {
        method: "POST",
        headers: {"Content-Type": "application/json"},
        body: JSON.stringify({fala}),
      });
      const {turno_id} = await r.json();

      const timer = setInterval(async () => {
        const s = await (await fetch("/turno/" + turno_id)).json();
        if (s.estado === "considerando") return;
        clearInterval(timer);
        espera.remove();
        if (s.estado === "erro") {
          p("erro", "⟡ <b>Mestre:</b> (o limiar se turvou: " + escapar(s.msg) + ")");
        } else if (s.foi_limite) {
          p("revelacao", "⟡ <b>Mestre:</b> " + escapar(s.texto));
        } else {
          p("revelacao", "⟡ <b>Mestre:</b> " + escapar(s.texto));
          if (s.citacoes.length) p("citacoes", "▸ funda em " + s.citacoes.map(escapar).join(", "));
          s.movimentos.forEach(m => p("movimento", "→ " + escapar(m)));
        }
        campo.disabled = false;
        campo.focus();
      }, 2000);
    });
  </script>
</body>
</html>
```

Replace `src/poimandres/web/static/estilo.css` with:

```css
body { max-width: 42rem; margin: 2rem auto; padding: 0 1rem;
  font-family: Georgia, "Times New Roman", serif; line-height: 1.5; color: #2b2b2b; }
h1 { font-weight: normal; letter-spacing: 0.1em; }
#dialogo p { margin: 0.6rem 0; }
.fala { color: #555; }
.revelacao { white-space: pre-wrap; }
.citacoes, .movimento { color: #8a6d3b; font-style: italic; font-size: 0.9em; }
.espera { color: #999; font-style: italic; }
.erro { color: #a33; font-style: italic; }
#fala { width: 100%; padding: 0.6rem; font-family: inherit; font-size: 1rem;
  border: 1px solid #ccc; border-radius: 4px; box-sizing: border-box; }
```

- [ ] **Step 4: Run test to verify it passes**

Run: `.venv/bin/pytest tests/test_web.py -q`
Expected: all pass.

- [ ] **Step 5: Commit**

```bash
git add src/poimandres/web/templates/chat.html src/poimandres/web/static/estilo.css tests/test_web.py
git commit -m "feat(web): caixa de fala + polling temático + CSS mínimo"
```
End the commit body with: `Co-Authored-By: Claude Opus 4.8 <noreply@anthropic.com>`

---

### Task 4: Comando CLI `servir`

**Files:**
- Modify: `src/poimandres/cli.py`
- Test: `tests/test_cli.py`

- [ ] **Step 1: Write the failing test** — append to `tests/test_cli.py`:

```python
def test_servir_listado_no_help():
    from click.testing import CliRunner

    from poimandres.cli import cli

    res = CliRunner().invoke(cli, ["servir", "--help"])
    assert res.exit_code == 0
    assert "--economico" in res.output
    assert "--opus" in res.output
    assert "--porta" in res.output
```

(`tests/test_cli.py` já importa o necessário do projeto; se não houver `CliRunner` importado no topo, o import local acima basta.)

- [ ] **Step 2: Run test to verify it fails**

Run: `.venv/bin/pytest tests/test_cli.py::test_servir_listado_no_help -q`
Expected: FAIL — `No such command 'servir'`.

- [ ] **Step 3: Add the `servir` command**

In `src/poimandres/cli.py`, append a `servir` command (the module already has `cli` group, `_DB_PADRAO`, `_fazer_embeddings`, `CorpusStore` imported, and `from pathlib import Path`):

```python
@cli.command()
@click.option(
    "--economico/--opus",
    default=True,
    show_default=True,
    help="Modo barato (Sonnet) ou voz plena (Opus) — cada turno custa via Claude API.",
)
@click.option("--porta", default=8000, show_default=True)
@click.option("--db", default=_DB_PADRAO, show_default=True)
def servir(economico: bool, porta: int, db: str) -> None:
    """Sobe o chat web local do oráculo em http://127.0.0.1:<porta>.

    Requer credencial Anthropic (``ANTHROPIC_API_KEY`` ou ``ant auth login``) e o
    índice em ``--db`` já ingerido. Buscador único (sem auth) — Plano 3a.
    """
    import uvicorn

    from poimandres.pipeline.fabrica import montar_oraculo, montar_oraculo_economico
    from poimandres.web import criar_app

    montar = montar_oraculo_economico if economico else montar_oraculo
    store = CorpusStore(db, _fazer_embeddings())
    oraculo = montar(store=store, db_memoria=str(Path(db).parent / "estado.db"))
    click.echo(f"Poimandres no ar em http://127.0.0.1:{porta}  (modo: "
               f"{'econômico' if economico else 'opus'})")
    uvicorn.run(criar_app(oraculo), host="127.0.0.1", port=porta)
```

- [ ] **Step 4: Run test to verify it passes**

Run: `.venv/bin/pytest tests/test_cli.py -q`
Expected: all pass. Also confirm full suite: `.venv/bin/pytest -q` → all green.

- [ ] **Step 5: Manual smoke (optional, gasta API)**

Run: `.venv/bin/poimandres servir --economico` → abra http://127.0.0.1:8000, faça uma pergunta, veja a Condução. (Requer chave; gasta tokens. Não é parte da suíte.)

- [ ] **Step 6: Commit**

```bash
git add src/poimandres/cli.py tests/test_cli.py
git commit -m "feat(web): comando CLI 'servir' (uvicorn; --economico/--opus/--porta)"
```
End the commit body with: `Co-Authored-By: Claude Opus 4.8 <noreply@anthropic.com>`

---

## Self-Review (preenchido)

**Cobertura do spec do 3a:**
- §2 pacote `web/` + FastAPI + `criar_app` + deps → Task 1. ✓
- §3 fluxo assíncrono (dict em-voo, thread, polling) + erro honesto → Tasks 1 (código) e 2 (provas). ✓
- §4 endpoints `GET /`, `POST /perguntar`, `GET /turno/{id}` → Tasks 1, 2. ✓
- §5 tela (histórico, espera temática, citações, movimentos ao vivo, silêncio/limite) → Tasks 1, 3. ✓
- §6 modelo configurável (`--economico/--opus`, `--porta`) → Task 4. ✓
- §7 injeção (`criar_app(oraculo, em_thread=…)`) + testes determinísticos sem LLM → Tasks 1-3. ✓
- §5 limitação: histórico não mostra `movimentos` (a tabela `turno` não os guarda) — respeitado: o template do histórico (Tasks 1/3) só renderiza fala/revelação/citações; movimentos só no turno ao vivo (JS). ✓

**Placeholders:** nenhum passo deixa código por preencher (o CSS "preenchido na Task 3" é literal: criado vazio na Task 1, escrito na Task 3 — não é um TODO de lógica). ✓

**Consistência de tipos/assinaturas:** `criar_app(oraculo, *, em_thread=True)`; o oráculo expõe `consultar(buscador_id, fala)` e `memoria.ler_turnos(buscador_id)`; `RevelacaoFinal` lida por atributos `texto/citacoes/movimentos/foi_limite`; endpoints e JS usam as mesmas chaves JSON (`turno_id`, `estado`, `texto`, `citacoes`, `movimentos`, `foi_limite`, `msg`); `servir` usa `montar_oraculo_economico`/`montar_oraculo` (assinaturas do 2b) + `criar_app`. Consistente entre tasks e testes. ✓

**Riscos conhecidos (não bloqueiam):** o teste do caminho `em_thread=True` (Task 2 Step 3) é levemente não-determinístico (polling com timeout) — mitigado por loop curto e fake instantâneo; o determinístico de verdade é o `em_thread=False`. O `servir` em si (uvicorn + BGE-M3) não é testado além do `--help` (glue); o smoke real é manual.
