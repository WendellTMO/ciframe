# coding: utf-8
"""Apply the SEQ_FAMOSA rule over the cifras loaded by main.py and compare the
result with the values stored in the CSV (musica.seqs_famosas).

Run from the repository root:

    python research/seq_famosa_rule.py          # rule over the cifra main.py loads
    python research/seq_famosa_rule.py --raw    # also compare with the raw CSV column

Requires the backend dependencies (Flask), because main.py is imported so that
the CSV is parsed by exactly the same code path the app uses at startup.
"""
import os
import sys
from collections import Counter

REPO_ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
os.chdir(REPO_ROOT)          # main.py opens data/top/dataset_final.csv by relative path
sys.path.insert(0, REPO_ROOT)

import main  # noqa: E402  (import after sys.path/CWD setup)

# Sequences from scripts/generate_data_set.py:8, ';'-separated. The ids are
# positional and match main.sequencias (main.py:40-45). `rule_matches` applies
# the implemented normalization (first character uppercase, rest preserved).
SEQS = {
    0: 'bm;g;d;a',
    1: 'c;g;am;f',
    2: 'em;g',
    3: 'c;a7;dm;g7',
    4: 'gm;f',
    5: 'c;c7;f;fm',
}

# The hardcoded API keys in main.py:40-45, keyed by the same ids.
API_KEYS = {0: 'BmGDA', 1: 'CGAmF', 2: 'EmG', 3: 'CA7DmG7', 4: 'GmF', 5: 'CC7FFm'}

CSV_PATH = os.path.join(REPO_ROOT, 'data', 'top', 'dataset_final.csv')


def normaliza_acorde(token):
    """First character uppercase, the rest preserved.

    This is the normalization of the implemented rule: `c` and `C` are the same
    chord, but `C7M` and `C7m` are not, and neither are `Gm` and `GM`. The
    legacy `get_famosas` lowercased the whole token and conflated those pairs.
    """
    return token[0].upper() + token[1:] if token else token


def check_normalizacao():
    """Guards the normalization decision; the six counts alone do not."""
    assert normaliza_acorde('bm') == 'Bm'
    assert normaliza_acorde('am') == 'Am'
    assert normaliza_acorde('C') == 'C'
    assert normaliza_acorde('C7M') != normaliza_acorde('C7m')
    assert normaliza_acorde('Gm') != normaliza_acorde('GM')
    print('normalizacao: ok (bm->Bm, am->Am, C7M!=C7m, Gm!=GM)')


def rule_matches(cifra_tokens, seq):
    """True when the sequence `seq` is considered present in `cifra_tokens`.

    Two conditions, both from scripts/generate_data_set.py:13-21:
      1. the sequence appears as a contiguous run (substring of the joined list);
      2. every token of the song belongs to the sequence vocabulary.
    `seq` may come in any root case (`bm;g;d;a` works); both sides are normalized
    with `normaliza_acorde`.
    """
    toks = [normaliza_acorde(t) for t in cifra_tokens]
    seq_toks = [normaliza_acorde(t) for t in seq.split(';')]
    key = ';'.join(seq_toks)
    if key not in ';'.join(toks):
        return False
    return all(t in seq_toks for t in toks)


def _tokens(cifra_tokens):
    return [t.lower() for t in cifra_tokens]


def variant_contiguity(cifra_tokens, seq):
    """Condition 1 alone (contiguous run, no vocabulary restriction)."""
    return seq in ';'.join(_tokens(cifra_tokens))


def variant_vocabulary(cifra_tokens, seq):
    """Condition 2 alone (closed vocabulary, order ignored)."""
    toks = _tokens(cifra_tokens)
    return bool(toks) and all(t in seq.split(';') for t in toks)


def variant_subsequence(cifra_tokens, seq):
    """In-order subsequence + closed vocabulary (i.e. gaps allowed)."""
    toks = _tokens(cifra_tokens)
    if not toks or not all(t in seq.split(';') for t in toks):
        return False
    it = iter(toks)
    return all(any(x == t for x in it) for t in seq.split(';'))



def column_ids(musica):
    return {int(t) for t in musica.seqs_famosas if t.isdigit()}


def table(rows, title):
    print(title)
    header = '%-2s %-12s %8s %8s %8s %12s %12s' % (
        'id', 'sequence', 'column', 'rule', 'both', 'only column', 'only rule')
    print(header)
    print('-' * len(header))
    for r in rows:
        print('%-2d %-12s %8d %8d %8d %12d %12d' % (
            r['id'], r['chords'], r['column'], r['rule'], r['both'],
            len(r['only_column']), len(r['only_rule'])))
    print()


def compare(songs, rule_fn, label):
    rows = []
    for id_seq, seq in sorted(SEQS.items()):
        col = {m.id_unico_musica for m in songs if id_seq in column_ids(m)}
        rule = {m.id_unico_musica for m in songs if rule_fn(m, seq)}
        rows.append({
            'id': id_seq,
            'chords': ' '.join(seq.split(';')),
            'column': len(col),
            'rule': len(rule),
            'both': len(col & rule),
            'only_column': sorted(col - rule),
            'only_rule': sorted(rule - col),
        })
    table(rows, label)
    print('total column-only: %d' % sum(len(r['only_column']) for r in rows))
    print('total rule-only  : %d' % sum(len(r['only_rule']) for r in rows))
    print()
    return rows


def report():
    check_normalizacao()

    for id_seq, key in API_KEYS.items():
        assert main.sequencias[key] == id_seq, (key, main.sequencias[key])

    songs = list(main.musicas.values())
    print('songs loaded by main.py: %d' % len(songs))
    print()

    # Rule over the cifra exactly as main.py loads it (post limpa_cifra).
    loaded = compare(songs, lambda m, s: rule_matches(m.cifra, s), 'rule over musica.cifra (loaded)')

    # Cross-checks: exclusivity of the six rules and total tagged songs.
    multi = [m.id_unico_musica for m in songs
             if sum(1 for s in SEQS.values() if rule_matches(m.cifra, s)) > 1]
    tagged = [m.id_unico_musica for m in songs if column_ids(m)]
    print('songs matching 2+ rules: %d' % len(multi))
    print('songs with any stored tag: %d' % len(tagged))
    print('stored seqs_famosas tokens: %s' % sorted(
        Counter(t for m in songs for t in m.seqs_famosas).items(), key=lambda x: -x[1]))
    print()

    print('candidate rules vs. stored column')
    header = '%-2s %-12s %7s %11s %10s %10s %11s %11s' % (
        'id', 'sequence', 'column', 'contiguity', 'vocab only', 'subseq+voc', 'subseq xor', 'implemented')
    print(header)
    print('-' * len(header))
    for id_seq, seq in sorted(SEQS.items()):
        col = {m.id_unico_musica for m in songs if id_seq in column_ids(m)}
        sub = {m.id_unico_musica for m in songs if variant_subsequence(m.cifra, seq)}
        print('%-2d %-12s %7d %11d %10d %10d %11d %11d' % (
            id_seq, ' '.join(seq.split(';')), len(col),
            sum(1 for m in songs if variant_contiguity(m.cifra, seq)),
            sum(1 for m in songs if variant_vocabulary(m.cifra, seq)),
            len(sub), len(col ^ sub),
            sum(1 for m in songs if rule_matches(m.cifra, seq))))
    print()

    if '--raw' in sys.argv:
        raw = {}
        with open(CSV_PATH) as f:
            f.readline()                      # main.py:50 skips the first line
            for line in f:
                p = line.rstrip('\n').split(',')
                if len(p) == 9:
                    raw[(p[0], p[1])] = p[8]
        print('raw CSV column 8 indexed by id: %d rows' % len(raw))
        print()
        compare(songs, lambda m, s: rule_matches(raw.get((m.id_artista, m.id_musica), '').split(';'), s),
                'rule over raw CSV column 8')
        diff = [m.id_unico_musica for m in songs
                if any(rule_matches(m.cifra, s) != rule_matches(
                    raw.get((m.id_artista, m.id_musica), '').split(';'), s) for s in SEQS.values())]
        print('songs where loaded-rule and raw-rule disagree: %d' % len(diff))
        for uid in diff[:10]:
            m = main.musicas[uid]
            print('  %-40s loaded=%s raw=%s' % (uid, m.cifra[:8],
                  raw.get((m.id_artista, m.id_musica), '').split(';')[:8]))

        # How the raw token list differs from the list main.py loads.
        na = blank = pipe = other = 0
        for m in songs:
            r = raw.get((m.id_artista, m.id_musica), '')
            toks = r.split(';')
            if r == 'NA':
                na += 1
            elif any(t.strip() == '' for t in toks):
                blank += 1
            elif '|' in r:
                pipe += 1
            elif toks != m.cifra:
                other += 1
        print()
        print('raw column 8 vs musica.cifra token lists:')
        print('  raw == NA (loaded []):                 %d' % na)
        print('  raw with blank chunk (;; or trailing): %d' % blank)
        print('  raw containing "|":                    %d' % pipe)
        print('  other token-level difference:          %d' % other)
        print('  total songs whose lists differ:        %d' % (na + blank + pipe + other))

    return loaded


if __name__ == '__main__':
    report()
