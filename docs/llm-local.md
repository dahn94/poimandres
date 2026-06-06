# LLM local (Gemma 4) — híbrido com toggle

O oráculo roda com Claude (default) ou com Gemma 4 local. O toggle é a env
`POIMANDRES_LLM` (`claude` | `local`). Mesmo backend `LocalLLM` (cliente
OpenAI-compatible) serve aos dois runtimes — só muda o `base_url`.

## Mac (M4) — mlx-lm no host

1. Instale o extra: `uv sync --extra local-mac`
2. Suba o servidor (baixa o modelo no 1º uso): `./scripts/servidor-mlx.sh`
   - Default: `unsloth/gemma-4-26b-a4b-it-MLX-4bit` na porta 8080.
   - Variante leve (24 GB apertados): `./scripts/servidor-mlx.sh unsloth/gemma-4-12b-it-MLX-8bit`
3. Em outro terminal: `POIMANDRES_LLM=local ./servir.sh`
   (o default por plataforma já aponta a `http://127.0.0.1:8080/v1`).

A thinking da Gemma fica **ligada só no Compositor** (a voz do Mestre); Discernidor
e Verificador rodam sem pensamento, devolvendo JSON limpo.

## Linux com GPU NVIDIA — vLLM via Docker

```bash
POIMANDRES_LLM=local POIMANDRES_LOCAL_URL=http://vllm:8000/v1 \
  docker compose --profile gpu up
```

No Mac, **não** use o perfil `gpu` (Metal não entra em container): rode o app com
`POIMANDRES_LOCAL_URL=http://host.docker.internal:8080/v1` apontando ao mlx-lm do host.

## Voltar ao Claude

Sem `POIMANDRES_LLM` (ou `=claude`): usa o preset econômico (Sonnet); `--opus`
para a voz plena do Mestre. A voz do Mestre degrada no local — o toggle existe
justamente para escolher turno a turno.

## Limitação conhecida (índice do corpus)

O container do app traz a **fonte** do corpus (`corpus/`), mas **não** um índice já
ingerido (`.poimandres/corpus.lance`), que o `servir` espera. Para rodar o container
é preciso prover o índice (montar um volume com o `.poimandres/` já ingerido, ou
ingerir dentro do container — o que baixa o modelo BGE-M3, ~2 GB). A provisão de
corpus no deploy é tema do **Plano 3b** (deploy na VPS), fora do escopo do toggle de
LLM. Localmente (sem Docker), `poimandres ingest corpus/` cuida disso.
