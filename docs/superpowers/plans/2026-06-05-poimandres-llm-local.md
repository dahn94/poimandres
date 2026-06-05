# Backend LLM local (Gemma 4) — híbrido com toggle — Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Adicionar um backend `LocalLLM` (Gemma 4 via servidor OpenAI-compatible — mlx-lm no Mac, vLLM no Linux), coexistindo com `ClaudeLLM`, selecionável por env var, e dockerizável.

**Architecture:** O pipeline já depende só da interface `LLMBackend`. Entra uma classe `LocalLLM` (cliente OpenAI-compatible com `base_url` configurável), um preset `montar_oraculo_local` (todos os papéis na Gemma; thinking só no Compositor) e um seletor por env (`montar_por_ambiente`) que a CLI usa. mlx-lm e vLLM falam o mesmo dialeto OpenAI, então o toggle de runtime é só o `base_url`.

**Tech Stack:** Python 3.12, lib `openai` (cliente), `click` (CLI), `pytest` (monkeypatch do cliente, sem rede), `uv` (deps), Docker/Compose, mlx-lm (host Mac/Metal) e vLLM (Docker/GPU) como servidores externos.

**Spec:** `docs/superpowers/specs/2026-06-05-poimandres-llm-local-design.md`

---

## File Structure

- **Modify** `pyproject.toml` — dep `openai`; extra opcional `local-mac` = `mlx-lm`.
- **Modify** `src/poimandres/pipeline/llm.py` — helpers `_limpar_pensamento`/`_extrair_json` + classe `LocalLLM`.
- **Modify** `src/poimandres/pipeline/fabrica.py` — `endpoint_local_padrao`, `resolver_url_local`, `montar_oraculo_local`, `montar_por_ambiente`.
- **Modify** `src/poimandres/cli.py` — `perguntar`/`servir` usam `montar_por_ambiente`; `servir` ganha `--host`.
- **Test** `tests/test_llm.py`, `tests/test_fabrica.py`, `tests/test_cli.py` — estendidos.
- **Create** `scripts/servidor-mlx.sh` — sobe a Gemma via mlx-lm no host (Metal).
- **Create** `Dockerfile`, `docker-compose.yml`, `.dockerignore`.
- **Create** `docs/llm-local.md` — quickstart; **Modify** o log de sessão.

---

### Task 1: Dependência `openai` + extra `local-mac`

**Files:**
- Modify: `pyproject.toml`
- Modify: `uv.lock` (gerado)

- [ ] **Step 1: Adicionar a dep `openai`**

Run:
```bash
uv add openai
```
Expected: `pyproject.toml` ganha `openai>=...` em `[project].dependencies`; `uv.lock` atualizado; instala no `.venv`.

- [ ] **Step 2: Adicionar o extra opcional `local-mac` (mlx-lm, só no macOS)**

Run:
```bash
uv add --optional local-mac "mlx-lm; sys_platform == 'darwin'"
```
Expected: `pyproject.toml` ganha `[project.optional-dependencies].local-mac = ["mlx-lm; sys_platform == 'darwin'"]`.

- [ ] **Step 3: Verificar import do cliente**

Run:
```bash
.venv/bin/python -c "import openai; print(openai.__version__)"
```
Expected: imprime uma versão (ex.: `1.x.y`), sem erro.

- [ ] **Step 4: Commit**

```bash
git add pyproject.toml uv.lock
git commit -m "build: dep openai (cliente do LocalLLM) + extra local-mac (mlx-lm)"
```

---

### Task 2: Helpers de limpeza da saída local

Gemma 4 pode emitir um canal de pensamento antes do JSON. Os três papéis do pipeline fazem `json.loads` direto na saída, então o backend tem de devolver JSON puro. Estes helpers fazem isso, de forma testável e sem rede.

**Files:**
- Modify: `src/poimandres/pipeline/llm.py`
- Test: `tests/test_llm.py`

- [ ] **Step 1: Escrever os testes que falham**

Adicione ao fim de `tests/test_llm.py`:
```python
def test_extrair_json_remove_pensamento_e_cercas():
    from poimandres.pipeline.llm import _extrair_json

    bruto = '<|channel>thought\no buscador pergunta { algo }\n<channel|>\n```json\n{"ok": true}\n```'
    assert _extrair_json(bruto) == '{"ok": true}'


def test_extrair_json_objeto_simples():
    from poimandres.pipeline.llm import _extrair_json

    assert _extrair_json('{"a": 1, "b": [2, 3]}') == '{"a": 1, "b": [2, 3]}'


def test_extrair_json_sem_objeto_falha_alto():
    import pytest

    from poimandres.pipeline.llm import _extrair_json

    with pytest.raises(RuntimeError):
        _extrair_json("não há JSON aqui")


def test_limpar_pensamento_sem_canal_devolve_intacto():
    from poimandres.pipeline.llm import _limpar_pensamento

    assert _limpar_pensamento("texto simples") == "texto simples"
```

- [ ] **Step 2: Rodar e ver falhar**

Run: `.venv/bin/pytest tests/test_llm.py -k "extrair_json or limpar_pensamento" -v`
Expected: FAIL com `ImportError`/`cannot import name '_extrair_json'`.

- [ ] **Step 3: Implementar os helpers**

Em `src/poimandres/pipeline/llm.py`, adicione `import json` no topo (após `from __future__`) se ainda não houver, e adicione antes da classe `FakeLLM`:
```python
def _limpar_pensamento(texto: str) -> str:
    """Descarta o canal de pensamento da Gemma 4 (tudo até o último ``<channel|>``)."""
    if "<channel|>" in texto:
        return texto.rsplit("<channel|>", 1)[1]
    return texto


def _extrair_json(texto: str) -> str:
    """Devolve só o objeto JSON externo da saída (remove pensamento, cercas, prosa).

    Os papéis do pipeline fazem ``json.loads`` direto neste retorno; um modelo
    local pode embrulhar o JSON em ``<channel|>``/```` ```json ````/prosa, então
    recortamos do primeiro ``{`` ao último ``}``. Sem objeto, erra alto (não passa
    em falso, espelhando o ``RuntimeError`` do ``ClaudeLLM``).
    """
    corpo = _limpar_pensamento(texto)
    ini = corpo.find("{")
    fim = corpo.rfind("}")
    if ini == -1 or fim == -1 or fim < ini:
        raise RuntimeError(f"LocalLLM: resposta sem objeto JSON — {texto!r}")
    return corpo[ini : fim + 1]
```

- [ ] **Step 4: Rodar e ver passar**

Run: `.venv/bin/pytest tests/test_llm.py -k "extrair_json or limpar_pensamento" -v`
Expected: PASS (4 testes).

- [ ] **Step 5: Commit**

```bash
git add src/poimandres/pipeline/llm.py tests/test_llm.py
git commit -m "feat(llm): helpers _limpar_pensamento/_extrair_json p/ saída local"
```

---

### Task 3: Classe `LocalLLM`

**Files:**
- Modify: `src/poimandres/pipeline/llm.py`
- Test: `tests/test_llm.py`

- [ ] **Step 1: Escrever os testes que falham**

Adicione ao fim de `tests/test_llm.py`:
```python
class _FakeChatMessage:
    def __init__(self, content):
        self.content = content


class _FakeChoice:
    def __init__(self, content):
        self.message = _FakeChatMessage(content)


class _FakeChatResp:
    def __init__(self, content):
        self.choices = [_FakeChoice(content)]


class _FakeCompletions:
    def __init__(self, rec, content):
        self._rec = rec
        self._content = content

    def create(self, **kwargs):
        self._rec.append(kwargs)
        return _FakeChatResp(self._content)


class _FakeOpenAIClient:
    def __init__(self, rec, content, ctor):
        self.chat = type("C", (), {"completions": _FakeCompletions(rec, content)})()
        self._ctor = ctor


def _patch_openai(monkeypatch, content):
    """Substitui openai.OpenAI por um fake; devolve (chamadas, ctor_kwargs)."""
    from poimandres.pipeline import llm as llm_mod

    chamadas: list[dict] = []
    ctor: dict = {}

    def fabricar(**kw):
        ctor.update(kw)
        return _FakeOpenAIClient(chamadas, content, ctor)

    monkeypatch.setattr(llm_mod.openai, "OpenAI", fabricar)
    return chamadas, ctor


def test_localllm_monta_request_com_schema_e_thinking(monkeypatch):
    from poimandres.pipeline.llm import LocalLLM

    chamadas, ctor = _patch_openai(monkeypatch, '<channel|>{"ok": true}')
    backend = LocalLLM(
        base_url="http://x:8080/v1", modelo="gemma-x", pensar=True, max_tokens=1234
    )
    texto = backend.gerar(
        PedidoLLM(sistema="as leis", usuario="quem sou?", schema={"type": "object"})
    )

    assert texto == '{"ok": true}'
    assert ctor["base_url"] == "http://x:8080/v1"
    req = chamadas[0]
    assert req["model"] == "gemma-x"
    assert req["max_tokens"] == 1234
    assert req["extra_body"]["chat_template_kwargs"]["enable_thinking"] is True
    assert req["extra_body"]["top_k"] == 64
    assert req["response_format"]["type"] == "json_schema"
    assert req["response_format"]["json_schema"]["schema"] == {"type": "object"}
    # schema embutido no prompt de sistema (garantia portável p/ mlx-lm)
    assert "as leis" in req["messages"][0]["content"]
    assert '"type": "object"' in req["messages"][0]["content"]
    assert req["messages"][1] == {"role": "user", "content": "quem sou?"}


def test_localllm_sem_pensar_desliga_thinking_e_sem_schema_nao_forca_json(monkeypatch):
    from poimandres.pipeline.llm import LocalLLM

    chamadas, _ = _patch_openai(monkeypatch, "prosa livre do Mestre")
    backend = LocalLLM(base_url="http://x:8000/v1", modelo="g", pensar=False)
    texto = backend.gerar(PedidoLLM(sistema="s", usuario="u"))

    assert texto == "prosa livre do Mestre"
    req = chamadas[0]
    assert req["extra_body"]["chat_template_kwargs"]["enable_thinking"] is False
    assert "response_format" not in req


def test_localllm_saida_sem_json_quando_ha_schema_falha_alto(monkeypatch):
    import pytest

    from poimandres.pipeline.llm import LocalLLM

    _patch_openai(monkeypatch, "o modelo divagou sem JSON")
    backend = LocalLLM(base_url="http://x/v1", modelo="g")
    with pytest.raises(RuntimeError):
        backend.gerar(PedidoLLM(sistema="s", usuario="u", schema={"type": "object"}))
```

- [ ] **Step 2: Rodar e ver falhar**

Run: `.venv/bin/pytest tests/test_llm.py -k localllm -v`
Expected: FAIL com `cannot import name 'LocalLLM'`.

- [ ] **Step 3: Implementar `LocalLLM`**

Em `src/poimandres/pipeline/llm.py`, adicione `import openai` junto aos imports do topo (depois de `import anthropic`), e adicione ao fim do arquivo:
```python
class LocalLLM:
    """Backend de LLM local via servidor OpenAI-compatible (mlx-lm no Mac, vLLM no Linux).

    Mesmo contrato ``LLMBackend`` do ``FakeLLM``/``ClaudeLLM``. Uma só classe serve
    aos dois runtimes — o toggle de plataforma é apenas o ``base_url``. Quando o
    pedido traz ``schema``, embute-o no prompt (garantia portável) **e** pede
    ``response_format=json_schema`` (vLLM impõe por guided-decoding; mlx-lm, quando
    suporta, reforça). ``pensar`` liga o canal de raciocínio da Gemma 4 (Compositor);
    a saída é sempre limpa para JSON puro quando há schema.
    """

    def __init__(
        self,
        *,
        base_url: str,
        modelo: str,
        pensar: bool = False,
        max_tokens: int = 4096,
        temperature: float = 1.0,
        top_p: float = 0.95,
        top_k: int = 64,
    ) -> None:
        self._client = openai.OpenAI(base_url=base_url, api_key="sk-local")
        self._modelo = modelo
        self._pensar = pensar
        self._max_tokens = max_tokens
        self._temperature = temperature
        self._top_p = top_p
        self._top_k = top_k

    def gerar(self, pedido: PedidoLLM) -> str:
        sistema = pedido.sistema
        kwargs: dict = {
            "model": self._modelo,
            "max_tokens": self._max_tokens,
            "temperature": self._temperature,
            "top_p": self._top_p,
            "extra_body": {
                "chat_template_kwargs": {"enable_thinking": self._pensar},
                "top_k": self._top_k,
            },
        }
        if pedido.schema is not None:
            sistema = (
                f"{sistema}\n\nResponda SOMENTE com um objeto JSON válido conforme "
                f"este schema, sem texto fora do JSON e sem cercas de código:\n"
                f"{json.dumps(pedido.schema, ensure_ascii=False)}"
            )
            kwargs["response_format"] = {
                "type": "json_schema",
                "json_schema": {"name": "resposta", "schema": pedido.schema},
            }
        kwargs["messages"] = [
            {"role": "system", "content": sistema},
            {"role": "user", "content": pedido.usuario},
        ]
        resposta = self._client.chat.completions.create(**kwargs)
        bruto = resposta.choices[0].message.content or ""
        if pedido.schema is not None:
            return _extrair_json(bruto)
        return _limpar_pensamento(bruto).strip()
```

- [ ] **Step 4: Rodar e ver passar**

Run: `.venv/bin/pytest tests/test_llm.py -k localllm -v`
Expected: PASS (3 testes).

- [ ] **Step 5: Rodar a suíte de LLM inteira**

Run: `.venv/bin/pytest tests/test_llm.py -v`
Expected: PASS (todos, incl. os do `ClaudeLLM`/`FakeLLM`).

- [ ] **Step 6: Commit**

```bash
git add src/poimandres/pipeline/llm.py tests/test_llm.py
git commit -m "feat(llm): LocalLLM — backend Gemma 4 via servidor OpenAI-compatible"
```

---

### Task 4: Resolução do endpoint local (plataforma + env)

**Files:**
- Modify: `src/poimandres/pipeline/fabrica.py`
- Test: `tests/test_fabrica.py`

- [ ] **Step 1: Escrever os testes que falham**

Adicione ao fim de `tests/test_fabrica.py`:
```python
def test_endpoint_padrao_por_plataforma(monkeypatch):
    from poimandres.pipeline import fabrica

    monkeypatch.setattr(fabrica.platform, "system", lambda: "Darwin")
    assert fabrica.endpoint_local_padrao() == "http://127.0.0.1:8080/v1"
    monkeypatch.setattr(fabrica.platform, "system", lambda: "Linux")
    assert fabrica.endpoint_local_padrao() == "http://127.0.0.1:8000/v1"


def test_resolver_url_local_precedencia(monkeypatch):
    from poimandres.pipeline import fabrica

    monkeypatch.setattr(fabrica.platform, "system", lambda: "Linux")
    monkeypatch.delenv("POIMANDRES_LOCAL_URL", raising=False)
    assert fabrica.resolver_url_local() == "http://127.0.0.1:8000/v1"

    monkeypatch.setenv("POIMANDRES_LOCAL_URL", "http://env:9/v1")
    assert fabrica.resolver_url_local() == "http://env:9/v1"

    # argumento explícito vence a env
    assert fabrica.resolver_url_local("http://arg:1/v1") == "http://arg:1/v1"
```

- [ ] **Step 2: Rodar e ver falhar**

Run: `.venv/bin/pytest tests/test_fabrica.py -k "endpoint_padrao or resolver_url" -v`
Expected: FAIL com `AttributeError`/`has no attribute 'endpoint_local_padrao'`.

- [ ] **Step 3: Implementar**

Em `src/poimandres/pipeline/fabrica.py`, adicione aos imports do topo:
```python
import os
import platform
```
e `from poimandres.pipeline.llm import ClaudeLLM, LLMBackend, LocalLLM` (acrescente `LocalLLM` ao import já existente). Depois das constantes `_MODELO_*`, adicione:
```python
_MODELO_LOCAL = "gemma-4-26b-a4b"


def endpoint_local_padrao() -> str:
    """URL default do servidor local por plataforma: Mac→mlx-lm :8080, Linux→vLLM :8000."""
    if platform.system() == "Darwin":
        return "http://127.0.0.1:8080/v1"
    return "http://127.0.0.1:8000/v1"


def resolver_url_local(base_url: str | None = None) -> str:
    """Precedência: argumento explícito > ``POIMANDRES_LOCAL_URL`` > default por plataforma."""
    return base_url or os.environ.get("POIMANDRES_LOCAL_URL") or endpoint_local_padrao()
```

- [ ] **Step 4: Rodar e ver passar**

Run: `.venv/bin/pytest tests/test_fabrica.py -k "endpoint_padrao or resolver_url" -v`
Expected: PASS (2 testes).

- [ ] **Step 5: Commit**

```bash
git add src/poimandres/pipeline/fabrica.py tests/test_fabrica.py
git commit -m "feat(fabrica): resolução do endpoint local (plataforma + POIMANDRES_LOCAL_URL)"
```

---

### Task 5: Preset `montar_oraculo_local`

O `montar_oraculo` chama `fazer_llm(modelo)` com `modelo_mestre` no Compositor e `modelo_rapido` nos demais. Aqui usamos rótulos de papel (`"mestre"`/`"rapido"`) para que o `LocalLLM` ligue ``pensar`` só no Compositor, enquanto envia sempre o mesmo modelo servido.

**Files:**
- Modify: `src/poimandres/pipeline/fabrica.py`
- Test: `tests/test_fabrica.py`

- [ ] **Step 1: Escrever o teste que falha**

Adicione ao fim de `tests/test_fabrica.py`:
```python
def test_oraculo_local_pensa_so_no_compositor(tmp_path, monkeypatch):
    from poimandres.pipeline import fabrica

    construidos = []

    class _FakeLocal:
        def __init__(self, *, base_url, modelo, pensar=False, max_tokens=4096):
            construidos.append({"base_url": base_url, "modelo": modelo, "pensar": pensar})

        def gerar(self, pedido):  # nunca chamado neste teste
            raise AssertionError("não deve gerar")

    monkeypatch.setattr(fabrica, "LocalLLM", _FakeLocal)
    store = CorpusStore(str(tmp_path / "c.lance"), FakeEmbeddings())

    oraculo = fabrica.montar_oraculo_local(
        store=store,
        db_memoria=str(tmp_path / "estado.db"),
        base_url="http://x:8080/v1",
    )
    assert isinstance(oraculo, Oraculo)
    # ordem de construção: Discernidor(rapido), Compositor(mestre), Verificador(rapido)
    assert [c["pensar"] for c in construidos] == [False, True, False]
    assert all(c["base_url"] == "http://x:8080/v1" for c in construidos)
    assert all(c["modelo"] == "gemma-4-26b-a4b" for c in construidos)
```

- [ ] **Step 2: Rodar e ver falhar**

Run: `.venv/bin/pytest tests/test_fabrica.py -k oraculo_local -v`
Expected: FAIL com `has no attribute 'montar_oraculo_local'`.

- [ ] **Step 3: Implementar**

Em `src/poimandres/pipeline/fabrica.py`, adicione após `montar_oraculo_economico`:
```python
def montar_oraculo_local(
    *,
    store: CorpusStore,
    db_memoria: str,
    base_url: str | None = None,
    modelo: str = _MODELO_LOCAL,
    max_tokens: int = 4096,
    **kwargs,
) -> Oraculo:
    """Preset LOCAL: todos os papéis na Gemma 4 (offline, $0). Thinking só no Compositor.

    ``base_url`` resolve por plataforma/env quando ``None`` (ver :func:`resolver_url_local`).
    Os rótulos ``"mestre"``/``"rapido"`` (passados a ``fazer_llm`` pelo ``montar_oraculo``)
    só decidem ``pensar``; o modelo servido é o mesmo ``modelo`` em todos os papéis.
    ``**kwargs`` repassa o resto (ex.: ``max_retries``, ``limiar``).
    """
    url = resolver_url_local(base_url)

    def fazer_llm(papel: str) -> LLMBackend:
        return LocalLLM(
            base_url=url, modelo=modelo, pensar=(papel == "mestre"), max_tokens=max_tokens
        )

    return montar_oraculo(
        store=store,
        db_memoria=db_memoria,
        modelo_mestre="mestre",
        modelo_rapido="rapido",
        fazer_llm=fazer_llm,
        **kwargs,
    )
```

- [ ] **Step 4: Rodar e ver passar**

Run: `.venv/bin/pytest tests/test_fabrica.py -k oraculo_local -v`
Expected: PASS.

- [ ] **Step 5: Commit**

```bash
git add src/poimandres/pipeline/fabrica.py tests/test_fabrica.py
git commit -m "feat(fabrica): montar_oraculo_local (Gemma 4 em tudo; thinking só no Compositor)"
```

---

### Task 6: Seletor por env `montar_por_ambiente`

**Files:**
- Modify: `src/poimandres/pipeline/fabrica.py`
- Test: `tests/test_fabrica.py`

- [ ] **Step 1: Escrever os testes que falham**

Adicione ao fim de `tests/test_fabrica.py`:
```python
def test_por_ambiente_local_quando_env_local(tmp_path, monkeypatch):
    from poimandres.pipeline import fabrica

    chamado = {}

    def fake_local(*, store, db_memoria, base_url=None):
        chamado["local"] = base_url
        return "ORACULO_LOCAL"

    monkeypatch.setattr(fabrica, "montar_oraculo_local", fake_local)
    monkeypatch.setenv("POIMANDRES_LLM", "local")
    store = CorpusStore(str(tmp_path / "c.lance"), FakeEmbeddings())

    out = fabrica.montar_por_ambiente(store=store, db_memoria="x", base_url="http://u/v1")
    assert out == "ORACULO_LOCAL"
    assert chamado["local"] == "http://u/v1"


def test_por_ambiente_claude_default_respeita_economico(tmp_path, monkeypatch):
    from poimandres.pipeline import fabrica

    escolhido = {}

    def fake_eco(*, store, db_memoria):
        escolhido["modo"] = "economico"
        return "ECO"

    def fake_opus(*, store, db_memoria):
        escolhido["modo"] = "opus"
        return "OPUS"

    monkeypatch.setattr(fabrica, "montar_oraculo_economico", fake_eco)
    monkeypatch.setattr(fabrica, "montar_oraculo", fake_opus)
    monkeypatch.delenv("POIMANDRES_LLM", raising=False)
    store = CorpusStore(str(tmp_path / "c.lance"), FakeEmbeddings())

    assert fabrica.montar_por_ambiente(store=store, db_memoria="x") == "ECO"
    assert fabrica.montar_por_ambiente(store=store, db_memoria="x", economico=False) == "OPUS"
```

- [ ] **Step 2: Rodar e ver falhar**

Run: `.venv/bin/pytest tests/test_fabrica.py -k por_ambiente -v`
Expected: FAIL com `has no attribute 'montar_por_ambiente'`.

- [ ] **Step 3: Implementar**

Em `src/poimandres/pipeline/fabrica.py`, adicione ao fim do arquivo:
```python
def montar_por_ambiente(
    *,
    store: CorpusStore,
    db_memoria: str,
    economico: bool = True,
    base_url: str | None = None,
) -> Oraculo:
    """Escolhe o backend por ``POIMANDRES_LLM`` (``claude``|``local``; default ``claude``).

    ``local`` → :func:`montar_oraculo_local` (Gemma 4). ``claude`` → preset econômico
    (Sonnet) ou, com ``economico=False``, produção (Opus). Ponto único de toggle que a
    CLL usa, amigável a Docker (só troca env).
    """
    if os.environ.get("POIMANDRES_LLM", "claude").lower() == "local":
        return montar_oraculo_local(store=store, db_memoria=db_memoria, base_url=base_url)
    montar = montar_oraculo_economico if economico else montar_oraculo
    return montar(store=store, db_memoria=db_memoria)
```

- [ ] **Step 4: Rodar e ver passar**

Run: `.venv/bin/pytest tests/test_fabrica.py -k por_ambiente -v`
Expected: PASS (2 testes).

- [ ] **Step 5: Rodar a suíte da fábrica inteira**

Run: `.venv/bin/pytest tests/test_fabrica.py -v`
Expected: PASS (todos).

- [ ] **Step 6: Commit**

```bash
git add src/poimandres/pipeline/fabrica.py tests/test_fabrica.py
git commit -m "feat(fabrica): montar_por_ambiente — toggle Claude/Local por POIMANDRES_LLM"
```

---

### Task 7: Fiar a CLI (`perguntar`/`servir`) ao seletor + `--host`

**Files:**
- Modify: `src/poimandres/cli.py`
- Test: `tests/test_cli.py`

- [ ] **Step 1: Escrever os testes que falham**

Adicione ao fim de `tests/test_cli.py` (o arquivo já usa `CliRunner` e monkeypatcha `_fazer_embeddings`; se faltar algum import no topo, acrescente `from click.testing import CliRunner`, `from poimandres import cli as cli_mod`, `from poimandres.pipeline import fabrica`):
```python
def test_perguntar_usa_montar_por_ambiente(tmp_path, monkeypatch):
    from click.testing import CliRunner

    from poimandres import cli as cli_mod
    from poimandres.corpus.embeddings import FakeEmbeddings
    from poimandres.pipeline import fabrica

    class _FinalFake:
        foi_limite = False
        texto = "eis a revelação"
        citacoes = ["ch-i-15"]
        movimentos = []

    class _OraculoFake:
        def consultar(self, buscador, fala):
            return _FinalFake()

    visto = {}

    def fake_por_ambiente(*, store, db_memoria, economico=True, base_url=None):
        visto["economico"] = economico
        return _OraculoFake()

    monkeypatch.setattr(cli_mod, "_fazer_embeddings", lambda: FakeEmbeddings())
    monkeypatch.setattr(fabrica, "montar_por_ambiente", fake_por_ambiente)

    res = CliRunner().invoke(
        cli_mod.cli, ["perguntar", "quem sou?", "--db", str(tmp_path / "c.lance")]
    )
    assert res.exit_code == 0, res.output
    assert "eis a revelação" in res.output
    assert visto["economico"] is True


def test_servir_aceita_host(tmp_path, monkeypatch):
    from click.testing import CliRunner

    from poimandres import cli as cli_mod
    from poimandres.corpus.embeddings import FakeEmbeddings
    from poimandres.pipeline import fabrica

    capturado = {}

    import poimandres.web as web_mod

    monkeypatch.setattr(cli_mod, "_fazer_embeddings", lambda: FakeEmbeddings())
    monkeypatch.setattr(fabrica, "montar_por_ambiente", lambda **kw: object())
    # criar_app é importado lazy dentro de servir (from poimandres.web import criar_app);
    # patchamos o módulo de origem para o import pegar o fake.
    monkeypatch.setattr(web_mod, "criar_app", lambda oraculo: "APP")

    def fake_run(app, host, port):
        capturado["host"] = host
        capturado["port"] = port

    import uvicorn

    monkeypatch.setattr(uvicorn, "run", fake_run)

    res = CliRunner().invoke(
        cli_mod.cli,
        ["servir", "--host", "0.0.0.0", "--porta", "9999", "--db", str(tmp_path / "c.lance")],
    )
    assert res.exit_code == 0, res.output
    assert capturado == {"host": "0.0.0.0", "port": 9999}
```

> Nota: `criar_app` continua importado lazy dentro de `servir` (preserva o `cli.py` leve para `ingest`/`buscar`); o teste patcha `poimandres.web.criar_app` no módulo de origem, então o `from poimandres.web import criar_app` de dentro de `servir` pega o fake.

- [ ] **Step 2: Rodar e ver falhar**

Run: `.venv/bin/pytest tests/test_cli.py -k "montar_por_ambiente or aceita_host" -v`
Expected: FAIL (sem `--host`; `montar_por_ambiente` não fiado).

- [ ] **Step 3: Implementar**

Em `src/poimandres/cli.py` (mantenha `criar_app` importado lazy dentro de `servir`):

(a) Substitua o corpo de `perguntar` (o trecho do `import`/`montar`/`oraculo`) por:
```python
    from poimandres.pipeline.fabrica import montar_por_ambiente

    store = CorpusStore(db, _fazer_embeddings())
    oraculo = montar_por_ambiente(
        store=store,
        db_memoria=str(Path(db).parent / "estado.db"),
        economico=economico,
    )
    final = oraculo.consultar(buscador, fala)
```
(mantenha o resto da função — a impressão de `final` — intacto).

(b) Em `servir`, adicione a opção `--host` antes de `--porta`:
```python
@click.option("--host", default="127.0.0.1", show_default=True)
```
ajuste a assinatura para `def servir(economico: bool, host: str, porta: int, db: str) -> None:` e substitua o corpo (do `import uvicorn` até o fim) por:
```python
    import uvicorn

    from poimandres.pipeline.fabrica import montar_por_ambiente

    store = CorpusStore(db, _fazer_embeddings())
    oraculo = montar_por_ambiente(
        store=store,
        db_memoria=str(Path(db).parent / "estado.db"),
        economico=economico,
    )
    import os as _os

    backend = "local" if _os.environ.get("POIMANDRES_LLM", "claude").lower() == "local" else (
        "opus" if not economico else "econômico"
    )
    click.echo(f"Poimandres no ar em http://{host}:{porta}  (backend: {backend})")
    uvicorn.run(criar_app(oraculo), host=host, port=porta)
```

- [ ] **Step 4: Rodar e ver passar**

Run: `.venv/bin/pytest tests/test_cli.py -v`
Expected: PASS (todos, incl. os antigos).

- [ ] **Step 5: Suíte inteira verde**

Run: `.venv/bin/pytest`
Expected: PASS (toda a suíte determinística; evals pulam sem credencial).

- [ ] **Step 6: Commit**

```bash
git add src/poimandres/cli.py tests/test_cli.py
git commit -m "feat(cli): perguntar/servir via montar_por_ambiente; servir --host (Docker)"
```

---

### Task 8: Script do servidor mlx-lm (host Mac/Metal)

**Files:**
- Create: `scripts/servidor-mlx.sh`

- [ ] **Step 1: Criar o script**

Crie `scripts/servidor-mlx.sh`:
```bash
#!/usr/bin/env bash
# Sobe a Gemma 4 via mlx-lm no host (Metal) para o Poimandres local.
# Uso:  ./scripts/servidor-mlx.sh                                  (26B-A4B MLX 4-bit, :8080)
#       ./scripts/servidor-mlx.sh unsloth/gemma-4-12b-it-MLX-8bit  (variante leve)
#       ./scripts/servidor-mlx.sh <modelo> <porta>
# Depois, em outro terminal:  POIMANDRES_LLM=local ./servir.sh
# Requer o extra:  uv sync --extra local-mac
set -euo pipefail
cd "$(dirname "$0")/.."
MODELO="${1:-unsloth/gemma-4-26b-a4b-it-MLX-4bit}"
PORTA="${2:-8080}"
# Dá ~20 GB ao Metal (de 24 GB unificados) p/ a 26B caber com contexto.
sudo sysctl -w iogpu.wired_limit_mb=20480 || echo "aviso: não ajustou iogpu.wired_limit_mb"
exec uv run --extra local-mac python -m mlx_lm.server --model "$MODELO" --port "$PORTA"
```

- [ ] **Step 2: Tornar executável**

Run:
```bash
chmod +x scripts/servidor-mlx.sh
```

- [ ] **Step 3: Verificar sintaxe (sem rodar — baixaria o modelo)**

Run: `bash -n scripts/servidor-mlx.sh && echo OK`
Expected: imprime `OK`.

- [ ] **Step 4: Commit**

```bash
git add scripts/servidor-mlx.sh
git commit -m "feat(local): scripts/servidor-mlx.sh — Gemma 4 via mlx-lm no host (Metal)"
```

---

### Task 9: Dockerização (app + vLLM no Linux/GPU)

**Files:**
- Create: `Dockerfile`, `docker-compose.yml`, `.dockerignore`

- [ ] **Step 1: Criar o `.dockerignore`**

Crie `.dockerignore`:
```
.git
.venv
.pytest_cache
.poimandres
**/__pycache__
tests
evals
docs
material
*.lance
```

- [ ] **Step 2: Criar o `Dockerfile`**

Crie `Dockerfile`:
```dockerfile
FROM python:3.12-slim
RUN pip install --no-cache-dir uv
WORKDIR /app
COPY pyproject.toml uv.lock ./
COPY src ./src
COPY corpus ./corpus
RUN uv sync --frozen --no-dev
EXPOSE 8000
ENV POIMANDRES_LLM=claude
CMD ["uv", "run", "poimandres", "servir", "--porta", "8000", "--host", "0.0.0.0"]
```

- [ ] **Step 3: Criar o `docker-compose.yml`**

Crie `docker-compose.yml`:
```yaml
services:
  app:
    build: .
    ports:
      - "8000:8000"
    environment:
      POIMANDRES_LLM: ${POIMANDRES_LLM:-claude}
      POIMANDRES_LOCAL_URL: ${POIMANDRES_LOCAL_URL:-}
      ANTHROPIC_API_KEY: ${ANTHROPIC_API_KEY:-}
    extra_hosts:
      - "host.docker.internal:host-gateway"

  # Perfil GPU (Linux): sobe junto com `docker compose --profile gpu up`.
  # No Mac, NÃO use este perfil — o mlx-lm roda no host (scripts/servidor-mlx.sh)
  # e o app o alcança via POIMANDRES_LOCAL_URL=http://host.docker.internal:8080/v1
  vllm:
    image: vllm/vllm-openai:latest
    profiles: ["gpu"]
    command: ["--model", "google/gemma-4-26b-a4b-it", "--port", "8000"]
    deploy:
      resources:
        reservations:
          devices:
            - driver: nvidia
              count: all
              capabilities: ["gpu"]
```

- [ ] **Step 4: Validar a sintaxe do compose**

Run: `docker compose config >/dev/null && echo OK`
Expected: imprime `OK` (valida YAML/refs; não sobe nada).
> Se o Docker não estiver instalado nesta máquina, pule a verificação e registre que o `docker compose config` deve ser rodado no alvo Linux.

- [ ] **Step 5: Commit**

```bash
git add Dockerfile docker-compose.yml .dockerignore
git commit -m "feat(docker): app dockerizado + perfil gpu (vLLM/Gemma 4 no Linux)"
```

---

### Task 10: Quickstart + log de sessão

**Files:**
- Create: `docs/llm-local.md`
- Modify: `docs/sessions/2026-06-02-domain-storytelling-log.md`

- [ ] **Step 1: Escrever o quickstart**

Crie `docs/llm-local.md`:
```markdown
# LLM local (Gemma 4) — híbrido com toggle

O oráculo roda com Claude (default) ou com Gemma 4 local. O toggle é a env
`POIMANDRES_LLM` (`claude` | `local`).

## Mac (M4) — mlx-lm no host

1. Instale o extra: `uv sync --extra local-mac`
2. Suba o servidor (baixa o modelo no 1º uso): `./scripts/servidor-mlx.sh`
   - Default: `unsloth/gemma-4-26b-a4b-it-MLX-4bit` na porta 8080.
   - Variante leve (24 GB apertados): `./scripts/servidor-mlx.sh unsloth/gemma-4-12b-it-MLX-8bit`
3. Em outro terminal: `POIMANDRES_LLM=local ./servir.sh`
   (default por plataforma já aponta a `http://127.0.0.1:8080/v1`).

## Linux com GPU NVIDIA — vLLM via Docker

```bash
POIMANDRES_LLM=local POIMANDRES_LOCAL_URL=http://vllm:8000/v1 \
  docker compose --profile gpu up
```

## Voltar ao Claude

Sem `POIMANDRES_LLM` (ou `=claude`): usa o preset econômico (Sonnet); `--opus`
para a voz plena. A voz do Mestre degrada no local — o toggle existe para isso.
```

- [ ] **Step 2: Registrar no log de sessão**

Adicione ao fim de `docs/sessions/2026-06-02-domain-storytelling-log.md` um parágrafo
`**Backend LLM local (Gemma 4) — FEITO:**` resumindo: `LocalLLM` (cliente
OpenAI-compatible; mlx-lm no Mac/Metal, vLLM no Linux/GPU), toggle por
`POIMANDRES_LLM`, thinking só no Compositor, saída sempre limpa p/ JSON, preset
`montar_oraculo_local`, `servir --host`, Docker (app + perfil gpu), e o spec/plano
em `docs/superpowers/`. Cite os commits relevantes.

- [ ] **Step 3: Commit**

```bash
git add docs/llm-local.md docs/sessions/2026-06-02-domain-storytelling-log.md
git commit -m "docs: quickstart do LLM local (Gemma 4) + log de sessão"
```

---

## Self-Review (preenchido)

**Spec coverage:**
- `LocalLLM` OpenAI-compat, schema embutido + response_format, thinking, limpeza → Tasks 2, 3. ✓
- `montar_oraculo_local` (pensar só no Compositor) → Task 5. ✓
- Toggle por env + default por plataforma + `POIMANDRES_LOCAL_URL` → Tasks 4, 6, 7. ✓
- Instalação Mac (mlx-lm, wired_limit, 26B-A4B/12B) → Tasks 1, 8, 10. ✓
- Docker (app + vLLM perfil gpu, host.docker.internal) → Task 9. ✓
- Testes sem rede (monkeypatch do cliente; FakeLLM intacto; eval manual) → Tasks 2-7. ✓
- Dep `openai`; `mlx-lm` extra opcional → Task 1. ✓

**Placeholder scan:** sem TODO/TBD; todo step de código traz o código completo. ✓

**Type/nome consistency:** `LocalLLM(base_url=, modelo=, pensar=, max_tokens=)`,
`endpoint_local_padrao()`, `resolver_url_local()`, `montar_oraculo_local(...)`,
`montar_por_ambiente(...)`, `_extrair_json`/`_limpar_pensamento` — usados de forma
idêntica entre tasks e testes. ✓
```
