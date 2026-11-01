# O que a página `#/porsequencia` faz hoje

Snapshot: commit `fb97001`, verificado em 2026-10-30 contra o app rodando localmente
(`python main.py`, porta 5000). Arquivos centrais: `static/templates/sequencia.html`,
`static/assets/js/controllers/sequencia.js`, `static/assets/js/routes.js` e `main.py`.

## Summary

A rota `#/porsequencia` (`static/assets/js/routes.js:17-21`) carrega
`static/templates/sequencia.html` com o `SequenciaController` exposto como `Sequencia`. As quatro
sequências exibidas **não vêm de nenhuma API nem do CSV**: são objetos hardcoded no controller
(`sequencia.js:2-37`), cada um com `acordes` (lista de `{acorde, cor}`) e um campo `index` que nunca é
lido. Clicar em um bloco chama `pesquisarPorSequencia` (`sequencia.js:63-90`), que monta a string
`Bm,G,D,A` e faz `GET /similares?sequencia=Bm,G,D,A` (relativo, mesma origem; opcionalmente
`&generos=...`). No backend, `main.py:170-201` remove as vírgulas, resolve o id no dicionário
`main.py:40-45`, filtra as músicas por `seqs_famosas` (`main.py:209`) e devolve até 100 itens
(`main.py:35`, `main.py:226-228`). A resposta vira cards ordenados por popularidade
(`sequencia.html:42-56`), e clicar em um card abre a cifra no Cifra Club (`sequencia.js:97-99`). As
4 (e não 6) são um hardcode de fevereiro de 2016 (`ddceb74`) que já convivia com uma linha
comentada listando as 6; o endpoint do backend só ganhou as 6 em maio de 2016 (`3b4d191`) e nenhum
commit posterior acrescentou `EmG` ou `CA7DmG7` ao frontend.

---

## 1. Como a página é montada

| Peça | Referência |
|---|---|
| Rota `#/porsequencia` → template + controller (`controllerAs: "Sequencia"`) | `static/assets/js/routes.js:17-21` |
| Template | `static/templates/sequencia.html:1-63` |
| Controller | `static/assets/js/controllers/sequencia.js:1-105` |
| Script incluído no HTML | `static/index.html:145` |
| Link de entrada na home | `static/templates/home.html:79-84` ("Conheces alguma dessas sequências de acordes?") |
| Diretiva que desenha o hexágono do acorde | `static/assets/js/directives/df-hex.js:1-12` + `static/templates/directives/df-hex.html:1-9` |

O template tem dois painéis: à esquerda a lista de sequências (`sequencia.html:6-8`) e à direita a
área de resultados (`:17-59`). Antes de qualquer clique, `minhaSequencia = {}`
(`sequencia.js:38`), então o bloco da direita fica oculto (`ng-show="Sequencia.minhaSequencia.acordes.length"`,
`sequencia.html:19`): **a página não faz nenhuma requisição ao carregar**.

## 2. De onde vêm as sequências mostradas

São quatro variáveis locais no controller, empilhadas em `vm.sequenciasFamosas`
(`sequencia.js:33-37`):

| Variável | Acordes (`sequencia.js`) | Id no backend (`main.py:40-45`) | Músicas com a tag |
|---|---|---|---|
| `sequencia1` | Bm, G, D, A (`:3-9`) | 0 (`BmGDA`) | 199 |
| `sequencia2` | C, G, Am, F (`:10-17`) | 1 (`CGAmF`) | 296 |
| `sequencia3` | Gm, F (`:18-23`) | 4 (`GmF`) | 7 |
| `sequencia4` | C, C7, F, Fm (`:24-31`) | 5 (`CC7FFm`) | 3 |

- Não há `$http` no carregamento: os quatro objetos são criados em memória.
- Cada acorde carrega a cor fixa `#2E1C74` (`sequencia.js:5-30`).
- O campo `'index': 1` existe nos quatro objetos (`sequencia.js:3,11,19,25`) e **não é lido em
  lugar nenhum** (o único `indexOf` do arquivo é o de `temAcorde`, `sequencia.js:49`).
- A ordem exibida é a ordem dos `push` (`sequencia.js:34-37`), que corresponde aos ids 0, 1, 4, 5.
- A lista de gêneros do `<select>` também é hardcoded: `GENEROS` em `static/assets/js/app.js:6-58`
  (51 itens), não vem de `GET /generos` (que devolve 52, incluindo `R&B;`, `main.py:159-160`).

## 3. O que acontece quando o usuário clica

O `ng-click` está no contêiner de cada sequência (`sequencia.html:6`), então clicar em qualquer
hexágono dentro dele também dispara, por borbulhamento. O fluxo é:

1. `pesquisarPorSequencia(sequencia)` (`sequencia.js:63-90`) grava a sequência escolhida em
   `vm.minhaSequencia` (`:64-66`).
2. Liga a barra de progresso (`:67`), troca o texto para "Procurando músicas com base na sequencia..." (`:68`),
   marca `isSearching = true` (`:69`) e limpa `vm.musics` (`:70`).
3. `createChordsString` (`:55-61`) concatena os acordes com vírgula e remove a última:
   `Bm,G,D,A`.
4. Monta `"similares?sequencia=" + acordes` (`:73`) e, se um gênero estiver escolhido, acrescenta
   `&generos=<gênero>` (`:74-76`). O `apiUrl` é `""` (`:72`), ou seja, a URL é **relativa** — a
   requisição vai para a mesma origem que serviu o SPA.
5. `$http.get(...)` (`:77`); no sucesso (`:78-84`) completa a barra, troca o texto para "Encontrei
   essas músicas", marca `showSearchResultsCount = true` e faz `vm.musics = data`; no erro (`:85-89`)
   mostra "Ops! Algo errado.".
6. Com `minhaSequencia` preenchida, o painel direito passa a mostrar o título, o `<select>` de gênero
   (`sequencia.html:19-38`) e os hexágonos da sequência escolhida (`:34`); clicar em um deles chama
   `limparPesquisa()` (`sequencia.js:92-95`), que zera `minhaSequencia` e `musics`.
7. Trocar o gênero no `<select>` dispara `ng-change="Sequencia.pesquisarPorSequencia()"`
   (`sequencia.html:28`) sem argumento — a função reaproveita `vm.minhaSequencia` (`sequencia.js:64-66`)
   e refaz a busca com `&generos=`.

`temAcorde` (`sequencia.js:47-53`) decide se o hexágono fica branco: compara por **identidade de
objeto** dentro de `minhaSequencia.acordes` (`indexOf`), então só os hexágonos da sequência
selecionada aparecem "checados" (`df-hex.html:4,8`).

## 4. A requisição que chega no backend

Exemplo real disparado pelo clique em `sequencia2`:

```
GET /similares?sequencia=C,G,Am,F
GET /similares?sequencia=C,G,Am,F&generos=Rock     (se um gênero estiver escolhido)
```

No backend (`main.py:170-201`):

| Passo | Referência |
|---|---|
| Lê `sequencia`, `generos`, `pagina` (default `'1'`) | `main.py:173-179` |
| `acordes = sequencia_tag.replace(',', '')` → `CGAmF` | `main.py:191` |
| Resolve o id no dicionário `sequencias` | `main.py:194-195` |
| Filtra por gênero (`apply_filtro`, `main.py:266-272`) e por `str(id_seq) in musica.seqs_famosas` | `main.py:203-209` |
| Pagina com `get_pagina` (100 por página) | `main.py:196`, `main.py:226-228` |
| Devolve `json.dumps(...)` (string, `Content-Type: text/html`) | `main.py:197` |

Se a string não existir no dicionário, `similares` continua `[]` e a resposta é `[]` com status 200
(`main.py:192-197`) — o frontend trata como sucesso e mostra a lista vazia.

Respostas medidas contra o app local:

| URL | Itens retornados |
|---|---|
| `/similares?sequencia=Bm,G,D,A` | 100 (de 199 músicas com a tag 0) |
| `/similares?sequencia=Bm,G,D,A&generos=Rock` | 5 |
| `/similares?sequencia=Em,G` | 4 |
| `/similares?sequencia=C,A7,Dm,G7` | 5 |
| `/similares?sequencia=bm,g,d,a` | 0 (a chave do dicionário é case-sensitive) |

Cada item tem as chaves `id_unico_musica`, `id_artista`, `id_musica`, `nome_artista`,
`nome_musica`, `popularidade`, `acordes`, `genero`, `url` (`main.py:210-220`). O caminho por
sequência **não** inclui `diferenca` nem `intersecao` (essas chaves só existem no caminho por
acordes, `main.py:235-260`).

## 5. Como os resultados aparecem

- `ng-repeat="music in Sequencia.musics | orderBy:'-popularidade'"` (`sequencia.html:42`)
  renderiza um card por música; a ordenação é feita no cliente sobre os até 100 itens recebidos.
- `ng-hide="music.diferenca.length"` (`sequencia.html:43`): como a resposta por sequência não tem
  `diferenca`, a expressão Angular resulta `undefined` (sem erro) e o card **sempre aparece**.
- Cada card (`sequencia.html:45-56`) mostra título (`:51`), artista (`:52`) e gênero como label
  (`:53`), com um ícone de cadeado aberto (`:48`).
- Clique no card → `goToLirics(music)` → `$window.open(music.url)` (`sequencia.js:97-99`), abrindo a
  cifra no Cifra Club em nova aba (`musica.py:22`).
- Após o sucesso, o botão "Encontrei essas músicas" (`sequencia.html:10-14`) aparece e, ao ser
  clicado, rola a página até `#results` (`sequencia.js:101-104`).
- Não há paginação: o frontend nunca envia `pagina`, então só a primeira página (100 itens) é
  exibida, mesmo quando a tag tem mais músicas (caso de `BmGDA`, 199, e `CGAmF`, 296).
- Os cards são os mesmos para os quatro botões; o que muda é a URL e, portanto, o id consultado.

## 6. Por que 4 se o backend tem 6

Linha do tempo (datas dos commits):

| Commit | Data | O que aconteceu |
|---|---|---|
| `acfefb0` | 2015-12-12 | Script que encontra sequências famosas no dataset; a lista de 6 nasce aí |
| `ddceb74` | 2016-02-23 | "Add sequence search behavior": cria `frontend/assets/js/controllers/sequencia.js` com **4** objetos e uma linha comentada listando as **6** |
| `3b4d191` | 2016-05-17 | "procurando por sequências e filtrando por gêneros": backend (`back-end/api.py`) ganha o dicionário com as **6** |
| `92c1976` | 2016-10-05 | Frontend move de `frontend/` para `static/` e o controller é reescrito; os **4** continuam, o comentário com as 6 é removido |
| `88dcaa6` | 2016-10-05 | Só troca `apiUrl` de `ciframe.herokuapp.com` para `ciframe-api.herokuapp.com` |
| `249bdc9` | 2026-10-15 | Só troca `apiUrl` para `""` (mesma origem) |

Evidências:

- No commit de criação (`ddceb74`), a primeira linha do controller era
  `// var sequenciasFamosas = ['Bm - G - D - A', "C - G - Am - F", "Em - G", "C - A7 - Dm - G7", "Gm - F", "C - C7 - F - Fm"];`
  — as 6 estavam ali, mas comentadas; abaixo só 4 viraram objetos (`sequencia1`..`sequencia4`).
- Nesse mesmo commit o backend (`back-end/api.py`) não tinha o dicionário de sequências; a rota
  `por_sequencia()` existente fazia `sequencia_famosa in x[SEQ_FAMOSA]` (substring da coluna 7,
  `back-end/api.py:110-112` naquele commit), e o controller ainda não chamava API nenhuma
  (`$http.get("")` com resultado comentado).
- `git log -S"EmG" -- static/` não retorna nenhum commit: nenhuma versão do frontend em `static/`
  teve `EmG` (id 2) nem `C A7 Dm G7` (id 3). Também não existe `sequencia5`/`sequencia6` em nenhum
  commit (`git log -S"sequencia5" --all` vazio).
- Os dois que faltam são justamente os de menor volume no CSV: id 2 = 4 músicas e id 3 = 5 músicas
  (`research/seq-famosa-rule.md`); os quatro exibidos têm 199, 296, 7 e 3.

Ou seja: a lista de 4 é um hardcode de fevereiro de 2016, anterior ao endpoint de sequências do
backend (maio de 2016), e a reescrita de outubro de 2016 a preservou. O histórico não registra
justificativa para a escolha dos 4; o que existe é a linha comentada com as 6, indicando que a lista
completa era conhecida na época.

## 7. Detalhes do código que afetam o comportamento

| Detalhe | Referência | Efeito |
|---|---|---|
| `apiUrl = ""` | `sequencia.js:72` | requisição relativa à origem; funciona em `:5000` e no container `:8080` |
| `RESTAPI` (`http://localhost:5003`) | `app.js:3-5` | constante definida e não usada em nenhum lugar (`grep -rn RESTAPI static/` só acha a definição) |
| `$anchorScroll`, `$location` injetados | `sequencia.js:1` | não são usados no controller |
| `isSearching` | `sequencia.js:39,69,81,87` | não aparece no template desta página |
| `limparPesquisa` não zera `showSearchResultsCount` | `sequencia.js:92-95` | o botão "Encontrei essas músicas" continua visível depois de limpar |
| `meuGenero` é string, não objeto | `sequencia.html:26-27` | o filtro envia `&generos=<nome>` direto (`sequencia.js:75`) |
| `orderBy:'-popularidade'` no cliente | `sequencia.html:42` | reordena apenas os 100 itens recebidos |
| `ng-hide="music.diferenca.length"` | `sequencia.html:43` | sempre falso neste caminho; cards nunca são escondidos |

## 8. Como reproduzir

```
python main.py        # ou: docker run -p 8080:8080 ciframe

curl -s "http://localhost:5000/similares?sequencia=Bm,G,D,A" | python3 -c \
  "import json,sys; d=json.load(sys.stdin); print(len(d), sorted(d[0].keys()))"
# 100 ['acordes','genero','id_artista','id_musica','id_unico_musica','nome_artista','nome_musica','popularidade','url']

curl -s "http://localhost:5000/similares?sequencia=Bm,G,D,A&generos=Rock" | python3 -c \
  "import json,sys; print(len(json.load(sys.stdin)))"
# 5
```

No navegador: abrir `#/porsequencia`, clicar em um dos quatro blocos e observar a requisição
`/similares?sequencia=...` na aba Network.

## 9. Artefatos

| Arquivo | Conteúdo |
|---|---|
| `research/porsequencia-page.md` | Este documento |
| `static/templates/sequencia.html` | Template da página (63 linhas) |
| `static/assets/js/controllers/sequencia.js` | Controller com as 4 sequências hardcoded (105 linhas) |
| `static/assets/js/routes.js` | Rota `#/porsequencia` (linhas 17-21) |
| `main.py` | Endpoint `/similares` e filtro por `seqs_famosas` (linhas 170-228) |
