"""
Script para criar e gerenciar o banco de dados SQLite do ConectaServ
Plataforma de marketplace para freelancers de tecnologia
"""

import sqlite3
import os
import re
import time
import hashlib
from contextlib import contextmanager
from datetime import datetime

# Caminho do banco (Render: use DATABASE_PATH em disco persistente)
_DB_DIR = os.path.dirname(__file__)
_DB_PADRAO = os.path.join(_DB_DIR, 'conecta_serv.db')


def obter_db_path():
    """Permite disco persistente no Render via variável DATABASE_PATH."""
    custom = (os.environ.get('DATABASE_PATH') or '').strip()
    if custom:
        pasta = os.path.dirname(custom)
        if pasta:
            os.makedirs(pasta, exist_ok=True)
        return custom
    return _DB_PADRAO


DB_PATH = obter_db_path()


def info_diagnostico_banco():
    """Retorna estado do banco para a página de diagnóstico (produção)."""
    info = {
        'caminho': DB_PATH,
        'database_path_env': os.environ.get('DATABASE_PATH', '').strip() or '(não definido)',
        'render': os.environ.get('RENDER', '') == 'true',
        'arquivo_existe': os.path.exists(DB_PATH),
        'gravavel': os.access(os.path.dirname(DB_PATH) or '.', os.W_OK),
    }
    if info['arquivo_existe']:
        stat = os.stat(DB_PATH)
        info['tamanho_kb'] = round(stat.st_size / 1024, 1)
        info['modificado'] = datetime.fromtimestamp(stat.st_mtime).strftime('%d/%m/%Y %H:%M:%S')
    else:
        info['tamanho_kb'] = 0
        info['modificado'] = '-'
    conn = criar_conexao()
    cur = conn.cursor()
    info['freelancers'] = cur.execute('SELECT COUNT(*) FROM freelancers').fetchone()[0]
    info['empresas'] = cur.execute('SELECT COUNT(*) FROM empresas').fetchone()[0]
    info['users'] = cur.execute('SELECT COUNT(*) FROM users').fetchone()[0]
    conn.close()
    if info['database_path_env'] != '(não definido)':
        info['persistencia'] = 'DISCO PERSISTENTE (configurado)'
    elif info['render']:
        info['persistencia'] = 'TEMPORÁRIO — plano grátis Render (cadastros podem sumir)'
    else:
        info['persistencia'] = 'PC local (normal)'
    return info


def garantir_banco_persistente():
    """Na primeira execução com DATABASE_PATH, copia o .db do deploy se ainda não existir."""
    if DB_PATH == _DB_PADRAO:
        return
    if os.path.exists(DB_PATH):
        return
    if os.path.exists(_DB_PADRAO):
        import shutil
        shutil.copy2(_DB_PADRAO, DB_PATH)
        print(f'Banco copiado para disco persistente: {DB_PATH}')

def configurar_sqlite(conn):
    """Configura SQLite para reduzir erro 'database is locked'."""
    conn.execute('PRAGMA journal_mode=WAL')
    conn.execute('PRAGMA busy_timeout=60000')
    conn.execute('PRAGMA synchronous=NORMAL')
    conn.execute('PRAGMA foreign_keys=ON')
    conn.execute('PRAGMA wal_checkpoint(PASSIVE)')

def criar_conexao():
    """Cria conexão com o banco de dados (tolerante a arquivo .db aberto no editor)."""
    conn = sqlite3.connect(DB_PATH, timeout=60)
    conn.row_factory = sqlite3.Row
    configurar_sqlite(conn)
    return conn

@contextmanager
def conexao_db():
    """Garante fechamento da conexão após cada operação."""
    conn = criar_conexao()
    try:
        yield conn
    finally:
        conn.close()

def executar_com_retry(operacao, tentativas=8):
    """Repete operação no banco se SQLite estiver temporariamente bloqueado."""
    ultimo_erro = None
    for tentativa in range(tentativas):
        conn = criar_conexao()
        try:
            conn.execute('BEGIN IMMEDIATE')
            resultado = operacao(conn)
            conn.commit()
            return resultado
        except sqlite3.OperationalError as erro:
            try:
                conn.rollback()
            except sqlite3.OperationalError:
                pass
            ultimo_erro = erro
            if 'locked' not in str(erro).lower() or tentativa == tentativas - 1:
                raise
            time.sleep(0.15 * (tentativa + 1))
        except Exception:
            try:
                conn.rollback()
            except sqlite3.OperationalError:
                pass
            raise
        finally:
            conn.close()
    raise ultimo_erro

def normalizar_email(email):
    return (email or '').strip().lower()

def normalizar_documento(valor):
    return re.sub(r'\D', '', valor or '')

def email_ja_cadastrado(cursor, email):
    email = normalizar_email(email)
    if not email:
        return False
    cursor.execute('SELECT 1 FROM users WHERE LOWER(TRIM(email)) = ?', (email,))
    if cursor.fetchone():
        return True
    if tabela_existe(cursor, 'empresas') and coluna_existe(cursor, 'empresas', 'email'):
        cursor.execute('SELECT 1 FROM empresas WHERE LOWER(TRIM(email)) = ?', (email,))
        if cursor.fetchone():
            return True
    if tabela_existe(cursor, 'freelancers') and coluna_existe(cursor, 'freelancers', 'email'):
        cursor.execute('SELECT 1 FROM freelancers WHERE LOWER(TRIM(email)) = ?', (email,))
        if cursor.fetchone():
            return True
    return False

def cnpj_ja_cadastrado(cursor, cnpj):
    digits = normalizar_documento(cnpj)
    if not digits:
        return False
    cursor.execute('''
        SELECT 1 FROM empresas
        WHERE REPLACE(REPLACE(REPLACE(REPLACE(cnpj, '.', ''), '/', ''), '-', ''), ' ', '') = ?
    ''', (digits,))
    return cursor.fetchone() is not None

def cnpj_valido(cnpj):
    return len(normalizar_documento(cnpj)) == 14

def buscar_empresa_cadastrada(cursor, email, cnpj):
    """Retorna (tipo, dados) somente se já existir conta de empresa completa."""
    email = normalizar_email(email)
    if email:
        cursor.execute('''
            SELECT e.nome_empresa, u.email
            FROM empresas e
            JOIN users u ON u.id = e.user_id AND u.role = 'empresa'
            WHERE LOWER(TRIM(u.email)) = ? AND e.user_id IS NOT NULL
        ''', (email,))
        row = cursor.fetchone()
        if row:
            return 'email', dict(row)

    digits = normalizar_documento(cnpj)
    if len(digits) == 14:
        cursor.execute('''
            SELECT e.nome_empresa, u.email
            FROM empresas e
            JOIN users u ON u.id = e.user_id AND u.role = 'empresa'
            WHERE REPLACE(REPLACE(REPLACE(REPLACE(e.cnpj, '.', ''), '/', ''), '-', ''), ' ', '') = ?
              AND e.user_id IS NOT NULL
        ''', (digits,))
        row = cursor.fetchone()
        if row:
            return 'cnpj', dict(row)
    return None, None

def papel_do_email(cursor, email):
    """Retorna 'empresa', 'freelancer' ou None. O mesmo e-mail não pode ter os dois papéis."""
    email = normalizar_email(email)
    if not email:
        return None
    cursor.execute('SELECT role FROM users WHERE LOWER(TRIM(email)) = ?', (email,))
    usuario = cursor.fetchone()
    if usuario and usuario['role'] in ('empresa', 'freelancer'):
        return usuario['role']
    if tabela_existe(cursor, 'empresas') and coluna_existe(cursor, 'empresas', 'email'):
        cursor.execute('SELECT 1 FROM empresas WHERE LOWER(TRIM(email)) = ?', (email,))
        if cursor.fetchone():
            return 'empresa'
    if tabela_existe(cursor, 'freelancers') and coluna_existe(cursor, 'freelancers', 'email'):
        cursor.execute('SELECT 1 FROM freelancers WHERE LOWER(TRIM(email)) = ?', (email,))
        if cursor.fetchone():
            return 'freelancer'
    return None

def limpar_cadastro_incompleto_empresa(cursor, email):
    """Remove só cadastro de empresa pela metade. Nunca apaga conta de freelancer."""
    email = normalizar_email(email)
    cursor.execute('''
        DELETE FROM users
        WHERE id IN (
            SELECT u.id
            FROM users u
            LEFT JOIN empresas e ON e.user_id = u.id
            LEFT JOIN freelancers f ON f.user_id = u.id
            WHERE LOWER(TRIM(u.email)) = ?
              AND e.id IS NULL
              AND f.id IS NULL
              AND (u.role IS NULL OR u.role = 'empresa')
        )
    ''', (email,))

def registrar_empresa(nome_empresa, cnpj, email, senha, telefone, descricao, setor):
    """
    Cadastra empresa em transação única.
    Retorna dict: status ('ok'|'duplicado'|'freelancer'|'erro'), mensagem, dados.
    """
    email = normalizar_email(email)
    senha_hash = hash_password(senha)

    def operacao(conn):
        cursor = conn.cursor()
        papel = papel_do_email(cursor, email)
        if papel == 'freelancer':
            return {'status': 'freelancer'}

        limpar_cadastro_incompleto_empresa(cursor, email)

        tipo_dup, dados_dup = buscar_empresa_cadastrada(cursor, email, cnpj)
        if tipo_dup:
            return {
                'status': 'duplicado',
                'tipo': tipo_dup,
                'dados': dados_dup,
            }

        cursor.execute('SELECT role FROM users WHERE LOWER(TRIM(email)) = ?', (email,))
        user_existente = cursor.fetchone()
        if user_existente and user_existente['role'] == 'freelancer':
            return {'status': 'freelancer'}
        if user_existente and user_existente['role'] == 'empresa':
            return {
                'status': 'duplicado',
                'tipo': 'email',
                'dados': {'nome_empresa': nome_empresa, 'email': email},
            }

        cursor.execute('''
            INSERT INTO users (email, senha, role, ativo)
            VALUES (?, ?, ?, ?)
        ''', (email, senha_hash, 'empresa', 1))
        user_id = cursor.lastrowid

        inserir_perfil_empresa(
            cursor, user_id, nome_empresa, cnpj, email, senha_hash,
            telefone, descricao, setor,
        )

        cursor.execute('SELECT id FROM empresas WHERE user_id = ?', (user_id,))
        if not cursor.fetchone():
            raise RuntimeError('Perfil da empresa não foi gravado no banco.')

        return {'status': 'ok', 'email': email}

    return executar_com_retry(operacao)

def usuario_orfao_empresa(cursor, email):
    """Usuário em users sem linha em empresas (cadastro interrompido)."""
    email = normalizar_email(email)
    cursor.execute('''
        SELECT u.id AS user_id, u.email, u.role
        FROM users u
        LEFT JOIN empresas e ON e.user_id = u.id
        WHERE LOWER(TRIM(u.email)) = ? AND e.id IS NULL
    ''', (email,))
    return cursor.fetchone()

def cpf_ja_cadastrado(cursor, cpf):
    digits = normalizar_documento(cpf)
    if not digits:
        return False
    cursor.execute('''
        SELECT 1 FROM freelancers
        WHERE REPLACE(REPLACE(REPLACE(REPLACE(cpf, '.', ''), '/', ''), '-', ''), ' ', '') = ?
    ''', (digits,))
    return cursor.fetchone() is not None

def atualizar_senha_usuario(cursor, user_id, email, senha_hash, role):
    """Atualiza senha em users e, no banco legado, também na tabela de perfil."""
    cursor.execute('UPDATE users SET senha = ? WHERE id = ?', (senha_hash, user_id))
    if role == 'empresa' and tabela_legado_auth(cursor, 'empresas'):
        cursor.execute('UPDATE empresas SET senha = ? WHERE user_id = ?', (senha_hash, user_id))
    elif role == 'freelancer' and tabela_legado_auth(cursor, 'freelancers'):
        cursor.execute('UPDATE freelancers SET senha = ? WHERE user_id = ?', (senha_hash, user_id))

def inserir_perfil_empresa(cursor, user_id, nome_empresa, cnpj, email, senha_hash, telefone, descricao, setor):
    if tabela_legado_auth(cursor, 'empresas'):
        cursor.execute('''
            INSERT INTO empresas (user_id, nome_empresa, cnpj, email, senha, telefone, descricao, setor)
            VALUES (?, ?, ?, ?, ?, ?, ?, ?)
        ''', (user_id, nome_empresa, cnpj, email, senha_hash, telefone, descricao, setor))
    else:
        cursor.execute('''
            INSERT INTO empresas (user_id, nome_empresa, cnpj, telefone, descricao, setor)
            VALUES (?, ?, ?, ?, ?, ?)
        ''', (user_id, nome_empresa, cnpj, telefone, descricao, setor))

def inserir_perfil_freelancer(cursor, user_id, nome_completo, email, senha_hash, telefone, cpf,
                              cidade, estado, especialidade, habilidades, biografia, hourly_rate):
    if tabela_legado_auth(cursor, 'freelancers'):
        cursor.execute('''
            INSERT INTO freelancers (user_id, nome_completo, email, senha, telefone, cpf, cidade, estado,
                                    especialidade, habilidades, biografia, hourly_rate)
            VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
        ''', (user_id, nome_completo, email, senha_hash, telefone, cpf, cidade, estado,
              especialidade, habilidades, biografia, hourly_rate))
    else:
        cursor.execute('''
            INSERT INTO freelancers (user_id, nome_completo, telefone, cpf, cidade, estado,
                                    especialidade, habilidades, biografia, hourly_rate)
            VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
        ''', (user_id, nome_completo, telefone, cpf, cidade, estado,
              especialidade, habilidades, biografia, hourly_rate))

def tabela_existe(cursor, tabela):
    cursor.execute("SELECT name FROM sqlite_master WHERE type='table' AND name=?", (tabela,))
    return cursor.fetchone() is not None

def coluna_existe(cursor, tabela, coluna):
    cursor.execute(f"PRAGMA table_info({tabela})")
    return any(row[1] == coluna for row in cursor.fetchall())

def tabela_legado_auth(cursor, tabela):
    """Banco antigo guarda email/senha também na tabela de perfil."""
    return coluna_existe(cursor, tabela, 'email') and coluna_existe(cursor, tabela, 'senha')

def hash_password(password):
    """Hash de senha: PBKDF2 (Werkzeug). Hashes SHA-256 antigos continuam válidos na verificação."""
    from werkzeug.security import generate_password_hash
    return generate_password_hash(password or '', method='pbkdf2:sha256', salt_length=16)

def criar_usuario_legacy(cursor, email, senha, role):
    if not email:
        return None
    senha_hash = hash_password(senha or '')
    cursor.execute(
        'INSERT OR IGNORE INTO users (email, senha, role, ativo) VALUES (?, ?, ?, 1)',
        (email, senha_hash, role)
    )
    cursor.execute('SELECT id FROM users WHERE email = ?', (email,))
    row = cursor.fetchone()
    return row['id'] if row else None

def migrar_dados_legado(cursor):
    if tabela_existe(cursor, 'empresas') and coluna_existe(cursor, 'empresas', 'email') and not coluna_existe(cursor, 'empresas', 'user_id'):
        cursor.execute('ALTER TABLE empresas ADD COLUMN user_id INTEGER')
        cursor.execute('SELECT id, email, senha FROM empresas WHERE user_id IS NULL')
        for row in cursor.fetchall():
            user_id = criar_usuario_legacy(cursor, row['email'], row['senha'], 'empresa')
            if user_id:
                cursor.execute('UPDATE empresas SET user_id = ? WHERE id = ?', (user_id, row['id']))

    if tabela_existe(cursor, 'freelancers') and coluna_existe(cursor, 'freelancers', 'email') and not coluna_existe(cursor, 'freelancers', 'user_id'):
        cursor.execute('ALTER TABLE freelancers ADD COLUMN user_id INTEGER')
        cursor.execute('SELECT id, email, senha FROM freelancers WHERE user_id IS NULL')
        for row in cursor.fetchall():
            user_id = criar_usuario_legacy(cursor, row['email'], row['senha'], 'freelancer')
            if user_id:
                cursor.execute('UPDATE freelancers SET user_id = ? WHERE id = ?', (user_id, row['id']))

    return

def criar_tabelas():
    """Cria todas as tabelas do banco de dados"""
    conn = criar_conexao()
    cursor = conn.cursor()
    cursor.execute('PRAGMA foreign_keys = ON')
    
    # Tabela de usuários (base para autenticação)
    cursor.execute('''
        CREATE TABLE IF NOT EXISTS users (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            email TEXT UNIQUE NOT NULL,
            senha TEXT NOT NULL,
            role TEXT NOT NULL CHECK (role IN ('freelancer', 'empresa', 'admin')),
            ativo INTEGER DEFAULT 1,
            data_cadastro TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
            ultimo_login TIMESTAMP
        )
    ''')
    
    migrar_dados_legado(cursor)
    
    # Tabela de empresas contratantes
    cursor.execute('''
        CREATE TABLE IF NOT EXISTS empresas (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            user_id INTEGER UNIQUE NOT NULL,
            nome_empresa TEXT NOT NULL,
            cnpj TEXT UNIQUE,
            telefone TEXT,
            descricao TEXT,
            setor TEXT,
            site TEXT,
            logo TEXT,
            endereco TEXT,
            cidade TEXT,
            estado TEXT,
            cep TEXT,
            nota_media DECIMAL(3,2) DEFAULT 0,
            data_cadastro TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
            status TEXT DEFAULT 'ativo',
            FOREIGN KEY (user_id) REFERENCES users(id) ON DELETE CASCADE
        )
    ''')
    
    # Garantir coluna de nota_media em empresas mesmo para bancos antigos
    cursor.execute("PRAGMA table_info(empresas)")
    columns = [row[1] for row in cursor.fetchall()]
    if 'nota_media' not in columns:
        cursor.execute('ALTER TABLE empresas ADD COLUMN nota_media DECIMAL(3,2) DEFAULT 0')
    for coluna, definicao in (
        ('cidade', 'TEXT'),
        ('estado', 'TEXT'),
        ('setor', 'TEXT'),
        ('descricao', 'TEXT'),
        ('status', "TEXT DEFAULT 'ativo'"),
    ):
        if coluna not in columns:
            try:
                cursor.execute(f'ALTER TABLE empresas ADD COLUMN {coluna} {definicao}')
            except sqlite3.OperationalError:
                pass
            columns.append(coluna)
    
    # Tabela de freelancers
    cursor.execute('''
        CREATE TABLE IF NOT EXISTS freelancers (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            user_id INTEGER UNIQUE NOT NULL,
            nome_completo TEXT NOT NULL,
            telefone TEXT,
            cpf TEXT UNIQUE,
            data_nascimento DATE,
            cidade TEXT,
            estado TEXT,
            especialidade TEXT,
            habilidades TEXT,
            portfolio TEXT,
            biografia TEXT,
            linkedin TEXT,
            github TEXT,
            foto TEXT,
            hourly_rate DECIMAL(10,2),
            disponibilidade TEXT DEFAULT 'disponivel',
            nota_media DECIMAL(3,2) DEFAULT 0,
            total_projetos INTEGER DEFAULT 0,
            projetos_concluidos INTEGER DEFAULT 0,
            taxa_conclusao DECIMAL(5,2) DEFAULT 0,
            tempo_resposta_horas INTEGER DEFAULT 0,
            data_cadastro TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
            status TEXT DEFAULT 'ativo',
            destaque TEXT DEFAULT 'nao',
            FOREIGN KEY (user_id) REFERENCES users(id) ON DELETE CASCADE
        )
    ''')

    
    # Tabela de projetos/vagas
    cursor.execute('''
        CREATE TABLE IF NOT EXISTS projetos (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            empresa_id INTEGER NOT NULL,
            titulo TEXT NOT NULL,
            descricao TEXT NOT NULL,
            categoria TEXT NOT NULL,
            habilidades_requeridas TEXT,
            presupuesto DECIMAL(10,2),
            prazo DATE,
            nivel_experiencia TEXT,
            status TEXT DEFAULT 'aberto',
            data_criacao TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
            FOREIGN KEY (empresa_id) REFERENCES empresas(id)
        )
    ''')
    
    # Tabela de propostas
    cursor.execute('''
        CREATE TABLE IF NOT EXISTS propostas (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            projeto_id INTEGER NOT NULL,
            freelancer_id INTEGER NOT NULL,
            valor_proposto DECIMAL(10,2) NOT NULL,
            prazo_dias INTEGER NOT NULL,
            proposta TEXT,
            status TEXT DEFAULT 'pendente',
            data_proposta TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
            FOREIGN KEY (projeto_id) REFERENCES projetos(id),
            FOREIGN KEY (freelancer_id) REFERENCES freelancers(id)
        )
    ''')
    
    # Tabela de avaliações para freelancers
    cursor.execute('''
        CREATE TABLE IF NOT EXISTS avaliacoes (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            projeto_id INTEGER NOT NULL,
            freelancer_id INTEGER NOT NULL,
            empresa_id INTEGER NOT NULL,
            nota_qualidade INTEGER NOT NULL,
            nota_prazo INTEGER NOT NULL,
            nota_comunicacao INTEGER NOT NULL,
            nota_portfolio INTEGER NOT NULL DEFAULT 0,
            comentario TEXT,
            data_avaliacao TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
            FOREIGN KEY (projeto_id) REFERENCES projetos(id),
            FOREIGN KEY (freelancer_id) REFERENCES freelancers(id),
            FOREIGN KEY (empresa_id) REFERENCES empresas(id)
        )
    ''')
    cursor.execute('PRAGMA table_info(avaliacoes)')
    avaliacao_columns = [row[1] for row in cursor.fetchall()]
    if 'nota_portfolio' not in avaliacao_columns:
        cursor.execute('ALTER TABLE avaliacoes ADD COLUMN nota_portfolio INTEGER NOT NULL DEFAULT 0')

    # Tabela de avaliações para empresas
    cursor.execute('''
        CREATE TABLE IF NOT EXISTS avaliacoes_empresa (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            projeto_id INTEGER NOT NULL,
            empresa_id INTEGER NOT NULL,
            freelancer_id INTEGER NOT NULL,
            nota_satisfacao INTEGER NOT NULL,
            nota_profissionalismo INTEGER NOT NULL DEFAULT 0,
            nota_portfolio INTEGER NOT NULL DEFAULT 0,
            comentario TEXT,
            data_avaliacao TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
            FOREIGN KEY (projeto_id) REFERENCES projetos(id),
            FOREIGN KEY (empresa_id) REFERENCES empresas(id),
            FOREIGN KEY (freelancer_id) REFERENCES freelancers(id)
        )
    ''')
    cursor.execute('PRAGMA table_info(avaliacoes_empresa)')
    avaliacao_empresa_columns = [row[1] for row in cursor.fetchall()]
    if 'nota_profissionalismo' not in avaliacao_empresa_columns:
        cursor.execute('ALTER TABLE avaliacoes_empresa ADD COLUMN nota_profissionalismo INTEGER NOT NULL DEFAULT 0')
    if 'nota_portfolio' not in avaliacao_empresa_columns:
        cursor.execute('ALTER TABLE avaliacoes_empresa ADD COLUMN nota_portfolio INTEGER NOT NULL DEFAULT 0')
    
    # Tabela de contratos
    cursor.execute('''
        CREATE TABLE IF NOT EXISTS contratos (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            proposta_id INTEGER UNIQUE NOT NULL,
            projeto_id INTEGER,
            empresa_id INTEGER,
            freelancer_id INTEGER,
            valor DECIMAL(10,2),
            prazo_dias INTEGER,
            status TEXT DEFAULT 'ativo',
            data_inicio TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
            data_conclusao TIMESTAMP,
            termos TEXT,
            FOREIGN KEY (proposta_id) REFERENCES propostas(id),
            FOREIGN KEY (projeto_id) REFERENCES projetos(id),
            FOREIGN KEY (empresa_id) REFERENCES empresas(id),
            FOREIGN KEY (freelancer_id) REFERENCES freelancers(id)
        )
    ''')

    # Tabela de notificações
    cursor.execute('''
        CREATE TABLE IF NOT EXISTS notificacoes (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            user_id INTEGER NOT NULL,
            titulo TEXT NOT NULL,
            mensagem TEXT NOT NULL,
            tipo TEXT DEFAULT 'info',
            lida INTEGER DEFAULT 0,
            data_criacao TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
            FOREIGN KEY (user_id) REFERENCES users(id)
        )
    ''')

    # Tabela de mensagens/chat
    cursor.execute('''
        CREATE TABLE IF NOT EXISTS mensagens (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            remetente_id INTEGER NOT NULL,
            destinatario_id INTEGER NOT NULL,
            remetente_tipo TEXT NOT NULL,
            destinatario_tipo TEXT NOT NULL,
            mensagem TEXT NOT NULL,
            lida INTEGER DEFAULT 0,
            data_envio TIMESTAMP DEFAULT CURRENT_TIMESTAMP
        )
    ''')

    # Tabela de acessibilidade
    cursor.execute('''
        CREATE TABLE IF NOT EXISTS acessibilidade (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            usuario_id INTEGER NOT NULL,
            usuario_tipo TEXT NOT NULL,
            alto_contraste INTEGER DEFAULT 0,
            fonte_aumentada INTEGER DEFAULT 0,
            leitor_tela INTEGER DEFAULT 0,
            linguagem_simplificada INTEGER DEFAULT 0
        )
    ''')

    # Categorias normalizadas
    cursor.execute('''
        CREATE TABLE IF NOT EXISTS categorias (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            nome TEXT UNIQUE NOT NULL,
            descricao TEXT,
            ativa INTEGER DEFAULT 1
        )
    ''')

    # Habilidades normalizadas
    cursor.execute('''
        CREATE TABLE IF NOT EXISTS habilidades (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            nome TEXT UNIQUE NOT NULL,
            categoria_id INTEGER,
            FOREIGN KEY (categoria_id) REFERENCES categorias(id)
        )
    ''')

    # Tarefas do projeto (pós-contratação)
    cursor.execute('''
        CREATE TABLE IF NOT EXISTS tarefas (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            projeto_id INTEGER NOT NULL,
            titulo TEXT NOT NULL,
            descricao TEXT,
            status TEXT DEFAULT 'pendente' CHECK (status IN ('pendente', 'em_andamento', 'concluida', 'cancelada')),
            ordem INTEGER DEFAULT 0,
            data_criacao TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
            data_conclusao TIMESTAMP,
            FOREIGN KEY (projeto_id) REFERENCES projetos(id) ON DELETE CASCADE
        )
    ''')

    # Pagamentos
    cursor.execute('''
        CREATE TABLE IF NOT EXISTS pagamentos (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            contrato_id INTEGER NOT NULL,
            projeto_id INTEGER NOT NULL,
            valor DECIMAL(10,2) NOT NULL,
            status TEXT DEFAULT 'pendente' CHECK (status IN ('pendente', 'pago', 'cancelado', 'reembolsado')),
            metodo TEXT,
            data_criacao TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
            data_pagamento TIMESTAMP,
            observacao TEXT,
            FOREIGN KEY (contrato_id) REFERENCES contratos(id),
            FOREIGN KEY (projeto_id) REFERENCES projetos(id)
        )
    ''')

    # Histórico / auditoria do projeto
    cursor.execute('''
        CREATE TABLE IF NOT EXISTS historico_projeto (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            projeto_id INTEGER NOT NULL,
            usuario_id INTEGER,
            evento TEXT NOT NULL,
            detalhe TEXT,
            etapa_anterior TEXT,
            etapa_nova TEXT,
            data_evento TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
            FOREIGN KEY (projeto_id) REFERENCES projetos(id) ON DELETE CASCADE,
            FOREIGN KEY (usuario_id) REFERENCES users(id)
        )
    ''')

    # Arquivos / anexos do projeto
    cursor.execute('''
        CREATE TABLE IF NOT EXISTS arquivos_projeto (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            projeto_id INTEGER NOT NULL,
            usuario_id INTEGER,
            nome_arquivo TEXT NOT NULL,
            caminho TEXT,
            tipo TEXT,
            tamanho INTEGER,
            data_upload TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
            FOREIGN KEY (projeto_id) REFERENCES projetos(id) ON DELETE CASCADE,
            FOREIGN KEY (usuario_id) REFERENCES users(id)
        )
    ''')

    # Colunas extras em projetos (ciclo pós-contratação)
    for coluna, definicao in [
        ('etapa', "TEXT DEFAULT 'publicado'"),
        ('progresso', 'INTEGER DEFAULT 0'),
        ('freelancer_contratado_id', 'INTEGER'),
        ('contrato_id', 'INTEGER'),
        ('data_contratacao', 'TIMESTAMP'),
        ('data_conclusao', 'TIMESTAMP'),
    ]:
        if not coluna_existe(cursor, 'projetos', coluna):
            cursor.execute(f'ALTER TABLE projetos ADD COLUMN {coluna} {definicao}')

    # Colunas extras em contratos (bancos antigos)
    for coluna, definicao in [
        ('projeto_id', 'INTEGER'),
        ('empresa_id', 'INTEGER'),
        ('freelancer_id', 'INTEGER'),
        ('valor', 'DECIMAL(10,2)'),
        ('prazo_dias', 'INTEGER'),
    ]:
        if not coluna_existe(cursor, 'contratos', coluna):
            cursor.execute(f'ALTER TABLE contratos ADD COLUMN {coluna} {definicao}')

    # Mensagens vinculadas ao projeto
    if not coluna_existe(cursor, 'mensagens', 'projeto_id'):
        cursor.execute('ALTER TABLE mensagens ADD COLUMN projeto_id INTEGER')

    # Categorias padrão
    categorias_padrao = [
        ('Desenvolvimento Web', 'Sites, sistemas e APIs web'),
        ('Desenvolvimento Mobile', 'Apps Android e iOS'),
        ('Design / UI-UX', 'Interfaces e experiência do usuário'),
        ('Dados / BI', 'Análise de dados e dashboards'),
        ('Infra / DevOps', 'Cloud, servidores e CI/CD'),
        ('Outros', 'Demais categorias'),
    ]
    for nome, desc in categorias_padrao:
        cursor.execute(
            'INSERT OR IGNORE INTO categorias (nome, descricao) VALUES (?, ?)',
            (nome, desc),
        )

    # Índices para performance
    cursor.execute('CREATE INDEX IF NOT EXISTS idx_users_email ON users(email)')
    cursor.execute('CREATE INDEX IF NOT EXISTS idx_empresas_user_id ON empresas(user_id)')
    cursor.execute('CREATE INDEX IF NOT EXISTS idx_freelancers_user_id ON freelancers(user_id)')
    cursor.execute('CREATE INDEX IF NOT EXISTS idx_projetos_empresa_id ON projetos(empresa_id)')
    cursor.execute('CREATE INDEX IF NOT EXISTS idx_propostas_projeto_id ON propostas(projeto_id)')
    cursor.execute('CREATE INDEX IF NOT EXISTS idx_avaliacoes_freelancer_id ON avaliacoes(freelancer_id)')
    cursor.execute('CREATE INDEX IF NOT EXISTS idx_mensagens_destinatario ON mensagens(destinatario_id, destinatario_tipo)')
    cursor.execute('CREATE INDEX IF NOT EXISTS idx_tarefas_projeto ON tarefas(projeto_id)')
    cursor.execute('CREATE INDEX IF NOT EXISTS idx_historico_projeto ON historico_projeto(projeto_id)')
    cursor.execute('CREATE INDEX IF NOT EXISTS idx_pagamentos_projeto ON pagamentos(projeto_id)')
    cursor.execute('CREATE INDEX IF NOT EXISTS idx_notificacoes_user ON notificacoes(user_id)')

    cursor.execute('''
        CREATE TABLE IF NOT EXISTS chat_mensagens (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            sessao_id TEXT NOT NULL,
            user_id INTEGER,
            origem TEXT NOT NULL CHECK (origem IN ('usuario', 'bot')),
            mensagem TEXT NOT NULL,
            canal TEXT DEFAULT 'web',
            data_envio TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
            FOREIGN KEY (user_id) REFERENCES users(id)
        )
    ''')
    cursor.execute('CREATE INDEX IF NOT EXISTS idx_chat_sessao ON chat_mensagens(sessao_id)')

    conn.commit()
    conn.close()
    print("Banco de dados criado com sucesso!")


ETAPAS_PROJETO = [
    'publicado',
    'propostas',
    'contratado',
    'inicio',
    'desenvolvimento',
    'entrega',
    'aprovacao',
    'pagamento',
    'avaliacao',
    'concluido',
]

ETAPA_LABELS = {
    'publicado': 'Projeto publicado',
    'propostas': 'Recebendo propostas',
    'contratado': 'Contratação',
    'inicio': 'Início',
    'desenvolvimento': 'Desenvolvimento',
    'entrega': 'Entrega',
    'aprovacao': 'Aprovação',
    'pagamento': 'Pagamento',
    'avaliacao': 'Avaliação',
    'concluido': 'Concluído',
}


def registrar_historico(cursor, projeto_id, evento, detalhe=None, usuario_id=None,
                        etapa_anterior=None, etapa_nova=None):
    cursor.execute('''
        INSERT INTO historico_projeto
            (projeto_id, usuario_id, evento, detalhe, etapa_anterior, etapa_nova)
        VALUES (?, ?, ?, ?, ?, ?)
    ''', (projeto_id, usuario_id, evento, detalhe, etapa_anterior, etapa_nova))


def criar_notificacao(cursor, user_id, titulo, mensagem, tipo='info'):
    if not user_id:
        return
    cursor.execute('''
        INSERT INTO notificacoes (user_id, titulo, mensagem, tipo)
        VALUES (?, ?, ?, ?)
    ''', (user_id, titulo, mensagem, tipo))


def notificar_destinatario(cursor, destinatario_tipo, destinatario_id, titulo, mensagem, tipo='mensagem'):
    """Avisa o dono da conta sem desfazer a mensagem se a notificação falhar."""
    if not destinatario_id or destinatario_tipo not in ('empresa', 'freelancer'):
        return
    tabela = 'empresas' if destinatario_tipo == 'empresa' else 'freelancers'
    try:
        cursor.execute('SAVEPOINT notif_msg')
        cursor.execute(f'SELECT user_id FROM {tabela} WHERE id = ?', (destinatario_id,))
        row = cursor.fetchone()
        if row and row['user_id']:
            criar_notificacao(cursor, row['user_id'], titulo, (mensagem or '')[:180], tipo)
        cursor.execute('RELEASE SAVEPOINT notif_msg')
    except sqlite3.Error:
        try:
            cursor.execute('ROLLBACK TO SAVEPOINT notif_msg')
            cursor.execute('RELEASE SAVEPOINT notif_msg')
        except sqlite3.Error:
            pass


TAXA_EMPRESA_PERCENTUAL = 10


def taxa_empresa(valor_proposta=0):
    """Taxa de serviço cobrada da empresa sobre o valor da proposta aceita."""
    try:
        valor = float(valor_proposta or 0)
    except (TypeError, ValueError):
        valor = 0.0
    taxa = round(valor * TAXA_EMPRESA_PERCENTUAL / 100.0, 2)
    return {
        'percentual': TAXA_EMPRESA_PERCENTUAL,
        'valor_proposta': round(valor, 2),
        'taxa': taxa,
        'total': round(valor + taxa, 2),
    }


def encerrar_projeto(cursor, projeto_id, empresa_id):
    cursor.execute(
        'SELECT id, status FROM projetos WHERE id = ? AND empresa_id = ?',
        (projeto_id, empresa_id),
    )
    row = cursor.fetchone()
    if not row:
        return 'nao_encontrado'
    if row['status'] != 'aberto':
        return 'nao_aberto'
    cursor.execute("UPDATE projetos SET status = 'encerrado' WHERE id = ?", (projeto_id,))
    try:
        cursor.execute(
            "UPDATE propostas SET status = 'recusada' WHERE projeto_id = ? AND status = 'pendente'",
            (projeto_id,),
        )
    except sqlite3.Error:
        pass
    return 'ok'


def excluir_projeto(cursor, projeto_id, empresa_id):
    cursor.execute(
        'SELECT id, status FROM projetos WHERE id = ? AND empresa_id = ?',
        (projeto_id, empresa_id),
    )
    row = cursor.fetchone()
    if not row:
        return 'nao_encontrado'
    if row['status'] not in ('aberto', 'encerrado'):
        return 'em_andamento'
    for sql in (
        'DELETE FROM arquivos_projeto WHERE projeto_id = ?',
        'DELETE FROM tarefas WHERE projeto_id = ?',
        'DELETE FROM historico_projeto WHERE projeto_id = ?',
        'DELETE FROM propostas WHERE projeto_id = ?',
        'DELETE FROM projetos WHERE id = ?',
    ):
        try:
            cursor.execute(sql, (projeto_id,))
        except sqlite3.Error:
            pass
    return 'ok'


def _expr_coluna(cursor, tabela, coluna, alias, vazio="''"):
    if coluna_existe(cursor, tabela, coluna):
        return f'{alias}.{coluna}'
    return vazio


def aceitar_proposta_db(cursor, proposta_id, empresa_id, usuario_id=None):
    """Aceita a proposta. Extras (contrato, tarefas, aviso) não derrubam a aceitação."""
    email_f = (
        'COALESCE(uf.email, f.email)' if coluna_existe(cursor, 'freelancers', 'email') else 'uf.email'
    )
    email_e = (
        'COALESCE(ue.email, e.email)' if coluna_existe(cursor, 'empresas', 'email') else 'ue.email'
    )
    tel_f = _expr_coluna(cursor, 'freelancers', 'telefone', 'f')
    tel_e = _expr_coluna(cursor, 'empresas', 'telefone', 'e')
    uid_f = _expr_coluna(cursor, 'freelancers', 'user_id', 'f', 'NULL')
    cursor.execute(f'''
        SELECT p.id, p.projeto_id, p.freelancer_id, p.valor_proposto, p.prazo_dias, p.status,
               proj.empresa_id, proj.titulo,
               f.nome_completo AS freelancer_nome, {tel_f} AS freelancer_telefone,
               {uid_f} AS freelancer_user_id,
               {email_f} AS freelancer_email,
               e.nome_empresa AS empresa_nome, {tel_e} AS empresa_telefone,
               {email_e} AS empresa_email
        FROM propostas p
        JOIN projetos proj ON p.projeto_id = proj.id
        JOIN freelancers f ON p.freelancer_id = f.id
        LEFT JOIN users uf ON uf.id = f.user_id
        JOIN empresas e ON proj.empresa_id = e.id
        LEFT JOIN users ue ON ue.id = e.user_id
        WHERE p.id = ?
    ''', (proposta_id,))
    proposta = cursor.fetchone()
    if not proposta or proposta['empresa_id'] != empresa_id:
        return {'status': 'nao_encontrada'}

    dados = dict(proposta)
    if dados.get('status') == 'aceita':
        return {'status': 'ja_aceita', 'projeto_id': dados['projeto_id'], 'proposta': dados}

    projeto_id = dados['projeto_id']
    cursor.execute('UPDATE propostas SET status = ? WHERE id = ?', ('aceita', proposta_id))
    cursor.execute(
        "UPDATE propostas SET status = 'recusada' WHERE projeto_id = ? AND id != ? AND status = 'pendente'",
        (projeto_id, proposta_id),
    )

    campos = ["status = 'andamento'"]
    valores = []
    if coluna_existe(cursor, 'projetos', 'etapa'):
        campos.append("etapa = 'contratado'")
    if coluna_existe(cursor, 'projetos', 'freelancer_contratado_id'):
        campos.append('freelancer_contratado_id = ?')
        valores.append(dados['freelancer_id'])
    if coluna_existe(cursor, 'projetos', 'data_contratacao'):
        campos.append('data_contratacao = CURRENT_TIMESTAMP')
    valores.append(projeto_id)
    cursor.execute(f"UPDATE projetos SET {', '.join(campos)} WHERE id = ?", valores)

    try:
        cursor.execute('SAVEPOINT aceitar_extra')
        if tabela_existe(cursor, 'contratos'):
            cursor.execute('''
                INSERT INTO contratos (proposta_id, projeto_id, empresa_id, freelancer_id, valor, prazo_dias, status, termos)
                VALUES (?, ?, ?, ?, ?, ?, 'ativo', ?)
            ''', (
                proposta_id, projeto_id, dados['empresa_id'], dados['freelancer_id'],
                dados['valor_proposto'], dados['prazo_dias'],
                f"Contrato gerado automaticamente para o projeto: {dados['titulo']}",
            ))
            contrato_id = cursor.lastrowid
            if coluna_existe(cursor, 'projetos', 'contrato_id'):
                cursor.execute('UPDATE projetos SET contrato_id = ? WHERE id = ?', (contrato_id, projeto_id))
            if tabela_existe(cursor, 'pagamentos'):
                cursor.execute('''
                    INSERT INTO pagamentos (contrato_id, projeto_id, valor, status, metodo, observacao)
                    VALUES (?, ?, ?, 'pendente', 'a_definir', 'Pagamento previsto após aprovação da entrega')
                ''', (contrato_id, projeto_id, dados['valor_proposto']))
        if tabela_existe(cursor, 'tarefas'):
            for ordem, titulo in (
                (1, 'Kick-off e alinhamento de escopo'),
                (2, 'Desenvolvimento / execução'),
                (3, 'Revisão e ajustes'),
                (4, 'Entrega final'),
            ):
                cursor.execute(
                    'INSERT INTO tarefas (projeto_id, titulo, status, ordem) VALUES (?, ?, ?, ?)',
                    (projeto_id, titulo, 'pendente' if ordem > 1 else 'em_andamento', ordem),
                )
        if tabela_existe(cursor, 'historico_projeto'):
            registrar_historico(
                cursor, projeto_id,
                evento='proposta_aceita',
                detalhe=f"Freelancer {dados.get('freelancer_nome')} contratado por R$ {dados.get('valor_proposto')}",
                usuario_id=usuario_id,
                etapa_anterior='propostas',
                etapa_nova='contratado',
            )
        if dados.get('freelancer_user_id'):
            criar_notificacao(
                cursor, dados['freelancer_user_id'],
                'Proposta aceita!',
                f'Sua proposta para "{dados.get("titulo")}" foi aceita. Acompanhe o projeto na plataforma.',
                'sucesso',
            )
        cursor.execute('RELEASE SAVEPOINT aceitar_extra')
    except sqlite3.Error:
        try:
            cursor.execute('ROLLBACK TO SAVEPOINT aceitar_extra')
            cursor.execute('RELEASE SAVEPOINT aceitar_extra')
        except sqlite3.Error:
            pass

    dados['status'] = 'aceita'
    return {'status': 'ok', 'projeto_id': projeto_id, 'proposta': dados}


def recalcular_progresso_projeto(cursor, projeto_id):
    cursor.execute('SELECT COUNT(*) AS total FROM tarefas WHERE projeto_id = ?', (projeto_id,))
    total = cursor.fetchone()['total']
    if total == 0:
        return 0
    cursor.execute(
        "SELECT COUNT(*) AS feitas FROM tarefas WHERE projeto_id = ? AND status = 'concluida'",
        (projeto_id,),
    )
    feitas = cursor.fetchone()['feitas']
    progresso = int(round((feitas / total) * 100))
    cursor.execute('UPDATE projetos SET progresso = ? WHERE id = ?', (progresso, projeto_id))
    return progresso


def calcular_indicadores_empresa(cursor, empresa_id):
    """KPIs do painel da empresa para apresentação / gestão."""
    cursor.execute(
        'SELECT COUNT(*) AS n FROM projetos WHERE empresa_id = ?',
        (empresa_id,),
    )
    total_projetos = cursor.fetchone()['n']

    cursor.execute(
        "SELECT COUNT(*) AS n FROM projetos WHERE empresa_id = ? AND status = 'aberto'",
        (empresa_id,),
    )
    publicados = cursor.fetchone()['n']

    cursor.execute(
        """SELECT COUNT(*) AS n FROM projetos
           WHERE empresa_id = ? AND status IN ('andamento', 'desenvolvimento', 'entrega', 'aprovacao', 'pagamento')""",
        (empresa_id,),
    )
    em_andamento = cursor.fetchone()['n']

    cursor.execute(
        "SELECT COUNT(*) AS n FROM projetos WHERE empresa_id = ? AND status = 'concluido'",
        (empresa_id,),
    )
    concluidos = cursor.fetchone()['n']

    cursor.execute('''
        SELECT COUNT(*) AS n FROM propostas p
        JOIN projetos pr ON p.projeto_id = pr.id
        WHERE pr.empresa_id = ?
    ''', (empresa_id,))
    propostas_recebidas = cursor.fetchone()['n']

    cursor.execute('''
        SELECT COALESCE(SUM(p.valor_proposto), 0) AS total
        FROM propostas p
        JOIN projetos pr ON p.projeto_id = pr.id
        WHERE pr.empresa_id = ? AND p.status = 'aceita'
    ''', (empresa_id,))
    valores_contratados = float(cursor.fetchone()['total'] or 0)

    cursor.execute('''
        SELECT COALESCE(SUM(pg.valor), 0) AS total
        FROM pagamentos pg
        JOIN projetos pr ON pg.projeto_id = pr.id
        WHERE pr.empresa_id = ? AND pg.status = 'pago'
    ''', (empresa_id,))
    valores_pagos = float(cursor.fetchone()['total'] or 0)

    cursor.execute('''
        SELECT AVG(
            JULIANDAY(pr.data_contratacao) - JULIANDAY(pr.data_criacao)
        ) AS media_dias
        FROM projetos pr
        WHERE pr.empresa_id = ? AND pr.data_contratacao IS NOT NULL
    ''', (empresa_id,))
    row_media = cursor.fetchone()
    tempo_medio_contratar = round(row_media['media_dias'] or 0, 1) if row_media else 0

    cursor.execute('''
        SELECT f.id, f.nome_completo, COUNT(*) AS contratacoes, AVG(f.nota_media) AS nota
        FROM propostas p
        JOIN projetos pr ON p.projeto_id = pr.id
        JOIN freelancers f ON p.freelancer_id = f.id
        WHERE pr.empresa_id = ? AND p.status = 'aceita'
        GROUP BY f.id
        ORDER BY contratacoes DESC, nota DESC
        LIMIT 5
    ''', (empresa_id,))
    freelancers_top = [dict(r) for r in cursor.fetchall()]

    cursor.execute('''
        SELECT categoria, COUNT(*) AS total
        FROM projetos
        WHERE empresa_id = ?
        GROUP BY categoria
        ORDER BY total DESC
        LIMIT 5
    ''', (empresa_id,))
    categorias_top = [dict(r) for r in cursor.fetchall()]

    cursor.execute('''
        SELECT AVG((a.nota_qualidade + a.nota_prazo + a.nota_comunicacao + a.nota_portfolio) / 4.0) AS media
        FROM avaliacoes a
        WHERE a.empresa_id = ?
    ''', (empresa_id,))
    row_av = cursor.fetchone()
    media_avaliacoes = round(float(row_av['media'] or 0), 2) if row_av and row_av['media'] else 0

    taxa_conclusao = round((concluidos / total_projetos) * 100, 1) if total_projetos else 0

    return {
        'total_projetos': total_projetos,
        'publicados': publicados,
        'em_andamento': em_andamento,
        'concluidos': concluidos,
        'propostas_recebidas': propostas_recebidas,
        'valores_contratados': valores_contratados,
        'valores_pagos': valores_pagos,
        'valores_movimentados': valores_contratados + valores_pagos,
        'tempo_medio_contratar': tempo_medio_contratar,
        'freelancers_top': freelancers_top,
        'categorias_top': categorias_top,
        'media_avaliacoes': media_avaliacoes,
        'taxa_conclusao': taxa_conclusao,
    }

def _user_por_email(cursor, email, senha_hash, role):
    cursor.execute('SELECT id FROM users WHERE LOWER(TRIM(email)) = ?', (email.lower(),))
    row = cursor.fetchone()
    if row:
        return row['id']
    cursor.execute(
        'INSERT INTO users (email, senha, role, ativo) VALUES (?, ?, ?, 1)',
        (email, senha_hash, role),
    )
    return cursor.lastrowid


def inserir_dados_exemplo():
    """Preenche a vitrine com empresas, freelancers, notas e vagas de demonstração."""
    conn = criar_conexao()
    cursor = conn.cursor()
    cursor.execute("SELECT COUNT(*) FROM projetos WHERE titulo LIKE 'Vitrine:%'")
    ja_tem_vitrine = cursor.fetchone()[0] >= 8

    senha = hash_password('Demo#2026')
    empresas_demo = [
        ('novaera@conectaserv.demo', 'Nova Era Sistemas', '11222333000181', '(11) 3100-2200',
         'Software house paulista focada em produtos digitais para varejo.', 'Tecnologia', 4.8, 'São Paulo', 'SP'),
        ('atlas@conectaserv.demo', 'Atlas Logística Digital', '22333444000172', '(21) 4002-1010',
         'Operação logística com app próprio de rastreio e entregas.', 'Logística', 4.6, 'Rio de Janeiro', 'RJ'),
        ('verde@conectaserv.demo', 'Verde Saúde Tech', '33444555000163', '(31) 3221-8877',
         'Clínica digital e prontuário eletrônico para redes de saúde.', 'Saúde', 4.9, 'Belo Horizonte', 'MG'),
        ('aurora@conectaserv.demo', 'Aurora Educação', '44555666000154', '(41) 3330-4400',
         'Plataforma de cursos e trilhas para escolas e empresas.', 'Educação', 4.7, 'Curitiba', 'PR'),
        ('norte@conectaserv.demo', 'Norte Agro Connect', '55666777000145', '(92) 3212-9090',
         'Soluções de agronegócio com dashboards de safra e IoT no campo.', 'Agronegócio', 4.5, 'Manaus', 'AM'),
        ('pulse@conectaserv.demo', 'Pulse Fintech', '66777888000136', '(51) 3022-1515',
         'Meios de pagamento e conciliação para PMEs.', 'Finanças', 4.8, 'Porto Alegre', 'RS'),
    ]
    emp_ids = []
    for email, nome, cnpj, tel, desc, setor, nota, cidade, estado in empresas_demo:
        uid = _user_por_email(cursor, email, senha, 'empresa')
        cursor.execute('SELECT id FROM empresas WHERE user_id = ?', (uid,))
        row = cursor.fetchone()
        if row:
            emp_ids.append(row['id'])
            continue
        try:
            cursor.execute(
                '''INSERT INTO empresas
                   (user_id, nome_empresa, cnpj, telefone, descricao, setor, nota_media)
                   VALUES (?, ?, ?, ?, ?, ?, ?)''',
                (uid, nome, cnpj, tel, desc, setor, nota),
            )
            emp_ids.append(cursor.lastrowid)
        except sqlite3.IntegrityError:
            cursor.execute('SELECT id FROM empresas WHERE user_id = ? OR cnpj = ?', (uid, cnpj))
            achou = cursor.fetchone()
            if achou:
                emp_ids.append(achou['id'])

    freelas_demo = [
        ('ana.costa@conectaserv.demo', 'Ana Costa', '11981001001', 'Desenvolvimento Web',
         'React, Next.js, TypeScript, Node.js', 'São Paulo', 'SP', 4.9, 34, 180,
         'Front-end sênior com 8 anos em produtos SaaS. Entregas pontuais e código revisado.'),
        ('bruno.lima@conectaserv.demo', 'Bruno Lima', '11981001002', 'Desenvolvimento Mobile',
         'Flutter, Dart, Firebase, Kotlin', 'Campinas', 'SP', 4.8, 21, 160,
         'Apps Android e iOS publicados na loja. Foco em performance e UX.'),
        ('camila.nunes@conectaserv.demo', 'Camila Nunes', '11981001003', 'Design UI/UX',
         'Figma, Design System, Prototipação, Acessibilidade', 'Florianópolis', 'SC', 5.0, 42, 150,
         'Design de interfaces com testes de usabilidade e Libras em mente.'),
        ('diego.alves@conectaserv.demo', 'Diego Alves', '11981001004', 'Data Science',
         'Python, Pandas, Power BI, SQL', 'Recife', 'PE', 4.7, 18, 170,
         'Dashboards e modelos preditivos para operação e marketing.'),
        ('elena.martins@conectaserv.demo', 'Elena Martins', '11981001005', 'DevOps',
         'AWS, Docker, Kubernetes, GitHub Actions', 'Brasília', 'DF', 4.8, 27, 200,
         'Pipeline CI/CD e redução de custo de nuvem em contas médias.'),
        ('felipe.rocha@conectaserv.demo', 'Felipe Rocha', '11981001006', 'Desenvolvimento Web',
         'PHP, Laravel, MySQL, Vue.js', 'Salvador', 'BA', 4.6, 15, 120,
         'Sistemas internos, APIs REST e lojas virtuais.'),
        ('gabriela.souza@conectaserv.demo', 'Gabriela Souza', '11981001007', 'Consultoria',
         'Product Discovery, Scrum, Métricas', 'Belo Horizonte', 'MG', 4.9, 31, 220,
         'Organiza backlog, rituais e indicadores para times de produto.'),
        ('henrique.dias@conectaserv.demo', 'Henrique Dias', '11981001008', 'Segurança',
         'Pentest, OWASP, LGPD, Cloudflare', 'Curitiba', 'PR', 4.8, 12, 210,
         'Testes de invasão e hardening de aplicações web.'),
        ('isabela.freitas@conectaserv.demo', 'Isabela Freitas', '11981001009', 'Desenvolvimento Mobile',
         'React Native, Expo, TypeScript', 'Fortaleza', 'CE', 4.7, 19, 155,
         'Apps híbridos com publicação nas lojas e push notification.'),
        ('joao.pinto@conectaserv.demo', 'João Pinto', '11981001010', 'Desenvolvimento Web',
         'Python, Flask, Django, PostgreSQL', 'Porto Alegre', 'RS', 4.9, 38, 175,
         'APIs e painéis administrativos. Documentação clara para o cliente.'),
        ('karina.melo@conectaserv.demo', 'Karina Melo', '11981001011', 'Design UI/UX',
         'Illustrator, Branding, Landing pages', 'Goiânia', 'GO', 4.6, 9, 110,
         'Identidade visual e páginas de conversão para startups.'),
        ('lucas.barros@conectaserv.demo', 'Lucas Barros', '11981001012', 'Data Science',
         'SQL Server, ETL, Looker Studio', 'São Paulo', 'SP', 4.5, 14, 140,
         'Integração de dados e relatórios executivos semanais.'),
        ('marina.teixeira@conectaserv.demo', 'Marina Teixeira', '11981001013', 'DevOps',
         'Azure, Terraform, Monitoramento', 'Rio de Janeiro', 'RJ', 4.8, 22, 190,
         'Infra como código e alertas que a operação realmente usa.'),
        ('otavio.ramos@conectaserv.demo', 'Otávio Ramos', '11981001014', 'Desenvolvimento Web',
         'Java, Spring, Angular, Kafka', 'Campinas', 'SP', 4.7, 26, 185,
         'Sistemas de alto volume com filas e autenticação corporativa.'),
    ]
    fr_ids = []
    for email, nome, cpf, esp, hab, cidade, estado, nota, concluidos, hora, bio in freelas_demo:
        uid = _user_por_email(cursor, email, senha, 'freelancer')
        cursor.execute('SELECT id FROM freelancers WHERE user_id = ?', (uid,))
        row = cursor.fetchone()
        if row:
            fr_ids.append(row['id'])
            cursor.execute(
                '''UPDATE freelancers SET nota_media = ?, projetos_concluidos = ?, total_projetos = ?,
                   hourly_rate = ?, status = 'ativo' WHERE id = ?''',
                (nota, concluidos, concluidos + 2, hora, row['id']),
            )
            continue
        try:
            cursor.execute(
                '''INSERT INTO freelancers
                   (user_id, nome_completo, telefone, cpf, cidade, estado, especialidade, habilidades,
                    biografia, hourly_rate, nota_media, projetos_concluidos, total_projetos, status, destaque)
                   VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, 'ativo', ?)''',
                (uid, nome, '(11) 9' + cpf[-8:-4] + '-' + cpf[-4:], cpf, cidade, estado, esp, hab,
                 bio, hora, nota, concluidos, concluidos + 2, 'sim' if nota >= 4.8 else 'nao'),
            )
            fr_ids.append(cursor.lastrowid)
        except (sqlite3.IntegrityError, sqlite3.OperationalError):
            cursor.execute('SELECT id FROM freelancers WHERE user_id = ?', (uid,))
            achou = cursor.fetchone()
            if achou:
                fr_ids.append(achou['id'])

    if len(emp_ids) < 3 or len(fr_ids) < 6:
        conn.commit()
        conn.close()
        return

    if not ja_tem_vitrine:
        vagas = [
            (emp_ids[0], 'Vitrine: Portal de clientes B2B',
             'Área logada para pedidos, notas fiscais e chamados. Layout responsivo e acessível.',
             'Desenvolvimento Web', 'React, Node.js, PostgreSQL', 18000, '45', 'Avançado'),
            (emp_ids[0], 'Vitrine: Landing page da Black Friday',
             'Página de campanha com cronômetro, cupom e integração ao CRM.',
             'Desenvolvimento Web', 'HTML, CSS, JavaScript', 4500, '12', 'Intermediário'),
            (emp_ids[1], 'Vitrine: App de rastreio de entregas',
             'Aplicativo com mapa, status em tempo real e push para o destinatário.',
             'Desenvolvimento Mobile', 'Flutter, Firebase', 22000, '60', 'Avançado'),
            (emp_ids[2], 'Vitrine: Prontuário eletrônico simplificado',
             'Cadastro de pacientes, evolução clínica e exportação em PDF.',
             'Desenvolvimento Web', 'Python, Flask, SQLite', 15000, '40', 'Intermediário'),
            (emp_ids[3], 'Vitrine: Redesign do app de estudos',
             'Novo fluxo de aulas, trilha de progresso e modo alto contraste.',
             'Design UI/UX', 'Figma, Prototipação', 7800, '20', 'Intermediário'),
            (emp_ids[3], 'Vitrine: Relatórios de engajamento',
             'Painel com cohort, retenção e exportação para a diretoria.',
             'Data Science', 'Power BI, SQL, Python', 9600, '25', 'Avançado'),
            (emp_ids[4], 'Vitrine: Dashboard de safra',
             'Indicadores de clima, produtividade e alertas no celular do gestor.',
             'Data Science', 'Looker Studio, SQL', 11200, '30', 'Intermediário'),
            (emp_ids[5], 'Vitrine: Conciliação de pagamentos',
             'Bate cartão, Pix e boleto com divergências destacadas.',
             'Desenvolvimento Web', 'Java, Spring, Angular', 27500, '50', 'Especialista'),
            (emp_ids[5], 'Vitrine: Pentest do internet banking',
             'Varredura OWASP, relatório executivo e plano de correção.',
             'Segurança', 'OWASP, Burp, LGPD', 14000, '18', 'Avançado'),
            (emp_ids[1], 'Vitrine: Automação de DevOps',
             'CI/CD, homologação automática e rollback em um clique.',
             'DevOps', 'Docker, GitHub Actions, AWS', 16500, '28', 'Avançado'),
        ]
        proj_ids = []
        for emp, titulo, desc, cat, hab, orc, prazo, nivel in vagas:
            cursor.execute(
                '''INSERT INTO projetos
                   (empresa_id, titulo, descricao, categoria, habilidades_requeridas,
                    presupuesto, prazo, nivel_experiencia, status, etapa, progresso)
                   VALUES (?, ?, ?, ?, ?, ?, ?, ?, 'aberto', 'publicado', 0)''',
                (emp, titulo, desc, cat, hab, orc, prazo, nivel),
            )
            proj_ids.append(cursor.lastrowid)

        if proj_ids and fr_ids:
            nfr = len(fr_ids)
            npr = len(proj_ids)
            propostas = [
                (proj_ids[0 % npr], fr_ids[0 % nfr], 17500, 40, 'Entrego o portal com testes e documentação da API.'),
                (proj_ids[0 % npr], fr_ids[5 % nfr], 16800, 42, 'Posso reaproveitar um boilerplate Flask + React já usado em B2B.'),
                (proj_ids[2 % npr], fr_ids[1 % nfr], 21000, 55, 'App Flutter com mapa e filas offline.'),
                (proj_ids[4 % npr], fr_ids[2 % nfr], 7400, 18, 'Design system completo e protótipo navegável.'),
                (proj_ids[8 % npr], fr_ids[3 % nfr], 13500, 16, 'Pentest com relatório para diretoria e time técnico.'),
            ]
            for projeto_id, fr, valor, prazo, texto in propostas:
                cursor.execute(
                    '''INSERT INTO propostas (projeto_id, freelancer_id, valor_proposto, prazo_dias, proposta, status)
                       VALUES (?, ?, ?, ?, ?, 'pendente')''',
                    (projeto_id, fr, valor, prazo, texto),
                )

        concluidos = [
            (emp_ids[0], fr_ids[0], 'Vitrine: Site institucional Nova Era',
             'Site institucional com blog e formulário de orçamento.', 4, 5, 5, 5,
             'Entrega rápida e comunicação clara o tempo todo.'),
            (emp_ids[2], fr_ids[2], 'Vitrine: Identidade do app Verde Saúde',
             'Identidade visual e telas do aplicativo de triagem.', 5, 5, 5, 5,
             'Design impecável. Pacientes entenderam o fluxo na hora.'),
            (emp_ids[5], fr_ids[4], 'Vitrine: Migração para a nuvem',
             'Contas AWS organizadas e pipeline de deploy.', 5, 4, 5, 4,
             'Reduzimos 22% do custo de nuvem no primeiro mês.'),
            (emp_ids[3], fr_ids[3], 'Vitrine: Painel pedagógico',
             'Indicadores de conclusão de aulas por turma.', 4, 5, 4, 5,
             'Os coordenadores passaram a usar o painel toda semana.'),
            (emp_ids[1], fr_ids[8], 'Vitrine: App do motorista',
             'Checklist de entrega e foto da ocorrência.', 5, 4, 5, 4,
             'Motoristas adotaram o app sem treinamento longo.'),
        ]
        for emp, fr, titulo, desc, nq, np, nc, nport, comentario in concluidos:
            cursor.execute(
                '''INSERT INTO projetos
                   (empresa_id, titulo, descricao, categoria, habilidades_requeridas,
                    presupuesto, prazo, nivel_experiencia, status, etapa, progresso, freelancer_contratado_id)
                   VALUES (?, ?, ?, 'Desenvolvimento Web', 'React, Python', 12000, '30', 'Intermediário',
                           'concluido', 'concluido', 100, ?)''',
                (emp, titulo, desc, fr),
            )
            pid = cursor.lastrowid
            cursor.execute(
                '''INSERT INTO avaliacoes
                   (projeto_id, freelancer_id, empresa_id, nota_qualidade, nota_prazo, nota_comunicacao, nota_portfolio, comentario)
                   VALUES (?, ?, ?, ?, ?, ?, ?, ?)''',
                (pid, fr, emp, nq, np, nc, nport, comentario),
            )
            cursor.execute(
                '''INSERT INTO avaliacoes_empresa
                   (projeto_id, empresa_id, freelancer_id, nota_satisfacao, nota_profissionalismo, nota_portfolio, comentario)
                   VALUES (?, ?, ?, ?, ?, ?, ?)''',
                (pid, emp, fr, 5, 5, 4, 'Empresa objetiva, pagou no combinado e deu feedback útil.'),
            )

    conn.commit()
    conn.close()
    print('Vitrine de demonstração pronta (notas, vagas e profissionais).')

def inicializar_banco():
    """Inicializa o banco de dados"""
    garantir_banco_persistente()
    criar_tabelas()
    inserir_dados_exemplo()

if __name__ == '__main__':
    inicializar_banco()