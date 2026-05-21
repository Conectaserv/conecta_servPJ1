# ConectaServ no Render — passo a passo (opção A)

Tempo estimado: **30 a 60 minutos** na primeira vez.

---

## Parte 1 — Enviar o projeto para o GitHub (sem programar no terminal)

O Render precisa puxar o código de um repositório. O jeito mais fácil é pelo site do GitHub.

### 1.1 Criar conta GitHub (se não tiver)

https://github.com/signup — é grátis.

### 1.2 Criar repositório vazio

1. GitHub → botão **+** → **New repository**
2. Nome: `conectaserv` (ou outro)
3. Deixe **Private** se não quiser código público
4. **Não** marque “Add README”
5. **Create repository**

### 1.3 Enviar arquivos pelo navegador

Na página do repositório novo:

1. **uploading an existing file** (link azul) ou **Add file** → **Upload files**
2. No Windows, abra a pasta:
   `C:\Users\Gabriel_0)\Desktop\conecta_servPJ1`
3. Arraste para o GitHub:

**Arquivos da raiz:**
- `app.py`
- `wsgi.py`
- `textos_pt.py`
- `requirements.txt`
- `render.yaml`
- `.gitignore`
- `.env.example` (só modelo, sem senha real)

**Pastas inteiras:**
- `templates`
- `static`
- `database` (com `database.py` e `conecta_serv.db` se quiser os cadastros)
- `utils`

**Não envie:**
- `.env`
- `.secret_key`
- `venv`
- `test_*.py`, `check_*.py`, `temp_app.py`

4. Role até o fim → **Commit changes**

Pronto: código no GitHub.

---

## Parte 2 — Criar o site no Render

### 2.1 Conta Render

https://dashboard.render.com/register — pode entrar com conta Google/GitHub.

### 2.2 Novo Web Service

1. **Dashboard** → **New +** → **Web Service**
2. **Build and deploy from a Git repository** → **Next**
3. Conecte **GitHub** (autorize o Render)
4. Escolha o repositório **conectaserv**
5. Preencha:

| Campo | Valor |
|--------|--------|
| **Name** | `conectaserv` |
| **Region** | Oregon ou São Paulo (se aparecer) |
| **Branch** | `main` |
| **Runtime** | Python 3 |
| **Build Command** | `pip install -r requirements.txt` |
| **Start Command** | `gunicorn --bind 0.0.0.0:$PORT wsgi:application` |
| **Instance Type** | **Free** |

### 2.3 Variáveis de ambiente (importante)

Role até **Environment Variables** → **Add Environment Variable**:

| Key | Value |
|-----|--------|
| `SECRET_KEY` | Cole uma chave longa (veja abaixo) |
| `FLASK_ENV` | `production` |
| `PYTHON_VERSION` | `3.11.0` |

**Gerar SECRET_KEY no seu PC (PowerShell):**

```powershell
python -c "import secrets; print(secrets.token_hex(32))"
```

Copie o resultado e cole em `SECRET_KEY`.

**E-mail (opcional)** — só se quiser envio real de e-mails:

| Key | Value |
|-----|--------|
| `SMTP_HOST` | `smtp.hostinger.com` |
| `SMTP_PORT` | `587` |
| `SMTP_USER` | seu e-mail Hostinger |
| `SMTP_PASS` | senha do e-mail |
| `SMTP_FROM` | mesmo e-mail |
| `SMTP_TLS` | `1` |

### 2.4 Publicar

Clique **Create Web Service**.

Aguarde o build (barra de log). Quando ficar **Live**, aparece a URL:

`https://conectaserv.onrender.com` (o nome pode variar).

Abra no navegador e teste: início, cadastro, login.

---

## Parte 3 — Testar

1. Página inicial abre?
2. Cadastro empresa ou freelancer grava?
3. Login funciona?
4. Botão **Libras** aparece? (precisa de internet)

**Primeira visita no plano grátis:** pode demorar **30–60 segundos** se o site estava “dormindo”.

---

## Parte 4 — Link na Hostinger (opcional)

Na pasta `public_html` da Hostinger, use o `index.html` que redireciona ou mostra o link.

Edite e troque:

`https://SEU_APP.onrender.com`

pela URL real que o Render mostrou.

---

## Problemas comuns

### Build falhou (vermelho nos logs)

- Confira se `requirements.txt` e `wsgi.py` foram para o GitHub.
- Build Command exatamente: `pip install -r requirements.txt`

### Site abre mas erro 502

- Start Command deve ser:
  `gunicorn --bind 0.0.0.0:$PORT wsgi:application`

### Login não mantém / desloga sempre

- Falta `SECRET_KEY` nas variáveis do Render.

### Cadastros sumiram depois de um deploy

- No plano grátis o disco às vezes zera. Solução: manter backup do `conecta_serv.db` no PC e reenviar ao GitHub quando necessário, ou usar VPS depois.

### Logs

Render → seu serviço → **Logs** (aba ao vivo).

---

## Atualizar o site depois

1. Altere arquivos no PC
2. Envie de novo no GitHub (upload ou commit)
3. Render faz **deploy automático** em 2–5 min

---

## Checklist rápido

- [ ] GitHub com `app.py`, `wsgi.py`, `requirements.txt`, pastas `templates`, `static`, `database`, `utils`
- [ ] Render Web Service criado (Free)
- [ ] `SECRET_KEY` definida
- [ ] Start Command com `$PORT`
- [ ] URL Live testada no celular e no PC

Quando chegar na etapa que travar (GitHub, build ou login), diga em qual passo e o que aparece na tela.
