"""③ Compositor (voz do Mestre) — compõe a :class:`RascunhoRevelacao`.

Recebe o :class:`Discernimento` e a :class:`Recuperacao`, pede ao LLM uma
Revelação no grau cabível e PARSEIA a saída num rascunho cujas afirmações
doutrinais vêm declaradamente citadas (contrato que o Verificador fará cumprir).
No retry, as violações apontadas pelo Verificador entram no pedido, para o
Mestre refazer. O prompt-sistema da voz do Mestre é uma versão inicial fiel às
leis; sua afinação fina é a fase iterativa do Plano 2b contra os evals. As
afirmações doutrinais saem declaradamente citadas (contrato que o Verificador
faz cumprir); iluminantes entram como iluminação, nunca como fundamento.
"""

from __future__ import annotations

import json

from poimandres.pipeline.llm import LLMBackend, PedidoLLM
from poimandres.pipeline.parsing import bool_ou_default
from poimandres.pipeline.tipos import (
    Afirmacao,
    Discernimento,
    Movimento,
    RascunhoRevelacao,
    Recuperacao,
)


_SISTEMA = (
    "Você é o MESTRE de um oráculo hermético clássico, que conduz como Hermes "
    "conduz Tat: sonda, devolve, revela por graus, pode adiar. Leis invioláveis:\n"
    "1. FUNDAR só nas passagens FUNDANTES dadas; toda afirmação doutrinal traz o "
    "citacao_id da fundante que a sustenta. Nunca funde no que não foi dado.\n"
    "2. GRAU: REVELAR é o padrão quando há fundante e a Disposição comporta — "
    "revele no grau que ela autoriza, fundado nas primárias; guarde/adie só o que "
    "está acima desse grau, apontando o caminho sem despejar (use grau e as 4 "
    "marcas como leitura, não como nota).\n"
    "3. LÍNGUA: se lingua_ausente, entre pela Imagem, depois NOMEIE o termo, "
    "depois Glose — guardando do anacronismo. Quando a fala descreve em palavras "
    "comuns algo que uma fundante nomeia (ex.: 'parte de mim que não acaba' = o "
    "homem essencial/imortal), DÊ esse nome no grau cabível, em vez de deixar a "
    "intuição do buscador sem nome.\n"
    "4. ILUMINANTES (erudição) só ILUMINAM, marcadas como tal; jamais fundam.\n"
    "5. DEVOLVER (devolveu=true, movimentos=[...]) é a EXCEÇÃO, não o costume: "
    "sonde antes de revelar só quando a Disposição é baixa ou incerta (marcas "
    "baixas ou de alta incerteza), quando a fala é vaga demais para fundar, ou "
    "quando o próprio Movimento é o que conduz. Tendo Disposição suficiente e "
    "fundante claro, REVELE — pode acrescentar um Movimento para integrar, sem "
    "trocar a Revelação por perguntas.\n"
    "6. Se houver só suporte técnico (so_tecnico), DECLARE o gênero "
    "(genero_declarado=true) em vez de tratá-lo como doutrina.\n"
    "7. CONVERSA: o DIÁLOGO até aqui é dado abaixo. NÃO repita perguntas já feitas "
    "nem re-sonde o que o buscador já respondeu; AVANCE — aprofunde o grau a cada "
    "troca, revele mais, varie os Movimentos, e não funde sempre nos mesmos versos. "
    "Se o buscador já se abriu (já disse o que o traz), REVELE em vez de sondar de novo.\n"
    "Devolva JSON: {texto, afirmacoes:[{frase,citacao_id}], movimentos:[...], "
    "devolveu, genero_declarado}."
)

_AFIRMACAO_SCHEMA = {
    "type": "object",
    "properties": {
        "frase": {"type": "string"},
        "citacao_id": {"type": "string"},
    },
    "required": ["frase", "citacao_id"],
    "additionalProperties": False,
}

_SCHEMA = {
    "type": "object",
    "properties": {
        "texto": {"type": "string"},
        "afirmacoes": {"type": "array", "items": _AFIRMACAO_SCHEMA},
        "movimentos": {"type": "array", "items": {"type": "string"}},
        "devolveu": {"type": "boolean"},
        "genero_declarado": {"type": "boolean"},
    },
    "required": ["texto", "afirmacoes", "movimentos", "devolveu", "genero_declarado"],
    "additionalProperties": False,
}


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
        historico: list[dict] | None = None,
    ) -> RascunhoRevelacao:
        """Compõe um :class:`RascunhoRevelacao` a partir do turno recuperado.

        Args:
            discernimento: a leitura do Buscador (grau, registro, língua).
            recuperacao: o material do corpus (fundantes/iluminantes/silêncio).
            violacoes: se este é um retry, as violações que o Verificador anotou —
                anexadas ao pedido para o Mestre refazer.
            historico: turnos anteriores do diálogo (o loop) — cada um
                ``{fala, revelacao, ...}``. Renderizados como o DIÁLOGO ATÉ AQUI
                que a regra #7 manda o Mestre não repetir e fazer avançar.
        """
        fundantes = "\n".join(f"{p.id}: {p.texto}" for p in recuperacao.fundantes)
        iluminantes = "\n".join(
            f"{p.id} ({p.obra}): {p.texto}" for p in recuperacao.iluminantes
        )
        marcas = ", ".join(
            f"{nome}={m.valor:.2f}(±{m.incerteza:.2f})"
            for nome, m in discernimento.marcas.items()
        )
        usuario = (
            f"grau={discernimento.grau} registro={discernimento.registro} "
            f"lingua_ausente={discernimento.lingua_ausente}\n"
            f"marcas da Disposição (valor±incerteza): {marcas}\n"
            f"silencio={recuperacao.silencio} so_tecnico={recuperacao.so_tecnico}\n"
            f"FUNDANTES (podem fundar):\n{fundantes}\n"
            f"ILUMINANTES (só iluminam, nunca fundam):\n{iluminantes}"
        )
        if historico:
            dialogo = "\n".join(
                f"Buscador: {t['fala']}\nMestre: {t['revelacao']}" for t in historico
            )
            usuario += f"\nDIÁLOGO ATÉ AQUI:\n{dialogo}"
        if violacoes:
            usuario += "\n[REFAÇA — violações: " + "; ".join(violacoes) + "]"
        bruto = self._llm.gerar(
            PedidoLLM(sistema=_SISTEMA, usuario=usuario, schema=_SCHEMA)
        )
        dados = json.loads(bruto)
        afirmacoes = [
            Afirmacao(frase=a["frase"], citacao_id=a["citacao_id"])
            for a in dados.get("afirmacoes", [])
        ]
        movimentos = [Movimento(pedido=m) for m in dados.get("movimentos", [])]
        return RascunhoRevelacao(
            texto=str(dados["texto"]),
            afirmacoes=afirmacoes,
            movimentos=movimentos,
            devolveu=bool_ou_default(dados, "devolveu", False),
            genero_declarado=bool_ou_default(dados, "genero_declarado", False),
        )
