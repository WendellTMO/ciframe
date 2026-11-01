# coding: utf-8
"""Regressão das 6 sequências iniciais contra a coluna SEQ_FAMOSA.

Roda a `main.casa_com_sequencia` sobre as músicas carregadas pelo `main.py` e
compara o resultado com a coluna precomputada do CSV, pela posição na lista
`SEQUENCIAS_INICIAIS` (0 a 5), nunca pelo id do banco. Também chama o
`/similares` pelo `test_client`, juntando todas as páginas, para cobrir o
caminho inteiro da busca (handler, banco e `casa_com_sequencia`).

Rodar da raiz do repositório, dentro do Docker (o `main.py` importa o Flask):

    docker run --rm ciframe python scripts/regressao_sequencias.py
"""
import json
import os
import sys

REPO_ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
os.chdir(REPO_ROOT)          # main.py abre o CSV por caminho relativo
sys.path.insert(0, REPO_ROOT)

import main  # noqa: E402  (import depois do ajuste de CWD e sys.path)
import sequencias_db  # noqa: E402
from sequencias_db import SEQUENCIAS_INICIAIS, normaliza_acorde  # noqa: E402

ESPERADO = [199, 296, 4, 5, 7, 3]


def check_normalizacao():
    """A contagem sozinha não distingue as duas normalizações."""
    assert normaliza_acorde('bm') == 'Bm'
    assert normaliza_acorde('am') == 'Am'
    assert normaliza_acorde('C') == 'C'
    assert normaliza_acorde('C7M') != normaliza_acorde('C7m')
    assert normaliza_acorde('Gm') != normaliza_acorde('GM')
    print('normalizacao: ok (bm->Bm, am->Am, C7M!=C7m, Gm!=GM)')


def check_am_a():
    """A comparação por texto casaria Am;A com uma música que só tem Am."""
    musica = main.musicas['oasis_the-swamp-song']
    assert set(musica.cifra) == {'Am'}, musica.cifra
    assert not main.casa_com_sequencia(musica.cifra, ['Am', 'A'])
    print('Am;A nao casa com oasis_the-swamp-song (cifra Am;Am): ok')


def check_init_db():
    """Simula um reinício com o banco já criado."""
    sequencias_db.init_db()
    sequencias = sequencias_db.listar()
    assert len(sequencias) == 6, sequencias
    print('init_db x2: ok (listar continua com 6)')


def column_ids(musica):
    return {int(tag) for tag in musica.seqs_famosas if tag.isdigit()}


def busca_http(client, acordes):
    """Chama /similares juntando as páginas até vir uma vazia."""
    encontrados = set()
    pagina = 1
    while True:
        resposta = client.get('/similares', query_string={
            'sequencia': ','.join(acordes),
            'pagina': str(pagina),
        })
        assert resposta.status_code == 200, resposta.status_code
        musicas = json.loads(resposta.get_data(as_text=True))
        if not musicas:
            break
        encontrados.update(musica['id_unico_musica'] for musica in musicas)
        pagina += 1
    return encontrados


def compara(client):
    musicas = list(main.musicas.values())
    print('musicas carregadas: %d' % len(musicas))
    print()

    cabecalho = '%-3s %-16s %8s %8s %8s %8s %8s' % (
        'pos', 'sequencia', 'coluna', 'regra', 'http',
        'd_regra', 'd_http')
    print(cabecalho)
    print('-' * len(cabecalho))

    total_so_regra = 0
    total_so_http = 0
    for posicao, acordes in enumerate(SEQUENCIAS_INICIAIS):
        coluna = {m.id_unico_musica for m in musicas
                  if posicao in column_ids(m)}
        regra = {m.id_unico_musica for m in musicas
                 if main.casa_com_sequencia(m.cifra, acordes)}
        http = busca_http(client, acordes)
        so_regra = coluna ^ regra
        so_http = coluna ^ http
        total_so_regra += len(so_regra)
        total_so_http += len(so_http)

        print('%-3d %-16s %8d %8d %8d %8d %8d' % (
            posicao, ' '.join(acordes), len(coluna), len(regra), len(http),
            len(so_regra), len(so_http)))

        assert len(coluna) == ESPERADO[posicao], (
            'posicao %d: coluna=%d, esperado=%d'
            % (posicao, len(coluna), ESPERADO[posicao]))
        assert len(regra) == ESPERADO[posicao], (
            'posicao %d: regra=%d, esperado=%d'
            % (posicao, len(regra), ESPERADO[posicao]))
        assert len(http) == ESPERADO[posicao], (
            'posicao %d: http=%d, esperado=%d'
            % (posicao, len(http), ESPERADO[posicao]))
        assert coluna == regra, (
            'posicao %d: funcao com %d diferencas, por exemplo %s'
            % (posicao, len(so_regra), sorted(so_regra)[:5]))
        assert coluna == http, (
            'posicao %d: /similares com %d diferencas, por exemplo %s'
            % (posicao, len(so_http), sorted(so_http)[:5]))

    print()
    print('diferencas da funcao: %d' % total_so_regra)
    print('diferencas do /similares: %d' % total_so_http)
    assert total_so_regra == 0 and total_so_http == 0


def check_busca_minuscula(client):
    """A busca normaliza a primeira letra: bm,g,d,a acha o mesmo que Bm,G,D,A."""
    minuscula = busca_http(client, ['bm', 'g', 'd', 'a'])
    maiuscula = busca_http(client, SEQUENCIAS_INICIAIS[0])
    assert minuscula == maiuscula, len(minuscula ^ maiuscula)
    assert len(minuscula) == ESPERADO[0], len(minuscula)
    print('bm,g,d,a == Bm,G,D,A: ok (%d musicas)' % len(minuscula))


def check_post_sequencias(client):
    """Testa os casos do POST /sequencias: 400, 409, normalização GM/Gm e D7+,G7+."""
    # 1. Erro 400: corpo vazio / não JSON / lista inválida / acordes vazios / ; ou ,
    r = client.post('/sequencias', data='nao-json')
    assert r.status_code == 400

    r = client.post('/sequencias', json={'acordes': 'nao-lista'})
    assert r.status_code == 400

    r = client.post('/sequencias', json={})
    assert r.status_code == 400

    r = client.post('/sequencias', json={'acordes': []})
    assert r.status_code == 400

    r = client.post('/sequencias', json={'acordes': [' ']})
    assert r.status_code == 400

    r = client.post('/sequencias', json={'acordes': ['C', 'D;E']})
    assert r.status_code == 400

    print('POST /sequencias validacoes 400: ok')

    # 2. Conflito 409 para sequência já existente (ex: C, G, Am, F)
    r = client.post('/sequencias', json={'acordes': ['C', 'G', 'Am', 'F']})
    assert r.status_code == 409
    data = json.loads(r.get_data(as_text=True))
    assert 'id' in data
    print('POST /sequencias 409 existente: ok')

    # 3. GM e Gm diferentes
    r1 = client.post('/sequencias', json={'acordes': ['Gm', 'F']})
    r2 = client.post('/sequencias', json={'acordes': ['GM', 'F']})
    assert r1.status_code in (201, 409)
    assert r2.status_code in (201, 409)
    # Se GM for normalizado para Gm, deve dar conflito com Gm se inserido depois,
    # mas o normalizador define primeira maiúscula e resto igual: 'GM'[0].upper() + 'GM'[1:] -> 'GM' != 'Gm'
    d1 = json.loads(client.get('/sequencias').get_data(as_text=True))
    gm_encontrado = any(s['acordes'] == ['Gm', 'F'] for s in d1)
    gm_maiusculo_encontrado = any(s['acordes'] == ['GM', 'F'] for s in d1)
    assert gm_encontrado and gm_maiusculo_encontrado
    print('GM e Gm distintos: ok')

    # 4. Sequência D7+, G7+ com 3 músicas esperadas
    r = client.post('/sequencias', json={'acordes': ['D7+', 'G7+']})
    assert r.status_code == 201
    criada = json.loads(r.get_data(as_text=True))
    http_res = busca_http(client, criada['acordes'])
    assert len(http_res) == 3, len(http_res)
    print('POST /sequencias D7+,G7+ com 3 musicas: ok')


if __name__ == '__main__':
    check_init_db()
    check_normalizacao()
    check_am_a()
    client = main.app.test_client()
    compara(client)
    check_busca_minuscula(client)
    check_post_sequencias(client)
    print('regressao: ok (199, 296, 4, 5, 7, 3; 0 diferencas na funcao e no /similares)')
