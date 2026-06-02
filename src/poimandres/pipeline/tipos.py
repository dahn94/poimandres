"""Tipos de domínio de UM turno do oráculo — as interfaces entre as 5 unidades.

Pacote puro (sem I/O): cada unidade do pipeline recebe e devolve estes tipos, de
modo que possam ser construídas e testadas isoladamente. Espelha o papel de
``poimandres.domain`` para o subsistema do corpus.
"""

from __future__ import annotations

from dataclasses import dataclass, field

from poimandres.domain import Passagem


@dataclass(frozen=True)
class Marca:
    """Uma das 4 marcas da Disposição, lida COM incerteza (lei nº7, humildade).

    O Mestre lê só o que se manifesta no diálogo; por isso cada marca carrega,
    além do ``valor`` estimado (0..1), a ``incerteza`` dessa leitura (0..1).
    """

    valor: float
    incerteza: float


@dataclass(frozen=True)
class Discernimento:
    """O que o Discernidor lê na fala do Buscador, antes de qualquer recuperação.

    Campos:
        registro: lugar no espectro existencial↔doutrinal.
        marcas: as 4 marcas da Disposição (reconhecimento_de_si, pureza,
            reta_intencao, capacidade_de_receber) → :class:`Marca`.
        grau: profundidade de revelação cabível AGORA (re-sondada a cada turno).
        lingua_ausente: o Buscador carece do vocabulário? (aciona o trilho da língua)
        e_retorno: é um retorno? (pede verificar a integração do grau anterior)
    """

    registro: str
    marcas: dict[str, Marca]
    grau: int
    lingua_ausente: bool
    e_retorno: bool


@dataclass(frozen=True)
class Recuperacao:
    """O que o Recuperador trouxe do corpus, já separado por papel de autoridade.

    ``tensoes`` nasce vazia no Plano 2a (a Tensão foi adiada). ``silencio`` indica
    que nenhuma primária funda o tema; ``so_tecnico`` que só há suporte técnico.
    """

    fundantes: list[Passagem]
    iluminantes: list[Passagem]
    tensoes: list = field(default_factory=list)
    silencio: bool = False
    so_tecnico: bool = False


@dataclass(frozen=True)
class Afirmacao:
    """Uma afirmação doutrinal do Mestre e a passagem fundante que a sustenta.

    O ``citacao_id`` é o ``id`` de uma :class:`~poimandres.domain.Passagem`
    FUNDANTE recuperada — o contrato duro que o Verificador faz cumprir.
    """

    frase: str
    citacao_id: str


@dataclass(frozen=True)
class Movimento:
    """O que o Mestre pede do Buscador (devolução, à maneira da Condução)."""

    pedido: str


@dataclass(frozen=True)
class RascunhoRevelacao:
    """A Revelação que o Compositor propõe, ANTES de passar pelo Verificador.

    ``afirmacoes`` são as afirmações doutrinais (cada uma citada); ``devolveu``
    marca que o Mestre escolheu devolver em vez de revelar; ``genero_declarado``
    que, havendo só suporte técnico, o gênero foi explicitado.
    """

    texto: str
    afirmacoes: list[Afirmacao] = field(default_factory=list)
    movimentos: list[Movimento] = field(default_factory=list)
    devolveu: bool = False
    genero_declarado: bool = False


@dataclass(frozen=True)
class Verificacao:
    """Veredito do Verificador sobre um :class:`RascunhoRevelacao`."""

    aprovado: bool
    violacoes: list[str] = field(default_factory=list)


@dataclass(frozen=True)
class RevelacaoFinal:
    """A Revelação entregue ao Buscador e registrada na Memória.

    ``foi_limite`` indica que o Mestre rebaixou a resposta a uma confissão de
    limite (silêncio/recusa) em vez de revelar — nunca uma resposta infiel.
    """

    texto: str
    citacoes: list[str] = field(default_factory=list)
    foi_limite: bool = False
