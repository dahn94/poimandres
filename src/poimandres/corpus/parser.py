from __future__ import annotations

import re

import yaml

from poimandres.corpus.segmentar import segmentar
from poimandres.domain import Passagem, Proveniencia, Texto

_FRONTMATTER_RE = re.compile(r"^---\n(.*?)\n---\n(.*)$", re.DOTALL)


def parse_texto(conteudo: str) -> Texto:
    m = _FRONTMATTER_RE.match(conteudo)
    if not m:
        raise ValueError("arquivo sem frontmatter YAML delimitado por ---")
    meta = yaml.safe_load(m.group(1)) or {}
    corpo = m.group(2)

    proveniencia = Proveniencia(meta["proveniencia"])
    obra = meta["obra"]
    tratado = meta.get("tratado")
    ref_base = meta["ref_base"]

    passagens = [
        Passagem(
            id=_slug(ref_base, numero),
            ref_canonica=f"{ref_base} §{numero}",
            texto=texto,
            proveniencia=proveniencia,
            obra=obra,
            tratado=tratado,
        )
        for numero, texto in segmentar(corpo)
    ]
    return Texto(
        obra=obra,
        tratado=tratado,
        proveniencia=proveniencia,
        autor_ou_tradutor=meta.get("autor_ou_tradutor", ""),
        idioma=meta.get("idioma", ""),
        ref_base=ref_base,
        passagens=passagens,
    )


def _slug(ref_base: str, numero: str) -> str:
    base = re.sub(r"[^a-z0-9]+", "-", ref_base.lower()).strip("-")
    return f"{base}-{numero}"
