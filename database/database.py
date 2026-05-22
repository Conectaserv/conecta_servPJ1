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


def garantir_banco_persistente():
    """
    Na primeira execução com DATABASE_PATH (disco Render), copia o .db do deploy
    se o arquivo persistente ainda não existir.
    """
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

def limpar_cadastro_incompleto_empresa(cursor, email):
    """Remove cadastro pela metade (falha anterior / banco travado)."""
    email = normalizar_email(email)
    cursor.execute('''
        DELETE FROM users
        WHERE id IN (
            SELECT u.id
            FROM users u
            LEFT JOIN empresas e ON e.user_id = u.id
            WHERE LOWER(TRIM(u.email)) = ? AND e.id IS NULL
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
    return hashlib.sha256(password.encode()).hexdigest()

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
    
    # Tabela de contratos (nova)
    cursor.execute('''
        CREATE TABLE IF NOT EXISTS contratos (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            proposta_id INTEGER UNIQUE NOT NULL,
            status TEXT DEFAULT 'aguardando',
            data_inicio TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
            data_conclusao TIMESTAMP,
            termos TEXT,
            FOREIGN KEY (proposta_id) REFERENCES propostas(id)
        )
    ''')
    
    # Tabela de notificações (nova)
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
    
    # Índices para performance
    cursor.execute('CREATE INDEX IF NOT EXISTS idx_users_email ON users(email)')
    cursor.execute('CREATE INDEX IF NOT EXISTS idx_empresas_user_id ON empresas(user_id)')
    cursor.execute('CREATE INDEX IF NOT EXISTS idx_freelancers_user_id ON freelancers(user_id)')
    cursor.execute('CREATE INDEX IF NOT EXISTS idx_projetos_empresa_id ON projetos(empresa_id)')
    cursor.execute('CREATE INDEX IF NOT EXISTS idx_propostas_projeto_id ON propostas(projeto_id)')
    cursor.execute('CREATE INDEX IF NOT EXISTS idx_avaliacoes_freelancer_id ON avaliacoes(freelancer_id)')
    cursor.execute('CREATE INDEX IF NOT EXISTS idx_mensagens_destinatario ON mensagens(destinatario_id, destinatario_tipo)')

    
    conn.commit()
    conn.close()
    print("Banco de dados criado com sucesso!")

def inserir_dados_exemplo():
    """Insere dados de exemplo no banco de dados"""
    conn = criar_conexao()
    cursor = conn.cursor()
    
    # Verificar se já existem dados
    cursor.execute("SELECT COUNT(*) FROM empresas")
    if cursor.fetchone()[0] > 0:
        conn.close()
        return
    
    # Inserir usuários exemplo
    exemplo_senha = hash_password('senha123')
    cursor.execute('''
        INSERT INTO users (email, senha, role)
        VALUES (?, ?, ?)
    ''', ('contato@techinnovators.com', exemplo_senha, 'empresa'))
    
    empresa_user_id = cursor.lastrowid
    
    # Inserir empresa exemplo
    cursor.execute('''
        INSERT INTO empresas (user_id, nome_empresa, cnpj, telefone, descricao, setor)
        VALUES (?, ?, ?, ?, ?, ?)
    ''', (empresa_user_id, 'Tech Innovators Ltda', '12.345.678/0001-90', '(11) 99999-9999', 'Empresa de desenvolvimento de software', 'Tecnologia'))
    
    # Inserir freelancers exemplos
    freelancers_data = [
        ('joao@email.com', 'João Silva', 'Desenvolvedor Full Stack', 'JavaScript, Python, React, Node.js', '3 anos de experiencia em desenvolvimento web'),
        ('maria@email.com', 'Maria Santos', 'Desenvolvedora Mobile', 'Flutter, React Native, Swift, Kotlin', 'Especialista em apps mobile'),
        ('pedro@email.com', 'Pedro Oliveira', 'Analista de Sistemas', 'SQL, Oracle, MySQL, PowerBI', '10 anos de experiencia em banco de dados')
    ]
    
    for email, nome, especialidade, habilidades, biografia in freelancers_data:
        cursor.execute('''
            INSERT INTO users (email, senha, role)
            VALUES (?, ?, ?)
        ''', (email, exemplo_senha, 'freelancer'))
        
        freelancer_user_id = cursor.lastrowid
        
        cursor.execute('''
            INSERT INTO freelancers (user_id, nome_completo, especialidade, habilidades, biografia)
            VALUES (?, ?, ?, ?, ?)
        ''', (freelancer_user_id, nome, especialidade, habilidades, biografia))

    
    # Inserir projetos exemplos
    projetos = [
        (1, 'Desenvolvimento de Site Institucional', 'Site institucional responsivo com CMS',
         'Desenvolvimento Web', 'HTML, CSS, JavaScript, PHP', 5000.00, '2026-06-30', 'Intermediario'),
        (1, 'App Mobile para Delivery', 'Aplicativo para entrega de produtos',
         'Desenvolvimento Mobile', 'Flutter, Firebase', 15000.00, '2026-08-30', 'Avancado'),
        (1, 'Sistema de Gestao Empresarial', 'Sistema completo de gestao',
         'Desenvolvimento Web', 'React, Node.js, PostgreSQL', 25000.00, '2026-10-30', 'Avancado')
    ]
    
    for p in projetos:
        cursor.execute('''
            INSERT INTO projetos (empresa_id, titulo, descricao, categoria, habilidades_requeridas, presupuesto, prazo, nivel_experiencia)
            VALUES (?, ?, ?, ?, ?, ?, ?, ?)
        ''', p)
    
    conn.commit()
    conn.close()
    print("Dados de exemplo inseridos com sucesso!")

def inicializar_banco():
    """Inicializa o banco de dados"""
    garantir_banco_persistente()
    criar_tabelas()
    inserir_dados_exemplo()

if __name__ == '__main__':
    inicializar_banco()