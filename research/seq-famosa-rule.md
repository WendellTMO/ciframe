# Validação da regra que gera a coluna `SEQ_FAMOSA`

Snapshot: commit `fb97001`, executado em 2026-10-30. Script de apoio:
`research/seq_famosa_rule.py` (somente leitura, não altera nenhum arquivo do app).

## Summary

A coluna 7 do CSV é escrita em tempo de geração por `scripts/generate_data_set.py:7-24`, sobre a
lista de acordes crua da música (`str_notas`, `generate_data_set.py:69-76`), e guarda o id da
sequência (0–5) ou `NA`. A regra tem duas condições simultâneas: a sequência precisa aparecer como
**trecho contíguo** da cifra e **todo** acorde da música precisa pertencer ao vocabulário da
sequência; a única normalização é `.lower()` (`generate_data_set.py:10-12`). Transcrevi essa regra em
`research/seq_famosa_rule.py` e a apliquei às 67.585 músicas carregadas por `main.py`
(`musica.cifra`, já pós-`limpa_cifra`): o resultado **reproduz a coluna exatamente**, com 0
divergências nas seis sequências (514 músicas marcadas na coluna, 514 encontradas pela regra, 514 em
comum). Aplicada à coluna 8 crua do CSV, a mesma regra também reproduz 100% da coluna. Variantes
mais frouxas da regra (só contiguidade, só vocabulário, ou subsequência com lacunas) produzem
contagens maiores e não fecham com a coluna em todas as sequências.

---

## 1. Qual regra gerou a coluna

### 1.1 Onde ela é escrita

| Passo | Referência |
|---|---|
| Função que decide as tags | `scripts/generate_data_set.py:7-24` (`get_famosas`) |
| Lista das 6 sequências (minúsculas, `;`) | `scripts/generate_data_set.py:8` |
| Cifra de entrada (`str_notas`) | `scripts/generate_data_set.py:69-74`; vira `'NA'` quando vazia (`:75-76`) |
| Chamada e junção dos ids | `scripts/generate_data_set.py:85-88` (`famosas = ''.join(get_famosas(str_notas))`) |
| Escrita da coluna 7 | `scripts/generate_data_set.py:89` (último campo do `print`) |

O script é Python 2 e não é executado pelo app; ele produziu o CSV que está versionado.

### 1.2 A regra, linha por linha

```python
seqs = ['bm;g;d;a','c;g;am;f', 'em;g' , 'c;a7;dm;g7', 'gm;f', 'c;c7;f;fm' ]   # :8
acorde = acorde.lower()                                                       # :12
if s in acorde:                                                               # :13  (1)
    ...
    for l in acorde.split(';'):                                               # :16
        tokens = s.split(';')                                                 # :17
        if l not in tokens:                                                   # :18  (2)
```

1. **Contiguidade** (`:13`): `s in acorde` é substring do string inteiro `a;b;c;...`, então a
   sequência tem que aparecer colada, na ordem, sem nenhum acorde entre os seus.
2. **Vocabulário fechado** (`:16-20`): cada token da música tem que estar entre os tokens da
   sequência. Uma música que usa C, G, Am, F **e mais** Dm não recebe a tag.
3. **Única normalização** (`:12`): `.lower()`; não há equivalência enarmônica (`C#` ≠ `Db`), nem
   tratamento de baixo (`C/G` ≠ `C`), nem de sufixo (`C7` ≠ `C`).
4. **Saída** (`:21-23`): `str(i)`, onde `i` é o índice na lista `:8`; sem match, `'NA'` (`:85-87`);
   com mais de um match, `''.join(...)` concatenaria os ids (`:88`).

`acorde` é reatribuído dentro do laço (`:12`), mas `lower()` é idempotente, então o efeito é o de
uma única conversão.

### 1.3 Mapa id ↔ sequência ↔ chave da API

Os ids da lista `generate_data_set.py:8` são os mesmos usados no dicionário `main.py:40-45`:

| id | `generate_data_set.py:8` | chave em `main.py:40-45` | acordes |
|---|---|---|---|
| 0 | `bm;g;d;a` | `BmGDA` | Bm G D A |
| 1 | `c;g;am;f` | `CGAmF` | C G Am F |
| 2 | `em;g` | `EmG` | Em G |
| 3 | `c;a7;dm;g7` | `CA7DmG7` | C A7 Dm G7 |
| 4 | `gm;f` | `GmF` | Gm F |
| 5 | `c;c7;f;fm` | `CC7FFm` | C C7 F Fm |

O dicionário de `main.py` é o lado da consulta; a coluna 7 é o lado dos dados. A única ligação entre
os dois é o índice posicional.

---

## 2. O script de validação

`research/seq_famosa_rule.py`

### 2.1 Como ele carrega os dados

- `os.chdir(REPO_ROOT)` + `sys.path.insert(0, REPO_ROOT)` antes do `import main`
  (`research/seq_famosa_rule.py:16-22`), porque `main.py:49` abre o CSV por caminho relativo.
- Itera `main.musicas.values()` (`main.py:88-89`), ou seja, exatamente as músicas carregadas pelo
  app: 67.585 objetos `Musica`.
- Lê `musica.cifra` (lista pós-`limpa_cifra`, `main.py:58-61` e `main.py:11-23`) e
  `musica.seqs_famosas` (coluna 7, `main.py:63`).
- Confere com `assert` que `main.sequencias[key] == id` para as seis chaves
  (`research/seq_famosa_rule.py:24-25` e `:102-103`), para não comparar ids trocados.

### 2.2 A regra implementada

```python
def rule_matches(cifra_tokens, seq):
    toks = [t.lower() for t in cifra_tokens]
    seq_toks = seq.split(';')
    if seq not in ';'.join(toks):
        return False
    return all(t in seq_toks for t in toks)
```

`research/seq_famosa_rule.py:47-58`. É a transcrição direta de `generate_data_set.py:12-20`.

### 2.3 Execução

```
python research/seq_famosa_rule.py          # regra sobre musica.cifra (carregada pelo main.py)
python research/seq_famosa_rule.py --raw    # idem + comparação com a coluna 8 crua
```

Requer `Flask` instalado (o script importa `main.py`); o ambiente usado foi Python 3.14.4 +
Flask 3.1.3. O modo `--raw` também imprime como a lista de tokens crua difere da carregada
(`research/seq_famosa_rule.py:128-152`).

---

## 3. Resultado por sequência

Saída de `python research/seq_famosa_rule.py` (regra sobre `musica.cifra`):

| id | sequência | coluna marca | regra encontra | em comum | só na coluna | só na regra |
|---|---|---|---|---|---|---|
| 0 | Bm G D A | 199 | 199 | 199 | 0 | 0 |
| 1 | C G Am F | 296 | 296 | 296 | 0 | 0 |
| 2 | Em G | 4 | 4 | 4 | 0 | 0 |
| 3 | C A7 Dm G7 | 5 | 5 | 5 | 0 | 0 |
| 4 | Gm F | 7 | 7 | 7 | 0 | 0 |
| 5 | C C7 F Fm | 3 | 3 | 3 | 0 | 0 |
| | **total** | **514** | **514** | **514** | **0** | **0** |

Conferências adicionais feitas pelo script (`research/seq_famosa_rule.py:110-117`):

- 0 músicas satisfazem duas regras ao mesmo tempo, então a soma por sequência é o total de músicas
  marcadas (514).
- Distribuição dos tokens armazenados em `seqs_famosas` nas 67.585 músicas:
  `''` 67.071, `1` 296, `0` 199, `4` 7, `3` 5, `2` 4, `5` 3.
- Não existe valor composto (tipo `01`) na coluna; todos os valores são `NA` ou um dígito.

---

## 4. Comparação com variantes da regra

O mesmo script mede três variantes (`research/seq_famosa_rule.py:60-91`):

- **contiguidade**: só a condição 1 — a sequência aparece colada, sem restrição de vocabulário.
- **vocabulário**: só a condição 2 — a música só usa acordes da sequência, em qualquer ordem.
- **subsequência + vocabulário**: os acordes aparecem na ordem, mas com lacunas permitidas.

| id | coluna | contiguidade | vocabulário | subsequência+voc | xor vs coluna (subseq) | regra implementada |
|---|---|---|---|---|---|---|
| 0 | 199 | 972 | 873 | 382 | 183 | **199** |
| 1 | 296 | 1.246 | 958 | 518 | 222 | **296** |
| 2 | 4 | 3.704 | 24 | 4 | 0 | **4** |
| 3 | 5 | 96 | 53 | 6 | 1 | **5** |
| 4 | 7 | 1.522 | 18 | 7 | 0 | **7** |
| 5 | 3 | 144 | 57 | 3 | 0 | **3** |

Somente a conjunção das duas condições fecha com a coluna nas seis sequências. Para os ids 2, 4 e 5
a variante "subsequência + vocabulário" chega ao mesmo conjunto (xor 0), mas para 0, 1 e 3 ela
diverge — exemplo do id 3: `os-originais-do-samba_samba-da-vizinha` usa `C, Dm, A7, Dm, G7, ...`, tem
os acordes na ordem com lacunas e vocabulário fechado, e não tem a tag porque o trecho não é
contíguo (`xor` = 1 nesse id).

---

## 5. Cifra carregada vs. coluna crua do CSV

A regra original rodou sobre a string crua da coluna 8; a validação principal roda sobre
`musica.cifra`, que passa por `limpa_cifra` (`main.py:11-23`: descarta pedaços vazios, corta trechos
com `|` e normaliza espaços internos via `.split()`). As duas listas de tokens diferem em 8.224
músicas:

| Diferença | Músicas | Efeito na regra |
|---|---|---|
| coluna 8 é `NA` → `musica.cifra == []` | 8.141 | nenhum: `NA` e `[]` não casam |
| pedaço vazio (`;;` ou `;` final) | 51 | contiguidade fica mais fácil na cifra carregada |
| trecho com `\|` (tablatura) | 3 | token truncado por `limpa_cifra` |
| diferença só de espaço interno no token | 29 | token normalizado por `.split()` |
| **total** | **8.224** | |

Apesar disso, rodando `--raw` (regra aplicada à coluna 8 crua), o resultado é idêntico:
0 divergências nas seis sequências e 0 músicas em que a classificação loaded vs. raw difere
(`research/seq_famosa_rule.py:155-165`).

---

## 6. Conexões com o restante do código

1. **Geração**: `str_notas` (`generate_data_set.py:69-76`) → `get_famosas` (`:7-24`) → coluna 7
   (`:85-89`).
2. **Carga**: `main.py:53` remove `NA`; `main.py:63` faz `split(';')` → `Musica.seqs_famosas`
   (`musica.py:18`).
3. **Consulta**: `main.py:191` remove as vírgulas do parâmetro; `main.py:194-196` traduz a string
   para id via `main.sequencias`; `main.py:209` testa `str(id_seq) in musica.seqs_famosas`.
4. **Resposta**: `main.py:210-221` monta os objetos sem `diferenca`/`intersecao`; `main.py:196`
   pagina com `get_pagina` (100 por página).
5. **Frontend**: `static/assets/js/controllers/sequencia.js:2-37` expõe 4 das 6 sequências (ids 0,
   1, 4, 5) e `static/templates/sequencia.html:40-58` renderiza os cards usando
   `ng-hide="music.diferenca.length"`.
6. **Nada no app recalcula a tag**: a única função que implementa a regra hoje é a do script de
   geração, fora do runtime (`scripts/generate_data_set.py:7-24`).

---

## 7. Como reproduzir

```
python3 -m venv .venv && source .venv/bin/activate
pip install -r requirements.txt
python research/seq_famosa_rule.py --raw
```

Saída esperada (trechos): `songs loaded by main.py: 67585`; tabela por sequência com
`column == rule == both` e `only column == only rule == 0`; `total column-only: 0`;
`total rule-only  : 0`; `songs where loaded-rule and raw-rule disagree: 0`.

## 8. Artefatos

| Arquivo | Conteúdo |
|---|---|
| `research/seq_famosa_rule.py` | Implementação da regra sobre `musica.cifra`, comparação com `seqs_famosas`, variantes e diagnóstico `--raw` |
| `research/seq-famosa-rule.md` | Este documento |
| `research/codebase-as-is.md` | Documentação geral do repositório; a coluna 7 e o caminho `/similares?sequencia` estão em §2.5 e §3.1 |
