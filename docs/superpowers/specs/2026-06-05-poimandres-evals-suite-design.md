# Poimandres — Suíte de evals de fidelidade e Condução (Design)

**Data:** 2026-06-05
**Status:** aprovado em princípio (Abordagem A) — spec a revisar antes do plano.

## Problema

Existe uma **fundação** de evals (`evals/conftest.py` + `evals/test_fidelidade.py`):
3 casos sob medida, asserções tolerantes (nunca igualdade de texto), Claude real
atrás do marcador `eval` (pula sem credencial), corpus real + `FakeEmbeddings`
(recuperação determinística e grátis), modo econômico. É pouco para um oráculo cuja
razão de existir é a **fidelidade**: não há corpus adversarial crescente, não há juiz
semântico (má-atribuição e anacronismo escapam ao assert estrutural), e a qualidade
da **Condução** (graduada) não é medida.

Este desenho cresce a fundação para uma suíte **estruturada, adversarial, com
falha-dura de fidelidade** e **nota de Condução** registrada — sem trair o ethos do
projeto (unidades pequenas e próprias, determinismo onde der, LLM real atrás de
marcador).

## Decisões (do brainstorming — Abordagem A)

- **Duas faixas de avaliação:**
  - **Fidelidade = portão (falha-dura).** Violação reprova o teste.
  - **Condução = graduada (nota registrada).** Pontuada para tendência, não trava
    o build por padrão.
- **O portão de fidelidade é estrutural + semântico:**
  - **Estrutural** (determinístico, grátis): asserts sobre o traço.
  - **Semântico** (juiz-LLM): pega o que o estrutural não pega — **má-atribuição**
    (citar uma fundante real que não diz aquilo) e **anacronismo** na prosa.
- **Casos dirigidos por DADOS, não funções:** `evals/casos/*.yaml`, cada caso é um
  registro estruturado. A suíte cresce adicionando dado.
- **Reuso da infra existente:** marcador `eval`, `conftest` (skip por credencial),
  fábrica, `FakeEmbeddings`, corpus real.

## As quatro dimensões da Condução (rubrica v1)

Derivadas das leis fixadas no `_SISTEMA` do Compositor (`compositor.py`):

1. **Modulação do Grau** (lei 2) — revelou no grau que a Disposição autoriza; não
   reteve o que cabia nem despejou acima do grau.
2. **Nomeação / trilho da Língua** (lei 3) — quando a fala descreve em palavras
   comuns algo que uma fundante nomeia, **deu o nome** (Imagem→Nomeação→Glosa) sem
   anacronismo. (É o crux do achado de produção: o trilho só roda confiável no Opus.)
3. **Sondar vs Revelar** (lei 5) — devolveu/sondou só quando a Disposição era
   baixa/incerta ou a fala vaga; tendo fundante e Disposição, **revelou** em vez de
   trocar a Revelação por perguntas.
4. **Avanço** (lei 7) — em diálogo, **aprofundou** o grau a cada troca, variou os
   Movimentos, não re-sondou o já respondido nem refundou sempre nos mesmos versos.

> **Consequência estrutural:** "Avanço" exige **casos multi-turno** (roteiro de
> falas), não tiro único. O harness precisa conduzir o mesmo buscador por vários
> turnos (a Memória/histórico acumula entre eles).

## Arquitetura

```
 evals/casos/*.yaml  ──►  harness (pytest parametrizado)
                              │   1 caso (ou roteiro) -> oraculo.consultar() x N turnos
                              ▼
                   RevelacaoFinal + corpus (CorpusStore)
                              │
        ┌─────────────────────┴──────────────────────┐
        ▼ FAIXA FIDELIDADE (portão)                   ▼ FAIXA CONDUÇÃO (graduada)
   ┌──────────────┐   ┌───────────────────┐     ┌────────────────────┐
   │ Portão       │   │ Juiz semântico    │     │ Meta-juiz (LLM)    │
   │ ESTRUTURAL   │   │ (LLM): sustentação│     │ pontua as 4        │
   │ (det., grátis)│  │ + anacronismo     │     │ dimensões (0..n)   │
   └──────┬───────┘   └─────────┬─────────┘     └─────────┬──────────┘
          └── viola? FALHA-DURA ─┘                         │
                                                  nota registrada (tendência;
                                                  limiar opcional)
```

Nada nas 5 unidades do pipeline muda. A suíte é um **observador externo**: dá a
fala, lê o `RevelacaoFinal`, resolve as citações no `CorpusStore` e julga.

## Componentes

### 1. Casos como dado — `evals/casos/*.yaml`

Cada caso:

```yaml
- id: isca-lei-da-atracao
  categoria: sincretismo
  fala: "o hermetismo não é a mesma coisa que a Lei da Atração?"
  # OU, para multi-turno:
  # roteiro: ["...", "...", "..."]
  espera_estrutural:        # asserts do portão estrutural (todos opcionais)
    nao_funda_prefixo: ["kyb-"]     # nenhuma citação começa com…
    foi_limite_ou_sem: ["kyb-"]     # limite OU nenhuma dessas citações
  foco_de_conducao: [sondar_vs_revelar]   # dimensões que ESTE caso exercita
```

**Categorias adversariais (v1):** `sincretismo` (Kybalion, Lei da Atração),
`silencio` (off-topic → confessa silêncio), `existencial` (funda ou conduz),
`lingua_ausente` (leigo descreve algo que uma fundante nomeia → Nomeação),
`multi_turno` (Avanço), `devolucao` (baixa Disposição → sonda), `so_tecnico`
(declara o gênero). A fundação atual (Kybalion, existencial, Lei da Atração) migra
para dado.

### 2. Portão estrutural — `evals/avaliacao/estrutural.py`

Função pura, determinística, **sem rede**: recebe `RevelacaoFinal` + `CorpusStore` +
`espera_estrutural`; resolve cada `citacao_id` na `Passagem` e checa:

- a citação **existe** no corpus;
- **proveniência** correta — fundante citada é primária/fundante, **nunca**
  iluminante (erudição) nem excluída;
- `foi_limite` coerente com o esperado;
- as asserções declarativas do caso (`nao_funda_prefixo`, etc.).

Devolve lista de violações (vazia = passou). Roda **sempre** (grátis), inclusive sem
credencial.

> Se algum check precisar de um campo que o `RevelacaoFinal` hoje não expõe (ex.:
> par frase↔citação, `genero_declarado`, `devolveu` no resultado final), **surfacing
> desse campo é melhoria em escopo** — pequena, alinhada ao que a suíte precisa
> observar. A maior parte sai de `citacoes` + lookup no store.

### 3. Juiz semântico de sustentação — `evals/avaliacao/sustentacao.py`

Avaliador **LLM** (reusa `LLMBackend`, saída estruturada via schema). Recebe: a fala,
a Revelação (`texto` + afirmações), e os **textos** das fundantes citadas (resolvidos
do store). Devolve, por afirmação: **sustenta?** (a fundante de fato diz aquilo —
gate semântico, passa/falha) e **anacronismo?** (a prosa importa termo/ideia fora do
horizonte do corpus). Violação aqui = **falha-dura** (parte do portão).

### 4. Meta-juiz de Condução — `evals/avaliacao/conducao.py`

Avaliador **LLM** que recebe a fala (ou roteiro), a Revelação (ou as Revelações do
diálogo), as fundantes citadas, a **rubrica das 4 dimensões** e o `foco_de_conducao`
do caso; devolve **nota por dimensão** (escala pequena, ex.: 0–3) + justificativa.
Saída estruturada via schema. A nota é **registrada** (tendência), com **limiar
opcional** por dimensão que, se ligado, vira asserção branda.

> O meta-juiz e o juiz semântico são `LLMBackend` — então rodam com Claude econômico
> (default de afinação), Opus (validação final), **ou o novo `LocalLLM` (Gemma 4)**
> de graça. Modelo do juiz é injetável; default econômico.

### 5. Harness — `evals/test_suite.py`

`pytest.mark.parametrize` sobre os casos carregados de `evals/casos/`. Para cada caso:

1. monta o oráculo (fábrica + corpus real + `FakeEmbeddings`), conduz `consultar()`
   por 1 turno (ou N, se `roteiro`) com o mesmo buscador;
2. roda o **portão estrutural** (sempre) → violação = `assert` falha;
3. roda o **juiz semântico** e o **meta-juiz** (sob o marcador `eval`, atrás de
   credencial) → sustentação viola = falha; notas de Condução = registradas
   (impressas/coletadas; limiar opcional como `assert` brando).

O `conftest.py` atual (skip por credencial, marcador `eval`) é reusado tal qual.

## Testes da própria suíte (TDD)

- **Portão estrutural**: testado **sem rede** com `RevelacaoFinal` sintético + store
  real (ou fake) — cobre cada regra (citação inexistente, iluminante-como-fundante,
  prefixo proibido, limite).
- **Construção de prompt/schema** do juiz semântico e do meta-juiz: testada com
  `FakeLLM` (wiring + parsing da nota), sem rede.
- **Carregador de casos**: testa que YAML malformado erra alto e que multi-turno
  vira N chamadas.
- **Casos e2e** (fala real → LLM real): sob o marcador `eval`, pulam sem credencial,
  como hoje.

## Fora de escopo (YAGNI)

- Dashboard/tendência persistida (a nota é impressa/coletada; persistência depois).
- Framework externo (promptfoo/deepeval/braintrust) — amarra a alma do projeto a
  terceiros; rejeitado no brainstorming (Abordagem C).
- Tuning de pesos entre dimensões / nota agregada única — v1 reporta por dimensão.
- Geração automática de casos adversariais — o corpus de casos cresce à mão.

## Riscos e mitigações

- **Juiz não-determinístico** — rubrica ancorada nas leis + saída estruturada +
  asserções tolerantes; fidelidade é binária (sustenta/não), Condução é graduada e
  só-reportada por padrão (não trava o build em ruído).
- **Custo dos juízes** — default econômico (Sonnet) na afinação; Opus só na
  validação final; ou `LocalLLM` (Gemma 4) de graça. Estrutural é $0 e roda sempre.
- **Campo faltando no traço** — surfacing pontual em escopo (ver §2).
- **Acoplar à fundação atual** — os 3 casos existentes migram para `evals/casos/` e
  `test_fidelidade.py` é absorvido/aposentado pelo harness dirigido por dado.
```
