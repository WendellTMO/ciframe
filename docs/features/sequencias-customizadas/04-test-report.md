# Relatório de testes — Sequências de Acordes Customizadas

## Cobertura

O teste automatizado é o `scripts/regressao_sequencias.py`. Ele roda dentro do Docker, carrega o `main.py` e confere:

- A normalização: `bm` vira `Bm` e `am` vira `Am`. `C7M` e `C7m` continuam diferentes, assim como `Gm` e `GM`.
- A comparação acorde por acorde: `Am;A` não casa com `oasis_the-swamp-song`, que só tem Am.
- O reinício com o banco já criado: rodar o `init_db` duas vezes mantém as 6 sequências, sem duplicar.
- O teste de regressão das 6 sequências, descrito na próxima seção.
- A busca em minúsculo: `bm,g,d,a` encontra as mesmas 199 músicas que `Bm,G,D,A`, tanto na função quanto no `/similares`.
- As regras do `POST /sequencias`: 400 para corpo que não é JSON, `acordes` que não é lista, corpo sem `acordes`, lista vazia, lista só com espaço e acorde com `;`. Também 409 para `C G Am F`, que já existe. `GM F` é aceita com 201 e fica gravada separada de `Gm F`. `C7M G` e `C7m G` são aceitas como sequências diferentes. `A E F#m D` é criada e encontra 159 músicas. `D7+ G7+` é criada e encontra 3.

Antes de entrarem no script, as regras do `POST /sequencias` foram conferidas à mão pelo `test_client` do Flask dentro do Docker:

| Entrada | Resposta |
|---|---|
| `{"acordes": []}` | 400, "informe pelo menos um acorde" |
| `nao e json` (corpo que não é JSON) | 400, "o corpo precisa ser um objeto JSON" |
| `["C"]` (lista no lugar do objeto) | 400, "o corpo precisa ser um objeto JSON" |
| `{"acordes": ["C,G"]}` | 400, "acorde nao pode conter ; ou ," |
| `{"acordes": ["a", "e", "f#m", "d"]}` | 201, gravada como `A E F#m D` |
| `{"acordes": ["c", "g", "am", "f"]}` | 409 com `id` 2, que é `C G Am F` |
| `GM F`, `C7M G` e `C7m G` | 201 para as três, porque são acordes diferentes de `Gm` e `C7m` |
| `{"acordes": ["D7+", "G7+"]}` | 201 |

Depois do cadastro, a busca por `A,E,F#m,D` encontrou 159 músicas, somando as páginas. A primeira página tem 100, como as outras buscas. A busca por `a,e,f#m,d` encontrou as mesmas 159 e a busca por `D7+,G7+` encontrou 3. O `GET /sequencias` num banco novo devolveu as 6 sequências com `id` de 1 a 6.

A página `#/porsequencia` foi testada no navegador com o container rodando com volume (passo 8 do plano). O teste foi gravado em vídeo. O vídeo mostra a lista com as 6 sequências, a busca por `C G Am F`, o aviso de sequência repetida ao montar `C G Am F` no modal, o cadastro de `Em F#m G7` (que não encontra músicas) e o cadastro e a busca de `A E F#m D`.

Depois do vídeo, o container foi parado, removido e criado de novo com o mesmo volume. O `GET /sequencias` voltou com as 6 originais e com `Em F#m G7` e `A E F#m D`, com os ids 7 e 8.

## Teste de regressão obrigatório

Para cada uma das 6 sequências, o script compara três conjuntos de músicas nas 67.585 do CSV:

1. As músicas marcadas com aquela sequência na coluna `SEQ_FAMOSA`, que era o que o código antigo usava.
2. As músicas que a `casa_com_sequencia` aceita.
3. As músicas que o `/similares` devolve, juntando todas as páginas. Esse caminho passa pelo banco.

A sequência é ligada à coluna pela posição na lista `SEQUENCIAS_INICIAIS` (de 0 a 5). O `id` do banco não entra nessa comparação.

Resultado:

| Sequência | Coluna | Função | `/similares` | Diferenças |
|---|---|---|---|---|
| Bm G D A | 199 | 199 | 199 | 0 |
| C G Am F | 296 | 296 | 296 | 0 |
| Em G | 4 | 4 | 4 | 0 |
| C A7 Dm G7 | 5 | 5 | 5 | 0 |
| Gm F | 7 | 7 | 7 | 0 |
| C C7 F Fm | 3 | 3 | 3 | 0 |

As diferenças comparam as músicas uma a uma, então os conjuntos são iguais e não só as contagens.

## Como rodar

```
docker build -t ciframe . && docker run --rm ciframe python scripts/regressao_sequencias.py
```

## O que ficou de fora

- O script grava sequências no banco. Ele roda no container com `--rm` e sem volume, então começa sempre com o banco vazio. Rodado fora do Docker, ele grava em `data/db/` e o caso `D7+ G7+` passa a dar 409 na segunda vez.
- O frontend não tem teste automatizado. O projeto não tem nenhuma ferramenta de teste para JavaScript. A página foi testada no navegador.
- O teste não roda com o volume montado. A persistência entre containers foi conferida só no teste manual do passo 8.
- O tempo da busca (cerca de 55 ms) foi medido à mão na fase de pesquisa e não é conferido pelo script.
- Acordes com `+`, `7M` e `sus` não estão na paleta do modal. O caso `D7+,G7+` foi testado só pela API.
- Um `POST` com HTML no lugar do acorde responde 201. Isso foi conferido à mão e ficou como risco aceito no plano, sem teste no script.
- Os hexágonos da paleta no modal ficaram todos brancos, com o texto rosa. Foi a correção para o `F` e o `F#`, que sumiam no fundo rosa. As cores da paleta continuam na sequência em construção, no topo do modal, onde o `F` ainda fica pouco visível.

## Revisão de código

A cota gratuita do BigPickle acabou antes da revisão. Na sessão principal, o Gemma 4 e o Gemini 3.5 Flash-Lite pararam no limite de tokens por minuto, porque cada pedido manda o histórico inteiro da sessão. A revisão rodou numa sessão separada, só com o diff do código (`git show HEAD -- main.py sequencias_db.py static scripts`). Uma primeira tentativa dessa sessão separada incluiu os documentos no diff e também estourou o limite.

A primeira resposta da revisão trouxe só elogios e uma sugestão de validar espaços internos nos acordes, que não foi seguida porque a página só envia acordes da paleta. Apontei os problemas vistos no teste do navegador e o agente corrigiu:

- O clique repetido no mesmo acorde tirava o último acorde, o que impedia montar `C C G`. Agora o clique só acrescenta e a remoção fica com a lixeira.
- O `F` e o `F#` sumiam na paleta do modal.
- As regras do `POST` entraram no script de regressão.

A regressão rodou de novo depois das correções, com 0 diferenças.

No dia seguinte a cota do BigPickle voltou e uma segunda revisão rodou na sessão principal, sobre todo o diff desde o último commit antes da feature. Ela achou problemas que a primeira não pegou. Foram corrigidos:

- A `casa_com_sequencia` normalizava só os acordes da música. Chamada direto com `bm,g,d,a`, ela devolvia 0 músicas. Pelo `/similares` funcionava porque o banco já guarda os acordes normalizados. Agora ela normaliza os dois lados e o script testa a chamada direta.
- O teste de `GM`/`Gm` aceitava 201 ou 409 e nunca falhava. Agora ele exige 409 para `Gm F` e 201 para `GM F`.
- O `AGENTS.md` ainda dizia que o projeto não tem banco.
- O relatório dizia que `GM F` respondia 409. O certo é 201.

Os smells apontados (duplicação da regra entre `main.py` e `research/seq_famosa_rule.py`, nomes e montagem repetida de `{id, acordes}`) não foram corrigidos, porque não mudam o comportamento. O script da pesquisa continua em `research/` como evidência, com a regra antiga de comparar texto.

## Sugestões para os comandos do RePPIT

- O `make-plan.md` manda abrir `@templates/design_doc_template.md`, que não existe no repositório do framework.
- O `implement.md` tem o caminho fixo `/path/to/plan_md` e não usa `$ARGUMENTS`. O plano precisa ser indicado à mão na mensagem.
- Não existe comando para a fase de testes. O `review-code` revisa o diff, mas não gera nem documenta testes. Um comando que preenchesse o relatório de testes a partir do plano e da definição de pronto fecharia as 5 fases.
- O `review-code` lê o `git diff` inteiro dentro da mesma sessão. Numa sessão longa, isso estoura o limite dos planos gratuitos. Rodar a revisão numa sessão nova, só com o diff e o plano, evitaria esse problema.
