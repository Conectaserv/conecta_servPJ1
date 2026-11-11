from flask import Flask, render_template, request, redirect, url_for, session, jsonify, flash, get_flashed_messages, send_from_directory
import sqlite3
import os
import secrets
import traceback
from functools import wraps
from datetime import datetime, timedelta

from utils.email_service import enviar_email_proposta_aceita

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
    papel_do_email,
    cnpj_valido,
    calcular_indicadores_empresa,
    aceitar_proposta_db,
    notificar_destinatario,
    DB_PATH,
    info_diagnostico_banco,
    registrar_historico,
    recalcular_progresso_projeto,
    ETAPAS_PROJETO,
    ETAPA_LABELS,
)
from api import api_bp
from security import verificar_senha

# Inicializar banco de dados
inicializar_banco()
app.register_blueprint(api_bp)


@app.after_request
def sem_cache(resp):
    resp.headers['Cache-Control'] = 'no-store, no-cache, must-revalidate, max-age=0'
    resp.headers['Pragma'] = 'no-cache'
    resp.headers['Expires'] = '0'
    return resp


@app.errorhandler(404)
def nao_encontrado(erro):
    if request.path.startswith('/api/'):
        return jsonify({'ok': False, 'erro': 'Rota não encontrada.'}), 404
    return ('Página não encontrada.', 404)


@app.errorhandler(500)
def erro_interno(erro):
    try:
        with open(os.path.join(os.path.dirname(__file__), 'erro_servidor.log'), 'a', encoding='utf-8') as log:
            log.write('\n==== ' + datetime.now().isoformat(sep=' ', timespec='seconds') + ' ' + request.path + ' ====\n')
            traceback.print_exc(file=log)
    except OSError:
        pass
    if request.path.startswith('/api/'):
        return jsonify({'ok': False, 'erro': 'Erro no servidor.'}), 500
    detalhe = str(getattr(erro, 'original_exception', None) or erro)
    return (
        '<!DOCTYPE html><html lang="pt-BR"><meta charset="UTF-8">'
        '<title>Erro</title><body style="font-family:system-ui;max-width:640px;margin:3rem auto;padding:0 1rem">'
        '<h1>Não foi possível abrir esta página</h1>'
        '<p>Sua conta de freelancer continua válida. Volte ao início ou entre de novo.</p>'
        '<p><a href="/">Início</a> · <a href="/login-freelancer">Entrar como freelancer</a> · '
        '<a href="/acessibilidade">Acessibilidade</a></p>'
        f'<pre style="background:#f4f4f5;padding:1rem;overflow:auto">{detalhe}</pre>'
        '</body></html>',
        500,
    )


ALERT_CLASS_MAP = {
    'sucesso': 'success',
    'erro': 'error',
    'aviso': 'warning',
    'info': 'info',
    'conta_existe': 'warning',
}

@app.context_processor
def inject_flash_messages():
    """Disponibiliza mensagens flash em todos os templates (uma única leitura)."""
    nao_lidas = 0
    if session.get('user_id'):
        try:
            conn = criar_conexao()
            cursor = conn.cursor()
            cursor.execute(
                'SELECT COUNT(*) FROM notificacoes WHERE user_id = ? AND COALESCE(lida, 0) = 0',
                (session['user_id'],),
            )
            nao_lidas = cursor.fetchone()[0]
            conn.close()
        except sqlite3.Error:
            nao_lidas = 0
    return {
        'flash_messages': get_flashed_messages(with_categories=True),
        'alert_class': lambda category: ALERT_CLASS_MAP.get(category, category),
        'notificacoes_nao_lidas': nao_lidas,
    }

# ==================== FUNÇÕES AUXILIARES ====================

def flash_erro_cadastro(erro, tipo_doc='CNPJ'):
    """Mensagem clara para falhas no cadastro."""
    msg = str(erro).lower()
    if 'locked' in msg or 'busy' in msg:
        flash(
            'Não foi possível salvar: o banco está em uso. Feche o arquivo conecta_serv.db no editor, '
            'reinicie o servidor e tente novamente.',
            'erro',
        )
    elif 'cnpj' in msg or 'cpf' in msg:
        flash(f'{tipo_doc} já cadastrado!', 'erro')
    elif 'email' in msg or 'users.email' in msg:
        flash('E-mail já cadastrado! Use outro e-mail ou faça login.', 'erro')
    elif 'not null' in msg:
        flash('Erro ao salvar cadastro. Reinicie o servidor e tente de novo.', 'erro')
    else:
        flash(f'Não foi possível salvar o cadastro: {erro}', 'erro')

def flash_erro_duplicado(erro, tipo):
    """Mensagem de cadastro conforme o campo duplicado."""
    msg = str(erro).lower()
    if 'cnpj' in msg or 'cpf' in msg:
        flash(f'{tipo} já cadastrado!', 'erro')
    elif 'email' in msg:
        flash('Email já cadastrado!', 'erro')
    else:
        flash(f'Email ou {tipo} já cadastrado!', 'erro')

def format_freelancer_data(row):
    """Formatar dados do freelancer"""
    if row is None:
        return None
    data = dict(row)
    nome_completo = data.get('nome_completo') or ''
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
    etapa = data.get('etapa') or (
        'concluido' if data.get('status') == 'concluido'
        else 'desenvolvimento' if data.get('status') == 'andamento'
        else 'publicado'
    )
    data['etapa'] = etapa
    data['etapa_label'] = ETAPA_LABELS.get(etapa, etapa)
    data['progresso'] = data.get('progresso') or 0
    return data


def dias_restantes_prazo(prazo):
    """Retorna dias restantes até o prazo (ou None se inválido)."""
    if not prazo:
        return None
    try:
        if isinstance(prazo, str):
            prazo_dt = datetime.strptime(prazo[:10], '%Y-%m-%d').date()
        else:
            prazo_dt = prazo
        return (prazo_dt - datetime.now().date()).days
    except (ValueError, TypeError):
        return None


def usuario_pode_acessar_projeto(cursor, projeto):
    """Empresa dona ou freelancer contratado."""
    if session.get('empresa_id') and session['empresa_id'] == projeto['empresa_id']:
        return True
    if session.get('freelancer_id') and projeto.get('freelancer_contratado_id') == session['freelancer_id']:
        return True
    return False

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

    if not user or not verificar_senha(user['senha'], senha):
        conn.close()
        return None, 'E-mail ou senha incorretos.'

    if not user['ativo']:
        conn.close()
        return None, 'Conta desativada. Entre em contato com o suporte.'

    cursor.execute('SELECT id FROM empresas WHERE user_id = ?', (user['id'],))
    tem_empresa = cursor.fetchone() is not None
    cursor.execute('SELECT id FROM freelancers WHERE user_id = ?', (user['id'],))
    tem_freelancer = cursor.fetchone() is not None
    if not tem_empresa:
        try:
            cursor.execute(
                'SELECT id FROM empresas WHERE LOWER(TRIM(email)) = ? AND (user_id IS NULL OR user_id = ?)',
                (email, user['id']),
            )
            legado = cursor.fetchone()
            if legado:
                cursor.execute('UPDATE empresas SET user_id = ? WHERE id = ?', (user['id'], legado['id']))
                conn.commit()
                tem_empresa = True
        except sqlite3.Error:
            pass
    if not tem_freelancer:
        try:
            cursor.execute(
                'SELECT id FROM freelancers WHERE LOWER(TRIM(email)) = ? AND (user_id IS NULL OR user_id = ?)',
                (email, user['id']),
            )
            legado = cursor.fetchone()
            if legado:
                cursor.execute('UPDATE freelancers SET user_id = ? WHERE id = ?', (user['id'], legado['id']))
                conn.commit()
                tem_freelancer = True
        except sqlite3.Error:
            pass

    if role_esperado == 'empresa':
        if not tem_empresa:
            conn.close()
            if tem_freelancer:
                return None, 'Este e-mail é de uma conta de freelancer. Use o login de freelancer.'
            return None, 'Perfil de empresa não encontrado. Cadastre-se como empresa.'
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
                return None, 'Este e-mail é de uma conta de empresa. Use o login de empresa.'
            return None, 'Perfil de freelancer não encontrado. Cadastre-se como freelancer.'
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
        return None, 'Perfil não encontrado para esta conta. Cadastre-se novamente.'

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
                flash('Você precisa estar logado para acessar esta página.', 'erro')
                return redirect(url_for('index'))
            
            if roles and session.get('role') not in roles:
                flash('Você não tem permissão para acessar esta página.', 'erro')
                return redirect(url_for('index'))
            
            return f(*args, **kwargs)
        return decorated_function
    return decorator

def completar_sessao_freelancer():
    """Garante freelancer_id na sessão (contas antigas ou cookie incompleto)."""
    if session.get('freelancer_id'):
        session['role'] = 'freelancer'
        session['tipo_usuario'] = 'freelancer'
        return True
    user_id = session.get('user_id')
    if not user_id:
        return False
    conn = criar_conexao()
    cursor = conn.cursor()
    cursor.execute('SELECT id, nome_completo FROM freelancers WHERE user_id = ?', (user_id,))
    row = cursor.fetchone()
    if not row:
        try:
            cursor.execute(
                '''SELECT id, nome_completo FROM freelancers
                   WHERE LOWER(TRIM(email)) = (SELECT LOWER(TRIM(email)) FROM users WHERE id = ?)''',
                (user_id,),
            )
            row = cursor.fetchone()
            if row:
                cursor.execute('UPDATE freelancers SET user_id = ? WHERE id = ?', (user_id, row['id']))
                conn.commit()
        except sqlite3.Error:
            row = None
    conn.close()
    if not row:
        return False
    session['freelancer_id'] = row['id']
    session['freelancer_nome'] = row['nome_completo']
    session['role'] = 'freelancer'
    session['tipo_usuario'] = 'freelancer'
    return True


def freelancer_required(f):
    """Decorator para rotas exclusivas de freelancers"""
    @wraps(f)
    def decorated_function(*args, **kwargs):
        if 'user_id' not in session:
            flash('Entre ou cadastre-se como freelancer para continuar.', 'info')
            return redirect(url_for('login_freelancer'))
        if not completar_sessao_freelancer():
            flash('Entre com a conta de freelancer para continuar.', 'info')
            return redirect(url_for('login_freelancer'))
        return f(*args, **kwargs)
    return decorated_function

def empresa_required(f):
    """Decorator para rotas exclusivas de empresas"""
    @wraps(f)
    def decorated_function(*args, **kwargs):
        if 'user_id' not in session or session.get('role') != 'empresa' or not session.get('empresa_id'):
            flash('Faça login como empresa para continuar.', 'erro')
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

    cursor.execute("SELECT COALESCE(AVG(nota_media), 0) FROM freelancers WHERE nota_media IS NOT NULL AND nota_media > 0")
    media_freelancers = cursor.fetchone()[0] or 0
    cursor.execute("SELECT COALESCE(SUM(presupuesto), 0) FROM projetos")
    valor_projetos = cursor.fetchone()[0] or 0
    
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
                         media_freelancers=round(media_freelancers, 1),
                         valor_projetos=valor_projetos,
                         projetos_recentes=projetos_recentes)

@app.route('/sobre')
def sobre():
    """Página sobre"""
    return render_template('sobre.html')

@app.route('/acessibilidade')
def acessibilidade():
    """Página de acessibilidade"""
    return render_template('acessibilidade.html')


@app.route('/diagnostico-banco')
def diagnostico_banco():
    """Mostra se o banco online está persistente (ajuda a entender cadastros que somem)."""
    d = info_diagnostico_banco()
    return f'''<!DOCTYPE html>
<html lang="pt-BR"><head><meta charset="UTF-8"><title>Diagnóstico banco</title>
<style>body{{font-family:system-ui;max-width:640px;margin:2rem auto;padding:1rem}}
.ok{{color:#166534}}.alert{{color:#b45309;background:#fffbeb;padding:1rem;border-radius:8px}}</style></head>
<body>
<h1>Diagnóstico do banco — ConectaServ</h1>
<p><strong>Modo de gravação:</strong> <span class="{"ok" if "PERSISTENTE" in d["persistencia"] else "alert"}">{d["persistencia"]}</span></p>
<ul>
<li>Arquivo do banco: <code>{d["caminho"]}</code></li>
<li>DATABASE_PATH: <code>{d["database_path_env"]}</code></li>
<li>Arquivo existe: {d["arquivo_existe"]}</li>
<li>Pasta gravável: {d["gravavel"]}</li>
<li>Tamanho: {d["tamanho_kb"]} KB — alterado em {d["modificado"]}</li>
<li>Freelancers: {d["freelancers"]} | Empresas: {d["empresas"]} | Usuários: {d["users"]}</li>
</ul>
<p><a href="/">Voltar ao início</a></p>
</body></html>'''


@app.route('/app')
def app_mobile():
    """Aplicativo mobile (PWA) com o mesmo visual 2.0 e a mesma API."""
    return render_template('app_mobile.html')


@app.route('/manifest.json')
def pwa_manifest():
    return send_from_directory(os.path.join(app.root_path, 'static'), 'manifest.json', mimetype='application/manifest+json')


@app.route('/sw.js')
def pwa_sw():
    resp = send_from_directory(os.path.join(app.root_path, 'static'), 'sw.js', mimetype='application/javascript')
    resp.headers['Service-Worker-Allowed'] = '/'
    return resp

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
            flash('Preencha todos os campos obrigatórios.', 'erro')
            return redirect(url_for('cadastro_empresa'))

        if not cnpj_valido(cnpj):
            flash('CNPJ inválido. Informe os 14 números do CNPJ.', 'erro')
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
                flash(
                    f'Este e-mail já está cadastrado na empresa "{dados_dup["nome_empresa"]}". '
                    f'Não precisa cadastrar de novo — faça login.',
                    'conta_existe',
                )
            else:
                flash(
                    f'Este CNPJ já está cadastrado na empresa "{dados_dup["nome_empresa"]}" '
                    f'({dados_dup["email"]}). Use outro CNPJ ou faça login.',
                    'conta_existe',
                )
            return redirect(url_for('cadastro_empresa'))

        if resultado['status'] == 'freelancer':
            flash('Este e-mail já é de um freelancer. Use o login/cadastro de freelancer.', 'erro')
            return redirect(url_for('cadastro_empresa'))

        flash(
            f'Cadastro salvo com sucesso para {resultado["email"]}! Use o botão abaixo para entrar.',
            'sucesso',
        )
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
            flash('Preencha todos os campos obrigatórios.', 'erro')
            return redirect(url_for('cadastro_freelancer'))
        
        conn = criar_conexao()
        cursor = conn.cursor()
        
        papel = papel_do_email(cursor, email)
        if papel:
            conn.close()
            if papel == 'empresa':
                flash('Este e-mail já é de uma empresa. Use outro e-mail para a conta de freelancer.', 'erro')
            else:
                flash('Este e-mail já é de um freelancer. Faça login em Já tenho conta.', 'erro')
            return redirect(url_for('cadastro_freelancer'))
        if cpf_ja_cadastrado(cursor, cpf):
            conn.close()
            flash('CPF já cadastrado!', 'erro')
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
            flash(
                f'Cadastro salvo com sucesso para {email}! Use o botão abaixo para entrar.',
                'sucesso',
            )
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
            flash('Email e senha são obrigatórios.', 'erro')
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
            flash('Email e senha são obrigatórios.', 'erro')
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
    flash('Você foi desconectado com sucesso.', 'sucesso')
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
            flash('Preencha o email e a nova senha.', 'erro')
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
            flash('Senha redefinida com sucesso. Faça login com a nova senha.', 'sucesso')
            return redirect(url_for('login_empresa' if tipo == 'empresa' else 'login_freelancer'))

        conn.close()
        flash('Email não encontrado para este tipo de conta.', 'erro')

    return render_template('recuperar_senha.html', tipo=tipo)

# ==================== DASHBOARDS ====================

@app.route('/dashboard-empresa')
@empresa_required
def dashboard_empresa():
    """Dashboard da empresa com indicadores de gestão"""
    conn = criar_conexao()
    cursor = conn.cursor()

    empresa_id = session['empresa_id']

    cursor.execute('SELECT * FROM empresas WHERE id = ?', (empresa_id,))
    empresa = format_empresa_data(cursor.fetchone())

    cursor.execute(
        'SELECT *, presupuesto AS orcamento FROM projetos WHERE empresa_id = ? ORDER BY data_criacao DESC',
        (empresa_id,),
    )
    meus_projetos = [format_projeto_data(p) for p in cursor.fetchall()]

    cursor.execute('''
        SELECT p.id, p.projeto_id, pr.titulo AS projeto_titulo, f.nome_completo AS freelancer_nome,
               p.valor_proposto AS valor, p.prazo_dias AS prazo, p.proposta, p.status, p.freelancer_id
        FROM propostas p
        JOIN projetos pr ON p.projeto_id = pr.id
        JOIN freelancers f ON p.freelancer_id = f.id
        WHERE pr.empresa_id = ?
        ORDER BY p.data_proposta DESC
    ''', (empresa_id,))
    propostas = [dict(proposta) for proposta in cursor.fetchall()]

    indicadores = calcular_indicadores_empresa(cursor, empresa_id)
    conn.close()

    return render_template(
        'dashboard_empresa.html',
        empresa=empresa,
        projetos=meus_projetos,
        propostas=propostas,
        indicadores=indicadores,
    )

@app.route('/dashboard-freelancer')
@freelancer_required
def dashboard_freelancer():
    """Dashboard do freelancer"""
    freelancer_id = session.get('freelancer_id')
    conn = criar_conexao()
    cursor = conn.cursor()
    minhas_propostas = []
    projetos_disponiveis = []
    try:
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
        for item in minhas_propostas:
            item['empresa_nome'] = item.get('empresa_nome') or item.get('nome_empresa')
    except sqlite3.Error:
        minhas_propostas = []

    try:
        cursor.execute('''
            SELECT p.*, e.nome_empresa, p.presupuesto AS orcamento
            FROM projetos p
            JOIN empresas e ON p.empresa_id = e.id
            WHERE p.status = 'aberto'
            ORDER BY p.data_criacao DESC
        ''')
        projetos_disponiveis = [p for p in (format_projeto_data(projeto) for projeto in cursor.fetchall()) if p]
    except sqlite3.Error:
        projetos_disponiveis = []

    cursor.execute('SELECT * FROM freelancers WHERE id = ?', (freelancer_id,))
    freelancer = format_freelancer_data(cursor.fetchone())
    conn.close()

    if not freelancer:
        flash('Não encontramos seu perfil. Entre novamente como freelancer.', 'erro')
        session.clear()
        return redirect(url_for('login_freelancer'))

    return render_template(
        'dashboard_freelancer.html',
        propostas=minhas_propostas,
        projetos_disponiveis=projetos_disponiveis,
        freelancer=freelancer,
    )

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
        flash('Projeto não encontrado.', 'erro')
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
    try:
        resultado = aceitar_proposta_db(
            cursor, proposta_id, session['empresa_id'], session.get('user_id'),
        )
        if resultado['status'] == 'nao_encontrada':
            conn.rollback()
            conn.close()
            flash('Proposta não encontrada ou acesso negado.', 'erro')
            return redirect(url_for('dashboard_empresa'))
        conn.commit()
    except Exception:
        try:
            conn.rollback()
            conn.close()
        except sqlite3.Error:
            pass
        flash('Não foi possível concluir a aceitação. Atualize o painel e tente de novo.', 'erro')
        return redirect(url_for('dashboard_empresa'))

    proposta = resultado.get('proposta') or {}
    conn.close()

    if resultado['status'] == 'ok':
        try:
            ok, msg_email = enviar_email_proposta_aceita(
                proposta.get('freelancer_email'),
                proposta.get('freelancer_nome'),
                proposta.get('titulo'),
                proposta.get('prazo_dias'),
                proposta.get('valor_proposto'),
                proposta.get('empresa_nome'),
                proposta.get('empresa_email'),
                proposta.get('empresa_telefone'),
            )
            if ok:
                flash('Proposta aceita! O freelancer foi avisado.', 'sucesso')
            else:
                flash(f'Proposta aceita. O aviso por e-mail não saiu: {msg_email}', 'aviso')
        except Exception:
            flash('Proposta aceita. O aviso por e-mail não saiu, mas o serviço foi registrado.', 'aviso')

    return redirect(url_for('servico_aceito', proposta_id=proposta_id))

@app.route('/servico-aceito/<int:proposta_id>')
@login_required()
def servico_aceito(proposta_id):
    """Página de confirmação após aceitar proposta"""
    conn = criar_conexao()
    cursor = conn.cursor()
    try:
        cursor.execute('''
            SELECT p.*, proj.titulo AS projeto_titulo, proj.presupuesto AS orcamento,
                   proj.prazo AS prazo_contrato, proj.empresa_id,
                   f.nome_completo AS freelancer_nome,
                   COALESCE(f.telefone, '') AS freelancer_telefone,
                   COALESCE(uf.email, f.email, '') AS freelancer_email,
                   e.nome_empresa AS empresa_nome,
                   COALESCE(e.telefone, '') AS empresa_telefone,
                   COALESCE(ue.email, e.email, '') AS empresa_email
            FROM propostas p
            JOIN projetos proj ON p.projeto_id = proj.id
            JOIN freelancers f ON p.freelancer_id = f.id
            LEFT JOIN users uf ON f.user_id = uf.id
            JOIN empresas e ON proj.empresa_id = e.id
            LEFT JOIN users ue ON e.user_id = ue.id
            WHERE p.id = ?
        ''', (proposta_id,))
        proposta = cursor.fetchone()
    except sqlite3.Error:
        cursor.execute('''
            SELECT p.*, proj.titulo AS projeto_titulo, proj.empresa_id,
                   f.nome_completo AS freelancer_nome
            FROM propostas p
            JOIN projetos proj ON p.projeto_id = proj.id
            JOIN freelancers f ON p.freelancer_id = f.id
            WHERE p.id = ?
        ''', (proposta_id,))
        proposta = cursor.fetchone()
    conn.close()
    if proposta:
        proposta = dict(proposta)
        proposta.setdefault('orcamento', '')
        proposta.setdefault('prazo_contrato', '')
        proposta.setdefault('freelancer_telefone', '')
        proposta.setdefault('freelancer_email', '')
        proposta.setdefault('empresa_nome', '')
        proposta.setdefault('empresa_telefone', '')
        proposta.setdefault('empresa_email', '')
        proposta.setdefault('prazo_dias', '—')
        proposta.setdefault('valor_proposto', '—')

    if not proposta:
        flash('Serviço não encontrado.', 'erro')
        return redirect(url_for('index'))

    if 'empresa_id' in session and session['empresa_id'] != proposta['empresa_id']:
        flash('Acesso negado.', 'erro')
        return redirect(url_for('index'))
    if 'freelancer_id' in session and session['freelancer_id'] != proposta['freelancer_id']:
        flash('Acesso negado.', 'erro')
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
    if not freelancer:
        conn.close()
        flash('Perfil não encontrado.', 'erro')
        return redirect(url_for('freelancers'))

    try:
        cursor.execute('''
            SELECT a.*, e.nome_empresa
            FROM avaliacoes a
            JOIN empresas e ON a.empresa_id = e.id
            WHERE a.freelancer_id = ?
            ORDER BY a.data_avaliacao DESC
            LIMIT 5
        ''', (freelancer_id,))
        avaliacoes = cursor.fetchall()
    except sqlite3.Error:
        avaliacoes = []

    conn.close()

    return render_template('perfil_freelancer.html', freelancer=freelancer, avaliacoes=avaliacoes)

@app.route('/contatar-freelancer/<int:freelancer_id>', methods=['GET', 'POST'])
@empresa_required
def contatar_freelancer(freelancer_id):
    """Página para empresas enviarem mensagem a freelancers"""
    if 'empresa_id' not in session:
        flash('Apenas empresas podem enviar mensagens a freelancers.', 'erro')
        return redirect(url_for('perfil_freelancer', freelancer_id=freelancer_id))

    conn = criar_conexao()
    cursor = conn.cursor()
    cursor.execute('SELECT * FROM freelancers WHERE id = ?', (freelancer_id,))
    freelancer = format_freelancer_data(cursor.fetchone())

    if not freelancer:
        conn.close()
        flash('Freelancer nao encontrado.', 'erro')
        return redirect(url_for('projetos'))

    if request.method == 'POST':
        mensagem = request.form.get('mensagem', '').strip()
        if not mensagem:
            flash('Digite sua mensagem antes de enviar.', 'erro')
        else:
            cursor.execute('''
                INSERT INTO mensagens (remetente_id, destinatario_id, remetente_tipo, destinatario_tipo, mensagem)
                VALUES (?, ?, ?, ?, ?)
            ''', (session['empresa_id'], freelancer_id, 'empresa', 'freelancer', mensagem))
            notificar_destinatario(
                cursor, 'freelancer', freelancer_id,
                'Nova mensagem',
                f'A empresa enviou: {mensagem}',
            )
            conn.commit()
            conn.close()
            flash('Mensagem enviada com sucesso!', 'sucesso')
            return redirect(url_for('perfil_freelancer', freelancer_id=freelancer_id))

    conn.close()
    return render_template('contatar_freelancer.html', freelancer=freelancer)

@app.route('/editar-empresa/<int:empresa_id>', methods=['GET', 'POST'])
@empresa_required
def editar_empresa(empresa_id):
    """Editar dados da empresa"""
    if 'empresa_id' not in session or session['empresa_id'] != empresa_id:
        flash('Acesso negado.', 'erro')
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
        flash('Perfil da empresa atualizado com sucesso!', 'sucesso')
        return redirect(url_for('dashboard_empresa'))

    conn.close()
    return render_template('editar_empresa.html', empresa=empresa)

@app.route('/editar-freelancer/<int:freelancer_id>', methods=['GET', 'POST'])
@freelancer_required
def editar_freelancer(freelancer_id):
    """Editar dados do freelancer"""
    if 'freelancer_id' not in session or session['freelancer_id'] != freelancer_id:
        flash('Acesso negado.', 'erro')
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
        flash('Perfil atualizado com sucesso!', 'sucesso')
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
        flash('Projeto não encontrado.', 'erro')
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
        
        flash('Proposta enviada com sucesso!', 'sucesso')
        return redirect(url_for('dashboard_freelancer'))
    
    conn.close()
    return render_template('enviar_proposta.html', projeto=projeto)

@app.route('/avaliar-freelancer/<int:projeto_id>/<int:freelancer_id>', methods=['GET', 'POST'])
@empresa_required
def avaliar_freelancer(projeto_id, freelancer_id):
    """Avaliar freelancer após conclusão do projeto"""
    if 'empresa_id' not in session:
        flash('Apenas empresas podem avaliar freelancers.', 'erro')
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
        flash('Não foi possível encontrar o projeto ou freelancer para avaliação.', 'erro')
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
            flash('Preencha todas as notas de avaliação entre 1 e 5.', 'erro')
        else:
            cursor.execute('''
                INSERT INTO avaliacoes (projeto_id, freelancer_id, empresa_id, nota_qualidade, nota_prazo, nota_comunicacao, nota_portfolio, comentario)
                VALUES (?, ?, ?, ?, ?, ?, ?, ?)
            ''', (projeto_id, freelancer_id, session['empresa_id'], nota_qualidade, nota_prazo, nota_comunicacao, nota_portfolio, comentario))
            conn.commit()
            conn.close()
            atualizar_nota_media_freelancer(freelancer_id)
            flash('Avaliação do freelancer registrada com sucesso!', 'sucesso')
            return redirect(url_for('detalhes_projeto', projeto_id=projeto_id))

    conn.close()
    return render_template('avaliar_freelancer.html', freelancer=freelancer, projeto=projeto)

@app.route('/avaliar-empresa/<int:projeto_id>/<int:empresa_id>', methods=['GET', 'POST'])
@freelancer_required
def avaliar_empresa(projeto_id, empresa_id):
    """Avaliar empresa após conclusão do projeto"""
    if 'freelancer_id' not in session:
        flash('Apenas freelancers podem avaliar empresas.', 'erro')
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
        flash('Não foi possível encontrar o projeto ou empresa para avaliação.', 'erro')
        return redirect(url_for('dashboard_freelancer'))

    empresa = format_empresa_data(avaliacao_info)
    projeto = {'id': avaliacao_info['projeto_id'], 'titulo': avaliacao_info['titulo']}

    if request.method == 'POST':
        nota_satisfacao = int(request.form.get('nota_satisfacao', 0))
        nota_profissionalismo = int(request.form.get('nota_profissionalismo', 0))
        nota_portfolio = int(request.form.get('nota_portfolio', 0))
        comentario = request.form.get('comentario', '').strip()

        if not (1 <= nota_satisfacao <= 5 and 1 <= nota_profissionalismo <= 5 and 1 <= nota_portfolio <= 5):
            flash('Preencha todas as notas de avaliação entre 1 e 5.', 'erro')
        else:
            cursor.execute('''
                INSERT INTO avaliacoes_empresa (projeto_id, empresa_id, freelancer_id, nota_satisfacao, nota_profissionalismo, nota_portfolio, comentario)
                VALUES (?, ?, ?, ?, ?, ?, ?)
            ''', (projeto_id, empresa_id, session['freelancer_id'], nota_satisfacao, nota_profissionalismo, nota_portfolio, comentario))
            conn.commit()
            conn.close()
            atualizar_nota_media_empresa(empresa_id)
            flash('Avaliação da empresa registrada com sucesso!', 'sucesso')
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
            INSERT INTO projetos (
                empresa_id, titulo, descricao, categoria, habilidades_requeridas,
                presupuesto, prazo, nivel_experiencia, status, etapa, progresso
            )
            VALUES (?, ?, ?, ?, ?, ?, ?, ?, 'aberto', 'publicado', 0)
        ''', (session['empresa_id'], titulo, descricao, categoria, habilidades, presupuesto, prazo, nivel))
        projeto_id = cursor.lastrowid
        registrar_historico(
            cursor, projeto_id, 'projeto_publicado',
            f'Projeto "{titulo}" publicado',
            usuario_id=session.get('user_id'),
            etapa_nova='publicado',
        )
        conn.commit()
        conn.close()

        flash('Projeto criado com sucesso!', 'sucesso')
        return redirect(url_for('dashboard_empresa'))
    
    return render_template('criar_projeto.html')

# ==================== MENSAGENS / INBOX ====================

@app.route('/inbox')
@login_required()
def inbox():
    """Inbox de mensagens"""
    if session.get('role') == 'freelancer' or session.get('tipo_usuario') == 'freelancer':
        completar_sessao_freelancer()
    conn = criar_conexao()
    cursor = conn.cursor()

    usuario_id = session.get('empresa_id') or session.get('freelancer_id')
    usuario_tipo = 'empresa' if session.get('empresa_id') else 'freelancer'

    mensagens_recebidas = []
    mensagens_enviadas = []
    try:
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
    except sqlite3.Error:
        mensagens_recebidas = []
        mensagens_enviadas = []

    conn.close()
    return render_template('inbox.html',
                         mensagens_recebidas=mensagens_recebidas,
                         mensagens_enviadas=mensagens_enviadas,
                         usuario_tipo=usuario_tipo)

@app.route('/inbox/responder', methods=['POST'])
@login_required()
def responder_mensagem():
    """Resposta no inbox (empresa ↔ freelancer)."""
    mensagem = request.form.get('mensagem', '').strip()
    destinatario_id = request.form.get('destinatario_id', type=int)
    destinatario_tipo = request.form.get('destinatario_tipo', '')
    remetente_id = session.get('empresa_id') or session.get('freelancer_id')
    remetente_tipo = 'empresa' if session.get('empresa_id') else 'freelancer'

    if not mensagem or not destinatario_id or destinatario_tipo not in ('empresa', 'freelancer'):
        flash('Preencha a resposta antes de enviar.', 'erro')
        return redirect(url_for('inbox'))
    if destinatario_tipo == remetente_tipo and destinatario_id == remetente_id:
        flash('Não é possível responder para a própria conta.', 'erro')
        return redirect(url_for('inbox'))

    conn = criar_conexao()
    cursor = conn.cursor()
    cursor.execute('''
        INSERT INTO mensagens (remetente_id, destinatario_id, remetente_tipo, destinatario_tipo, mensagem)
        VALUES (?, ?, ?, ?, ?)
    ''', (remetente_id, destinatario_id, remetente_tipo, destinatario_tipo, mensagem))
    notificar_destinatario(
        cursor, destinatario_tipo, destinatario_id,
        'Nova mensagem',
        mensagem,
    )
    conn.commit()
    conn.close()
    flash('Resposta enviada.', 'sucesso')
    return redirect(url_for('inbox'))

@app.route('/notificacoes')
@login_required()
def notificacoes():
    """Sino: avisos de mensagem e de proposta, para empresa e freelancer."""
    conn = criar_conexao()
    cursor = conn.cursor()
    try:
        cursor.execute('''
            SELECT * FROM notificacoes
            WHERE user_id = ?
            ORDER BY data_criacao DESC
            LIMIT 50
        ''', (session['user_id'],))
        itens = [dict(r) for r in cursor.fetchall()]
        cursor.execute(
            'UPDATE notificacoes SET lida = 1 WHERE user_id = ? AND COALESCE(lida, 0) = 0',
            (session['user_id'],),
        )
        conn.commit()
    except sqlite3.Error:
        itens = []
    conn.close()
    return render_template('notificacoes.html', itens=itens)

# ==================== WORKSPACE DO PROJETO (PÓS-CONTRATAÇÃO) ====================

@app.route('/projeto/<int:projeto_id>/workspace')
@login_required()
def workspace_projeto(projeto_id):
    """Acompanhamento completo do projeto após a contratação."""
    conn = criar_conexao()
    cursor = conn.cursor()
    cursor.execute('''
        SELECT p.*, e.nome_empresa, p.presupuesto AS orcamento,
               f.nome_completo AS freelancer_nome, f.id AS freelancer_id_contratado
        FROM projetos p
        JOIN empresas e ON p.empresa_id = e.id
        LEFT JOIN freelancers f ON p.freelancer_contratado_id = f.id
        WHERE p.id = ?
    ''', (projeto_id,))
    projeto = format_projeto_data(cursor.fetchone())

    if not projeto:
        conn.close()
        flash('Projeto não encontrado.', 'erro')
        return redirect(url_for('index'))

    if not usuario_pode_acessar_projeto(cursor, projeto):
        conn.close()
        flash('Acesso negado a este workspace.', 'erro')
        return redirect(url_for('index'))

    def _linhas(sql, params):
        try:
            cursor.execute(sql, params)
            return [dict(r) for r in cursor.fetchall()]
        except sqlite3.Error:
            return []

    tarefas = _linhas(
        'SELECT * FROM tarefas WHERE projeto_id = ? ORDER BY ordem, id',
        (projeto_id,),
    )
    historico = _linhas('''
        SELECT h.*, u.email AS usuario_email
        FROM historico_projeto h
        LEFT JOIN users u ON h.usuario_id = u.id
        WHERE h.projeto_id = ?
        ORDER BY h.data_evento DESC
        LIMIT 40
    ''', (projeto_id,))
    mensagens = _linhas('''
        SELECT * FROM mensagens
        WHERE projeto_id = ?
        ORDER BY data_envio ASC
        LIMIT 100
    ''', (projeto_id,))
    arquivos = _linhas('''
        SELECT * FROM arquivos_projeto
        WHERE projeto_id = ?
        ORDER BY data_upload DESC
    ''', (projeto_id,))
    contratos = _linhas('''
        SELECT c.*, p.valor_proposto
        FROM contratos c
        JOIN propostas p ON c.proposta_id = p.id
        WHERE c.projeto_id = ?
        ORDER BY c.id DESC LIMIT 1
    ''', (projeto_id,))
    contrato = contratos[0] if contratos else None
    pagamentos = _linhas(
        'SELECT * FROM pagamentos WHERE projeto_id = ? ORDER BY data_criacao DESC',
        (projeto_id,),
    )

    prazo_restante = dias_restantes_prazo(projeto.get('prazo'))
    conn.close()

    indice_etapa = ETAPAS_PROJETO.index(projeto['etapa']) if projeto['etapa'] in ETAPAS_PROJETO else 0

    return render_template(
        'workspace_projeto.html',
        projeto=projeto,
        tarefas=tarefas,
        historico=historico,
        mensagens=mensagens,
        arquivos=arquivos,
        contrato=contrato,
        pagamentos=pagamentos,
        prazo_restante=prazo_restante,
        etapas=ETAPAS_PROJETO,
        etapa_labels=ETAPA_LABELS,
        indice_etapa=indice_etapa,
        eh_empresa=bool(session.get('empresa_id') and session['empresa_id'] == projeto['empresa_id']),
    )


@app.route('/projeto/<int:projeto_id>/avancar-etapa', methods=['POST'])
@login_required()
def avancar_etapa_projeto(projeto_id):
    conn = criar_conexao()
    cursor = conn.cursor()
    cursor.execute('SELECT * FROM projetos WHERE id = ?', (projeto_id,))
    projeto = cursor.fetchone()
    if not projeto or not usuario_pode_acessar_projeto(cursor, projeto):
        conn.close()
        flash('Acesso negado.', 'erro')
        return redirect(url_for('index'))

    etapa_atual = projeto['etapa'] or 'contratado'
    if etapa_atual not in ETAPAS_PROJETO:
        etapa_atual = 'contratado'
    idx = ETAPAS_PROJETO.index(etapa_atual)
    if idx >= len(ETAPAS_PROJETO) - 1:
        conn.close()
        flash('Projeto já está concluído.', 'info')
        return redirect(url_for('workspace_projeto', projeto_id=projeto_id))

    nova_etapa = ETAPAS_PROJETO[idx + 1]
    novo_status = 'concluido' if nova_etapa == 'concluido' else 'andamento'
    extras = ''
    params = [nova_etapa, novo_status, projeto_id]
    if nova_etapa == 'concluido':
        extras = ', data_conclusao = CURRENT_TIMESTAMP, progresso = 100'

    cursor.execute(
        f'UPDATE projetos SET etapa = ?, status = ?{extras} WHERE id = ?',
        params,
    )

    if nova_etapa == 'pagamento':
        cursor.execute(
            "UPDATE pagamentos SET status = 'pendente' WHERE projeto_id = ? AND status = 'pendente'",
            (projeto_id,),
        )
    if nova_etapa == 'concluido':
        cursor.execute(
            "UPDATE pagamentos SET status = 'pago', data_pagamento = CURRENT_TIMESTAMP WHERE projeto_id = ? AND status = 'pendente'",
            (projeto_id,),
        )
        cursor.execute(
            "UPDATE contratos SET status = 'concluido', data_conclusao = CURRENT_TIMESTAMP WHERE projeto_id = ?",
            (projeto_id,),
        )
        if projeto['freelancer_contratado_id']:
            cursor.execute('''
                UPDATE freelancers SET
                    projetos_concluidos = COALESCE(projetos_concluidos, 0) + 1,
                    total_projetos = COALESCE(total_projetos, 0) + 1
                WHERE id = ?
            ''', (projeto['freelancer_contratado_id'],))

    registrar_historico(
        cursor, projeto_id,
        evento='etapa_avancada',
        detalhe=f"Etapa alterada para {ETAPA_LABELS.get(nova_etapa, nova_etapa)}",
        usuario_id=session.get('user_id'),
        etapa_anterior=etapa_atual,
        etapa_nova=nova_etapa,
    )
    conn.commit()
    conn.close()
    flash(f'Projeto avançou para: {ETAPA_LABELS.get(nova_etapa, nova_etapa)}', 'sucesso')
    return redirect(url_for('workspace_projeto', projeto_id=projeto_id))


@app.route('/projeto/<int:projeto_id>/tarefa', methods=['POST'])
@login_required()
def adicionar_tarefa(projeto_id):
    titulo = (request.form.get('titulo') or '').strip()
    if not titulo:
        flash('Informe o título da tarefa.', 'erro')
        return redirect(url_for('workspace_projeto', projeto_id=projeto_id))

    conn = criar_conexao()
    cursor = conn.cursor()
    cursor.execute('SELECT * FROM projetos WHERE id = ?', (projeto_id,))
    projeto = cursor.fetchone()
    if not projeto or not usuario_pode_acessar_projeto(cursor, projeto):
        conn.close()
        flash('Acesso negado.', 'erro')
        return redirect(url_for('index'))

    cursor.execute('SELECT COALESCE(MAX(ordem), 0) + 1 AS prox FROM tarefas WHERE projeto_id = ?', (projeto_id,))
    ordem = cursor.fetchone()['prox']
    cursor.execute(
        'INSERT INTO tarefas (projeto_id, titulo, descricao, status, ordem) VALUES (?, ?, ?, ?, ?)',
        (projeto_id, titulo, request.form.get('descricao', ''), 'pendente', ordem),
    )
    recalcular_progresso_projeto(cursor, projeto_id)
    registrar_historico(
        cursor, projeto_id, 'tarefa_criada', f'Tarefa: {titulo}',
        usuario_id=session.get('user_id'),
    )
    conn.commit()
    conn.close()
    flash('Tarefa adicionada.', 'sucesso')
    return redirect(url_for('workspace_projeto', projeto_id=projeto_id))


@app.route('/projeto/<int:projeto_id>/tarefa/<int:tarefa_id>/status', methods=['POST'])
@login_required()
def atualizar_status_tarefa(projeto_id, tarefa_id):
    novo_status = request.form.get('status', 'pendente')
    if novo_status not in ('pendente', 'em_andamento', 'concluida', 'cancelada'):
        flash('Status inválido.', 'erro')
        return redirect(url_for('workspace_projeto', projeto_id=projeto_id))

    conn = criar_conexao()
    cursor = conn.cursor()
    cursor.execute('SELECT * FROM projetos WHERE id = ?', (projeto_id,))
    projeto = cursor.fetchone()
    if not projeto or not usuario_pode_acessar_projeto(cursor, projeto):
        conn.close()
        flash('Acesso negado.', 'erro')
        return redirect(url_for('index'))

    data_conc = 'CURRENT_TIMESTAMP' if novo_status == 'concluida' else 'NULL'
    cursor.execute(
        f'UPDATE tarefas SET status = ?, data_conclusao = {data_conc} WHERE id = ? AND projeto_id = ?',
        (novo_status, tarefa_id, projeto_id),
    )
    progresso = recalcular_progresso_projeto(cursor, projeto_id)
    registrar_historico(
        cursor, projeto_id, 'tarefa_atualizada',
        f'Tarefa #{tarefa_id} → {novo_status} (progresso {progresso}%)',
        usuario_id=session.get('user_id'),
    )
    conn.commit()
    conn.close()
    return redirect(url_for('workspace_projeto', projeto_id=projeto_id))


@app.route('/projeto/<int:projeto_id>/mensagem', methods=['POST'])
@login_required()
def mensagem_projeto(projeto_id):
    texto = (request.form.get('mensagem') or '').strip()
    if not texto:
        flash('Digite uma mensagem.', 'erro')
        return redirect(url_for('workspace_projeto', projeto_id=projeto_id))

    conn = criar_conexao()
    cursor = conn.cursor()
    cursor.execute('SELECT * FROM projetos WHERE id = ?', (projeto_id,))
    projeto = cursor.fetchone()
    if not projeto or not usuario_pode_acessar_projeto(cursor, projeto):
        conn.close()
        flash('Acesso negado.', 'erro')
        return redirect(url_for('index'))

    if session.get('empresa_id'):
        remetente_id, remetente_tipo = session['empresa_id'], 'empresa'
        destinatario_id = projeto['freelancer_contratado_id']
        destinatario_tipo = 'freelancer'
    else:
        remetente_id, remetente_tipo = session['freelancer_id'], 'freelancer'
        destinatario_id = projeto['empresa_id']
        destinatario_tipo = 'empresa'

    if not destinatario_id:
        conn.close()
        flash('Ainda não há contratado neste projeto.', 'aviso')
        return redirect(url_for('workspace_projeto', projeto_id=projeto_id))

    cursor.execute('''
        INSERT INTO mensagens
            (remetente_id, destinatario_id, remetente_tipo, destinatario_tipo, mensagem, projeto_id)
        VALUES (?, ?, ?, ?, ?, ?)
    ''', (remetente_id, destinatario_id, remetente_tipo, destinatario_tipo, texto, projeto_id))
    notificar_destinatario(
        cursor, destinatario_tipo, destinatario_id,
        'Nova mensagem no projeto',
        texto,
    )
    registrar_historico(
        cursor, projeto_id, 'mensagem', 'Nova mensagem no projeto',
        usuario_id=session.get('user_id'),
    )
    conn.commit()
    conn.close()
    flash('Mensagem enviada.', 'sucesso')
    return redirect(url_for('workspace_projeto', projeto_id=projeto_id))


@app.route('/projeto/<int:projeto_id>/arquivo', methods=['POST'])
@login_required()
def registrar_arquivo_projeto(projeto_id):
    """Registro de arquivo/link (upload físico pode ser ampliado depois)."""
    nome = (request.form.get('nome_arquivo') or '').strip()
    caminho = (request.form.get('caminho') or '').strip()
    if not nome:
        flash('Informe o nome do arquivo ou link.', 'erro')
        return redirect(url_for('workspace_projeto', projeto_id=projeto_id))

    conn = criar_conexao()
    cursor = conn.cursor()
    cursor.execute('SELECT * FROM projetos WHERE id = ?', (projeto_id,))
    projeto = cursor.fetchone()
    if not projeto or not usuario_pode_acessar_projeto(cursor, projeto):
        conn.close()
        flash('Acesso negado.', 'erro')
        return redirect(url_for('index'))

    cursor.execute('''
        INSERT INTO arquivos_projeto (projeto_id, usuario_id, nome_arquivo, caminho, tipo)
        VALUES (?, ?, ?, ?, ?)
    ''', (projeto_id, session.get('user_id'), nome, caminho or nome, request.form.get('tipo', 'link')))
    registrar_historico(
        cursor, projeto_id, 'arquivo', f'Arquivo/link: {nome}',
        usuario_id=session.get('user_id'),
    )
    conn.commit()
    conn.close()
    flash('Arquivo registrado no projeto.', 'sucesso')
    return redirect(url_for('workspace_projeto', projeto_id=projeto_id))


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
    print("=" * 50)
    print("ConectaServ - Plataforma de Freelancers")
    print("Versao: 2026-05-21-cadastro-fix")
    print("=" * 50)
    print("Servidor iniciado em: http://127.0.0.1:5000")
    print("Acesse na rede local com: http://SEU_IP_LOCAL:5000")
    print("=" * 50)
    app.run(host='0.0.0.0', port=5000, debug=True, use_reloader=False)
