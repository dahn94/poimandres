# Poimandres — Plano 2a: Espinha determinística do turno (Implementation Plan)

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Construir um turno inteiro do oráculo (Discernidor→Recuperador→Compositor→Verificador→Memória + Orquestrador) com um `FakeLLM` roteirizado, deixando as três leis verificáveis hoje (silêncio · recusa do excluído · contrato de citação) verdes por construção; trocar o cérebro pelo Claude real e afinar a Condução fica para o Plano 2b.

**Architecture:** Novo pacote `src/poimandres/pipeline/` espelhando o estilo de `corpus/`: tipos de domínio do turno como dataclasses frozen; um backend de LLM **plugável** (`LLMBackend` Protocol + `FakeLLM`, igual ao par `EmbeddingsBackend`/`FakeEmbeddings`); cinco unidades isoladas e testáveis; um Orquestrador que as fia, faz retry quando o Verificador reprova e rebaixa ao "limite honesto" em vez de entregar resposta infiel. Tudo determinístico nos testes — nenhuma chamada de rede.

**Tech Stack:** Python 3.12, dataclasses, `sqlite3` (stdlib) para a Memória, pytest. Reusa `poimandres.corpus.store.CorpusStore`, `poimandres.corpus.embeddings.FakeEmbeddings`, `poimandres.corpus.ingest.ingerir_pasta` e `poimandres.domain.Passagem`. Sem novas dependências.

---

## File Structure

| Arquivo | Responsabilidade |
|---|---|
| `src/poimandres/pipeline/__init__.py` | Re-exporta os tipos do turno (como `domain/__init__.py`). |
| `src/poimandres/pipeline/tipos.py` | Dataclasses frozen: `Marca`, `Discernimento`, `Recuperacao`, `Afirmacao`, `Movimento`, `RascunhoRevelacao`, `Verificacao`, `RevelacaoFinal`. |
| `src/poimandres/pipeline/llm.py` | `PedidoLLM`, `LLMBackend` (Protocol), `FakeLLM` roteirizado. `ClaudeLLM` fica para o 2b. |
| `src/poimandres/pipeline/recuperador.py` | `Recuperador` — `CorpusStore` → `Recuperacao` (fundantes/iluminantes, `silencio`, `so_tecnico`; `tensoes=[]`). |
| `src/poimandres/pipeline/discernidor.py` | `Discernidor` — `LLMBackend` → `Discernimento` (parsing+validação da saída estruturada). |
| `src/poimandres/pipeline/compositor.py` | `Compositor` — `LLMBackend` → `RascunhoRevelacao` (parsing; declara afirmações citadas). |
| `src/poimandres/pipeline/verificador.py` | `Verificador` — 3 checagens determinísticas; juiz-LLM = stub que aprova (vira real no 2b). |
| `src/poimandres/pipeline/memoria.py` | `Memoria` — SQLite: `turno`, `grau`. |
| `src/poimandres/pipeline/orquestrador.py` | `Oraculo` — fia as 5 unidades, loop de retry, fallback ao limite honesto. |
| `tests/test_pipeline_tipos.py` … `tests/test_oraculo_e2e.py` | Um arquivo de teste por unidade + os casos-ouro determinísticos. |

**Nota sobre prompts:** as constantes de prompt (`_SISTEMA_*`) nascem como textos curtos e honestos. Afiná-las é trabalho do Plano 2b; no 2a só importa que o **encanamento** (montar pedido, parsear saída, validar contrato, retry) seja real e testado.

---

### Task 1: Tipos do turno

**Files:**
- Create: `src/poimandres/pipeline/__init__.py`
- Create: `src/poimandres/pipeline/tipos.py`
- Test: `tests/test_pipeline_tipos.py`

- [ ] **Step 1: Write the failing test**

```python
# tests/test_pipeline_tipos.py
from poimandres.pipeline import (
    Afirmacao,
    Discernimento,
    Marca,
    Movimento,
    RascunhoRevelacao,
    Recuperacao,
    RevelacaoFinal,
    Verificacao,
)


def test_discernimento_carrega_marcas_com_incerteza():
    d = Discernimento(
        registro="existencial",
        marcas={"pureza": Marca(valor=0.5, incerteza=0.3)},
        grau=1,
        lingua_ausente=False,
        e_retorno=False,
    )
    assert d.marcas["pureza"].incerteza == 0.3
    assert d.grau == 1


def test_recuperacao_tem_defaults_seguros():
    r = Recuperacao(fundantes=[], iluminantes=[])
    assert r.tensoes == []
    assert r.silencio is False
    assert r.so_tecnico is False


def test_rascunho_declara_afirmacoes_citadas():
    rasc = RascunhoRevelacao(
        texto="...",
        afirmacoes=[Afirmacao(frase="o homem é duplo", citacao_id="ch-i-15")],
    )
    assert rasc.afirmacoes[0].citacao_id == "ch-i-15"
    assert rasc.devolveu is False
    assert rasc.genero_declarado is False


def test_revelacao_final_e_verificacao():
    assert Verificacao(aprovado=True).violacoes == []
    assert RevelacaoFinal(texto="silente").foi_limite is False
    assert Movimento(pedido="observe-se").pedido == "observe-se"
```

- [ ] **Step 2: Run test to verify it fails**

Run: `.venv/bin/pytest tests/test_pipeline_tipos.py -q`
Expected: FAIL com `ModuleNotFoundError: No module named 'poimandres.pipeline'`.

- [ ] **Step 3: Write the types**

```python
# src/poimandres/pipeline/tipos.py
"""Tipos de domínio de UM turno do oráculo — as interfaces entre as 5 unidades.

Pacote puro (sem I/O): cada unidade do pipeline recebe e devolve estes tipos, de
modo que possam ser construídas e testadas isoladamente. Espelha o papel de
``poimandres.domain`` para o subsistema do corpus.
"""

from __future__ import annotations

from dataclasses import dataclass, field

from poimandres.domain import Passagem


@dataclass(frozen=True)
class Marca:
    """Uma das 4 marcas da Disposição, lida COM incerteza (lei nº7, humildade).

    O Mestre lê só o que se manifesta no diálogo; por isso cada marca carrega,
    além do ``valor`` estimado (0..1), a ``incerteza`` dessa leitura (0..1).
    """

    valor: float
    incerteza: float


@dataclass(frozen=True)
class Discernimento:
    """O que o Discernidor lê na fala do Buscador, antes de qualquer recuperação.

    Campos:
        registro: lugar no espectro existencial↔doutrinal.
        marcas: as 4 marcas da Disposição (reconhecimento_de_si, pureza,
            reta_intencao, capacidade_de_receber) → :class:`Marca`.
        grau: profundidade de revelação cabível AGORA (re-sondada a cada turno).
        lingua_ausente: o Buscador carece do vocabulário? (aciona o trilho da língua)
        e_retorno: é um retorno? (pede verificar a integração do grau anterior)
    """

    registro: str
    marcas: dict[str, Marca]
    grau: int
    lingua_ausente: bool
    e_retorno: bool


@dataclass(frozen=True)
class Recuperacao:
    """O que o Recuperador trouxe do corpus, já separado por papel de autoridade.

    ``tensoes`` nasce vazia no Plano 2a (a Tensão foi adiada). ``silencio`` indica
    que nenhuma primária funda o tema; ``so_tecnico`` que só há suporte técnico.
    """

    fundantes: list[Passagem]
    iluminantes: list[Passagem]
    tensoes: list = field(default_factory=list)
    silencio: bool = False
    so_tecnico: bool = False


@dataclass(frozen=True)
class Afirmacao:
    """Uma afirmação doutrinal do Mestre e a passagem fundante que a sustenta.

    O ``citacao_id`` é o ``id`` de uma :class:`~poimandres.domain.Passagem`
    FUNDANTE recuperada — o contrato duro que o Verificador faz cumprir.
    """

    frase: str
    citacao_id: str


@dataclass(frozen=True)
class Movimento:
    """O que o Mestre pede do Buscador (devolução, à maneira da Condução)."""

    pedido: str


@dataclass(frozen=True)
class RascunhoRevelacao:
    """A Revelação que o Compositor propõe, ANTES de passar pelo Verificador.

    ``afirmacoes`` são as afirmações doutrinais (cada uma citada); ``devolveu``
    marca que o Mestre escolheu devolver em vez de revelar; ``genero_declarado``
    que, havendo só suporte técnico, o gênero foi explicitado.
    """

    texto: str
    afirmacoes: list[Afirmacao] = field(default_factory=list)
    movimentos: list[Movimento] = field(default_factory=list)
    devolveu: bool = False
    genero_declarado: bool = False


@dataclass(frozen=True)
class Verificacao:
    """Veredito do Verificador sobre um :class:`RascunhoRevelacao`."""

    aprovado: bool
    violacoes: list[str] = field(default_factory=list)


@dataclass(frozen=True)
class RevelacaoFinal:
    """A Revelação entregue ao Buscador e registrada na Memória.

    ``foi_limite`` indica que o Mestre rebaixou a resposta a uma confissão de
    limite (silêncio/recusa) em vez de revelar — nunca uma resposta infiel.
    """

    texto: str
    citacoes: list[str] = field(default_factory=list)
    foi_limite: bool = False
```

```python
# src/poimandres/pipeline/__init__.py
"""Pipeline de um turno do oráculo — re-exporta os tipos do turno.

Permite ``from poimandres.pipeline import Discernimento`` independentemente da
subdivisão interna do pacote (mesmo padrão de ``poimandres.domain``).
"""

from poimandres.pipeline.tipos import (
    Afirmacao,
    Discernimento,
    Marca,
    Movimento,
    RascunhoRevelacao,
    Recuperacao,
    RevelacaoFinal,
    Verificacao,
)

__all__ = [
    "Marca",
    "Discernimento",
    "Recuperacao",
    "Afirmacao",
    "Movimento",
    "RascunhoRevelacao",
    "Verificacao",
    "RevelacaoFinal",
]
```

- [ ] **Step 4: Run test to verify it passes**

Run: `.venv/bin/pytest tests/test_pipeline_tipos.py -q`
Expected: `4 passed`.

- [ ] **Step 5: Commit**

```bash
git add src/poimandres/pipeline/__init__.py src/poimandres/pipeline/tipos.py tests/test_pipeline_tipos.py
git commit -m "feat(pipeline): tipos de domínio do turno do oráculo"
```

---

### Task 2: Backend de LLM plugável + FakeLLM

**Files:**
- Create: `src/poimandres/pipeline/llm.py`
- Test: `tests/test_llm.py`

- [ ] **Step 1: Write the failing test**

```python
# tests/test_llm.py
import pytest

from poimandres.pipeline.llm import FakeLLM, PedidoLLM


def test_fakellm_devolve_respostas_em_ordem_e_registra_chamadas():
    llm = FakeLLM(["primeira", "segunda"])
    p1 = PedidoLLM(sistema="s", usuario="u1")
    p2 = PedidoLLM(sistema="s", usuario="u2")
    assert llm.gerar(p1) == "primeira"
    assert llm.gerar(p2) == "segunda"
    assert [c.usuario for c in llm.chamadas] == ["u1", "u2"]


def test_fakellm_esgotado_falha_alto():
    llm = FakeLLM([])
    with pytest.raises(AssertionError):
        llm.gerar(PedidoLLM(sistema="s", usuario="u"))
```

- [ ] **Step 2: Run test to verify it fails**

Run: `.venv/bin/pytest tests/test_llm.py -q`
Expected: FAIL com `ModuleNotFoundError: No module named 'poimandres.pipeline.llm'`.

- [ ] **Step 3: Write the backend**

```python
# src/poimandres/pipeline/llm.py
"""Backend de LLM PLUGÁVEL — interface única + um fake roteirizado para testes.

Espelha o par ``EmbeddingsBackend``/``FakeEmbeddings`` do subsistema do corpus:
o pipeline depende só da interface :class:`LLMBackend`, de modo que trocar o
``FakeLLM`` (testes) pelo Claude real (Plano 2b) — ou por um modelo local no
futuro — é questão de configuração, sem tocar nas unidades.
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import Protocol


@dataclass(frozen=True)
class PedidoLLM:
    """Um pedido ao LLM: a instrução de sistema e a mensagem do usuário.

    No Plano 2a o ``FakeLLM`` ignora o conteúdo e devolve respostas roteirizadas;
    a saída estruturada (schema/tool-use) e o prompt caching entram no 2b.
    """

    sistema: str
    usuario: str


class LLMBackend(Protocol):
    """Contrato mínimo de um backend de LLM: dado um pedido, devolve texto."""

    def gerar(self, pedido: PedidoLLM) -> str: ...


class FakeLLM:
    """LLM roteirizado para testes: devolve respostas pré-definidas, em ordem.

    Registra cada :class:`PedidoLLM` recebido em ``chamadas`` (para asserções
    sobre o que cada unidade enviou) e falha alto se as respostas se esgotarem —
    assim um teste que dispara mais chamadas do que o previsto não passa em falso.
    """

    def __init__(self, respostas: list[str]) -> None:
        self._respostas = list(respostas)
        self.chamadas: list[PedidoLLM] = []

    def gerar(self, pedido: PedidoLLM) -> str:
        self.chamadas.append(pedido)
        if not self._respostas:
            raise AssertionError("FakeLLM: sem respostas roteirizadas restantes")
        return self._respostas.pop(0)
```

- [ ] **Step 4: Run test to verify it passes**

Run: `.venv/bin/pytest tests/test_llm.py -q`
Expected: `2 passed`.

- [ ] **Step 5: Commit**

```bash
git add src/poimandres/pipeline/llm.py tests/test_llm.py
git commit -m "feat(pipeline): LLMBackend plugável + FakeLLM roteirizado"
```

---

### Task 3: Recuperador

**Files:**
- Create: `src/poimandres/pipeline/recuperador.py`
- Test: `tests/test_recuperador.py`

O Recuperador deriva `silencio` (nenhuma fundante dentro do `limiar` de distância) e `so_tecnico` (sem fundantes, mas há técnicas). O `limiar` é o mecanismo que permite ao oráculo confessar silêncio em vez de devolver sempre o vizinho mais próximo; seu valor real é afinado no 2b com as distâncias do BGE-M3. `tensoes` fica vazia (adiada).

- [ ] **Step 1: Write the failing test**

```python
# tests/test_recuperador.py
from poimandres.corpus.embeddings import FakeEmbeddings
from poimandres.corpus.store import CorpusStore
from poimandres.domain import Passagem, Proveniencia
from poimandres.pipeline.recuperador import Recuperador


def _passagem(id, texto, prov, obra):
    return Passagem(
        id=id, ref_canonica=id, texto=texto, proveniencia=prov, obra=obra
    )


def test_recupera_fundantes_e_marca_nao_silencio(tmp_path):
    store = CorpusStore(str(tmp_path / "c.lance"), FakeEmbeddings())
    store.adicionar(
        [_passagem("ch-i-15", "o homem é duplo", Proveniencia.PRIMARIA, "CH")]
    )
    rec = Recuperador(store).recuperar("homem duplo")
    assert any(p.id == "ch-i-15" for p in rec.fundantes)
    assert rec.silencio is False
    assert rec.tensoes == []


def test_sem_primarias_confessa_silencio(tmp_path):
    store = CorpusStore(str(tmp_path / "c.lance"), FakeEmbeddings())
    store.adicionar(
        [_passagem("kyb-1", "o tudo é mente", Proveniencia.EXCLUIDO, "Kyb")]
    )
    rec = Recuperador(store).recuperar("o tudo é mente")
    assert rec.fundantes == []
    assert rec.silencio is True


def test_limiar_estrito_corta_fundantes_distantes(tmp_path):
    store = CorpusStore(str(tmp_path / "c.lance"), FakeEmbeddings())
    store.adicionar(
        [_passagem("ch-i-15", "o homem é duplo", Proveniencia.PRIMARIA, "CH")]
    )
    # limiar negativo: nenhuma distância (>= 0) qualifica → silêncio forçado
    rec = Recuperador(store).recuperar("homem duplo", limiar=-1.0)
    assert rec.fundantes == []
    assert rec.silencio is True


def test_so_tecnico_quando_so_ha_tecnica(tmp_path):
    store = CorpusStore(str(tmp_path / "c.lance"), FakeEmbeddings())
    store.adicionar(
        [_passagem("dec-1", "decano de áries", Proveniencia.TECNICA, "Liber")]
    )
    rec = Recuperador(store).recuperar("decano")
    assert rec.silencio is True
    assert rec.so_tecnico is True
```

- [ ] **Step 2: Run test to verify it fails**

Run: `.venv/bin/pytest tests/test_recuperador.py -q`
Expected: FAIL com `ModuleNotFoundError: No module named 'poimandres.pipeline.recuperador'`.

- [ ] **Step 3: Write the Recuperador**

```python
# src/poimandres/pipeline/recuperador.py
"""② Recuperador — do corpus para a :class:`Recuperacao`, com filtro DURO de autoridade.

Envolve o :class:`~poimandres.corpus.store.CorpusStore` (que já separa as buscas
por proveniência) e deriva os sinais que as unidades seguintes precisam: se
nenhuma primária funda o tema dentro do ``limiar`` de distância, marca
``silencio``; se nesse caso há suporte técnico, marca ``so_tecnico``. A Tensão
foi adiada (Plano 2a), então ``tensoes`` sai sempre vazia — mas o campo já existe.
"""

from __future__ import annotations

from math import inf

from poimandres.corpus.store import CorpusStore, Resultado
from poimandres.pipeline.tipos import Recuperacao


class Recuperador:
    """Recupera do corpus o material de um turno, separado por papel de autoridade."""

    def __init__(self, store: CorpusStore) -> None:
        self._store = store

    def recuperar(
        self,
        consulta: str,
        *,
        k_fundantes: int = 6,
        k_iluminantes: int = 4,
        limiar: float = inf,
    ) -> Recuperacao:
        """Monta a :class:`Recuperacao` para ``consulta``.

        Args:
            consulta: a fala/tema do Buscador.
            k_fundantes: quantas primárias buscar (antes do corte por ``limiar``).
            k_iluminantes: quantas fontes de erudição/testemunho buscar.
            limiar: distância máxima para uma fundante "fundar" de fato; acima
                dela, o corpus é tratado como silente sobre o tema. ``inf`` =
                sem corte (o valor real é afinado no Plano 2b).
        """
        fundantes = self._dentro(self._store.buscar_fundantes(consulta, k_fundantes), limiar)
        iluminantes = [r.passagem for r in self._store.buscar_iluminantes(consulta, k_iluminantes)]
        silencio = not fundantes
        so_tecnico = silencio and bool(self._store.buscar_tecnicas(consulta, k_iluminantes))
        return Recuperacao(
            fundantes=fundantes,
            iluminantes=iluminantes,
            tensoes=[],
            silencio=silencio,
            so_tecnico=so_tecnico,
        )

    @staticmethod
    def _dentro(resultados: list[Resultado], limiar: float) -> list:
        """Passagens cuja distância à consulta não excede o ``limiar``."""
        return [r.passagem for r in resultados if r.distancia <= limiar]
```

- [ ] **Step 4: Run test to verify it passes**

Run: `.venv/bin/pytest tests/test_recuperador.py -q`
Expected: `4 passed`.

- [ ] **Step 5: Commit**

```bash
git add src/poimandres/pipeline/recuperador.py tests/test_recuperador.py
git commit -m "feat(pipeline): Recuperador (silêncio/só-técnico; tensão adiada)"
```

---

### Task 4: Discernidor

**Files:**
- Create: `src/poimandres/pipeline/discernidor.py`
- Test: `tests/test_discernidor.py`

O Discernidor monta o pedido, chama o `LLMBackend` e PARSEIA a saída estruturada (JSON) num `Discernimento`. No 2a o `FakeLLM` devolve o JSON; o prompt de verdade é afinado no 2b.

- [ ] **Step 1: Write the failing test**

```python
# tests/test_discernidor.py
import json

from poimandres.pipeline.discernidor import Discernidor
from poimandres.pipeline.llm import FakeLLM

_RESP = json.dumps(
    {
        "registro": "existencial",
        "marcas": {
            "reconhecimento_de_si": {"valor": 0.6, "incerteza": 0.2},
            "pureza": {"valor": 0.4, "incerteza": 0.3},
            "reta_intencao": {"valor": 0.7, "incerteza": 0.1},
            "capacidade_de_receber": {"valor": 0.5, "incerteza": 0.4},
        },
        "grau": 2,
        "lingua_ausente": True,
        "e_retorno": False,
    }
)


def test_discerne_parseia_saida_estruturada():
    d = Discernidor(FakeLLM([_RESP])).discernir("o que há após a morte?")
    assert d.registro == "existencial"
    assert d.grau == 2
    assert d.lingua_ausente is True
    assert d.marcas["reta_intencao"].valor == 0.7
    assert d.marcas["capacidade_de_receber"].incerteza == 0.4


def test_discernidor_envia_a_fala_ao_llm():
    llm = FakeLLM([_RESP])
    Discernidor(llm).discernir("minha fala")
    assert "minha fala" in llm.chamadas[0].usuario
```

- [ ] **Step 2: Run test to verify it fails**

Run: `.venv/bin/pytest tests/test_discernidor.py -q`
Expected: FAIL com `ModuleNotFoundError: No module named 'poimandres.pipeline.discernidor'`.

- [ ] **Step 3: Write the Discernidor**

```python
# src/poimandres/pipeline/discernidor.py
"""① Discernidor — lê a fala do Buscador num :class:`Discernimento` estruturado.

Chama o :class:`~poimandres.pipeline.llm.LLMBackend` pedindo uma leitura das 4
marcas da Disposição (cada uma COM incerteza — lei nº7), do Registro, do Grau
cabível agora e dos sinais de língua-ausente/retorno; depois PARSEIA essa saída
estruturada (JSON) no tipo de domínio. No Plano 2a o prompt é mínimo e o
``FakeLLM`` devolve o JSON; afiná-lo é trabalho do Plano 2b.
"""

from __future__ import annotations

import json

from poimandres.pipeline.llm import LLMBackend, PedidoLLM
from poimandres.pipeline.tipos import Discernimento, Marca

#: As 4 marcas da Disposição, na ordem canônica do modelo de domínio.
MARCAS = (
    "reconhecimento_de_si",
    "pureza",
    "reta_intencao",
    "capacidade_de_receber",
)

# Prompt mínimo e honesto; a Condução (revelação por graus) é afinada no Plano 2b.
_SISTEMA = (
    "Você lê a disposição interior de um buscador a partir da fala dele e "
    "devolve um JSON com: registro, marcas (as 4: reconhecimento_de_si, pureza, "
    "reta_intencao, capacidade_de_receber — cada uma {valor, incerteza} em 0..1), "
    "grau (inteiro), lingua_ausente (bool), e_retorno (bool)."
)


class Discernidor:
    """Transforma a fala do Buscador num :class:`Discernimento` auditável."""

    def __init__(self, llm: LLMBackend) -> None:
        self._llm = llm

    def discernir(
        self, fala: str, *, graus_memoria: dict[str, str] | None = None
    ) -> Discernimento:
        """Lê ``fala`` (e os graus já abertos, se houver) num :class:`Discernimento`.

        ``graus_memoria`` é um sinal entre outros (lei nº3: a Memória informa, não
        determina); no 2a é apenas anexado ao pedido.
        """
        contexto = ""
        if graus_memoria:
            contexto = f"\n[graus já abertos: {graus_memoria}]"
        bruto = self._llm.gerar(PedidoLLM(sistema=_SISTEMA, usuario=fala + contexto))
        dados = json.loads(bruto)
        marcas = {
            nome: Marca(
                valor=float(dados["marcas"][nome]["valor"]),
                incerteza=float(dados["marcas"][nome]["incerteza"]),
            )
            for nome in MARCAS
        }
        return Discernimento(
            registro=str(dados["registro"]),
            marcas=marcas,
            grau=int(dados["grau"]),
            lingua_ausente=bool(dados["lingua_ausente"]),
            e_retorno=bool(dados["e_retorno"]),
        )
```

- [ ] **Step 4: Run test to verify it passes**

Run: `.venv/bin/pytest tests/test_discernidor.py -q`
Expected: `2 passed`.

- [ ] **Step 5: Commit**

```bash
git add src/poimandres/pipeline/discernidor.py tests/test_discernidor.py
git commit -m "feat(pipeline): Discernidor (parsing da saída estruturada)"
```

---

### Task 5: Compositor

**Files:**
- Create: `src/poimandres/pipeline/compositor.py`
- Test: `tests/test_compositor.py`

O Compositor monta o pedido (incluindo, no retry, as violações anotadas), chama o LLM e parseia a saída num `RascunhoRevelacao` com afirmações declaradamente citadas. O prompt da "voz do Mestre" é afinado no 2b; aqui valida-se o encanamento.

- [ ] **Step 1: Write the failing test**

```python
# tests/test_compositor.py
import json

from poimandres.domain import Passagem, Proveniencia
from poimandres.pipeline.compositor import Compositor
from poimandres.pipeline.llm import FakeLLM
from poimandres.pipeline.tipos import Discernimento, Marca, Recuperacao

_DISC = Discernimento(
    registro="existencial",
    marcas={m: Marca(0.5, 0.2) for m in ("a", "b")},
    grau=1,
    lingua_ausente=False,
    e_retorno=False,
)
_REC = Recuperacao(
    fundantes=[
        Passagem(
            id="ch-i-15",
            ref_canonica="CH I §15",
            texto="o homem é duplo",
            proveniencia=Proveniencia.PRIMARIA,
            obra="Corpus Hermeticum",
        )
    ],
    iluminantes=[],
)
_RESP = json.dumps(
    {
        "texto": "O homem é duplo, mortal e imortal.",
        "afirmacoes": [{"frase": "o homem é duplo", "citacao_id": "ch-i-15"}],
        "devolveu": False,
        "genero_declarado": False,
    }
)


def test_compor_parseia_afirmacoes_citadas():
    rasc = Compositor(FakeLLM([_RESP])).compor(_DISC, _REC)
    assert rasc.afirmacoes[0].citacao_id == "ch-i-15"
    assert rasc.devolveu is False


def test_retry_inclui_violacoes_no_pedido():
    llm = FakeLLM([_RESP])
    Compositor(llm).compor(_DISC, _REC, violacoes=["citação inexistente: x"])
    assert "citação inexistente: x" in llm.chamadas[0].usuario
```

- [ ] **Step 2: Run test to verify it fails**

Run: `.venv/bin/pytest tests/test_compositor.py -q`
Expected: FAIL com `ModuleNotFoundError: No module named 'poimandres.pipeline.compositor'`.

- [ ] **Step 3: Write the Compositor**

```python
# src/poimandres/pipeline/compositor.py
"""③ Compositor (voz do Mestre) — compõe a :class:`RascunhoRevelacao`.

Recebe o :class:`Discernimento` e a :class:`Recuperacao`, pede ao LLM uma
Revelação no grau cabível e PARSEIA a saída num rascunho cujas afirmações
doutrinais vêm declaradamente citadas (contrato que o Verificador fará cumprir).
No retry, as violações apontadas pelo Verificador entram no pedido, para o
Mestre refazer. O prompt da voz do Mestre (Condução, trilho da língua, quando
devolver) é afinado no Plano 2b; aqui o que importa é o encanamento.
"""

from __future__ import annotations

import json

from poimandres.pipeline.llm import LLMBackend, PedidoLLM
from poimandres.pipeline.tipos import (
    Afirmacao,
    Discernimento,
    RascunhoRevelacao,
    Recuperacao,
)

_SISTEMA = (
    "Você é o Mestre, que conduz como Hermes conduz Tat. Componha uma resposta "
    "fundada SOMENTE nas passagens fundantes fornecidas; toda afirmação doutrinal "
    "deve trazer o citacao_id da passagem que a sustenta. Pode devolver uma "
    "pergunta em vez de revelar. Devolva um JSON: {texto, afirmacoes:[{frase,"
    "citacao_id}], devolveu:bool, genero_declarado:bool}."
)


class Compositor:
    """Compõe a Revelação proposta, com afirmações declaradamente citadas."""

    def __init__(self, llm: LLMBackend) -> None:
        self._llm = llm

    def compor(
        self,
        discernimento: Discernimento,
        recuperacao: Recuperacao,
        *,
        violacoes: list[str] | None = None,
    ) -> RascunhoRevelacao:
        """Compõe um :class:`RascunhoRevelacao` a partir do turno recuperado.

        Args:
            discernimento: a leitura do Buscador (grau, registro, língua).
            recuperacao: o material do corpus (fundantes/iluminantes/silêncio).
            violacoes: se este é um retry, as violações que o Verificador anotou —
                anexadas ao pedido para o Mestre refazer.
        """
        fundantes = "\n".join(f"{p.id}: {p.texto}" for p in recuperacao.fundantes)
        usuario = (
            f"grau={discernimento.grau} registro={discernimento.registro}\n"
            f"silencio={recuperacao.silencio} so_tecnico={recuperacao.so_tecnico}\n"
            f"FUNDANTES:\n{fundantes}"
        )
        if violacoes:
            usuario += "\n[REFAÇA — violações: " + "; ".join(violacoes) + "]"
        bruto = self._llm.gerar(PedidoLLM(sistema=_SISTEMA, usuario=usuario))
        dados = json.loads(bruto)
        afirmacoes = [
            Afirmacao(frase=a["frase"], citacao_id=a["citacao_id"])
            for a in dados.get("afirmacoes", [])
        ]
        return RascunhoRevelacao(
            texto=str(dados["texto"]),
            afirmacoes=afirmacoes,
            devolveu=bool(dados.get("devolveu", False)),
            genero_declarado=bool(dados.get("genero_declarado", False)),
        )
```

- [ ] **Step 4: Run test to verify it passes**

Run: `.venv/bin/pytest tests/test_compositor.py -q`
Expected: `2 passed`.

- [ ] **Step 5: Commit**

```bash
git add src/poimandres/pipeline/compositor.py tests/test_compositor.py
git commit -m "feat(pipeline): Compositor (rascunho com afirmações citadas + retry)"
```

---

### Task 6: Verificador (checagens determinísticas)

**Files:**
- Create: `src/poimandres/pipeline/verificador.py`
- Test: `tests/test_verificador.py`

Três checagens determinísticas, cada uma espelhando uma virtude:
1. **Contrato de citação** (anti-alucinação) — todo `citacao_id` existe entre os ids dos fundantes recuperados. Como o excluído NUNCA entra em fundantes, esta mesma regra já barra fundar no que está em quarentena (a recusa do excluído é garantida por construção).
2. **Silêncio honesto** — se `recuperacao.silencio`, então `afirmacoes` deve estar vazia (nada de afirmação doutrinal sem fundante).
3. **Distinção de gênero** — se `recuperacao.so_tecnico`, o rascunho deve ter `genero_declarado=True`.

O juiz-LLM (entailment "a passagem sustenta a frase?", anacronismo fino) é um stub que aprova no 2a e vira real no 2b.

- [ ] **Step 1: Write the failing test**

```python
# tests/test_verificador.py
from poimandres.domain import Passagem, Proveniencia
from poimandres.pipeline.tipos import Afirmacao, RascunhoRevelacao, Recuperacao
from poimandres.pipeline.verificador import Verificador


def _rec(silencio=False, so_tecnico=False):
    fund = (
        []
        if silencio
        else [
            Passagem(
                id="ch-i-15",
                ref_canonica="CH I §15",
                texto="o homem é duplo",
                proveniencia=Proveniencia.PRIMARIA,
                obra="CH",
            )
        ]
    )
    return Recuperacao(
        fundantes=fund, iluminantes=[], silencio=silencio, so_tecnico=so_tecnico
    )


def test_aprova_quando_toda_afirmacao_cita_fundante():
    rasc = RascunhoRevelacao(
        texto="...", afirmacoes=[Afirmacao("o homem é duplo", "ch-i-15")]
    )
    assert Verificador().verificar(rasc, _rec()).aprovado is True


def test_reprova_citacao_inexistente():
    rasc = RascunhoRevelacao(
        texto="...", afirmacoes=[Afirmacao("invenção", "nao-existe")]
    )
    v = Verificador().verificar(rasc, _rec())
    assert v.aprovado is False
    assert any("nao-existe" in viol for viol in v.violacoes)


def test_reprova_afirmacao_em_silencio():
    rasc = RascunhoRevelacao(
        texto="...", afirmacoes=[Afirmacao("algo", "ch-i-15")]
    )
    v = Verificador().verificar(rasc, _rec(silencio=True))
    assert v.aprovado is False
    assert any("silêncio" in viol.lower() for viol in v.violacoes)


def test_aprova_silencio_sem_afirmacoes():
    rasc = RascunhoRevelacao(texto="o corpus é silente sobre isto.")
    assert Verificador().verificar(rasc, _rec(silencio=True)).aprovado is True


def test_reprova_so_tecnico_sem_declarar_genero():
    rasc = RascunhoRevelacao(texto="...", genero_declarado=False)
    v = Verificador().verificar(rasc, _rec(silencio=True, so_tecnico=True))
    assert v.aprovado is False
    assert any("gênero" in viol.lower() for viol in v.violacoes)
```

- [ ] **Step 2: Run test to verify it fails**

Run: `.venv/bin/pytest tests/test_verificador.py -q`
Expected: FAIL com `ModuleNotFoundError: No module named 'poimandres.pipeline.verificador'`.

- [ ] **Step 3: Write the Verificador**

```python
# src/poimandres/pipeline/verificador.py
"""④ Verificador — as virtudes dos limites viram checagens, fora do LLM.

No Plano 2a faz as checagens DETERMINÍSTICAS (não dependem de juízo): o contrato
de citação, o silêncio honesto e a distinção de gênero. O juiz-LLM (entailment —
"a passagem realmente sustenta a frase?" — e anacronismo fino) é, por ora, um
stub que aprova; ele se torna uma chamada de LLM real no Plano 2b. Reprovar
devolve as violações nomeadas, que o Orquestrador anexa ao retry do Compositor.
"""

from __future__ import annotations

from poimandres.pipeline.tipos import RascunhoRevelacao, Recuperacao, Verificacao


class Verificador:
    """Faz cumprir, por construção, as leis verificáveis sobre um rascunho."""

    def verificar(
        self, rascunho: RascunhoRevelacao, recuperacao: Recuperacao
    ) -> Verificacao:
        """Aplica as checagens determinísticas e devolve o veredito.

        Lei nº4 (autoridade) + nº5 (limites): só primárias fundam; sem fundante,
        confessa-se silêncio; suporte só-técnico é declarado como tal.
        """
        violacoes: list[str] = []
        ids_fundantes = {p.id for p in recuperacao.fundantes}

        # 1. Contrato de citação (anti-alucinação). Como o excluído jamais entra
        #    em ``fundantes``, isto também garante a recusa do que está em quarentena.
        for af in rascunho.afirmacoes:
            if af.citacao_id not in ids_fundantes:
                violacoes.append(f"citação inexistente nos fundantes: {af.citacao_id}")

        # 2. Silêncio honesto: sem fundante, nenhuma afirmação doutrinal.
        if recuperacao.silencio and rascunho.afirmacoes:
            violacoes.append(
                "afirmação doutrinal sob silêncio (nenhuma primária funda o tema)"
            )

        # 3. Distinção de gênero: suporte só-técnico precisa ser declarado.
        if recuperacao.so_tecnico and not rascunho.genero_declarado:
            violacoes.append("suporte só-técnico sem declaração de gênero")

        # 4. Juiz-LLM (entailment/anacronismo) — stub que aprova no 2a; real no 2b.
        return Verificacao(aprovado=not violacoes, violacoes=violacoes)
```

- [ ] **Step 4: Run test to verify it passes**

Run: `.venv/bin/pytest tests/test_verificador.py -q`
Expected: `5 passed`.

- [ ] **Step 5: Commit**

```bash
git add src/poimandres/pipeline/verificador.py tests/test_verificador.py
git commit -m "feat(pipeline): Verificador (3 checagens determinísticas; juiz-LLM em 2b)"
```

---

### Task 7: Memória (SQLite)

**Files:**
- Create: `src/poimandres/pipeline/memoria.py`
- Test: `tests/test_memoria.py`

- [ ] **Step 1: Write the failing test**

```python
# tests/test_memoria.py
from poimandres.pipeline.memoria import Memoria
from poimandres.pipeline.tipos import RevelacaoFinal


def test_registra_turno_e_le_de_volta(tmp_path):
    mem = Memoria(str(tmp_path / "estado.db"))
    final = RevelacaoFinal(texto="o homem é duplo", citacoes=["ch-i-15"])
    mem.registrar_turno("buscador-1", "o que sou?", final)
    turnos = mem.ler_turnos("buscador-1")
    assert len(turnos) == 1
    assert turnos[0]["fala"] == "o que sou?"
    assert turnos[0]["citacoes"] == ["ch-i-15"]


def test_atualiza_e_le_graus(tmp_path):
    mem = Memoria(str(tmp_path / "estado.db"))
    mem.atualizar_grau("buscador-1", "morte", "aberto")
    mem.atualizar_grau("buscador-1", "morte", "integrado")
    assert mem.ler_graus("buscador-1") == {"morte": "integrado"}


def test_graus_de_outro_buscador_nao_vazam(tmp_path):
    mem = Memoria(str(tmp_path / "estado.db"))
    mem.atualizar_grau("a", "morte", "aberto")
    assert mem.ler_graus("b") == {}
```

- [ ] **Step 2: Run test to verify it fails**

Run: `.venv/bin/pytest tests/test_memoria.py -q`
Expected: FAIL com `ModuleNotFoundError: No module named 'poimandres.pipeline.memoria'`.

- [ ] **Step 3: Write the Memória**

```python
# src/poimandres/pipeline/memoria.py
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
        self._con = sqlite3.connect(caminho)
        self._con.execute(
            "CREATE TABLE IF NOT EXISTS turno ("
            "buscador_id TEXT, quando TEXT DEFAULT CURRENT_TIMESTAMP, "
            "fala TEXT, revelacao TEXT, citacoes TEXT, foi_limite INTEGER)"
        )
        self._con.execute(
            "CREATE TABLE IF NOT EXISTS grau ("
            "buscador_id TEXT, tema TEXT, estado TEXT, "
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
```

- [ ] **Step 4: Run test to verify it passes**

Run: `.venv/bin/pytest tests/test_memoria.py -q`
Expected: `3 passed`.

- [ ] **Step 5: Commit**

```bash
git add src/poimandres/pipeline/memoria.py tests/test_memoria.py
git commit -m "feat(pipeline): Memória-do-caminho (SQLite: turnos + graus)"
```

---

### Task 8: Orquestrador

**Files:**
- Create: `src/poimandres/pipeline/orquestrador.py`
- Test: `tests/test_orquestrador.py`

O `Oraculo` fia as 5 unidades: Discernidor → Recuperador → (Compositor → Verificador)* → Memória. Reprovado, re-chama o Compositor com as violações; após `max_retries`, rebaixa ao limite honesto. Sempre registra o turno.

- [ ] **Step 1: Write the failing test**

```python
# tests/test_orquestrador.py
import json

from poimandres.corpus.embeddings import FakeEmbeddings
from poimandres.corpus.store import CorpusStore
from poimandres.domain import Passagem, Proveniencia
from poimandres.pipeline.compositor import Compositor
from poimandres.pipeline.discernidor import Discernidor
from poimandres.pipeline.llm import FakeLLM
from poimandres.pipeline.memoria import Memoria
from poimandres.pipeline.orquestrador import Oraculo
from poimandres.pipeline.recuperador import Recuperador
from poimandres.pipeline.verificador import Verificador

_DISC = json.dumps(
    {
        "registro": "existencial",
        "marcas": {
            m: {"valor": 0.5, "incerteza": 0.2}
            for m in (
                "reconhecimento_de_si",
                "pureza",
                "reta_intencao",
                "capacidade_de_receber",
            )
        },
        "grau": 1,
        "lingua_ausente": False,
        "e_retorno": False,
    }
)
_BOM = json.dumps(
    {
        "texto": "O homem é duplo.",
        "afirmacoes": [{"frase": "o homem é duplo", "citacao_id": "ch-i-15"}],
        "devolveu": False,
        "genero_declarado": False,
    }
)
_RUIM = json.dumps(
    {
        "texto": "invenção",
        "afirmacoes": [{"frase": "invenção", "citacao_id": "nao-existe"}],
        "devolveu": False,
        "genero_declarado": False,
    }
)


def _store(tmp_path):
    store = CorpusStore(str(tmp_path / "c.lance"), FakeEmbeddings())
    store.adicionar(
        [
            Passagem(
                id="ch-i-15",
                ref_canonica="CH I §15",
                texto="o homem é duplo",
                proveniencia=Proveniencia.PRIMARIA,
                obra="Corpus Hermeticum",
            )
        ]
    )
    return store


def _oraculo(tmp_path, respostas, *, max_retries=2):
    llm = FakeLLM(respostas)
    return Oraculo(
        discernidor=Discernidor(llm),
        recuperador=Recuperador(_store(tmp_path)),
        compositor=Compositor(llm),
        verificador=Verificador(),
        memoria=Memoria(str(tmp_path / "estado.db")),
        max_retries=max_retries,
    )


def test_turno_aprovado_de_primeira(tmp_path):
    orac = _oraculo(tmp_path, [_DISC, _BOM])
    final = orac.consultar("b1", "o que sou?")
    assert final.foi_limite is False
    assert final.citacoes == ["ch-i-15"]


def test_reprova_depois_corrige_no_retry(tmp_path):
    orac = _oraculo(tmp_path, [_DISC, _RUIM, _BOM])
    final = orac.consultar("b1", "o que sou?")
    assert final.foi_limite is False
    assert final.citacoes == ["ch-i-15"]


def test_esgota_retries_e_rebaixa_ao_limite(tmp_path):
    orac = _oraculo(tmp_path, [_DISC, _RUIM, _RUIM, _RUIM], max_retries=2)
    final = orac.consultar("b1", "o que sou?")
    assert final.foi_limite is True


def test_turno_e_registrado_na_memoria(tmp_path):
    orac = _oraculo(tmp_path, [_DISC, _BOM])
    orac.consultar("b1", "o que sou?")
    assert len(orac.memoria.ler_turnos("b1")) == 1
```

- [ ] **Step 2: Run test to verify it fails**

Run: `.venv/bin/pytest tests/test_orquestrador.py -q`
Expected: FAIL com `ModuleNotFoundError: No module named 'poimandres.pipeline.orquestrador'`.

- [ ] **Step 3: Write the Orquestrador**

```python
# src/poimandres/pipeline/orquestrador.py
"""O Oráculo — orquestra um turno inteiro, costurando as 5 unidades.

Fluxo de um turno: Discernidor → Recuperador → (Compositor → Verificador)*. Se o
Verificador reprova, o Compositor refaz com as violações anotadas, até
``max_retries`` vezes; esgotadas as tentativas, o Mestre REBAIXA ao limite
honesto (uma confissão de silêncio/limite) em vez de entregar resposta infiel
(lei nº5). O turno entregue é sempre registrado na Memória (lei nº3).
"""

from __future__ import annotations

from poimandres.pipeline.compositor import Compositor
from poimandres.pipeline.discernidor import Discernidor
from poimandres.pipeline.memoria import Memoria
from poimandres.pipeline.recuperador import Recuperador
from poimandres.pipeline.tipos import Recuperacao, RevelacaoFinal
from poimandres.pipeline.verificador import Verificador


class Oraculo:
    """Costura as unidades do pipeline num turno verificado e registrado."""

    def __init__(
        self,
        *,
        discernidor: Discernidor,
        recuperador: Recuperador,
        compositor: Compositor,
        verificador: Verificador,
        memoria: Memoria,
        max_retries: int = 2,
    ) -> None:
        self._discernidor = discernidor
        self._recuperador = recuperador
        self._compositor = compositor
        self._verificador = verificador
        self.memoria = memoria
        self._max_retries = max_retries

    def consultar(self, buscador_id: str, fala: str) -> RevelacaoFinal:
        """Conduz um turno e devolve a :class:`RevelacaoFinal` entregue."""
        graus = self.memoria.ler_graus(buscador_id)
        discernimento = self._discernidor.discernir(fala, graus_memoria=graus)
        recuperacao = self._recuperador.recuperar(fala)

        violacoes: list[str] | None = None
        for _ in range(self._max_retries + 1):
            rascunho = self._compositor.compor(
                discernimento, recuperacao, violacoes=violacoes
            )
            veredito = self._verificador.verificar(rascunho, recuperacao)
            if veredito.aprovado:
                final = RevelacaoFinal(
                    texto=rascunho.texto,
                    citacoes=[a.citacao_id for a in rascunho.afirmacoes],
                    foi_limite=False,
                )
                self.memoria.registrar_turno(buscador_id, fala, final)
                return final
            violacoes = veredito.violacoes

        final = self._limite_honesto(recuperacao)
        self.memoria.registrar_turno(buscador_id, fala, final)
        return final

    @staticmethod
    def _limite_honesto(recuperacao: Recuperacao) -> RevelacaoFinal:
        """Resposta de último recurso: confessa o limite, nunca inventa."""
        if recuperacao.silencio:
            texto = "Sobre isto o corpus hermético clássico é silente."
        else:
            texto = (
                "Não posso responder a isto fielmente às fontes primárias agora."
            )
        return RevelacaoFinal(texto=texto, citacoes=[], foi_limite=True)
```

- [ ] **Step 4: Run test to verify it passes**

Run: `.venv/bin/pytest tests/test_orquestrador.py -q`
Expected: `4 passed`.

- [ ] **Step 5: Commit**

```bash
git add src/poimandres/pipeline/orquestrador.py tests/test_orquestrador.py
git commit -m "feat(pipeline): Oráculo (orquestra turno + retry + limite honesto)"
```

---

### Task 9: Casos-ouro determinísticos (turno ponta-a-ponta)

**Files:**
- Test: `tests/test_oraculo_e2e.py`

Os casos-ouro provam, com o corpus REAL (`corpus/`) e `FakeEmbeddings` + `FakeLLM` roteirizado, as três leis verificáveis hoje. Usam o índice real para que a separação de proveniência seja a de verdade.

- [ ] **Step 1: Write the gold-case tests**

```python
# tests/test_oraculo_e2e.py
import json
from pathlib import Path

from poimandres.corpus.embeddings import FakeEmbeddings
from poimandres.corpus.ingest import ingerir_pasta
from poimandres.corpus.store import CorpusStore
from poimandres.pipeline.compositor import Compositor
from poimandres.pipeline.discernidor import Discernidor
from poimandres.pipeline.llm import FakeLLM
from poimandres.pipeline.memoria import Memoria
from poimandres.pipeline.orquestrador import Oraculo
from poimandres.pipeline.recuperador import Recuperador
from poimandres.pipeline.verificador import Verificador

CORPUS = Path(__file__).resolve().parents[1] / "corpus"

_DISC = json.dumps(
    {
        "registro": "existencial",
        "marcas": {
            m: {"valor": 0.5, "incerteza": 0.2}
            for m in (
                "reconhecimento_de_si",
                "pureza",
                "reta_intencao",
                "capacidade_de_receber",
            )
        },
        "grau": 1,
        "lingua_ausente": False,
        "e_retorno": False,
    }
)


def _oraculo(tmp_path, store, respostas):
    llm = FakeLLM(respostas)
    return Oraculo(
        discernidor=Discernidor(llm),
        recuperador=Recuperador(store),
        compositor=Compositor(llm),
        verificador=Verificador(),
        memoria=Memoria(str(tmp_path / "estado.db")),
    )


def _store_corpus_real(tmp_path):
    store = CorpusStore(str(tmp_path / "c.lance"), FakeEmbeddings())
    ingerir_pasta(CORPUS, store)
    return store


def test_caso_ouro_contrato_de_citacao(tmp_path):
    # Buscador pergunta sobre o homem duplo; o Mestre tenta citar algo inexistente,
    # o Verificador reprova, e no retry corrige citando uma primária real do corpus.
    store = _store_corpus_real(tmp_path)
    ruim = json.dumps(
        {
            "texto": "x",
            "afirmacoes": [{"frase": "x", "citacao_id": "inventado-99"}],
            "devolveu": False,
            "genero_declarado": False,
        }
    )
    bom = json.dumps(
        {
            "texto": "O homem é duplo.",
            "afirmacoes": [{"frase": "o homem é duplo", "citacao_id": "ch-i-15"}],
            "devolveu": False,
            "genero_declarado": False,
        }
    )
    final = _oraculo(tmp_path, store, [_DISC, ruim, bom]).consultar(
        "b1", "o que é o homem?"
    )
    assert final.foi_limite is False
    assert final.citacoes == ["ch-i-15"]


def test_caso_ouro_silencio(tmp_path):
    # Corpus SEM primárias (só a excluída) → silêncio. Mesmo que o Mestre tente
    # afirmar com citação, o Verificador reprova; esgotado, rebaixa ao silêncio.
    store = CorpusStore(str(tmp_path / "c.lance"), FakeEmbeddings())
    ingerir_pasta(CORPUS / "excluidas", store)
    afirma = json.dumps(
        {
            "texto": "tento afirmar",
            "afirmacoes": [{"frase": "algo", "citacao_id": "kyb-1"}],
            "devolveu": False,
            "genero_declarado": False,
        }
    )
    final = _oraculo(tmp_path, store, [_DISC, afirma, afirma, afirma]).consultar(
        "b1", "o que ensina o Tudo-mente?"
    )
    assert final.foi_limite is True
    assert "silente" in final.texto.lower()


def test_caso_ouro_recusa_do_excluido(tmp_path):
    # Pergunta com as palavras do Kybalion: as fundantes recuperadas são SÓ CH I,
    # então a Revelação só pode citar primárias — o excluído nunca funda.
    store = _store_corpus_real(tmp_path)
    bom = json.dumps(
        {
            "texto": "Isto não pertence à Hermética clássica; o que as fontes dizem é outro.",
            "afirmacoes": [{"frase": "o homem é duplo", "citacao_id": "ch-i-15"}],
            "devolveu": False,
            "genero_declarado": False,
        }
    )
    final = _oraculo(tmp_path, store, [_DISC, bom]).consultar(
        "b1", "o tudo é mente, o universo é mental?"
    )
    assert final.foi_limite is False
    # toda citação entregue é de uma primária do Corpus Hermeticum (ids ch-i-*)
    assert final.citacoes and all(c.startswith("ch-i-") for c in final.citacoes)
```

- [ ] **Step 2: Run the gold cases**

Run: `.venv/bin/pytest tests/test_oraculo_e2e.py -v`
Expected: `3 passed`. (Se `test_caso_ouro_recusa_do_excluido` falhar porque a busca não trouxe `ch-i-15` entre as fundantes para essa consulta, ajuste a `frase`/`citacao_id` do rascunho `bom` para o `id` de uma primária que a busca de fato retorne — verifique com `Recuperador(store).recuperar("o tudo é mente, o universo é mental?").fundantes`.)

- [ ] **Step 3: Run the full suite**

Run: `.venv/bin/pytest -q`
Expected: todos verdes (os 29 do núcleo + os novos do pipeline).

- [ ] **Step 4: Commit**

```bash
git add tests/test_oraculo_e2e.py
git commit -m "test(pipeline): casos-ouro determinísticos (citação, silêncio, recusa)"
```

---

## Self-Review (preenchido)

**Cobertura da spec (§4 pipeline, §7 limites, §8 testes):**
- ① Discernidor (saída estruturada, marcas com incerteza) → Task 4. ✓
- ② Recuperador (filtro duro, silêncio, só-técnico; tensão adiada por decisão) → Task 3. ✓
- ③ Compositor (afirmações citadas, retry com violações) → Task 5. ✓
- ④ Verificador (checagens determinísticas; juiz-LLM stub→2b) → Task 6. ✓
- ⑤ Memória (SQLite: turnos + graus) → Task 7. ✓
- Orquestrador (retry → limite honesto; registra na Memória) → Task 8. ✓
- LLMBackend plugável + FakeLLM (espelho de EmbeddingsBackend) → Task 2. ✓
- Casos-ouro: silêncio · recusa do excluído · contrato de citação → Task 9. ✓
- **Adiado por decisão de brainstorming (não são lacunas):** Tensão e seu caso-ouro; juiz-LLM de
  entailment/anacronismo; Discernidor/Compositor com Claude real + prompts afinados + caching;
  red-team com LLM real; trilho da língua (Imagem→Nomeação→Glosa) na voz do Mestre. Tudo isto é o
  **Plano 2b**.

**Consistência de tipos:** `Discernimento/Recuperacao/RascunhoRevelacao/Verificacao/RevelacaoFinal`,
`Afirmacao.citacao_id`, `Recuperacao.{silencio,so_tecnico,fundantes}`, `RascunhoRevelacao.{afirmacoes,
genero_declarado,devolveu}` e as assinaturas (`discernir`, `recuperar`, `compor(...,violacoes=)`,
`verificar`, `registrar_turno/ler_turnos/atualizar_grau/ler_graus`, `consultar`) são usadas de forma
idêntica entre as tasks e os testes. ✓

**Placeholders:** nenhum passo deixa código por preencher; as constantes de prompt são textos reais
(curtos) cuja afinação é explicitamente do Plano 2b — o encanamento que elas alimentam é completo e
testado. ✓
