# Poimandres — Plano 2b: O Claude real e a Condução (Implementation Plan)

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking. **Quando escrever código do SDK `anthropic`, use a skill `claude-api`.**

**Goal:** Trocar o `FakeLLM` pelo Claude real e afinar a Condução — o oráculo passa a responder ponta-a-ponta com Claude (Opus no Compositor, Sonnet no Discernidor e no juiz do Verificador), com saída estruturada, prompt caching, devolução/iluminantes/gênero fiados, e uma suíte de evals opt-in contra a API real.

**Architecture:** Um backend `ClaudeLLM` (SDK `anthropic`) implementa o mesmo `LLMBackend` do 2a; a saída estruturada vem de `output_config.format` (JSON schema), não de prefill (removido nesses modelos) nem de tool-use (lock-in). O `PedidoLLM` ganha um `schema` opcional que o `ClaudeLLM` usa e backends locais futuros podem embutir no prompt. Os 59 testes determinísticos (FakeLLM) seguem como portão de regressão; uma pasta `evals/` (marcada, pula sem `ANTHROPIC_API_KEY`) mede a fidelidade da Condução com asserções tolerantes de comportamento.

**Tech Stack:** Python 3.12, SDK `anthropic` (novo), `pytest` (+ marker `eval`). Modelos: `claude-opus-4-8` (Compositor), `claude-sonnet-4-6` (Discernidor, juiz). Adaptive thinking + `output_config.effort` + prompt caching no sistema. Reusa todo o pacote `poimandres.pipeline` do 2a.

---

## File Structure

| Arquivo | Mudança | Responsabilidade |
|---|---|---|
| `pyproject.toml` | Modificar | Adicionar `anthropic>=0.92` às deps; registrar o marker `eval`. |
| `pipeline/llm.py` | Modificar | `PedidoLLM` ganha `schema: dict|None`; novo `ClaudeLLM` (SDK, structured outputs, caching, adaptive thinking, effort). |
| `pipeline/discernidor.py` | Modificar | Prompt-sistema real (inicial) + JSON schema do `Discernimento`, passado no `PedidoLLM`. |
| `pipeline/compositor.py` | Modificar | Prompt da voz do Mestre (inicial) + schema do rascunho; inclui iluminantes; ensina `genero_declarado`/devolução. |
| `pipeline/verificador.py` | Modificar | Juiz-LLM opcional (entailment/anacronismo/gênero) após as 3 checagens determinísticas. |
| `pipeline/tipos.py` | Modificar | `RevelacaoFinal` ganha `movimentos: list[str]`. |
| `pipeline/orquestrador.py` | Modificar | Surfaca devolução (`devolveu`/`movimentos`) na `RevelacaoFinal`; injeta o juiz no Verificador. |
| `pipeline/fabrica.py` | Criar | `montar_oraculo(...)` — fia `ClaudeLLM(opus)`/`ClaudeLLM(sonnet)` + store + memória nas 5 unidades. |
| `cli.py` | Modificar | Comando `perguntar "<fala>"` para exercitar o oráculo real. |
| `evals/` | Criar | `conftest.py` (marker + skip sem chave) + `test_fidelidade.py` (casos-ouro/red-team com API real). |
| `tests/test_llm.py` … | Modificar/criar | Testes determinísticos do encanamento novo (ClaudeLLM mockado, juiz com FakeLLM, devolução, fábrica). |

**Prompts:** os `_SISTEMA_*` nascem em versão inicial fiel às leis; a afinação fina é a fase iterativa contra os `evals/` (não um checkbox).

---

### Task 1: Dependência `anthropic`, marker de eval e `schema` no PedidoLLM

**Files:**
- Modify: `pyproject.toml`
- Modify: `src/poimandres/pipeline/llm.py`
- Test: `tests/test_llm.py`

- [ ] **Step 1: Write the failing test** — adicione ao final de `tests/test_llm.py`:

```python
def test_pedido_carrega_schema_opcional():
    p = PedidoLLM(sistema="s", usuario="u", schema={"type": "object"})
    assert p.schema == {"type": "object"}


def test_pedido_schema_default_none():
    p = PedidoLLM(sistema="s", usuario="u")
    assert p.schema is None
```

- [ ] **Step 2: Run test to verify it fails**

Run: `.venv/bin/pytest tests/test_llm.py::test_pedido_carrega_schema_opcional -q`
Expected: FAIL — `TypeError: __init__() got an unexpected keyword argument 'schema'`.

- [ ] **Step 3: Add the field and the dependency**

In `src/poimandres/pipeline/llm.py`, change the `PedidoLLM` dataclass to add an optional `schema` field (keep the existing docstring; append a line about `schema`):

```python
@dataclass(frozen=True)
class PedidoLLM:
    """Um pedido ao LLM: a instrução de sistema e a mensagem do usuário.

    No Plano 2a o ``FakeLLM`` ignora o conteúdo e devolve respostas roteirizadas;
    no 2b o ``ClaudeLLM`` usa ``schema`` (quando presente) para forçar saída
    estruturada via ``output_config.format``. ``schema`` é um JSON Schema; um
    backend local futuro pode embuti-lo no prompt em vez de usar o recurso nativo.
    """

    sistema: str
    usuario: str
    schema: dict | None = None
```

In `pyproject.toml`, add `anthropic` to `dependencies` and register the `eval` marker. The `dependencies` list becomes:

```toml
dependencies = [
    "pyyaml>=6.0",
    "lancedb>=0.13",
    "sentence-transformers>=3.0",
    "click>=8.1",
    "anthropic>=0.92",
]
```

And append to `[tool.pytest.ini_options]`:

```toml
markers = [
    "eval: avaliações de fidelidade que chamam a API real do Claude (pulam sem ANTHROPIC_API_KEY)",
]
```

- [ ] **Step 4: Install and verify**

Run: `.venv/bin/pip install 'anthropic>=0.92' && .venv/bin/pytest tests/test_llm.py -q`
Expected: all pass (the two new + the existing FakeLLM tests).

- [ ] **Step 5: Commit**

```bash
git add pyproject.toml src/poimandres/pipeline/llm.py tests/test_llm.py
git commit -m "feat(2b): dependência anthropic, marker eval, schema opcional no PedidoLLM"
```
End the commit body with: `Co-Authored-By: Claude Opus 4.8 <noreply@anthropic.com>`

---

### Task 2: Backend `ClaudeLLM`

**Files:**
- Modify: `src/poimandres/pipeline/llm.py`
- Test: `tests/test_llm.py`

`ClaudeLLM` implements `LLMBackend` via the `anthropic` SDK. Per the `claude-api` skill: prompt caching on the system block; **adaptive thinking** (`thinking={"type":"adaptive"}`); `output_config={"effort": ...}` plus `format` when a schema is present; the model bound at construction (Opus for Compositor, Sonnet for the others). The test mocks the SDK client — no network.

- [ ] **Step 1: Write the failing test** — add to `tests/test_llm.py`:

```python
class _FakeContentBlock:
    def __init__(self, type, text=""):
        self.type = type
        self.text = text


class _FakeMessage:
    def __init__(self, blocks):
        self.content = blocks


class _FakeMessages:
    def __init__(self, recorder):
        self._recorder = recorder

    def create(self, **kwargs):
        self._recorder.append(kwargs)
        # Claude com adaptive thinking devolve um bloco de thinking + um de texto.
        return _FakeMessage(
            [_FakeContentBlock("thinking", ""), _FakeContentBlock("text", '{"ok": true}')]
        )


class _FakeClient:
    def __init__(self):
        self.chamadas: list[dict] = []
        self.messages = _FakeMessages(self.chamadas)


def test_claudellm_monta_request_e_extrai_texto(monkeypatch):
    from poimandres.pipeline import llm as llm_mod

    fake = _FakeClient()
    monkeypatch.setattr(llm_mod.anthropic, "Anthropic", lambda: fake)

    backend = llm_mod.ClaudeLLM("claude-opus-4-8", effort="high")
    texto = backend.gerar(
        PedidoLLM(sistema="as leis", usuario="quem sou?", schema={"type": "object"})
    )

    assert texto == '{"ok": true}'  # só o bloco de texto, não o thinking
    req = fake.chamadas[0]
    assert req["model"] == "claude-opus-4-8"
    assert req["thinking"] == {"type": "adaptive"}
    assert req["output_config"]["effort"] == "high"
    # schema vira structured output (não prefill, não tool-use)
    assert req["output_config"]["format"]["type"] == "json_schema"
    assert req["output_config"]["format"]["schema"] == {"type": "object"}
    # sistema é cacheado (prefix estável das leis do Mestre)
    assert req["system"][0]["cache_control"] == {"type": "ephemeral"}
    assert req["system"][0]["text"] == "as leis"
    # a fala vai como mensagem de usuário
    assert req["messages"] == [{"role": "user", "content": "quem sou?"}]


def test_claudellm_sem_schema_nao_passa_format(monkeypatch):
    from poimandres.pipeline import llm as llm_mod

    fake = _FakeClient()
    monkeypatch.setattr(llm_mod.anthropic, "Anthropic", lambda: fake)

    llm_mod.ClaudeLLM("claude-sonnet-4-6").gerar(PedidoLLM(sistema="s", usuario="u"))
    assert "format" not in fake.chamadas[0]["output_config"]
```

- [ ] **Step 2: Run test to verify it fails**

Run: `.venv/bin/pytest tests/test_llm.py::test_claudellm_monta_request_e_extrai_texto -q`
Expected: FAIL — `AttributeError: module 'poimandres.pipeline.llm' has no attribute 'anthropic'` (or `ClaudeLLM` undefined).

- [ ] **Step 3: Implement `ClaudeLLM`**

In `src/poimandres/pipeline/llm.py`, add `import anthropic` at the top (after `from __future__ import annotations`), and append the class:

```python
class ClaudeLLM:
    """Backend real (Claude API). Mesmo contrato ``LLMBackend`` do ``FakeLLM``.

    O modelo é fixado na construção (injeção de dependência: Opus no Compositor,
    Sonnet no Discernidor/juiz). Saída estruturada via ``output_config.format``
    quando o pedido traz ``schema`` — Claude garante JSON válido contra o schema,
    sem prefill (removido nesses modelos) nem tool-use. O bloco de sistema é
    cacheado (as leis do Mestre são longas e estáveis entre turnos).
    """

    def __init__(
        self, modelo: str, *, max_tokens: int = 8192, effort: str = "high"
    ) -> None:
        self._client = anthropic.Anthropic()
        self._modelo = modelo
        self._max_tokens = max_tokens
        self._effort = effort

    def gerar(self, pedido: PedidoLLM) -> str:
        output_config: dict = {"effort": self._effort}
        if pedido.schema is not None:
            output_config["format"] = {
                "type": "json_schema",
                "schema": pedido.schema,
            }
        resposta = self._client.messages.create(
            model=self._modelo,
            max_tokens=self._max_tokens,
            system=[
                {
                    "type": "text",
                    "text": pedido.sistema,
                    "cache_control": {"type": "ephemeral"},
                }
            ],
            thinking={"type": "adaptive"},
            output_config=output_config,
            messages=[{"role": "user", "content": pedido.usuario}],
        )
        return next(b.text for b in resposta.content if b.type == "text")
```

- [ ] **Step 4: Run test to verify it passes**

Run: `.venv/bin/pytest tests/test_llm.py -q`
Expected: all pass.

- [ ] **Step 5: Commit**

```bash
git add src/poimandres/pipeline/llm.py tests/test_llm.py
git commit -m "feat(2b): ClaudeLLM (structured outputs, caching, adaptive thinking, effort)"
```
End the commit body with: `Co-Authored-By: Claude Opus 4.8 <noreply@anthropic.com>`

---

### Task 3: Discernidor — prompt real + schema

**Files:**
- Modify: `src/poimandres/pipeline/discernidor.py`
- Test: `tests/test_discernidor.py`

Give the Discernidor a real (initial) system prompt and a JSON schema for its structured output, passed via `PedidoLLM.schema`. Behavior (parsing) is unchanged — the existing FakeLLM tests still pass; one new test asserts the schema is sent.

- [ ] **Step 1: Write the failing test** — add to `tests/test_discernidor.py`:

```python
def test_discernidor_envia_schema_estruturado():
    llm = FakeLLM([_RESP])
    Discernidor(llm).discernir("uma fala")
    pedido = llm.chamadas[0]
    assert pedido.schema is not None
    assert pedido.schema["type"] == "object"
    # as 4 marcas estão nas propriedades exigidas do schema
    marcas = pedido.schema["properties"]["marcas"]["properties"]
    assert set(marcas) == {
        "reconhecimento_de_si",
        "pureza",
        "reta_intencao",
        "capacidade_de_receber",
    }
```

- [ ] **Step 2: Run test to verify it fails**

Run: `.venv/bin/pytest tests/test_discernidor.py::test_discernidor_envia_schema_estruturado -q`
Expected: FAIL — `assert None is not None` (schema not yet sent).

- [ ] **Step 3: Add the schema and the real prompt**

In `src/poimandres/pipeline/discernidor.py`, replace the `_SISTEMA` constant with the initial real prompt and add a `_SCHEMA`, then pass `schema=_SCHEMA` in the `PedidoLLM`:

```python
_SISTEMA = (
    "Você assiste um oráculo hermético clássico lendo a DISPOSIÇÃO interior de "
    "um buscador a partir da fala dele — não para julgá-lo, mas para que o Mestre "
    "saiba até que profundidade conduzir. Leis: (1) você lê só o que se manifesta "
    "no diálogo, com humildade — cada marca vem com uma incerteza; (2) os dois "
    "trilhos são desacoplados: ignorância de vocabulário (lingua_ausente) NÃO é "
    "despreparo da alma; (3) o grau é emergente e re-sondado a cada turno, sem "
    "currículo fixo. Devolva as 4 marcas da Disposição (reconhecimento_de_si, "
    "pureza, reta_intencao, capacidade_de_receber), cada uma com valor e incerteza "
    "em 0..1; o registro (lugar no espectro existencial↔doutrinal); o grau cabível "
    "agora (inteiro ≥ 1); lingua_ausente; e_retorno."
)

_MARCA_SCHEMA = {
    "type": "object",
    "properties": {
        "valor": {"type": "number"},
        "incerteza": {"type": "number"},
    },
    "required": ["valor", "incerteza"],
    "additionalProperties": False,
}

_SCHEMA = {
    "type": "object",
    "properties": {
        "registro": {"type": "string"},
        "marcas": {
            "type": "object",
            "properties": {nome: _MARCA_SCHEMA for nome in MARCAS},
            "required": list(MARCAS),
            "additionalProperties": False,
        },
        "grau": {"type": "integer"},
        "lingua_ausente": {"type": "boolean"},
        "e_retorno": {"type": "boolean"},
    },
    "required": ["registro", "marcas", "grau", "lingua_ausente", "e_retorno"],
    "additionalProperties": False,
}
```

Then in `discernir`, change the `PedidoLLM(...)` construction to pass the schema:

```python
        bruto = self._llm.gerar(
            PedidoLLM(sistema=_SISTEMA, usuario=fala + contexto, schema=_SCHEMA)
        )
```

- [ ] **Step 4: Run test to verify it passes**

Run: `.venv/bin/pytest tests/test_discernidor.py -q`
Expected: all pass (the 3 existing + the new schema test).

- [ ] **Step 5: Commit**

```bash
git add src/poimandres/pipeline/discernidor.py tests/test_discernidor.py
git commit -m "feat(2b): Discernidor — prompt real + JSON schema da saída estruturada"
```
End the commit body with: `Co-Authored-By: Claude Opus 4.8 <noreply@anthropic.com>`

---

### Task 4: Compositor — voz do Mestre + schema + iluminantes + gênero

**Files:**
- Modify: `src/poimandres/pipeline/compositor.py`
- Test: `tests/test_compositor.py`

Give the Compositor the initial Master-voice prompt, a JSON schema for the draft, an iluminantes block in the request, and explicit teaching of `genero_declarado` and devolution. Parsing is unchanged; new tests assert the schema and the iluminantes block.

- [ ] **Step 1: Write the failing tests** — add to `tests/test_compositor.py` (note: `_REC` there has empty `iluminantes`; this test builds one with an iluminante):

```python
def test_compositor_envia_schema_estruturado():
    llm = FakeLLM([_RESP])
    Compositor(llm).compor(_DISC, _REC)
    pedido = llm.chamadas[0]
    assert pedido.schema is not None
    assert "afirmacoes" in pedido.schema["properties"]


def test_compositor_inclui_iluminantes_no_pedido():
    rec = Recuperacao(
        fundantes=_REC.fundantes,
        iluminantes=[
            Passagem(
                id="coment-15",
                ref_canonica="Coment. §15",
                texto="o homem duplo na tradição órfica",
                proveniencia=Proveniencia.ERUDICAO,
                obra="Comentário",
            )
        ],
    )
    llm = FakeLLM([_RESP])
    Compositor(llm).compor(_DISC, rec)
    usuario = llm.chamadas[0].usuario
    assert "ILUMINANTES" in usuario
    assert "coment-15" in usuario
```

- [ ] **Step 2: Run test to verify it fails**

Run: `.venv/bin/pytest tests/test_compositor.py::test_compositor_envia_schema_estruturado -q`
Expected: FAIL — `assert None is not None`.

- [ ] **Step 3: Real prompt, schema, iluminantes block**

In `src/poimandres/pipeline/compositor.py`, replace `_SISTEMA` with the initial Master-voice prompt, add `_SCHEMA`, include an iluminantes block in `usuario`, and pass the schema. Replace the constant and the `compor` body's request-building:

```python
_SISTEMA = (
    "Você é o MESTRE de um oráculo hermético clássico, que conduz como Hermes "
    "conduz Tat: sonda, devolve, revela por graus, pode adiar. Leis invioláveis:\n"
    "1. FUNDAR só nas passagens FUNDANTES dadas; toda afirmação doutrinal traz o "
    "citacao_id da fundante que a sustenta. Nunca funde no que não foi dado.\n"
    "2. GRAU: revele apenas até a profundidade que a Disposição autoriza (use o "
    "grau e as 4 marcas como leitura, não como nota); guarde/adie o mais alto, "
    "aponte o caminho sem despejar.\n"
    "3. LÍNGUA: se lingua_ausente, entre pela Imagem, depois Nomeie o termo, "
    "depois Glose — guardando do anacronismo.\n"
    "4. ILUMINANTES (erudição) só ILUMINAM, marcadas como tal; jamais fundam.\n"
    "5. Pode DEVOLVER uma pergunta/Movimento em vez de revelar (devolveu=true, "
    "movimentos=[...]).\n"
    "6. Se houver só suporte técnico (so_tecnico), DECLARE o gênero "
    "(genero_declarado=true) em vez de tratá-lo como doutrina.\n"
    "Devolva JSON: {texto, afirmacoes:[{frase,citacao_id}], movimentos:[...], "
    "devolveu, genero_declarado}."
)

_AFIRMACAO_SCHEMA = {
    "type": "object",
    "properties": {
        "frase": {"type": "string"},
        "citacao_id": {"type": "string"},
    },
    "required": ["frase", "citacao_id"],
    "additionalProperties": False,
}

_SCHEMA = {
    "type": "object",
    "properties": {
        "texto": {"type": "string"},
        "afirmacoes": {"type": "array", "items": _AFIRMACAO_SCHEMA},
        "movimentos": {"type": "array", "items": {"type": "string"}},
        "devolveu": {"type": "boolean"},
        "genero_declarado": {"type": "boolean"},
    },
    "required": ["texto", "afirmacoes", "movimentos", "devolveu", "genero_declarado"],
    "additionalProperties": False,
}
```

Then rewrite the body of `compor` (keep the signature and docstring) so it includes iluminantes, passes the schema, and parses `movimentos`:

```python
        fundantes = "\n".join(f"{p.id}: {p.texto}" for p in recuperacao.fundantes)
        iluminantes = "\n".join(
            f"{p.id} ({p.obra}): {p.texto}" for p in recuperacao.iluminantes
        )
        usuario = (
            f"grau={discernimento.grau} registro={discernimento.registro} "
            f"lingua_ausente={discernimento.lingua_ausente}\n"
            f"silencio={recuperacao.silencio} so_tecnico={recuperacao.so_tecnico}\n"
            f"FUNDANTES (podem fundar):\n{fundantes}\n"
            f"ILUMINANTES (só iluminam, nunca fundam):\n{iluminantes}"
        )
        if violacoes:
            usuario += "\n[REFAÇA — violações: " + "; ".join(violacoes) + "]"
        bruto = self._llm.gerar(
            PedidoLLM(sistema=_SISTEMA, usuario=usuario, schema=_SCHEMA)
        )
        dados = json.loads(bruto)
        afirmacoes = [
            Afirmacao(frase=a["frase"], citacao_id=a["citacao_id"])
            for a in dados.get("afirmacoes", [])
        ]
        movimentos = [Movimento(pedido=m) for m in dados.get("movimentos", [])]
        return RascunhoRevelacao(
            texto=str(dados["texto"]),
            afirmacoes=afirmacoes,
            movimentos=movimentos,
            devolveu=bool_ou_default(dados, "devolveu", False),
            genero_declarado=bool_ou_default(dados, "genero_declarado", False),
        )
```

Update the imports at the top of `compositor.py` to include `Movimento` (from `poimandres.pipeline.tipos`). The import block becomes:

```python
from poimandres.pipeline.tipos import (
    Afirmacao,
    Discernimento,
    Movimento,
    RascunhoRevelacao,
    Recuperacao,
)
```

(`_RESP` in the test already omits `movimentos`; `dados.get("movimentos", [])` yields `[]`, so existing tests stay green.)

- [ ] **Step 4: Run test to verify it passes**

Run: `.venv/bin/pytest tests/test_compositor.py -q`
Expected: all pass (existing + 2 new).

- [ ] **Step 5: Commit**

```bash
git add src/poimandres/pipeline/compositor.py tests/test_compositor.py
git commit -m "feat(2b): Compositor — voz do Mestre, schema, iluminantes, gênero, movimentos"
```
End the commit body with: `Co-Authored-By: Claude Opus 4.8 <noreply@anthropic.com>`

---

### Task 5: Verificador — juiz-LLM (entailment, anacronismo, gênero)

**Files:**
- Modify: `src/poimandres/pipeline/verificador.py`
- Test: `tests/test_verificador.py`

Add an optional LLM-judge. `Verificador(juiz=None)` keeps 2a behavior (deterministic only). When a `juiz: LLMBackend` is injected AND the deterministic checks pass, the judge evaluates each affirmation against its cited fundante's text (entailment) plus anachronism/genre, returning extra violations.

- [ ] **Step 1: Write the failing tests** — add to `tests/test_verificador.py`:

```python
import json

from poimandres.pipeline.llm import FakeLLM


def test_juiz_nao_e_chamado_quando_deterministico_ja_reprova():
    # citação inexistente → reprova determinístico; juiz nem deve ser consultado
    llm = FakeLLM([])  # vazio: se for chamado, levanta AssertionError
    rasc = RascunhoRevelacao(texto="x", afirmacoes=[Afirmacao("x", "nao-existe")])
    v = Verificador(juiz=llm).verificar(rasc, _rec())
    assert v.aprovado is False
    assert llm.chamadas == []


def test_juiz_reprova_quando_passagem_nao_sustenta():
    veredito_juiz = json.dumps(
        {"violacoes": ["a passagem ch-i-15 não sustenta 'a alma é tripartite'"]}
    )
    llm = FakeLLM([veredito_juiz])
    rasc = RascunhoRevelacao(
        texto="...", afirmacoes=[Afirmacao("a alma é tripartite", "ch-i-15")]
    )
    v = Verificador(juiz=llm).verificar(rasc, _rec())
    assert v.aprovado is False
    assert any("não sustenta" in viol for viol in v.violacoes)


def test_juiz_aprova_quando_sem_violacoes():
    llm = FakeLLM([json.dumps({"violacoes": []})])
    rasc = RascunhoRevelacao(
        texto="...", afirmacoes=[Afirmacao("o homem é duplo", "ch-i-15")]
    )
    assert Verificador(juiz=llm).verificar(rasc, _rec()).aprovado is True


def test_sem_juiz_mantem_comportamento_2a():
    rasc = RascunhoRevelacao(
        texto="...", afirmacoes=[Afirmacao("o homem é duplo", "ch-i-15")]
    )
    assert Verificador().verificar(rasc, _rec()).aprovado is True
```

- [ ] **Step 2: Run test to verify it fails**

Run: `.venv/bin/pytest tests/test_verificador.py::test_juiz_reprova_quando_passagem_nao_sustenta -q`
Expected: FAIL — `TypeError: __init__() got an unexpected keyword argument 'juiz'`.

- [ ] **Step 3: Add the judge**

In `src/poimandres/pipeline/verificador.py`, add imports and the judge. Replace the file's import section and class with:

```python
from __future__ import annotations

import json

from poimandres.pipeline.llm import LLMBackend, PedidoLLM
from poimandres.pipeline.tipos import RascunhoRevelacao, Recuperacao, Verificacao

_SISTEMA_JUIZ = (
    "Você verifica a fidelidade de uma resposta de um oráculo hermético clássico. "
    "Para cada afirmação, recebe a FRASE e o TEXTO da passagem fundante citada. "
    "Reprove (liste a violação) quando: a passagem NÃO sustenta a frase (alucinação "
    "de entailment); um termo técnico/moderno foi usado sem glosa (anacronismo); ou "
    "houve confusão de gênero. Devolva JSON {violacoes: [string]} — lista vazia se "
    "tudo se sustenta."
)


class Verificador:
    """Faz cumprir as leis verificáveis: 3 checagens determinísticas + juiz-LLM opcional.

    Sem ``juiz`` (Plano 2a), só as checagens determinísticas rodam. Com um ``juiz``
    injetado (Plano 2b), e SÓ se as determinísticas passarem, o juiz avalia
    entailment/anacronismo/gênero e acrescenta violações ao veredito.
    """

    def __init__(self, juiz: LLMBackend | None = None) -> None:
        self._juiz = juiz

    def verificar(
        self, rascunho: RascunhoRevelacao, recuperacao: Recuperacao
    ) -> Verificacao:
        """Aplica as checagens determinísticas e, se passarem, o juiz-LLM.

        Lei nº4 (autoridade) + nº5 (limites): só primárias fundam; sem fundante,
        confessa-se silêncio; suporte só-técnico é declarado como tal; e a citação
        precisa de fato SUSTENTAR a frase (juiz).
        """
        violacoes: list[str] = []
        # As checagens acumulam de forma independente (sem short-circuit): cada uma
        # reporta sua própria verdade. Sob silêncio, p.ex., uma afirmação citada pode
        # disparar tanto (1) quanto (2) — é intencional; o retry do Compositor lida
        # com múltiplas violações.
        ids_fundantes = {p.id for p in recuperacao.fundantes}

        for af in rascunho.afirmacoes:
            if af.citacao_id not in ids_fundantes:
                violacoes.append(f"citação inexistente nos fundantes: {af.citacao_id}")

        if recuperacao.silencio and rascunho.afirmacoes:
            violacoes.append(
                "afirmação doutrinal sob silêncio (nenhuma primária funda o tema)"
            )

        if recuperacao.so_tecnico and not rascunho.genero_declarado:
            violacoes.append("suporte só-técnico sem declaração de gênero")

        # Juiz-LLM: só quando o determinístico passou (evita pedir entailment de uma
        # citação que nem existe) e há um juiz injetado.
        if not violacoes and self._juiz is not None and rascunho.afirmacoes:
            violacoes.extend(self._julgar(rascunho, recuperacao))

        return Verificacao(aprovado=not violacoes, violacoes=violacoes)

    def _julgar(
        self, rascunho: RascunhoRevelacao, recuperacao: Recuperacao
    ) -> list[str]:
        """Consulta o juiz-LLM sobre entailment/anacronismo/gênero das afirmações."""
        por_id = {p.id: p.texto for p in recuperacao.fundantes}
        pares = "\n".join(
            f"- FRASE: {af.frase}\n  PASSAGEM ({af.citacao_id}): {por_id.get(af.citacao_id, '')}"
            for af in rascunho.afirmacoes
        )
        bruto = self._juiz.gerar(
            PedidoLLM(
                sistema=_SISTEMA_JUIZ,
                usuario=pares,
                schema={
                    "type": "object",
                    "properties": {
                        "violacoes": {"type": "array", "items": {"type": "string"}}
                    },
                    "required": ["violacoes"],
                    "additionalProperties": False,
                },
            )
        )
        return list(json.loads(bruto).get("violacoes", []))
```

- [ ] **Step 4: Run test to verify it passes**

Run: `.venv/bin/pytest tests/test_verificador.py -q`
Expected: all pass (the 5 existing + 4 new).

- [ ] **Step 5: Commit**

```bash
git add src/poimandres/pipeline/verificador.py tests/test_verificador.py
git commit -m "feat(2b): Verificador — juiz-LLM (entailment/anacronismo/gênero) após o determinístico"
```
End the commit body with: `Co-Authored-By: Claude Opus 4.8 <noreply@anthropic.com>`

---

### Task 6: Devolução — `RevelacaoFinal.movimentos` + Orquestrador

**Files:**
- Modify: `src/poimandres/pipeline/tipos.py`
- Modify: `src/poimandres/pipeline/orquestrador.py`
- Modify: `src/poimandres/pipeline/__init__.py` (nada a mudar — `RevelacaoFinal` já é re-exportada)
- Test: `tests/test_orquestrador.py`

`RevelacaoFinal` gains `movimentos: list[str]`. The Orquestrador, on an approved turn, surfaces the draft's movimentos (the Master's devolution) into the final. A devolution (no afirmacoes) under non-silence is a valid turn.

- [ ] **Step 1: Write the failing test** — add to `tests/test_orquestrador.py`:

```python
def test_devolucao_surfaca_movimentos(tmp_path):
    devolve = json.dumps(
        {
            "texto": "Antes de responder: o que você já entregou ao buscar isto?",
            "afirmacoes": [],
            "movimentos": ["observe o que move sua pergunta"],
            "devolveu": True,
            "genero_declarado": False,
        }
    )
    orac = _oraculo(tmp_path, [_DISC, devolve])
    final = orac.consultar("b1", "o que é a gnose?")
    assert final.foi_limite is False
    assert final.movimentos == ["observe o que move sua pergunta"]
    assert final.citacoes == []
```

- [ ] **Step 2: Run test to verify it fails**

Run: `.venv/bin/pytest tests/test_orquestrador.py::test_devolucao_surfaca_movimentos -q`
Expected: FAIL — `TypeError: __init__() got an unexpected keyword argument 'movimentos'` (RevelacaoFinal has no movimentos yet).

- [ ] **Step 3: Add the field and surface it**

In `src/poimandres/pipeline/tipos.py`, add `movimentos` to `RevelacaoFinal`:

```python
@dataclass(frozen=True)
class RevelacaoFinal:
    """A Revelação entregue ao Buscador e registrada na Memória.

    ``foi_limite`` indica que o Mestre rebaixou a resposta a uma confissão de
    limite (silêncio/recusa) em vez de revelar — nunca uma resposta infiel.
    ``movimentos`` carrega o que o Mestre pediu quando DEVOLVEU em vez de revelar.
    """

    texto: str
    citacoes: list[str] = field(default_factory=list)
    foi_limite: bool = False
    movimentos: list[str] = field(default_factory=list)
```

In `src/poimandres/pipeline/orquestrador.py`, in `consultar`, build the approved `RevelacaoFinal` carrying the movimentos:

```python
            if veredito.aprovado:
                final = RevelacaoFinal(
                    texto=rascunho.texto,
                    citacoes=[a.citacao_id for a in rascunho.afirmacoes],
                    foi_limite=False,
                    movimentos=[m.pedido for m in rascunho.movimentos],
                )
                self.memoria.registrar_turno(buscador_id, fala, final)
                return final
```

- [ ] **Step 4: Run test to verify it passes**

Run: `.venv/bin/pytest tests/test_orquestrador.py -q`
Expected: all pass (the existing + new). Run `.venv/bin/pytest tests/test_pipeline_tipos.py -q` too — still green (new field has a default).

- [ ] **Step 5: Commit**

```bash
git add src/poimandres/pipeline/tipos.py src/poimandres/pipeline/orquestrador.py tests/test_orquestrador.py
git commit -m "feat(2b): devolução — RevelacaoFinal.movimentos surfaçada pelo Orquestrador"
```
End the commit body with: `Co-Authored-By: Claude Opus 4.8 <noreply@anthropic.com>`

---

### Task 7: Fábrica do oráculo + CLI `perguntar`

**Files:**
- Create: `src/poimandres/pipeline/fabrica.py`
- Modify: `src/poimandres/cli.py`
- Test: `tests/test_fabrica.py`

`montar_oraculo` wires real Claude backends into the units (Opus → Compositor; Sonnet → Discernidor and the Verificador judge), plus the `CorpusStore` and `Memoria`. The factory is tested by injecting fakes for the backend constructor (no network). A CLI command `perguntar` exercises the real oracle.

- [ ] **Step 1: Write the failing test** — create `tests/test_fabrica.py`:

```python
from poimandres.corpus.embeddings import FakeEmbeddings
from poimandres.corpus.store import CorpusStore
from poimandres.pipeline.fabrica import montar_oraculo
from poimandres.pipeline.llm import FakeLLM
from poimandres.pipeline.orquestrador import Oraculo


def test_monta_oraculo_com_backend_injetado(tmp_path):
    store = CorpusStore(str(tmp_path / "c.lance"), FakeEmbeddings())
    # injeta uma fábrica de LLM falsa para não tocar a rede
    criados = []

    def fazer_llm(modelo):
        criados.append(modelo)
        return FakeLLM([])

    oraculo = montar_oraculo(
        store=store,
        db_memoria=str(tmp_path / "estado.db"),
        fazer_llm=fazer_llm,
    )
    assert isinstance(oraculo, Oraculo)
    # Opus para o Compositor; Sonnet para Discernidor e juiz do Verificador
    assert "claude-opus-4-8" in criados
    assert "claude-sonnet-4-6" in criados
```

- [ ] **Step 2: Run test to verify it fails**

Run: `.venv/bin/pytest tests/test_fabrica.py -q`
Expected: FAIL — `ModuleNotFoundError: No module named 'poimandres.pipeline.fabrica'`.

- [ ] **Step 3: Implement the factory**

Create `src/poimandres/pipeline/fabrica.py`:

```python
"""Fábrica do oráculo — fia os backends de LLM nas 5 unidades do pipeline.

Concentra a injeção de dependência do Plano 2b: Opus 4.8 (a voz do Mestre) no
Compositor; Sonnet 4.6 (rápido, estruturado) no Discernidor e no juiz do
Verificador. ``fazer_llm`` é injetável para que os testes não toquem a rede.
"""

from __future__ import annotations

from collections.abc import Callable

from poimandres.corpus.store import CorpusStore
from poimandres.pipeline.compositor import Compositor
from poimandres.pipeline.discernidor import Discernidor
from poimandres.pipeline.llm import ClaudeLLM, LLMBackend
from poimandres.pipeline.memoria import Memoria
from poimandres.pipeline.orquestrador import Oraculo
from poimandres.pipeline.recuperador import Recuperador
from poimandres.pipeline.verificador import Verificador

_MODELO_MESTRE = "claude-opus-4-8"
_MODELO_RAPIDO = "claude-sonnet-4-6"


def montar_oraculo(
    *,
    store: CorpusStore,
    db_memoria: str,
    fazer_llm: Callable[[str], LLMBackend] = ClaudeLLM,
    max_retries: int = 2,
) -> Oraculo:
    """Constrói um :class:`Oraculo` pronto para responder com Claude.

    Args:
        store: índice do corpus já ingerido.
        db_memoria: caminho do SQLite de estado.
        fazer_llm: fábrica de backend por modelo (injetável nos testes).
        max_retries: tentativas do Compositor antes do limite honesto.
    """
    return Oraculo(
        discernidor=Discernidor(fazer_llm(_MODELO_RAPIDO)),
        recuperador=Recuperador(store),
        compositor=Compositor(fazer_llm(_MODELO_MESTRE)),
        verificador=Verificador(juiz=fazer_llm(_MODELO_RAPIDO)),
        memoria=Memoria(db_memoria),
        max_retries=max_retries,
    )
```

In `src/poimandres/cli.py`, add the `perguntar` command (after `buscar`). It uses the default `_DB_PADRAO` LanceDB store and a sibling SQLite path:

```python
@cli.command()
@click.argument("fala")
@click.option("--buscador", default="anon", show_default=True)
@click.option("--db", default=_DB_PADRAO, show_default=True)
def perguntar(fala: str, buscador: str, db: str) -> None:
    """Conduz um turno do oráculo (Claude real) para a FALA do buscador.

    Requer ``ANTHROPIC_API_KEY`` no ambiente. Usa o índice em ``--db``.
    """
    from poimandres.pipeline.fabrica import montar_oraculo

    store = CorpusStore(db, _fazer_embeddings())
    oraculo = montar_oraculo(store=store, db_memoria=".poimandres/estado.db")
    final = oraculo.consultar(buscador, fala)
    if final.foi_limite:
        click.echo(f"[limite] {final.texto}")
    else:
        click.echo(final.texto)
        for cit in final.citacoes:
            click.echo(f"  — funda em {cit}")
        for mov in final.movimentos:
            click.echo(f"  → {mov}")
```

- [ ] **Step 4: Run test to verify it passes**

Run: `.venv/bin/pytest tests/test_fabrica.py -q`
Expected: `1 passed`.

- [ ] **Step 5: Commit**

```bash
git add src/poimandres/pipeline/fabrica.py src/poimandres/cli.py tests/test_fabrica.py
git commit -m "feat(2b): fábrica do oráculo + CLI 'perguntar'"
```
End the commit body with: `Co-Authored-By: Claude Opus 4.8 <noreply@anthropic.com>`

---

### Task 8: Harness de evals (API real, opt-in)

**Files:**
- Create: `evals/__init__.py` (vazio)
- Create: `evals/conftest.py`
- Create: `evals/test_fidelidade.py`
- Modify: `pyproject.toml` (já tem o marker da Task 1; adicionar `evals` ao testpaths NÃO — evals ficam fora do testpaths padrão para não rodar no portão de regressão)

The eval suite uses the **real** Claude API via the factory + real corpus (`FakeEmbeddings` keeps retrieval deterministic and free; only the LLM is real). Marked `eval` and skipped without `ANTHROPIC_API_KEY`. Assertions are **tolerant of behavior**, never exact text. These are run manually (`pytest evals/ -m eval`), not in the default suite.

- [ ] **Step 1: Write the eval conftest** — create `evals/conftest.py`:

```python
import os

import pytest


def pytest_collection_modifyitems(config, items):
    """Pula todos os evals quando não há ANTHROPIC_API_KEY (sem chave, sem rede)."""
    if os.environ.get("ANTHROPIC_API_KEY"):
        return
    skip = pytest.mark.skip(reason="evals exigem ANTHROPIC_API_KEY")
    for item in items:
        item.add_marker(skip)
```

Create `evals/__init__.py` (empty file).

- [ ] **Step 2: Write the fidelity evals** — create `evals/test_fidelidade.py`:

```python
"""Evals de fidelidade — chamam o Claude real (pulam sem ANTHROPIC_API_KEY).

Asserções TOLERANTES de comportamento (foi_limite, proveniência das citações,
veredito), nunca igualdade de texto: o modelo é não-determinístico. O corpus é o
real (corpus/) com FakeEmbeddings (recuperação determinística e grátis); só o LLM
é real. Rode com: .venv/bin/pytest evals/ -m eval -v
"""

from pathlib import Path

import pytest

from poimandres.corpus.embeddings import FakeEmbeddings
from poimandres.corpus.ingest import ingerir_pasta
from poimandres.corpus.store import CorpusStore
from poimandres.pipeline.fabrica import montar_oraculo

CORPUS = Path(__file__).resolve().parents[1] / "corpus"

pytestmark = pytest.mark.eval


@pytest.fixture
def oraculo(tmp_path):
    store = CorpusStore(str(tmp_path / "c.lance"), FakeEmbeddings())
    ingerir_pasta(CORPUS, store)
    return montar_oraculo(store=store, db_memoria=str(tmp_path / "estado.db"))


def test_recusa_o_kybalion(oraculo):
    final = oraculo.consultar("e1", "o que o Kybalion ensina sobre o mentalismo?")
    # ou confessa limite, ou só funda em primárias do CH — nunca no excluído
    assert final.foi_limite or all(c.startswith("ch-i-") for c in final.citacoes)


def test_pergunta_existencial_funda_ou_conduz(oraculo):
    final = oraculo.consultar("e2", "o que sou eu diante da morte?")
    # responde fundado em primária, OU devolve/conduz (movimentos) — nunca infiel
    assert final.foi_limite or final.citacoes or final.movimentos


def test_isca_sincretica_nao_funda_em_lei_da_atracao(oraculo):
    final = oraculo.consultar(
        "e3", "o hermetismo não é a mesma coisa que a Lei da Atração?"
    )
    assert final.foi_limite or all(c.startswith("ch-i-") for c in final.citacoes)
```

- [ ] **Step 3: Run the evals (skips without a key)**

Run (no key): `.venv/bin/pytest evals/ -q`
Expected: `3 skipped` (no `ANTHROPIC_API_KEY`).

Run (with key, manual): `ANTHROPIC_API_KEY=… .venv/bin/pytest evals/ -m eval -v`
Expected: `3 passed` (tolerant assertions). This spends tokens — run intentionally.

- [ ] **Step 4: Confirm the regression suite is unaffected**

Run: `.venv/bin/pytest -q`
Expected: all the deterministic tests pass; `evals/` is NOT collected by the default run (it's outside `testpaths = ["tests"]`).

- [ ] **Step 5: Commit**

```bash
git add evals/
git commit -m "test(2b): harness de evals de fidelidade (API real, opt-in, asserções tolerantes)"
```
End the commit body with: `Co-Authored-By: Claude Opus 4.8 <noreply@anthropic.com>`

---

## Self-Review (preenchido)

**Cobertura do spec do 2b:**
- §2 ClaudeLLM (structured outputs, caching, modelo por injeção, adaptive thinking) → Tasks 1, 2. ✓ (prefill corrigido para `output_config.format`).
- §3 Discernidor real → Task 3; Compositor (voz do Mestre, grau, língua, devolução, gênero, iluminantes) → Task 4; juiz do Verificador → Task 5. ✓
- §4 Fiação das postergações: devolução → Task 6; iluminantes → Task 4; `genero_declarado` → Task 4. ✓
- §5 Fábrica + CLI `perguntar` → Task 7. ✓
- §6 Stack (`anthropic`, modelos, caching) → Tasks 1, 2. ✓
- §7 Testes em dois níveis: determinístico (FakeLLM/SDK mockado) em todas as tasks; evals opt-in → Task 8. ✓
- **Afinação fina dos prompts** = fase iterativa contra os evals (começa aqui, não "termina"): os `_SISTEMA_*` são iniciais, por decisão. Não é lacuna.

**Placeholders:** nenhum passo deixa código por preencher; os prompts são textos reais (iniciais), o que o spec definiu explicitamente. ✓

**Consistência de tipos/assinaturas:** `PedidoLLM(sistema, usuario, schema=None)`; `ClaudeLLM(modelo, *, max_tokens, effort).gerar`; `Discernidor`/`Compositor` passam `schema=`; `Verificador(juiz=None).verificar`; `Movimento(pedido)`; `RascunhoRevelacao.movimentos`; `RevelacaoFinal.movimentos`; `montar_oraculo(*, store, db_memoria, fazer_llm=ClaudeLLM, max_retries=2)`. Usados de forma idêntica entre tasks e testes. ✓

**Riscos conhecidos (para a fase de eval, não bloqueiam o plano):** os prompts iniciais quase certamente precisarão de afinação; o juiz-LLM pode ser conservador/severo demais (calibrar contra evals); custo por turno (3 chamadas: Discernidor + Compositor + juiz) — caching no sistema mitiga.
