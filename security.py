"""
Camada de segurança do ConectaServ:
- senha com PBKDF2 (compatível com hashes SHA-256 antigos)
- sessão de API com token opaco (não envia senha)
- limite de tentativas por IP
- validação de senha
"""

import hashlib
import secrets
import time
from collections import defaultdict
from datetime import datetime, timedelta

from werkzeug.security import check_password_hash, generate_password_hash

from database.database import criar_conexao

_tentativas = defaultdict(list)
LIMITE_JANELA = 60
LIMITE_MAX = 20


def hash_password(password):
    return generate_password_hash(password or '', method='pbkdf2:sha256', salt_length=16)


def verificar_senha(guardado, senha):
    if not guardado or senha is None:
        return False
    if guardado.startswith(('pbkdf2:', 'scrypt:', 'argon2:')):
        try:
            return check_password_hash(guardado, senha)
        except ValueError:
            return False
    return secrets.compare_digest(guardado, hashlib.sha256(senha.encode('utf-8')).hexdigest())


def senha_valida(senha):
    senha = senha or ''
    if len(senha) < 6:
        return False, 'A senha precisa ter no mínimo 6 caracteres.'
    if senha.strip() != senha or ' ' in senha[:1]:
        return False, 'Evite espaços no início da senha.'
    return True, ''


def limitar_requisicao(chave, maximo=LIMITE_MAX, janela=LIMITE_JANELA):
    agora = time.time()
    lista = [t for t in _tentativas[chave] if agora - t < janela]
    if len(lista) >= maximo:
        _tentativas[chave] = lista
        return False
    lista.append(agora)
    _tentativas[chave] = lista
    return True


def garantir_tabela_sessoes():
    conn = criar_conexao()
    cursor = conn.cursor()
    cursor.execute('''
        CREATE TABLE IF NOT EXISTS api_sessoes (
            token TEXT PRIMARY KEY,
            user_id INTEGER NOT NULL,
            criado_em TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
            expira_em TIMESTAMP NOT NULL,
            revogado INTEGER DEFAULT 0,
            FOREIGN KEY (user_id) REFERENCES users(id)
        )
    ''')
    conn.commit()
    conn.close()


def criar_sessao_api(user_id, horas=24):
    garantir_tabela_sessoes()
    token = secrets.token_urlsafe(32)
    expira = datetime.utcnow() + timedelta(hours=horas)
    conn = criar_conexao()
    cursor = conn.cursor()
    cursor.execute(
        'INSERT INTO api_sessoes (token, user_id, expira_em) VALUES (?, ?, ?)',
        (token, user_id, expira.isoformat(sep=' ')),
    )
    conn.commit()
    conn.close()
    return token


def usuario_por_token(token):
    if not token:
        return None
    garantir_tabela_sessoes()
    conn = criar_conexao()
    cursor = conn.cursor()
    cursor.execute(
        '''SELECT s.user_id, u.role, u.ativo
           FROM api_sessoes s
           JOIN users u ON u.id = s.user_id
           WHERE s.token = ? AND s.revogado = 0 AND s.expira_em > ?''',
        (token, datetime.utcnow().isoformat(sep=' ')),
    )
    row = cursor.fetchone()
    conn.close()
    if not row or not row['ativo']:
        return None
    return {'user_id': row['user_id'], 'role': row['role']}
