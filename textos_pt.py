"""
Textos em português do ConectaServ (interface e mensagens do sistema).
Altere aqui para corrigir ortografia e padronizar frases em todo o site.
"""
from types import SimpleNamespace


def _ns(dados):
    """Converte dict aninhado em SimpleNamespace para uso nos templates Jinja."""
    if isinstance(dados, dict):
        return SimpleNamespace(**{chave: _ns(valor) for chave, valor in dados.items()})
    return dados


# --- Mensagens flash e erros (app.py) ---
MSG = SimpleNamespace(
    CAMPOS_OBRIGATORIOS='Preencha todos os campos obrigatórios.',
    CNPJ_INVALIDO='CNPJ inválido. Informe os 14 números do CNPJ.',
    CPF_CADASTRADO='CPF já cadastrado!',
    CNPJ_CADASTRADO='CNPJ já cadastrado!',
    EMAIL_CADASTRADO='E-mail já cadastrado! Use outro e-mail ou faça login.',
    EMAIL_FREELANCER='Este e-mail já é de um freelancer. Use o login/cadastro de freelancer.',
    EMAIL_SENHA_OBRIGATORIOS='E-mail e senha são obrigatórios.',
    EMAIL_NOVA_SENHA='Preencha o e-mail e a nova senha.',
    EMAIL_NAO_ENCONTRADO='E-mail não encontrado para este tipo de conta.',
    SENHA_REDEFINIDA='Senha redefinida com sucesso. Faça login com a nova senha.',
    LOGOUT_SUCESSO='Você foi desconectado com sucesso.',
    LOGIN_EMPRESA='Faça login como empresa para continuar.',
    LOGIN_NECESSARIO='Você precisa estar logado para acessar esta página.',
    SEM_PERMISSAO='Você não tem permissão para acessar esta página.',
    APENAS_FREELANCER='Apenas freelancers podem acessar esta página.',
    APENAS_EMPRESA='Apenas empresas podem acessar esta página.',
    APENAS_EMPRESA_MSG='Apenas empresas podem enviar mensagens a freelancers.',
    APENAS_EMPRESA_AVALIAR='Apenas empresas podem avaliar freelancers.',
    APENAS_FREELANCER_AVALIAR='Apenas freelancers podem avaliar empresas.',
    ACESSO_NEGADO='Acesso negado.',
    PROJETO_NAO_ENCONTRADO='Projeto não encontrado.',
    PROPOSTA_NAO_ENCONTRADA='Proposta não encontrada ou acesso negado.',
    SERVICO_NAO_ENCONTRADO='Serviço não encontrado.',
    FREELANCER_NAO_ENCONTRADO='Freelancer não encontrado.',
    MENSAGEM_VAZIA='Digite sua mensagem antes de enviar.',
    MENSAGEM_ENVIADA='Mensagem enviada com sucesso!',
    PERFIL_EMPRESA_OK='Perfil da empresa atualizado com sucesso!',
    PERFIL_OK='Perfil atualizado com sucesso!',
    PROPOSTA_ENVIADA='Proposta enviada com sucesso!',
    PROJETO_CRIADO='Projeto criado com sucesso!',
    PROPOSTA_ACEITA='Proposta aceita! O freelancer foi notificado por e-mail com o prazo e os dados de contato.',
    NOTAS_INVALIDAS='Preencha todas as notas de avaliação entre 1 e 5.',
    AVALIACAO_FREELANCER_OK='Avaliação do freelancer registrada com sucesso!',
    AVALIACAO_EMPRESA_OK='Avaliação da empresa registrada com sucesso!',
    AVALIACAO_NAO_ENCONTRADA_FL='Não foi possível encontrar o projeto ou freelancer para avaliação.',
    AVALIACAO_NAO_ENCONTRADA_EM='Não foi possível encontrar o projeto ou empresa para avaliação.',
    ERRO_SALVAR_CADASTRO='Erro ao salvar cadastro. Reinicie o servidor e tente de novo.',
    BANCO_BLOQUEADO=(
        'Não foi possível salvar: o banco está em uso. Feche o arquivo conecta_serv.db no editor, '
        'reinicie o servidor e tente novamente.'
    ),
    EMAIL_SENHA_INCORRETOS='E-mail ou senha incorretos.',
    CONTA_DESATIVADA='Conta desativada. Entre em contato com o suporte.',
    PERFIL_NAO_ENCONTRADO='Perfil não encontrado para esta conta. Cadastre-se novamente.',
    PERFIL_EMPRESA_NAO='Perfil de empresa não encontrado. Cadastre-se como empresa.',
    PERFIL_FREELANCER_NAO='Perfil de freelancer não encontrado. Cadastre-se como freelancer.',
    EMAIL_E_EMPRESA='Este e-mail é de uma conta de empresa. Use o login de empresa.',
    EMAIL_E_FREELANCER='Este e-mail é de uma conta de freelancer. Use o login de freelancer.',
)


def cadastro_sucesso(email):
    return f'Cadastro salvo com sucesso para {email}! Use o botão abaixo para entrar.'


def conta_existe_email(nome_empresa):
    return (
        f'Este e-mail já está cadastrado na empresa "{nome_empresa}". '
        f'Não precisa cadastrar de novo — faça login.'
    )


def conta_existe_cnpj(nome_empresa, email):
    return (
        f'Este CNPJ já está cadastrado na empresa "{nome_empresa}" ({email}). '
        f'Use outro CNPJ ou faça login.'
    )


def erro_salvar_cadastro(erro):
    return f'Não foi possível salvar o cadastro: {erro}'


def proposta_aceita_email_erro(msg_email):
    return f'Proposta aceita, mas houve problema ao enviar o e-mail: {msg_email}'


# --- Textos de interface (templates) ---
_TEXTOS = {
    'site': {
        'nome': 'ConectaServ',
        'titulo_padrao': 'ConectaServ — Marketplace de freelancers tech',
        'rodape_descricao': 'Conectando empresas a freelancers especializados em tecnologia.',
        'direitos': '© 2026 ConectaServ. Todos os direitos reservados.',
    },
    'nav': {
        'inicio': 'Início',
        'projetos': 'Projetos',
        'freelancers': 'Freelancers',
        'sobre': 'Sobre',
        'entrar': 'Entrar',
        'cadastrar': 'Cadastrar',
        'empresa': 'Empresa',
        'freelancer': 'Freelancer',
        'dashboard': 'Meu dashboard',
        'criar_projeto': 'Criar projeto',
        'sair': 'Sair',
        'acessibilidade': 'Acessibilidade',
        'aumentar_fonte': 'Aumentar fonte',
        'diminuir_fonte': 'Diminuir fonte',
        'alto_contraste': 'Alto contraste',
        'config_acessibilidade': 'Configurações de acessibilidade',
        'libras': 'Libras',
        'libras_titulo': 'Abrir tradutor VLibras (Língua Brasileira de Sinais)',
    },
    'footer': {
        'links_rapidos': 'Links rápidos',
        'buscar_projetos': 'Buscar projetos',
        'buscar_freelancers': 'Buscar freelancers',
        'sou_empresa': 'Sou empresa',
        'sou_freelancer': 'Sou freelancer',
        'contato': 'Contato',
        'redes': 'Redes sociais',
    },
    'comum': {
        'obrigatorio': '*',
        'selecione': 'Selecione...',
        'enviar': 'Enviar',
        'salvar': 'Salvar',
        'cancelar': 'Cancelar',
        'voltar': 'Voltar',
        'ver_detalhes': 'Ver detalhes',
        'placeholder_email': 'seu@email.com',
        'placeholder_senha': 'Sua senha',
        'senha_minima': 'Mínimo de 6 caracteres',
        'ja_tem_conta': 'Já tem conta?',
        'nao_tem_conta': 'Não tem conta?',
        'entrar': 'Entrar',
        'ir_login': 'Ir para o login',
        'esqueceu_senha': 'Esqueceu a senha?',
    },
    'cadastro_empresa': {
        'titulo_pagina': 'Cadastro empresa — ConectaServ',
        'titulo': 'Cadastro de empresa',
        'subtitulo': 'Preencha os dados da sua empresa para começar.',
        'nome': 'Nome da empresa',
        'nome_ph': 'Nome da sua empresa',
        'cnpj': 'CNPJ',
        'cnpj_ph': '00.000.000/0001-00',
        'email': 'E-mail corporativo',
        'senha': 'Senha',
        'telefone': 'Telefone',
        'telefone_ph': '(11) 99999-9999',
        'setor': 'Setor de atuação',
        'descricao': 'Descrição da empresa',
        'descricao_ph': 'Fale um pouco sobre sua empresa...',
        'botao': 'Cadastrar empresa',
        'cadastrar_link': 'Cadastrar empresa',
    },
    'cadastro_freelancer': {
        'titulo_pagina': 'Cadastro freelancer — ConectaServ',
        'titulo': 'Cadastro freelancer',
        'subtitulo': 'Junte-se à plataforma de freelancers tech.',
        'nome': 'Nome completo',
        'nome_ph': 'Seu nome completo',
        'cpf': 'CPF',
        'cpf_ph': '000.000.000-00',
        'telefone': 'Telefone',
        'telefone_ph': '(00) 00000-0000',
        'email': 'E-mail',
        'senha': 'Senha',
        'cidade': 'Cidade',
        'cidade_ph': 'São Paulo',
        'estado': 'Estado',
        'especialidade': 'Especialidade principal',
        'area_ph': 'Selecione sua área de atuação',
        'habilidades': 'Habilidades (separadas por vírgula)',
        'habilidades_ph': 'Python, JavaScript, React, Node.js',
        'biografia': 'Biografia / apresentação',
        'biografia_ph': 'Fale sobre sua experiência e habilidades...',
        'valor_hora': 'Valor da hora (R$)',
        'valor_hora_ph': 'Ex.: 100',
        'botao': 'Cadastrar',
        'fazer_login': 'Fazer login',
    },
    'login_empresa': {
        'titulo_pagina': 'Login empresa — ConectaServ',
        'titulo': 'Login empresa',
        'subtitulo': 'Acesse sua conta de empresa',
        'email': 'E-mail corporativo',
        'senha': 'Senha',
        'botao': 'Entrar',
    },
    'login_freelancer': {
        'titulo_pagina': 'Login freelancer — ConectaServ',
        'titulo': 'Login freelancer',
        'subtitulo': 'Acesse sua conta de profissional',
        'email': 'E-mail',
        'senha': 'Senha',
        'botao': 'Entrar',
    },
    'recuperar_senha': {
        'titulo': 'Recuperar senha',
        'subtitulo_empresa': 'Informe seu e-mail e escolha uma nova senha para acessar sua conta de empresa.',
        'subtitulo_freelancer': 'Informe seu e-mail e escolha uma nova senha para acessar sua conta de freelancer.',
        'email': 'E-mail',
        'nova_senha': 'Nova senha',
        'nova_senha_ph': 'Digite a nova senha',
        'botao': 'Redefinir senha',
    },
    'index': {
        'titulo_pagina': 'ConectaServ — Início',
        'hero_titulo': 'Conecte-se aos melhores profissionais de tecnologia',
        'hero_texto': (
            'A plataforma que conecta empresas a freelancers especializados em '
            'desenvolvimento, infraestrutura, segurança e muito mais.'
        ),
        'buscar_projetos': 'Buscar projetos',
        'freelancers_ativos': 'Freelancers ativos',
        'projetos_abertos': 'Projetos abertos',
        'satisfacao': 'Satisfação',
        'valor_projetos': 'Valor em projetos',
        'destaque': 'Projetos em destaque',
        'ver_todos': 'Ver todos os projetos',
        'como_funciona': 'Como funciona',
        'passo1_titulo': '1. Busque',
        'passo1_texto': 'Encontre projetos ou profissionais que atendam às suas necessidades',
        'passo2_titulo': '2. Conecte',
        'passo2_texto': 'Entre em contato e combine os detalhes do projeto',
        'passo3_titulo': '3. Execute',
        'passo3_texto': 'Realize o trabalho e receba sua avaliação',
        'areas': 'Áreas de atuação',
        'cta_titulo': 'Pronto para começar?',
        'cta_texto': 'Junte-se a milhares de empresas e profissionais que já utilizam o ConectaServ',
        'cadastrar_empresa': 'Cadastrar empresa',
        'cadastrar_freelancer': 'Cadastrar freelancer',
    },
    'dashboard_empresa': {
        'bem_vindo': 'Bem-vindo',
        'subtitulo': 'Gerencie seus projetos e propostas',
        'buscar_freelancers': 'Buscar freelancers',
        'criar_projeto': 'Criar projeto',
        'meus_projetos': 'Meus projetos',
        'propostas': 'Propostas recebidas',
        'sem_projetos': 'Você ainda não criou projetos.',
        'sem_propostas': 'Nenhuma proposta recebida ainda.',
    },
    'dashboard_freelancer': {
        'bem_vindo': 'Bem-vindo',
        'subtitulo': 'Encontre projetos e acompanhe suas propostas',
        'buscar_projetos': 'Buscar projetos',
        'projetos_disp': 'projetos disponíveis',
        'minhas_propostas': 'Minhas propostas',
        'sem_propostas': 'Você ainda não enviou propostas.',
        'buscar_link': 'Buscar projetos',
    },
    'perfil': {
        'sem_descricao': 'Este freelancer ainda não adicionou uma descrição.',
        'portfolio_vazio': 'Portfólio não disponibilizado.',
        'sem_avaliacoes': 'Este freelancer ainda não recebeu avaliações.',
        'avaliacoes': 'Avaliações',
    },
    'busca': {
        'sem_projetos': 'Nenhum projeto encontrado com os filtros selecionados.',
        'sem_freelancers': 'Nenhum freelancer encontrado com os filtros selecionados.',
        'sem_termo_proj': 'Nenhum projeto encontrado para',
        'sem_termo_fl': 'Nenhum freelancer encontrado para',
    },
    'acessibilidade': {
        'titulo_pagina': 'Acessibilidade — ConectaServ',
        'titulo': 'Acessibilidade',
        'subtitulo': 'Personalize sua experiência na plataforma',
        'fonte_titulo': 'Tamanho da fonte',
        'fonte_texto': 'Aumente ou diminua o tamanho do texto em toda a plataforma',
        'contraste_titulo': 'Alto contraste',
        'contraste_texto': 'Ative o modo de alto contraste para melhor visualização',
        'leitor_titulo': 'Leitor de tela',
        'leitor_texto': 'Otimizado para usuários de leitores de tela',
        'linguagem_titulo': 'Linguagem simplificada',
        'linguagem_texto': 'Use textos mais simples e fáceis de entender',
        'libras_titulo': 'Tradução para Libras (VLibras)',
        'libras_texto': (
            'O ConectaServ usa o VLibras, ferramenta oficial do governo federal, '
            'para traduzir trechos do site para a Língua Brasileira de Sinais.'
        ),
        'libras_como_usar': 'Como usar',
        'libras_passo1': 'Clique em Libras na barra superior ou no ícone flutuante do VLibras (canto da tela).',
        'libras_passo2': 'Selecione com o mouse o texto que deseja traduzir.',
        'libras_passo3': 'Acompanhe a tradução em Libras no painel do tradutor.',
        'libras_nota': 'É necessário estar conectado à internet. A tradução automática pode não cobrir termos muito técnicos.',
        'libras_abrir': 'Abrir tradutor VLibras',
        'dicas_titulo': 'Dicas de acessibilidade',
        'dica1': 'Use os botões A+ e A− para ajustar o tamanho do texto',
        'dica2': 'O modo de alto contraste melhora a leitura para pessoas com baixa visão',
        'dica3': 'Todos os botões e links têm descrições acessíveis',
        'dica4': 'A plataforma é totalmente navegável pelo teclado',
        'dica5': 'Imagens têm textos alternativos para leitores de tela',
        'dica6': 'Use o botão Libras ou o VLibras para traduzir trechos do site para Libras',
        'voltar': 'Voltar ao início',
    },
    'setores': {
        'tecnologia': 'Tecnologia',
        'financeiro': 'Financeiro',
        'saude': 'Saúde',
        'educacao': 'Educação',
        'varejo': 'Varejo',
        'industria': 'Indústria',
        'servicos': 'Serviços',
        'outro': 'Outro',
    },
}

TEXTOS = _ns(_TEXTOS)


def obter_textos():
    """Retorna textos para templates."""
    return TEXTOS
