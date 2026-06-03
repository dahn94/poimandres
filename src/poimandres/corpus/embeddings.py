from __future__ import annotations

from typing import Protocol


class EmbeddingsBackend(Protocol):
    def embed(self, textos: list[str]) -> list[list[float]]: ...


class FakeEmbeddings:
    """Embeddings determinísticos para testes — sem baixar modelos nem rede."""

    def __init__(self, dim: int = 8) -> None:
        self.dim = dim

    def embed(self, textos: list[str]) -> list[list[float]]:
        # "Hash" determinístico: distribui os caracteres em ``dim`` baldes
        # (i % dim) e acumula em cada balde um valor em [0, 1) derivado do código
        # do caractere (ord(ch) % 17 / 17). Não tem semântica — só dá vetores
        # estáveis e variados o bastante para os testes.
        vetores: list[list[float]] = []
        for t in textos:
            v = [0.0] * self.dim
            for i, ch in enumerate(t):
                v[i % self.dim] += (ord(ch) % 17) / 17.0
            vetores.append(v)
        return vetores


class LocalEmbeddings:
    """BGE-M3 via sentence-transformers; roda local na VPS (CPU ok), multilíngue.

    Vetoriza em lotes pequenos (``batch_size``) para limitar o pico de memória —
    passagens longas (ex.: comentários do corpus) podem estourar a GPU (MPS) ou a
    RAM se codificadas todas de uma vez.
    """

    def __init__(self, modelo: str = "BAAI/bge-m3", *, batch_size: int = 8) -> None:
        from sentence_transformers import SentenceTransformer

        self._model = SentenceTransformer(modelo)
        self._batch_size = batch_size

    def embed(self, textos: list[str]) -> list[list[float]]:
        return self._model.encode(
            textos, normalize_embeddings=True, batch_size=self._batch_size
        ).tolist()
