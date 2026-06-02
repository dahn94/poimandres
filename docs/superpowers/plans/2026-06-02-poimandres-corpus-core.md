# Poimandres — Plano 1: Núcleo do Corpus (Implementation Plan)

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Permitir que o Curador alimente o corpus hermético a partir de arquivos Markdown e o consulte por busca semântica, com filtro DURO de proveniência (só primárias podem ser recuperadas como fundantes).

**Architecture:** Pipeline de ingestão offline: cada arquivo Markdown (frontmatter YAML + corpo segmentado por marcas `§N`) vira `Passagem`s endereçáveis que herdam a Proveniência do texto; cada passagem é embeddada localmente (BGE-M3) e gravada num vector store local (LanceDB). A recuperação expõe métodos *separados por papel de proveniência* (`buscar_fundantes`, `buscar_iluminantes`, `buscar_tecnicas`, `reconhecer_excluidas`), de modo que o filtro de autoridade é garantido por construção, não por instrução.

**Tech Stack:** Python 3.12 · PyYAML · LanceDB (vector store embarcado) · sentence-transformers (BGE-M3) · Click (CLI) · pytest. Embeddings e store rodam 100% locais na VPS.

**Escopo deste plano:** domínio (Proveniência, Passagem, Texto) · segmentação · parser de arquivo · backends de embeddings (Fake p/ testes + Local BGE-M3) · vector store com busca filtrada · ingestão de pasta · CLI `ingest`/`buscar`. **Fora deste plano (vai p/ Plano 2):** ingestão de `tensoes/` e `glossario/`, e todas as unidades da consulta (Discernidor, Compositor, Verificador, Memória, orquestrador).

---

### Task 1: Scaffold do projeto

**Files:**
- Create: `pyproject.toml`
- Create: `src/poimandres/__init__.py`
- Create: `tests/__init__.py`
- Create: `tests/test_smoke.py`
- Create: `.gitignore`

- [ ] **Step 1: Inicializar o repositório git**

Run:
```bash
cd /Users/dahn/Development/dahn94/poimandres && git init
```
Expected: `Initialized empty Git repository in .../poimandres/.git/`

- [ ] **Step 2: Criar `.gitignore`**

```gitignore
__pycache__/
*.pyc
.pytest_cache/
.venv/
*.egg-info/
.poimandres/
```

- [ ] **Step 3: Criar `pyproject.toml`**

```toml
[build-system]
requires = ["hatchling"]
build-backend = "hatchling.build"

[project]
name = "poimandres"
version = "0.1.0"
description = "Oráculo hermético — núcleo do corpus"
requires-python = ">=3.12"
dependencies = [
    "pyyaml>=6.0",
    "lancedb>=0.13",
    "sentence-transformers>=3.0",
    "click>=8.1",
]

[project.optional-dependencies]
dev = ["pytest>=8.0"]

[project.scripts]
poimandres = "poimandres.cli:cli"

[tool.hatch.build.targets.wheel]
packages = ["src/poimandres"]

[tool.pytest.ini_options]
pythonpath = ["src"]
testpaths = ["tests"]
```

- [ ] **Step 4: Criar pacotes vazios**

`src/poimandres/__init__.py`:
```python
__all__: list[str] = []
```

`tests/__init__.py`:
```python
```

- [ ] **Step 5: Escrever o smoke test**

`tests/test_smoke.py`:
```python
import poimandres


def test_pacote_importavel():
    assert poimandres.__all__ == []
```

- [ ] **Step 6: Criar venv, instalar e rodar o smoke test**

Run:
```bash
cd /Users/dahn/Development/dahn94/poimandres && python3.12 -m venv .venv && .venv/bin/pip install -e ".[dev]" && .venv/bin/pytest tests/test_smoke.py -v
```
Expected: `1 passed`. (A instalação baixa lancedb e sentence-transformers; pode demorar.)

- [ ] **Step 7: Commit**

```bash
git add -A
git commit -m "chore: scaffold do projeto poimandres (núcleo do corpus)"
```

---

### Task 2: Enum de Proveniência

**Files:**
- Create: `src/poimandres/domain.py`
- Test: `tests/test_domain.py`

- [ ] **Step 1: Escrever o teste que falha**

`tests/test_domain.py`:
```python
from poimandres.domain import Proveniencia


def test_so_primaria_funda():
    assert Proveniencia.PRIMARIA.pode_fundar is True
    for p in (Proveniencia.TECNICA, Proveniencia.TESTEMUNHO,
              Proveniencia.ERUDICAO, Proveniencia.EXCLUIDO):
        assert p.pode_fundar is False


def test_iluminam_erudicao_e_testemunho():
    assert Proveniencia.ERUDICAO.pode_iluminar is True
    assert Proveniencia.TESTEMUNHO.pode_iluminar is True
    assert Proveniencia.PRIMARIA.pode_iluminar is False
    assert Proveniencia.EXCLUIDO.pode_iluminar is False


def test_so_excluido_em_quarentena():
    assert Proveniencia.EXCLUIDO.em_quarentena is True
    assert Proveniencia.PRIMARIA.em_quarentena is False


def test_valor_serializa_em_string():
    assert Proveniencia.PRIMARIA.value == "primaria"
    assert Proveniencia("erudicao") is Proveniencia.ERUDICAO
```

- [ ] **Step 2: Rodar e verificar que falha**

Run: `.venv/bin/pytest tests/test_domain.py -v`
Expected: FAIL com `ModuleNotFoundError: No module named 'poimandres.domain'`

- [ ] **Step 3: Implementar o mínimo**

`src/poimandres/domain.py`:
```python
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
```

- [ ] **Step 4: Rodar e verificar que passa**

Run: `.venv/bin/pytest tests/test_domain.py -v`
Expected: `4 passed`

- [ ] **Step 5: Commit**

```bash
git add src/poimandres/domain.py tests/test_domain.py
git commit -m "feat: enum Proveniencia com hierarquia de autoridade"
```

---

### Task 3: Dataclasses Passagem e Texto

**Files:**
- Modify: `src/poimandres/domain.py`
- Test: `tests/test_domain.py`

- [ ] **Step 1: Acrescentar testes que falham**

Acrescentar ao fim de `tests/test_domain.py`:
```python
from poimandres.domain import Passagem, Texto


def test_passagem_e_imutavel_e_carrega_proveniencia():
    p = Passagem(
        id="ch-i-15",
        ref_canonica="CH I §15",
        texto="o homem é duplo",
        proveniencia=Proveniencia.PRIMARIA,
        obra="Corpus Hermeticum",
        tratado="I (Poimandres)",
    )
    assert p.ref_canonica == "CH I §15"
    assert p.proveniencia.pode_fundar is True
    import dataclasses
    try:
        p.texto = "outro"  # type: ignore[misc]
        assert False, "Passagem deveria ser imutável"
    except dataclasses.FrozenInstanceError:
        pass


def test_texto_agrega_passagens():
    p = Passagem("ch-i-15", "CH I §15", "x", Proveniencia.PRIMARIA, "Corpus Hermeticum")
    t = Texto(
        obra="Corpus Hermeticum",
        tratado="I (Poimandres)",
        proveniencia=Proveniencia.PRIMARIA,
        autor_ou_tradutor="Copenhaver 1992",
        idioma="pt",
        ref_base="CH I",
        passagens=[p],
    )
    assert len(t.passagens) == 1
    assert t.passagens[0].id == "ch-i-15"
```

- [ ] **Step 2: Rodar e verificar que falha**

Run: `.venv/bin/pytest tests/test_domain.py -v`
Expected: FAIL com `ImportError: cannot import name 'Passagem'`

- [ ] **Step 3: Implementar**

Acrescentar ao fim de `src/poimandres/domain.py`:
```python
from dataclasses import dataclass


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
```

- [ ] **Step 4: Rodar e verificar que passa**

Run: `.venv/bin/pytest tests/test_domain.py -v`
Expected: `6 passed`

- [ ] **Step 5: Commit**

```bash
git add src/poimandres/domain.py tests/test_domain.py
git commit -m "feat: dataclasses Passagem (imutável) e Texto"
```

---

### Task 4: Segmentação do corpo por marcas §N

**Files:**
- Create: `src/poimandres/corpus/__init__.py`
- Create: `src/poimandres/corpus/segmentar.py`
- Test: `tests/test_segmentar.py`

- [ ] **Step 1: Escrever o teste que falha**

`tests/test_segmentar.py`:
```python
from poimandres.corpus.segmentar import segmentar


def test_divide_por_marcas():
    corpo = "§14 a beleza da natureza\n§15 o homem é duplo\n§16 mortal pelo corpo"
    secoes = segmentar(corpo)
    assert secoes == [
        ("14", "a beleza da natureza"),
        ("15", "o homem é duplo"),
        ("16", "mortal pelo corpo"),
    ]


def test_ignora_texto_antes_da_primeira_marca():
    corpo = "preâmbulo solto\n§1 começo de fato"
    assert segmentar(corpo) == [("1", "começo de fato")]


def test_aceita_sufixo_de_letra_na_secao():
    corpo = "§9a parte um\n§9b parte dois"
    assert segmentar(corpo) == [("9a", "parte um"), ("9b", "parte dois")]


def test_corpo_sem_marcas_retorna_vazio():
    assert segmentar("texto sem marca alguma") == []
```

- [ ] **Step 2: Rodar e verificar que falha**

Run: `.venv/bin/pytest tests/test_segmentar.py -v`
Expected: FAIL com `ModuleNotFoundError: No module named 'poimandres.corpus'`

- [ ] **Step 3: Implementar**

`src/poimandres/corpus/__init__.py`:
```python
```

`src/poimandres/corpus/segmentar.py`:
```python
from __future__ import annotations

import re

_MARK_RE = re.compile(r"^§\s*(\d+[a-z]?)\s*", re.MULTILINE)


def segmentar(corpo: str) -> list[tuple[str, str]]:
    """Divide o corpo em pares (numero, texto) por marcas '§N' no início da linha.

    Texto antes da primeira marca é ignorado.
    """
    secoes: list[tuple[str, str]] = []
    marcas = list(_MARK_RE.finditer(corpo))
    for i, m in enumerate(marcas):
        numero = m.group(1)
        inicio = m.end()
        fim = marcas[i + 1].start() if i + 1 < len(marcas) else len(corpo)
        texto = corpo[inicio:fim].strip()
        secoes.append((numero, texto))
    return secoes
```

- [ ] **Step 4: Rodar e verificar que passa**

Run: `.venv/bin/pytest tests/test_segmentar.py -v`
Expected: `4 passed`

- [ ] **Step 5: Commit**

```bash
git add src/poimandres/corpus/__init__.py src/poimandres/corpus/segmentar.py tests/test_segmentar.py
git commit -m "feat: segmentação do corpo por marcas canônicas §N"
```

---

### Task 5: Parser de arquivo (frontmatter + corpo → Texto)

**Files:**
- Create: `src/poimandres/corpus/parser.py`
- Test: `tests/test_parser.py`

- [ ] **Step 1: Escrever o teste que falha**

`tests/test_parser.py`:
```python
import pytest

from poimandres.corpus.parser import parse_texto
from poimandres.domain import Proveniencia

ARQUIVO = """---
obra: "Corpus Hermeticum"
tratado: "I (Poimandres)"
proveniencia: primaria
autor_ou_tradutor: "Copenhaver 1992"
idioma: "pt"
ref_base: "CH I"
---
§14 a beleza da natureza
§15 o homem é duplo, mortal pelo corpo
"""


def test_parse_extrai_metadados_e_passagens():
    t = parse_texto(ARQUIVO)
    assert t.obra == "Corpus Hermeticum"
    assert t.proveniencia is Proveniencia.PRIMARIA
    assert len(t.passagens) == 2


def test_passagem_recebe_ref_canonica_e_id():
    t = parse_texto(ARQUIVO)
    p = t.passagens[1]
    assert p.ref_canonica == "CH I §15"
    assert p.id == "ch-i-15"
    assert p.texto == "o homem é duplo, mortal pelo corpo"


def test_passagem_herda_proveniencia_do_texto():
    t = parse_texto(ARQUIVO)
    assert all(p.proveniencia is Proveniencia.PRIMARIA for p in t.passagens)


def test_arquivo_sem_frontmatter_erra():
    with pytest.raises(ValueError, match="frontmatter"):
        parse_texto("§1 sem cabeçalho")
```

- [ ] **Step 2: Rodar e verificar que falha**

Run: `.venv/bin/pytest tests/test_parser.py -v`
Expected: FAIL com `ModuleNotFoundError: No module named 'poimandres.corpus.parser'`

- [ ] **Step 3: Implementar**

`src/poimandres/corpus/parser.py`:
```python
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
```

- [ ] **Step 4: Rodar e verificar que passa**

Run: `.venv/bin/pytest tests/test_parser.py -v`
Expected: `4 passed`

- [ ] **Step 5: Commit**

```bash
git add src/poimandres/corpus/parser.py tests/test_parser.py
git commit -m "feat: parser de arquivo do corpus (frontmatter + passagens)"
```

---

### Task 6: Backends de embeddings (Fake p/ testes + Local BGE-M3)

**Files:**
- Create: `src/poimandres/corpus/embeddings.py`
- Test: `tests/test_embeddings.py`

- [ ] **Step 1: Escrever o teste que falha**

`tests/test_embeddings.py`:
```python
from poimandres.corpus.embeddings import EmbeddingsBackend, FakeEmbeddings


def test_fake_retorna_vetor_por_texto_com_dim_fixa():
    fake = FakeEmbeddings(dim=8)
    vetores = fake.embed(["alfa", "beta", "gama"])
    assert len(vetores) == 3
    assert all(len(v) == 8 for v in vetores)


def test_fake_e_deterministico():
    fake = FakeEmbeddings(dim=8)
    assert fake.embed(["heimarmene"]) == fake.embed(["heimarmene"])


def test_fake_distingue_textos():
    fake = FakeEmbeddings(dim=8)
    assert fake.embed(["nous"]) != fake.embed(["hyle"])


def test_fake_satisfaz_o_protocolo():
    backend: EmbeddingsBackend = FakeEmbeddings()
    assert backend.embed(["x"])
```

- [ ] **Step 2: Rodar e verificar que falha**

Run: `.venv/bin/pytest tests/test_embeddings.py -v`
Expected: FAIL com `ModuleNotFoundError: No module named 'poimandres.corpus.embeddings'`

- [ ] **Step 3: Implementar**

`src/poimandres/corpus/embeddings.py`:
```python
from __future__ import annotations

from typing import Protocol


class EmbeddingsBackend(Protocol):
    def embed(self, textos: list[str]) -> list[list[float]]: ...


class FakeEmbeddings:
    """Embeddings determinísticos para testes — sem baixar modelos nem rede."""

    def __init__(self, dim: int = 8) -> None:
        self.dim = dim

    def embed(self, textos: list[str]) -> list[list[float]]:
        vetores: list[list[float]] = []
        for t in textos:
            v = [0.0] * self.dim
            for i, ch in enumerate(t):
                v[i % self.dim] += (ord(ch) % 17) / 17.0
            vetores.append(v)
        return vetores


class LocalEmbeddings:
    """BGE-M3 via sentence-transformers; roda local na VPS (CPU ok), multilíngue."""

    def __init__(self, modelo: str = "BAAI/bge-m3") -> None:
        from sentence_transformers import SentenceTransformer

        self._model = SentenceTransformer(modelo)

    def embed(self, textos: list[str]) -> list[list[float]]:
        return self._model.encode(textos, normalize_embeddings=True).tolist()
```

- [ ] **Step 4: Rodar e verificar que passa**

Run: `.venv/bin/pytest tests/test_embeddings.py -v`
Expected: `4 passed`

- [ ] **Step 5: Smoke test manual do backend local (opcional, baixa o modelo)**

Run:
```bash
.venv/bin/python -c "from poimandres.corpus.embeddings import LocalEmbeddings; print(len(LocalEmbeddings().embed(['nous'])[0]))"
```
Expected: imprime `1024` (dimensão do BGE-M3). Pode demorar no 1º uso (download).

- [ ] **Step 6: Commit**

```bash
git add src/poimandres/corpus/embeddings.py tests/test_embeddings.py
git commit -m "feat: backends de embeddings plugáveis (Fake + Local BGE-M3)"
```

---

### Task 7: Vector store com busca filtrada por proveniência

**Files:**
- Create: `src/poimandres/corpus/store.py`
- Test: `tests/test_store.py`

- [ ] **Step 1: Escrever o teste que falha**

`tests/test_store.py`:
```python
import pytest

from poimandres.corpus.embeddings import FakeEmbeddings
from poimandres.corpus.store import CorpusStore
from poimandres.domain import Passagem, Proveniencia


def _p(id, texto, prov):
    return Passagem(id, id.upper(), texto, prov, "Obra")


@pytest.fixture
def store(tmp_path):
    s = CorpusStore(str(tmp_path / "c.lance"), FakeEmbeddings())
    s.adicionar([
        _p("a1", "o nous é livre da heimarmene", Proveniencia.PRIMARIA),
        _p("a2", "o destino tece o corpo pelas esferas", Proveniencia.PRIMARIA),
        _p("e1", "fowden comenta o fatalismo astrológico", Proveniencia.ERUDICAO),
        _p("x1", "a lei da atração e o mentalismo do kybalion", Proveniencia.EXCLUIDO),
    ])
    return s


def test_fundantes_so_trazem_primarias(store):
    res = store.buscar_fundantes("heimarmene destino", k=10)
    assert res, "deveria achar primárias"
    assert all(r.passagem.proveniencia is Proveniencia.PRIMARIA for r in res)


def test_iluminantes_nao_trazem_primarias_nem_excluidas(store):
    res = store.buscar_iluminantes("fatalismo", k=10)
    assert all(r.passagem.proveniencia is Proveniencia.ERUDICAO for r in res)


def test_excluidas_nunca_aparecem_nas_fundantes(store):
    res = store.buscar_fundantes("kybalion lei da atração mentalismo", k=10)
    assert all(r.passagem.id != "x1" for r in res)


def test_reconhecer_excluidas_so_traz_quarentena(store):
    res = store.reconhecer_excluidas("kybalion", k=10)
    assert all(r.passagem.proveniencia is Proveniencia.EXCLUIDO for r in res)


def test_busca_em_store_vazio_retorna_lista_vazia(tmp_path):
    s = CorpusStore(str(tmp_path / "vazio.lance"), FakeEmbeddings())
    assert s.buscar_fundantes("qualquer") == []
```

- [ ] **Step 2: Rodar e verificar que falha**

Run: `.venv/bin/pytest tests/test_store.py -v`
Expected: FAIL com `ModuleNotFoundError: No module named 'poimandres.corpus.store'`

- [ ] **Step 3: Implementar**

`src/poimandres/corpus/store.py`:
```python
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
        if _TABELA in self._db.table_names():
            self._db.open_table(_TABELA).add(registros)
        else:
            self._db.create_table(_TABELA, data=registros)

    def _buscar(self, consulta: str, provs: list[Proveniencia], k: int) -> list[Resultado]:
        if _TABELA not in self._db.table_names():
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
```

- [ ] **Step 4: Rodar e verificar que passa**

Run: `.venv/bin/pytest tests/test_store.py -v`
Expected: `5 passed`

- [ ] **Step 5: Commit**

```bash
git add src/poimandres/corpus/store.py tests/test_store.py
git commit -m "feat: vector store com busca filtrada por proveniência (filtro duro)"
```

---

### Task 8: Ingestão de pasta

**Files:**
- Create: `src/poimandres/corpus/ingest.py`
- Test: `tests/test_ingest.py`

- [ ] **Step 1: Escrever o teste que falha**

`tests/test_ingest.py`:
```python
from poimandres.corpus.embeddings import FakeEmbeddings
from poimandres.corpus.ingest import ingerir_pasta
from poimandres.corpus.store import CorpusStore
from poimandres.domain import Proveniencia

PRIMARIA = """---
obra: "Corpus Hermeticum"
tratado: "I"
proveniencia: primaria
ref_base: "CH I"
---
§15 o homem é duplo
"""

EXCLUIDA = """---
obra: "Kybalion"
proveniencia: excluido
ref_base: "Kyb"
---
§1 o tudo é mente
"""


def _corpus(tmp_path):
    (tmp_path / "primarias").mkdir()
    (tmp_path / "primarias" / "ch01.md").write_text(PRIMARIA, encoding="utf-8")
    (tmp_path / "excluidas").mkdir()
    (tmp_path / "excluidas" / "kyb.md").write_text(EXCLUIDA, encoding="utf-8")
    # estes diretórios devem ser PULADOS neste plano:
    (tmp_path / "tensoes").mkdir()
    (tmp_path / "tensoes" / "heimarmene.md").write_text("pares\n", encoding="utf-8")
    return tmp_path


def test_ingere_conta_passagens_dos_textos(tmp_path):
    corpus = _corpus(tmp_path)
    store = CorpusStore(str(tmp_path / "c.lance"), FakeEmbeddings())
    n = ingerir_pasta(corpus, store)
    assert n == 2  # 1 primária + 1 excluída; tensoes/ é pulado


def test_excluida_vai_para_quarentena_nao_para_fundantes(tmp_path):
    corpus = _corpus(tmp_path)
    store = CorpusStore(str(tmp_path / "c.lance"), FakeEmbeddings())
    ingerir_pasta(corpus, store)
    assert store.buscar_fundantes("mente tudo", k=10) == [] or all(
        r.passagem.proveniencia is Proveniencia.PRIMARIA
        for r in store.buscar_fundantes("mente tudo", k=10)
    )
    assert any(r.passagem.id == "kyb-1" for r in store.reconhecer_excluidas("mente"))
```

- [ ] **Step 2: Rodar e verificar que falha**

Run: `.venv/bin/pytest tests/test_ingest.py -v`
Expected: FAIL com `ModuleNotFoundError: No module named 'poimandres.corpus.ingest'`

- [ ] **Step 3: Implementar**

`src/poimandres/corpus/ingest.py`:
```python
from __future__ import annotations

from pathlib import Path

from poimandres.corpus.parser import parse_texto
from poimandres.corpus.store import CorpusStore

# Diretórios cujo conteúdo NÃO é texto-de-corpus (tratados no Plano 2).
_PULAR = {"tensoes", "glossario"}


def ingerir_pasta(pasta: Path, store: CorpusStore) -> int:
    """Ingere todos os .md de `pasta` (recursivo), pulando tensoes/ e glossario/.

    Retorna o total de passagens ingeridas.
    """
    total = 0
    for arquivo in sorted(pasta.rglob("*.md")):
        partes = arquivo.relative_to(pasta).parts
        if any(p in _PULAR for p in partes):
            continue
        texto = parse_texto(arquivo.read_text(encoding="utf-8"))
        store.adicionar(texto.passagens)
        total += len(texto.passagens)
    return total
```

- [ ] **Step 4: Rodar e verificar que passa**

Run: `.venv/bin/pytest tests/test_ingest.py -v`
Expected: `2 passed`

- [ ] **Step 5: Commit**

```bash
git add src/poimandres/corpus/ingest.py tests/test_ingest.py
git commit -m "feat: ingestão recursiva da pasta do corpus"
```

---

### Task 9: CLI (`ingest` e `buscar`)

**Files:**
- Create: `src/poimandres/cli.py`
- Test: `tests/test_cli.py`

- [ ] **Step 1: Escrever o teste que falha**

`tests/test_cli.py`:
```python
from click.testing import CliRunner

from poimandres.cli import cli

PRIMARIA = """---
obra: "Corpus Hermeticum"
proveniencia: primaria
ref_base: "CH I"
---
§15 o homem é duplo, mortal pelo corpo
"""


def test_ingest_e_buscar_fim_a_fim(tmp_path, monkeypatch):
    # Usa embeddings Fake p/ não baixar BGE-M3 nos testes.
    import poimandres.cli as climod
    from poimandres.corpus.embeddings import FakeEmbeddings
    monkeypatch.setattr(climod, "_fazer_embeddings", lambda: FakeEmbeddings())

    corpus = tmp_path / "corpus" / "primarias"
    corpus.mkdir(parents=True)
    (corpus / "ch01.md").write_text(PRIMARIA, encoding="utf-8")
    db = str(tmp_path / "c.lance")

    runner = CliRunner()
    r1 = runner.invoke(cli, ["ingest", str(tmp_path / "corpus"), "--db", db])
    assert r1.exit_code == 0, r1.output
    assert "ingeridas 1 passagens" in r1.output

    r2 = runner.invoke(cli, ["buscar", "o homem é duplo", "--db", db])
    assert r2.exit_code == 0, r2.output
    assert "CH I §15" in r2.output
```

- [ ] **Step 2: Rodar e verificar que falha**

Run: `.venv/bin/pytest tests/test_cli.py -v`
Expected: FAIL com `ModuleNotFoundError: No module named 'poimandres.cli'`

- [ ] **Step 3: Implementar**

`src/poimandres/cli.py`:
```python
from __future__ import annotations

from pathlib import Path

import click

from poimandres.corpus.embeddings import EmbeddingsBackend, LocalEmbeddings
from poimandres.corpus.ingest import ingerir_pasta
from poimandres.corpus.store import CorpusStore

_DB_PADRAO = ".poimandres/corpus.lance"


def _fazer_embeddings() -> EmbeddingsBackend:
    """Ponto de troca de backend (sobrescrito nos testes)."""
    return LocalEmbeddings()


@click.group()
def cli() -> None:
    """Poimandres — curadoria e consulta do corpus hermético."""


@cli.command()
@click.argument(
    "corpus", type=click.Path(exists=True, file_okay=False, path_type=Path)
)
@click.option("--db", default=_DB_PADRAO, show_default=True)
def ingest(corpus: Path, db: str) -> None:
    """Ingere a pasta CORPUS (arquivos Markdown) no vector store."""
    store = CorpusStore(db, _fazer_embeddings())
    n = ingerir_pasta(corpus, store)
    click.echo(f"ingeridas {n} passagens de {corpus}")


@cli.command()
@click.argument("consulta")
@click.option("--db", default=_DB_PADRAO, show_default=True)
@click.option("--k", default=6, show_default=True)
def buscar(consulta: str, db: str, k: int) -> None:
    """Busca passagens FUNDANTES (primárias) semanticamente próximas de CONSULTA."""
    store = CorpusStore(db, _fazer_embeddings())
    resultados = store.buscar_fundantes(consulta, k)
    if not resultados:
        click.echo("(o corpus é silente sobre isto)")
        return
    for r in resultados:
        click.echo(f"[{r.passagem.ref_canonica}] {r.passagem.texto[:120]}")
```

- [ ] **Step 4: Rodar e verificar que passa**

Run: `.venv/bin/pytest tests/test_cli.py -v`
Expected: `1 passed`

- [ ] **Step 5: Commit**

```bash
git add src/poimandres/cli.py tests/test_cli.py
git commit -m "feat: CLI poimandres ingest/buscar"
```

---

### Task 10: Corpus de exemplo + suíte completa verde

**Files:**
- Create: `corpus/primarias/ch-i-poimandres.md`
- Create: `corpus/excluidas/kybalion.md`
- Create: `corpus/README.md`
- Test: `tests/test_e2e.py`

- [ ] **Step 1: Criar o corpus de exemplo (semente real)**

`corpus/primarias/ch-i-poimandres.md`:
```markdown
---
obra: "Corpus Hermeticum"
tratado: "I (Poimandres)"
proveniencia: primaria
autor_ou_tradutor: "(traduzir/curar)"
idioma: "pt"
ref_base: "CH I"
---
§14 E a Natureza, vendo a beleza da forma de Deus refletida na água e sua sombra
sobre a terra, sorriu de amor.
§15 Por isso, dentre todos os seres da terra, o homem é duplo: mortal pelo corpo,
imortal pelo Homem essencial.
§24 Primeiro, na dissolução do corpo material, entregas o próprio corpo à mudança.
§25 E então ascendes através das harmonias das esferas, deixando em cada uma as
paixões que dela vieram.
```

`corpus/excluidas/kybalion.md`:
```markdown
---
obra: "The Kybalion"
proveniencia: excluido
autor_ou_tradutor: "Three Initiates 1908"
idioma: "pt"
ref_base: "Kyb"
---
§1 O Tudo é mente; o universo é mental. (Texto NÃO pertencente à Hermética clássica;
mantido apenas para reconhecimento e recusa.)
```

`corpus/README.md`:
```markdown
# corpus/

Fonte de verdade do Poimandres, versionada em git.

- `primarias/`  — só estas FUNDAM uma Revelação (Corpus Hermeticum, Asclépio, Estobeu, Definições).
- `erudicao/`   — só ILUMINA (artigos acadêmicos).
- `testemunho/` — contexto (citações antigas de Hermes).
- `tecnica/`    — Hermética técnica (gênero à parte; tratada no Plano 2).
- `excluidas/`  — pseudo-Hermética (Kybalion, Golden Dawn...); QUARENTENA, só p/ recusar.
- `tensoes/`, `glossario/` — tratados no Plano 2.

Cada arquivo: frontmatter YAML (`obra`, `proveniencia`, `ref_base`...) + corpo segmentado por `§N`.
Ingerir: `poimandres ingest corpus/`.
```

- [ ] **Step 2: Escrever o teste fim-a-fim que falha**

`tests/test_e2e.py`:
```python
from pathlib import Path

from poimandres.corpus.embeddings import FakeEmbeddings
from poimandres.corpus.ingest import ingerir_pasta
from poimandres.corpus.store import CorpusStore

CORPUS = Path(__file__).resolve().parents[1] / "corpus"


def test_corpus_de_exemplo_ingere_e_filtra(tmp_path):
    store = CorpusStore(str(tmp_path / "c.lance"), FakeEmbeddings())
    n = ingerir_pasta(CORPUS, store)
    assert n >= 5  # 4 passagens primárias + 1 excluída

    # a pseudo-Hermética jamais funda
    fundantes = store.buscar_fundantes("o tudo é mente universo mental", k=10)
    assert all(r.passagem.obra == "Corpus Hermeticum" for r in fundantes)

    # mas é reconhecível para recusa
    quarentena = store.reconhecer_excluidas("o tudo é mente", k=10)
    assert any(r.passagem.obra == "The Kybalion" for r in quarentena)
```

- [ ] **Step 3: Rodar e verificar que passa**

Run: `.venv/bin/pytest tests/test_e2e.py -v`
Expected: `1 passed`

- [ ] **Step 4: Rodar a suíte inteira**

Run: `.venv/bin/pytest -v`
Expected: todos verdes (smoke, domain, segmentar, parser, embeddings, store, ingest, cli, e2e).

- [ ] **Step 5: Smoke real opcional (com BGE-M3 de verdade)**

Run:
```bash
.venv/bin/poimandres ingest corpus/ && .venv/bin/poimandres buscar "o que compreender diante da morte"
```
Expected: ingere as passagens e lista trechos de `CH I` (provável `§15`, `§24-25`). Baixa o BGE-M3 no 1º uso.

- [ ] **Step 6: Commit**

```bash
git add corpus tests/test_e2e.py
git commit -m "feat: corpus de exemplo + teste fim-a-fim do núcleo"
```

---

## Self-Review (preenchido)

**Cobertura da spec (Seções 5-6, parte de 4):**
- Proveniência (5 camadas, hierarquia de autoridade) → Task 2. ✓
- Passagem endereçável herda proveniência → Tasks 3, 5. ✓
- Frontmatter YAML + segmentação por `§N` → Tasks 4, 5. ✓
- Embeddings LOCAIS plugáveis (BGE-M3) → Task 6. ✓
- Vector store LanceDB local + filtro DURO de proveniência (só primárias fundam; excluídas em quarentena só-de-reconhecimento) → Task 7. ✓
- Ingestão da pasta `corpus/` por CLI → Tasks 8, 9. ✓
- Árvore do corpus em Markdown versionado → Task 10. ✓
- **Deferido explicitamente ao Plano 2:** `tensoes/` e `glossario/`; Discernidor/Compositor/Verificador/Memória/orquestrador; Estado SQLite; casos-ouro de fidelidade da consulta. (O filtro de proveniência — base das virtudes — já fica testado aqui.)

**Placeholders:** nenhum "TBD/TODO" em código. `(traduzir/curar)` no corpus de exemplo é conteúdo a curar pelo especialista, não placeholder de plano.

**Consistência de tipos/nomes:** `Proveniencia`, `Passagem(id, ref_canonica, texto, proveniencia, obra, tratado)`, `Texto`, `parse_texto`, `segmentar`, `EmbeddingsBackend.embed`, `FakeEmbeddings/LocalEmbeddings`, `CorpusStore.adicionar/buscar_fundantes/buscar_iluminantes/buscar_tecnicas/reconhecer_excluidas/_buscar/_para_resultado`, `Resultado(passagem, distancia)`, `ingerir_pasta`, `_fazer_embeddings` — usados de forma idêntica entre tasks. ✓
