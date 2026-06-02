from __future__ import annotations

from dataclasses import dataclass
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


@dataclass(frozen=True)
class Passagem:
    id: str
    ref_canonica: str
    texto: str
    proveniencia: Proveniencia
    obra: str
    tratado: str | None = None


@dataclass
class Texto:
    obra: str
    tratado: str | None
    proveniencia: Proveniencia
    autor_ou_tradutor: str
    idioma: str
    ref_base: str
    passagens: list[Passagem]
