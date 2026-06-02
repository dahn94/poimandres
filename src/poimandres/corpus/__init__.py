"""Subsistema do *corpus* — a coleção de textos herméticos do Poimandres.

Distinção dos três termos próximos, porém diferentes:

* **corpus (a coleção)** — todos os textos curados, tomados em conjunto. Em
  *dados*, vivem na pasta ``corpus/`` na raiz do projeto (arquivos Markdown
  versionados em git): ``corpus/primarias/``, ``corpus/erudicao/``,
  ``corpus/excluidas/`` etc. Em *código*, este pacote (``poimandres.corpus``)
  é quem lê, segmenta, vetoriza e consulta esses textos.
* **"Corpus Hermeticum"** — uma OBRA específica dentro do corpus (um valor do
  campo ``obra`` no frontmatter); não confundir com a coleção inteira.
* **corpo (de um arquivo)** — o texto de UM arquivo Markdown abaixo do
  frontmatter (ver ``parser.parse_texto``); é o que ``segmentar`` quebra em
  passagens.

Cada texto da pasta ``corpus/`` carrega uma *proveniência* (ver
``poimandres.domain.Proveniencia``) que define sua autoridade: só as fontes
primárias podem FUNDAR uma resposta; a erudição apenas ILUMINA; o excluído fica
em quarentena (só para reconhecer e recusar).
"""
