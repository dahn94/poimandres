#!/usr/bin/env bash
# Sobe a Gemma 4 via mlx-lm no host (Metal) para o Poimandres local.
# Uso:  ./scripts/servidor-mlx.sh                                  (26B-A4B MLX 4-bit, :8080)
#       ./scripts/servidor-mlx.sh unsloth/gemma-4-12b-it-MLX-8bit  (variante leve)
#       ./scripts/servidor-mlx.sh <modelo> <porta>
# Depois, em outro terminal:  POIMANDRES_LLM=local ./servir.sh
# Requer o extra:  uv sync --extra local-mac
set -euo pipefail
cd "$(dirname "$0")/.."
MODELO="${1:-unsloth/gemma-4-26b-a4b-it-MLX-4bit}"
PORTA="${2:-8080}"
# Dá ~20 GB ao Metal (de 24 GB unificados) p/ a 26B caber com contexto.
sudo sysctl -w iogpu.wired_limit_mb=20480 || echo "aviso: não ajustou iogpu.wired_limit_mb"
exec uv run --extra local-mac python -m mlx_lm.server --model "$MODELO" --port "$PORTA"
