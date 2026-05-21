from flask import Flask, render_template, request, redirect, url_for, session, jsonify, flash, get_flashed_messages
import sqlite3
import os
import secrets
from functools import wraps
from datetime import datetime, timedelta

from utils.email_service import enviar_email_proposta_aceita
from textos_pt import (
    MSG,
    cadastro_sucesso,
    conta_existe_cnpj,
    conta_existe_email,
    erro_salvar_cadastro,
    obter_textos,
    proposta_aceita_email_erro,
)

def carregar_env_local():
    env_path = os.path.join(os.path.dirname(__file__), '.env')
    if not os.path.exists(env_path):
        return
    with open(env_path, encoding='utf-8') as arquivo:
        for linha in arquivo:
            linha = linha.strip()
            if not linha or linha.startswith('#') or '=' not in linha:
                continue
            chave, valor = linha.split('=', 1)
            os.environ.setdefault(chave.strip(), valor.strip().strip('"\''))

def obter_secret_key():
    if os.environ.get('SECRET_KEY'):
        return os.environ['SECRET_KEY']
    arquivo = os.path.join(os.path.dirname(__file__), '.secret_key')
    if os.path.exists(arquivo):
        with open(arquivo, encoding='utf-8') as f:
            return f.read().strip()
    chave = secrets.token_hex(32)
    with open(arquivo, 'w', encoding='utf-8') as f:
        f.write(chave)
    return chave

carregar_env_local()

app = Flask(__name__)
app.secret_key = obter_secret_key()
app.config['PERMANENT_SESSION_LIFETIME'] = timedelta(hours=24)
app.config['SESSION_COOKIE_HTTPONLY'] = True
app.config['SESSION_COOKIE_SAMESITE'] = 'Lax'

# Importar banco de dados
from database.database import (
    criar_conexao,
    inicializar_banco,
    hash_password,
    normalizar_email,
    email_ja_cadastrado,
    cnpj_ja_cadastrado,
    cpf_ja_cadastrado,
    buscar_empresa_cadastrada,
    usuario_orfao_empresa,
    inserir_perfil_empresa,
    inserir_perfil_freelancer,
    atualizar_senha_usuario,
    registrar_empresa,
    cnpj_valido,
    DB_PATH,
)

# Inicializar banco de dados
inicializar_banco()

ALERT_CLASS_MAP = {
    'sucesso': 'success',
    'erro': 'error',
    'aviso': 'warning',
    'info': 'info',
    'conta_existe': 'warning',
}

@app.context_processor
def inject_globals():
    """Disponibiliza mensagens flash e textos em português em todos os templates."""
    return {
        'flash_messages': get_flashed_messages(with_categories=True),
        'alert_class': lambda category: ALERT_CLASS_MAP.get(category, category),
        'textos': obter_textos(),
        't': obter_textos(),
    }

# ==================== FUNÇÕES AUXILIARES ====================

def flash_erro_cadastro(erro, tipo_doc='CNPJ'):
    """Mensagem clara para falhas no cadastro."""
    msg = str(erro).lower()
    if 'locked' in msg or 'busy' in msg:
        flash(MSG.BANCO_BLOQUEADO, 'erro')
    elif 'cnpj' in msg:
        flash(MSG.CNPJ_CADASTRADO, 'erro')
    elif 'cpf' in msg:
        flash(MSG.CPF_CADASTRADO, 'erro')
    elif 'email' in msg or 'users.email' in msg:
        flash(MSG.EMAIL_CADASTRADO, 'erro')
    elif 'not null' in msg:
        flash(MSG.ERRO_SALVAR_CADASTRO, 'erro')
    else:
        flash(erro_salvar_cadastro(erro), 'erro')

def format_freelancer_data(row):
    """Formatar dados do freelancer"""
    if row is None:
        return None
    data = dict(row)
    nome_completo = data.get('nome_completo', '')
    partes = nome_completo.split()
    data['nome'] = partes[0] if partes else ''
    data['sobrenome'] = partes[-1] if len(partes) > 1 else ''
    return data

def format_empresa_data(row):
    """Formatar dados da empresa"""
    if row is None:
        return None
    data = dict(row)
    data['nome'] = data.get('nome_empresa')
    data['satisfacao'] = data.get('nota_media', 0)
    return data

def format_projeto_data(row):
    """Formatar dados do projeto"""
    if row is None:
        return None
    data = dict(row)
    if 'presupuesto' in data:
        data['orcamento'] = data['presupuesto']
    return data

def atualizar_nota_media_freelancer(freelancer_id):
    """Atualiza a nota média do freelancer"""
    conn = criar_conexao()
    cursor = conn.cursor()
    cursor.execute('''
        SELECT AVG((nota_qualidade + nota_prazo + nota_comunicacao + nota_portfolio) / 4.0) as media
        FROM avaliacoes
        WHERE freelancer_id = ?
    ''', (freelancer_id,))
    media = cursor.fetchone()[0] or 0
    cursor.execute('UPDATE freelancers SET nota_media = ? WHERE id = ?', (round(media, 2), freelancer_id))
    conn.commit()
    conn.close()

def autenticar_login(email, senha, role_esperado):
    """
    Autentica usuário no portal correto (empresa ou freelancer).
    Usa o perfil real (tabela empresas/freelancers), não só o campo role que pode estar desatualizado.
    Retorna (dados_usuario, mensagem_erro).
    """
    email = email.strip().lower()
    role_esperado = role_esperado.strip().lower()

    conn = criar_conexao()
    cursor = conn.cursor()
    cursor.execute('SELECT * FROM users WHERE LOWER(email) = ?', (email,))
    user = cursor.fetchone()

    if not user or hash_password(senha) != user['senha']:
        conn.close()
        return None, MSG.EMAIL_SENHA_INCORRETOS

    if not user['ativo']:
        conn.close()
        return None, MSG.CONTA_DESATIVADA

    cursor.execute('SELECT id FROM empresas WHERE user_id = ?', (user['id'],))
    tem_empresa = cursor.fetchone() is not None
    cursor.execute('SELECT id FROM freelancers WHERE user_id = ?', (user['id'],))
    tem_freelancer = cursor.fetchone() is not None

    if role_esperado == 'empresa':
        if not tem_empresa:
            conn.close()
            if tem_freelancer:
                return None, MSG.EMAIL_E_FREELANCER
            return None, MSG.PERFIL_EMPRESA_NAO
        if user['role'] != 'empresa':
            cursor.execute("UPDATE users SET role = 'empresa' WHERE id = ?", (user['id'],))
            conn.commit()
        cursor.execute('''
            SELECT u.*, e.id as empresa_id, e.nome_empresa
            FROM users u
            JOIN empresas e ON u.id = e.user_id
            WHERE u.id = ?
        ''', (user['id'],))
    else:
        if not tem_freelancer:
            conn.close()
            if tem_empresa:
                return None, MSG.EMAIL_E_EMPRESA
            return None, MSG.PERFIL_FREELANCER_NAO
        if user['role'] != 'freelancer':
            cursor.execute("UPDATE users SET role = 'freelancer' WHERE id = ?", (user['id'],))
            conn.commit()
        cursor.execute('''
            SELECT u.*, f.id as freelancer_id, f.nome_completo
            FROM users u
            JOIN freelancers f ON u.id = f.user_id
            WHERE u.id = ?
        ''', (user['id'],))

    dados = cursor.fetchone()
    conn.close()

    if not dados:
        return None, MSG.PERFIL_NAO_ENCONTRADO

    return dados, None

def atualizar_nota_media_empresa(empresa_id):
    """Atualiza a nota média da empresa"""
    conn = criar_conexao()
    cursor = conn.cursor()
    cursor.execute('''
        SELECT AVG((nota_satisfacao + nota_profissionalismo + nota_portfolio) / 3.0) as media
        FROM avaliacoes_empresa
        WHERE empresa_id = ?
    ''', (empresa_id,))
    media = cursor.fetchone()[0] or 0
    cursor.execute('UPDATE empresas SET nota_media = ? WHERE id = ?', (round(media, 2), empresa_id))
    conn.commit()
    conn.close()

# ==================== DECORATORS DE AUTENTICAÇÃO ====================

def login_required(roles=None):
    """Decorator para proteger rotas com autenticação"""
    def decorator(f):
        @wraps(f)
        def decorated_function(*args, **kwargs):
            if 'user_id' not in session:
                flash(MSG.LOGIN_NECESSARIO, 'erro')
                return redirect(url_for('index'))
            
            if roles and session.get('role') not in roles:
                flash(MSG.SEM_PERMISSAO, 'erro')
                return redirect(url_for('index'))
            
            return f(*args, **kwargs)
        return decorated_function
    return decorator

def freelancer_required(f):
    """Decorator para rotas exclusivas de freelancers"""
    @wraps(f)
    def decorated_function(*args, **kwargs):
        if 'user_id' not in session or session.get('role') != 'freelancer':
            flash(MSG.APENAS_FREELANCER, 'erro')
            return redirect(url_for('index'))
        return f(*args, **kwargs)
    return decorated_function

def empresa_required(f):
    """Decorator para rotas exclusivas de empresas"""
    @wraps(f)
    def decorated_function(*args, **kwargs):
        if 'user_id' not in session or session.get('role') != 'empresa' or not session.get('empresa_id'):
            flash(MSG.LOGIN_EMPRESA, 'erro')
            return redirect(url_for('login_empresa'))
        return f(*args, **kwargs)
    return decorated_function

# ==================== ROTAS PRINCIPAIS ====================

@app.route('/')
def index():
    """Página inicial"""
    conn = criar_conexao()
    cursor = conn.cursor()
    
    cursor.execute("SELECT COUNT(*) FROM freelancers WHERE status = 'ativo'")
    total_freelancers = cursor.fetchone()[0]
    
    cursor.execute("SELECT COUNT(*) FROM projetos WHERE status = 'aberto'")
    total_projetos = cursor.fetchone()[0]
    
    cursor.execute('''
        SELECT p.*, e.nome_empresa 
        FROM projetos p 
        JOIN empresas e ON p.empresa_id = e.id 
        WHERE p.status = 'aberto' 
        ORDER BY p.data_criacao DESC 
        LIMIT 6
    ''')
    projetos_recentes = cursor.fetchall()
    
    conn.close()
    
    return render_template('index.html', 
                         freelancers=total_freelancers, 
                         projetos=total_projetos,
                         projetos_recentes=projetos_recentes)

@app.route('/sobre')
def sobre():
    """Página sobre"""
    return render_template('sobre.html')

@app.route('/acessibilidade')
def acessibilidade():
    """Página de acessibilidade"""
    return render_template('acessibilidade.html')

# ==================== ROTAS DE CADASTRO ====================

@app.route('/cadastro-empresa', methods=['GET', 'POST'])
def cadastro_empresa():
    """Cadastro de empresa"""
    if request.method == 'POST':
        nome_empresa = request.form.get('nome_empresa', '').strip()
        cnpj = request.form.get('cnpj', '').strip()
        email = normalizar_email(request.form.get('email', ''))
        senha = request.form.get('senha', '').strip()
        telefone = request.form.get('telefone', '').strip()
        descricao = request.form.get('descricao', '').strip()
        setor = request.form.get('setor', '').strip()
        
        if not all([nome_empresa, cnpj, email, senha]):
            flash(MSG.CAMPOS_OBRIGATORIOS, 'erro')
            return redirect(url_for('cadastro_empresa'))

        if not cnpj_valido(cnpj):
            flash(MSG.CNPJ_INVALIDO, 'erro')
            return redirect(url_for('cadastro_empresa'))
        
        try:
            resultado = registrar_empresa(
                nome_empresa, cnpj, email, senha, telefone, descricao, setor,
            )
        except sqlite3.OperationalError as e:
            flash_erro_cadastro(e, 'CNPJ')
            return redirect(url_for('cadastro_empresa'))
        except Exception as e:
            flash_erro_cadastro(e, 'CNPJ')
            return redirect(url_for('cadastro_empresa'))

        if resultado['status'] == 'duplicado':
            dados_dup = resultado['dados']
            if resultado['tipo'] == 'email':
                flash(conta_existe_email(dados_dup['nome_empresa']), 'conta_existe')
            else:
                flash(conta_existe_cnpj(dados_dup['nome_empresa'], dados_dup['email']), 'conta_existe')
            return redirect(url_for('cadastro_empresa'))

        if resultado['status'] == 'freelancer':
            flash(MSG.EMAIL_FREELANCER, 'erro')
            return redirect(url_for('cadastro_empresa'))

        flash(cadastro_sucesso(resultado['email']), 'sucesso')
        return redirect(url_for('cadastro_empresa'))
    
    return render_template('cadastro_empresa.html')

@app.route('/cadastro-freelancer', methods=['GET', 'POST'])
def cadastro_freelancer():
    """Cadastro de freelancer"""
    if request.method == 'POST':
        nome_completo = request.form.get('nome_completo', '').strip()
        email = normalizar_email(request.form.get('email', ''))
        senha = request.form.get('senha', '').strip()
        telefone = request.form.get('telefone', '').strip()
        cpf = request.form.get('cpf', '').strip()
        cidade = request.form.get('cidade', '').strip()
        estado = request.form.get('estado', '').strip()
        especialidade = request.form.get('especialidade', '').strip()
        habilidades = request.form.get('habilidades', '').strip()
        biografia = request.form.get('biografia', '').strip()
        hourly_rate = request.form.get('hourly_rate', '0').strip() or '0'
        
        if not all([nome_completo, email, senha, cpf]):
            flash(MSG.CAMPOS_OBRIGATORIOS, 'erro')
            return redirect(url_for('cadastro_freelancer'))
        
        conn = criar_conexao()
        cursor = conn.cursor()
        
        if email_ja_cadastrado(cursor, email):
            conn.close()
            flash(MSG.EMAIL_CADASTRADO, 'erro')
            return redirect(url_for('cadastro_freelancer'))
        if cpf_ja_cadastrado(cursor, cpf):
            conn.close()
            flash(MSG.CPF_CADASTRADO, 'erro')
            return redirect(url_for('cadastro_freelancer'))
        
        senha_hash = hash_password(senha)
        
        try:
            cursor.execute('''
                INSERT INTO users (email, senha, role, ativo)
                VALUES (?, ?, ?, ?)
            ''', (email, senha_hash, 'freelancer', 1))
            user_id = cursor.lastrowid
            inserir_perfil_freelancer(
                cursor, user_id, nome_completo, email, senha_hash, telefone, cpf,
                cidade, estado, especialidade, habilidades, biografia, hourly_rate,
            )
            conn.commit()
            cursor.execute('SELECT id FROM freelancers WHERE user_id = ?', (user_id,))
            if not cursor.fetchone():
                raise RuntimeError('Perfil do freelancer não foi gravado no banco.')
            conn.close()
            flash(cadastro_sucesso(email), 'sucesso')
            return redirect(url_for('cadastro_freelancer'))
        except sqlite3.IntegrityError as e:
            conn.rollback()
            conn.close()
            flash_erro_cadastro(e, 'CPF')
            return redirect(url_for('cadastro_freelancer'))
        except sqlite3.OperationalError as e:
            conn.rollback()
            conn.close()
            flash_erro_cadastro(e, 'CPF')
            return redirect(url_for('cadastro_freelancer'))
        except Exception as e:
            conn.rollback()
            conn.close()
            flash_erro_cadastro(e, 'CPF')
            return redirect(url_for('cadastro_freelancer'))
    
    return render_template('cadastro_freelancer.html')

# ==================== ROTAS DE LOGIN ====================

@app.route('/login-empresa', methods=['GET', 'POST'])
def login_empresa():
    """Login de empresa"""
    if request.method == 'GET':
        if session.get('role') == 'empresa' and session.get('empresa_id'):
            return redirect(url_for('dashboard_empresa'))

    if request.method == 'POST':
        email = normalizar_email(request.form.get('email', ''))
        senha = request.form.get('senha', '').strip()

        if not email or not senha:
            flash(MSG.EMAIL_SENHA_OBRIGATORIOS, 'erro')
            return render_template('login_empresa.html')

        user, erro = autenticar_login(email, senha, 'empresa')
        if erro:
            flash(erro, 'erro')
            return render_template('login_empresa.html')

        session.clear()
        session.permanent = True
        session['user_id'] = user['id']
        session['role'] = 'empresa'
        session['empresa_id'] = user['empresa_id']
        session['empresa_nome'] = user['nome_empresa']
        session['tipo_usuario'] = 'empresa'

        conn = criar_conexao()
        cursor = conn.cursor()
        cursor.execute('UPDATE users SET ultimo_login = CURRENT_TIMESTAMP WHERE id = ?', (user['id'],))
        conn.commit()
        conn.close()

        return redirect(url_for('dashboard_empresa'))

    return render_template('login_empresa.html')

@app.route('/login-freelancer', methods=['GET', 'POST'])
def login_freelancer():
    """Login de freelancer"""
    if request.method == 'GET':
        if session.get('role') == 'freelancer' and session.get('freelancer_id'):
            return redirect(url_for('dashboard_freelancer'))

    if request.method == 'POST':
        email = normalizar_email(request.form.get('email', ''))
        senha = request.form.get('senha', '').strip()

        if not email or not senha:
            flash(MSG.EMAIL_SENHA_OBRIGATORIOS, 'erro')
            return render_template('login_freelancer.html')

        user, erro = autenticar_login(email, senha, 'freelancer')
        if erro:
            flash(erro, 'erro')
            return render_template('login_freelancer.html')

        session.clear()
        session.permanent = True
        session['user_id'] = user['id']
        session['role'] = 'freelancer'
        session['freelancer_id'] = user['freelancer_id']
        session['freelancer_nome'] = user['nome_completo']
        session['tipo_usuario'] = 'freelancer'

        conn = criar_conexao()
        cursor = conn.cursor()
        cursor.execute('UPDATE users SET ultimo_login = CURRENT_TIMESTAMP WHERE id = ?', (user['id'],))
        conn.commit()
        conn.close()

        return redirect(url_for('dashboard_freelancer'))

    return render_template('login_freelancer.html')

@app.route('/logout')
def logout():
    """Logout"""
    session.clear()
    flash(MSG.LOGOUT_SUCESSO, 'sucesso')
    return redirect(url_for('index'))

@app.route('/esqueceu-senha/<tipo>', methods=['GET', 'POST'])
def esqueceu_senha(tipo):
    """Recuperar senha"""
    if tipo not in ['empresa', 'freelancer']:
        return redirect(url_for('index'))

    if request.method == 'POST':
        email = normalizar_email(request.form.get('email', ''))
        nova_senha = request.form.get('nova_senha', '').strip()
        if not email or not nova_senha:
            flash(MSG.EMAIL_NOVA_SENHA, 'erro')
            return render_template('recuperar_senha.html', tipo=tipo)

        conn = criar_conexao()
        cursor = conn.cursor()
        
        cursor.execute(
            'SELECT id FROM users WHERE LOWER(TRIM(email)) = ? AND role = ?',
            (email, tipo),
        )
        usuario = cursor.fetchone()
        
        if usuario:
            nova_senha_hash = hash_password(nova_senha)
            atualizar_senha_usuario(cursor, usuario['id'], email, nova_senha_hash, tipo)
            conn.commit()
            conn.close()
            flash(MSG.SENHA_REDEFINIDA, 'sucesso')
            return redirect(url_for('login_empresa' if tipo == 'empresa' else 'login_freelancer'))

        conn.close()
        flash(MSG.EMAIL_NAO_ENCONTRADO, 'erro')

    return render_template('recuperar_senha.html', tipo=tipo)

# ==================== DASHBOARDS ====================

@app.route('/dashboard-empresa')
@empresa_required
def dashboard_empresa():
    """Dashboard da empresa"""
    conn = criar_conexao()
    cursor = conn.cursor()
    
    empresa_id = session['empresa_id']
    
    cursor.execute('SELECT * FROM empresas WHERE id = ?', (empresa_id,))
    empresa = format_empresa_data(cursor.fetchone())
    
    cursor.execute('SELECT *, presupuesto AS orcamento FROM projetos WHERE empresa_id = ? ORDER BY data_criacao DESC', (empresa_id,))
    meus_projetos = [format_projeto_data(p) for p in cursor.fetchall()]
    
    cursor.execute('''
        SELECT p.id, pr.titulo AS projeto_titulo, f.nome_completo AS freelancer_nome,
               p.valor_proposto AS valor, p.prazo_dias AS prazo, p.proposta, p.status, p.freelancer_id
        FROM propostas p
        JOIN projetos pr ON p.projeto_id = pr.id
        JOIN freelancers f ON p.freelancer_id = f.id
        WHERE pr.empresa_id = ?
        ORDER BY p.data_proposta DESC
    ''', (empresa_id,))
    propostas = [dict(proposta) for proposta in cursor.fetchall()]
    
    conn.close()
    
    return render_template('dashboard_empresa.html', empresa=empresa, projetos=meus_projetos, propostas=propostas)

@app.route('/dashboard-freelancer')
@freelancer_required
def dashboard_freelancer():
    """Dashboard do freelancer"""
    conn = criar_conexao()
    cursor = conn.cursor()
    
    freelancer_id = session['freelancer_id']
    
    cursor.execute('''
        SELECT p.id AS proposta_id, pr.id AS projeto_id, pr.titulo AS projeto_titulo, pr.descricao, pr.categoria,
               pr.presupuesto AS orcamento, p.valor_proposto AS valor, p.prazo_dias AS prazo,
               p.status AS status, p.projeto_id, e.nome_empresa
        FROM propostas p
        JOIN projetos pr ON p.projeto_id = pr.id
        JOIN empresas e ON pr.empresa_id = e.id
        WHERE p.freelancer_id = ?
        ORDER BY p.data_proposta DESC
    ''', (freelancer_id,))
    minhas_propostas = [dict(proposta) for proposta in cursor.fetchall()]
    
    cursor.execute('''
        SELECT p.*, e.nome_empresa, p.presupuesto AS orcamento
        FROM projetos p 
        JOIN empresas e ON p.empresa_id = e.id 
        WHERE p.status = 'aberto' 
        ORDER BY p.data_criacao DESC
    ''')
    projetos_disponiveis = [format_projeto_data(projeto) for projeto in cursor.fetchall()]
    
    cursor.execute('SELECT * FROM freelancers WHERE id = ?', (freelancer_id,))
    freelancer = format_freelancer_data(cursor.fetchone())
    
    conn.close()
    
    return render_template('dashboard_freelancer.html', 
                         propostas=minhas_propostas,
                         projetos_disponiveis=projetos_disponiveis,
                         freelancer=freelancer)

# ==================== ROTAS DE PROJETOS ====================

@app.route('/projetos')
def projetos():
    """Lista de projetos"""
    conn = criar_conexao()
    cursor = conn.cursor()
    
    categoria = request.args.get('categoria')
    nivel = request.args.get('nivel')
    
    query = '''
        SELECT p.*, e.nome_empresa, p.presupuesto AS orcamento
        FROM projetos p 
        JOIN empresas e ON p.empresa_id = e.id 
        WHERE p.status = 'aberto'
    '''
    params = []
    
    if categoria:
        query += ' AND p.categoria = ?'
        params.append(categoria)
    if nivel:
        query += ' AND p.nivel_experiencia = ?'
        params.append(nivel)
    
    query += ' ORDER BY p.data_criacao DESC'
    
    cursor.execute(query, params)
    projetos_list = [format_projeto_data(projeto) for projeto in cursor.fetchall()]
    
    conn.close()
    
    return render_template('projetos.html', projetos=projetos_list)

@app.route('/projeto/<int:projeto_id>')
def detalhes_projeto(projeto_id):
    """Detalhes do projeto"""
    conn = criar_conexao()
    cursor = conn.cursor()
    
    cursor.execute('''
        SELECT p.*, e.nome_empresa, e.descricao as empresa_descricao, e.nota_media as empresa_nota, 
               e.data_cadastro as empresa_data, p.presupuesto AS orcamento
        FROM projetos p 
        JOIN empresas e ON p.empresa_id = e.id 
        WHERE p.id = ?
    ''', (projeto_id,))
    projeto = format_projeto_data(cursor.fetchone())
    
    if not projeto:
        conn.close()
        flash(MSG.PROJETO_NAO_ENCONTRADO, 'erro')
        return redirect(url_for('projetos'))
    
    propostas = []
    if 'empresa_id' in session and session['empresa_id'] == projeto['empresa_id']:
        cursor.execute('''
            SELECT p.*, f.nome_completo AS freelancer_nome
            FROM propostas p
            JOIN freelancers f ON p.freelancer_id = f.id
            WHERE p.projeto_id = ?
            ORDER BY p.data_proposta DESC
        ''', (projeto_id,))
        propostas = [dict(proposta) for proposta in cursor.fetchall()]
    
    ja_enviou = False
    proposta_aceita_id = None
    if 'freelancer_id' in session:
        cursor.execute('''
            SELECT id, status FROM propostas
            WHERE projeto_id = ? AND freelancer_id = ?
        ''', (projeto_id, session['freelancer_id']))
        minha_proposta = cursor.fetchone()
        if minha_proposta:
            ja_enviou = True
            if minha_proposta['status'] == 'aceita':
                proposta_aceita_id = minha_proposta['id']
    
    conn.close()
    
    return render_template('detalhes_projeto.html', projeto=projeto, ja_enviou=ja_enviou,
                         propostas=propostas, proposta_aceita_id=proposta_aceita_id)

@app.route('/aceitar-proposta/<int:proposta_id>', methods=['POST'])
@empresa_required
def aceitar_proposta(proposta_id):
    """Aceita proposta de freelancer para um projeto"""
    conn = criar_conexao()
    cursor = conn.cursor()
    cursor.execute('''
        SELECT p.*, proj.empresa_id, proj.titulo,
               f.nome_completo AS freelancer_nome, f.telefone AS freelancer_telefone,
               uf.email AS freelancer_email,
               e.nome_empresa AS empresa_nome, e.telefone AS empresa_telefone,
               ue.email AS empresa_email
        FROM propostas p
        JOIN projetos proj ON p.projeto_id = proj.id
        JOIN freelancers f ON p.freelancer_id = f.id
        JOIN users uf ON f.user_id = uf.id
        JOIN empresas e ON proj.empresa_id = e.id
        JOIN users ue ON e.user_id = ue.id
        WHERE p.id = ?
    ''', (proposta_id,))
    proposta = cursor.fetchone()

    if not proposta or proposta['empresa_id'] != session['empresa_id']:
        conn.close()
        flash(MSG.PROPOSTA_NAO_ENCONTRADA, 'erro')
        return redirect(url_for('dashboard_empresa'))

    if proposta['status'] == 'aceita':
        conn.close()
        return redirect(url_for('servico_aceito', proposta_id=proposta_id))

    cursor.execute('UPDATE propostas SET status = ? WHERE id = ?', ('aceita', proposta_id))
    cursor.execute('UPDATE projetos SET status = ? WHERE id = ?', ('andamento', proposta['projeto_id']))
    conn.commit()
    conn.close()

    ok, msg_email = enviar_email_proposta_aceita(
        proposta['freelancer_email'],
        proposta['freelancer_nome'],
        proposta['titulo'],
        proposta['prazo_dias'],
        proposta['valor_proposto'],
        proposta['empresa_nome'],
        proposta['empresa_email'],
        proposta['empresa_telefone'],
    )

    if ok:
        flash(MSG.PROPOSTA_ACEITA, 'sucesso')
    else:
        flash(proposta_aceita_email_erro(msg_email), 'erro')

    return redirect(url_for('servico_aceito', proposta_id=proposta_id))

@app.route('/servico-aceito/<int:proposta_id>')
@login_required()
def servico_aceito(proposta_id):
    """Página de confirmação após aceitar proposta"""
    conn = criar_conexao()
    cursor = conn.cursor()
    cursor.execute('''
        SELECT p.*, proj.titulo AS projeto_titulo, proj.presupuesto AS orcamento,
               proj.prazo AS prazo_contrato, proj.empresa_id,
               f.nome_completo AS freelancer_nome, f.telefone AS freelancer_telefone,
               uf.email AS freelancer_email,
               e.nome_empresa AS empresa_nome, e.telefone AS empresa_telefone,
               ue.email AS empresa_email
        FROM propostas p
        JOIN projetos proj ON p.projeto_id = proj.id
        JOIN freelancers f ON p.freelancer_id = f.id
        JOIN users uf ON f.user_id = uf.id
        JOIN empresas e ON proj.empresa_id = e.id
        JOIN users ue ON e.user_id = ue.id
        WHERE p.id = ?
    ''', (proposta_id,))
    proposta = cursor.fetchone()
    conn.close()

    if not proposta:
        flash(MSG.SERVICO_NAO_ENCONTRADO, 'erro')
        return redirect(url_for('index'))

    if 'empresa_id' in session and session['empresa_id'] != proposta['empresa_id']:
        flash(MSG.ACESSO_NEGADO, 'erro')
        return redirect(url_for('index'))
    if 'freelancer_id' in session and session['freelancer_id'] != proposta['freelancer_id']:
        flash(MSG.ACESSO_NEGADO, 'erro')
        return redirect(url_for('index'))

    return render_template('servico_aceito.html', proposta=proposta)

@app.route('/freelancers')
def freelancers():
    """Lista todos os freelancers"""
    conn = criar_conexao()
    cursor = conn.cursor()
    
    especialidade = request.args.get('especialidade')
    
    query = 'SELECT * FROM freelancers WHERE status = ?'
    params = ['ativo']
    
    if especialidade:
        query += ' AND especialidade = ?'
        params.append(especialidade)
    
    query += ' ORDER BY nota_media DESC, projetos_concluidos DESC'
    
    cursor.execute(query, params)
    freelancers = [format_freelancer_data(f) for f in cursor.fetchall()]
    
    conn.close()
    
    return render_template('freelancers.html', freelancers=freelancers)

@app.route('/freelancer/<int:freelancer_id>')
def perfil_freelancer(freelancer_id):
    """Perfil publico do freelancer"""
    conn = criar_conexao()
    cursor = conn.cursor()
    
    cursor.execute('SELECT * FROM freelancers WHERE id = ?', (freelancer_id,))
    freelancer = format_freelancer_data(cursor.fetchone())
    
    cursor.execute('''
        SELECT a.*, e.nome_empresa
        FROM avaliacoes a
        JOIN empresas e ON a.empresa_id = e.id
        WHERE a.freelancer_id = ?
        ORDER BY a.data_avaliacao DESC
        LIMIT 5
    ''', (freelancer_id,))
    avaliacoes = cursor.fetchall()
    
    conn.close()
    
    return render_template('perfil_freelancer.html', freelancer=freelancer, avaliacoes=avaliacoes)

@app.route('/contatar-freelancer/<int:freelancer_id>', methods=['GET', 'POST'])
@empresa_required
def contatar_freelancer(freelancer_id):
    """Página para empresas enviarem mensagem a freelancers"""
    if 'empresa_id' not in session:
        flash(MSG.APENAS_EMPRESA_MSG, 'erro')
        return redirect(url_for('perfil_freelancer', freelancer_id=freelancer_id))

    conn = criar_conexao()
    cursor = conn.cursor()
    cursor.execute('SELECT * FROM freelancers WHERE id = ?', (freelancer_id,))
    freelancer = format_freelancer_data(cursor.fetchone())

    if not freelancer:
        conn.close()
        flash(MSG.FREELANCER_NAO_ENCONTRADO, 'erro')
        return redirect(url_for('projetos'))

    if request.method == 'POST':
        mensagem = request.form.get('mensagem', '').strip()
        if not mensagem:
            flash(MSG.MENSAGEM_VAZIA, 'erro')
        else:
            cursor.execute('''
                INSERT INTO mensagens (remetente_id, destinatario_id, remetente_tipo, destinatario_tipo, mensagem)
                VALUES (?, ?, ?, ?, ?)
            ''', (session['empresa_id'], freelancer_id, 'empresa', 'freelancer', mensagem))
            conn.commit()
            conn.close()
            flash(MSG.MENSAGEM_ENVIADA, 'sucesso')
            return redirect(url_for('perfil_freelancer', freelancer_id=freelancer_id))

    conn.close()
    return render_template('contatar_freelancer.html', freelancer=freelancer)

@app.route('/editar-empresa/<int:empresa_id>', methods=['GET', 'POST'])
@empresa_required
def editar_empresa(empresa_id):
    """Editar dados da empresa"""
    if 'empresa_id' not in session or session['empresa_id'] != empresa_id:
        flash(MSG.ACESSO_NEGADO, 'erro')
        return redirect(url_for('dashboard_empresa'))

    conn = criar_conexao()
    cursor = conn.cursor()
    cursor.execute('SELECT * FROM empresas WHERE id = ?', (empresa_id,))
    empresa = cursor.fetchone()

    if request.method == 'POST':
        nome_empresa = request.form.get('nome_empresa', '').strip()
        telefone = request.form.get('telefone', '').strip()
        descricao = request.form.get('descricao', '').strip()
        setor = request.form.get('setor', '').strip()
        site = request.form.get('site', '').strip()

        cursor.execute('''
            UPDATE empresas
            SET nome_empresa = ?, telefone = ?, descricao = ?, setor = ?, site = ?
            WHERE id = ?
        ''', (nome_empresa, telefone, descricao, setor, site, empresa_id))
        conn.commit()
        conn.close()
        session['empresa_nome'] = nome_empresa
        flash(MSG.PERFIL_EMPRESA_OK, 'sucesso')
        return redirect(url_for('dashboard_empresa'))

    conn.close()
    return render_template('editar_empresa.html', empresa=empresa)

@app.route('/editar-freelancer/<int:freelancer_id>', methods=['GET', 'POST'])
@freelancer_required
def editar_freelancer(freelancer_id):
    """Editar dados do freelancer"""
    if 'freelancer_id' not in session or session['freelancer_id'] != freelancer_id:
        flash(MSG.ACESSO_NEGADO, 'erro')
        return redirect(url_for('dashboard_freelancer'))

    conn = criar_conexao()
    cursor = conn.cursor()
    cursor.execute('SELECT * FROM freelancers WHERE id = ?', (freelancer_id,))
    freelancer = cursor.fetchone()

    if request.method == 'POST':
        nome_completo = request.form.get('nome_completo', '').strip()
        telefone = request.form.get('telefone', '').strip()
        cidade = request.form.get('cidade', '').strip()
        estado = request.form.get('estado', '').strip()
        especialidade = request.form.get('especialidade', '').strip()
        habilidades = request.form.get('habilidades', '').strip()
        biografia = request.form.get('biografia', '').strip()
        portfolio = request.form.get('portfolio', '').strip()
        linkedin = request.form.get('linkedin', '').strip()
        github = request.form.get('github', '').strip()

        cursor.execute('''
            UPDATE freelancers
            SET nome_completo = ?, telefone = ?, cidade = ?, estado = ?, especialidade = ?, habilidades = ?, biografia = ?, portfolio = ?, linkedin = ?, github = ?
            WHERE id = ?
        ''', (nome_completo, telefone, cidade, estado, especialidade, habilidades, biografia, portfolio, linkedin, github, freelancer_id))
        conn.commit()
        conn.close()
        session['freelancer_nome'] = nome_completo
        flash(MSG.PERFIL_OK, 'sucesso')
        return redirect(url_for('perfil_freelancer', freelancer_id=freelancer_id))

    conn.close()
    return render_template('editar_freelancer.html', freelancer=freelancer)

@app.route('/enviar-proposta/<int:projeto_id>', methods=['GET', 'POST'])
@freelancer_required
def enviar_proposta(projeto_id):
    """Enviar proposta para um projeto"""
    conn = criar_conexao()
    cursor = conn.cursor()
    
    cursor.execute('SELECT *, presupuesto AS orcamento FROM projetos WHERE id = ?', (projeto_id,))
    projeto = format_projeto_data(cursor.fetchone())
    
    if not projeto:
        conn.close()
        flash(MSG.PROJETO_NAO_ENCONTRADO, 'erro')
        return redirect(url_for('projetos'))
    
    if request.method == 'POST':
        valor = request.form.get('valor', '').strip()
        prazo = request.form.get('prazo', '').strip()
        proposta = request.form.get('proposta', '').strip()
        
        cursor.execute('''
            INSERT INTO propostas (projeto_id, freelancer_id, valor_proposto, prazo_dias, proposta)
            VALUES (?, ?, ?, ?, ?)
        ''', (projeto_id, session['freelancer_id'], valor, prazo, proposta))
        
        conn.commit()
        conn.close()
        
        flash(MSG.PROPOSTA_ENVIADA, 'sucesso')
        return redirect(url_for('dashboard_freelancer'))
    
    conn.close()
    return render_template('enviar_proposta.html', projeto=projeto)

@app.route('/avaliar-freelancer/<int:projeto_id>/<int:freelancer_id>', methods=['GET', 'POST'])
@empresa_required
def avaliar_freelancer(projeto_id, freelancer_id):
    """Avaliar freelancer após conclusão do projeto"""
    if 'empresa_id' not in session:
        flash(MSG.APENAS_EMPRESA_AVALIAR, 'erro')
        return redirect(url_for('index'))

    conn = criar_conexao()
    cursor = conn.cursor()
    cursor.execute('''
        SELECT p.id AS projeto_id, p.titulo, f.*
        FROM projetos p
        JOIN propostas pr ON pr.projeto_id = p.id
        JOIN freelancers f ON f.id = pr.freelancer_id
        WHERE p.id = ? AND pr.freelancer_id = ? AND p.empresa_id = ?
    ''', (projeto_id, freelancer_id, session['empresa_id']))
    avaliacao_info = cursor.fetchone()

    if not avaliacao_info:
        conn.close()
        flash(MSG.AVALIACAO_NAO_ENCONTRADA_FL, 'erro')
        return redirect(url_for('dashboard_empresa'))

    freelancer = format_freelancer_data(avaliacao_info)
    projeto = {'id': avaliacao_info['projeto_id'], 'titulo': avaliacao_info['titulo']}

    if request.method == 'POST':
        nota_qualidade = int(request.form.get('nota_qualidade', 0))
        nota_prazo = int(request.form.get('nota_prazo', 0))
        nota_comunicacao = int(request.form.get('nota_comunicacao', 0))
        nota_portfolio = int(request.form.get('nota_portfolio', 0))
        comentario = request.form.get('comentario', '').strip()

        if not (1 <= nota_qualidade <= 5 and 1 <= nota_prazo <= 5 and 1 <= nota_comunicacao <= 5 and 1 <= nota_portfolio <= 5):
            flash(MSG.NOTAS_INVALIDAS, 'erro')
        else:
            cursor.execute('''
                INSERT INTO avaliacoes (projeto_id, freelancer_id, empresa_id, nota_qualidade, nota_prazo, nota_comunicacao, nota_portfolio, comentario)
                VALUES (?, ?, ?, ?, ?, ?, ?, ?)
            ''', (projeto_id, freelancer_id, session['empresa_id'], nota_qualidade, nota_prazo, nota_comunicacao, nota_portfolio, comentario))
            conn.commit()
            conn.close()
            atualizar_nota_media_freelancer(freelancer_id)
            flash(MSG.AVALIACAO_FREELANCER_OK, 'sucesso')
            return redirect(url_for('detalhes_projeto', projeto_id=projeto_id))

    conn.close()
    return render_template('avaliar_freelancer.html', freelancer=freelancer, projeto=projeto)

@app.route('/avaliar-empresa/<int:projeto_id>/<int:empresa_id>', methods=['GET', 'POST'])
@freelancer_required
def avaliar_empresa(projeto_id, empresa_id):
    """Avaliar empresa após conclusão do projeto"""
    if 'freelancer_id' not in session:
        flash(MSG.APENAS_FREELANCER_AVALIAR, 'erro')
        return redirect(url_for('index'))

    conn = criar_conexao()
    cursor = conn.cursor()
    cursor.execute('''
        SELECT p.id AS projeto_id, p.titulo, e.*
        FROM projetos p
        JOIN empresas e ON e.id = p.empresa_id
        JOIN propostas pr ON pr.projeto_id = p.id
        WHERE p.id = ? AND p.empresa_id = ? AND pr.freelancer_id = ?
    ''', (projeto_id, empresa_id, session['freelancer_id']))
    avaliacao_info = cursor.fetchone()

    if not avaliacao_info:
        conn.close()
        flash(MSG.AVALIACAO_NAO_ENCONTRADA_EM, 'erro')
        return redirect(url_for('dashboard_freelancer'))

    empresa = format_empresa_data(avaliacao_info)
    projeto = {'id': avaliacao_info['projeto_id'], 'titulo': avaliacao_info['titulo']}

    if request.method == 'POST':
        nota_satisfacao = int(request.form.get('nota_satisfacao', 0))
        nota_profissionalismo = int(request.form.get('nota_profissionalismo', 0))
        nota_portfolio = int(request.form.get('nota_portfolio', 0))
        comentario = request.form.get('comentario', '').strip()

        if not (1 <= nota_satisfacao <= 5 and 1 <= nota_profissionalismo <= 5 and 1 <= nota_portfolio <= 5):
            flash(MSG.NOTAS_INVALIDAS, 'erro')
        else:
            cursor.execute('''
                INSERT INTO avaliacoes_empresa (projeto_id, empresa_id, freelancer_id, nota_satisfacao, nota_profissionalismo, nota_portfolio, comentario)
                VALUES (?, ?, ?, ?, ?, ?, ?)
            ''', (projeto_id, empresa_id, session['freelancer_id'], nota_satisfacao, nota_profissionalismo, nota_portfolio, comentario))
            conn.commit()
            conn.close()
            atualizar_nota_media_empresa(empresa_id)
            flash(MSG.AVALIACAO_EMPRESA_OK, 'sucesso')
            return redirect(url_for('detalhes_projeto', projeto_id=projeto_id))

    conn.close()
    return render_template('avaliar_empresa.html', empresa=empresa, projeto=projeto)

@app.route('/criar-projeto', methods=['GET', 'POST'])
@empresa_required
def criar_projeto():
    """Criar novo projeto"""
    if request.method == 'POST':
        titulo = request.form.get('titulo', '').strip()
        descricao = request.form.get('descricao', '').strip()
        categoria = request.form.get('categoria', '').strip()
        habilidades = request.form.get('requisitos', '').strip()
        presupuesto = request.form.get('orcamento', '0').strip() or '0'
        prazo = request.form.get('prazo', '').strip()
        nivel = request.form.get('nivel', 'Intermediário').strip()
        
        conn = criar_conexao()
        cursor = conn.cursor()
        
        cursor.execute('''
            INSERT INTO projetos (empresa_id, titulo, descricao, categoria, habilidades_requeridas, presupuesto, prazo, nivel_experiencia)
            VALUES (?, ?, ?, ?, ?, ?, ?, ?)
        ''', (session['empresa_id'], titulo, descricao, categoria, habilidades, presupuesto, prazo, nivel))
        
        conn.commit()
        conn.close()
        
        flash(MSG.PROJETO_CRIADO, 'sucesso')
        return redirect(url_for('dashboard_empresa'))
    
    return render_template('criar_projeto.html')

# ==================== MENSAGENS / INBOX ====================

@app.route('/inbox')
@login_required()
def inbox():
    """Inbox de mensagens"""
    conn = criar_conexao()
    cursor = conn.cursor()

    usuario_id = session.get('empresa_id') or session.get('freelancer_id')
    usuario_tipo = 'empresa' if 'empresa_id' in session else 'freelancer'

    cursor.execute('''
        SELECT m.*,
               CASE WHEN m.remetente_tipo = 'empresa' THEN e.nome_empresa ELSE f.nome_completo END AS remetente_nome,
               e.id AS empresa_id, f.id AS freelancer_id, 'recebida' AS tipo_msg
        FROM mensagens m
        LEFT JOIN empresas e ON m.remetente_id = e.id AND m.remetente_tipo = 'empresa'
        LEFT JOIN freelancers f ON m.remetente_id = f.id AND m.remetente_tipo = 'freelancer'
        WHERE m.destinatario_id = ? AND m.destinatario_tipo = ?
        ORDER BY m.data_envio DESC
    ''', (usuario_id, usuario_tipo))
    mensagens_recebidas = cursor.fetchall()

    cursor.execute('''
        SELECT m.*,
               CASE WHEN m.destinatario_tipo = 'empresa' THEN e.nome_empresa ELSE f.nome_completo END AS destinatario_nome,
               e.id AS empresa_id, f.id AS freelancer_id, 'enviada' AS tipo_msg
        FROM mensagens m
        LEFT JOIN empresas e ON m.destinatario_id = e.id AND m.destinatario_tipo = 'empresa'
        LEFT JOIN freelancers f ON m.destinatario_id = f.id AND m.destinatario_tipo = 'freelancer'
        WHERE m.remetente_id = ? AND m.remetente_tipo = ?
        ORDER BY m.data_envio DESC
    ''', (usuario_id, usuario_tipo))
    mensagens_enviadas = cursor.fetchall()

    conn.close()
    return render_template('inbox.html',
                         mensagens_recebidas=mensagens_recebidas,
                         mensagens_enviadas=mensagens_enviadas,
                         usuario_tipo=usuario_tipo)

# ==================== ROTAS DE BUSCA ====================

@app.route('/busca')
def busca():
    """Busca global"""
    termo = request.args.get('q', '')
    
    conn = criar_conexao()
    cursor = conn.cursor()
    
    # Buscar projetos
    cursor.execute('''
        SELECT p.*, e.nome_empresa, p.presupuesto AS orcamento
        FROM projetos p 
        JOIN empresas e ON p.empresa_id = e.id 
        WHERE p.titulo LIKE ? OR p.descricao LIKE ? OR p.categoria LIKE ?
        ORDER BY p.data_criacao DESC
    ''', (f'%{termo}%', f'%{termo}%', f'%{termo}%'))
    projetos_list = [format_projeto_data(projeto) for projeto in cursor.fetchall()]
    
    # Buscar freelancers
    cursor.execute('''
        SELECT * FROM freelancers 
        WHERE nome_completo LIKE ? OR especialidade LIKE ? OR habilidades LIKE ?
        ORDER BY nota_media DESC
    ''', (f'%{termo}%', f'%{termo}%', f'%{termo}%'))
    freelancers_list = [format_freelancer_data(freelancer) for freelancer in cursor.fetchall()]
    
    conn.close()
    
    return render_template('busca.html', projetos=projetos_list, freelancers=freelancers_list, termo=termo)

# ==================== INICIO DO SERVIDOR ====================

if __name__ == '__main__':
    debug = os.environ.get('FLASK_ENV', 'development') != 'production'
    print("=" * 50)
    print("ConectaServ - Plataforma de Freelancers")
    print("Versao: 2026-05-21-cadastro-fix")
    print("BANCO OFICIAL (HeidiSQL):", DB_PATH)
    print("Modo:", "desenvolvimento" if debug else "producao (use Gunicorn na Hostinger)")
    print("=" * 50)
    print("Servidor iniciado em: http://127.0.0.1:5000")
    print("Acesse na rede local com: http://SEU_IP_LOCAL:5000")
    print("=" * 50)
    app.run(host='0.0.0.0', port=5000, debug=debug, use_reloader=False)
