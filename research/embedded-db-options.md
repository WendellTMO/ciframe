# Bancos embarcados no container único do ADR 0001

Snapshot: commit `fb97001`, medido em 2026-10-30 com Docker 28.5.1 em arm64 (Apple Silicon),
imagem base `python:3.9-slim` (Python 3.9.25, SQLite 3.46.1). Nenhuma opção é escolhida neste
documento — ele só mede o que cabe no container e o que acontece com os dados em cada ciclo de vida.

## Summary

O container descrito em `docs/adr/0001-local-only-docker-deploy.md:9-16` é um `Dockerfile` de 12
linhas (`Dockerfile:1-12`): `python:3.9-slim`, `pip install -r requirements.txt`, `COPY . .` e
`gunicorn --bind 0.0.0.0:8080 main:app`, sem `VOLUME`, sem `USER`, sem `HEALTHCHECK` e sem compose.
O gunicorn não recebe `--workers`, e o default do gunicorn 23 é **1 worker** (medido com
`gunicorn --help`), então hoje existe um único processo Python servindo o app. Os 78 MB de `/app`
(77 MB são `data/`) entram na imagem pelo `COPY . .` (`Dockerfile:8`); o `.dockerignore` só exclui
`.git`, `.venv`, `__pycache__` e `*.pyc`. O processo atual **não escreve nada em disco**: o único
`open()` do backend é `main.py:49`, em modo leitura, e o CSV é carregado uma vez no import
(`main.py:47-98`). Cabem no container, sem serviço externo e sem `apt-get`: `sqlite3` (stdlib, 0 MB),
`tinydb` (1 MB), `lmdb` (2 MB), `rocksdict` (11 MB), `zodb` (30 MB), `duckdb` (52 MB) e
`shelve`/`dbm.gnu` (stdlib) — todos com wheel `cp39` para linux/arm64; `h5py`/`tables` (75 MB) e
`pyarrow` (130 MB) também instalam, e `bsddb3` não (sem wheel e o build quebra no `slim`). Qualquer
uma dessas opções, sem volume, grava no *writable layer* do container: os dados sobrevivem a
`docker restart`/`stop`+`start` e somem em `docker rm` + `docker run`. Só volume nomeado ou bind
mount sobrevive à recriação do container; `VOLUME` no `Dockerfile` **não** resolve isso, porque cada
container novo ganha um volume anônimo novo (medido).

---

## 1. O container de hoje

### 1.1 O que o `Dockerfile` fixa

| Linha | Conteúdo | Consequência para um banco embarcado |
|---|---|---|
| `Dockerfile:1` | `FROM python:3.9-slim` | libc/glibc do Debian slim; wheels `manylinux` funcionam, builds a partir de sdist não têm compilador |
| `Dockerfile:3` | `WORKDIR /app` | todo caminho relativo do app cai em `/app` (é o caso de `main.py:49`) |
| `Dockerfile:5-6` | copia `requirements.txt` e roda `pip install --no-cache-dir` | qualquer dependência nova entra como linha em `requirements.txt`, sem tocar no `Dockerfile` |
| `Dockerfile:8` | `COPY . .` | tudo que estiver no contexto de build entra na imagem, inclusive um arquivo de banco criado localmente |
| `Dockerfile:10` | `EXPOSE 8080` | irrelevante para o banco |
| `Dockerfile:12` | `CMD gunicorn --bind 0.0.0.0:8080 main:app` | sem `--workers` → 1 processo; sem `--preload` → cada worker importa `main` por conta própria |

Não há `VOLUME`, `ENTRYPOINT`, `USER`, `HEALTHCHECK`, multi-stage, nem `docker-compose*.yml` no
repositório (verificado com `ls docker-compose* compose*`). O comando de execução documentado é
`docker run -p 8080:8080 ciframe` (`AGENTS.md:24`), sem `-v`.

### 1.2 O que já vai dentro da imagem

- `data/` = 77 MB, sendo `data/top/dataset_final.csv` = 15.866.887 bytes.
- repositório inteiro = 124 MB; `/app` dentro da imagem = 78 MB.
- imagem construída a partir do `Dockerfile` atual = **345 MB** (`docker build -t ciframe-baseline .`).
- `.dockerignore:1-4` exclui apenas `.git`, `.venv`, `__pycache__` e `*.pyc` — `data/`, `docs/`,
  `scripts/`, `research/` e `static/` vão para a imagem.

### 1.3 O processo não escreve nada hoje

`grep -nE "open\(|\.write\(" main.py musica.py` retorna só `main.py:49` (`open('data/top/dataset_final.csv')`,
modo leitura). O catálogo de músicas/gêneros é montado em memória no import (`main.py:52-98`) e os
handlers só serializam (`main.py:142-201`). Ou seja, um banco embarcado seria o primeiro caminho de
escrita do backend.

O `Dockerfile` também não define usuário, então o processo roda como root e os arquivos que criar
ficarão com dono `root:root` (em volume nomeado é invisível; em bind mount no Linux aparece como
root no host).

---

## 2. Onde um banco pode gravar e o que sobrevive

### 2.1 Os quatro lugares possíveis

| Lugar | Como é criado | Quem grava | Some quando |
|---|---|---|---|
| camada da imagem | `COPY`/`RUN` no build | ninguém (read-only em runtime) | `docker build` de novo (a imagem é reconstruída) |
| writable layer do container | qualquer escrita em `/app` sem volume | processo do container | `docker rm` |
| volume nomeado | `-v nome:/caminho` ou `VOLUME` + `docker run -v nome:` | processo do container | `docker volume rm`, `docker system prune --volumes` |
| bind mount | `-v /host/dir:/caminho` | processo do container, arquivo no host | remoção manual no host |

### 2.2 Ciclo de vida (comportamento do Docker, medido na seção 2.3)

| Evento | Imagem | Writable layer | Volume nomeado | Bind mount |
|---|---|---|---|---|
| `docker restart` / `docker stop` + `docker start` | igual | **preserva** | preserva | preserva |
| `docker rm` + `docker run` (recriar) | igual | **perde** (volta ao estado da imagem) | **preserva** | preserva |
| `docker build` + `docker run` (imagem nova) | novo conteúdo | container antigo não é afetado; container novo usa a imagem nova | preserva | preserva |
| `docker run --rm` | igual | perde ao sair | preserva | preserva |
| `docker system prune --volumes` | — | — | **perde** | preserva |

### 2.3 Medições do ciclo de vida

Harness: imagem `python:3.9-slim` com `COPY . .` e um `store.py` que abre
`/app/data/store.sqlite` (ou `$DB_PATH`), faz `create table if not exists` e insere uma linha,
imprimindo o total. Saída real:

| Cenário | Total de linhas |
|---|---|
| `docker run` (container novo) | 1 |
| `docker stop` + `docker start` no mesmo container | 2 |
| `docker rm -f` + `docker run` (recriado, sem volume) | 1 |
| `-v vol:/data`, container novo | 1 |
| volume, `stop` + `start` | 2 |
| volume, `rm -f` + `run` | 3 |
| volume, `docker volume rm` + `run` | 1 |
| bind mount `-v $PWD/hostdata:/data`, duas execuções | 1 → 2, arquivo `store.sqlite` visível no host |
| arquivo de banco presente no contexto de build (`data/store.sqlite` com 6 linhas) + `COPY . .` | 6 em **todo** container novo |
| `VOLUME /app/data` no Dockerfile, imagem com o arquivo de 6 linhas | 6 no primeiro run, 7 após restart, **6** após `rm` + `run` (volume anônimo novo), volume antigo fica órfão |

`docker diff` no container após o primeiro run mostra `A /app/data` e `A /app/data/store.sqlite`,
confirmando que o arquivo está no writable layer, não na imagem.

### 2.4 Nuances que mudam a resposta

1. **`COPY . .` (`Dockerfile:8`) assa o banco no build.** Se um arquivo de banco existir no diretório
   local na hora do `docker build`, ele entra na imagem (medido: 6 linhas em todos os containers
   novos). O `.dockerignore` atual não exclui nenhum caminho de dados.
2. **`VOLUME` no `Dockerfile` não compartilha dados entre containers.** Cada `docker run` cria um
   volume anônimo novo; `docker rm` sem `-v` deixa o anterior órfão (medido: 2 volumes dangling).
   O volume novo é populado com o conteúdo que já existe na imagem naquele caminho (por isso o
   primeiro run viu 6 linhas).
3. **Reiniciar não é recriar.** `docker restart`, `docker stop`/`start` e a política
   `--restart unless-stopped` só reiniciam o processo; o writable layer continua o mesmo. Já
   `docker rm` + `docker run`, `docker compose up --force-recreate` (não há compose hoje) ou
   `docker run --rm` partem do estado da imagem.
4. **Volume nomeado no Docker Desktop mora na VM do Docker**, não no Finder; `docker volume rm` e
   o botão de "clean / purge data" apagam. Bind mount grava direto no host, mas passa pela camada de
   compartilhamento de arquivos do Docker Desktop.

---

## 3. Opções que cabem no container

Todas as medições abaixo foram feitas dentro de `python:3.9-slim` arm64, com
`pip install --no-cache-dir --target` e execução real de escrita/leitura.

### 3.1 Visão geral

| Opção | Import | Dependência nova | Delta no `Dockerfile` | Instalado | Processos | Artefato em disco |
|---|---|---|---|---|---|---|
| SQLite | `sqlite3` (stdlib) | nenhuma | nenhum | 0 MB | multi-processo OK (medido) | 1 arquivo (`.db`, + `-wal`/`-shm` se WAL) |
| DuckDB | `duckdb` | 1 linha em `requirements.txt` | nenhum | 52 MB | **1 processo** (lock exclusivo, medido) | 1 arquivo (`.duckdb` + `.wal`) |
| LMDB | `lmdb` | 1 linha | nenhum | 2 MB | multi-processo OK (medido) | 1 diretório (`data.mdb`, `lock.mdb`) |
| RocksDB | `rocksdict` | 1 linha | nenhum | 11 MB | **1 processo** (`LOCK`, medido) | 1 diretório |
| TinyDB | `tinydb` | 1 linha | nenhum | 1 MB | não suporta multi-processo (doc) | 1 arquivo JSON |
| `shelve`/`dbm.gnu` | stdlib | nenhuma | nenhum | 0 MB | escrita concorrente não suportada (doc) | 1+ arquivos `dbm` |
| ZODB | `zodb` | 1 linha | nenhum | 30 MB | `FileStorage` é de 1 processo; multi via ZEO (serviço) | `Data.fs` + índice |
| HDF5 | `h5py` / `tables` | 1 linha | nenhum (wheel traz HDF5) | 75 MB | 1 processo | 1 arquivo `.h5` |
| Parquet | `pyarrow` | 1 linha | nenhum | 130 MB | arquivos imutáveis, sem transação | arquivo(s) `.parquet` |
| BerkeleyDB | `bsddb3` | 1 linha + `apt` | `apt-get install libdb-dev` antes do `pip` | — | — | — |

### 3.2 SQLite (`sqlite3`, stdlib)

- **Dependência:** nenhuma; o módulo já está na imagem (`sqlite3.sqlite_version` = 3.46.1).
- **Delta no `Dockerfile`:** nenhum. `requirements.txt:1-5` fica como está.
- **Reinício vs recriação:** arquivo em `/app/...` → sobrevive a `restart`/`stop`+`start`, some em
  `rm` + `run`; sobrevive a recriação se o caminho estiver em volume nomeado ou bind mount.
- **Concorrência:** dois processos escrevendo no mesmo arquivo funcionaram (segundo processo `rc 0`,
  linha visível na conexão do primeiro). O gunicorn roda com 1 worker hoje (`Dockerfile:12`).
- **Tamanho medido:** 8.192 bytes para um arquivo com uma tabela e uma linha.
- **Observações:** arquivo único; `PRAGMA journal_mode=WAL` cria também `-wal`/`-shm`; o diretório
  precisa ser gravável (o processo roda como root, então `/app` serve).

### 3.3 DuckDB (`duckdb==1.4.5`)

- **Dependência:** wheel `cp39` `manylinux_2_28_aarch64` disponível; instala sem compilador.
- **Delta no `Dockerfile`:** uma linha em `requirements.txt`
  (`duckdb==1.4.5`), nada mais — `Dockerfile:5-6` já instala.
- **Reinício vs recriação:** igual ao SQLite (arquivo + `.wal`).
- **Concorrência:** abre o arquivo com lock exclusivo por processo. Segundo processo no mesmo
  arquivo falha:
  `_duckdb.IOException: IO Error: Could not set lock on file ".../x.duckdb": Conflicting lock is held in ...`.
  Com o `CMD` atual (1 worker) isso não aparece; com `gunicorn -w N` (N > 1) cada worker tentaria
  abrir o mesmo arquivo.
- **Tamanho medido:** 52 MB instalados; arquivo mínimo de 274.432 bytes para uma tabela de uma linha.

### 3.4 LMDB (`lmdb==3.0.0`)

- **Dependência:** wheel `cp39` `manylinux2014_aarch64` (544 KB de download).
- **Delta no `Dockerfile`:** uma linha em `requirements.txt`.
- **Reinício vs recriação:** é um diretório (não um arquivo) — o volume/bind mount precisa apontar
  para o diretório.
- **Concorrência:** dois processos no mesmo *environment* funcionaram (segundo processo `rc 0`; o
  primeiro enxergou a chave gravada pelo segundo).
- **Tamanho medido:** 2 MB instalados.
- **Observação:** `map_size` é definido na abertura do environment.

### 3.5 RocksDB (`rocksdict==0.3.29`)

- **Dependência:** wheel `cp39` `manylinux_2_28_aarch64`.
- **Delta no `Dockerfile`:** uma linha em `requirements.txt` (11 MB instalados).
- **Reinício vs recriação:** diretório; mesma regra de volume.
- **Concorrência:** segundo processo no mesmo diretório falha:
  `IO error: While lock file: .../LOCK: Resource temporarily unavailable`.

### 3.6 TinyDB (`tinydb==4.8.2`)

- **Dependência:** pacote puro Python (28 KB de wheel, 1 MB instalado).
- **Delta no `Dockerfile`:** uma linha em `requirements.txt`.
- **Reinício vs recriação:** arquivo JSON; mesma regra de volume.
- **Concorrência:** a própria documentação lista "access from multiple processes or threads (e.g.
  when using Flask!)" e "ACID guarantees" entre os motivos para **não** usar TinyDB
  (tinydb.readthedocs.io, *Why Not Use TinyDB?*). Cada escrita reescreve o arquivo inteiro.
- **Tamanho medido:** 29 bytes para um documento `{"x": 1}`.

### 3.7 `shelve` + `dbm.gnu` (stdlib)

- **Dependência:** nenhuma; `import dbm.gnu` funciona na imagem.
- **Delta no `Dockerfile`:** nenhum.
- **Reinício vs recriação:** um ou mais arquivos `dbm` no caminho informado; mesma regra de volume.
- **Concorrência:** a documentação do `shelve` (Python 3.9) diz que o módulo "does not support
  concurrent read/write access"; leituras simultâneas são seguras.
- **Observação:** valores passam por `pickle`; chaves são strings.

### 3.8 ZODB (`zodb==6.1`)

- **Dependência:** `zodb` + `BTrees`, `persistent`, `transaction`, `ZConfig`, `cffi` (puro Python
  exceto `cffi`, que tem wheel).
- **Delta no `Dockerfile`:** uma linha em `requirements.txt` (30 MB instalados).
- **Reinício vs recriação:** `FileStorage` grava `Data.fs` (+ arquivo de índice) em um diretório;
  mesma regra de volume.
- **Concorrência:** armazenamento em arquivo é para um processo; acesso multi-processo é feito com
  ZEO, que é um servidor à parte (fora do escopo de "banco embarcado").
- **Observação:** banco de objetos com transações; não tem linguagem de consulta além de Python.

### 3.9 HDF5 (`h5py==3.14.0` / `tables==3.9.2`)

- **Dependência:** wheels `cp39` `manylinux_2_17_aarch64` (o wheel já traz a libhdf5).
- **Delta no `Dockerfile`:** uma linha em `requirements.txt` (75 MB instalados).
- **Reinício vs recriação:** arquivo `.h5`; mesma regra de volume.
- **Concorrência:** HDF5 é single-writer por processo.
- **Observação:** é formato hierárquico de arrays, sem semântica relacional/transacional.

### 3.10 Parquet (`pyarrow==21.0.0`)

- **Dependência:** wheel `cp39` `manylinux_2_28_aarch64`.
- **Delta no `Dockerfile`:** uma linha em `requirements.txt` (130 MB instalados — o maior da lista).
- **Reinício vs recriação:** arquivos `.parquet`; mesma regra de volume.
- **Observação:** é formato de arquivo colunar, não um banco: não há transação, índice nem escrita
  incremental; atualizar um registro significa reescrever o arquivo.

### 3.11 BerkeleyDB (`bsddb3`) — não instala no `slim`

- **Dependência:** não há wheel `cp39` para linux/arm64; o `pip download` cai para o sdist e falha
  com `metadata-generation-failed` (falta `libdb-dev` e compilador no `python:3.9-slim`).
- **Delta no `Dockerfile`:** exigiria uma camada de `apt-get` antes do `pip`, por exemplo:

  ```dockerfile
  RUN apt-get update && apt-get install -y --no-install-recommends libdb-dev \
      && rm -rf /var/lib/apt/lists/*
  ```

  (mais o custo de manter compilador/headers na imagem, já que o `slim` não os tem).
- **Reinício vs recriação:** arquivo(s) BerkeleyDB; mesma regra de volume.

### 3.12 Fora do escopo: servidores

PostgreSQL, MySQL/MariaDB, Redis e MongoDB não são embarcados: exigiriam um segundo processo dentro
do mesmo container (supervisor/entrypoint próprio), o que muda o modelo de processo único do
`CMD` (`Dockerfile:12`) e o "sem serviços externos adicionais" do enunciado
(`docs/features/sequencias-customizadas/00-enunciado.md:63-65`). O host já tem as imagens locais
`mariadb:10.11` e `postgis/postgis:16-3.4`, mas elas rodam como containers separados.

---

## 4. Consolidado: o que muda no `Dockerfile`, por opção

O `Dockerfile` tem 12 linhas e nenhuma delas precisa mudar para as opções que são apenas
dependência Python, porque `Dockerfile:5-6` já instala tudo que está em `requirements.txt`.

| Grupo | Opções | Mudança exata |
|---|---|---|
| stdlib | SQLite, `shelve`/`dbm.gnu` | **nenhuma** — `Dockerfile` e `requirements.txt` intactos |
| pip puro | DuckDB, LMDB, RocksDB, TinyDB, ZODB, HDF5, Parquet | 1 linha ao final de `requirements.txt` (hoje `Flask==3.1.3` / `gunicorn==23.0.0`, `requirements.txt:4-5`); `Dockerfile:5-6` já cobre |
| precisa de `apt` | BerkeleyDB (`bsddb3`) | `RUN apt-get update && apt-get install -y --no-install-recommends libdb-dev && rm -rf /var/lib/apt/lists/*` entre `Dockerfile:6` e `Dockerfile:8` |
| precisa de volume | qualquer uma das acima, se os dados tiverem que sobreviver a recriação | **nada no `Dockerfile`**; `docker run -v ciframe-data:/app/data/db ...` (o `AGENTS.md:24` não tem `-v`) |
| quer assar o banco no build | qualquer uma | `RUN python -c "..."` **depois** de `Dockerfile:8` (o `COPY . .` precisa vir antes), com o cuidado do item 2.4.1 |

Exemplo do diff de `requirements.txt` (idêntico para qualquer opção do grupo "pip puro"):

```diff
 Flask==3.1.3
 gunicorn==23.0.0
+duckdb==1.4.5
```

Nada mais do `Dockerfile` muda nesse caso: `FROM`, `WORKDIR`, `EXPOSE` e `CMD` continuam iguais, e a
camada de `pip` é reconstruída sozinha porque `Dockerfile:5-6` vêm antes de `Dockerfile:8`.

---

## 5. Como as opções encostam no código atual

1. **Carga:** `main.py:47-98` roda no import do módulo, uma vez por processo. O `CMD`
   (`Dockerfile:12`) não usa `--preload`, então cada worker faria sua própria inicialização — com 1
   worker (default) há uma. `musica.py:17` monta `acordes` com `set`, sem tocar em disco.
2. **Escrita:** não existe hoje (item 1.3). O único estado mutável é em memória
   (`musicas_dict`/`musicas`, `main.py:47-98`).
3. **Persistência exigida:** só o catálogo de sequências
   (`docs/features/sequencias-customizadas/00-enunciado.md:52-53`); músicas e gêneros continuam
   vindo do CSV (`:60-62`).
4. **Container:** continua o `Dockerfile` único, local-only, sem serviço adicional (`:63-65`).
5. **Concorrência:** com o `CMD` atual há um processo; se `--workers` for adicionado, DuckDB e
   RocksDB deixam de abrir o arquivo (lock exclusivo), SQLite e LMDB continuam abrindo, e TinyDB
   fica sem garantia de multi-processo.
6. **Volume:** o `Dockerfile` não declara `VOLUME`, então hoje todo caminho é writable layer. Para
   sobreviver a `docker rm`/recriação, o caminho do banco precisa estar em volume nomeado ou bind
   mount; `VOLUME` sozinho dá um volume anônimo novo por container (item 2.4.2).

---

## 6. Como reproduzir

Os números de instalação e de ciclo de vida saem de:

```
bash research/embedded_db_probe.sh
```

Equivalente manual, dentro do `python:3.9-slim` (arm64):

```
docker run --rm python:3.9-slim bash -c '
  python -c "import sqlite3; print(sqlite3.sqlite_version)"
  for p in duckdb lmdb rocksdict tinydb zodb h5py pyarrow bsddb3; do
    python -m pip download --no-deps -q -d /tmp/$p $p && echo "OK $p" || echo "FAIL $p"
  done'
```

Ciclo de vida: construir uma imagem com `COPY . .` e um script que escreve em `/app/data/x.sqlite`,
depois `run` → `stop`/`start` → `rm`+`run` → `-v vol:/data` → `docker volume rm vol`.

## 7. Artefatos

| Arquivo | Conteúdo |
|---|---|
| `research/embedded-db-options.md` | Este documento |
| `research/embedded_db_probe.sh` | Script que reproduz as medições de disponibilidade de wheel, tamanho instalado e ciclo de vida |
| `Dockerfile` | Container único medido (12 linhas, sem volume) |
| `docs/adr/0001-local-only-docker-deploy.md` | Decisão de deploy que define o container |
| `docs/features/sequencias-customizadas/00-enunciado.md` | Requisito de persistência e de container único |
