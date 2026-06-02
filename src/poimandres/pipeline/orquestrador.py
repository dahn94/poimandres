"""O Oráculo — orquestra um turno inteiro, costurando as 5 unidades.

Fluxo de um turno: Discernidor → Recuperador → (Compositor → Verificador)*. Se o
Verificador reprova, o Compositor refaz com as violações anotadas, até
``max_retries`` vezes; esgotadas as tentativas, o Mestre REBAIXA ao limite
honesto (uma confissão de silêncio/limite) em vez de entregar resposta infiel
(lei nº5). O turno entregue é sempre registrado na Memória (lei nº3).
"""

from __future__ import annotations

from poimandres.pipeline.compositor import Compositor
from poimandres.pipeline.discernidor import Discernidor
from poimandres.pipeline.memoria import Memoria
from poimandres.pipeline.recuperador import Recuperador
from poimandres.pipeline.tipos import Recuperacao, RevelacaoFinal
from poimandres.pipeline.verificador import Verificador


class Oraculo:
    """Costura as unidades do pipeline num turno verificado e registrado."""

    def __init__(
        self,
        *,
        discernidor: Discernidor,
        recuperador: Recuperador,
        compositor: Compositor,
        verificador: Verificador,
        memoria: Memoria,
        max_retries: int = 2,
    ) -> None:
        self._discernidor = discernidor
        self._recuperador = recuperador
        self._compositor = compositor
        self._verificador = verificador
        self.memoria = memoria
        self._max_retries = max_retries

    def consultar(self, buscador_id: str, fala: str) -> RevelacaoFinal:
        """Conduz um turno e devolve a :class:`RevelacaoFinal` entregue."""
        graus = self.memoria.ler_graus(buscador_id)
        discernimento = self._discernidor.discernir(fala, graus_memoria=graus)
        recuperacao = self._recuperador.recuperar(fala)

        violacoes: list[str] | None = None
        for _ in range(self._max_retries + 1):
            rascunho = self._compositor.compor(
                discernimento, recuperacao, violacoes=violacoes
            )
            veredito = self._verificador.verificar(rascunho, recuperacao)
            if veredito.aprovado:
                final = RevelacaoFinal(
                    texto=rascunho.texto,
                    citacoes=[a.citacao_id for a in rascunho.afirmacoes],
                    foi_limite=False,
                )
                self.memoria.registrar_turno(buscador_id, fala, final)
                return final
            violacoes = veredito.violacoes

        final = self._limite_honesto(recuperacao)
        self.memoria.registrar_turno(buscador_id, fala, final)
        return final

    @staticmethod
    def _limite_honesto(recuperacao: Recuperacao) -> RevelacaoFinal:
        """Resposta de último recurso: confessa o limite, nunca inventa."""
        if recuperacao.silencio:
            texto = "Sobre isto o corpus hermético clássico é silente."
        else:
            texto = (
                "Não posso responder a isto fielmente às fontes primárias agora."
            )
        return RevelacaoFinal(texto=texto, citacoes=[], foi_limite=True)
