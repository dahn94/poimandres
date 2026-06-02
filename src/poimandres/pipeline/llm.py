"""Backend de LLM PLUGÁVEL — interface única + um fake roteirizado para testes.

Espelha o par ``EmbeddingsBackend``/``FakeEmbeddings`` do subsistema do corpus:
o pipeline depende só da interface :class:`LLMBackend`, de modo que trocar o
``FakeLLM`` (testes) pelo Claude real (Plano 2b) — ou por um modelo local no
futuro — é questão de configuração, sem tocar nas unidades.
"""

from __future__ import annotations

import anthropic
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
        return next(b.text for b in resposta.content if b.type == "text")
