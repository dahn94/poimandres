"""Backend de LLM PLUGÁVEL — interface única + um fake roteirizado para testes.

Espelha o par ``EmbeddingsBackend``/``FakeEmbeddings`` do subsistema do corpus:
o pipeline depende só da interface :class:`LLMBackend`, de modo que trocar o
``FakeLLM`` (testes) pelo Claude real (Plano 2b) — ou por um modelo local no
futuro — é questão de configuração, sem tocar nas unidades.
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import Protocol


@dataclass(frozen=True)
class PedidoLLM:
    """Um pedido ao LLM: a instrução de sistema e a mensagem do usuário.

    No Plano 2a o ``FakeLLM`` ignora o conteúdo e devolve respostas roteirizadas;
    a saída estruturada (schema/tool-use) e o prompt caching entram no 2b.
    """

    sistema: str
    usuario: str


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
