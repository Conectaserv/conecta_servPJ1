# ConectaServ

**Conecta você. Resolve para você.**

Marketplace acadêmico que liga empresas a freelancers de tecnologia: cadastro, vagas, propostas, painel, acompanhamento do projeto e app no celular (PWA).

Repositório: [https://github.com/Conectaserv/conecta_servPJ1](https://github.com/Conectaserv/conecta_servPJ1)

## O que o sistema faz

- Cadastro e login de **empresa** (CNPJ) e **freelancer** (CPF)
- Publicação de projetos, envio de proposta e aceite
- Encerrar vaga ou excluir projeto ainda aberto
- Busca por nome de freelancer, empresa ou projeto
- Notas, avaliações e painel da empresa
- Mensagens, notificações e workspace após a contratação
- Política de taxa (10% para a empresa só quando aceita a proposta)
- Chat de ajuda e página de acessibilidade (fonte, contraste, Libras)
- App instalável em `/app`

## Tecnologias

| Camada | Tecnologia |
| --- | --- |
| Backend | Python 3.11, Flask 3, Gunicorn |
| Banco | SQLite |
| Front | HTML, CSS, JavaScript (Jinja) |
| App | PWA em `/app` + API `/api/v1` |
| Hospedagem | Render |

## Como rodar no computador

Requisito: Python 3.11 ou superior.

```bash
git clone https://github.com/Conectaserv/conecta_servPJ1.git
cd conecta_servPJ1
python -m venv venv
venv\Scripts\activate
pip install -r requirements.txt
python app.py
```

Abra [http://127.0.0.1:5000](http://127.0.0.1:5000).

No celular da mesma rede: `http://SEU_IP_LOCAL:5000/app`.

## Vitrine de demonstração

Na primeira inicialização o banco recebe profissionais, notas, empresas e vagas de exemplo (títulos começando com `Vitrine:`), para a home e a lista de freelancers não ficarem vazias.

Contas de demonstração (senha `Demo#2026`):

| Tipo | E-mail |
| --- | --- |
| Empresa | `novaera@conectaserv.demo` |
| Freelancer | `ana.costa@conectaserv.demo` |

Você também pode criar contas reais pelo site ou pelo app.

## API (site e app)

Prefixo: `/api/v1`

Exemplos: `GET /health`, `POST /auth/login`, `GET /projetos`, `POST /projetos`, `POST /projeto/<id>/proposta`, `GET /freelancers`, `POST /chat`.

Login do app usa token (não envia a senha em toda requisição).

## Deploy no Render

O serviço lê este repositório (`main`). Depois de um `git push`, o Render faz o build.

- Build: `pip install -r requirements.txt`
- Start: `gunicorn --bind 0.0.0.0:$PORT wsgi:application`
- Variável: `SECRET_KEY` (o Render pode gerar)

No plano gratuito o SQLite some se o serviço dormir ou for recriado. Disco persistente (`DATABASE_PATH`) só em plano pago.

## Estrutura

```
conecta_servPJ1/
├── app.py                 # rotas do site
├── api.py                 # API JSON (web e celular)
├── wsgi.py                # entrada de produção
├── security.py            # senha, token e limite de tentativas
├── chatbot.py             # assistente de ajuda
├── database/
│   └── database.py        # SQLite, tabelas e vitrine
├── templates/             # páginas HTML
├── static/                # CSS, JS, imagens, PWA
├── requirements.txt
└── README.md
```

## Segurança (resumo)

- Senha com hash (PBKDF2); hashes antigos SHA-256 ainda entram
- Sessão HTTP-only no site; token opaco no app
- Limite de tentativas de login e cadastro
- Páginas de freelancer e empresa só com a conta certa

## Trabalho acadêmico

Projeto de PIM — Análise e Desenvolvimento de Sistemas.

Desenvolvido por **João Pedro Ramos de Souza**.

Uso acadêmico. Não há gateway de pagamento real: a taxa de 10% é registrada na política da plataforma, sem cobrança bancária.
