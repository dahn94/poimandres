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
