# coding: utf-8
"""Catálogo de sequências de acordes, persistido em SQLite."""
import os
import sqlite3

DB_DIR = os.path.join(os.path.dirname(os.path.abspath(__file__)), 'data', 'db')
DB_PATH = os.path.join(DB_DIR, 'sequencias.sqlite')

# Ordem de scripts/generate_data_set.py:8, já normalizada. A posição na lista
# (0 a 5) é o número que a coluna SEQ_FAMOSA usa; o id do banco começa em 1 e
# não entra nessa comparação.
SEQUENCIAS_INICIAIS = [
    ['Bm', 'G', 'D', 'A'],
    ['C', 'G', 'Am', 'F'],
    ['Em', 'G'],
    ['C', 'A7', 'Dm', 'G7'],
    ['Gm', 'F'],
    ['C', 'C7', 'F', 'Fm'],
]


def normaliza_acorde(acorde):
    """Deixa a primeira letra maiúscula e mantém o resto."""
    return acorde[0].upper() + acorde[1:] if acorde else acorde


def _normaliza(acordes):
    return [normaliza_acorde(acorde.strip())
            for acorde in acordes if acorde.strip()]


def _serializa(acordes):
    return ';'.join(_normaliza(acordes))


def _desserializa(acordes):
    return acordes.split(';') if acordes else []


def _conecta():
    return sqlite3.connect(DB_PATH)


def init_db():
    """Cria a pasta e a tabela, se faltarem, e semeia as 6 sequências."""
    os.makedirs(DB_DIR, exist_ok=True)
    conexao = _conecta()
    try:
        conexao.execute(
            'CREATE TABLE IF NOT EXISTS sequencias ('
            'id INTEGER PRIMARY KEY, '
            'acordes TEXT NOT NULL UNIQUE)'
        )
        conexao.executemany(
            'INSERT INTO sequencias (acordes) VALUES (?) '
            'ON CONFLICT (acordes) DO NOTHING',
            [(_serializa(acordes),) for acordes in SEQUENCIAS_INICIAIS],
        )
        conexao.commit()
    finally:
        conexao.close()


def listar():
    """Sequências ordenadas por id, cada uma com id e a lista de acordes."""
    conexao = _conecta()
    try:
        linhas = conexao.execute(
            'SELECT id, acordes FROM sequencias ORDER BY id'
        ).fetchall()
    finally:
        conexao.close()
    return [{'id': id_, 'acordes': _desserializa(acordes)}
            for id_, acordes in linhas]


def buscar(acordes):
    """Devolve id e acordes da sequência, ou None se ela não existir."""
    conexao = _conecta()
    try:
        linha = conexao.execute(
            'SELECT id, acordes FROM sequencias WHERE acordes = ?',
            (_serializa(acordes),),
        ).fetchone()
    finally:
        conexao.close()
    if linha is None:
        return None
    return {'id': linha[0], 'acordes': _desserializa(linha[1])}


def criar(acordes):
    """Grava a sequência normalizada e devolve o id e a lista de acordes."""
    normalizados = _normaliza(acordes)
    if not normalizados:
        raise ValueError('lista de acordes vazia')
    conexao = _conecta()
    try:
        cursor = conexao.execute(
            'INSERT INTO sequencias (acordes) VALUES (?)',
            (';'.join(normalizados),),
        )
        novo_id = cursor.lastrowid
        conexao.commit()
    finally:
        conexao.close()
    return {'id': novo_id, 'acordes': normalizados}
