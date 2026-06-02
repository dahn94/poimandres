"""④ Verificador — as virtudes dos limites viram checagens, fora do LLM.

No Plano 2a faz as checagens DETERMINÍSTICAS (não dependem de juízo): o contrato
de citação, o silêncio honesto e a distinção de gênero. O juiz-LLM (entailment —
"a passagem realmente sustenta a frase?" — e anacronismo fino) é, por ora, um
stub que aprova; ele se torna uma chamada de LLM real no Plano 2b. Reprovar
devolve as violações nomeadas, que o Orquestrador anexa ao retry do Compositor.
"""

from __future__ import annotations

from poimandres.pipeline.tipos import RascunhoRevelacao, Recuperacao, Verificacao


class Verificador:
    """Faz cumprir, por construção, as leis verificáveis sobre um rascunho."""

    def verificar(
        self, rascunho: RascunhoRevelacao, recuperacao: Recuperacao
    ) -> Verificacao:
        """Aplica as checagens determinísticas e devolve o veredito.

        Lei nº4 (autoridade) + nº5 (limites): só primárias fundam; sem fundante,
        confessa-se silêncio; suporte só-técnico é declarado como tal.
        """
        violacoes: list[str] = []
        # As checagens acumulam de forma independente (sem short-circuit): cada uma
        # reporta sua própria verdade. Sob silêncio, p.ex., uma afirmação citada pode
        # disparar tanto (1) quanto (2) — é intencional; o retry do Compositor lida
        # com múltiplas violações.
        ids_fundantes = {p.id for p in recuperacao.fundantes}

        # 1. Contrato de citação (anti-alucinação). Como o excluído jamais entra
        #    em ``fundantes``, isto também garante a recusa do que está em quarentena.
        for af in rascunho.afirmacoes:
            if af.citacao_id not in ids_fundantes:
                violacoes.append(f"citação inexistente nos fundantes: {af.citacao_id}")

        # 2. Silêncio honesto: sem fundante, nenhuma afirmação doutrinal.
        if recuperacao.silencio and rascunho.afirmacoes:
            violacoes.append(
                "afirmação doutrinal sob silêncio (nenhuma primária funda o tema)"
            )

        # 3. Distinção de gênero: suporte só-técnico precisa ser declarado.
        if recuperacao.so_tecnico and not rascunho.genero_declarado:
            violacoes.append("suporte só-técnico sem declaração de gênero")

        # 4. Juiz-LLM (entailment/anacronismo) — stub que aprova no 2a; real no 2b.
        return Verificacao(aprovado=not violacoes, violacoes=violacoes)
