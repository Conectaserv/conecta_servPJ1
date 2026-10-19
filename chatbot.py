"""
Chatbot ConectaServ — API usada pelo site e pelo app mobile.

Funciona sem chave externa (FAQ + dados do banco).
Se OPENAI_API_KEY estiver no ambiente, tenta complementar a resposta.
"""

import json
import os
import re
import urllib.error
import urllib.request
from unicodedata import normalize

from database.database import criar_conexao

FAQ = [
    {
        'chaves': ['oi', 'ola', 'olá', 'bom dia', 'boa tarde', 'boa noite', 'eae', 'hey'],
        'resposta': 'Olá! Sou a assistente do ConectaServ 2.0. Posso ajudar com cadastro, projetos, propostas, painel da empresa, workspace e o app. O que você precisa?',
    },
    {
        'chaves': ['o que e', 'o que é', 'conectaserv', 'plataforma', 'sobre'],
        'resposta': 'O ConectaServ e um marketplace que conecta empresas a freelancers de tecnologia. Nesta versao 2.0 o ciclo vai alem da contratacao: propostas, contrato, desenvolvimento, entrega, pagamento e avaliacao.',
    },
    {
        'chaves': ['cadastr', 'criar conta', 'registrar', 'sign up'],
        'resposta': 'Há dois cadastros: Empresa (CNPJ) e Freelancer (CPF). No site use Cadastrar no menu. No app mobile, abra a aba Conta. Depois do login você acessa o painel correspondente.',
    },
    {
        'chaves': ['login', 'entrar', 'senha', 'acessar'],
        'resposta': 'Use Entrar → Empresa ou Entrar → Freelancer. No app, informe e-mail, senha e o tipo de conta. Esqueceu a senha? Há recuperação em Esqueceu a senha.',
    },
    {
        'chaves': ['proposta', 'orcamento', 'orçamento', 'enviar proposta'],
        'resposta': 'Freelancer abre um projeto aberto e envia proposta (valor, prazo e texto). A empresa vê tudo no painel, aceita uma proposta e o restante é recusado automaticamente. Aí nasce o contrato e o workspace.',
    },
    {
        'chaves': ['painel', 'dashboard', 'indicador', 'kpi', 'estatistic'],
        'resposta': 'O painel da empresa mostra projetos publicados, em andamento e concluídos, propostas, valores movimentados, tempo médio para contratar, freelancers mais contratados, categorias, avaliações e taxa de conclusão.',
    },
    {
        'chaves': ['workspace', 'acompanh', 'tarefa', 'etapa', 'progresso', 'ciclo'],
        'resposta': 'Depois da contratacao o projeto continua no Workspace: etapas (inicio, desenvolvimento, entrega, aprovacao, pagamento, avaliacao), tarefas com %, mensagens, arquivos, prazo restante, contrato e historico.',
    },
    {
        'chaves': ['pagament', 'contrato', 'pagar'],
        'resposta': 'Ao aceitar a proposta o sistema gera contrato e um pagamento pendente. Quando o projeto avança até a etapa de pagamento/conclusão, o status é atualizado na plataforma (demonstração acadêmica, sem gateway bancário).',
    },
    {
        'chaves': ['avaliac', 'nota', 'estrela', 'feedback'],
        'resposta': 'Empresa avalia o freelancer (qualidade, prazo, comunicação, portfólio). Freelancer avalia a empresa (satisfação, profissionalismo). As médias aparecem nos perfis e no painel.',
    },
    {
        'chaves': ['app', 'aplicativo', 'celular', 'mobile', 'android', 'ios'],
        'resposta': 'O app usa a mesma API do site (/api/v1). Abra /app no celular ou instale o PWA. Login, projetos, freelancers, indicadores e este chat ficam sincronizados com o site.',
    },
    {
        'chaves': ['api', 'integrac', 'json', 'token'],
        'resposta': 'API central em /api/v1: health, auth/login, projetos, projeto/{id}, empresa/indicadores, freelancers e chat. Autenticação: sessão no site ou Bearer email|senha no mobile (demo PIM).',
    },
    {
        'chaves': ['libras', 'acessib', 'contraste', 'fonte'],
        'resposta': 'Há barra de acessibilidade (A+/A−, contraste, VLibras). Também existe a página Acessibilidade para salvar preferências.',
    },
    {
        'chaves': ['ajuda', 'help', 'como funciona', 'passo'],
        'resposta': 'Fluxo: 1) cadastre-se 2) empresa publica projeto 3) freelancer envia proposta 4) empresa aceita 5) workspace acompanha 6) entrega, pagamento e avaliação. Pergunte qualquer etapa.',
    },
    {
        'chaves': ['contato', 'email', 'suporte', 'falar'],
        'resposta': 'Suporte: conectaservconectavoceresolvep@gmail.com. Você também pode usar as mensagens do projeto no workspace.',
    },
]


def _normalizar(texto):
    texto = (texto or '').lower().strip()
    texto = normalize('NFD', texto)
    return ''.join(c for c in texto if not (0x300 <= ord(c) <= 0x36F))


def _contexto_banco():
    try:
        conn = criar_conexao()
        cursor = conn.cursor()
        cursor.execute("SELECT COUNT(*) AS n FROM freelancers WHERE status = 'ativo'")
        freelancers = cursor.fetchone()['n']
        cursor.execute("SELECT COUNT(*) AS n FROM projetos WHERE status = 'aberto'")
        projetos = cursor.fetchone()['n']
        cursor.execute('SELECT COUNT(*) AS n FROM empresas')
        empresas = cursor.fetchone()['n']
        conn.close()
        return (
            f'Agora na plataforma: {empresas} empresas, {freelancers} freelancers ativos '
            f'e {projetos} projetos abertos.'
        )
    except Exception:
        return ''


def _responder_faq(mensagem):
    texto = _normalizar(mensagem)
    if re.search(r'\b(quantos?|qtd|numero|número)\b.*(freelancer|projeto|empresa)', texto) or \
            re.search(r'\b(freelancer|projeto|empresa).*(quantos?|qtd)\b', texto):
        extra = _contexto_banco()
        return extra or 'Ainda não consegui consultar os números do banco.'

    melhor, pontos = None, 0
    for item in FAQ:
        score = sum(1 for chave in item['chaves'] if _normalizar(chave) in texto)
        if score > pontos:
            melhor, pontos = item, score
    if melhor and pontos:
        extra = _contexto_banco() if 'conectaserv' in texto or 'plataforma' in texto else ''
        return (melhor['resposta'] + (' ' + extra if extra else '')).strip()
    return None


def _openai_complemento(mensagem, fallback):
    chave = os.environ.get('OPENAI_API_KEY', '').strip()
    if not chave:
        return None
    payload = {
        'model': os.environ.get('OPENAI_MODEL', 'gpt-4o-mini'),
        'temperature': 0.4,
        'messages': [
            {
                'role': 'system',
                'content': (
                    'Você é a assistente do ConectaServ, marketplace brasileiro de freelancers de tech. '
                    'Responda em português, curto e claro. Não invente pagamentos reais.'
                ),
            },
            {'role': 'user', 'content': mensagem},
        ],
    }
    req = urllib.request.Request(
        'https://api.openai.com/v1/chat/completions',
        data=json.dumps(payload).encode('utf-8'),
        headers={
            'Content-Type': 'application/json',
            'Authorization': f'Bearer {chave}',
        },
        method='POST',
    )
    try:
        with urllib.request.urlopen(req, timeout=12) as resp:
            data = json.loads(resp.read().decode('utf-8'))
        texto = data['choices'][0]['message']['content'].strip()
        return texto or fallback
    except (urllib.error.URLError, KeyError, TimeoutError, json.JSONDecodeError):
        return None


def responder_chat(mensagem):
    mensagem = (mensagem or '').strip()
    if not mensagem:
        return 'Digite uma pergunta para eu ajudar.'
    if len(mensagem) > 800:
        return 'Mensagem longa demais. Resuma em até 800 caracteres.'

    faq = _responder_faq(mensagem)
    ia = _openai_complemento(mensagem, faq)
    if ia:
        return ia
    if faq:
        return faq
    extra = _contexto_banco()
    return (
        'Ainda não entendi. Tente perguntar sobre cadastro, login, propostas, painel, '
        'workspace, pagamentos, avaliações, API ou o app. ' + extra
    ).strip()
