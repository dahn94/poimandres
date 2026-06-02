"""① Discernidor — lê a fala do Buscador num :class:`Discernimento` estruturado.

Chama o :class:`~poimandres.pipeline.llm.LLMBackend` pedindo uma leitura das 4
marcas da Disposição (cada uma COM incerteza — lei nº7), do Registro, do Grau
cabível agora e dos sinais de língua-ausente/retorno; depois PARSEIA essa saída
estruturada (JSON) no tipo de domínio. O prompt-sistema é uma versão inicial fiel
às leis; sua afinação fina é a fase iterativa do Plano 2b contra os evals. Com o
``ClaudeLLM`` a saída estruturada é garantida pelo schema (``PedidoLLM.schema``);
com o ``FakeLLM`` (testes) o schema é ignorado.
"""

from __future__ import annotations

import json

from poimandres.pipeline.llm import LLMBackend, PedidoLLM
from poimandres.pipeline.parsing import exigir_bool
from poimandres.pipeline.tipos import Discernimento, Marca

#: As 4 marcas da Disposição, na ordem canônica do modelo de domínio.
MARCAS = (
    "reconhecimento_de_si",
    "pureza",
    "reta_intencao",
    "capacidade_de_receber",
)

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
        bruto = self._llm.gerar(
            PedidoLLM(sistema=_SISTEMA, usuario=fala + contexto, schema=_SCHEMA)
        )
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
            lingua_ausente=exigir_bool(dados, "lingua_ausente"),
            e_retorno=exigir_bool(dados, "e_retorno"),
        )
