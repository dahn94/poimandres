from __future__ import annotations

from dataclasses import dataclass

import lancedb

from poimandres.corpus.embeddings import EmbeddingsBackend
from poimandres.domain import Passagem, Proveniencia

_TABELA = "passagens"


@dataclass
class Resultado:
    passagem: Passagem
    distancia: float


class CorpusStore:
    """Armazena passagens vetorizadas; expõe busca SEPARADA por papel de proveniência.

    O filtro de autoridade é garantido por construção: cada método só consulta as
    proveniências do seu papel.
    """

    def __init__(self, caminho: str, embeddings: EmbeddingsBackend) -> None:
        self._db = lancedb.connect(caminho)
        self._emb = embeddings

    def adicionar(self, passagens: list[Passagem]) -> None:
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
        if _TABELA not in self._db.list_tables().tables:
            return []
        tbl = self._db.open_table(_TABELA)
        vetor = self._emb.embed([consulta])[0]
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
        return self._buscar(consulta, [Proveniencia.PRIMARIA], k)

    def buscar_iluminantes(self, consulta: str, k: int = 4) -> list[Resultado]:
        return self._buscar(
            consulta, [Proveniencia.ERUDICAO, Proveniencia.TESTEMUNHO], k
        )

    def buscar_tecnicas(self, consulta: str, k: int = 3) -> list[Resultado]:
        return self._buscar(consulta, [Proveniencia.TECNICA], k)

    def reconhecer_excluidas(self, consulta: str, k: int = 3) -> list[Resultado]:
        return self._buscar(consulta, [Proveniencia.EXCLUIDO], k)
