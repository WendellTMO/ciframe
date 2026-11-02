# Plano — Sequências de Acordes Customizadas

## Passos

1. [x] Colocar `data/db/` no `.gitignore` e no `.dockerignore`. Isso vem primeiro porque, a partir do passo 4, todo import do `main.py` cria o arquivo do banco.

2. [x] Criar o `sequencias_db.py`. Cada função abre e fecha a própria conexão.
   - A lista `SEQUENCIAS_INICIAIS` guarda as 6 sequências atuais já normalizadas, na ordem de `scripts/generate_data_set.py:8`. A posição de cada uma (de 0 a 5) é o número que a coluna `SEQ_FAMOSA` usa para ela. O `id` do banco não entra nessa comparação.
   - A função `normaliza_acorde` deixa a primeira letra maiúscula e mantém o resto.
   - A função `init_db` cria a pasta e a tabela `sequencias(id, acordes)` se ainda não existirem. A coluna `acordes` guarda os acordes normalizados separados por `;` e não pode se repetir. As 6 sequências entram com `ON CONFLICT DO NOTHING`, para não duplicar a cada reinício.
   - A função `listar` devolve as sequências ordenadas por `id`.
   - As funções `buscar` e `criar` normalizam os acordes antes de procurar ou gravar. O `criar` recusa lista vazia.

3. [x] Escrever a `casa_com_sequencia(cifra, acordes)` no `main.py`. Ela compara acorde por acorde, em duas etapas:
   - Primeiro confere se todos os acordes da música pertencem à sequência e para no primeiro de fora. Essa parada deixa a busca em cerca de 55 ms. Normalizando a cifra inteira antes, a busca leva cerca de 290 ms.
   - Depois procura a sequência na cifra, em ordem e com os acordes seguidos.

   No mesmo passo, criar o `scripts/regressao_sequencias.py` a partir do `research/seq_famosa_rule.py`. O script da pesquisa continua em `research/` como evidência da fase de pesquisa, com a regra antiga de comparar texto. O script compara a função com a coluna `SEQ_FAMOSA` e precisa dar 199, 296, 4, 5, 7 e 3 músicas, com 0 diferenças, antes de seguir. Esses números saem iguais com qualquer uma das normalizações e formas de comparar testadas na pesquisa. Por isso o script também confere `bm`/`Bm`, `C7M`/`C7m`, `Gm`/`GM` e que `Am;A` não casa com `oasis_the-swamp-song`. O teste roda no Docker:

   ```
   docker build -t ciframe . && docker run --rm ciframe python scripts/regressao_sequencias.py
   ```

4. [x] Ligar o `/similares` ao banco. O dicionário de `main.py:40-45` sai e o `init_db` roda no import, depois da carga do CSV. O handler procura a sequência com `buscar` e responde `[]` se ela não existir. O `get_similares_por_sequencia` passa a receber a lista de acordes e a usar a `casa_com_sequencia`. O teste de regressão ganha duas checagens. A primeira junta todas as páginas do `/similares` das 6 sequências. A segunda roda o `init_db` duas vezes e confere que nada duplica.

5. [x] Criar `GET /sequencias` e `POST /sequencias`, sempre com `json.dumps`, inclusive nos erros. Regras do `POST`:
   - O corpo precisa ser um objeto JSON com `acordes` como lista de textos. Fora disso, 400.
   - Cada acorde perde os espaços das pontas e os vazios saem. Se não sobrar nenhum, 400.
   - Acorde com `;` ou `,` responde 400, porque quebraria a separação no banco e na URL.
   - Sequência nova responde 201 com `id` e acordes normalizados. Sequência repetida responde 409 com o `id` da existente.

6. [x] Mudar a página `#/porsequencia`:
   - A lista passa a vir de `GET /sequencias`. Cada sequência é convertida para `{id, acordes: [{acorde, cor}]}`, o formato que o template já usa.
   - Um botão "Nova sequência" abre um modal com a sequência em construção no topo e a paleta de acordes embaixo. Cada clique acrescenta um acorde. A lixeira, que aparece ao passar o mouse, remove qualquer acorde do topo.
   - A paleta sai do `acordes.js` para a constante `ACORDES` no `app.js`, usada pelas duas páginas. A `#/poracordes` continua igual.
   - "Salvar" faz o `POST`. O 201 acrescenta a sequência à lista e fecha o modal. O 409 seleciona a existente e avisa. O 400 mostra o erro no modal, que continua aberto.
   - A busca monta a URL com `params` do `$http`. Sem isso, o `#` de `F#m` corta a URL e o `+` de `A7+` chega como espaço. Nos dados, 31.701 músicas têm acorde com `#` e 6.142 têm acorde com `+`.

7. [x] Trocar o comando de execução no `AGENTS.md` por `docker run -p 8080:8080 -v ciframe-seq:/app/data/db ciframe`.

8. [x] Testar no navegador com o container e o volume: montar `A E F#m D` pelo modal, buscar, recriar o container e conferir que ela continua na lista. Conferir pela API que `D7+,G7+` é aceita, já que o modal só oferece a paleta.

9. [x] Aplicar as correções da revisão de código:
   - O clique repetido no mesmo acorde tirava o último da sequência. Agora o clique só acrescenta.
   - O `F` e o `F#` sumiam no fundo rosa do modal. A paleta do modal passou a usar hexágonos brancos.
   - Os casos do `POST` (400, 409, `GM`/`Gm` e `D7+,G7+`) entram no teste de regressão.

10. [x] Aplicar as correções da segunda revisão, feita com o BigPickle:
   - A `casa_com_sequencia` passa a normalizar também os acordes da sequência.
   - O teste de `GM`/`Gm` exige 409 para `Gm F` e 201 para `GM F`.
   - O script passa a testar os 159 de `A E F#m D` e o `POST` de `C7M G` e `C7m G`.

## Mudanças durante a implementação

- O primeiro plano tinha um campo de texto para digitar os acordes. Depois do teste da página, o campo foi trocado pelo modal com a paleta, para o visitante não precisar saber escrever os acordes.
- A exclusão de sequências chegou a entrar no plano, com as 6 originais protegidas pelos acordes. Ela saiu antes de ser implementada porque a cota do BigPickle acabou (ver `02-proposal.md`).
- Os passos 9 e 10 entraram depois das duas revisões de código.

## Arquivos afetados

| Arquivo | Mudança |
|---|---|
| `main.py` | Sai o dicionário das 6 sequências. Entram a `casa_com_sequencia`, o `GET /sequencias` e o `POST /sequencias`. O `/similares` passa a buscar no banco |
| (novo) `sequencias_db.py` | Tabela, 6 sequências iniciais, normalização e acesso ao banco |
| (novo) `scripts/regressao_sequencias.py` | Teste de regressão das 6 sequências e das regras do `POST` |
| `static/assets/js/controllers/sequencia.js` | Lista vinda da API, modal de montagem e busca com a URL codificada |
| `static/templates/sequencia.html` | Botão "Nova sequência", modal e mensagens de erro e aviso |
| `static/assets/js/app.js` | Constante `ACORDES` com a lista e a paleta |
| `static/assets/js/controllers/acordes.js` | Passa a usar a constante `ACORDES` |
| `static/assets/css/app.css` | Estilos do modal e da lixeira |
| `.gitignore`, `.dockerignore` | Passam a ignorar `data/db/` |
| `AGENTS.md` | Comando com volume |
| `musica.py`, `Dockerfile`, `requirements.txt` | Sem mudança. O `sqlite3` já vem com o Python |

## Riscos e mitigação

| Risco | Como perceber | O que fazer |
|---|---|---|
| A regra nova muda os resultados das 6 sequências | O teste de regressão mostra diferença | Parar e corrigir a função antes de ligar no `/similares` |
| O teste compara a sequência errada | As contagens saem trocadas entre as 6 | Comparar pela posição na lista (0 a 5), nunca pelo `id` |
| O teste passa com uma normalização errada | O script não acusa nada | Conferir os pares `bm`/`Bm`, `C7M`/`C7m` e `Gm`/`GM` |
| Comparar como texto gera falso positivo | `Am;A` casa com uma música que só tem Am | Comparar acorde por acorde e testar esse caso |
| A busca fica lenta | O `/similares` passa de 100 ms | Parar no primeiro acorde da música que não está na sequência |
| O `#` e o `+` quebram a URL da busca | `F#m` volta vazia pela página e funciona no `curl` com `%23` | Montar a URL com `params` do `$http` |
| A extração da paleta quebra a `#/poracordes` | Faltam acordes ou as cores saem trocadas | Mover a lista inteira sem alterar os valores e conferir a página |
| O segundo start duplica as 6 sequências | O `listar` passa de 6 depois de dois `init_db` | Tabela com `IF NOT EXISTS` e inserção com `ON CONFLICT DO NOTHING` |
| O volume montado no lugar errado esconde o CSV | O `/generos` não responde | Montar só em `/app/data/db` |
| O modal só oferece a paleta | Não dá para montar `D7+` clicando | Aceito. A paleta só tem maior, menor e sétima. O `+` é testado pela API |
| Um acorde enviado pela API como `c7m` vira `C7m` (dó menor com sétima) | A sequência não acha as músicas esperadas | Aceito. Só a primeira letra é normalizada |
| Um acorde enviado pela API como `d/f#` vira `D/f#` | Não casa com `D/F#` | Aceito. Nos dados, a letra minúscula depois da barra é extensão em 817 casos e baixo em só 35 |
| Alguém grava HTML como acorde pela API | Um `POST` com `<img src=x onerror=alert(1)>` responde 201 | Aceito. A página só envia acordes da paleta e o Angular escapa o texto |

## Definição de pronto

- [x] As 6 sequências originais dão 199, 296, 4, 5, 7 e 3 músicas, com 0 diferenças em relação à coluna `SEQ_FAMOSA`, na função e no `/similares`.
- [x] O `GET /sequencias` devolve as 6 sequências no primeiro uso, ordenadas por `id`.
- [x] O `POST /sequencias` responde 201 para sequência nova, 400 para corpo inválido ou lista vazia e 409 com o `id` da existente para sequência repetida, inclusive `c,g,am,f`.
- [x] As sequências `GM;F` e `Gm;F` são aceitas como diferentes. O mesmo vale para `C7M` e `C7m`.
- [x] A sequência `Am;A` não casa com música que só tem Am.
- [x] A busca por `bm,g,d,a` encontra as mesmas músicas que `Bm,G,D,A`. Antes ela retornava `[]`.
- [x] Montar `A E F#m D` pelo modal cria a sequência, que encontra 159 músicas. A página mostra as 100 primeiras.
- [x] A sequência `D7+,G7+`, criada pela API, encontra 3 músicas.
- [x] Uma sequência cadastrada continua na lista depois de recriar o container com o volume.
- [x] Todos os endpoints continuam respondendo com `json.dumps`.
