"""
API JSON central do ConectaServ — compartilhada entre site e app mobile.
Autenticação via sessão (web) ou token Bearer simples (mobile/demo).
"""

import sqlite3
import uuid
from functools import wraps
from flask import Blueprint, jsonify, make_response, request, session

from chatbot import responder_chat
from database.database import (
    criar_conexao,
    hash_password,
    normalizar_email,
    normalizar_documento,
    cnpj_valido,
    email_ja_cadastrado,
    cpf_ja_cadastrado,
    inserir_perfil_freelancer,
    registrar_empresa,
    calcular_indicadores_empresa,
    ETAPA_LABELS,
)

api_bp = Blueprint('api', __name__, url_prefix='/api/v1')


@api_bp.after_request
def cors_mobile(resp):
    """Permite o app mobile (PWA / outro host) chamar a API."""
    origem = request.headers.get('Origin', '*')
    resp.headers['Access-Control-Allow-Origin'] = origem if origem else '*'
    resp.headers['Access-Control-Allow-Headers'] = 'Content-Type, Authorization'
    resp.headers['Access-Control-Allow-Methods'] = 'GET, POST, OPTIONS'
    resp.headers['Access-Control-Allow-Credentials'] = 'true'
    return resp


@api_bp.before_request
def api_preflight():
    if request.method == 'OPTIONS':
        return make_response('', 204)


def _usuario_sessao_ou_token():
    """Resolve usuário logado pela sessão Flask ou header Authorization."""
    if session.get('user_id'):
        return {
            'user_id': session['user_id'],
            'role': session.get('role') or session.get('tipo_usuario'),
            'empresa_id': session.get('empresa_id'),
            'freelancer_id': session.get('freelancer_id'),
        }

    auth = request.headers.get('Authorization', '')
    if not auth.startswith('Bearer '):
        return None
    token = auth[7:].strip()
    # Token demo: base64 simples "user_id:role" não — usamos email:hash lookup na tabela users
    # Formato: Bearer <email>|<senha> apenas para demo PIM (trocar por JWT depois)
    if '|' not in token:
        return None
    email, senha = token.split('|', 1)
    conn = criar_conexao()
    cursor = conn.cursor()
    cursor.execute(
        'SELECT id, role FROM users WHERE LOWER(TRIM(email)) = ? AND senha = ? AND ativo = 1',
        (normalizar_email(email), hash_password(senha)),
    )
    user = cursor.fetchone()
    if not user:
        conn.close()
        return None
    dados = {'user_id': user['id'], 'role': user['role'], 'empresa_id': None, 'freelancer_id': None}
    if user['role'] == 'empresa':
        cursor.execute('SELECT id FROM empresas WHERE user_id = ?', (user['id'],))
        row = cursor.fetchone()
        if row:
            dados['empresa_id'] = row['id']
    elif user['role'] == 'freelancer':
        cursor.execute('SELECT id FROM freelancers WHERE user_id = ?', (user['id'],))
        row = cursor.fetchone()
        if row:
            dados['freelancer_id'] = row['id']
    conn.close()
    return dados


def api_login_required(roles=None):
    def decorator(f):
        @wraps(f)
        def wrapped(*args, **kwargs):
            user = _usuario_sessao_ou_token()
            if not user:
                return jsonify({'ok': False, 'erro': 'Não autenticado'}), 401
            if roles and user.get('role') not in roles:
                return jsonify({'ok': False, 'erro': 'Acesso negado'}), 403
            request.api_user = user
            return f(*args, **kwargs)
        return wrapped
    return decorator


@api_bp.route('/health')
def health():
    return jsonify({
        'ok': True,
        'servico': 'ConectaServ API',
        'versao': '1.0',
        'recursos': [
            '/api/v1/auth/login',
            '/api/v1/projetos',
            '/api/v1/empresa/indicadores',
            '/api/v1/projeto/<id>',
            '/api/v1/freelancers',
            '/api/v1/chat',
        ],
    })


@api_bp.route('/auth/login', methods=['POST'])
def api_login():
    dados = request.get_json(silent=True) or {}
    email = normalizar_email(dados.get('email', ''))
    senha = dados.get('senha', '')
    role = (dados.get('role') or '').strip().lower()

    if not email or not senha:
        return jsonify({'ok': False, 'erro': 'Email e senha obrigatórios'}), 400

    conn = criar_conexao()
    cursor = conn.cursor()
    cursor.execute(
        'SELECT id, email, role FROM users WHERE LOWER(TRIM(email)) = ? AND senha = ? AND ativo = 1',
        (email, hash_password(senha)),
    )
    user = cursor.fetchone()
    if not user:
        conn.close()
        return jsonify({'ok': False, 'erro': 'Credenciais inválidas'}), 401
    if role and user['role'] != role:
        conn.close()
        return jsonify({'ok': False, 'erro': 'Portal incorreto para este usuário'}), 403

    perfil = {}
    if user['role'] == 'empresa':
        cursor.execute('SELECT id, nome_empresa FROM empresas WHERE user_id = ?', (user['id'],))
        emp = cursor.fetchone()
        if emp:
            perfil = {'empresa_id': emp['id'], 'nome': emp['nome_empresa']}
    elif user['role'] == 'freelancer':
        cursor.execute('SELECT id, nome_completo FROM freelancers WHERE user_id = ?', (user['id'],))
        fr = cursor.fetchone()
        if fr:
            perfil = {'freelancer_id': fr['id'], 'nome': fr['nome_completo']}
    conn.close()

    # Token demo para mobile (substituir por JWT no PIM final)
    token = f"{email}|{senha}"

    return jsonify({
        'ok': True,
        'token': token,
        'user': {
            'id': user['id'],
            'email': user['email'],
            'role': user['role'],
            **perfil,
        },
    })


@api_bp.route('/projetos')
def api_listar_projetos():
    status = request.args.get('status', 'aberto')
    conn = criar_conexao()
    cursor = conn.cursor()
    cursor.execute('''
        SELECT p.id, p.titulo, p.descricao, p.categoria, p.presupuesto, p.prazo,
               p.status, p.etapa, p.progresso, p.data_criacao, e.nome_empresa
        FROM projetos p
        JOIN empresas e ON p.empresa_id = e.id
        WHERE p.status = ?
        ORDER BY p.data_criacao DESC
        LIMIT 50
    ''', (status,))
    itens = [dict(r) for r in cursor.fetchall()]
    conn.close()
    return jsonify({'ok': True, 'projetos': itens})


@api_bp.route('/projeto/<int:projeto_id>')
def api_detalhe_projeto(projeto_id):
    conn = criar_conexao()
    cursor = conn.cursor()
    cursor.execute('''
        SELECT p.*, e.nome_empresa
        FROM projetos p
        JOIN empresas e ON p.empresa_id = e.id
        WHERE p.id = ?
    ''', (projeto_id,))
    projeto = cursor.fetchone()
    if not projeto:
        conn.close()
        return jsonify({'ok': False, 'erro': 'Projeto não encontrado'}), 404

    cursor.execute(
        'SELECT id, titulo, status, ordem FROM tarefas WHERE projeto_id = ? ORDER BY ordem, id',
        (projeto_id,),
    )
    tarefas = [dict(r) for r in cursor.fetchall()]
    cursor.execute(
        '''SELECT evento, detalhe, etapa_nova, data_evento
           FROM historico_projeto WHERE projeto_id = ? ORDER BY data_evento DESC LIMIT 20''',
        (projeto_id,),
    )
    historico = [dict(r) for r in cursor.fetchall()]
    conn.close()

    dados = dict(projeto)
    dados['etapa_label'] = ETAPA_LABELS.get(dados.get('etapa') or '', dados.get('etapa'))
    return jsonify({
        'ok': True,
        'projeto': dados,
        'tarefas': tarefas,
        'historico': historico,
    })


@api_bp.route('/empresa/indicadores')
@api_login_required(roles=['empresa'])
def api_indicadores_empresa():
    empresa_id = request.api_user.get('empresa_id')
    if not empresa_id:
        return jsonify({'ok': False, 'erro': 'Empresa não encontrada'}), 404
    conn = criar_conexao()
    cursor = conn.cursor()
    indicadores = calcular_indicadores_empresa(cursor, empresa_id)
    conn.close()
    return jsonify({'ok': True, 'indicadores': indicadores})


@api_bp.route('/freelancers')
def api_freelancers():
    conn = criar_conexao()
    cursor = conn.cursor()
    cursor.execute('''
        SELECT id, nome_completo, especialidade, habilidades, cidade, estado,
               nota_media, hourly_rate, status
        FROM freelancers
        WHERE status = 'ativo'
        ORDER BY nota_media DESC
        LIMIT 50
    ''')
    itens = [dict(r) for r in cursor.fetchall()]
    conn.close()
    return jsonify({'ok': True, 'freelancers': itens})


def _sessao_chat(sid=None):
    sid = (sid or request.headers.get('X-Chat-Session') or request.args.get('sessao_id') or '').strip()
    if not sid:
        sid = session.get('chat_sessao') or str(uuid.uuid4())
        session['chat_sessao'] = sid
    return sid


@api_bp.route('/chat', methods=['POST'])
def api_chat():
    """Chatbot usado pelo site e pelo aplicativo mobile."""
    dados = request.get_json(silent=True) or {}
    texto = (dados.get('mensagem') or dados.get('message') or '').strip()
    canal = (dados.get('canal') or 'web').strip()[:20]
    if not texto:
        return jsonify({'ok': False, 'erro': 'Mensagem vazia'}), 400

    sessao_id = _sessao_chat((dados.get('sessao_id') or '').strip())
    user = _usuario_sessao_ou_token()
    user_id = user['user_id'] if user else None
    resposta = responder_chat(texto)

    conn = criar_conexao()
    cursor = conn.cursor()
    cursor.execute(
        '''INSERT INTO chat_mensagens (sessao_id, user_id, origem, mensagem, canal)
           VALUES (?, ?, 'usuario', ?, ?)''',
        (sessao_id, user_id, texto, canal),
    )
    cursor.execute(
        '''INSERT INTO chat_mensagens (sessao_id, user_id, origem, mensagem, canal)
           VALUES (?, ?, 'bot', ?, ?)''',
        (sessao_id, user_id, resposta, canal),
    )
    conn.commit()
    conn.close()

    return jsonify({
        'ok': True,
        'resposta': resposta,
        'sessao_id': sessao_id,
        'bot': 'ConectaServ Assistente',
    })


@api_bp.route('/chat/historico')
def api_chat_historico():
    sessao_id = (request.args.get('sessao_id') or session.get('chat_sessao') or '').strip()
    if not sessao_id:
        return jsonify({'ok': True, 'mensagens': []})
    conn = criar_conexao()
    cursor = conn.cursor()
    cursor.execute(
        '''SELECT origem, mensagem, data_envio
           FROM chat_mensagens WHERE sessao_id = ?
           ORDER BY id ASC LIMIT 40''',
        (sessao_id,),
    )
    mensagens = [dict(r) for r in cursor.fetchall()]
    conn.close()
    return jsonify({'ok': True, 'sessao_id': sessao_id, 'mensagens': mensagens})


def _senha_curta(senha):
    if not senha or len(senha.strip()) < 6:
        return 'A senha precisa ter pelo menos 6 caracteres.'
    return ''


@api_bp.route('/auth/cadastro-empresa', methods=['POST'])
def api_cadastro_empresa():
    d = request.get_json(silent=True) or {}
    nome = (d.get('nome_empresa') or '').strip()
    cnpj = (d.get('cnpj') or '').strip()
    email = (d.get('email') or '').strip()
    senha = d.get('senha') or ''
    if not nome or not email or not senha or not cnpj:
        return jsonify({'ok': False, 'erro': 'Preencha nome, e-mail, senha e CNPJ.'}), 400
    if not cnpj_valido(cnpj):
        return jsonify({'ok': False, 'erro': 'CNPJ inválido. Informe 14 números.'}), 400
    curta = _senha_curta(senha)
    if curta:
        return jsonify({'ok': False, 'erro': curta}), 400
    try:
        resultado = registrar_empresa(
            nome, cnpj, email, senha,
            (d.get('telefone') or '').strip(),
            (d.get('descricao') or '').strip(),
            (d.get('setor') or 'Tecnologia').strip(),
        )
    except Exception:
        return jsonify({'ok': False, 'erro': 'Não foi possível salvar. Tente outro e-mail ou CNPJ.'}), 400
    if resultado.get('status') == 'ok':
        return jsonify({'ok': True, 'mensagem': 'Conta criada. Entre com o mesmo e-mail e senha.'})
    if resultado.get('status') == 'duplicado':
        return jsonify({'ok': False, 'erro': 'Este e-mail ou CNPJ já possui conta. Toque em Já tenho conta.'}), 409
    if resultado.get('status') == 'freelancer':
        return jsonify({'ok': False, 'erro': 'Este e-mail já é de um freelancer. Entre como freelancer.'}), 409
    return jsonify({'ok': False, 'erro': 'Não foi possível cadastrar.'}), 400


@api_bp.route('/auth/cadastro-freelancer', methods=['POST'])
def api_cadastro_freelancer():
    d = request.get_json(silent=True) or {}
    nome = (d.get('nome_completo') or '').strip()
    email = normalizar_email(d.get('email', ''))
    senha = (d.get('senha') or '').strip()
    cpf = (d.get('cpf') or '').strip()
    if not all([nome, email, senha, cpf]):
        return jsonify({'ok': False, 'erro': 'Preencha nome, e-mail, senha e CPF.'}), 400
    if len(normalizar_documento(cpf)) != 11:
        return jsonify({'ok': False, 'erro': 'CPF inválido. Informe 11 números, sem pontos.'}), 400
    curta = _senha_curta(senha)
    if curta:
        return jsonify({'ok': False, 'erro': curta}), 400
    conn = criar_conexao()
    cursor = conn.cursor()
    try:
        if email_ja_cadastrado(cursor, email):
            conn.close()
            return jsonify({'ok': False, 'erro': 'Este e-mail já possui conta. Toque em Já tenho conta.'}), 409
        if cpf_ja_cadastrado(cursor, cpf):
            conn.close()
            return jsonify({'ok': False, 'erro': 'Este CPF já possui conta. Toque em Já tenho conta.'}), 409
        senha_hash = hash_password(senha)
        cursor.execute(
            'INSERT INTO users (email, senha, role, ativo) VALUES (?, ?, ?, 1)',
            (email, senha_hash, 'freelancer'),
        )
        user_id = cursor.lastrowid
        inserir_perfil_freelancer(
            cursor, user_id, nome, email, senha_hash, d.get('telefone') or '', cpf,
            d.get('cidade') or '', d.get('estado') or '', d.get('especialidade') or 'Tecnologia',
            d.get('habilidades') or '', d.get('biografia') or '', d.get('hourly_rate') or '0',
        )
        conn.commit()
        conn.close()
        return jsonify({'ok': True, 'mensagem': 'Conta criada. Entre com o mesmo e-mail e senha.'})
    except sqlite3.IntegrityError:
        try:
            conn.rollback()
            conn.close()
        except sqlite3.Error:
            pass
        return jsonify({'ok': False, 'erro': 'E-mail ou CPF já existentes. Toque em Já tenho conta.'}), 409
    except Exception:
        try:
            conn.rollback()
            conn.close()
        except sqlite3.Error:
            pass
        return jsonify({'ok': False, 'erro': 'Não foi possível salvar o cadastro. Tente novamente.'}), 400
