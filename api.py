"""
API JSON central do ConectaServ — compartilhada entre site e app mobile.
Autenticação via sessão (web) ou token Bearer opaco (mobile).
"""

import sqlite3
import uuid
from functools import wraps
from flask import Blueprint, jsonify, make_response, request, session

from chatbot import responder_chat
from security import (
    criar_sessao_api,
    limitar_requisicao,
    senha_valida,
    usuario_por_token,
    verificar_senha,
)
from database.database import (
    criar_conexao,
    hash_password,
    normalizar_email,
    normalizar_documento,
    cnpj_valido,
    email_ja_cadastrado,
    cpf_ja_cadastrado,
    papel_do_email,
    inserir_perfil_freelancer,
    registrar_empresa,
    calcular_indicadores_empresa,
    aceitar_proposta_db,
    registrar_historico,
    encerrar_projeto,
    excluir_projeto,
    TAXA_EMPRESA_PERCENTUAL,
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


def _perfil_ids(user_id, role):
    dados = {'user_id': user_id, 'role': role, 'empresa_id': None, 'freelancer_id': None}
    conn = criar_conexao()
    cursor = conn.cursor()
    if role == 'empresa':
        cursor.execute('SELECT id FROM empresas WHERE user_id = ?', (user_id,))
        row = cursor.fetchone()
        if row:
            dados['empresa_id'] = row['id']
    elif role == 'freelancer':
        cursor.execute('SELECT id FROM freelancers WHERE user_id = ?', (user_id,))
        row = cursor.fetchone()
        if row:
            dados['freelancer_id'] = row['id']
    conn.close()
    return dados


def _usuario_sessao_ou_token():
    """Resolve o usuário. O token do app vale mais que o cookie do site, para as duas contas coexistirem."""
    auth = request.headers.get('Authorization', '')
    if auth.startswith('Bearer '):
        token = auth[7:].strip()
        sess = usuario_por_token(token)
        if sess:
            return _perfil_ids(sess['user_id'], sess['role'])

    if session.get('user_id'):
        return {
            'user_id': session['user_id'],
            'role': session.get('role') or session.get('tipo_usuario'),
            'empresa_id': session.get('empresa_id'),
            'freelancer_id': session.get('freelancer_id'),
        }
    return None


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
    ip = request.headers.get('X-Forwarded-For', request.remote_addr or 'local')
    if not limitar_requisicao('login:' + ip, maximo=8, janela=60):
        return jsonify({'ok': False, 'erro': 'Muitas tentativas. Aguarde um minuto.'}), 429

    dados = request.get_json(silent=True) or {}
    email = normalizar_email(dados.get('email', ''))
    senha = dados.get('senha', '')
    role = (dados.get('role') or '').strip().lower()

    if not email or not senha:
        return jsonify({'ok': False, 'erro': 'Email e senha obrigatórios'}), 400

    conn = criar_conexao()
    cursor = conn.cursor()
    cursor.execute(
        'SELECT id, email, role, senha, ativo FROM users WHERE LOWER(TRIM(email)) = ?',
        (email,),
    )
    user = cursor.fetchone()
    if not user or not user['ativo'] or not verificar_senha(user['senha'], senha):
        conn.close()
        return jsonify({'ok': False, 'erro': 'E-mail ou senha incorretos.'}), 401
    if role and user['role'] != role:
        conn.close()
        nome_papel = 'empresa' if user['role'] == 'empresa' else 'freelancer'
        return jsonify({
            'ok': False,
            'erro': f'Este e-mail é de uma conta de {nome_papel}. Entre como {nome_papel}.',
        }), 403

    perfil = {}
    if user['role'] == 'empresa':
        cursor.execute('SELECT id, nome_empresa FROM empresas WHERE user_id = ?', (user['id'],))
        emp = cursor.fetchone()
        if not emp:
            try:
                cursor.execute(
                    'SELECT id, nome_empresa FROM empresas WHERE LOWER(TRIM(email)) = ?',
                    (email,),
                )
                emp = cursor.fetchone()
                if emp:
                    cursor.execute('UPDATE empresas SET user_id = ? WHERE id = ?', (user['id'], emp['id']))
                    conn.commit()
            except sqlite3.Error:
                emp = None
        if emp:
            perfil = {'empresa_id': emp['id'], 'nome': emp['nome_empresa']}
    elif user['role'] == 'freelancer':
        cursor.execute('SELECT id, nome_completo FROM freelancers WHERE user_id = ?', (user['id'],))
        fr = cursor.fetchone()
        if not fr:
            try:
                cursor.execute(
                    'SELECT id, nome_completo FROM freelancers WHERE LOWER(TRIM(email)) = ?',
                    (email,),
                )
                fr = cursor.fetchone()
                if fr:
                    cursor.execute('UPDATE freelancers SET user_id = ? WHERE id = ?', (user['id'], fr['id']))
                    conn.commit()
            except sqlite3.Error:
                fr = None
        if fr:
            perfil = {'freelancer_id': fr['id'], 'nome': fr['nome_completo']}
    if not perfil:
        conn.close()
        return jsonify({'ok': False, 'erro': 'Perfil não encontrado para esta conta. Cadastre-se de novo com outro e-mail.'}), 404
    conn.close()

    token = criar_sessao_api(user['id'])

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


@api_bp.route('/projetos', methods=['GET'])
def api_listar_projetos():
    status = request.args.get('status', 'aberto')
    q = (request.args.get('q') or '').strip()
    conn = criar_conexao()
    cursor = conn.cursor()
    sql = '''
        SELECT p.id, p.titulo, p.descricao, p.categoria, p.presupuesto, p.prazo,
               p.status, p.etapa, p.progresso, p.data_criacao, e.nome_empresa
        FROM projetos p
        JOIN empresas e ON p.empresa_id = e.id
        WHERE p.status = ?
    '''
    params = [status]
    if q:
        like = f'%{q}%'
        sql += ' AND (p.titulo LIKE ? OR p.descricao LIKE ? OR e.nome_empresa LIKE ?)'
        params.extend([like, like, like])
    sql += ' ORDER BY p.data_criacao DESC LIMIT 50'
    cursor.execute(sql, params)
    itens = [dict(r) for r in cursor.fetchall()]
    conn.close()
    return jsonify({'ok': True, 'projetos': itens})


@api_bp.route('/projetos', methods=['POST'])
@api_login_required(roles=['empresa'])
def api_criar_projeto():
    empresa_id = request.api_user.get('empresa_id')
    if not empresa_id:
        return jsonify({'ok': False, 'erro': 'Entre de novo como empresa.'}), 401
    d = request.get_json(silent=True) or {}
    titulo = (d.get('titulo') or '').strip()
    descricao = (d.get('descricao') or '').strip()
    categoria = (d.get('categoria') or 'Outros').strip() or 'Outros'
    habilidades = (d.get('requisitos') or d.get('habilidades') or '').strip()
    orcamento = str(d.get('orcamento') or d.get('presupuesto') or '0').strip() or '0'
    prazo = str(d.get('prazo') or '').strip()
    nivel = (d.get('nivel') or 'Intermediário').strip()
    if not titulo or not descricao:
        return jsonify({'ok': False, 'erro': 'Informe o título e a descrição do projeto.'}), 400
    conn = criar_conexao()
    cursor = conn.cursor()
    cursor.execute('''
        INSERT INTO projetos (
            empresa_id, titulo, descricao, categoria, habilidades_requeridas,
            presupuesto, prazo, nivel_experiencia, status, etapa, progresso
        )
        VALUES (?, ?, ?, ?, ?, ?, ?, ?, 'aberto', 'publicado', 0)
    ''', (empresa_id, titulo, descricao, categoria, habilidades, orcamento, prazo, nivel))
    projeto_id = cursor.lastrowid
    try:
        registrar_historico(
            cursor, projeto_id, 'projeto_publicado',
            f'Projeto "{titulo}" publicado',
            usuario_id=request.api_user.get('user_id'),
            etapa_nova='publicado',
        )
    except Exception:
        pass
    conn.commit()
    conn.close()
    return jsonify({
        'ok': True,
        'projeto_id': projeto_id,
        'mensagem': 'Projeto publicado. A taxa de 10% só é cobrada da empresa quando uma proposta for aceita.',
    })


@api_bp.route('/projeto/<int:projeto_id>/proposta', methods=['POST'])
@api_login_required(roles=['freelancer'])
def api_enviar_proposta(projeto_id):
    freelancer_id = request.api_user.get('freelancer_id')
    if not freelancer_id:
        return jsonify({'ok': False, 'erro': 'Entre de novo como freelancer.'}), 401
    d = request.get_json(silent=True) or {}
    try:
        valor = float(d.get('valor') or d.get('valor_proposto') or 0)
        prazo = int(d.get('prazo') or d.get('prazo_dias') or 0)
    except (TypeError, ValueError):
        return jsonify({'ok': False, 'erro': 'Informe valor e prazo em números.'}), 400
    texto = (d.get('proposta') or d.get('texto') or '').strip()
    if valor <= 0 or prazo <= 0 or not texto:
        return jsonify({'ok': False, 'erro': 'Preencha valor, prazo em dias e a descrição da proposta.'}), 400
    conn = criar_conexao()
    cursor = conn.cursor()
    cursor.execute('SELECT id, status FROM projetos WHERE id = ?', (projeto_id,))
    projeto = cursor.fetchone()
    if not projeto:
        conn.close()
        return jsonify({'ok': False, 'erro': 'Projeto não encontrado.'}), 404
    if projeto['status'] != 'aberto':
        conn.close()
        return jsonify({'ok': False, 'erro': 'Esta vaga já foi encerrada.'}), 409
    cursor.execute(
        'SELECT id FROM propostas WHERE projeto_id = ? AND freelancer_id = ?',
        (projeto_id, freelancer_id),
    )
    if cursor.fetchone():
        conn.close()
        return jsonify({'ok': False, 'erro': 'Você já enviou uma proposta para este projeto.'}), 409
    cursor.execute(
        '''INSERT INTO propostas (projeto_id, freelancer_id, valor_proposto, prazo_dias, proposta)
           VALUES (?, ?, ?, ?, ?)''',
        (projeto_id, freelancer_id, valor, prazo, texto),
    )
    conn.commit()
    conn.close()
    return jsonify({'ok': True, 'mensagem': 'Proposta enviada.'})


@api_bp.route('/projeto/<int:projeto_id>/encerrar', methods=['POST'])
@api_login_required(roles=['empresa'])
def api_encerrar_projeto(projeto_id):
    empresa_id = request.api_user.get('empresa_id')
    conn = criar_conexao()
    cursor = conn.cursor()
    resultado = encerrar_projeto(cursor, projeto_id, empresa_id)
    if resultado == 'ok':
        conn.commit()
    conn.close()
    if resultado == 'ok':
        return jsonify({'ok': True, 'mensagem': 'Vaga encerrada. Ela não aparece mais para novos freelancers.'})
    if resultado == 'nao_aberto':
        return jsonify({'ok': False, 'erro': 'Só é possível encerrar vagas ainda abertas.'}), 409
    return jsonify({'ok': False, 'erro': 'Projeto não encontrado.'}), 404


@api_bp.route('/projeto/<int:projeto_id>/excluir', methods=['POST'])
@api_login_required(roles=['empresa'])
def api_excluir_projeto(projeto_id):
    empresa_id = request.api_user.get('empresa_id')
    conn = criar_conexao()
    cursor = conn.cursor()
    resultado = excluir_projeto(cursor, projeto_id, empresa_id)
    if resultado == 'ok':
        conn.commit()
    conn.close()
    if resultado == 'ok':
        return jsonify({'ok': True, 'mensagem': 'Projeto excluído.'})
    if resultado == 'em_andamento':
        return jsonify({'ok': False, 'erro': 'Não é possível excluir um projeto já contratado. Encerre a vaga só enquanto estiver aberta.'}), 409
    return jsonify({'ok': False, 'erro': 'Projeto não encontrado.'}), 404


@api_bp.route('/politica-taxa')
def api_politica_taxa():
    return jsonify({
        'ok': True,
        'percentual': TAXA_EMPRESA_PERCENTUAL,
        'resumo': (
            f'A empresa paga {TAXA_EMPRESA_PERCENTUAL}% de taxa de serviço sobre o valor da proposta aceita. '
            'O freelancer recebe o valor combinado. Não há mensalidade.'
        ),
    })


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

    try:
        cursor.execute(
            'SELECT id, titulo, status, ordem FROM tarefas WHERE projeto_id = ? ORDER BY ordem, id',
            (projeto_id,),
        )
        tarefas = [dict(r) for r in cursor.fetchall()]
    except sqlite3.Error:
        tarefas = []
    try:
        cursor.execute(
            '''SELECT evento, detalhe, etapa_nova, data_evento
               FROM historico_projeto WHERE projeto_id = ? ORDER BY data_evento DESC LIMIT 20''',
            (projeto_id,),
        )
        historico = [dict(r) for r in cursor.fetchall()]
    except sqlite3.Error:
        historico = []
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
    q = (request.args.get('q') or '').strip()
    conn = criar_conexao()
    cursor = conn.cursor()
    sql = '''
        SELECT id, nome_completo, especialidade, habilidades, cidade, estado,
               nota_media, hourly_rate, status
        FROM freelancers
        WHERE status = 'ativo'
    '''
    params = []
    if q:
        like = f'%{q}%'
        sql += ' AND (nome_completo LIKE ? OR especialidade LIKE ? OR habilidades LIKE ? OR cidade LIKE ?)'
        params.extend([like, like, like, like])
    sql += ' ORDER BY nota_media DESC LIMIT 50'
    cursor.execute(sql, params)
    itens = [dict(r) for r in cursor.fetchall()]
    conn.close()
    return jsonify({'ok': True, 'freelancers': itens})


@api_bp.route('/empresas')
def api_empresas():
    q = (request.args.get('q') or '').strip()
    conn = criar_conexao()
    cursor = conn.cursor()
    sql = 'SELECT id, nome_empresa, setor, cidade, estado, nota_media FROM empresas WHERE 1=1'
    params = []
    if q:
        like = f'%{q}%'
        sql += ' AND (nome_empresa LIKE ? OR setor LIKE ? OR cidade LIKE ?)'
        params.extend([like, like, like])
    sql += ' ORDER BY nome_empresa LIMIT 50'
    try:
        cursor.execute(sql, params)
        itens = [dict(r) for r in cursor.fetchall()]
    except sqlite3.Error:
        cursor.execute(
            'SELECT id, nome_empresa FROM empresas WHERE nome_empresa LIKE ? ORDER BY nome_empresa LIMIT 50',
            (f'%{q}%',),
        )
        itens = [dict(r) for r in cursor.fetchall()]
    conn.close()
    return jsonify({'ok': True, 'empresas': itens})


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

    try:
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
    except Exception:
        resposta = resposta or 'Posso te ensinar a criar a conta. Pergunte: como me cadastrar?'

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


@api_bp.route('/auth/cadastro-empresa', methods=['POST'])
def api_cadastro_empresa():
    ip = request.headers.get('X-Forwarded-For', request.remote_addr or 'local')
    if not limitar_requisicao('cad:' + ip, maximo=6, janela=120):
        return jsonify({'ok': False, 'erro': 'Muitas tentativas de cadastro. Aguarde.'}), 429
    d = request.get_json(silent=True) or {}
    nome = (d.get('nome_empresa') or '').strip()
    cnpj = (d.get('cnpj') or '').strip()
    email = (d.get('email') or '').strip()
    senha = d.get('senha') or ''
    if not nome or not email or not senha or not cnpj:
        return jsonify({'ok': False, 'erro': 'Preencha nome, e-mail, senha e CNPJ.'}), 400
    if not cnpj_valido(cnpj):
        return jsonify({'ok': False, 'erro': 'CNPJ inválido. Informe 14 números.'}), 400
    ok_s, msg_s = senha_valida(senha)
    if not ok_s:
        return jsonify({'ok': False, 'erro': msg_s}), 400
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
    ip = request.headers.get('X-Forwarded-For', request.remote_addr or 'local')
    if not limitar_requisicao('cad:' + ip, maximo=6, janela=120):
        return jsonify({'ok': False, 'erro': 'Muitas tentativas de cadastro. Aguarde.'}), 429
    d = request.get_json(silent=True) or {}
    nome = (d.get('nome_completo') or '').strip()
    email = normalizar_email(d.get('email', ''))
    senha = (d.get('senha') or '').strip()
    cpf = (d.get('cpf') or '').strip()
    if not all([nome, email, senha, cpf]):
        return jsonify({'ok': False, 'erro': 'Preencha nome, e-mail, senha e CPF.'}), 400
    if len(normalizar_documento(cpf)) != 11:
        return jsonify({'ok': False, 'erro': 'CPF inválido. Informe 11 números, sem pontos.'}), 400
    ok_s, msg_s = senha_valida(senha)
    if not ok_s:
        return jsonify({'ok': False, 'erro': msg_s}), 400
    conn = criar_conexao()
    cursor = conn.cursor()
    try:
        papel = papel_do_email(cursor, email)
        if papel == 'empresa':
            conn.close()
            return jsonify({'ok': False, 'erro': 'Este e-mail já é de uma empresa. Use outro e-mail para o freelancer.'}), 409
        if papel == 'freelancer' or email_ja_cadastrado(cursor, email):
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


@api_bp.route('/freelancer/<int:freelancer_id>')
def api_perfil_freelancer(freelancer_id):
    conn = criar_conexao()
    cursor = conn.cursor()
    cursor.execute('SELECT * FROM freelancers WHERE id = ?', (freelancer_id,))
    row = cursor.fetchone()
    conn.close()
    if not row:
        return jsonify({'ok': False, 'erro': 'Perfil não encontrado'}), 404
    dados = dict(row)
    for segredo in ('senha', 'cpf', 'user_id'):
        dados.pop(segredo, None)
    return jsonify({'ok': True, 'freelancer': dados})


@api_bp.route('/empresa/propostas')
@api_login_required(roles=['empresa'])
def api_empresa_propostas():
    empresa_id = request.api_user.get('empresa_id')
    if not empresa_id:
        return jsonify({'ok': False, 'erro': 'Entre de novo como empresa.'}), 401
    conn = criar_conexao()
    cursor = conn.cursor()
    cursor.execute('''
        SELECT p.id, p.projeto_id, p.valor_proposto, p.prazo_dias, p.status,
               proj.titulo AS projeto_titulo, f.nome_completo AS freelancer_nome
        FROM propostas p
        JOIN projetos proj ON proj.id = p.projeto_id
        JOIN freelancers f ON f.id = p.freelancer_id
        WHERE proj.empresa_id = ?
        ORDER BY p.id DESC
    ''', (empresa_id,))
    itens = [dict(r) for r in cursor.fetchall()]
    conn.close()
    return jsonify({'ok': True, 'propostas': itens})


@api_bp.route('/empresa/projetos')
@api_login_required(roles=['empresa'])
def api_empresa_projetos():
    empresa_id = request.api_user.get('empresa_id')
    if not empresa_id:
        return jsonify({'ok': False, 'erro': 'Entre de novo como empresa.'}), 401
    conn = criar_conexao()
    cursor = conn.cursor()
    cursor.execute('''
        SELECT id, titulo, status, categoria
        FROM projetos
        WHERE empresa_id = ?
        ORDER BY id DESC
    ''', (empresa_id,))
    itens = [dict(r) for r in cursor.fetchall()]
    conn.close()
    return jsonify({'ok': True, 'projetos': itens})


@api_bp.route('/freelancer/propostas')
@api_login_required(roles=['freelancer'])
def api_freelancer_propostas():
    freelancer_id = request.api_user.get('freelancer_id')
    if not freelancer_id:
        return jsonify({'ok': False, 'erro': 'Entre de novo como freelancer.'}), 401
    conn = criar_conexao()
    cursor = conn.cursor()
    cursor.execute('''
        SELECT p.id, p.projeto_id, p.valor_proposto, p.prazo_dias, p.status,
               proj.titulo AS projeto_titulo, e.nome_empresa
        FROM propostas p
        JOIN projetos proj ON proj.id = p.projeto_id
        JOIN empresas e ON e.id = proj.empresa_id
        WHERE p.freelancer_id = ?
        ORDER BY p.id DESC
    ''', (freelancer_id,))
    itens = [dict(r) for r in cursor.fetchall()]
    conn.close()
    return jsonify({'ok': True, 'propostas': itens})


@api_bp.route('/proposta/<int:proposta_id>/aceitar', methods=['POST'])
@api_login_required(roles=['empresa'])
def api_aceitar_proposta(proposta_id):
    empresa_id = request.api_user.get('empresa_id')
    if not empresa_id:
        return jsonify({'ok': False, 'erro': 'Entre de novo como empresa.'}), 401
    conn = criar_conexao()
    cursor = conn.cursor()
    try:
        resultado = aceitar_proposta_db(
            cursor, proposta_id, empresa_id, request.api_user.get('user_id'),
        )
        if resultado['status'] == 'nao_encontrada':
            conn.rollback()
            conn.close()
            return jsonify({'ok': False, 'erro': 'Proposta não encontrada.'}), 404
        conn.commit()
        conn.close()
    except Exception:
        try:
            conn.rollback()
            conn.close()
        except sqlite3.Error:
            pass
        return jsonify({'ok': False, 'erro': 'Não foi possível aceitar agora. Tente de novo.'}), 500
    return jsonify({'ok': True, 'projeto_id': resultado.get('projeto_id')})


@api_bp.route('/notificacoes')
@api_login_required()
def api_notificacoes():
    user_id = request.api_user.get('user_id')
    conn = criar_conexao()
    cursor = conn.cursor()
    try:
        cursor.execute('''
            SELECT id, titulo, mensagem, tipo, lida, data_criacao
            FROM notificacoes
            WHERE user_id = ?
            ORDER BY id DESC
            LIMIT 40
        ''', (user_id,))
        itens = [dict(r) for r in cursor.fetchall()]
        cursor.execute(
            'SELECT COUNT(*) FROM notificacoes WHERE user_id = ? AND COALESCE(lida, 0) = 0',
            (user_id,),
        )
        nao_lidas = cursor.fetchone()[0]
    except sqlite3.Error:
        itens = []
        nao_lidas = 0
    conn.close()
    return jsonify({'ok': True, 'nao_lidas': nao_lidas, 'itens': itens})


@api_bp.route('/notificacoes/lidas', methods=['POST'])
@api_login_required()
def api_notificacoes_lidas():
    user_id = request.api_user.get('user_id')
    conn = criar_conexao()
    cursor = conn.cursor()
    try:
        cursor.execute(
            'UPDATE notificacoes SET lida = 1 WHERE user_id = ?',
            (user_id,),
        )
        conn.commit()
    except sqlite3.Error:
        conn.rollback()
    conn.close()
    return jsonify({'ok': True})
