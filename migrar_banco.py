"""
Migra dados do banco antigo (Downloads) para o banco atual (Desktop/HeidiSQL).
Faz backup antes de alterar o banco atual.
"""
import os
import shutil
import sqlite3
from datetime import datetime

BANCO_ATUAL = os.path.join(os.path.dirname(__file__), 'database', 'conecta_serv.db')
BANCO_ANTIGO = r'c:\Users\Gabriel_0)\Downloads\conecta_servPJ1\conecta_servPJ1\database\conecta_serv.db'
BACKUP_ANTIGO_ALT = r'c:\Users\Gabriel_0)\Downloads\conecta_servPJ1\conecta_servPJ1\database\conecta_serv.db.backup-antigo'

def escolher_banco_antigo():
    if os.path.exists(BANCO_ANTIGO):
        return BANCO_ANTIGO
    if os.path.exists(BACKUP_ANTIGO_ALT):
        return BACKUP_ANTIGO_ALT
    raise FileNotFoundError('Banco antigo nao encontrado em Downloads.')

def normalizar_email(email):
    return (email or '').strip().lower()

def normalizar_doc(valor):
    import re
    return re.sub(r'\D', '', valor or '')

def listar_tabelas(conn):
    c = conn.cursor()
    c.execute("SELECT name FROM sqlite_master WHERE type='table' AND name NOT LIKE 'sqlite_%'")
    return [r[0] for r in c.fetchall()]

def contar(conn):
    info = {}
    for t in listar_tabelas(conn):
        try:
            info[t] = conn.execute(f'SELECT COUNT(*) FROM {t}').fetchone()[0]
        except sqlite3.Error:
            info[t] = -1
    return info

def backup_banco(path):
    stamp = datetime.now().strftime('%Y%m%d_%H%M%S')
    dest = path + f'.backup-antes-migracao-{stamp}'
    shutil.copy2(path, dest)
    return dest

def migrar():
    origem_path = escolher_banco_antigo()
    destino_path = BANCO_ATUAL

    print('Banco ANTIGO:', origem_path)
    print('Banco ATUAL :', destino_path)

    backup = backup_banco(destino_path)
    print('Backup criado:', backup)

    origem = sqlite3.connect(origem_path)
    origem.row_factory = sqlite3.Row
    destino = sqlite3.connect(destino_path, timeout=120)
    destino.row_factory = sqlite3.Row

    for conn in (origem, destino):
        conn.execute('PRAGMA journal_mode=WAL')
        conn.execute('PRAGMA busy_timeout=60000')

    o = origem.cursor()
    d = destino.cursor()
    relatorio = []

    # --- USERS ---
    emails_destino = {normalizar_email(r['email']) for r in d.execute('SELECT email FROM users')}
    mapa_user_id = {}  # id_antigo -> id_novo

    for row in o.execute('SELECT * FROM users ORDER BY id'):
        email = normalizar_email(row['email'])
        if email in emails_destino:
            existente = d.execute('SELECT id FROM users WHERE LOWER(TRIM(email))=?', (email,)).fetchone()
            mapa_user_id[row['id']] = existente['id']
            relatorio.append(f'users: email {email} ja existe (id {existente["id"]})')
            continue

        cols = [k for k in row.keys() if k != 'id']
        placeholders = ','.join('?' * len(cols))
        vals = [row[c] for c in cols]
        try:
            d.execute(f'INSERT INTO users ({",".join(cols)}) VALUES ({placeholders})', vals)
            novo_id = d.lastrowid
            mapa_user_id[row['id']] = novo_id
            emails_destino.add(email)
            relatorio.append(f'users: importado {email} id {row["id"]} -> {novo_id}')
        except sqlite3.IntegrityError as e:
            relatorio.append(f'users: pulado {email} ({e})')

    # --- EMPRESAS ---
    cnpjs_destino = set()
    for r in d.execute('SELECT cnpj FROM empresas WHERE cnpj IS NOT NULL'):
        cnpjs_destino.add(normalizar_doc(r['cnpj']))

    for row in o.execute('SELECT * FROM empresas ORDER BY id'):
        uid_antigo = row['user_id']
        uid_novo = mapa_user_id.get(uid_antigo)
        if not uid_novo:
            relatorio.append(f'empresas: pulado id {row["id"]} (user_id {uid_antigo} sem mapeamento)')
            continue

        doc = normalizar_doc(row['cnpj'])
        if doc and doc in cnpjs_destino:
            relatorio.append(f'empresas: CNPJ {row["cnpj"]} ja existe no destino')
            continue

        email_emp = normalizar_email(row['email']) if 'email' in row.keys() and row['email'] else None
        if email_emp:
            dup = d.execute('SELECT id FROM empresas WHERE LOWER(TRIM(email))=?', (email_emp,)).fetchone()
            if dup:
                relatorio.append(f'empresas: email {email_emp} ja em empresas id {dup["id"]}')
                continue

        cols = [k for k in row.keys() if k != 'id']
        data = dict(row)
        data['user_id'] = uid_novo
        vals = [data[c] for c in cols]
        placeholders = ','.join('?' * len(cols))
        try:
            d.execute(f'INSERT INTO empresas ({",".join(cols)}) VALUES ({placeholders})', vals)
            if doc:
                cnpjs_destino.add(doc)
            relatorio.append(f'empresas: importada {row["nome_empresa"]} (user {uid_novo})')
        except sqlite3.IntegrityError as e:
            relatorio.append(f'empresas: pulado {row["nome_empresa"]} ({e})')

    # Mapear empresa_id antigo -> novo por CNPJ/email
    mapa_empresa_id = {}
    for row_o in o.execute('SELECT id, cnpj, email FROM empresas'):
        doc = normalizar_doc(row_o['cnpj'])
        em = normalizar_email(row_o['email']) if row_o['email'] else ''
        for row_d in d.execute('SELECT id, cnpj, email FROM empresas'):
            if doc and normalizar_doc(row_d['cnpj']) == doc:
                mapa_empresa_id[row_o['id']] = row_d['id']
                break
            if em and normalizar_email(row_d['email']) == em:
                mapa_empresa_id[row_o['id']] = row_d['id']
                break

    mapa_freelancer_id = {}

    # --- FREELANCERS ---
    for row in o.execute('SELECT * FROM freelancers ORDER BY id'):
        uid_novo = mapa_user_id.get(row['user_id'])
        if not uid_novo:
            relatorio.append(f'freelancers: pulado id {row["id"]}')
            continue
        existente = d.execute('SELECT id FROM freelancers WHERE user_id=?', (uid_novo,)).fetchone()
        if existente:
            mapa_freelancer_id[row['id']] = existente['id']
            continue

        cols = [k for k in row.keys() if k != 'id']
        data = dict(row)
        data['user_id'] = uid_novo
        vals = [data[c] for c in cols]
        try:
            d.execute(f'INSERT INTO freelancers ({",".join(cols)}) VALUES ({",".join("?"*len(cols))})', vals)
            mapa_freelancer_id[row['id']] = d.lastrowid
            relatorio.append(f'freelancers: importado {row["nome_completo"]}')
        except sqlite3.IntegrityError as e:
            relatorio.append(f'freelancers: pulado {row["nome_completo"]} ({e})')

    # --- PROJETOS ---
    for row in o.execute('SELECT * FROM projetos ORDER BY id'):
        eid = mapa_empresa_id.get(row['empresa_id'])
        if not eid:
            relatorio.append(f'projetos: pulado {row["titulo"]} (empresa_id {row["empresa_id"]})')
            continue
        cols = [k for k in row.keys() if k != 'id']
        data = dict(row)
        data['empresa_id'] = eid
        try:
            d.execute(f'INSERT INTO projetos ({",".join(cols)}) VALUES ({",".join("?"*len(cols))})', [data[c] for c in cols])
            relatorio.append(f'projetos: importado {row["titulo"]}')
        except sqlite3.IntegrityError as e:
            relatorio.append(f'projetos: pulado {row["titulo"]} ({e})')

    mapa_projeto_id = {}
    for row_o in o.execute('SELECT id, titulo, empresa_id FROM projetos'):
        eid = mapa_empresa_id.get(row_o['empresa_id'])
        if eid:
            r = d.execute('SELECT id FROM projetos WHERE titulo=? AND empresa_id=?', (row_o['titulo'], eid)).fetchone()
            if r:
                mapa_projeto_id[row_o['id']] = r['id']

    # --- PROPOSTAS ---
    if 'propostas' in listar_tabelas(origem):
        for row in o.execute('SELECT * FROM propostas ORDER BY id'):
            pid = mapa_projeto_id.get(row['projeto_id'])
            fid = mapa_freelancer_id.get(row['freelancer_id'])
            if not pid or not fid:
                continue
            cols = [k for k in row.keys() if k != 'id']
            data = dict(row)
            data['projeto_id'] = pid
            data['freelancer_id'] = fid
            try:
                d.execute(f'INSERT INTO propostas ({",".join(cols)}) VALUES ({",".join("?"*len(cols))})', [data[c] for c in cols])
            except sqlite3.IntegrityError:
                pass

    # --- MENSAGENS, AVALIACOES (se existirem) ---
    for tabela, mapa_ids in [
        ('mensagens', None),
        ('avaliacoes', None),
        ('avaliacoes_empresa', None),
        ('notificacoes', mapa_user_id),
    ]:
        if tabela not in listar_tabelas(origem):
            continue
        try:
            for row in o.execute(f'SELECT * FROM {tabela}'):
                cols = [k for k in row.keys() if k != 'id']
                data = dict(row)
                if tabela == 'notificacoes' and mapa_ids and row['user_id'] in mapa_ids:
                    data['user_id'] = mapa_ids[row['user_id']]
                try:
                    d.execute(f'INSERT INTO {tabela} ({",".join(cols)}) VALUES ({",".join("?"*len(cols))})', [data[c] for c in cols])
                except sqlite3.IntegrityError:
                    pass
        except sqlite3.Error as e:
            relatorio.append(f'{tabela}: erro {e}')

    destino.commit()
    origem.close()
    destino.close()

    print('\n=== CONTAGEM DEPOIS DA MIGRACAO ===')
    dest2 = sqlite3.connect(destino_path)
    for t, n in sorted(contar(dest2).items()):
        print(f'  {t}: {n}')
    dest2.close()

    print('\n=== RESUMO (ultimas 30 linhas) ===')
    for linha in relatorio[-30:]:
        print(' ', linha)
    print(f'\nTotal acoes registradas: {len(relatorio)}')
    print('Concluido com sucesso.')

if __name__ == '__main__':
    migrar()
