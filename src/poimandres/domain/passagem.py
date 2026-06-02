"""A passagem — a menor unidade pesquisável do corpus (um trecho citável)."""

from __future__ import annotations

from dataclasses import dataclass

from poimandres.domain.proveniencia import Proveniencia


@dataclass(frozen=True)
class Passagem:
    """Menor unidade pesquisável do corpus: um trecho citável de um ``Texto``.

    Imutável (``frozen``) porque, uma vez extraída de um arquivo curado, uma
    passagem é uma citação fixa — identidade e texto não mudam.

    Campos:
        id: identificador estável (slug derivado de ``ref_base`` + número).
        ref_canonica: referência citável legível (ex.: ``"CH I §14"``).
        texto: o trecho em si.
        proveniencia: autoridade herdada do ``Texto`` de origem.
        obra: a obra a que pertence (ex.: ``"Corpus Hermeticum"``).
        tratado: subdivisão da obra, se houver.
    """

    id: str
    ref_canonica: str
    texto: str
    proveniencia: Proveniencia
    obra: str
    tratado: str | None = None
