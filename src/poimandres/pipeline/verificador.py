"""④ Verificador — as virtudes dos limites viram checagens, fora do LLM.

Faz cumprir as leis verificáveis: 3 checagens DETERMINÍSTICAS (contrato de
citação, silêncio honesto, distinção de gênero) e — no Plano 2b — um juiz-LLM
OPCIONAL que avalia o que o determinístico não alcança (entailment: "a passagem
realmente sustenta a frase?"; anacronismo; confusão de gênero). Sem ``juiz`` o
comportamento é o do Plano 2a. Reprovar devolve as violações nomeadas, que o
Orquestrador anexa ao retry do Compositor.
"""

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

_SCHEMA_JUIZ = {
    "type": "object",
    "properties": {"violacoes": {"type": "array", "items": {"type": "string"}}},
    "required": ["violacoes"],
    "additionalProperties": False,
}


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

        # Juiz-LLM: só quando o determinístico passou (não faz sentido pedir
        # entailment de uma citação que nem existe) e há um juiz injetado.
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
            PedidoLLM(sistema=_SISTEMA_JUIZ, usuario=pares, schema=_SCHEMA_JUIZ)
        )
        return list(json.loads(bruto).get("violacoes", []))
