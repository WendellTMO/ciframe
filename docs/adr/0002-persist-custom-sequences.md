# Persist the custom sequence catalog in SQLite and compute matches at query time

Sequence search only worked for the six progressions hardcoded in `main.py:40-45`. Each
song was linked to a sequence by the precomputed `SEQ_FAMOSA` column in the CSV, generated
by `get_famosas` in `scripts/generate_data_set.py`. A precomputed column cannot cover
sequences registered after the CSV was built, so letting visitors add new sequences meant
moving the catalog out of the code and computing the match at request time.

We moved the catalog into a single SQLite table, using the `sqlite3` module that already
ships with Python, and seeded it with the six existing sequences. Matching now runs on
`musica.cifra` with the same rule `get_famosas` used: the sequence must appear in order
with no chord in between, and every chord of the song must belong to the sequence. Songs
and genres still come from the CSV in memory.

There are two differences from `get_famosas`. The first is normalization: the first
character of each chord is uppercased and the rest is preserved. `get_famosas` lowercased
the whole token, which merged different qualities such as `C7M` (major seventh) and `C7m`
(minor seventh) and made `GM;F` collide with the `Gm;F` entry. Now `c` and `C` are the same
chord, while `C7M` and `C7m` stay distinct. The second is that the comparison runs chord by
chord on the token list. `get_famosas` searched the joined text, so `Am;A` would match a
song that only has `Am`, because the text `Am;A` occurs inside `Am;Am`.

We kept the rule because it reproduced `SEQ_FAMOSA` with 0 differences across all 67,585
songs, so the six original sequences keep their results; the counts are 199/296/4/5/7/3
with or without the two changes. We rejected keeping the six on the CSV tag with a looser rule
for new sequences, because the same sequence would then return 199 or 382 songs depending
on how it entered the catalog.

The database file lives in `data/db/` and is only kept across container recreation when
the container runs with a volume (`-v ciframe-seq:/app/data/db`). `SEQ_FAMOSA` stays in
the CSV but is no longer read. Each sequence search still scans every song. Checking first
whether the song's chords belong to the sequence, and stopping at the first one that does
not, keeps it at about 55 ms in local tests.
