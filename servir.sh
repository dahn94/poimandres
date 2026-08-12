#!/usr/bin/env bash
# Sobe o chat web local do Poimandres em http://127.0.0.1:8000
# Uso:  ./servir.sh            (modo econômico, Sonnet — barato)
#       ./servir.sh --opus     (voz plena do Mestre — mais caro)
#       ./servir.sh --porta 8001
# Pare com Ctrl+C. Requer credencial Anthropic (ANTHROPIC_API_KEY ou `ant auth login`).
cd "$(dirname "$0")"
exec .venv/bin/poimandres servir "$@"
