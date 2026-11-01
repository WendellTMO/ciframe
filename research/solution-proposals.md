# Propostas de solução — Sequências de acordes customizadas

Snapshot: commit `fb97001`, escrito em 2026-10-30. Nenhuma das duas propostas foi escolhida; este
documento só organiza o espaço de solução a partir da pesquisa em `research/`.

## Context

- **Request:** permitir que qualquer visitante cadastre uma sequência de acordes e busque músicas por
  ela, com o catálogo de sequências persistido em banco, mantendo iguais os resultados das 6
  sequências atuais (`docs/features/sequencias-customizadas/00-enunciado.md:45-55`).
- **Research Source:**
  - `docs/features/sequencias-customizadas/01-research.md:33-65` — as quatro descobertas (regra,
    validação, banco, frontend) e os trade-offs já registrados.
  - `research/seq-famosa-rule.md:8-18, 36-58, 119-164` — a regra da coluna `SEQ_FAMOSA`
    (contiguidade + vocabulário fechado, só `.lower()`), os números por sequência e as variantes
    medidas.
  - `research/embedded-db-options.md:9-62, 66-136, 138-246, 250-305` — o container único, o ciclo de
    vida dos dados, as opções de banco e o delta exato de `Dockerfile`/`requirements.txt`.
  - `research/porsequencia-page.md:24-63, 152-198` — o que a página faz hoje, a requisição que ela
    dispara e por que aparecem 4 de 6.
  - `research/codebase-as-is.md:89-104, 128-165, 327-370` — endpoints, semântica de `/similares`,
    fluxos e deploy.
- **Restrições fixas:** músicas/gêneros continuam no CSV em memória (`main.py:47-98`); só o catálogo
  de sequências vai para o banco; `Dockerfile` único, local-only, sem serviço externo
  (`docs/adr/0001-local-only-docker-deploy.md:9-16`); as 6 mantêm os mesmos resultados
  (199/296/4/5/7/3 músicas, `research/seq-famosa-rule.md:125-131`); respostas continuam
  `json.dumps`, não `jsonify` (`00-enunciado.md:68`).
- **Lacunas da pesquisa (valem para as duas propostas):** não há medição do custo de matching em
  runtime (medido durante esta síntese, ver Proposta 1), nem de recuperação de crash do LMDB, nem
  teste sob escrita concorrente com carga. O repositório não tem suíte de testes
  (`research/codebase-as-is.md:12`), e nada na pesquisa decide política de abuso/moderação para um
  `POST` anônimo.

---

## Proposal 1 — SQLite (stdlib) + uma única regra contígua calculada na consulta

- **Overview:** o dicionário hardcoded de `main.py:40-45` é substituído por uma tabela SQLite
  (`sqlite3`, já presente na imagem) semeada com as 6 sequências; toda busca por sequência passa a
  rodar a regra validada em `research/seq-famosa-rule.md:47-58` sobre `musica.cifra`, em vez de ler a
  coluna `SEQ_FAMOSA`. É a proposta mais alinhada: zero dependência nova, zero mudança de
  `Dockerfile`, uma só semântica para as 6 e para as novas, e a igualdade dos resultados já foi
  medida (0 diferenças em 67.585 músicas).

- **Key Changes:**
  - **Novo módulo `sequencias_store.py`** (ou ~60 linhas em `main.py`): `init_db()` com
    `CREATE TABLE IF NOT EXISTS`, seed idempotente e funções `listar()`, `criar(acordes)`,
    `buscar_por_chave(chave)`.
  - **Esquema:** `sequencias(id INTEGER PRIMARY KEY AUTOINCREMENT, chave TEXT NOT NULL UNIQUE,
    acordes TEXT NOT NULL, criado_em TEXT NOT NULL DEFAULT (datetime('now')))`, onde `chave` é
    `';'.join(t.lower() for t in acordes)` — a mesma tokenização da regra, então a chave de dedupe é
    exatamente a chave de matching — e `acordes` guarda a grafia de exibição (`Bm;G;D;A`).
  - **Seed:** as 6 listas ordenadas de `scripts/generate_data_set.py:8` (é a única fonte com os
    acordes separados; as chaves de `main.py:40-45` não são divisíveis — `BmGDA` não diz onde corta).
    `INSERT ... ON CONFLICT(chave) DO NOTHING`, na ordem dos ids 0–5.
  - **Matching:** nova função em `main.py` com a regra de `research/seq-famosa-rule.md:47-58`,
    consumindo `musica.cifra` (a lista ordenada) e não `musica.acordes` (`musica.py:17`, que é
    `set`, sem ordem). `get_similares_por_sequencia` (`main.py:203-223`) deixa de testar
    `str(id_seq) in musica.seqs_famosas` (`main.py:209`) e passa a varrer
    `apply_filtro(musicas.values(), generos_key)` (`main.py:266-272`) com essa função; o resto do
    payload (`main.py:210-221`) e o `get_pagina` (`main.py:226-228`) não mudam.
  - **Resolução da consulta:** `/similares?sequencia=C,G,Am,F` continua recebendo a mesma string
    (`main.py:191`), mas em vez de `acordes in sequencias` (`main.py:194`) normaliza para `chave` e
    consulta o banco; desconhecida continua devolvendo `[]` (`main.py:192-197`).
  - **API nova:** `GET /sequencias` → `json.dumps` de `[{id, acordes: [...], criado_em}]`;
    `POST /sequencias` com corpo JSON `{"acordes": ["Bm","G","D","A"]}` → `201` com o objeto criado,
    `400` para lista vazia/acorde vazio, `409` para chave já existente (devolvendo o `id`). Sem
    `jsonify`: `return json.dumps(obj), 201` mantém o `Content-Type` atual.
  - **Inicialização:** `init_db()` depois da carga do CSV (`main.py:47-98`), no import; caminho em
    `SEQUENCIAS_DB`, default `data/db/sequencias.sqlite`. Subdiretório próprio, porque montar volume
    em `/app/data` esconderia `data/top/dataset_final.csv` e quebraria `main.py:49`.
  - **Frontend:** apagar os quatro objetos de `sequencia.js:2-37`; no controller, `$http.get
    ('sequencias')` e mapear `{acordes: ["Bm", ...]}` para `{acordes: [{acorde, cor:'#2E1C74'}]}`,
    que é o contrato de `df-hex` (`sequencia.html:7`). `pesquisarPorSequencia` (`sequencia.js:63-90`)
    e `createChordsString` (`:55-61`) ficam como estão. Em `sequencia.html`, adicionar um formulário
    no painel esquerdo (input de acordes separados por vírgula + botão) que faz `$http.post` e
    recarrega a lista; o `ng-repeat` de `sequencia.html:6-8` passa a mostrar as 6 + as novas sem
    outra mudança.
  - **Deploy:** `Dockerfile` e `requirements.txt` intactos; `.dockerignore` ganha `data/db/` e
    `*.sqlite*` (senão `COPY . .` assa o banco local, `research/embedded-db-options.md:111-113`);
    `AGENTS.md:24` passa a documentar `docker run -p 8080:8080 -v ciframe-seq:/app/data/db ciframe`.

- **Trade-offs:**
  - **A favor:** nenhuma dependência nova (0 MB, `research/embedded-db-options.md:148-158`);
    `Dockerfile` de 12 linhas intocado; uma regra só, já validada com 0 divergências; SQL resolve
    listagem e dedupe sem código; SQLite aceita múltiplos processos (medido,
    `research/embedded-db-options.md:154-155`) — não trava um futuro `gunicorn -w > 1`.
  - **Contra:** cada busca varre 67.585 músicas. Medido em `python:3.9-slim`: **~185 ms por
    sequência** com a regra literal (`';'.join` por música a cada consulta) e **~10–27 ms** por
    sequência se `Musica` guardar a cifra já minúscula e unida por `;` (custo único de 189 ms e
    ~14 MB no import). Sem esse campo, o custo cresce linearmente com o catálogo (N sequências ×
    185 ms por requisição); com ele, o teto prático é ~10 ms × N.
  - **Contra:** a busca passa a depender do banco estar legível em toda requisição (hoje depende só
    de um `dict`); banco ausente/corrompido deve falhar no import, não por request.
  - **Contra:** `?sequencia=bm,g,d,a` passa a funcionar (hoje devolve `[]`,
    `research/porsequencia-page.md:120`), porque a chave normaliza para minúsculas. É uma mudança de
    comportamento observável, ainda que desejável.
  - **Contra:** o volume é obrigatório para a promessa de "não volta a ser perdido" — sem `-v`, o
    catálogo morre em `docker rm` (`research/embedded-db-options.md:79-84`), e `VOLUME` no
    `Dockerfile` não resolve (volume anônimo novo por container, `research/embedded-db-options.md:114-117`).

- **Validation:**
  1. **Regressão obrigatória:** rodar `python research/seq_famosa_rule.py` (baseline, 0 diferenças)
     e um script novo no estilo do repo (sem framework, já que não há suíte) que compara, para cada
     sequência semeada, o conjunto completo retornado pelo matcher novo com
     `str(id) in musica.seqs_famosas`: espera 199/296/4/5/7/3 e xor 0. Comparar conjuntos completos,
     não HTTP, porque `/similares` corta em 100 (`main.py:226-228`).
  2. **API:** `GET /sequencias` devolve 6; `POST` de `["C","G","Am","F"]` devolve 409; `POST` de
     `["C","G","Dm"]` devolve 201 e aparece no `GET`; `POST` vazio devolve 400;
     `GET /similares?sequencia=C,G,Dm` devolve as músicas esperadas; `curl -i` confirma
     `Content-Type: text/html` em todas.
  3. **Persistência:** `run` → cadastrar → `restart` (mantém) → `rm` + `run` sem volume (perde, como
     documentado) → `rm` + `run -v ciframe-seq:/app/data/db` (mantém). Espelha
     `research/embedded_db_probe.sh lifecycle`.
  4. **Custo:** medir o endpoint com o corpus real; alvo < 100 ms por requisição com a cifra
     pré-normalizada.
  5. **Frontend:** abrir `#/porsequencia`, conferir 6 blocos vindos da API, clicar em um, conferir a
     requisição `/similares?sequencia=...` e a lista; cadastrar uma sequência e recarregar a página.

- **Open Questions:**
  - Duplicata: rejeitar com 409 ou devolver a existente com 200? Normalizar caixa/espaços muda o que
    conta como duplicata — confirmar.
  - Validar acorde contra `GET /acordes` (6.653 tokens, `research/codebase-as-is.md:98`)? O que fazer
    com `C/G`, `C#`, acorde inexistente?
  - Limites: máximo de acordes por sequência, máximo de sequências, rate limit — o catálogo é
    anônimo e sem moderação (`00-enunciado.md:47-48`).
  - As 6 passam a ser dados: como corrigi-las/removê-las depois, se o seed só roda em tabela vazia?
  - Paginação: manter o corte de 100 (o frontend nunca envia `pagina`,
    `research/porsequencia-page.md:139-141`) ou corrigir nesta feature?
  - `SEQ_FAMOSA` deixa de ser lida pelo app: manter a coluna no CSV (fixo, `:60-62`) e no pipeline,
    ou só ignorá-la?

---

## Proposal 2 — LMDB + catálogo aditivo: as 6 continuam na tag, as novas usam subsequência com lacunas

- **Overview:** o catálogo vai para um LMDB (`lmdb`, 2 MB, chave-valor, multi-processo) e o caminho
  das 6 sequências **não muda**: elas são semeadas com `regra='tag'` e continuam sendo resolvidas por
  `str(id) in musica.seqs_famosas`, o que torna a regressão exata por construção. Sequências novas
  usam uma regra mais permissiva já medida na pesquisa — ordem preservada com lacunas + vocabulário
  fechado (`research/seq-famosa-rule.md:145-158`) —, que devolve mais músicas (382/518/4/6/7/3 para
  as 6, contra 199/296/4/5/7/3). DuckDB foi descartado por 52 MB e lock exclusivo por processo
  (`research/embedded-db-options.md:160-171`), que quebraria com mais de um worker.

- **Key Changes:**
  - **`requirements.txt`:** `+lmdb==3.0.0` (2 MB instalados, wheel `cp39` linux/arm64,
    `research/embedded-db-options.md:173-182`); `Dockerfile` continua intocado.
  - **`sequencias_store.py` com LMDB:** `lmdb.open('data/seqdb', map_size=10*1024*1024)` e três
    sub-bancos — `sequencias` (id zero-padded → JSON do registro), `chaves` (chave → id, dedupe) e
    `meta` (`next_id`, já que LMDB não tem autoincremento). Registro:
    `{id, acordes: [...], regra: "tag"|"subsequencia", tag_id: 0-5|null, criado_em}`.
  - **Seed:** as 6 de `scripts/generate_data_set.py:8` com `regra='tag'` e `tag_id` posicional 0–5,
    inseridas só se `meta/next_id` não existir.
  - **`/similares` (`main.py:190-197`):** normaliza `sequencia` para `chave`, resolve no LMDB e
    ramifica: `regra='tag'` → `get_similares_por_sequencia` como hoje (`main.py:203-223`, sem tocar
    em `:209`); `regra='subsequencia'` → varredura com a regra de subsequência
    (`research/seq-famosa-rule.py:60-91`); desconhecida → `[]`.
  - **API:** `GET /sequencias` inclui `regra`; `POST /sequencias` grava sempre
    `regra='subsequencia'`; `400`/`409` iguais à Proposta 1.
  - **Frontend:** `#/porsequencia` passa a listar o catálogo da API, mas o formulário fica em uma
    rota nova `#/nova-sequencia` (`static/assets/js/routes.js:1-29`), reaproveitando o seletor de
    acordes de `acordes.js`/`acordes.html`; a página atual ganha um botão para essa rota. Mantém o
    controller antigo quase intacto, ao custo de separar cadastro de busca (opção levantada em
    `01-research.md:65`).
  - **Deploy:** volume em diretório, `-v ciframe-seq:/app/data/seqdb` (LMDB grava `data.mdb` +
    `lock.mdb`); `.dockerignore` ganha `data/seqdb/`; nunca montar `/app/data` (esconderia o CSV).

- **Trade-offs:**
  - **A favor:** risco de regressão zero para as 6 — o código que as atende é o mesmo de hoje; a
    regra nova é mais generosa com o usuário e já tem números medidos para comparação; LMDB é leve
    (2 MB), não exige compilador e aceita múltiplos processos (medido,
    `research/embedded-db-options.md:179-181`).
  - **A favor:** a busca das 6 continua O(n) sem custo de tokenização (só um `in` na tag), então não
    precisa do campo pré-normalizado da Proposta 1.
  - **Contra:** duas semânticas no mesmo endpoint — a mesma sequência de acordes pode dar 199 ou 382
    resultados dependendo de ter sido semeada ou cadastrada; isso é difícil de explicar e de testar,
    e quebra a ideia de um catálogo único.
  - **Contra:** as 6 continuam acopladas a `SEQ_FAMOSA` e ao alinhamento posicional dos ids com
    `generate_data_set.py:8`; qualquer regeração do CSV pode mudar resultados sem tocar no código.
  - **Contra:** LMDB não tem consulta: listar é varrer cursor, dedupe é um segundo índice manual, o
    id é um contador manual e `map_size` é fixado na abertura (`research/embedded-db-options.md:182`);
    crescer o banco exige reabrir com outro tamanho.
  - **Contra:** +1 dependência e +2 MB na imagem, mais um diretório de artefatos; a durabilidade
    continua dependendo do volume.
  - **Contra (alinhamento):** `00-enunciado.md:54-55` pede que `#/porsequencia` **permita cadastrar**;
    uma rota separada só atende isso se houver um caminho claro a partir da página atual — é um risco
    literal de requisito, não só de UX.

- **Validation:**
  1. **Regressão das 6:** comparar as respostas de `/similares?sequencia=...` (todas as páginas, ou o
     conjunto completo via função interna) antes e depois da mudança, contra a imagem atual; tem que
     ser idêntico por construção, e o teste serve para provar que o seed não trocou ids.
  2. **Regra nova:** para uma sequência cadastrada, comparar o conjunto com a variante
     "subsequência + vocabulário" de `research/seq_famosa_rule.py`; documentar o contrafactual das 6
     (382/518/4/6/7/3) para deixar explícito o que a regra relaxada faria.
  3. **LMDB:** `run` → cadastrar → `restart` (mantém) → `rm` + `run -v` (mantém) → `rm` sem `-v`
     (perde); abrir dois processos escrevendo no mesmo diretório (medido OK,
     `research/embedded-db-options.md:179-181`); `map_size` estourado deve falhar de forma visível.
  4. **API:** mesmos casos da Proposta 1 (201/400/409, `Content-Type: text/html`, `[]` para
     desconhecida).
  5. **Frontend:** `#/porsequencia` lista 6 vindas da API; o botão leva a `#/nova-sequencia`;
     cadastrar volta para a lista e a sequência nova busca com a regra relaxada.
  6. **Carga:** medir o caminho `tag` (deve ficar igual ao de hoje) e o caminho relaxado
     (~125–150 ms por sequência sem pré-normalização, medido).

- **Open Questions:**
  - A diferença de semântica entre sequências semeadas e novas é aceitável como produto? Se não, esta
    proposta colapsa na Proposta 1.
  - Vale manter `SEQ_FAMOSA` como dependência viva do runtime? Isso precisa entrar na ADR 0002.
  - Uma rota separada de cadastro atende `00-enunciado.md:54-55`? Se não, o formulário tem que ir para
    `#/porsequencia` e a diferença para a Proposta 1 encolhe.
  - Recuperação de crash, backup e compactação do LMDB não foram medidos.
  - Migração futura de `regra='tag'` para a regra calculada: precisa recalcular e comparar antes de
    trocar, ou os resultados das 6 mudam.

---

## Medições feitas durante a síntese (não estavam na pesquisa)

Executado em `python:3.9-slim` (Python 3.9.25), 67.585 músicas carregadas por `main.py`, mesma regra
de `research/seq-famosa-rule.md:47-58`:

| Variante | Custo por sequência | Custo único no import | Memória extra |
|---|---|---|---|
| regra literal (`join` + `lower` por música, por consulta) | 183–188 ms | — | — |
| cifra pré-normalizada (`';'.join(lower)`, 14 MB) | 8–27 ms | 189 ms | ~14 MB |
| cifra pré-normalizada + `set` de tokens (31 MB) | 10–14 ms | 634 ms | ~31 MB |

Contagens idênticas às da pesquisa nas três variantes (199/296/4/5/7/3); a variante relaxada dá
382/518/4/6/7/3. O ganho de ~10x vem de não reconstruir a string da cifra a cada comparação.

## Artefatos

| Arquivo | Conteúdo |
|---|---|
| `research/solution-proposals.md` | Este documento |
| `research/seq-famosa-rule.md` | Regra validada e variantes |
| `research/embedded-db-options.md` | Opções de banco e ciclo de vida no container |
| `research/porsequencia-page.md` | Comportamento atual da página |
| `research/codebase-as-is.md` | Mapa do repositório com referências de linha |
