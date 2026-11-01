> **Substituído por [`docs/features/sequencias-customizadas/03-plan.md`](../docs/features/sequencias-customizadas/03-plan.md).** Rascunho histórico; o plano vigente é o `03-plan.md`.

# Plano — Sequências de Acordes Customizadas

## Passos

1. [ ] Criar `sequencias_db.py` (novo, na raiz, ao lado de `main.py`): caminho fixo
   `data/db/sequencias.sqlite`, `init_db()` que cria `data/db/` e a tabela
   `sequencias(id INTEGER PRIMARY KEY AUTOINCREMENT, chave TEXT NOT NULL UNIQUE, acordes TEXT NOT NULL)`,
   e faz o seed das 6 na ordem de `scripts/generate_data_set.py:8`
   (`Bm;G;D;A`, `C;G;Am;F`, `Em;G`, `C;A7;Dm;G7`, `Gm;F`, `C;C7;F;Fm`), só quando a tabela está
   vazia e com `ON CONFLICT(chave) DO NOTHING`. Expor `listar()`, `buscar_por_chave(chave)` e
   `criar(acordes)`. Conexão por operação, com `timeout` curto; nenhuma dependência nova.

2. [ ] Trocar o matching em `main.py`: apagar o dicionário `sequencias` (`:40-45`); chamar
   `init_db()` no import, depois da carga do CSV; adicionar `casa_com_sequencia(cifra, chave)` com
   as duas condições da proposta — trecho contíguo em `';'.join(normaliza(t) for t in cifra)` e
   todo token da música presente no vocabulário da sequência — usando `musica.cifra`, nunca
   `musica.acordes`. `normaliza(t)` deixa a primeira letra maiúscula e preserva o resto, então
   `C7M` ≠ `C7m` e `Gm` ≠ `GM`. Ajustar `/similares` (`:190-197`) para normalizar o parâmetro
   (split por vírgula, `strip()`, `normaliza`, junção com `;`), buscar a chave no catálogo e devolver
   `[]` quando não existir; manter o payload (`:210-220`) e `get_pagina` (`:226-228`) iguais.
   `get_similares_por_sequencia` (`:203-223`) passa a filtrar por `casa_com_sequencia` no lugar de
   `str(id_seq) in musica.seqs_famosas`.

3. [ ] Adicionar `GET /sequencias` e `POST /sequencias` em `main.py`, todos com `json.dumps`:
   `GET` devolve `[{"id": 1, "acordes": [...]}, ...]` ordenado por `id`; `POST` aceita
   `{"acordes": [...]}`, rejeita lista ausente/vazia/só em branco com `400`, cria com `201` e
   devolve `{"id", "acordes"}`, e em chave já existente devolve `409` com o `id` existente
   (tratar `IntegrityError` além da checagem prévia). Sem validação contra `/acordes`.

4. [ ] Atualizar o frontend de `#/porsequencia`: em `sequencia.js`, remover os 4 objetos
   hardcoded (`:2-37`), carregar a lista com `$http.get('sequencias')` e mapear cada item para
   `{acorde: token, cor: '#2E1C74'}`; acrescentar a função de cadastro que quebra o texto em
   `[,;\s]+`, faz `POST /sequencias`, trata `201` (adiciona e seleciona), `409` (seleciona a
   existente e avisa) e `400` (mostra erro). Em `sequencia.html`, manter a lista (`:6-8`) e
   adicionar abaixo dela o campo de texto + botão "Cadastrar"; a busca, o `<select>` de gênero e
   os cards (`:42-56`) não mudam.

5. [ ] Ajustar a operação: incluir `data/db/` em `.dockerignore` e `.gitignore`; trocar o comando
   em `AGENTS.md:24` por `docker run -p 8080:8080 -v ciframe-seq:/app/data/db ciframe`. Não mexer
   em `Dockerfile`, `requirements.txt` nem `musica.py`.

6. [ ] Escrever/adaptar o script de regressão (baseado em `research/seq_famosa_rule.py`, que hoje
   depende de `main.sequencias`) para carregar `main`, aplicar o matcher novo às 6 chaves do seed e
   comparar com a coluna `SEQ_FAMOSA`: esperado 199, 296, 4, 5, 7 e 3 músicas e 0 diferenças.
   Rodar também os testes manuais de `GET`/`POST`/`/similares` e da página.

## Arquivos afetados

| Arquivo | Mudança |
|---|---|
| `main.py` | Remove o dicionário de sequências; chama `init_db()`; matching por `casa_com_sequencia`; `/similares` resolve pelo catálogo; novos `GET`/`POST /sequencias` |
| `sequencias_db.py` (novo) | Schema, seed das 6, conexão, `listar`/`buscar_por_chave`/`criar` |
| `static/assets/js/controllers/sequencia.js` | Lista vem de `GET /sequencias`; cadastro via `POST`; remoção dos 4 objetos hardcoded |
| `static/templates/sequencia.html` | Campo de texto + botão de cadastro abaixo da lista |
| `.dockerignore` | Inclui `data/db/` |
| `.gitignore` | Inclui `data/db/` |
| `AGENTS.md` | Comando `docker run` com o volume `ciframe-seq` |
| Script de regressão | Compara o matcher novo com `SEQ_FAMOSA` para as 6 |
| `musica.py` | Sem mudança: `seqs_famosas` continua sendo lido do CSV, só deixa de ser usado |
| `Dockerfile`, `requirements.txt` | Sem mudança: `sqlite3` já vem no Python |

## Riscos e mitigação

| Risco | Como perceber | Mitigação |
|---|---|---|
| `data/db/` não existe ou não tem permissão no primeiro boot | Erro no import / container não sobe | `init_db()` cria o diretório com `os.makedirs(..., exist_ok=True)` e falha no import, não na requisição |
| Banco local assado na imagem ou commitado | `docker run ... ls /app/data/db` mostra arquivo; `git status` mostra o `.sqlite` | `data/db/` no `.dockerignore` e no `.gitignore` |
| Volume no caminho errado esconde o CSV | `/generos` falha ao subir | Volume em `/app/data/db`, nunca em `/app/data` |
| Remover o dicionário quebra o script de regressão | `AttributeError` em `main.sequencias` | Atualizar o script no mesmo passo; ele passa a usar as chaves do seed |
| Seed duplicar a cada restart | `GET /sequencias` com mais de 6 itens | Seed só com tabela vazia + `UNIQUE(chave)` + `ON CONFLICT DO NOTHING` |
| Corrida entre dois `POST` iguais | Erro 500 em vez de 409 | `UNIQUE(chave)` e captura de `IntegrityError` retornando o `id` existente |
| Normalização nova muda resultados | Busca `bm,g,d,a` deixa de devolver `[]` (mudança desejada) ou as 6 divergem | Regressão das 6 com 0 diferenças; conferir `C7M` ≠ `C7m` e `Gm` ≠ `GM` |
| Busca lenta (~185 ms) | Tempo de resposta de `/similares?sequencia=` | Custo aceito; otimização de cifra pré-normalizada fora de escopo |
| Página quebra se `GET /sequencias` falhar | Lista vazia e erro no console | Estado textual de erro; busca existente continua funcionando |
| `POST` com acorde inexistente gera sequência sem resultados | Busca da sequência recém-criada retorna `[]` | Comportamento aceito: só lista vazia é recusada |

## Definição de pronto

- [ ] Subir o app com banco novo cria `data/db/sequencias.sqlite` e `GET /sequencias` devolve as 6
      sequências com `id` e `acordes`, ordenadas por `id`.
- [ ] `POST /sequencias` com `{"acordes": ["C","G","Dm"]}` responde `201`, o item aparece no
      `GET /sequencias` e a busca por ele devolve resultados coerentes com a regra.
- [ ] `POST` com lista vazia responde `400`; com sequência já existente (mesmo em outra caixa)
      responde `409` com o `id` da existente; acorde desconhecido é aceito.
- [ ] `GET /similares?sequencia=C,G,Am,F` mantém o formato e a ordem atuais, e sequência fora do
      catálogo continua devolvendo `[]`.
- [ ] As 6 sequências originais continuam com 199, 296, 4, 5, 7 e 3 músicas e 0 diferenças em
      relação à coluna `SEQ_FAMOSA` no script de regressão.
- [ ] `#/porsequencia` mostra as 6 (não 4), cadastra uma sequência sem recarregar a página e
      mantém a busca e o filtro por gênero como antes.
- [ ] Reiniciar o container mantém as sequências cadastradas (com o volume documentado em
      `AGENTS.md`); `data/db/` não entra na imagem nem no git.
- [ ] Todos os endpoints novos e alterados continuam devolvendo `json.dumps`
      (`Content-Type: text/html`) e `/generos` segue respondendo normalmente.
