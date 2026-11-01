# Proposta — Sequências de Acordes Customizadas

## Abordagem escolhida

O catálogo de sequências vai para um banco SQLite e o match passa a ser calculado na hora da busca, a partir da cifra de cada música. Todas as sequências usam a mesma regra, tanto as 6 antigas quanto as novas. Músicas e gêneros continuam vindo do CSV, como hoje.

### Algoritmo de matching

A regra é a mesma do `get_famosas` (`scripts/generate_data_set.py:7-24`), que gerou a coluna `SEQ_FAMOSA`, com duas diferenças: a normalização e a comparação acorde por acorde. Uma música casa com uma sequência quando as duas condições valem juntas:

1. Os acordes da sequência aparecem na cifra da música em ordem e um logo depois do outro.
2. Todos os acordes da música pertencem à sequência.

Antes da comparação, a primeira letra de cada acorde vira maiúscula e o resto fica como está. Assim `c` e `C` são o mesmo acorde. `C7M` e `C7m` continuam diferentes, assim como `Gm` e `GM`. O `get_famosas` passava tudo para minúsculo e juntava esses pares, que são acordes diferentes.

A comparação usa `musica.cifra` e é feita acorde por acorde. O campo `musica.acordes` não serve porque é um set e perde a ordem. O `get_famosas` procurava o texto da sequência dentro do texto da cifra. Desse jeito, `Am;A` casaria com uma música que só tem Am, porque o texto `Am;A` aparece dentro de `Am;Am`.

Exemplos para a sequência C G Am F:

- C C G Am F casa.
- G C G Am F casa.
- C G Am F Dm não casa, porque Dm não está na sequência.
- F Am G C não casa, porque a ordem é outra.

Com essas duas mudanças, a regra deu 0 diferenças em relação à coluna `SEQ_FAMOSA` nas 67.585 músicas (199, 296, 4, 5, 7 e 3 músicas para as 6 sequências), os mesmos números da regra antiga. O dicionário de `main.py:40-45` sai do código e as 6 sequências passam a ser dados no banco.

Cada busca percorre todas as músicas. Para ficar rápida, a comparação confere primeiro se os acordes da música estão na sequência e para no primeiro que não está. Nos testes locais, a busca levou cerca de 55 ms.

### Banco de dados

SQLite, pelo módulo `sqlite3` que já vem com o Python. Não entra dependência nova e o Dockerfile não muda.

O arquivo fica em `data/db/sequencias.sqlite`. A pasta é separada porque um volume montado em `data/` esconderia o CSV.

Sem volume, o banco se perde quando o container é recriado. Por isso o comando de execução no `AGENTS.md` passa a ser:

```
docker run -p 8080:8080 -v ciframe-seq:/app/data/db ciframe
```

A pasta `data/db/` entra no `.dockerignore` e no `.gitignore`. Sem isso, o `COPY . .` levaria um banco local para a imagem.

### Esquema de dados (alto nível)

Uma tabela `sequencias`:

| Campo | Exemplo | Para que serve |
|---|---|---|
| `id` | `2` | Identifica a sequência na API |
| `acordes` | `C;G;Am;F` | Acordes já normalizados e separados por `;`. Não se repetem no banco e servem para a busca, para barrar duplicadas e para a tela |

Na primeira execução, a tabela recebe as 6 sequências atuais. Como os acordes são gravados normalizados, cadastrar `a,e,f#m,d` mostra `A E F#m D` na lista.

### API

Todos os endpoints continuam respondendo com `json.dumps`.

| Endpoint | Entrada | Saída |
|---|---|---|
| `GET /sequencias` | Nada | Lista com `id` e `acordes` de cada sequência |
| `POST /sequencias` | `{"acordes": ["C", "G", "Dm"]}` | `201` com a sequência criada |
| `POST /sequencias` com lista vazia | `{"acordes": []}` | `400` com mensagem de erro |
| `POST /sequencias` com sequência que já existe | `{"acordes": ["C", "G", "Am", "F"]}` | `409` com o `id` da que já existe |
| `GET /similares?sequencia=C,G,Am,F` | Igual a hoje | Mesmo formato de hoje, buscando a sequência no banco |

Sequência que não está no catálogo continua retornando `[]`. Como a busca normaliza a primeira letra de cada acorde, `bm,g,d,a` passa a encontrar músicas. Hoje essa busca retorna `[]`. Pelo mesmo motivo, `Gm;F` e `GM;F` podem ser cadastradas como sequências diferentes.

### Frontend

As mudanças ficam na própria página `#/porsequencia`.

- As 4 sequências escritas no `sequencia.js` saem e a lista passa a vir de `GET /sequencias`. Com isso a página mostra as 6.
- Abaixo da lista entra um botão "Nova sequência". Ele abre um card no meio da tela com os acordes da paleta. A sequência é montada clicando neles. A sequência nova aparece na lista na hora.
- A busca passa a codificar os acordes na URL. Hoje o `#` de `F#m` corta a URL e o navegador manda só `sequencia=F`. O `+` de `A7+` chega no servidor como espaço.
- A exibição dos resultados não muda.

## Alternativas consideradas e descartadas

A outra proposta usava LMDB, mantinha as 6 sequências lendo a coluna `SEQ_FAMOSA` e aplicava uma regra mais solta às sequências novas, com o cadastro numa página separada. Ela foi descartada por três motivos:

1. Com duas regras, a mesma sequência daria 199 ou 382 músicas, dependendo de ter sido semeada ou cadastrada.
2. O enunciado pede o cadastro na página `#/porsequencia`.
3. O LMDB adiciona uma dependência sem nenhuma vantagem sobre o SQLite.

## Escopo explícito

**Dentro do escopo:**

- Tabela de sequências no SQLite, com as 6 atuais.
- Match calculado na busca, com a regra acima.
- Os endpoints `GET /sequencias` e `POST /sequencias`. O `/similares` passa a buscar no banco.
- Página `#/porsequencia` lendo o catálogo da API e permitindo cadastro.
- Volume no `docker run` para os dados não se perderem.
- Teste de regressão das 6 sequências: 199, 296, 4, 5, 7 e 3 músicas, com 0 diferenças.

**Fora do escopo (e por quê):**

- Acelerar a busca guardando a cifra já normalizada: a busca já leva cerca de 55 ms.
- Validar os acordes contra a lista de `/acordes`: só lista vazia é recusada. Um acorde desconhecido apenas não encontra músicas.
- Rate limit e moderação: o catálogo é aberto por requisito. Controle de abuso não foi pedido.
- Editar e excluir sequências: não foi pedido. A exclusão chegou a entrar no plano depois do teste da página, com as 6 originais protegidas pelos acordes. Ela saiu antes de ser implementada porque a cota do BigPickle acabou e o prazo não permitia esperar.
- Paginação na página: o limite de 100 resultados já existe hoje e é outra mudança.
- Data de criação e variável de ambiente para o caminho do banco: nada precisa disso agora.
- Mexer na coluna `SEQ_FAMOSA` do CSV: ela continua no arquivo, mas o código para de ler.
