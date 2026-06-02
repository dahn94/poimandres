# Poimandres — Design do Plano 2b: O Claude real e a Condução

**Data:** 2026-06-02
**Relaciona-se a:** `2026-06-02-poimandres-oracle-design.md` (spec-mãe) e
`docs/superpowers/plans/2026-06-02-poimandres-pipeline-2a.md` (espinha determinística, completa).
**Status:** desenho aprovado; pronto para o plano de implementação.

---

## 1. Propósito e fronteira

O Plano 2a entregou a **espinha determinística do turno** com um `FakeLLM`: as 5 unidades, o
Orquestrador, o retry e o limite honesto, com as 3 leis verificáveis (citação · silêncio · recusa do
excluído) verdes por construção (59 testes). O **Plano 2b troca o cérebro falso pelo Claude real e
afina a Condução** — entrega o oráculo respondendo ponta-a-ponta.

**Natureza diferente do 2a.** O 2a era encanamento determinístico (TDD puro). O 2b é **engenharia de
prompt + avaliação contra um modelo não-determinístico e pago**. Por isso a estratégia de teste é em
**dois níveis** (§7): a suíte determinística com `FakeLLM` segue sendo o portão de regressão rápido e
offline; a qualidade da Condução é medida empiricamente por uma suíte de **evals** opt-in contra a API
real. A afinação fina dos prompts é uma **fase iterativa** contra os evals, não um checkbox congelado.

## 2. Backend `ClaudeLLM`

Implementa o mesmo `LLMBackend` do 2a (`gerar(PedidoLLM) -> str`), via SDK `anthropic`.

- **Portabilidade (decisão, corrigida):** a interface continua devolvendo **texto**; a saída
  estruturada é obtida por **structured outputs** (`output_config.format` com um JSON schema), não
  por prefill (prefill na última fala do assistente **retorna 400** em Opus 4.8 / Sonnet 4.6) nem por
  tool-use (que amarraria a modelos com tool-use). O `PedidoLLM` ganha um campo opcional
  `schema: dict | None`: o `ClaudeLLM` o usa via `output_config.format` (Claude garante JSON válido
  contra o schema); um backend local futuro pode embutir o mesmo schema no prompt. O `parsing.py`
  estrito + o loop de retry seguem como rede de segurança. Estruturados são suportados em Opus 4.8 /
  Sonnet 4.6 e convivem com adaptive thinking.
- **Modelo por injeção:** instâncias distintas — `ClaudeLLM(opus)` injetada no Compositor;
  `ClaudeLLM(sonnet)` no Discernidor e no juiz do Verificador. A unidade não conhece o modelo; o
  *dependency injection* (no factory, §5) decide. Modelos: Opus 4.8 (`claude-opus-4-8`) para o
  Compositor; Sonnet (`claude-sonnet-4-6`) para Discernidor e juiz.
- **Prompt caching:** `cache_control` no bloco de **sistema** (as leis do Mestre são longas e estáveis
  entre turnos), reduzindo custo e latência. A implementação seguirá a skill `claude-api`.
- **Erros:** falhas de API/transporte propagam como exceção; JSON inválido segue o caminho de retry já
  existente; sem `ANTHROPIC_API_KEY`, o backend não é instanciável (os evals pulam).

## 3. Os três prompts reais

Os prompts nascem em versão **inicial** (eu rascunho das leis da spec; o especialista refina contra os
evals — a palavra final é dele).

- **Discernidor (Sonnet):** da fala → JSON do `Discernimento`. Lê as 4 marcas da Disposição *com
  incerteza* (lei nº7, humildade), o Registro, o Grau *emergente* (sem currículo) e os sinais
  `lingua_ausente`/`e_retorno`. Reforça os trilhos desacoplados (lei nº2): ignorância de léxico ≠
  despreparo da alma.
- **Compositor (Opus) — a voz do Mestre:** recebe `Discernimento` + fundantes + iluminantes. Compõe a
  Revelação na postura de Condução (Hermes conduz Tat):
  - **Contrato de citação:** toda afirmação doutrinal traz o `citacao_id` de uma fundante.
  - **Modulação suave do grau:** revela só até a profundidade que a Disposição autoriza; guarda/adia os
    mistérios mais altos, aponta o caminho sem despejar. (Juízo do Mestre; sem porta estrutural.)
  - **Trilho da língua:** quando `lingua_ausente`, entra por Imagem → Nomeação → Glosa.
  - **Devolução:** pode devolver uma pergunta/Movimento em vez de revelar (`devolveu=True` +
    `movimentos`).
  - **Gênero:** se `so_tecnico`, declara o gênero (`genero_declarado=True`).
  - **Iluminantes:** tece a erudição como *iluminação* (marcada como tal), nunca como fundamento.
- **Juiz do Verificador (Sonnet):** roda **após** as 3 checagens determinísticas do 2a (que
  permanecem). Para cada afirmação, dado o **texto da fundante citada** + a frase, julga:
  - **Entailment** — a passagem realmente sustenta a afirmação? (anti-alucinação semântica)
  - **Anacronismo** — termo técnico/moderno entregue sem glosa?
  - **Gênero** — confusão de gêneros não declarada?
  Devolve violações estruturadas que entram no **mesmo loop de retry** do Orquestrador. O juiz não
  checa grau (modulação suave é juízo, não lei falsificável).

## 4. Fiação das postergações do 2a

- **Devolução:** o Orquestrador passa a considerar `rascunho.devolveu`/`movimentos`; uma devolução é um
  turno válido (não infidelidade) — a `RevelacaoFinal` carrega a pergunta/Movimento. `RevelacaoFinal`
  ganha um campo `movimentos: list[str]` (vazio por padrão) para surfacar o que o Mestre pediu.
- **Iluminantes:** entram no prompt do Compositor (bloco "ILUMINA, não funda"); o juiz garante que não
  sejam usados como fundamento.
- **`genero_declarado`:** ensinado no prompt do Compositor.

## 5. Entrada mínima para exercitar o oráculo

- Um factory `montar_oraculo(...)` que fia os backends Claude nas 5 unidades (Opus no Compositor,
  Sonnet nos demais), a `Memoria` e o `CorpusStore`.
- Um comando CLI `poimandres perguntar "<fala>" [--buscador <id>]` para sentir o oráculo na mão.
- O chat web do círculo + chaves-de-convite são o **Plano 3** (fora do 2b).

## 6. Stack e dependências

Adiciona `anthropic` (SDK) às dependências. Embeddings/vector store/estado seguem locais (2a). Só as
chamadas de LLM saem da máquina (Claude API) — custo por token e o texto da consulta trafega para a
API, como já registrado na spec-mãe §6.

## 7. Estratégia de testes (dois níveis)

- **Nível 1 — regressão determinística (`tests/`, FakeLLM):** os 59 testes do 2a seguem verdes. O
  encanamento novo ganha testes determinísticos: construção do request do `ClaudeLLM` (com o SDK
  mockado — verifica modelo, `cache_control`, prefill); lógica do juiz com `FakeLLM` (entrada
  roteirizada → violações esperadas); fiação de devolução/iluminantes/`genero_declarado`. Rápido,
  offline, grátis, no CI.
- **Nível 2 — evals de fidelidade (`evals/`, API real, opt-in):** marcados para pular sem
  `ANTHROPIC_API_KEY`. Casos-ouro da spec-mãe §8 + red-team (iscas sincréticas, anacronismo, invenção).
  **Asserções tolerantes de comportamento** — `foi_limite`, proveniência das citações (`ch-i-*`),
  veredito do juiz, ausência de fontes excluídas — nunca igualdade de texto. São avaliações empíricas,
  rodadas quando há chave; guiam a afinação iterativa dos prompts.

## 8. O que fica para depois (não-2b)

- Afinação fina e contínua dos prompts (fase iterativa que *começa* no 2b mas não "termina").
- Plano 3: interface do círculo (FastAPI + chat web + chaves-de-convite).
- Migração do LLM para modelo local (a interface `LLMBackend` já preserva a opção).
- Tensão (`corpus/tensoes/`) e o grafo de doutrina (com a lógica paraconsistente de Belnap/da Costa,
  registrada em `logica-paraconsistente-tensoes`).
