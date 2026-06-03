"""⑤ Memória-do-caminho — registro persistente do que foi aberto e vivido.

É REGISTRO, não trava (lei nº3): alimenta o Discernidor no próximo turno como um
sinal entre outros, jamais determinando o grau. Persiste em SQLite local: os
turnos do diálogo e o estado dos graus por buscador (aberto ≠ integrado). As
citações de um turno são guardadas como texto separado por ``\\n``.
"""

from __future__ import annotations

import sqlite3

from poimandres.pipeline.tipos import RevelacaoFinal


class Memoria:
    """Acesso ao estado persistente (SQLite) de turnos e graus por buscador."""

    def __init__(self, caminho: str) -> None:
        """Abre/cria o banco em ``caminho`` e garante o esquema."""
        # check_same_thread=False: o turno web roda numa thread separada da que
        # criou a conexão. Turnos são seriais (single-user), sem escrita concorrente.
        self._con = sqlite3.connect(caminho, check_same_thread=False)
        self._con.execute(
            "CREATE TABLE IF NOT EXISTS turno ("
            "buscador_id TEXT NOT NULL, quando TEXT DEFAULT CURRENT_TIMESTAMP, "
            "fala TEXT NOT NULL, revelacao TEXT NOT NULL, citacoes TEXT NOT NULL, "
            "foi_limite INTEGER NOT NULL)"
        )
        self._con.execute(
            "CREATE TABLE IF NOT EXISTS grau ("
            "buscador_id TEXT NOT NULL, tema TEXT NOT NULL, estado TEXT NOT NULL, "
            "quando TEXT DEFAULT CURRENT_TIMESTAMP, "
            "PRIMARY KEY (buscador_id, tema))"
        )
        self._con.commit()

    def registrar_turno(
        self, buscador_id: str, fala: str, revelacao: RevelacaoFinal
    ) -> None:
        """Persiste um turno do diálogo (fala + Revelação entregue)."""
        self._con.execute(
            "INSERT INTO turno (buscador_id, fala, revelacao, citacoes, foi_limite) "
            "VALUES (?, ?, ?, ?, ?)",
            (
                buscador_id,
                fala,
                revelacao.texto,
                "\n".join(revelacao.citacoes),
                int(revelacao.foi_limite),
            ),
        )
        self._con.commit()

    def ler_turnos(self, buscador_id: str) -> list[dict]:
        """Devolve os turnos de um buscador, em ordem de inserção."""
        cur = self._con.execute(
            "SELECT fala, revelacao, citacoes, foi_limite FROM turno "
            "WHERE buscador_id = ? ORDER BY rowid",
            (buscador_id,),
        )
        return [
            {
                "fala": fala,
                "revelacao": rev,
                "citacoes": cit.split("\n") if cit else [],
                "foi_limite": bool(lim),
            }
            for fala, rev, cit, lim in cur.fetchall()
        ]

    def atualizar_grau(self, buscador_id: str, tema: str, estado: str) -> None:
        """Registra/atualiza o estado de um grau (``aberto`` | ``integrado``)."""
        self._con.execute(
            "INSERT INTO grau (buscador_id, tema, estado) VALUES (?, ?, ?) "
            "ON CONFLICT(buscador_id, tema) DO UPDATE SET "
            "estado = excluded.estado, quando = CURRENT_TIMESTAMP",
            (buscador_id, tema, estado),
        )
        self._con.commit()

    def ler_graus(self, buscador_id: str) -> dict[str, str]:
        """Mapa ``tema -> estado`` dos graus já tocados por um buscador."""
        cur = self._con.execute(
            "SELECT tema, estado FROM grau WHERE buscador_id = ?", (buscador_id,)
        )
        return {tema: estado for tema, estado in cur.fetchall()}
