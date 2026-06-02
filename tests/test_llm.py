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
