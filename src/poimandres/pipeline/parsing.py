"""Auxiliares de parsing estrito da saída (JSON) do LLM.

Compartilhados pelas unidades que leem a saída estruturada do LLM. O contrato é
que o backend devolva tipos JSON corretos; estes helpers transformam uma violação
silenciosa (ex.: ``bool("false") == True``) num erro diagnosticável. No Plano 2b,
quando o backend real usar saída estruturada/tool-use, este é o ponto natural
para evoluir a validação.
"""

from __future__ import annotations


def exigir_bool(dados: dict, campo: str) -> bool:
    """Lê um campo booleano OBRIGATÓRIO, exigindo que já seja ``bool``.

    Evita a corrupção silenciosa de ``bool("false") == True``: o contrato é que o
    backend devolva um booleano JSON, não uma string.
    """
    valor = dados[campo]
    if not isinstance(valor, bool):
        raise ValueError(f"campo '{campo}' deve ser booleano, veio {valor!r}")
    return valor


def bool_ou_default(dados: dict, campo: str, padrao: bool) -> bool:
    """Lê um campo booleano OPCIONAL, exigindo ``bool`` quando presente.

    Chave ausente devolve ``padrao`` (ex.: omitir ``devolveu`` significa False);
    presente, delega a :func:`exigir_bool` para validar o tipo.
    """
    if campo not in dados:
        return padrao
    return exigir_bool(dados, campo)
