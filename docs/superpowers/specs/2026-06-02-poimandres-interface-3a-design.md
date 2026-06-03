# Poimandres — Design do Plano 3a: Chat web local do oráculo

**Data:** 2026-06-02
**Relaciona-se a:** `2026-06-02-poimandres-oracle-design.md` (spec-mãe, §6 "Interface do círculo")
e aos planos 2a/2b (o pipeline `poimandres.pipeline` + `montar_oraculo`).
**Status:** desenho aprovado; pronto para o plano de implementação.

---

## 1. Propósito e fronteira

Tirar o oráculo da CLI e dar a experiência de **chat web** — uma primeira versão **local, de um
único buscador** (você), sem autenticação. Valida a UI e, sobretudo, o **fluxo do turno lento**
(cada consulta são 3 chamadas LLM, ~minuto) antes da complexidade de auth/multiusuário/deploy.

**Fora do 3a (reservado ao 3b):** chaves-de-convite, tabela `buscador`, multiusuário, deploy na VPS,
e streaming de etapas (presença "discernindo… compondo…"). A spec-mãe (§163, §187) prevê esses;
o 3a constrói a espinha sobre a qual o 3b cresce.

## 2. Arquitetura

Um app **FastAPI** (`src/poimandres/web/`) que envolve o `Oraculo` existente (via
`montar_oraculo`/`montar_oraculo_economico`), servindo HTML renderizado no servidor (Jinja2) + um JS
mínimo de polling. Sem SPA, sem build step. Um comando CLI `poimandres servir` sobe o `uvicorn`.

```
src/poimandres/web/
├── __init__.py
├── app.py            cria o FastAPI; injeta o Oráculo; rotas; registro de turnos-em-voo
├── templates/
│   └── chat.html     a página do chat (histórico + caixa de fala + JS de polling)
└── static/
    └── estilo.css    CSS mínimo
```

Novas dependências: `fastapi`, `uvicorn[standard]`, `jinja2`.

## 3. Fluxo do turno (assíncrono + polling)

Single-user, single-process → o registro de turnos-em-voo é um **dict em memória**
(`turno_id -> {estado, resultado}`); não há tabela de jobs. O `Oraculo.consultar` roda **sem
alteração** numa thread (`fastapi.concurrency.run_in_threadpool`), liberando o event loop.

```
[navegador]                          [FastAPI]                          [Oráculo]
 GET /              ──────────────▶  renderiza chat + histórico (Memoria.ler_turnos)
 POST /perguntar {fala} ─────────▶  turno_id = novo; EM_VOO[id]={estado:"considerando"};
                                     dispara consultar() em thread; ao terminar grava o
                                     resultado em EM_VOO[id] (a Memória já é gravada dentro
                                     de consultar)
                   ◀──────────────  {turno_id, estado:"considerando"}
 GET /turno/{id} (a cada ~2s) ───▶  devolve EM_VOO[id]: "considerando" | "pronto"+Revelação
                   ◀──────────────  quando "pronto", a página troca a espera pela Revelação
```

- Exceção dentro de `consultar` (ex.: falha da API) → `EM_VOO[id]={estado:"erro", msg}`; a página
  mostra uma mensagem honesta e não quebra. O turno de erro **não** é registrado como Revelação.
- O dict é efêmero (reinício do servidor o limpa); o histórico durável vive na Memória (SQLite),
  relido em `GET /`.

## 4. Endpoints

| Método | Rota | Faz |
|---|---|---|
| `GET` | `/` | Renderiza `chat.html`: histórico do buscador (`Memoria.ler_turnos("local")`) + caixa de fala. |
| `POST` | `/perguntar` | Body `{fala}`. Cria `turno_id`, dispara o turno em thread, devolve `{turno_id, estado:"considerando"}`. |
| `GET` | `/turno/{turno_id}` | Status do turno: `{estado}` ou, pronto, `{estado:"pronto", texto, citacoes, movimentos, foi_limite}`. |

Buscador fixo `"local"` no 3a (sem auth). A `RevelacaoFinal` é serializada em JSON pelos campos
(`texto`, `citacoes`, `foi_limite`, `movimentos`).

## 5. A tela (mínima, fiel à Condução)

```
┌──────────────────────────────────────────┐
│  Poimandres                                │
│  você: o que sou eu diante da morte?       │
│  ⟡ o Mestre considera tua fala…            │   (estado de espera, durante o polling)
│  ⟡ Mestre: O homem é duplo… [Revelação]    │
│      ▸ funda em CH I §15, §24              │   (citações)
│      → observe o que move tua pergunta     │   (Movimento)
│  ┌────────────────────────────────────┐    │
│  │ fala…                          [↵]  │    │
│  └────────────────────────────────────┘    │
└──────────────────────────────────────────┘
```

- Revelação fundada: texto + citações (`funda em <ref_canonica>`) + movimentos (`→ …`).
- Silêncio/limite (`foi_limite=True`): renderiza como confissão honesta, sem citações.
- Devolução (sem citações, com movimentos): renderiza o texto + os movimentos.
- **Histórico vs. turno ao vivo:** a tabela `turno` da Memória guarda fala/revelação/citações/
  foi_limite, mas **não** `movimentos`. Logo, os movimentos aparecem no **turno ao vivo** (via
  `GET /turno/{id}`), e o histórico relido em `GET /` mostra fala/revelação/citações. Persistir
  movimentos (coluna na tabela `turno`) é um refinamento do 3b.

## 6. Modelo & custo

`poimandres servir` aceita `--economico` (default — Sonnet, barato) ou `--opus` (voz plena, mais caro)
e `--porta` (default 8000). O modelo é escolhido ao subir o servidor, dando controle de gasto. Usa o
índice padrão (`.poimandres/corpus.lance`, BGE-M3 local) e a Memória padrão (`.poimandres/estado.db`).

## 7. Injeção e testes

`app.py` expõe uma fábrica de app, `criar_app(oraculo=None)`: quando `oraculo` é dado, usa-o
(testes injetam um **Oráculo falso**, sem LLM real); quando `None`, monta o real via fábrica. Os
testes usam `fastapi.testclient.TestClient` e cobrem, sem custo:
- `GET /` renderiza a página (e o histórico, quando há turnos na Memória).
- `POST /perguntar` cria o turno e responde "considerando"; `GET /turno/{id}` faz polling até
  "pronto" e devolve a Revelação (com um Oráculo fake rápido).
- Casos de **silêncio/limite** (`foi_limite=True`) e de **erro** (o fake levanta exceção →
  estado "erro", página não quebra).

O `run_in_threadpool` mantém o handler assíncrono; nos testes, um Oráculo fake retorna na hora.

## 8. Fora de escopo (futuro)
- **3b:** chaves-de-convite + tabela `buscador` + multiusuário + deploy na VPS + streaming de etapas.
- Autenticação robusta, HTTPS, rate-limiting, serviço público aberto (a spec-mãe os exclui da 1ª fase).
