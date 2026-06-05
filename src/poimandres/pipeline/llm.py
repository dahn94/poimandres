"""Backend de LLM PLUGÁVEL — interface única + um fake roteirizado para testes.

Espelha o par ``EmbeddingsBackend``/``FakeEmbeddings`` do subsistema do corpus:
o pipeline depende só da interface :class:`LLMBackend`, de modo que trocar o
``FakeLLM`` (testes) pelo Claude real (Plano 2b) — ou por um modelo local no
futuro — é questão de configuração, sem tocar nas unidades.
"""

from __future__ import annotations

import anthropic
import json
import openai
from dataclasses import dataclass
from typing import Protocol


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


class LLMBackend(Protocol):
    """Contrato mínimo de um backend de LLM: dado um pedido, devolve texto."""

    def gerar(self, pedido: PedidoLLM) -> str: ...


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


class FakeLLM:
    """LLM roteirizado para testes: devolve respostas pré-definidas, em ordem.

    Registra cada :class:`PedidoLLM` recebido em ``chamadas`` (para asserções
    sobre o que cada unidade enviou) e falha alto se as respostas se esgotarem —
    assim um teste que dispara mais chamadas do que o previsto não passa em falso.
    """

    def __init__(self, respostas: list[str]) -> None:
        self._respostas = list(respostas)
        self.chamadas: list[PedidoLLM] = []

    def gerar(self, pedido: PedidoLLM) -> str:
        self.chamadas.append(pedido)
        if not self._respostas:
            raise AssertionError("FakeLLM: sem respostas roteirizadas restantes")
        return self._respostas.pop(0)


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
        texto = next((b.text for b in resposta.content if b.type == "text"), None)
        if texto is None:
            raise RuntimeError(
                f"ClaudeLLM: resposta sem bloco de texto — conteúdo: {resposta.content!r}"
            )
        return texto


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
