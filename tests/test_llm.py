import pytest

from poimandres.pipeline.llm import FakeLLM, PedidoLLM


def test_fakellm_devolve_respostas_em_ordem_e_registra_chamadas():
    llm = FakeLLM(["primeira", "segunda"])
    p1 = PedidoLLM(sistema="s", usuario="u1")
    p2 = PedidoLLM(sistema="s", usuario="u2")
    assert llm.gerar(p1) == "primeira"
    assert llm.gerar(p2) == "segunda"
    assert llm.chamadas == [p1, p2]


def test_fakellm_esgotado_falha_alto():
    llm = FakeLLM([])
    with pytest.raises(AssertionError):
        llm.gerar(PedidoLLM(sistema="s", usuario="u"))


def test_pedido_carrega_schema_opcional():
    p = PedidoLLM(sistema="s", usuario="u", schema={"type": "object"})
    assert p.schema == {"type": "object"}


def test_pedido_schema_default_none():
    p = PedidoLLM(sistema="s", usuario="u")
    assert p.schema is None


class _FakeContentBlock:
    def __init__(self, tipo, text=""):
        self.type = tipo
        self.text = text


class _FakeMessage:
    def __init__(self, blocks):
        self.content = blocks


class _FakeMessages:
    def __init__(self, recorder):
        self._recorder = recorder

    def create(self, **kwargs):
        self._recorder.append(kwargs)
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

    assert texto == '{"ok": true}'
    req = fake.chamadas[0]
    assert req["model"] == "claude-opus-4-8"
    assert req["thinking"] == {"type": "adaptive"}
    assert req["output_config"]["effort"] == "high"
    assert req["output_config"]["format"]["type"] == "json_schema"
    assert req["output_config"]["format"]["schema"] == {"type": "object"}
    assert req["system"][0]["cache_control"] == {"type": "ephemeral"}
    assert req["system"][0]["text"] == "as leis"
    assert req["messages"] == [{"role": "user", "content": "quem sou?"}]


def test_claudellm_sem_schema_nao_passa_format(monkeypatch):
    from poimandres.pipeline import llm as llm_mod

    fake = _FakeClient()
    monkeypatch.setattr(llm_mod.anthropic, "Anthropic", lambda: fake)

    llm_mod.ClaudeLLM("claude-sonnet-4-6").gerar(PedidoLLM(sistema="s", usuario="u"))
    assert "format" not in fake.chamadas[0]["output_config"]


def test_claudellm_falha_sem_bloco_de_texto(monkeypatch):
    from poimandres.pipeline import llm as llm_mod

    class _SoThinking:
        content = [_FakeContentBlock("thinking", "")]

    class _MsgsSoThinking:
        def create(self, **kwargs):
            return _SoThinking()

    class _ClientSoThinking:
        def __init__(self):
            self.messages = _MsgsSoThinking()

    monkeypatch.setattr(llm_mod.anthropic, "Anthropic", lambda: _ClientSoThinking())
    with pytest.raises(RuntimeError):
        llm_mod.ClaudeLLM("claude-opus-4-8").gerar(PedidoLLM(sistema="s", usuario="u"))


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
    def __init__(self, rec, content):
        self.chat = type("C", (), {"completions": _FakeCompletions(rec, content)})()


def _patch_openai(monkeypatch, content):
    """Substitui openai.OpenAI por um fake; devolve (chamadas, ctor_kwargs)."""
    from poimandres.pipeline import llm as llm_mod

    chamadas: list[dict] = []
    ctor: dict = {}

    def fabricar(**kw):
        ctor.update(kw)
        return _FakeOpenAIClient(chamadas, content)

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
    assert req["response_format"]["json_schema"]["strict"] is True
    assert req["response_format"]["json_schema"]["schema"] == {"type": "object"}
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
