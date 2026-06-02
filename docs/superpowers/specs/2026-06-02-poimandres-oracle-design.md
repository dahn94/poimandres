# Poimandres — Especificação de Design

**Data:** 2026-06-02
**Método de modelagem:** Domain Storytelling (ver log em `docs/sessions/2026-06-02-domain-storytelling-log.md`)
**Status:** desenho aprovado; pronto para o plano de implementação.

---

## 1. Propósito

Poimandres é um oráculo de software que conduz um **Buscador** segundo a tradição hermética
clássica (Corpus Hermeticum, Asclépio, fragmentos de Estobeu, Definições Herméticas), respondendo
*precisamente* — isto é, fundando-se apenas em fontes primárias curadas, citando-as, e recusando-se
a contaminar a doutrina com camadas posteriores ou invenção.

**Percepção central de engenharia:** um LLM já carrega, do seu treino, abundante pseudo-Hermética
(Kybalion, Golden Dawn, Teosofia, Nova Era). O software inteiro existe para **impedir o modelo de
falar dessa memória poluída** e forçá-lo a fundar-se só nas primárias curadas. A fidelidade não é
pedida ao modelo — é **construída e verificada em volta dele**.

## 2. Escopo

**Neste software:** apenas o **Buscador** (do leigo ao praticante, num contínuo) e o **Curador**.
A forma é *sempre* a **Condução iniciática** — o oráculo conduz como Hermes conduz Tat.

**Fora de escopo (software futuro separado):** o "Erudito em pesquisa" (postura de Serviço,
Levantamento exaustivo, Aparato crítico). Os dois softwares partilharão um **núcleo comum** — o
Corpus, a hierarquia de Proveniência, as virtudes dos limites — mas isso não é construído agora.

**Primeira versão:** pequeno círculo de buscadores convidados (multiusuário simples, sem serviço
público aberto). Stack Python. Corpus em arquivos Markdown versionados em git.

## 3. Modelo de domínio (linguagem ubíqua)

| Termo | Significado |
|---|---|
| **Buscador** | quem traz um desejo-de-saber; do leigo ao praticante |
| **Curador** | guarda do corpus; atribui proveniência, marca tensões |
| **Mestre** | o oráculo na função de Hermes — conduz, não despeja |
| **Registro** | lugar no espectro existencial↔doutrinal (sempre sob Condução) |
| **Disposição** | estado interior, 4 marcas: reconhecimento-de-si · pureza · reta-intenção (eusébeia) · capacidade-de-receber |
| **Grau** | profundidade de revelação que a Disposição autoriza; **emergente, re-sondado a cada turno** |
| **Estado-do-grau** | *aberto* (revelado) ≠ *integrado* (vivido) |
| **Movimento** | o que o Mestre pede do buscador e o que lê nele |
| **Trilho da língua** | Imagem → Nomeação → Glosa (entra pelo mito, dá o termo, guarda do anacronismo) |
| **Proveniência** | camada de autoridade: *primária ▸ funda · técnica · testemunho · erudição ▸ ilumina · excluído ▸ quarentena* |
| **Passagem** | trecho endereçável (ref. canônica) que herda a proveniência |
| **Tensão** | contradição interna preservada, nunca aplainada |
| **Revelação** | a entrega, no grau cabível, fundada em primárias e iluminada por erudição, sempre citada |
| **Memória-do-caminho** | registro do que foi aberto *e vivido*; informa o presente, não o determina |

### As leis do domínio (invariantes)

1. **FORMA** — sempre Condução iniciática (sondar · devolver · conduzir por graus · poder adiar).
2. **DOIS TRILHOS** desacoplados — interior (4 marcas → profundidade) ⟂ língua (forma de entrega).
   Léxico é andaime, nunca critério: ignorância de termos ≠ despreparo da alma.
3. **PRESENTE** — grau re-sondado a cada consulta; a Memória informa, não gateia.
4. **AUTORIDADE** — só primárias FUNDAM; erudição só ILUMINA; excluído → quarentena.
5. **LIMITES (4 virtudes)** — confessa silêncio · expõe divisão · devolve · distingue gêneros.
6. **POLIFONIA** — nunca aplaina as tensões do corpus.
7. **HUMILDADE** — o Mestre lê só o que se manifesta no diálogo; não é onisciente.

### As 4 infidelidades a evitar (espelhadas pelas virtudes)
sincretismo · alucinação · anacronismo · confusão de gêneros.

## 4. Arquitetura: o pipeline de um turno (Abordagem "Recuperar → Restringir → Verificar")

Cada turno do diálogo atravessa **cinco unidades isoladas e testáveis**. Cada lei vira engrenagem.

```
 fala do Buscador + Memória-do-caminho
        │
        ▼
 ① DISCERNIDOR  [LLM, saída estruturada]
     • Registro (lugar no espectro)
     • Disposição: 4 marcas, cada uma estimada COM incerteza (humildade)
     • Grau cabível agora (re-sondado no presente)
     • vocabulário ausente? → aciona trilho da língua
     • é retorno? → marca Verificação de integração do grau anterior
        │
        ▼
 ② RECUPERADOR  [busca semântica + filtro de proveniência]
     • FUNDANTES (só primárias)  • ILUMINANTES (erudição, à parte)
     • excluídas → nunca entram (índice de quarentena só p/ reconhecer e recusar)
     • detecta TENSÕES (primárias conflitantes → devolve os dois lados marcados)
     • nenhuma primária funda? → sinaliza SILÊNCIO / só-técnico
        │
        ▼
 ③ COMPOSITOR (voz do Mestre)  [LLM]
     • compõe a Revelação no grau cabível, na postura de Condução
     • CONTRATO DURO: toda afirmação doutrinal cita uma passagem FUNDANTE;
       erudição só ilumina (marcada como tal)
     • aplica o trilho da língua: Imagem → Nomeação → Glosa
     • pode DEVOLVER (pergunta/Movimento) em vez de revelar
        │
        ▼
 ④ VERIFICADOR (as 4 virtudes viram checagens)  [regras + LLM-juiz]
     ✓ alucinação?   toda afirmação rastreia a citação real e a passagem a sustenta?
     ✓ sincretismo?  zero conteúdo de fonte excluída ou doutrina não-citada
     ✓ anacronismo?  termo técnico veio acompanhado de glosa?
     ✓ gêneros?      se só há suporte técnico, foi declarado?
     ✓ limites?      sem fundante → confessou silêncio / expôs divisão / distinguiu gênero?
     REPROVA → devolve a ③ para refazer (com a violação anotada),
               ou rebaixa à resposta honesta do limite
        │
        ▼
 ⑤ MEMÓRIA  registra grau aberto, passagens citadas, e (no retorno) o estado de
     integração lido. É REGISTRO, não trava: alimenta ① no próximo turno como
     um sinal entre outros.
```

### Contratos das unidades (interfaces)

- **Discernidor** — `entrada: (fala, memória) → saída: Discernimento{registro, marcas{4 floats+incerteza},
  grau_cabível, língua_ausente: bool, é_retorno: bool}`. Auditável (logado).
- **Recuperador** — `entrada: (tema/grau, fala) → saída: {fundantes: [Passagem], iluminantes: [Passagem],
  tensões: [Tensão], silêncio: bool, só_técnico: bool}`. Filtro de proveniência é DURO (por construção).
- **Compositor** — `entrada: (Discernimento, recuperação, memória) → saída: RascunhoRevelação{texto,
  afirmações: [{frase, citação_id}], movimentos: [...]}`.
- **Verificador** — `entrada: (RascunhoRevelação, recuperação) → saída: {aprovado: bool, violações: [...]}`.
  Determinístico onde possível (ids de citação existem no recuperado; strings de fonte excluída ausentes);
  LLM-juiz para entailment (a passagem sustenta a frase?) e anacronismo/gênero.
- **Memória** — `entrada: (buscador_id, turno, RevelaçãoFinal) → efeito: persiste turno + atualiza graus`.

## 5. Dados e curadoria

### Árvore do corpus (Markdown versionado)
```
corpus/
├── primarias/     proveniencia: primaria  → PODE FUNDAR
├── erudicao/      proveniencia: erudicao  → SÓ ILUMINA
├── excluidas/     proveniencia: excluido  → QUARENTENA (reconhecer/recusar)
├── tensoes/       pares de passagens em tensão (+ tipo + nota)
└── glossario/     termo → glosa + passagens de origem (semente do grafo futuro)
```

### Esquema do frontmatter de um texto
```yaml
---
obra: "Corpus Hermeticum"
tratado: "I (Poimandres)"
proveniencia: primaria        # primaria | tecnica | testemunho | erudicao | excluido
autor_ou_tradutor: "Copenhaver 1992"
idioma: "pt"
ref_base: "CH I"              # prefixo da referência canônica
---
§14  E a Natureza, vendo a beleza...
§15  Por isso o homem é duplo: mortal pelo corpo, imortal pelo Homem essencial...
```

### Fluxo de ingestão (`poimandres ingest`)
```
arquivo .md → [parser frontmatter+corpo] → segmenta em PASSAGENS por marca (§/título)
   cada Passagem: herda proveniência, recebe ref canônica ("CH I §15")
   → [embeddings LOCAIS: BGE-M3] → [vector store LanceDB]
        coleção FUNDANTE (primárias) · ILUMINANTE (erudição) · QUARENTENA (excluídas)
tensoes/*.md → registros Tensão (par de refs + tipo + nota)
glossario/*.md → registros Glossário (termo + glosa + passagens de origem)
```

### Estado (SQLite)
```
buscador(id, nome, chave_de_convite)
turno(buscador_id, quando, fala, revelacao, citacoes[])
grau(buscador_id, tema, estado: aberto|integrado, passagens[], quando)
```
A tabela `grau` é REGISTRO, não trava: alimenta o Discernidor como um sinal entre outros.

## 6. Stack

**Filosofia de deploy (decidida 2026-06-02): híbrido — embeddings e busca locais na VPS
(grátis, soberanos); LLM via Claude API.** Os backends de LLM e de embeddings são **plugáveis**
(interfaces únicas), de modo que migrar o LLM para um modelo local (Ollama/vLLM) no futuro é só
configuração, sem reescrever o pipeline.

```
Python 3.12
├─ LLM (backend PLUGÁVEL; padrão = Claude API, SDK anthropic) + PROMPT CACHING
│    • Compositor (voz do Mestre) ...... Claude Opus 4.8   (fidelidade/qualidade)
│    • Discernidor + Verificador-juiz ... Claude Sonnet 4.6 (rápido, estruturado)
│    • interface LLMBackend → troca para modelo local sem tocar nas unidades
├─ Embeddings (backend PLUGÁVEL; padrão = LOCAL): BGE-M3 ou multilingual-e5-large
│    via sentence-transformers — roda na VPS (CPU ok), multilíngue (PT + grego/traduções)
├─ Vector store: LanceDB (embarcado, em disco, sem servidor) — local
├─ Estado: SQLite — local
├─ Curadoria: CLI 'poimandres ingest' sobre a pasta corpus/
└─ Interface do círculo: FastAPI + chat web mínimo; chave-de-convite por buscador
```

**Nota de soberania/custo:** vector store, embeddings e estado são 100% locais e gratuitos. Só as
chamadas de LLM saem da VPS (Claude API) — o que implica custo por token e que o texto da consulta
trafega para a API. A interface LLMBackend preserva a opção de fechar essa porta depois (modelo local).

## 7. Tratamento de erros e limites (as virtudes como comportamento)

- **Silêncio** — Recuperador sem passagem fundante ⇒ o Mestre confessa que o corpus não trata o tema;
  jamais inventa. Verificador barra qualquer afirmação doutrinal sem citação.
- **Divisão** — Recuperador detecta tensão ⇒ Compositor expõe os lados, sem decidir; Verificador
  reprova se um lado foi suprimido (aplainamento).
- **Devolução** — Compositor pode, à maneira do Mestre, devolver a questão/propor um Movimento.
- **Gêneros** — se só há suporte técnico (astrologia/magia), o Mestre o declara em vez de tratá-lo
  como autoridade doutrinal.
- **Reconhecimento do excluído** — se o buscador cita pseudo-Hermética, o índice de quarentena permite
  reconhecê-la e recusá-la explicitamente ("isto não pertence à Hermética clássica").
- **Falha de verificação** — Verificador reprova ⇒ retry do Compositor com a violação anotada;
  após até 2 retentativas, rebaixa à resposta honesta do limite (nunca entrega resposta infiel).

## 8. Estratégia de testes (TDD; o especialista é o oráculo dos testes)

**Casos-ouro de fidelidade** (expectativas escritas pelo Curador-especialista):
- "O que o Kybalion ensina sobre X?" → RECONHECE e RECUSA (excluída).
- Pergunta sem suporte no corpus → CONFESSA SILÊNCIO.
- Pergunta sobre tema com tensão conhecida → EXPÕE A DIVISÃO (não aplaina).
- Qualquer afirmação doutrinal → carrega citação primária válida e sustentada.
- Pergunta de leigo sem vocabulário → usa Imagem → Nomeação → Glosa.
- Iscas sincréticas ("Hermetismo não é a Lei da Atração?") → CORRIGE/RECUSA.

**Testes de unidade por estágio:**
- Discernidor — saída estruturada bem-formada; estima incerteza.
- Recuperador — filtro de proveniência DURO (excluídas nunca entram); detecção de tensão.
- Compositor — toda afirmação sai com citação_id.
- Verificador — DETERMINÍSTICO onde possível (ids existem no recuperado; strings excluídas ausentes);
  juiz de entailment para "a passagem sustenta a frase?".

**Red-team set** — prompts que tentam induzir sincretismo, anacronismo, invenção.

## 9. Fora de escopo / futuro
- Software do Erudito (postura de Serviço, Levantamento, Aparato) — separado, partilha o núcleo do corpus.
- **Grafo de doutrina** (Abordagem 3) — enriquecimento opcional que o Curador faz crescer com o tempo,
  a partir da semente do glossário e das tensões. Nunca pré-requisito.
- Serviço público aberto, autenticação robusta, escala multirregião.
