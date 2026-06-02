from __future__ import annotations

from enum import Enum


class Proveniencia(Enum):
    PRIMARIA = "primaria"
    TECNICA = "tecnica"
    TESTEMUNHO = "testemunho"
    ERUDICAO = "erudicao"
    EXCLUIDO = "excluido"

    @property
    def pode_fundar(self) -> bool:
        return self is Proveniencia.PRIMARIA

    @property
    def pode_iluminar(self) -> bool:
        return self in (Proveniencia.ERUDICAO, Proveniencia.TESTEMUNHO)

    @property
    def em_quarentena(self) -> bool:
        return self is Proveniencia.EXCLUIDO
