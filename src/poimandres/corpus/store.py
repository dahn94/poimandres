"""Persistência vetorial e busca semântica das passagens do corpus.

Responsabilidade única: guardar as passagens vetorizadas (LanceDB) e recuperá-las
por similaridade — mas SEMPRE através de métodos separados por papel de
proveniência. A separação não é cosmética: é onde o filtro DURO de autoridade do
oráculo é imposto, por construção. Quem chama ``buscar_fundantes`` recebe só
fontes que podem fundar; quem chama ``reconhecer_excluidas`` recebe só material
em quarentena. Não há um método de busca "geral" que misture proveniências.
"""

from __future__ import annotations

from dataclasses import dataclass

import lancedb

from poimandres.corpus.embeddings import EmbeddingsBackend
from poimandres.domain import Passagem, Proveniencia

_TABELA = "passagens"


@dataclass
class Resultado:
    """Uma passagem recuperada e sua distância vetorial à consulta.

    Distância menor = mais próxima/relevante (métrica do LanceDB).
    """

    passagem: Passagem
    distancia: float


class CorpusStore:
    """Armazena passagens vetorizadas; expõe busca SEPARADA por papel de proveniência.

    O filtro de autoridade é garantido por construção: cada método público só
    consulta as proveniências do seu papel (fundantes, iluminantes, técnicas ou
    excluídas), de modo que é impossível, p.ex., devolver uma fonte excluída onde
    se esperava uma fundante.
    """

    def __init__(self, caminho: str, embeddings: EmbeddingsBackend) -> None:
        """Conecta ao banco vetorial em ``caminho`` usando o backend de embeddings.

        Args:
            caminho: diretório do banco LanceDB (criado se não existir).
            embeddings: backend que vetoriza textos e consultas; o MESMO modelo
                precisa ser usado na ingestão e na busca para que as distâncias
                façam sentido.
        """
        self._db = lancedb.connect(caminho)
        self._emb = embeddings

    def adicionar(self, passagens: list[Passagem]) -> None:
        """Vetoriza e persiste as passagens, criando a tabela se ainda não existir.

        Cada passagem vira um registro com seus campos achatados mais o vetor do
        seu texto. Chamar com lista vazia é um no-op.
        """
        if not passagens:
            return
        vetores = self._emb.embed([p.texto for p in passagens])
        registros = [
            {
                "id": p.id,
                "ref_canonica": p.ref_canonica,
                "texto": p.texto,
                "proveniencia": p.proveniencia.value,
                "obra": p.obra,
                "tratado": p.tratado or "",
                "vector": v,
            }
            for p, v in zip(passagens, vetores)
        ]
        if _TABELA in self._db.list_tables().tables:
            self._db.open_table(_TABELA).add(registros)
        else:
            self._db.create_table(_TABELA, data=registros)

    def _buscar(self, consulta: str, provs: list[Proveniencia], k: int) -> list[Resultado]:
        """Busca os ``k`` mais próximos da consulta, restritos às proveniências dadas.

        Núcleo compartilhado dos métodos públicos. O filtro de proveniência é
        aplicado como *prefilter*: a restrição entra ANTES da busca vetorial, de
        modo que proveniências fora do papel nem disputam as ``k`` vagas. Tabela
        ainda inexistente devolve lista vazia.
        """
        if _TABELA not in self._db.list_tables().tables:
            return []
        tbl = self._db.open_table(_TABELA)
        vetor = self._emb.embed([consulta])[0]
        # Cláusula SQL 'IN (...)' com os valores das proveniências permitidas.
        valores = ", ".join(f"'{p.value}'" for p in provs)
        linhas = (
            tbl.search(vetor)
            .where(f"proveniencia IN ({valores})", prefilter=True)
            .limit(k)
            .to_list()
        )
        return [self._para_resultado(r) for r in linhas]

    @staticmethod
    def _para_resultado(r: dict) -> Resultado:
        """Reconstrói uma ``Passagem`` (e seu ``Resultado``) a partir de uma linha."""
        return Resultado(
            passagem=Passagem(
                id=r["id"],
                ref_canonica=r["ref_canonica"],
                texto=r["texto"],
                proveniencia=Proveniencia(r["proveniencia"]),
                obra=r["obra"],
                tratado=r["tratado"] or None,
            ),
            distancia=r["_distance"],
        )

    def buscar_fundantes(self, consulta: str, k: int = 6) -> list[Resultado]:
        """Passagens que podem FUNDAR uma resposta — apenas fontes ``PRIMARIA``.

        Restringe-se às primárias porque, pela regra dura do oráculo, só as
        fontes clássicas primárias têm autoridade para alicerçar uma afirmação.
        """
        return self._buscar(consulta, [Proveniencia.PRIMARIA], k)

    def buscar_iluminantes(self, consulta: str, k: int = 4) -> list[Resultado]:
        """Passagens que ILUMINAM (contextualizam) — ``ERUDICAO`` e ``TESTEMUNHO``.

        Servem para enriquecer e situar uma resposta, nunca para fundá-la.
        """
        return self._buscar(
            consulta, [Proveniencia.ERUDICAO, Proveniencia.TESTEMUNHO], k
        )

    def buscar_tecnicas(self, consulta: str, k: int = 3) -> list[Resultado]:
        """Passagens do hermetismo técnico — apenas fontes ``TECNICA``."""
        return self._buscar(consulta, [Proveniencia.TECNICA], k)

    def reconhecer_excluidas(self, consulta: str, k: int = 3) -> list[Resultado]:
        """Passagens em QUARENTENA — apenas fontes ``EXCLUIDO``.

        Recuperadas não para fundar nem iluminar, mas para que o oráculo possa
        RECONHECER a pseudo-hermética e RECUSÁ-la explicitamente.
        """
        return self._buscar(consulta, [Proveniencia.EXCLUIDO], k)
