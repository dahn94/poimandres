"""① Discernidor — lê a fala do Buscador num :class:`Discernimento` estruturado.

Chama o :class:`~poimandres.pipeline.llm.LLMBackend` pedindo uma leitura das 4
marcas da Disposição (cada uma COM incerteza — lei nº7), do Registro, do Grau
cabível agora e dos sinais de língua-ausente/retorno; depois PARSEIA essa saída
estruturada (JSON) no tipo de domínio. No Plano 2a o prompt é mínimo e o
``FakeLLM`` devolve o JSON; afiná-lo é trabalho do Plano 2b.
"""

from __future__ import annotations

import json

from poimandres.pipeline.llm import LLMBackend, PedidoLLM
from poimandres.pipeline.tipos import Discernimento, Marca

#: As 4 marcas da Disposição, na ordem canônica do modelo de domínio.
MARCAS = (
    "reconhecimento_de_si",
    "pureza",
    "reta_intencao",
    "capacidade_de_receber",
)

# Prompt mínimo e honesto; a Condução (revelação por graus) é afinada no Plano 2b.
_SISTEMA = (
    "Você lê a disposição interior de um buscador a partir da fala dele e "
    "devolve um JSON com: registro, marcas (as 4: reconhecimento_de_si, pureza, "
    "reta_intencao, capacidade_de_receber — cada uma {valor, incerteza} em 0..1), "
    "grau (inteiro), lingua_ausente (bool), e_retorno (bool)."
)


def _exigir_bool(dados: dict, campo: str) -> bool:
    """Lê um campo booleano exigindo que já seja bool (parsing estrito).

    Evita a corrupção silenciosa de ``bool("false") == True``: o contrato é que o
    backend devolva um booleano JSON, não uma string.
    """
    valor = dados[campo]
    if not isinstance(valor, bool):
        raise ValueError(f"campo '{campo}' deve ser booleano, veio {valor!r}")
    return valor


class Discernidor:
    """Transforma a fala do Buscador num :class:`Discernimento` auditável."""

    def __init__(self, llm: LLMBackend) -> None:
        self._llm = llm

    def discernir(
        self, fala: str, *, graus_memoria: dict[str, str] | None = None
    ) -> Discernimento:
        """Lê ``fala`` (e os graus já abertos, se houver) num :class:`Discernimento`.

        ``graus_memoria`` é um sinal entre outros (lei nº3: a Memória informa, não
        determina); no 2a é apenas anexado ao pedido.
        """
        contexto = ""
        if graus_memoria:
            contexto = f"\n[graus já abertos: {graus_memoria}]"
        bruto = self._llm.gerar(PedidoLLM(sistema=_SISTEMA, usuario=fala + contexto))
        dados = json.loads(bruto)
        marcas = {
            nome: Marca(
                valor=float(dados["marcas"][nome]["valor"]),
                incerteza=float(dados["marcas"][nome]["incerteza"]),
            )
            for nome in MARCAS
        }
        return Discernimento(
            registro=str(dados["registro"]),
            marcas=marcas,
            grau=int(dados["grau"]),
            lingua_ausente=_exigir_bool(dados, "lingua_ausente"),
            e_retorno=_exigir_bool(dados, "e_retorno"),
        )
