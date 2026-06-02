"""③ Compositor (voz do Mestre) — compõe a :class:`RascunhoRevelacao`.

Recebe o :class:`Discernimento` e a :class:`Recuperacao`, pede ao LLM uma
Revelação no grau cabível e PARSEIA a saída num rascunho cujas afirmações
doutrinais vêm declaradamente citadas (contrato que o Verificador fará cumprir).
No retry, as violações apontadas pelo Verificador entram no pedido, para o
Mestre refazer. O prompt da voz do Mestre (Condução, trilho da língua, quando
devolver) é afinado no Plano 2b; aqui o que importa é o encanamento.
"""

from __future__ import annotations

import json

from poimandres.pipeline.llm import LLMBackend, PedidoLLM
from poimandres.pipeline.tipos import (
    Afirmacao,
    Discernimento,
    RascunhoRevelacao,
    Recuperacao,
)

_SISTEMA = (
    "Você é o Mestre, que conduz como Hermes conduz Tat. Componha uma resposta "
    "fundada SOMENTE nas passagens fundantes fornecidas; toda afirmação doutrinal "
    "deve trazer o citacao_id da passagem que a sustenta. Pode devolver uma "
    "pergunta em vez de revelar. Devolva um JSON: {texto, afirmacoes:[{frase,"
    "citacao_id}], devolveu:bool, genero_declarado:bool}."
)


class Compositor:
    """Compõe a Revelação proposta, com afirmações declaradamente citadas."""

    def __init__(self, llm: LLMBackend) -> None:
        self._llm = llm

    def compor(
        self,
        discernimento: Discernimento,
        recuperacao: Recuperacao,
        *,
        violacoes: list[str] | None = None,
    ) -> RascunhoRevelacao:
        """Compõe um :class:`RascunhoRevelacao` a partir do turno recuperado.

        Args:
            discernimento: a leitura do Buscador (grau, registro, língua).
            recuperacao: o material do corpus (fundantes/iluminantes/silêncio).
            violacoes: se este é um retry, as violações que o Verificador anotou —
                anexadas ao pedido para o Mestre refazer.
        """
        fundantes = "\n".join(f"{p.id}: {p.texto}" for p in recuperacao.fundantes)
        usuario = (
            f"grau={discernimento.grau} registro={discernimento.registro}\n"
            f"silencio={recuperacao.silencio} so_tecnico={recuperacao.so_tecnico}\n"
            f"FUNDANTES:\n{fundantes}"
        )
        if violacoes:
            usuario += "\n[REFAÇA — violações: " + "; ".join(violacoes) + "]"
        bruto = self._llm.gerar(PedidoLLM(sistema=_SISTEMA, usuario=usuario))
        dados = json.loads(bruto)
        afirmacoes = [
            Afirmacao(frase=a["frase"], citacao_id=a["citacao_id"])
            for a in dados.get("afirmacoes", [])
        ]
        return RascunhoRevelacao(
            texto=str(dados["texto"]),
            afirmacoes=afirmacoes,
            devolveu=bool(dados.get("devolveu", False)),
            genero_declarado=bool(dados.get("genero_declarado", False)),
        )
