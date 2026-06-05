# Poimandres — Backend LLM local (Gemma 4), híbrido com toggle (Design)

**Data:** 2026-06-05
**Status:** aprovado (brainstorming) — pronto para o plano de implementação.

## Problema

O pipeline depende só da interface `LLMBackend` (`pipeline/llm.py`), mas o único
backend real é `ClaudeLLM` (API Anthropic). A intenção sempre registrada foi
"migrar o LLM para um modelo local depois = só config". Este desenho materializa
esse backend local com **Gemma 4**, mantendo o **híbrido**: `ClaudeLLM` e
`LocalLLM` coexistem e um **toggle** (env var) escolhe qual roda — para privacidade,
custo $0 e operação offline, sem perder a voz plena do Mestre (Claude) quando se
quer.

Restrição de domínio que pesa no desenho: o log de produção mostra que o trilho da
língua da Condução (Imagem→Nomeação→Glosa) só roda de forma confiável no Opus; um
modelo local é mais fraco. O híbrido com toggle preserva a escolha turno a turno.

## Decisões (do brainstorming)

- **Híbrido com toggle**, não substituição. `ClaudeLLM` permanece.
- **Toggle por env var** (12-factor, amigável a Docker): `POIMANDRES_LLM=claude|local`.
- **`LocalLLM` = um cliente OpenAI-compatible** com `base_url` configurável. mlx-lm
  (Apple) e vLLM (Linux/GPU) falam o mesmo dialeto OpenAI → uma só classe serve aos dois.
- **Runtime por plataforma:** Mac/M4 → `mlx_lm.server` nativo no host (Metal);
  Linux com GPU NVIDIA → `vllm/vllm-openai` dockerizado. Auto-detect por plataforma
  como default; `POIMANDRES_LOCAL_URL` sobrescreve.
- **Modelo primário:** Gemma **26B-A4B** (MoE, 4B ativos) — no Mac em **MLX 4-bit**
  da Unsloth; no Linux servido pelo vLLM. Fallback leve no Mac: **12B Q8**.
- **Metal não entra em Docker no Mac** (limitação Apple): o mlx-lm roda no host; o
  container do app o alcança via `host.docker.internal`.
- **Thinking** (Gemma 4 `<|think|>`) **ligado só no Compositor** (voz do Mestre);
  desligado no Discernidor e no juiz do Verificador (JSON rápido e limpo).

## Achado que molda a implementação

Os **três** papéis enviam `schema` e fazem `json.loads(bruto)` sobre o retorno —
inclusive o Compositor (`compositor.py:131-134`, além de `discernidor.py:87-90` e
`verificador.py:93-96`). Logo:

1. O `LocalLLM` precisa **sempre devolver JSON puro** (sem canal de pensamento, sem
   cercas de código), porque a unidade chama `json.loads` direto no texto.
2. "Pensar" não pode ser inferido pela ausência de schema (todos têm). A distinção
   vem da **fábrica**, por papel (ver `montar_oraculo_local`).

## Arquitetura

```
                    POIMANDRES_LLM = claude | local
                                 │
          ┌──────────────────────┴───────────────────────┐
          ▼                                               ▼
     ClaudeLLM  (API Anthropic)                  LocalLLM  (OpenAI-compat client)
     Opus/Sonnet, output_config nativo           base_url p/ servidor local
          │                                               │
          │                          POIMANDRES_LOCAL_URL │ (ou auto por plataforma)
          │                          ┌────────────────────┴─────────────────┐
          │                          ▼ Darwin (host)           Linux (GPU)  ▼
          │                     mlx_lm.server              vllm/vllm-openai (Docker)
          │                     :8080/v1 (Metal)           :8000/v1 (--gpus all)
          │                     Unsloth Gemma-4 MLX        Gemma-4
          ▼                                               ▼
   ┌───────────────────────────── Oraculo (mesmas 5 unidades) ─────────────────────┐
   │  Discernidor(rápido)   Compositor(mestre, pensar=ON)   Verificador(rápido)      │
   └────────────────────────────────────────────────────────────────────────────────┘
```

Nada nas 5 unidades muda: a interface `LLMBackend` já isola. Entra um novo backend
e uma seleção por env. mlx-lm e vLLM compartilham o dialeto OpenAI, então o toggle
de runtime é apenas o `base_url`.

## Componentes

### 1. `LocalLLM` (em `pipeline/llm.py`)

Cliente OpenAI-compatible (lib `openai`, `base_url` + `api_key` dummy). Mesmo
contrato `LLMBackend` do `FakeLLM`/`ClaudeLLM`. Em `gerar(pedido)`:

- **Embute o schema no prompt** (instrução "responda SOMENTE com JSON conforme este
  schema: …") quando `pedido.schema` está presente — garantia portável entre
  mlx-lm e vLLM.
- **E** envia `response_format` como `json_schema` quando há schema (vLLM impõe por
  guided-decoding; mlx-lm, quando suportar, reforça; senão o prompt carrega). Cinto
  e suspensório.
- `chat_template_kwargs={"enable_thinking": pensar}` (passado no `extra_body`).
  `pensar` é fixado na construção (injeção por papel).
- **Limpa a saída antes de devolver:** remove o canal de pensamento
  (`<|channel>thought … <channel|>` / bloco vazio), remove cercas ` ```json … ``` `,
  e extrai o objeto `{…}` externo. Devolve JSON puro para o `json.loads` da unidade.
- Erra alto e diagnosticável se não houver bloco JSON (espelha o `RuntimeError` do
  `ClaudeLLM`), para não passar em falso.
- Amostragem Gemma 4 default (`temperature=1.0`, `top_p=0.95`, `top_k=64`),
  ajustável na construção; `max_tokens` configurável. (Se o JSON ficar instável nos
  papéis estruturais, baixar a temperatura é um botão exposto — não default.)

Construção: `LocalLLM(base_url, modelo, *, pensar=False, max_tokens=..., temperature=..., top_p=..., top_k=...)`.

### 2. `montar_oraculo_local()` (em `pipeline/fabrica.py`)

Irmão de `montar_oraculo_economico`. Constrói o `Oraculo` com `LocalLLM` em todos os
papéis. `fazer_llm(modelo)` devolve `LocalLLM(base_url, modelo, pensar=(modelo == modelo_mestre))`
— assim o Compositor (recebe `modelo_mestre`) pensa; Discernidor/Verificador (recebem
`modelo_rapido`) não. `base_url` e nomes de modelo vêm por argumento, com default por
plataforma (ver §3). Reusa `montar_oraculo(..., fazer_llm=…)` para não duplicar a
fiação das unidades.

### 3. Seleção e defaults por plataforma (em `cli.py`)

- `servir` e `perguntar` leem `POIMANDRES_LLM` (default `claude`).
  - `local` → `montar_oraculo_local(...)`.
  - `claude` → comportamento atual (`--opus` → `montar_oraculo`; senão
    `montar_oraculo_economico`). Os flags Claude permanecem intactos.
- `base_url` local: `POIMANDRES_LOCAL_URL` se setado; senão default por
  `platform.system()`:
  - `Darwin` → `http://127.0.0.1:8080/v1` (mlx-lm).
  - outro (Linux) → `http://127.0.0.1:8000/v1` (vLLM).
- Helper isolado (ex.: `_endpoint_local()` / `_montar_por_env(...)`) testável sem rede.

### 4. Dependências

- Adicionar `openai>=1.0` às deps do `pyproject` (cliente do `LocalLLM`).
- `mlx-lm` **não** é dep do app — é o servidor, rodado à parte no host. Entra como
  extra opcional `[local-mac]` para conveniência de instalação.
- vLLM **não** é dep Python — vem pela imagem Docker.

## Instalação no Mac M4 Pro (24 GB) — "a melhor instalação"

- **Modelo:** Gemma **26B-A4B** MLX 4-bit da Unsloth (~16-18 GB). Fallback: **12B Q8**.
- **Servidor (host, fora do Docker):**
  `mlx_lm.server --model unsloth/gemma-4-26b-a4b-it-MLX-4bit --port 8080`.
- **Folga de Metal:** `sudo sysctl iogpu.wired_limit_mb=20480` (≈20 GB à GPU) para a
  26B caber com contexto + BGE-M3 + app.
- Empacotar em `scripts/servidor-mlx.sh` (sobe wired_limit + `mlx_lm.server`),
  análogo ao `servir.sh`.

## Docker

- **`Dockerfile`** do app: `python:3.12-slim` + `uv`, instala o projeto, `EXPOSE 8000`,
  `CMD poimandres servir --porta 8000`.
- **`docker-compose.yml`:**
  - serviço `app` (sempre); recebe `POIMANDRES_LLM`, `POIMANDRES_LOCAL_URL`,
    `ANTHROPIC_API_KEY` por env.
  - serviço `vllm` sob *profile* `gpu` (imagem `vllm/vllm-openai`, `--gpus all`,
    modelo Gemma-4, porta 8000).
  - **Mac:** sobe só `app`; `POIMANDRES_LOCAL_URL=http://host.docker.internal:8080/v1`
    aponta ao mlx-lm do host. (Metal não entra em container — limitação Apple.)
  - **Linux/GPU:** `docker compose --profile gpu up` sobe `app` + `vllm` juntos;
    `POIMANDRES_LOCAL_URL=http://vllm:8000/v1`.

## Testes (TDD)

- `LocalLLM` testado **sem rede**: transporte OpenAI stubado (monkeypatch do cliente)
  verifica:
  - wiring do pedido: `response_format=json_schema` quando há schema, schema embutido
    no prompt, `enable_thinking` conforme `pensar`, amostragem default;
  - **limpeza da saída**: remove canal de pensamento, remove cercas, extrai o `{…}`,
    devolve JSON puro; erra alto quando não há JSON.
- `montar_oraculo_local`: injeta `fazer_llm` fake e confere `pensar=True` só no
  Compositor.
- Seleção por env: helper testado lendo `POIMANDRES_LLM`/`POIMANDRES_LOCAL_URL` e o
  default por plataforma (monkeypatch de `platform.system`).
- `FakeLLM` e os testes determinísticos existentes permanecem intactos.
- **Smoke real** (Gemma de fato servindo via mlx-lm) é **manual**, como o do BGE-M3
  — não roda na suíte.

## Fora de escopo (YAGNI)

- Fine-tuning da Gemma (Unsloth treina, mas não é o objetivo aqui).
- Multimodal (imagem/áudio da Gemma 4) — o oráculo é texto.
- Streaming de tokens (o `servir` já trata o turno lento por polling).
- Roteamento por papel entre Claude e local (ex.: Compositor no Claude, resto local):
  a interface permite no futuro, mas o toggle atual é por preset (tudo-Claude ou
  tudo-local).
- Cache/quantização-aware training, Unsloth Studio como motor do pipeline (é UI
  interativa, não backend de biblioteca).

## Riscos e mitigações

- **Voz do Mestre mais fraca no local** — esperado; o toggle deixa voltar ao Opus. O
  thinking ligado no Compositor é a mitigação dentro do local.
- **JSON inválido do modelo local** — schema embutido no prompt + `response_format` +
  limpeza/extração defensiva + erro alto; botão de baixar temperatura se necessário.
- **Memória apertada na 26B (24 GB)** — `iogpu.wired_limit_mb` e fallback 12B Q8.
- **mlx-lm fora do Docker** — documentado; o app no container fala com o host.
```
