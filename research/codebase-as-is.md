# deciframe — codebase as it exists today

Snapshot: commit `fb97001` ("Update 00-enunciado.md", author date Sat Oct 17 12:16:33 2026 -0300),
working tree clean at time of writing. Everything below describes the code and data present at
that commit, verified by reading the files and by running the app locally (see
[Verification log](#verification-log)).

## Summary

deciframe is a Flask application that loads a single 15 MB CSV (`data/top/dataset_final.csv`) into
memory at import time and serves both a JSON API and a static AngularJS 1.4.9 single-page app from
the same process; there is no database, no build step, and no test suite. `main.py` (280 lines) holds
all routes, all search/matching logic and all in-memory indexes, while `musica.py` (25 lines) is the
only domain class. The frontend in `static/` is a hash-routed SPA with five routes
(`/`, `/poracordes`, `/pormusica`, `/porsequencia`, `/sobre`), three of which call the API with a
relative URL. Two matching mechanisms coexist: chord/song similarity is computed live from each
song's chord list, while "famous sequence" search depends on a pre-computed `SEQ_FAMOSA` column
plus six sequence keys hardcoded in `main.py:40-45`; the `#/porsequencia` page hardcodes four of
those six sequences in JavaScript. Deploy is a single `python:3.9-slim` Dockerfile running gunicorn
on port 8080, and the repository also carries a Python-2/R data-collection pipeline under
`scripts/` and `data/top/` that the application never invokes.

---

## 1. Repository layout

| Path | Contents |
|---|---|
| `main.py` | Flask app, routes, in-memory indexes, matching logic (280 lines) |
| `musica.py` | `Musica` domain class (25 lines) |
| `requirements.txt` | `Flask==3.1.3`, `gunicorn==23.0.0` |
| `Dockerfile` | `python:3.9-slim` + gunicorn on `0.0.0.0:8080` |
| `static/` | AngularJS SPA (`index.html`, `assets/`, `templates/`) |
| `data/top/` | Source CSV, intermediate extracts, genre HTML snapshots (88 tracked files) |
| `scripts/` | Data collection/parsing/transform scripts (Python 2, R, Java, shell) |
| `docs/adr/` | Three ADRs: 0001 and 0003 written, 0002 is an unfilled template |
| `docs/features/sequencias-customizadas/` | Five phase templates; `00-enunciado.md` is the task statement, `01`–`04` are unfilled templates |
| `README.md`, `CONTRIB.md`, `AGENTS.md`, `LICENSE` (Apache 2.0) | Documentation and licensing |
| `.playground` | Google App Engine sample metadata file (`project_name: "Hello World - Python with Flask"`, `show_files` lists `main.py`, `app.yaml`, `appengine_config.py`; the latter two are not in the tree) |

No `.github/`, no CI config, no `pytest.ini`/`tox.ini`, no `tests/` directory; the only file matching
`*test*` in the repo is `docs/features/sequencias-customizadas/04-test-report.md` (an unfilled template).

---

## 2. Backend

### 2.1 Import-time data loading (`main.py:47-98`)

Loading happens at module import, so it also runs under gunicorn before the first request.

| Step | Lines | Behavior |
|---|---|---|
| Open + skip first line | `main.py:49-50` | `open('data/top/dataset_final.csv')` (relative path, so the process CWD must be the repo/`/app`), then `f.readline()` |
| Per-line normalization | `main.py:53` | `line.replace('"','').replace('NA','')[:-1]` — removes every double quote, removes every occurrence of the substring `NA` anywhere in the line, then drops the last character (`\n`) |
| Field split | `main.py:55` | plain `line.split(',')`, no CSV quoting |
| Popularity | `main.py:56` | `int(musica[5].replace('.',''))` |
| Chords | `main.py:58-61` | `limpa_cifra(musica[8].split(';'))`, or `[]` when empty |
| Famous sequences | `main.py:63` | `musica[7].split(';')` |
| Genres set | `main.py:66` | adds `musica[4]` to module-level `generos` |
| `Musica` object | `main.py:69-72` | built from the 9 columns |
| `musicas_dict` | `main.py:74` | keyed by `id_unico_musica` (`<id_artista>_<id_musica>`) |
| Chords set | `main.py:77-78` | union of each song's `acordes` |
| `genero_musicas` | `main.py:82-85` | genre → list of `Musica`, used by `apply_filtro` |
| Global ordering | `main.py:88-89` | `OrderedDict` of all songs sorted by `popularidade` descending |
| Genre ordering | `main.py:95-96` | each `genero_musicas[genre]` sorted by `popularidade` descending |
| Genre list | `main.py:92` | `generos = list(generos)` (set → list, order is set iteration order) |

Column index constants are at `main.py:26-34`; page size `TAM_PAGINA = 100` at `main.py:35`.

`limpa_cifra` (`main.py:11-23`) drops blank tokens, and for any token containing `|` keeps only the
text before the first `|` (first whitespace-delimited token of that prefix), so tablature lines
contribute their leftmost chord. Otherwise the line is split on whitespace and all tokens are kept.

### 2.2 `Musica` model (`musica.py:1-25`)

Fields assigned in `__init__`: `id_artista`, `nome_artista`, `id_musica`, `nome_musica`, `genero`,
`popularidade`, `tom`, `cifra` (list of chord tokens in playing order, duplicates preserved),
`acordes` = `list(set(cifra))` (deduplicated, unordered), `seqs_famosas` (list of strings),
`id_unico_musica` = `%s_%s % (id_artista, id_musica)`, and `url` =
`http://www.cifraclub.com.br/<id_artista>/<id_musica>`. `__str__` returns
`id_unico_musica,genero,popularidade`.

Because `acordes` comes from `set`, its ordering is not stable across processes; this ordering is
what `/musicas`, `/musica/<id>/` and the `acordes` field of `/similares` serialize (observed:
`/musica/guns-n-roses_sweet-child-omine/` returns the chord list starting `["D","C","G","D",...]`
with the underlying cifra also starting `D;C;G;...`, but the two orders are independent).

### 2.3 Endpoints

| Route | Handler | Inputs | Response shape |
|---|---|---|---|
| `/` | `main.py:101-103` | — | `static/index.html` |
| `/<path:path>` | `main.py:109-112` | any path | `app.send_static_file(path)`; serves `static/` (JS resolves to `text/javascript`, missing files → 404) |
| `/search` | `main.py:114-142` | `key` (required), `generos` (comma list, optional), `pagina` (default `'1'`) | array of `{id_unico_musica, id_artista, id_musica, nome_artista, nome_musica, genero, url}` — no `popularidade`, no `acordes` |
| `/musicas` | `main.py:154-156` | none | array of every song's full `__dict__` (12 keys) |
| `/generos` | `main.py:158-160` | none | array of 52 genre strings |
| `/acordes` | `main.py:162-164` | none | array of every distinct chord token (6,653) |
| `/musica/<m_id>/` | `main.py:166-168` | path id | one song's full `__dict__` |
| `/similares` | `main.py:170-201` | `acordes` OR `id_unico_musica` OR `sequencia`, plus `generos`, `pagina` | array of similar-song objects (see below), paginated |

All handlers return `json.dumps(...)` on a Python `str`, so responses carry
`Content-Type: text/html; charset=utf-8` (confirmed live). `@app.after_request` at `main.py:274-277`
adds `Access-Control-Allow-Origin: *` to every response, including static files and errors.

### 2.4 Search semantics (`/search`, `main.py:114-142`)

1. `generos_tag = request.args.get('generos', [])`; when absent the filter list is the module-level
   `generos` (all genres) — `main.py:116,121-123`.
2. `keys = request.args.get('key').lower()` then `remover_combinantes(keys).split(' ')` —
   `main.py:118-119`. `remover_combinantes` (`main.py:145-147`) NFD-normalizes and drops combining
   marks, i.e. accent-insensitive and case-insensitive.
3. Candidate set is `apply_filtro(musicas.values(), generos_key)` (`main.py:125`, `main.py:265-272`),
   which concatenates `genero_musicas[g]` for each requested genre that is present in the global
   genre list. Order is therefore genre-block order, each block sorted by popularity; it is not a
   single global popularity ordering.
4. Match rule: `all(key in text_list for key in keys)` where `text_list` is
   `(nome_artista + ' ' + nome_musica).lower()`, accent-stripped, split on single spaces —
   `main.py:128-131`. It is a token-equality test, not substring: the query `rock` does not match
   `rockabilly`, and word order does not matter but every query token must appear as a whole token.
5. Result is sliced by `get_pagina` (`main.py:226-228`): `colecao[(pagina-1)*100 : pagina*100]`.

Observed edge behavior: no `key` parameter → `AttributeError` on `None.lower()` → HTTP 500;
`pagina` non-numeric → `ValueError` → HTTP 500; `key=` (empty) → `keys == ['']`, and `'' in
text_list` is true only for titles/artists containing a double space, which returns 91 songs with no
ranking-by-relevance effect; `pagina=0` yields the slice `[ -100:0 ]` = empty list.

### 2.5 Similarity by chords / by song (`/similares`, `main.py:170-201`, `main.py:230-263`)

Input resolution order (`main.py:184-197`):

- `acordes` present → `acordes_tag.split(',')`.
- else `id_unico_musica` present → `musicas[id_musica_tag].acordes` (deduplicated chord set).
- else `sequencia` present → `sequencia_tag.replace(',','')`, so `sequencia=C,G,Am,F` becomes the
  string `CGAmF`. Only if that string is a key of the hardcoded `sequencias` dict
  (`main.py:40-45`) is `get_similares_por_sequencia` called; otherwise the handler returns `[]`
  immediately (`main.py:190-197`), bypassing pagination.
- otherwise `acordes` stays `[]`, and the generic path returns `[]`.

`get_similares` (`main.py:230-263`) iterates candidates from `apply_filtro`, skips the song whose
`id_unico_musica` equals the `id_unico_musica` query parameter, and keeps songs where
`set(acordes) ∩ set(musica.acordes)` is non-empty. Each result carries `id_unico_musica`,
`id_artista`, `id_musica`, `nome_artista`, `nome_musica`, `popularidade`, `acordes`, `genero`, `url`,
plus `diferenca` = `musica.acordes - query acordes` and `intersecao` = the intersection
(`main.py:240-258`). Results are sorted by `(len(diferenca), -len(intersecao))` (`main.py:263`); the
comment at `main.py:262` also mentions popularity, and the sort key does not include it. Ties keep
the genre-block order described in 2.4. Match is set-based, so chord order and repetition inside
`musica.cifra` play no role here.

`get_similares_por_sequencia` (`main.py:203-223`) does not compute anything from the song's chord
list: it includes a song when `str(id_seq) in musica.seqs_famosas` (`main.py:209`), where
`seqs_famosas` came from the `SEQ_FAMOSA` CSV column, and returns objects with `popularidade` and
`acordes` but no `diferenca`/`intersecao`. The dict `sequencias` maps the six literal strings
`BmGDA→0`, `CGAmF→1`, `EmG→2`, `CA7DmG7→3`, `GmF→4`, `CC7FFm→5` (`main.py:40-45`).

### 2.6 Pagination and filtering helpers

- `get_pagina(colecao, pagina_tag)` — `main.py:226-228`, 100 items per page, used by `/search` and
  by both `/similares` paths except the unknown-`sequencia` early return.
- `apply_filtro(musicas, generos_key)` — `main.py:265-272`; the parameter name shadows the global
  `musicas` `OrderedDict` inside the function body; genres not in the global `generos` list are
  silently skipped (observed: `generos=Nope` → `[]`).
- `/musicas` is not paginated despite the docstring at `main.py:149-153` which describes pages of
  100 and a `pagina` parameter; `get_musicas` at `main.py:154-156` returns every song
  (observed: 67,585 objects).

### 2.7 Process entry

- `python main.py` → `app.run(debug=True)` (default port 5000) — `main.py:279-280`.
- Docker → `gunicorn --bind 0.0.0.0:8080 main:app` — `Dockerfile:12`. No gunicorn config file, so
  gunicorn defaults apply (one sync worker).

---

## 3. Data assets

### 3.1 `data/top/dataset_final.csv`

15 MB, 67,586 lines, 9 comma-separated fields, no header row. First line is data
(`14-bis,a-qualquer-tempo,14 Bis,A Qualquer Tempo,MPB,70115,B,NA,E;F#;...`) and is discarded by
`f.readline()` at `main.py:50`, so **67,585 songs are loaded**.

Column order, per `main.py:26-34` and confirmed against the file:

| Index | Constant | Example |
|---|---|---|
| 0 | `ARTISTA_ID` | `guns-n-roses` |
| 1 | `MUSICA_ID` | `sweet-child-omine` |
| 2 | `ARTISTA` | `Guns N' Roses` |
| 3 | `MUSICA` | `Sweet Child O' Mine` |
| 4 | `GENERO` | `Rock` |
| 5 | `POPULARIDADE` | `7063127` (thousands separators as `.`) |
| 6 | `TOM` | `D`, or `NA` |
| 7 | `SEQ_FAMOSA` | `NA`, `0`, `1`, `1-...` composites |
| 8 | `CIFRA` | `D;C;G;D;...` or `NA` |

Observed properties of the file at this commit:

- 52 distinct values in column 4. 51 of them match the `GENEROS` array hardcoded in
  `static/assets/js/app.js:6-58`; the extra value is `R&B;` (the raw genre is `R&B,` and the
  comma-split leaves the semicolon).
- 8,141 rows have `CIFRA == NA`, which the global `NA` strip turns into `[]`.
- 6,653 distinct chord tokens survive into the `acordes` index (includes non-chord fragments such
  as `#11`, `(Cm)`, `1a.vez`, `2x`, `/Bbm`).
- `SEQ_FAMOSA` token frequency: empty (from `NA`) 67,071; `1` 296; `0` 199; `4` 7; `3` 5; `2` 4;
  `5` 3. Only 514 song-tag instances exist across six ids.
- 67,585 distinct `(ARTISTA_ID, MUSICA_ID)` pairs — no duplicate keys.
- The global `replace('NA','')` at `main.py:53` also hits 7 rows where `NA` occurs inside the song
  title column (e.g. `DNA`, `CABANA`, `JULIANA`, `ROTINA DE POBRE`, `BESTA RUANA`,
  `Surfando Em Karmas e DNA`, `She's Got Style (Versão ORIGINAL)`). Live effect:
  `/musica/gusttavo-lima_dna/` returns `"nome_musica": "D"`.

### 3.2 Other data files (`data/top/`)

`visualizacoes.csv` / `visualizacoes_pontos.csv` (view counts), `artista_musica_estilo.txt`
(artist→style mapping), `top_artistas.txt` + four `*.songs` shards (song URL lists),
`url-estilos.txt`, `html_estilos/` (75 saved genre pages), `chords-transitions-empty.csv`
(a header-only transition matrix: 42 `I-II…VII-VI` columns plus an unnamed index column).

---

## 4. Frontend

### 4.1 Bootstrap (`static/index.html`)

- `ng-app="deciframeApp"` on `<html>` (`:2`), `ng-controller="MainController"` on `<body>` (`:22`).
- CDN dependencies (`:126-134`): jQuery 1.11.3, Bootstrap 3.3.6 JS/CSS, AngularJS 1.4.9 +
  `angular-route` + `angular-animate`, `angular-ui-bootstrap` 2.1.4 (`ui-bootstrap` and
  `ui-bootstrap-tpls`), Google Fonts (Varela Round), plus local `assets/css/app.css`,
  `assets/css/icons.css` (icomoon font-face, 36 lines) and `favicon.ico`.
- Local scripts in load order (`:136-147`): `ngprogress.js` (vendored ngProgress 1.1.2, 218 lines),
  `app.js`, `routes.js`, `controllers/{main,home,about,acordes,musica,sequencia}.js`,
  `directives/{df-hex,df-esfinge}.js`. `controllers/search.js` is **not** referenced by
  `index.html` and no template uses `SearchController` or `pesquisarPorTitulo`.
- Google Analytics snippet with property `UA-85286010-1` (`:25-32`); Open Graph tags pointing at
  `http://deciframe.com` (`:7-11`); hidden preload of the logo image (`:23`).
- Chrome: navbar with inline SVG wordmark (`:40-85`) and a `df-hex` "?" toggle (`:37`);
  `showMenu` panel with project blurb and team grid (`:90-121`); routed view container
  `<div class="page" ng-view>` (`:123`).

### 4.2 Module, constants, routing

- `static/assets/js/app.js:1-2` declares `deciframeApp` with `ngRoute`, `ngAnimate`, `ngProgress`,
  `ui.bootstrap`.
- `app.js:3-5` registers a `RESTAPI` constant (`http://localhost:5003`) that no file consumes
  (grep for `RESTAPI` finds only this declaration).
- `app.js:6-58` hardcodes a 51-entry `GENEROS` array, injected into the three search controllers and
  used for the genre `<select>`. No controller calls `GET /generos`; the genre list in the UI is
  this constant.
- `static/assets/js/routes.js:1-29` maps `/`→`home.html`+`HomeController`,
  `/poracordes`→`acordes.html`+`AcordesController as Chords`,
  `/pormusica`→`musica.html`+`MusicaController as Musica`,
  `/porsequencia`→`sequencia.html`+`SequenciaController as Sequencia`,
  `/sobre`→`about.html`+`AboutController`, `otherwise`→`/`. No `$locationProvider`/html5Mode
  configuration exists, so URLs are hash-based.
- `MainController` (`controllers/main.js:1-12`) exposes `showMenu`, `toggleMenu()` and
  `isActive(path)`, which tests `$route.current.regexp`.

### 4.3 Search-by-chords page (`/poracordes`)

- `controllers/acordes.js:2-53` builds a fixed chord palette: arrays for C, D, E, F, G, A, B with
  color per chord (`acordesC`…`acordesB`), flattened into `vm.acordes` (7 groups).
- `vm.addAcorde` (`:63-71`) toggles a chord in `vm.meusAcordes` and re-runs the search;
  `vm.temAcorde` (`:72-74`) drives the "checked" visual state.
- `vm.pesquisarPorAcordes` (`:84-115`) builds `similares?acordes=A,B,C` from
  `vm.meusAcordes`, appends `&generos=<meuGenero>` when a genre is selected, GETs it through
  `$http`, and assigns `data` to `vm.musics`. `apiUrl` is the empty string (`:91`), so the request
  is same-origin. Empty chord selection clears results (`:109-114`).
- `vm.goToLirics` opens `music.url` in a new window (`:117-119`); `vm.goToResults` scrolls `body`
  to `#results` with a jQuery animation (`:121-124`).

### 4.4 Search-by-song page (`/pormusica`)

- `controllers/musica.js:14-20` provides `vm.getMusicas(val)` for the typeahead, calling
  `search?key=<val>` and returning `response.data`.
- The input in `templates/musica.html:13-18` uses `uib-typeahead` with
  `typeahead-min-length="3"`, `typeahead-wait-ms="1000"`, label
  `nome_musica (nome_artista)`, and `typeahead-on-select="Musica.pesquisarPorMusica(minhaMusica)"`.
- `vm.pesquisarPorMusica` (`:43-70`) calls `similares?id_unico_musica=<id>` (+ optional genre),
  sets `vm.minhaMusica`, `vm.musics`, and the "esfinge" speech text used as the results heading.
- Template renders the selected song as a highlighted card (`musica.html:47-62`), then songs with
  empty `diferenca` as playable (`:63-80`) and songs with non-empty `diferenca` under
  "Aprenda mais alguns acordes para tocar:" with the missing chords rendered as small `df-hex`
  (`:83-113`).

### 4.5 Famous-sequence page (`/porsequencia`)

- `controllers/sequencia.js:2-31` hardcodes four sequences as objects of `{acorde, cor}`:
  `Bm G D A`, `C G Am F`, `Gm F`, `C C7 F Fm`; all four have `'index': 1`. These are pushed into
  `vm.sequenciasFamosas` (`:33-37`). They correspond to backend ids 0, 1, 4 and 5; backend
  sequences `EmG` (id 2) and `CA7DmG7` (id 3) have no frontend entry.
- `vm.pesquisarPorSequencia` (`:63-90`) sends `similares?sequencia=<chords joined by commas>`
  (+ optional genre), so the backend receives e.g. `CGAmF` after stripping commas.
- `vm.limparPesquisa` (`:92-95`) resets the selection and results; `temAcorde` (`:47-53`) checks
  object identity within the selected sequence's chord objects.
- `templates/sequencia.html:6-8` repeats `Sequencia.sequenciasFamosas` and calls the search on
  click. The results grid (`:40-58`) uses `ng-hide="music.diferenca.length"`; the
  sequence endpoint's objects have no `diferenca` key, so that expression is `undefined` and the
  cards are shown. The template has no section for the "learn more chords" list that
  `acordes.html`/`musica.html` include, and no registration form.

### 4.6 Directives and CSS

- `dfHex` (`directives/df-hex.js:1-12`) is an element directive with isolate scope
  `acorde: '@'`, `acordeColor: '@'`, `acordeChecked: '='`, `small: '='`; template
  `templates/directives/df-hex.html:1-9` draws a hexagon SVG and fills it `#FFF` when checked,
  otherwise `acordeColor`, with the chord name below.
- `dfEsfinge` (`directives/df-esfinge.js:1-9`) takes `dfAnimated: '='` and renders
  `templates/directives/df-esfinge.html` (326 lines, inline SVG with `<style>` classes `.st0`–`.st17`
  and `ng-class="{'animated': dfAnimated}"` on the `#sompra_x5F_chao` and `#esfinge` groups).
  Used only on the home page (`templates/home.html:7`).
- `static/assets/css/app.css` (652 lines) holds layout and animation: page transitions
  (`:34-39`), colour-coded panels `.viewWindow-panel-A…F` (`:69-100`), chord palette container
  (`.acordes-container`, `:161`), navbar/menu (`:220-260`, `:308-…`), music cards
  (`.music-card`, `:263-…`), and keyframes (`:17-24`, `:468-…`) including `bounce`, `rotateIn`,
  `fadeInRight`.

### 4.7 Frontend build/dependency state

`static/bower.json:23-25` declares one dependency, `ng-material-floating-button` (`~0.6.2`), which
no HTML or JS file references (grep for `mfb` finds nothing). `static/.bowerrc` sets the bower
directory to `assets/vendor`, and `.gitignore:1` ignores `static/assets/vendor`; that directory is
not present. There is no `package.json`, bundler, transpiler or minified asset in the tree.

---

## 5. Cross-component data flows

1. **Browse by chords** — `acordes.html:7` click → `AcordesController.addAcorde`
   (`acordes.js:63-71`) → `pesquisarPorAcordes` (`:84-108`) → `GET /similares?acordes=…[&generos=…]`
   → `main.py:170-201` → `get_similares` (`main.py:230-263`) over `apply_filtro` candidates
   (`main.py:265-272`) → paginated to 100 → rendered as playable cards
   (`music.diferenca` empty) or "learn these chords" cards showing `music.diferenca` hexagons.
2. **Browse by a song** — typeahead on `musica.html:13` → `GET /search?key=` (`main.py:114-142`) →
   selecting a suggestion calls `GET /similares?id_unico_musica=<id>` → the selected song's
   `musica.acordes` become the query chord set (`main.py:187-189`) → same `get_similares` path.
   The selected song is excluded by `musica.id_unico_musica != id_musica` (`main.py:238`).
3. **Browse by famous sequence** — `sequencia.html:6` click → `GET /similares?sequencia=Bm,G,D,A`
   → commas stripped to `BmGDA` (`main.py:191`) → lookup in the hardcoded `sequencias` dict
   (`main.py:40-45`) → if present, `get_similares_por_sequencia` scans `musica.seqs_famosas`
   (`main.py:203-223`), which came from CSV column 7 → paginated to 100; unknown sequences return
   `[]` (`main.py:190-197`).
4. **Static + API same origin** — the Flask process serves `static/index.html` at `/`
   (`main.py:101-103`), everything else under `static/` via `/<path:path>`
   (`main.py:109-112`), and the API on the same host; the three search controllers use
   `var apiUrl = ""` (`acordes.js:91`, `musica.js:12`, `sequencia.js:72`) so requests are relative
   to the page origin. The `RESTAPI` constant in `app.js:3-5` is not used.
5. **Client-side genre filter** — dropdown options come from the `GENEROS` constant (`app.js:6-58`),
   and the chosen value is appended verbatim as `generos=` to `/similares`; `/search` accepts the
   same parameter but the song typeahead never sends it.

---

## 6. Deploy and configuration

- `Dockerfile:1-12`: `python:3.9-slim`, `WORKDIR /app`, `pip install --no-cache-dir -r
  requirements.txt`, `COPY . .`, `EXPOSE 8080`, `CMD gunicorn --bind 0.0.0.0:8080 main:app`.
- `requirements.txt:4-5`: `Flask==3.1.3`, `gunicorn==23.0.0` only.
- `.dockerignore`: `.git`, `.venv`, `__pycache__`, `*.pyc`. `.gitignore`: `static/assets/vendor`,
  `.venv`, `*.pyc`, `__pycache__/`.
- The CSV path is relative (`main.py:49`), so the working directory must be the repo root (local)
  or `/app` (container).
- No environment variables, config files, database connection strings, Procfile, `app.yaml` or
  App Engine vendoring remain; ADR 0001 (`docs/adr/0001-local-only-docker-deploy.md:1-16`) records
  their removal and that no cloud target is chosen.
- ADR 0003 (`docs/adr/0003-lift-frontend-freeze.md:1-21`) records the removal of the previous
  "don't touch the AngularJS frontend" instruction and states the stack is unchanged.
- ADR 0002 (`docs/adr/0002-persist-custom-sequences.md:1-8`) is still the unfilled template:
  title placeholder plus a quoted instruction block and `[seu texto aqui]`.

---

## 7. Data pipeline in the repo (not invoked by the app)

Nothing in `main.py` or the frontend imports or executes these; they document how
`data/top/dataset_final.csv` and the other extracts were produced.

| File | Content |
|---|---|
| `scripts/DownloadAll.java` (+ compiled `.class`, `jsoup-1.8.3.jar`) | Jsoup crawler: reads artist page URLs, collects same-band links, writes them to `<input>_<n>.songs` shards of 25,000 links |
| `scripts/collect_song_list.sh` | `java -cp jsoup-1.8.3.jar:. DownloadAll <artists.txt>` |
| `scripts/download_band_names.sh`, `scripts/download_cifras.sh` | `curl` loops over URL lists; the latter writes into `cifras_erro/<band>/` |
| `scripts/cifra_parser.py` | Python 2, BeautifulSoup: extracts artist/song/key/chord sequence per saved HTML file |
| `scripts/generate_data_set.py` | Python 2: builds the 9-column rows; contains `get_famosas` (`:7-24`) with the same six sequences and the same id enumeration used in `main.py:40-45`; column assembly at `:89` |
| `scripts/parse_estilos.py`, `parse_artistas_estilos.py`, `add_estilos.py`, `add_estilos.R` | Genre/style scraping and joins (Python 2 `print` statements in the `.py` files) |
| `scripts/simplify_chords.R`, `normalize_chords.R`, `build-chords-transitions.R` | Transpose chords to scale degrees using `data/transposition_matrix2.csv` (referenced but not present in the repo) and build a chord-transition matrix from `data/top/chords-transitions-empty.csv` |
| `data/top/merge_datasets.R` | Joins a 4-column `dataset.csv` with `visualizacoes_pontos.csv` and writes `dataset_final.csv` with 5 columns (`ARTISTA, MUSICA, VISUALIZACOES, TOM, CIFRA`) — a different shape from the 9-column `dataset_final.csv` currently in the tree |
| `data/top/popularidade.R` | Reads `dataset_final.csv`, aggregates views per artist, filters one artist |

---

## 8. Documentation inventory

| File | State |
|---|---|
| `README.md` | Project description, stack summary, Docker and virtualenv run instructions (ports 8080 vs 5000), links to `CONTRIB.md` and `LICENSE` |
| `AGENTS.md` | Stack, run commands, `/generos` smoke check, three gotchas (CSV read once at startup, `json.dumps` not `jsonify`, check `docs/adr/` before deploy changes) |
| `CONTRIB.md` | Unmodified Google Cloud Platform sample boilerplate (CLA, "Contributing A New Sample App" naming `{product}-{app-name}-{language}`) |
| `docs/adr/0001`, `0003` | Written decision records (deploy; frontend freeze lifted) |
| `docs/adr/0002` | Template, unfilled |
| `docs/features/sequencias-customizadas/00-enunciado.md` | Full task statement (130 lines): custom chord sequences, DB persistence, full-stack, mandatory workflow, grading weights |
| `docs/features/sequencias-customizadas/01`–`04` | Templates with quoted instructions and bracketed placeholders; `04-test-report.md` states the regression requirement against `main.py:40-45` |

---

## 9. Verification log

Commands run against a local copy of this tree (Flask 3.1.3 in a throwaway venv, app started with
`main.app.run(host='127.0.0.1', port=5055)`, i.e. the same `main.py` code path):

| Command | Observed |
|---|---|
| `curl -i /generos` | `HTTP/1.1 200`, `Content-Type: text/html; charset=utf-8`, `Access-Control-Allow-Origin: *`, 665-byte JSON array |
| `curl /acordes` | 6,653 strings |
| `curl /musicas` | 67,585 objects, keys `id_artista, nome_artista, id_musica, nome_musica, genero, popularidade, tom, cifra, acordes, seqs_famosas, id_unico_musica, url` |
| `curl "/search?key=chico+buarque"` | 100 results (page size cap), first `chico-buarque_joao-maria` |
| `curl "/search?key=jo%C3%A3o"` | 100 results, accents matched (`João E Grazi`, `Menino João`) |
| `curl /search` (no `key`) | HTTP 500 |
| `curl "/search?key="` | 91 results, all with a double space in artist/title |
| `curl "/similares?acordes=C,G,Am,F"` | 100 results; first has `diferenca: []`, `intersecao: ["F","Am","G","C"]` |
| `curl "/similares?sequencia=C,G,Am,F"` | 100 results, objects without `diferenca` |
| `curl "/similares?sequencia=X,Y,Z"` | `[]` |
| `curl "/similares?id_unico_musica=guns-n-roses_sweet-child-omine"` | 100 results, selected song absent |
| `curl "/similares?acordes=C,G,Am,F&generos=Rock"` | 100 results, all `genero == "Rock"` |
| `curl "/similares?acordes=C,G&generos=Nope"` | `[]` |
| `curl "/similares?acordes=C&pagina=x"` | HTTP 500 |
| `curl "/similares?acordes=C&pagina=0"` | `[]` |
| `curl /musica/guns-n-roses_sweet-child-omine/` | one object; `id_musica` is `sweet-child-omine` as stored in the CSV |
| `curl /musica/gusttavo-lima_dna/` | `"nome_musica": "D"` (global `NA` strip) |
| `curl /musica/nope/` | HTTP 500 |
| `curl /` | 200 `text/html` |
| `curl /assets/js/app.js` | 200 `text/javascript` |
| `curl /nope.html` | 404 |

Offline checks run against the CSV with plain Python (replicating `main.py`'s parsing, without
Flask) produced the counts in [§3.1](#31-datatopdataset_finalcsv): 67,586 lines / 67,585 loaded,
52 genres, 6,653 chord tokens, 8,141 empty cifras, sequence-tag frequencies
`1:296, 0:199, 4:7, 3:5, 2:4, 5:3`.

---

## 10. Code/comment/doc divergences present today

Listed because they describe what the tree contains, not as recommendations.

| Location | Comment or doc says | Code actually does |
|---|---|---|
| `main.py:149-153` vs `main.py:154-156` | `/musicas` is paginated, 100 per page, accepts `pagina` | returns all 67,585 songs, ignores `pagina` |
| `main.py:262` vs `main.py:263` | results ordered by smallest difference, largest intersection and largest popularity | sort key is `(len(diferenca), -len(intersecao))`, no popularity term |
| `docs/features/.../01-research.md:26-33` and `00-enunciado.md:26-31` | `#/porsequencia` shows 4 hardcoded sequences while the backend has 6 | matches the code (`sequencia.js:2-37` has 4; `main.py:40-45` has 6) |
| `data/top/merge_datasets.R:1-11` | writes `dataset_final.csv` | writes 5 columns; the tracked CSV has 9 |
| `static/bower.json:23-25` | declares `ng-material-floating-button` | no reference to it in HTML/JS; vendor dir gitignored and absent |
| `AGENTS.md:12-15` vs `docs/adr/0003` | frontend "legacy, no plan to modernize" | ADR 0003 records that touching it is allowed; both statements coexist in the tree |
| `.playground:1-12` | App Engine Flask sample, `show_files` lists `app.yaml`/`appengine_config.py` | those files are not in the tree (removed in `ff57dc5`) |
| `main.py:40-45` vs `scripts/generate_data_set.py:7` | backend sequence keys `BmGDA, CGAmF, EmG, CA7DmG7, GmF, CC7FFm` | the generator lowercases and uses the same six strings with `;` separators; ids line up 0–5 |

---

## 11. Git context for the current state

Relevant commits (most recent first): `fb97001` docs; `e03bc62` "Remove restrição de não tocar no
frontend legado"; `3b8ec59` adds the feature statement/templates; `d834fb7` adds `AGENTS.md` and
shortens `README.md`; `ff57dc5` upgrades Flask/gunicorn and replaces App Engine/Heroku artifacts
with the Dockerfile (deletes `app.yaml`, `appengine_config.py`, `Procfile`, `lib/`); `249bdc9`
ports `main.py` off Python 2 syntax, fixes `musicas.values` → `musicas.values()`, and changes the
three search controllers from a dead Heroku API URL to a relative URL. `249bdc9` and `ff57dc5` are
the two commits that produced the backend and deploy shape described above; the six-sequence
dict and the `SEQ_FAMOSA`-based matching predate them (`git log -- main.py` reaches back to
`aad53ae`/`56f1378`, which introduced the "global issues" refactors).
