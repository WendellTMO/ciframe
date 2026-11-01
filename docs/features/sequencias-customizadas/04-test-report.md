# Relatório de testes — Sequências de Acordes Customizadas

## Cobertura

O teste automatizado é o `scripts/regressao_sequencias.py`. Ele roda dentro do Docker, carrega o `main.py` e confere:

- A normalização: `bm` vira `Bm` e `am` vira `Am`. `C7M` e `C7m` continuam diferentes, assim como `Gm` e `GM`.
- A comparação acorde por acorde: `Am;A` não casa com `oasis_the-swamp-song`, que só tem Am.
- O reinício com o banco já criado: rodar o `init_db` duas vezes mantém as 6 sequências, sem duplicar.
- O teste de regressão das 6 sequências, descrito na próxima seção.
- A busca em minúsculo: `bm,g,d,a` encontra as mesmas 199 músicas que `Bm,G,D,A`.

As regras do `POST /sequencias` foram conferidas pelo `test_client` do Flask dentro do Docker, sem script no repositório:

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

- As regras do `POST /sequencias` não estão no script. Elas foram conferidas uma vez, à mão, como mostra a tabela acima.
- O frontend não tem teste automatizado. O projeto não tem nenhuma ferramenta de teste para JavaScript. A página foi testada no navegador.
- O teste não roda com o volume montado. A persistência entre containers foi conferida só no teste manual do passo 8.
- O tempo da busca (cerca de 55 ms) foi medido à mão na fase de pesquisa e não é conferido pelo script.
- Acordes com `+`, `7M` e `sus` não estão na paleta do modal. O caso `D7+,G7+` foi testado só pela API.
- Um `POST` com HTML no lugar do acorde responde 201. Isso foi conferido à mão e ficou como risco aceito no plano, sem teste no script.
- O `/review-code` do RePPIT não chegou a rodar. A cota gratuita do BigPickle acabou antes dessa fase. Na mesma sessão, tentei o Gemma 4 e o Gemini 3.5 Flash-Lite pela chave gratuita do Google. Os dois pararam no limite de tokens por minuto, porque cada pedido manda o histórico inteiro da sessão. As tentativas estão no log.
- No teste do navegador apareceram dois detalhes visuais que não foram corrigidos. Os hexágonos `F` e `F#` quase somem no modal, porque a cor deles na paleta (`#ba007c`) é quase igual ao fundo. Isso já acontecia na `#/poracordes`. O aviso de sequência repetida aparece numa caixa roxa que vai até o fim da tela.

## Sugestões para os comandos do RePPIT

- O `make-plan.md` manda abrir `@templates/design_doc_template.md`, que não existe no repositório do framework.
- O `implement.md` tem o caminho fixo `/path/to/plan_md` e não usa `$ARGUMENTS`. O plano precisa ser indicado à mão na mensagem.
- Não existe comando para a fase de testes. O `review-code` revisa o diff, mas não gera nem documenta testes. Um comando que preenchesse o relatório de testes a partir do plano e da definição de pronto fecharia as 5 fases.
- O `review-code` lê o `git diff` inteiro dentro da mesma sessão. Numa sessão longa, isso estoura o limite dos planos gratuitos. Rodar a revisão numa sessão nova, só com o diff e o plano, evitaria esse problema.
